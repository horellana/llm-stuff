# llm-stuff

My global instructions and subagents for coding agents.

- `AGENTS.md`: engineering rules applied to every project, tagged
  **MUST** / **DEFAULT** / **JUDGE**. Installed as Claude Code's global
  `CLAUDE.md`.
- `agents/`: Claude Code subagent definitions that those rules delegate to.
- `skills/`: Claude Code skills. `delegated-tdd` holds the procedure for
  behavior changes; `AGENTS.md` keeps the invariants and points to it.
- `hooks/`: Claude Code hooks that back those rules up where the model alone
  is not reliable.

## Install

Clone somewhere permanent, then symlink the files into `~/.claude`. With links,
editing `~/.claude/CLAUDE.md` or an agent edits this repo, so the two never
drift apart.

```bash
git clone https://github.com/horellana/llm-stuff.git ~/work/llm-stuff
```

```bash
REPO=~/work/llm-stuff
mkdir -p ~/.claude/agents
[ -e ~/.claude/CLAUDE.md ] && [ ! -L ~/.claude/CLAUDE.md ] && mv ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.bak
ln -sfn "$REPO/AGENTS.md" ~/.claude/CLAUDE.md
for f in "$REPO"/agents/*.md; do ln -sfn "$f" ~/.claude/agents/; done
mkdir -p ~/.claude/skills
ln -sfn "$REPO/skills/delegated-tdd" ~/.claude/skills/
mkdir -p ~/.claude/hooks
ln -sfn "$REPO/hooks/delegation-reminder.sh" ~/.claude/hooks/
ln -sfn "$REPO/hooks/approval_gate.py" ~/.claude/hooks/
```

An existing `CLAUDE.md` is kept as `CLAUDE.md.bak`. Agent files with the same
names in `~/.claude/agents/` are replaced by links.

