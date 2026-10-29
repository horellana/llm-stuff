# llm-stuff

My global instructions and subagents for coding agents.

- `AGENTS.md`: engineering rules applied to every project, tagged
  **MUST** / **DEFAULT** / **JUDGE**. Installed as Claude Code's global
  `CLAUDE.md`.
- `agents/`: Claude Code subagent definitions that those rules delegate to.

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
```

An existing `CLAUDE.md` is kept as `CLAUDE.md.bak`. Agent files with the same
names in `~/.claude/agents/` are replaced by links. Start a new Claude Code
session to load the changes.

## Agents

| Agent | Role |
|---|---|
| `test-planner` | Read-only. Decides which cases to test, at which level, and what to leave out. Raises open questions. |
| `tdd-test-writer` | Implements the plan as failing tests and proves they fail. Never writes production code. |
| `tdd-implementer` | Makes the tests pass without editing them. |
| `doc-writer` | Updates docs and config templates. Never touches code or tests. |
| `reviewer` | Read-only. Re-runs checks, confirms tests were not edited after the red phase, and checks coverage against the plan. |
| `pr-manager` | Opens PRs with English titles and descriptions, and prepares merges. Never merges. |

Delegated TDD work runs in this order: `test-planner` → `tdd-test-writer` →
`tdd-implementer` (with `doc-writer` in parallel) → `reviewer` → `pr-manager`.
The main session passes each handoff and owns commits. The user sees the test
plan only when it has open questions, and merges always wait for the user.

`test-planner` runs on Opus, because a case missing from the plan goes
untested all the way down; the other agents run on Sonnet.

## Per-project setup

`pr-manager` needs each project's `CLAUDE.md` to declare its branches:

```
Integration branch: dev
Production branch: main
```

If either line is missing, it stops and asks instead of guessing.

## License

[AGPL-3.0](LICENSE)
