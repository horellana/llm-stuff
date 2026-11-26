"""Contract with Claude Code: interface, fail-closed policy, no needless git."""

import json
import os
import stat

from hook_harness import (
    OMIT,
    REAL_HOOK,
    GateCase,
    agent,
    bash,
    payload,
    run_hook,
)


class HookContractTest(GateCase):
    # T1
    def test_hook_file_is_executable_with_python3_env_shebang(self):
        self.assertTrue(os.path.isfile(REAL_HOOK), "missing %s" % REAL_HOOK)
        self.assertTrue(os.access(REAL_HOOK, os.X_OK), "hook is not executable")
        with open(REAL_HOOK, encoding="utf-8") as fh:
            self.assertEqual(fh.readline().rstrip("\n"), "#!/usr/bin/env python3")

    # T2
    def test_direct_execution_asks_with_exact_decision_shape_for_a_merge(self):
        result = run_hook(bash("gh pr merge 7", self.sb.root), env=self.sb.env())
        self.assert_ask(result, "Merging is the user's call")

    # T3
    def test_direct_execution_stays_silent_for_an_unrelated_command(self):
        result = run_hook(bash("ls -la", self.sb.root), env=self.sb.env())
        self.assert_silent(result)

    # T4
    def test_hook_runs_with_only_the_standard_library(self):
        result = run_hook(
            bash("gh pr merge 7", self.sb.root), env=self.sb.env(), direct=False
        )
        self.assert_ask(result, "Merging is the user's call")

    # T5
    def test_unusable_stdin_gives_no_opinion_and_exit_zero(self):
        for raw in ["not json", "", "[]", json.dumps("str"), "{}"]:
            with self.subTest(stdin=raw):
                self.assert_silent(run_hook(raw, env=self.sb.env()))

    # T6
    def test_only_bash_and_agent_tools_are_inspected(self):
        repo = self.sb.make_repo()
        for tool in ["Read", "Edit", "Write"]:
            with self.subTest(tool=tool):
                data = payload(
                    tool,
                    {"command": "git push origin main", "file_path": "/x"},
                    repo,
                )
                self.assert_silent(run_hook(data, env=self.sb.env()))
        with self.subTest(tool="(none)"):
            data = payload(
                OMIT, {"command": "git push origin main"}, repo
            )
            self.assert_silent(run_hook(data, env=self.sb.env()))

    # T7
    def test_malformed_bash_tool_input_gives_no_opinion(self):
        repo = self.sb.make_repo()
        cases = [
            ("missing tool_input", OMIT),
            ("string tool_input", "x"),
            ("numeric command", {"command": 42}),
            ("null command", {"command": None}),
            ("list command", {"command": ["git", "push"]}),
        ]
        for label, tool_input in cases:
            with self.subTest(case=label):
                data = payload("Bash", tool_input, repo)
                self.assert_silent(run_hook(data, env=self.sb.env()))

    # T8
    def test_unbalanced_quotes_mentioning_git_or_gh_ask_that_parsing_failed(self):
        repo = self.sb.make_repo()
        self.check_ask(
            ['git push origin "main', "gh pr merge 'x"],
            repo,
            "could not parse",
            section=False,
        )

    # T9
    def test_unbalanced_quotes_without_git_or_gh_stay_silent(self):
        self.check_silent('echo "unterminated', self.sb.make_repo())

    # T10
    def test_git_and_gh_inside_longer_words_do_not_count_on_parse_failure(self):
        self.check_silent('echo "digit gitlab ghost', self.sb.make_repo())

    # T11
    def test_push_without_a_cwd_asks_because_the_repo_cannot_be_determined(self):
        result = run_hook(bash("git push origin feature"), env=self.sb.env())
        self.assert_ask(result, "could not be determined")

    def _shim(self):
        shim_dir = self.sb.path("shim")
        os.makedirs(shim_dir)
        marker = self.sb.path("git-was-called")
        script = os.path.join(shim_dir, "git")
        with open(script, "w") as fh:
            fh.write('#!/bin/sh\ntouch "%s"\nexit 1\n' % marker)
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return self.sb.env(path_prepend=shim_dir), marker

    # T12
    def test_git_is_not_started_unless_the_command_contains_a_push(self):
        repo = self.sb.make_repo()
        env, marker = self._shim()
        cases = [
            ("git status", bash("git status", repo), "silent"),
            ("gh pr merge 7", bash("gh pr merge 7", repo), "ask"),
            ("ls", bash("ls", repo), "silent"),
            (
                "commit message mentioning a push",
                bash('git commit -m "docs: git push origin main"', repo),
                "silent",
            ),
            ("parse failure", bash('git push origin "main', repo), "parse"),
            (
                "release-manager execute",
                agent("release-manager", "mode: execute prod", repo),
                "ask",
            ),
        ]
        for label, data, expected in cases:
            with self.subTest(case=label):
                result = run_hook(data, env=env)
                if expected == "silent":
                    self.assert_silent(result)
                elif expected == "ask":
                    self.assert_ask(result)
                else:
                    self.assert_ask(result, "could not parse", section=False)
                self.assertFalse(os.path.exists(marker), "git was started")

    # T13
    def test_git_is_found_through_path_when_a_push_needs_repo_state(self):
        repo = self.sb.make_repo()
        env, marker = self._shim()
        result = run_hook(bash("git push origin feature", repo), env=env)
        self.assertTrue(os.path.exists(marker), "git from PATH was never started")
        self.assert_ask(result, "could not be determined")


    # T101
    def test_parse_failure_is_detected_on_quote_joined_git_names(self):
        repo = self.sb.make_repo()
        self.check_ask(
            "g''it push origin \"main", repo, "could not parse", section=False
        )
        self.check_silent('ec\'\'ho "unterminated', repo)


if __name__ == "__main__":
    import unittest

    unittest.main()