Then register both hooks in `~/.claude/settings.json`. The reminder needs `jq`;
the gate needs `python3` and `git` (see "Hooks"):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/delegation-reminder.sh" }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash|Agent",
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/approval_gate.py" }
        ]
      }
    ]
  }
}
```

Start a new Claude Code session to load the changes.

## Hooks

`delegation-reminder.sh` runs on every prompt. When the prompt is a slash
command whose name contains `apply` or `implement` (for example
`/opsx:apply`), it adds a reminder that the command's steps define what to
build, not who builds it, and tells the session to load the `delegated-tdd`
skill. It never blocks a prompt. A skill the model picks on its own, without a
slash command, is covered only by the rule in `AGENTS.md`.

`approval_gate.py` is a `PreToolUse` hook (Python 3 standard library only) that
backs up the approval rules of `AGENTS.md` §9. It asks you to confirm:

- **Merges**: `gh pr merge` (any flags), and `gh api` calls that target a merge
  (a `merge` or `merges` path segment, or the `mergePullRequest` and
  `enablePullRequestAutoMerge` mutations). A `GET` on a merge path asks too.
- **Pushes that can reach a protected branch**: every `git push` in the command
  is resolved to its destination branches. It asks if any is protected.
- **`release-manager` runs** whose prompt does not start with `mode: plan`.

Protected branches are the union of:

- the `Integration branch:` and `Production branch:` lines of the repo's
  `CLAUDE.md` or `.claude/CLAUDE.md`, read tolerantly (list bullet, bold, any
  letter case, name in backticks);
- the remote's default branch, when it resolves;
- `main` and `master`.

It also asks when it cannot determine a push destination (`--all`, `--mirror`,
a wildcard, brace or shell expansion in the push arguments, a detached HEAD,
an unknown option, `push.default=matching`, a directory that is not a
resolvable git repository) or cannot parse a command that mentions `git` or
`gh`. It never allows or denies on its own, and it
ignores `git push --dry-run`.

Not covered: commands run over `ssh`; shell and git aliases, and shell
functions; scripts that push or merge internally, including a script given to
a shell on standard input (heredoc, here-string, or pipe); a command name that
comes from a variable; shells other than `bash`, `sh` and `zsh`; `curl`
against the GitHub API; a substitution inside the body of an unquoted heredoc;
and Claude Code versions where the subagent tool is not named `Agent`. It is a
backstop for a push or merge written as a command on the command line, not a
sandbox.

Requirements: `python3` (written for 3.8 or later, verified only on 3.9.6) and
`git` on `PATH`. If `python3` is missing, the hook fails without blocking, so
the gate is silently off.

"Ask" sends the tool call to the permission prompt. Per the Claude Code docs
(read on 2026-11-10), in auto mode a hook's "ask" goes to the prompt instead of
the classifier. For `bypassPermissions` and non-interactive `-p` runs the docs
do not say; it is not verified there, so do not count on the gate in those
modes.

Tests: `python3 -m unittest discover -s tests` from the repo root.

## Agents

| Agent | Role |
|---|---|
| `test-planner` | Read-only. Decides which cases to test, at which level, and what to leave out. Raises open questions. |
| `tdd-test-writer` | Implements the plan as failing tests and proves they fail. Never writes production code. |
| `tdd-implementer` | Makes the tests pass without editing them. |
| `doc-writer` | Updates docs and config templates. Never touches code or tests. |
| `reviewer` | Read-only. Re-runs checks, diffs the tests against the red commit to confirm they were not edited, and checks coverage against the plan. |
| `pr-manager` | Opens PRs with English titles and descriptions, and prepares merges. Never merges. |
| `release-manager` | Plans releases (artifact, baseline, checks, rollback), then deploys one approved environment at a time by the project's runbook, verifies, and rolls back immediately on a failed check. Its prompt starts with `mode: plan` or `mode: execute <environment>` (`AGENTS.md` §9). |

Behavior changes go through the `delegated-tdd` skill, which picks a tier first:

- **Trivial** (typo, comment, one-line fix with no new test): done directly.
- **Light** (one behavior in one module, none of the full-tier triggers): the
  main session writes the red test and the code, and `reviewer` checks.
- **Full**: the role-separated pipeline below.

Refactors, docs-only changes and spikes are not behavior changes and have
their own rule in the skill.

The full pipeline runs in this order: `test-planner` → `tdd-test-writer` →
`tdd-implementer` (with `doc-writer` in parallel) → `reviewer` → `pr-manager`.
The main session passes each handoff and owns commits. The red tests are
committed, and `reviewer` diffs against that commit. The plan and the commit
SHAs live in a self-ignoring `.tdd/<slug>/` directory in the project. The user
sees the test plan only when it has open questions, and merges always wait for
the user.

When the plan divides the work into independent slices, the writer and
implementer steps run once per slice, at the same time, each slice in its own
local branch and git worktree under `.claude/worktrees/` and limited to the
files it owns. A worktree is removed right after its branch is merged. A shared
slice (fixtures, schemas, migrations) runs first; cases that span slices are
written after the slices are merged. Planning, docs, and review stay single, so
one agent still sees the whole change. At most four slices run at once.

Releases run separately, after merge: `release-manager` returns a plan, the
user approves it once per environment, and the agent deploys that environment,
verifies it, and rolls back on its own if a check misses its criterion. It
deploys only by a project's runbook (for example a deploy skill); without one,
it drafts a runbook for review.

`test-planner` and `release-manager` run on Opus: a case missing from the plan
goes untested all the way down, and a release mistake reaches production. The
other agents run on Sonnet.

## Per-project setup

`pr-manager` needs each project's `CLAUDE.md` to declare its branches:

```
Integration branch: dev
Production branch: main
```

If either line is missing, it stops and asks instead of guessing. The approval
gate reads the same two lines to know which branches are protected.

## Measuring

Every run above the trivial tier ends by writing `.tdd/<slug>/outcome.json`. It
records the date, repo, task, tier, number of slices and subagents, reviewer
findings that were real or noise, which reviewer checks produced a real
finding, edits to red tests the review caught, bounces (an agent stopped and
came back), and a one-line note.

Collect them across projects:

```bash
jq -s '.' <projects>/*/.tdd/*/outcome.json
```

The tier thresholds and the reviewer checks are starting points. Review them
against these files on 2026-11-24.

## License

[AGPL-3.0](LICENSE)
