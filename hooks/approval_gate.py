#!/usr/bin/env python3
"""PreToolUse hook: ask the user before merges, pushes that can reach a
protected branch, and release-manager runs outside plan mode (AGENTS.md §9).

Reads one JSON object on stdin. Prints nothing (no opinion) or one JSON object
with permissionDecision "ask". Never emits allow or deny and always exits 0.
Text taken from the inspected command is only ever parsed, never executed.
"""

import json
import os
import sys

SECTION = "AGENTS.md §9"
GIT_TIMEOUT = 5  # seconds, per git subprocess

SHELLS = ("bash", "sh", "zsh", "dash", "ksh")
UNPARSED = (
    "Approval gate could not parse the command (it mentions git or gh): "
    "confirm it manually"
)
NOT_PLAN = (
    "release-manager is not in plan mode: deploying needs your approval (%s)"
    % SECTION
)

# git push options (git 2.50, `git push -h`). Long names are without "--".
LONG_FLAGS = frozenset(
    "verbose quiet delete tags porcelain force force-with-lease "
    "force-if-includes thin set-upstream progress verify follow-tags signed "
    "atomic ipv4 ipv6".split()
)
LONG_VALUE = frozenset("push-option receive-pack exec recurse-submodules".split())
LONG_WIDE = frozenset("all branches mirror prune repo".split())  # dest unknown
SHORT_FLAGS = frozenset("vqdnfu46")

# git options accepted before the subcommand (git 2.50, `git --help`).
GIT_GLOBAL_FLAGS = frozenset(
    "-v --version -h --help --html-path --man-path --info-path -p --paginate "
    "-P --no-pager --no-replace-objects --no-lazy-fetch --no-optional-locks "
    "--no-advice --bare --literal-pathspecs --glob-pathspecs "
    "--noglob-pathspecs --icase-pathspecs".split()
)
GIT_GLOBAL_VALUE = ("-c", "--namespace", "--super-prefix", "--config-env")

# Scope markers in the parsed command list: ( ... ) and $( ... ) restore the
# working directory tracked by analyze() when they close.
_OPEN = object()
_CLOSE = object()


class Ask(Exception):
    """Carries the reason of an ask decision."""


class ParseError(Exception):
    pass


def undetermined(why):
    return Ask("Push destination could not be determined (%s): %s" % (SECTION, why))


# --- Shell tokenizer ---------------------------------------------------------


class Word(object):
    __slots__ = ("text", "dyn")

    def __init__(self, text, dyn):
        self.text = text
        self.dyn = dyn  # contains a shell expansion ($ or a substitution)


class _Cmd(object):
    """The simple command and the word being built by the parser."""

    def __init__(self):
        self.words = []
        self.skip = False  # next word is a redirection target
        self._reset()

    def _reset(self):
        self.buf = []
        self.has = False
        self.dyn = False

    def add(self, text, dyn=False):
        self.buf.append(text)
        self.has = True
        if dyn:
            self.dyn = True

    def end_word(self):
        if self.has:
            if self.skip:
                self.skip = False
            else:
                self.words.append(Word("".join(self.buf), self.dyn))
        self._reset()

    def end(self, out):
        self.end_word()
        if self.words:
            out.append(self.words)
        self.words = []
        self.skip = False


