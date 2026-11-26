"""Shared harness for the approval gate hook tests.

The hook is always exercised as a subprocess with JSON on stdin, which is how
Claude Code calls it. Anything that needs git state uses a real temporary
repository, never a mock.

The hook path can be overridden with the APPROVAL_GATE_HOOK environment
variable. That exists only to check that the suite discriminates (against
throwaway fakes); test_hook_contract.test_hook_file_... always targets the
real path.
"""

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import namedtuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
REAL_HOOK = os.path.join(REPO_ROOT, "hooks", "approval_gate.py")
HOOK = os.environ.get("APPROVAL_GATE_HOOK") or REAL_HOOK
TIMEOUT = 10

OMIT = object()  # "leave this key out of the payload"

Result = namedtuple("Result", "returncode stdout stderr")

SECTION = "AGENTS.md §9"

_scratch = None


def process_dir():
    """Neutral, non-repo directory used as the hook process's own cwd."""
    global _scratch
    if _scratch is None:
        _scratch = os.path.realpath(tempfile.mkdtemp(prefix="gate-proc-"))
        os.makedirs(os.path.join(_scratch, "home"))
        atexit.register(shutil.rmtree, _scratch, True)
    return _scratch


def base_env(home=None, ceiling=None, path_prepend=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("APPROVAL_GATE_HOOK", None)
    env.update(
        HOME=home or os.path.join(process_dir(), "home"),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.invalid",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.invalid",
    )
    if ceiling:
        env["GIT_CEILING_DIRECTORIES"] = ceiling
    if path_prepend:
        env["PATH"] = path_prepend + os.pathsep + env.get("PATH", "")
    return env


def run_hook(payload, *, cwd_for_process=None, env=None, direct=True, hook=None):
    """Run the hook. `payload` is a dict (sent as JSON) or a str (sent raw)."""
    hook = hook or HOOK
    if not os.path.exists(hook):
        raise AssertionError("hook not found: %s" % hook)
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    cmd = [hook] if direct else [sys.executable, "-I", "-S", hook]
    try:
        proc = subprocess.run(
            cmd,
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            cwd=cwd_for_process or process_dir(),
            env=env if env is not None else base_env(),
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError("hook did not finish within %ss" % TIMEOUT)
    return Result(proc.returncode, proc.stdout, proc.stderr)


def payload(tool_name=OMIT, tool_input=OMIT, cwd=None, **extra):
    data = {
        "session_id": "abc123",
        "transcript_path": "/nonexistent/transcript.jsonl",
        "hook_event_name": "PreToolUse",
        "permission_mode": "default",
    }
    if tool_name is not OMIT:
        data["tool_name"] = tool_name
    if tool_input is not OMIT:
        data["tool_input"] = tool_input
    if cwd is not None:
        data["cwd"] = cwd
    data.update(extra)
    return data


def bash(command, cwd=None):
    return payload("Bash", {"command": command}, cwd)


def agent(subagent_type, prompt=OMIT, cwd=None):
    tool_input = {"description": "x"}
    if subagent_type is not OMIT:
        tool_input["subagent_type"] = subagent_type
    if prompt is not OMIT:
        tool_input["prompt"] = prompt
    return payload("Agent", tool_input, cwd)


def as_list(value):
    return [value] if isinstance(value, str) else list(value)


class Sandbox:
    """A temporary directory tree holding real git repositories.

    Repositories are always sub-directories of `root`, and root is never a
    repository, so a plain directory next to them can never resolve to one.
    """

    def __init__(self, space=False):
        self._tmp = tempfile.TemporaryDirectory(
            prefix="gate sandbox " if space else "gate-sandbox-"
        )
        self.root = os.path.realpath(self._tmp.name)

    def cleanup(self):
        self._tmp.cleanup()

    def env(self, home=None, path_prepend=None):
        return base_env(
            home=home,
            ceiling=os.path.dirname(self.root),
            path_prepend=path_prepend,
        )

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def git(self, repo, *args):
        subprocess.run(
            ["git", "-C", repo] + list(args),
            env=self.env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def write(self, repo, relpath, text):
        target = os.path.join(repo, relpath)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(text)

    def declare(self, repo, text, where="CLAUDE.md"):
        """Write an uncommitted CLAUDE.md (or .claude/CLAUDE.md) in a repo."""
        self.write(repo, where, text if text.endswith("\n") else text + "\n")

    # Fixtures -------------------------------------------------------------

    def make_repo(self, name="repo", branch="feature"):
        """BASIC: one commit, no remotes, no CLAUDE.md, `branch` checked out."""
        path = self.path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        subprocess.run(
            ["git", "init", "-q", "-b", branch, path],
            env=self.env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        self.git(path, "commit", "-q", "--allow-empty", "-m", "init")
        return path

    def on_main(self, name="repo"):
        return self.make_repo(name, "main")

    def detached(self, name="repo"):
        path = self.make_repo(name)
        self.git(path, "checkout", "-q", "--detach")
        return path

    def declared(self, name="repo"):
        path = self.make_repo(name)
        self.declare(
            path, "Integration branch: dev\nProduction branch: `prod`\n"
        )
        return path

    def remote(self):
        """Clone whose origin/HEAD points to origin/trunk, on branch feature."""
        bare = self.path("remote.git")
        subprocess.run(
            ["git", "init", "-q", "--bare", "-b", "trunk", bare],
            env=self.env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        seed = self.make_repo("seed", "trunk")
        self.git(seed, "remote", "add", "origin", bare)
        self.git(seed, "push", "-q", "origin", "trunk")
        clone = self.path("clone")
        subprocess.run(
            ["git", "clone", "-q", bare, clone],
            env=self.env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        self.git(clone, "checkout", "-q", "-b", "feature")
        return clone

    def upstream(self, merge, name="up"):
        """Branch `topic` tracking origin with branch.topic.merge = `merge`."""
        path = self.make_repo(name, "topic")
        self.git(path, "remote", "add", "origin", "https://example.invalid/o/r.git")
        self.git(path, "config", "branch.topic.remote", "origin")
        self.git(path, "config", "branch.topic.merge", merge)
        return path

    def siblings(self, a_text=None, b_text="Production branch: prod"):
        """<root>/a and <root>/b, each optionally declaring branches."""
        a = self.make_repo("a")
        b = self.make_repo("b")
        if a_text:
            self.declare(a, a_text)
        if b_text:
            self.declare(b, b_text)
        return a, b


class GateCase(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)

    # Assertions -------------------------------------------------------------

    @staticmethod
    def _ctx(result):
        return "\nreturncode=%r\nstdout=%r\nstderr=%r" % (
            result.returncode,
            result.stdout,
            result.stderr,
        )

    def assert_silent(self, result):
        ctx = self._ctx(result)
        self.assertEqual(result.returncode, 0, ctx)
        self.assertEqual(result.stdout, "", "expected no output" + ctx)
        self.assertNotIn("Traceback", result.stderr, ctx)

    def assert_ask(self, result, *substrings, section=True):
        """Exit 0, exactly one ask object, one-line reason with substrings.

        `section=True` also requires "AGENTS.md §9" (every R1, R2 and R3
        reason carries it). Parse-failure reasons are not an R1-R3 rule, so
        those cases pass section=False.
        """
        ctx = self._ctx(result)
        self.assertEqual(result.returncode, 0, ctx)
        self.assertNotIn("Traceback", result.stderr, ctx)
        self.assertNotEqual(
            result.stdout.strip(), "", "expected an ask decision, got no output" + ctx
        )
        try:
            data = json.loads(result.stdout)
        except ValueError:
            self.fail("stdout is not a single JSON object" + ctx)
        self.assertIsInstance(data, dict, ctx)
        self.assertEqual(set(data), {"hookSpecificOutput"}, ctx)
        out = data["hookSpecificOutput"]
        self.assertIsInstance(out, dict, ctx)
        self.assertEqual(
            set(out),
            {"hookEventName", "permissionDecision", "permissionDecisionReason"},
            ctx,
        )
        self.assertEqual(out["hookEventName"], "PreToolUse", ctx)
        self.assertEqual(out["permissionDecision"], "ask", ctx)
        reason = out["permissionDecisionReason"]
        self.assertIsInstance(reason, str, ctx)
        self.assertNotIn("\n", reason, "reason must be one line" + ctx)
        self.assertNotIn("\r", reason, "reason must be one line" + ctx)
        needed = list(substrings) + ([SECTION] if section else [])
        for text in needed:
            self.assertIn(text, reason, "reason lacks %r%s" % (text, ctx))

    # Drivers ----------------------------------------------------------------

    def run_bash(self, command, cwd, *, env=None, direct=True):
        return run_hook(
            bash(command, cwd),
            env=env if env is not None else self.sb.env(),
            direct=direct,
        )

    def check_ask(self, commands, cwd, *substrings, env=None, section=True):
        for command in as_list(commands):
            with self.subTest(command=command):
                self.assert_ask(
                    self.run_bash(command, cwd, env=env),
                    *substrings,
                    section=section
                )

    def check_silent(self, commands, cwd, *, env=None):
        for command in as_list(commands):
            with self.subTest(command=command):
                self.assert_silent(self.run_bash(command, cwd, env=env))

    def run_agent(self, subagent_type, prompt=OMIT):
        return run_hook(agent(subagent_type, prompt, self.sb.root), env=self.sb.env())
