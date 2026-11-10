---
name: delegated-tdd
description: Run a behavior change at the right weight. Picks the tier (trivial, light, full) and, for the full tier, drives role-separated subagents (test-planner, tdd-test-writer, tdd-implementer, doc-writer, reviewer), in parallel slices when the plan allows. Load before writing or changing production code for a feature, bug fix, or other behavior change, and whenever a slash command, skill, or workflow says to apply or implement work.
---

# Delegated TDD

You are the orchestrator. You pick the tier, pass each handoff, own every
commit, and decide on reviewer findings. In the full tier you do not write the
tests or the code.

What this procedure protects, in every tier above trivial:

- A failing test is committed before the code that passes it (the red commit).
- Nothing in a red commit is edited afterwards. A test believed wrong goes
  back to its author, never into someone else's edit.
- `reviewer` checks the result before it is pushed or a PR is opened.

And in the full tier:

- The author of a test is not the author of the code that makes it pass.
- One `test-planner` sees the whole change.

## Pick the tier

Decide first, and write the tier and the reason in `run.md`.

| Tier | When | What runs |
|---|---|---|
| **Trivial** | A typo, a comment, a rename, a one-line fix with no new test. | You, directly. No run record. |
| **Light** | One behavior you can state in a sentence, inside one module, with none of the triggers below. | You write the red test and the code; `reviewer` checks. See "Light tier". |
| **Full** | Everything else. | Sections 1 to 7. |

Any one of these makes the change **full**:

- A contract others consume changes: an API or event schema, a stored or
  serialized format, a database schema, the config or env surface, a log or
  error format something parses.
- Concurrency, retries, idempotency, or ordering.
- Input validation, authorization, secrets, or another security boundary.
- A new dependency, or a test level the project does not have yet.
- More than one module, or more than about 50 lines of production code.

Not a behavior change, so no tier:

- **Refactor** that keeps behavior: the existing tests are the specification.
  Do it, change no test, and have `reviewer` confirm both. If the code is not
  covered, add characterization tests first, as a light or full run.
- **Docs or config templates only**: `doc-writer`, or you.
- **Spike**: code written to learn something. Say it is throwaway, keep it off
  the integration branch, and when it becomes real start again through a tier,
  tests first.

When unsure between two tiers, take the heavier one. If a light run meets a
full trigger on the way, stop and restart it as full with `test-planner`.
Only an explicit instruction to use a single agent turns a full change into a
light run; a request for "a subagent" does not.

## Light tier

You do both roles. The red commit and `reviewer` are the independent check.

1. Start the run record (section 1) with `run.md` only: the behavior in one or
   two sentences, the tier and why, the base ref.
2. Write the failing test or tests. Run them and confirm each fails for the
   expected reason. Commit them as the red commit and record the SHA.
3. Make them pass with the smallest correct change, refactor, and run every
   check the project has. Update the docs the change makes inaccurate. Commit.
4. Spawn `reviewer` with the path of `run.md` and the base ref. Decide on its
   findings; a fix follows the same order, test first.
5. Record the outcome (section 6), then hand off (section 7).

## 1. Run record

Keep the state of the run on disk, not in your context. The plan and the
commit SHAs must survive a compaction and reach every agent unchanged.

```bash
mkdir -p .tdd/<slug> && printf '*\n' > .tdd/.gitignore
```

`.tdd/` ignores itself: it never shows in `git status` and cannot be committed
by accident. It holds, per run:

- `plan.md`: the planner's output, unchanged (full tier).
- `run.md`: what the run is and where it stands. Update it after every step,
  and read it first when you resume a run.
- `outcome.json`: written at the end (section 6).

```markdown
# <slug>
- Requirement: <one or two sentences, or the path of the spec>
- Tier: <light | full>, because <reason>
- Base ref: <sha the topic branch was cut from>
- Topic branch: <name>

| Slice | Branch | Worktree | Red | Green | Status |
|---|---|---|---|---|---|
```

Give agents the absolute paths of these files instead of pasting their
content.

## 2. Plan

1. Work on a topic branch (`feat/*`, `fix/*`, …), never on the integration or
   production branch. Create one if needed.
2. Spawn `test-planner` with the requirement in the user's words, the paths of
   any spec or task artifacts, and the base ref. Every scenario in a spec
   becomes at least one case in the plan.
3. Save its output as `plan.md`, unchanged.
4. Open questions go to the user before any test is written. Write the answers
   into `plan.md`, and run the planner again if they change the cases. With no
   open questions, continue without showing the plan.

