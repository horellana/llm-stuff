---
name: delegated-tdd
description: Run a behavior change through role-separated subagents (test-planner, tdd-test-writer, tdd-implementer, doc-writer, reviewer), in parallel slices when the plan allows. Load before writing or changing production code for a feature, bug fix, or other behavior change that is not trivial, and whenever a slash command, skill, or workflow says to apply or implement work.
---

# Delegated TDD

You are the orchestrator. You pass each handoff, own every commit, and decide
on reviewer findings. You do not write the tests or the code.

What this procedure protects:

- A failing test is committed before the code that passes it (the red commit).
- Nothing in a red commit is edited afterwards. A test believed wrong goes
  back to `tdd-test-writer`, never into someone else's edit.
- The author of a test is not the author of the code that makes it pass.
- One `test-planner` sees the whole change, and one `reviewer` checks all of it.

Skip the procedure for a trivial change (a typo, a one-line fix with no new
test). Only an explicit instruction to use a single agent overrides the split;
a request for "a subagent" does not.

## 1. Run record

Keep the state of the run on disk, not in your context. The plan and the
commit SHAs must survive a compaction and reach every agent unchanged.

```bash
mkdir -p .tdd/<slug> && printf '*\n' > .tdd/.gitignore
```

`.tdd/` ignores itself: it never shows in `git status` and cannot be committed
by accident. It holds two files per run:

- `plan.md`: the planner's output, unchanged.
- `run.md`: what the run is and where it stands. Update it after every step,
  and read it first when you resume a run.

```markdown
# <slug>
- Requirement: <one or two sentences, or the path of the spec>
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

## 6. Hand off

Hand the branch to `pr-manager` with what changed and why, and the checks that
were run with their results. Merging stays the user's call.