class _Parser(object):
    """Splits a command line into simple commands (lists of Word).

    Nothing is expanded or executed. Substitutions ($(...) and backticks) are
    parsed as commands of their own; heredoc bodies are skipped as data.
    """

    def __init__(self, text):
        self.s = text
        self.i = 0
        self.pending = []  # heredocs whose body starts at the next newline

    def commands(self, out, term):
        s, n = self.s, len(self.s)
        cmd = _Cmd()
        while True:
            if self.i >= n:
                if term:
                    raise ParseError("unterminated substitution")
                cmd.end(out)
                return
            c = s[self.i]
            if c in " \t":
                cmd.end_word()
                self.i += 1
            elif c == "\n":
                cmd.end(out)
                self.i += 1
                self._skip_heredocs()
            elif c in ";&|":
                cmd.end(out)
                self.i += 1
            elif c == "(":
                cmd.end(out)
                out.append(_OPEN)
                self.i += 1
            elif c == ")":
                cmd.end(out)
                self.i += 1
                if term == ")":
                    return
                out.append(_CLOSE)
            elif c == "`":
                self.i += 1
                if term == "`":
                    cmd.end(out)
                    return
                self._scope(out, "`")
                cmd.add("$()", True)
            elif c == "'":
                j = s.find("'", self.i + 1)
                if j < 0:
                    raise ParseError("unterminated single quote")
                cmd.add(s[self.i + 1 : j])
                self.i = j + 1
            elif c == '"':
                self._dquote(out, cmd)
            elif c == "\\":
                if self.i + 1 < n:
                    if s[self.i + 1] != "\n":
                        cmd.add(s[self.i + 1])
                    self.i += 2
                else:
                    self.i += 1
            elif c == "$":
                self._dollar(out, cmd)
            elif c in "<>":
                self._redirect(cmd)
            else:
                cmd.add(c)
                self.i += 1

    def _scope(self, out, term):
        out.append(_OPEN)
        self.commands(out, term)
        out.append(_CLOSE)

    def _dollar(self, out, cmd):
        s, n = self.s, len(self.s)
        if s.startswith("$((", self.i):  # arithmetic: skip to the matching ))
            depth, j = 0, self.i + 1
            while j < n:
                if s[j] == "(":
                    depth += 1
                elif s[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            else:
                raise ParseError("unterminated arithmetic expansion")
            self.i = j + 1
            cmd.add("$(())", True)
        elif s.startswith("$(", self.i):
            self.i += 2
            self._scope(out, ")")
            cmd.add("$()", True)
        elif s.startswith("$'", self.i):  # ANSI-C quoting: a quoted string
            j = self.i + 2
            while j < n and s[j] != "'":
                j += 2 if s[j] == "\\" else 1
            if j >= n:
                raise ParseError("unterminated $'' string")
            cmd.add(s[self.i + 2 : j])
            self.i = j + 1
        elif s.startswith('$"', self.i):  # locale string: plain double quotes
            self.i += 1
            self._dquote(out, cmd)
        else:
            self.i += 1
            cmd.add("$", True)

    def _dquote(self, out, cmd):
        s, n = self.s, len(self.s)
        self.i += 1
        cmd.has = True
        while True:
            if self.i >= n:
                raise ParseError("unterminated double quote")
            c = s[self.i]
            if c == '"':
                self.i += 1
                return
            if c == "$":
                self._dollar(out, cmd)
            elif c == "`":
                self.i += 1
                self._scope(out, "`")
                cmd.add("$()", True)
            elif c == "\\" and s[self.i + 1 : self.i + 2] in ("$", "`", '"', "\\", "\n"):
                if s[self.i + 1] != "\n":
                    cmd.add(s[self.i + 1])
                self.i += 2
            else:
                cmd.add(c)
                self.i += 1

    def _redirect(self, cmd):
        s, n = self.s, len(self.s)
        c = s[self.i]
        if cmd.has and not cmd.dyn and "".join(cmd.buf).isdigit():
            cmd._reset()  # the fd number of `2>file`
        else:
            cmd.end_word()
        if s.startswith("<<<", self.i):
            self.i += 3
            cmd.skip = True
        elif s.startswith("<<", self.i):
            self.i += 2
            dash = s.startswith("-", self.i)
            if dash:
                self.i += 1
            self._heredoc_delimiter(dash)
        else:
            self.i += 1
            if c == ">" and s.startswith(">", self.i):
                self.i += 1
            if s[self.i : self.i + 1] in ("&", "|"):
                self.i += 1
            cmd.skip = not s.startswith("(", self.i)  # <(...) is not a target

    def _heredoc_delimiter(self, dash):
        s, n = self.s, len(self.s)
        j = self.i
        while j < n and s[j] in " \t":
            j += 1
        chars = []
        while j < n and s[j] not in " \t\n;&|()<>":
            ch = s[j]
            if ch in "'\"":
                k = s.find(ch, j + 1)
                if k < 0:
                    raise ParseError("unterminated heredoc delimiter")
                chars.append(s[j + 1 : k])
                j = k + 1
            elif ch == "\\" and j + 1 < n:
                chars.append(s[j + 1])
                j += 2
            else:
                chars.append(ch)
                j += 1
        self.i = j
        self.pending.append(("".join(chars), dash))

    def _skip_heredocs(self):
        s, n = self.s, len(self.s)
        for delim, dash in self.pending:
            while self.i < n:
                j = s.find("\n", self.i)
                end = n if j < 0 else j
                line = s[self.i : end]
                self.i = end + 1
                if (line.lstrip("\t") if dash else line) == delim:
                    break
        self.pending = []


def parse(text):
    out = []
    _Parser(text).commands(out, None)
    return out


# --- Rules -------------------------------------------------------------------


def _base(word):
    return word.text.rsplit("/", 1)[-1]


def _join(cur, word):
    """Directory reached by `cd <word>` / `git -C <word>` from `cur`, or None."""
    if word.dyn or word.text == "-":
        return None
    path = word.text
    if path.startswith("~"):
        home = os.environ.get("HOME")
        if not home or not (path == "~" or path.startswith("~/")):
            return None
        path = home + path[1:]
    if os.path.isabs(path):
        return path
    return None if cur is None else os.path.join(cur, path)


def _cd(cur, args):
    args = [w for w in args if w.text not in ("-L", "-P", "-e", "-@", "--")]
    if not args:
        return os.environ.get("HOME") or None
    return _join(cur, args[0])


def _git_env(text):
    return text.startswith(("GIT_DIR=", "GIT_WORK_TREE="))


def analyze(text, cur):
    """Raise Ask when `text` merges or can push to a protected branch."""
    saved = []
    for words in parse(text):
        if words is _OPEN:
            saved.append(cur)
            continue
        if words is _CLOSE:
            cur = saved.pop() if saved else cur
            continue
        first = words[0].text
        if first == "cd":
            cur = _cd(cur, words[1:])
            continue
        if first in ("pushd", "popd"):
            cur = None
            continue
        for i, word in enumerate(words):
            name = _base(word)
            if name == "git":
                _git(words, i, cur, any(_git_env(w.text) for w in words[:i]))
            elif name == "gh":
                _gh(words, i)
            elif name in SHELLS:
                _shell(words, i, cur)
            elif name == "eval":
                analyze(" ".join(w.text for w in words[i + 1 :]), cur)


def _shell(words, i, cur):
    """`sh -c` with a short-flag group containing c: later words are scripts."""
    for j in range(i + 1, len(words)):
        t = words[j].text
        if t.startswith("-") and not t.startswith("--") and "c" in t[1:]:
            for script in words[j + 1 :]:
                analyze(script.text, cur)
            return


def _gh(words, i):
    rest = [w.text for w in words[i + 1 :]]
    merge = Ask("Merging is the user's call (%s): gh pr merge" % SECTION)
    if "pr" in rest and "merge" in rest[rest.index("pr") + 1 :]:
        raise merge
    if "api" in rest:
        merge = Ask("Merging is the user's call (%s): gh api merge call" % SECTION)
        for arg in rest[rest.index("api") + 1 :]:
            segments = arg.replace("?", "/").replace("#", "/").split("/")
            if "merge" in segments or "merges" in segments:
                raise merge
            if "mergePullRequest" in arg or "enablePullRequestAutoMerge" in arg:
                raise merge


def _git(words, i, cur, lost):
    """`lost`: the repository is not the cwd's (GIT_DIR, --git-dir, ...)."""
    unknown = False  # an option we do not know may hide the subcommand
    j, n = i + 1, len(words)
    while j < n:
        t = words[j].text
        if t == "-C":
            if j + 1 >= n:
                return
            cur = _join(cur, words[j + 1])
            j += 2
        elif t in GIT_GLOBAL_VALUE:
            j += 2
        elif t in ("--git-dir", "--work-tree"):
            lost = True
            j += 2
        elif t.startswith("--git-dir=") or t.startswith("--work-tree="):
            lost = True
            j += 1
        elif t.startswith("-"):
            unknown = unknown or not (
                t in GIT_GLOBAL_FLAGS or t.startswith("--exec-path")
            )
            j += 1
        else:
            break
    else:
        return
    if not unknown:
        if words[j].text == "push":
            _push(words[j + 1 :], None if lost else cur)
        return
    for k in range(j, n):  # unknown option: do not let it hide a push
        if words[k].text == "push":
            _push(words[k + 1 :], None if lost else cur)
            return


def _push_options(args):
    """Return (dry_run, unknown, wide, positionals, tags) for `git push` args."""
    dry = unknown = wide = tags = False
    pos = []
    done = False
    i = 0
    while i < len(args):
        word = args[i]
        t = word.text
        i += 1
        if done or not t.startswith("-") or t == "-":
            pos.append(word)
        elif t == "--":
            done = True
        elif t.startswith("--"):
            name, eq, _value = t[2:].partition("=")
            if name == "dry-run" and not eq:
                dry = True
            elif name in LONG_FLAGS:
                tags = tags or name == "tags"
            elif name in LONG_VALUE:
                i += 0 if eq else 1
            elif name in LONG_WIDE:
                wide = True
                i += 1 if name == "repo" and not eq else 0
            elif (
                name.startswith("no-")
                and not eq
                and name[3:] in LONG_FLAGS | LONG_VALUE | LONG_WIDE
            ):
                pass  # a --no- form never takes a value
            else:
                unknown = True
        else:
            for k, ch in enumerate(t[1:], 1):
                if ch in SHORT_FLAGS:
                    dry = dry or ch == "n"
                elif ch == "o":
                    i += 0 if k + 1 < len(t) else 1  # value attached or next word
                    break
                else:
                    unknown = True
                    break
    return dry, unknown, wide, pos, tags


def _push(args, cur):
    dry, unknown, wide, pos, tags = _push_options(args)
    if dry and not unknown:
        return  # a dry run changes nothing
    if unknown:
        raise undetermined("unknown push option")
    if any(w.dyn for w in args):
        raise undetermined("shell expansion in the push arguments")
    if wide:
        raise undetermined("--all, --branches, --mirror, --prune or --repo")
    refspecs = pos[1:]  # pos[0] is the remote
    dests = []
    current = False
    if not refspecs:
        if tags:
            return  # a tags-only push is not a branch push
        current = True
    k = 0
    while k < len(refspecs):
        word = refspecs[k]
        k += 1
        t = word.text
        if t == "tag" and k < len(refspecs):
            k += 1
            continue
        if any(ch in t for ch in "*?[{}"):
            raise undetermined("refspec with a wildcard or brace expansion")
        if t.startswith("+"):
            t = t[1:]
        if ":" in t:
            t = t.split(":", 1)[1]
            if not t:
                raise undetermined("refspec with an empty destination")
        if t in ("HEAD", "@"):
            current = True
        elif t.startswith("refs/tags/"):
            continue
        elif t.startswith("refs/heads/"):
            dests.append(t[len("refs/heads/") :])
        else:
            dests.append(t)
            if t.startswith("heads/") and len(t) > len("heads/"):
                # git may resolve `heads/<name>` to refs/heads/<name>
                dests.append(t[len("heads/") :])
    if not dests and not current:
        return
    for name in dests:
        if name in ("main", "master"):
            raise _protected(name)
    if cur is None:
        raise undetermined("repository directory unknown")
    rc, out = _git_run(cur, "rev-parse", "--show-toplevel")
    top = out.strip()
    if rc != 0 or not top:
        raise undetermined("directory is not a resolvable git repository")
    if not refspecs and _push_config_widens(cur, pos[0].text if pos else None):
        raise undetermined("push.default=matching or remote.<name>.push is set")
    if current:
        rc, out = _git_run(cur, "symbolic-ref", "-q", "HEAD")
        head = out.strip()
        if rc != 0 or not head:
            raise undetermined("detached HEAD")
        branch = head[len("refs/heads/") :] if head.startswith("refs/heads/") else head
        dests.append(branch)
        if not refspecs:
            rc, out = _git_run(cur, "config", "--get", "branch.%s.merge" % branch)
            if rc == 0:
                up = out.strip()
                dests.append(up[len("refs/heads/") :] if up.startswith("refs/heads/") else up)
            elif rc != 1:
                raise undetermined("could not read the upstream branch")
    names = _protected_names(top, cur)
    for name in dests:
        if name in names:
            raise _protected(name)


def _push_config_widens(cur, remote):
    """True when configuration makes a refspec-less push reach more branches."""
    rc, out = _git_run(
        cur, "config", "--get-regexp", r"^(push\.default|remote\..*\.push)$"
    )
    if rc == 1:
        return False
    if rc != 0:
        return True  # unreadable configuration: fail closed
    for line in out.splitlines():
        key, _, value = line.partition(" ")
        if key == "push.default" and value.strip().lower() == "matching":
            return True
        if key.startswith("remote.") and key.endswith(".push"):
            if remote is None or key[len("remote.") : -len(".push")] == remote:
                return True
    return False


def _protected(name):
    return Ask("Push can reach protected branch '%s' (%s)" % (name, SECTION))


def _protected_names(top, cur):
    names = {"main", "master"} | _declared(top)
    # Default branch of every remote; a dangling or missing HEAD is ignored.
    rc, out = _git_run(cur, "for-each-ref", "--format=%(symref)", "refs/remotes")
    for line in out.splitlines() if rc == 0 else ():
        parts = line.strip().split("/", 3)
        if len(parts) == 4 and parts[:2] == ["refs", "remotes"]:
            names.add(parts[3])
    return names


def _declared(top):
    """Branch names declared in the repo's top-level CLAUDE.md files."""
    import re

    pattern = re.compile(
        r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?\s*(?:integration|production)\s+branch"
        r"(?:\*\*|__)?\s*:(.*)$",
        re.IGNORECASE,
    )
    names = set()
    for rel in ("CLAUDE.md", os.path.join(".claude", "CLAUDE.md")):
        try:
            with open(os.path.join(top, rel), encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
            continue
        for line in text.splitlines():
            match = pattern.match(line)
            rest = match.group(1).strip().lstrip("*_ ") if match else ""
            if rest:
                token = rest.split()[0]
                names.add(token.strip("`*"))
                names.add(token.strip("`*_"))
                names.add(token.strip("`*_.,;:)"))
    names.discard("")
    return names


def _git_run(cwd, *args):
    """Run git (found through PATH) in `cwd`; return (returncode, stdout)."""
    import subprocess

    try:
        proc = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None, ""
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def _plan_mode(prompt):
    if not isinstance(prompt, str):
        return False
    for line in prompt.splitlines():
        if line.strip():
            return line.strip().lower() == "mode: plan"
    return False


def _mentions_git_or_gh(command):
    import re

    bare = re.sub(r"['\"\\]", "", command)  # as the shell joins split words
    return re.search(r"\b(git|gh)\b", bare) is not None


def decide(data):
    """Return the reason to ask about, or None for no opinion."""
    if not isinstance(data, dict):
        return None
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    tool = data.get("tool_name")
    if tool == "Agent":
        if tool_input.get("subagent_type") != "release-manager":
            return None
        try:
            return None if _plan_mode(tool_input.get("prompt")) else NOT_PLAN
        except Exception:
            return NOT_PLAN
    if tool != "Bash":
        return None
    command = tool_input.get("command")
    if not isinstance(command, str):
        return None
    cwd = data.get("cwd")
    try:
        analyze(command, cwd if isinstance(cwd, str) and cwd else None)
    except Ask as ask:
        return str(ask)
    except Exception:  # ParseError or an internal error: fail closed
        return UNPARSED if _mentions_git_or_gh(command) else None
    return None


def main():
    try:
        reason = decide(json.loads(sys.stdin.read()))
        if reason:
            sys.stdout.write(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "ask",
                            "permissionDecisionReason": reason,
                        }
                    }
                )
                + "\n"
            )
    except Exception:
        pass  # malformed input: no opinion
    sys.exit(0)


if __name__ == "__main__":
    main()