## 3. Red, then green

For each slice (section 4 when the plan has more than one):

1. Spawn `tdd-test-writer` with the path of `plan.md`, the plan IDs to
   implement and, for a slice, its worktree and the files it owns.
2. Check its report: every plan ID has a test, and each test fails for the
   expected reason. Commit exactly the files it lists
   (`git -C <dir> add -- <files>`, then `git -C <dir> commit`) and record the
   SHA as the slice's red commit.
3. Spawn `tdd-implementer` with the red SHA, the path of `plan.md` and, for a
   slice, its worktree and files. If it reports a test as wrong, that test
   goes back to step 1; nobody else edits it.
4. Check its report, commit its files the same way, and record the SHA.

`doc-writer` runs once: alongside the implementer in a single-slice run, after
the merge in a sliced one. It works from the plan and the red tests. Commit
its files on their own.

A red commit fails by design and stays on the topic branch. If the project
needs every commit on its integration branch to pass, squash at merge.

## 4. Slices

Fan out by slice, not by role. A plan with a single slice skips this section.

1. **Run `S0` first**, in the main checkout, through section 3.
2. **Give each parallel slice a worktree**, cut from the topic branch once `S0`
   is in:

   ```bash
   mkdir -p .claude/worktrees && printf '*\n' > .claude/worktrees/.gitignore
   ```

   ```bash
   git worktree add -b <topic>-<slice> .claude/worktrees/<slug>-<slice> <topic>
   ```

   Run these from the main checkout and stay there: use absolute paths and
   `git -C <worktree>`, not `cd`.
3. **Make the worktree able to run the tests** before any agent touches it.
   Install dependencies the way the project does (README, Makefile, CI
   workflow), copy the untracked local config the tests need (`.env*`) from
   the main checkout, then run the existing suite in the worktree. If it does
   not pass there, fix the setup or run that slice sequentially. A slice never
   starts from a broken baseline.
4. **Run the slices at the same time**, each through section 3 in its own
   worktree: at most four at once, and never two at once that use the same
   external resource (database, fixed port, container). A slice goes to its
   implementer as soon as its own tests are red.
5. **A slice that needs a file it does not own** stops and comes back to you.
   Give that work to the owning slice, or merge the two slices.
6. **Check bounds, then merge.** `git diff --name-only <topic>...<topic>-<slice>`
   must list only files the slice owns. Then, in the main checkout,
   `git merge --no-ff <topic>-<slice>`. A conflict means the slices were not
   independent: stop and re-plan them instead of resolving it by hand.
7. **Remove each worktree once its branch is merged**
   (`git worktree remove <path>`), so tools that scan the tree do not pick up
   the copies during review. Keep the slice branches until the review passes,
   then delete them.
8. **Run the whole suite on the merged branch**, then run `SJ` (the cases that
   span slices) through section 3 in the main checkout.

## 5. Review

Spawn `reviewer` with the paths of `plan.md` and `run.md` and the base ref. It
re-runs every check, compares against the red commits, and checks that each
slice stayed within its files.

You decide on each finding. A fix goes through the same roles: a wrong test to
`tdd-test-writer` (a new red commit), wrong code to `tdd-implementer`. Review
again after fixes. Mark a task done only after `reviewer` passes it.

## 6. Record the outcome

Once the review passes, in every tier above trivial:

```bash
jq -n --arg date "$(date +%F)" --arg repo "<repo>" --arg task "<slug>" \
  --arg tier "<light|full>" --argjson slices <n> --argjson agents <n> \
  --argjson findings_real <n> --argjson findings_noise <n> \
  --argjson checks_hit '[<reviewer check numbers>]' \
  --argjson red_edits <n> --argjson bounces <n> --arg notes "<one line>" \
  '$ARGS.named' > .tdd/<slug>/outcome.json
```

- `agents`: subagents spawned, re-runs included.
- `findings_real`, `findings_noise`: reviewer findings that led to a change,
  and those you rejected.
- `checks_hit`: which of the reviewer's numbered checks produced a real
  finding.
- `red_edits`: edits to a red commit's files that the review caught.
- `bounces`: times an agent stopped and came back (a wrong test, a file
  outside its slice, a plan it could not follow), plus planner open questions.
- `notes`: what the process caught that you would have missed, or what it
  cost for nothing.

These files are the data for tuning the tiers and the checks.

## 7. Hand off

Hand the branch to `pr-manager` with what changed and why, and the checks that
were run with their results. Merging stays the user's call.
