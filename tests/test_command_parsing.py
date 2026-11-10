"""Finding git and gh commands inside a Bash command line."""

from hook_harness import GateCase

MERGE = "Merging is the user's call"
MAIN = "protected branch 'main'"

HEREDOC_COMMIT = """git commit -m "$(cat <<'EOF'
fix: stop running gh pr merge and git push origin main
EOF
)\""""


class CommandParsingTest(GateCase):
    def setUp(self):
        super().setUp()
        self.repo = self.sb.make_repo()  # branch "feature"

    # T58
    def test_every_command_separator_exposes_the_command_after_it(self):
        self.check_ask(
            [
                "true; git push origin main",
                "true && git push origin main",
                "false || git push origin main",
                "sleep 0 & git push origin main",
                "true\ngit push origin main",
                "(git push origin main)",
                "echo $(git push origin main)",
                "echo `gh pr merge 7`",
                "cat x | xargs git push origin main",
            ],
            self.repo,
        )

    # T59
    def test_text_inside_quotes_and_heredoc_messages_is_not_a_command(self):
        self.check_silent(
            [
                'git commit -m "docs: explain gh pr merge"',
                'grep -n "git push origin main" README.md',
                "echo 'gh api repos/o/r/pulls/7/merge'",
                HEREDOC_COMMIT,
            ],
            self.repo,
        )

    # T60
    def test_prefixes_before_git_are_skipped(self):
        prefixes = [
            "sudo git push origin %s",
            "sudo -u root env A=b git push origin %s",
            "env A=b git push origin %s",
            "time git push origin %s",
            "A=b git push origin %s",
            "/usr/bin/git push origin %s",
            "xargs git push origin %s",
        ]
        self.check_ask([p % "main" for p in prefixes], self.repo, MAIN)
        self.check_silent([p % "feature" for p in prefixes], self.repo)

    # T61
    def test_global_git_options_before_the_subcommand_are_skipped(self):
        forms = [
            "git -c push.default=current push origin %s",
            "git --no-pager push origin %s",
            "git -C . push origin %s",
            "git -c core.x=1 -C . --no-pager push origin %s",
        ]
        self.check_ask([f % "main" for f in forms], self.repo, MAIN)
        self.check_silent([f % "feature" for f in forms], self.repo)

    # T62
    def test_push_as_an_argument_of_another_subcommand_is_not_a_push(self):
        self.check_silent(
            [
                "git stash push -m wip",
                "git log --grep push",
                "git config push.default current",
                "git help push",
            ],
            self.sb.root,
        )

    # T63
    def test_shell_c_scripts_and_eval_are_parsed_recursively(self):
        self.check_ask(
            [
                "bash -c 'git push origin main'",
                'sh -c "gh pr merge 7"',
                "zsh -c 'git push origin main'",
                'eval "git push origin main"',
                "eval git push origin main",
            ],
            self.repo,
        )

    # T64
    def test_nested_shell_scripts_are_parsed_with_their_own_quoting(self):
        self.check_ask("bash -c \"sh -c 'gh pr merge 7'\"", self.sb.root, MERGE)
        self.check_silent("bash -c 'echo \"gh pr merge\"'", self.sb.root)

    # T65
    def test_a_hash_hides_nothing(self):
        self.check_ask(
            ["echo a#b; git push origin main", "git push origin main # ship it"],
            self.repo,
            MAIN,
        )

    # T66
    def test_parse_failure_inside_a_shell_c_script_asks(self):
        self.check_ask(
            "bash -c 'git push origin \"main'", self.sb.root, section=False
        )

    # T76
    def test_command_substitution_inside_double_quotes_is_a_command(self):
        self.check_ask('out="$(git push origin main)"', self.repo, MAIN)
        self.check_ask('git commit -m "$(gh pr merge 7)"', self.repo, MERGE)
        self.check_ask('echo "pre $(git push origin main) post"', self.repo, MAIN)

    # T77
    def test_heredoc_bodies_are_data_and_only_the_closing_word_ends_them(self):
        body = "gh pr merge 7\ngit push origin main\n"
        variants = [
            ("cat <<EOF\n" + body + "EOF", "unquoted delimiter"),
            ("cat <<'EOF'\n" + body + "EOF", "single-quoted delimiter"),
            ('cat <<"EOF"\n' + body + "EOF", "double-quoted delimiter"),
            (
                "cat <<-EOF\n\tgh pr merge 7\n\tgit push origin main\n\tEOF",
                "dash form with tab-indented body and closing word",
            ),
        ]
        for command, label in variants:
            with self.subTest(heredoc=label):
                self.check_silent(command, self.repo)
        self.check_ask(
            "cat <<'EOF'\ngh pr merge 7\nEOF\ngit push origin main", self.repo, MAIN
        )

    # T78
    def test_code_after_a_heredoc_marker_on_the_same_line_is_a_command(self):
        self.check_ask("cat <<EOF && git push origin main\nbody\nEOF", self.repo, MAIN)
        self.check_silent('git commit -m "$(echo "gh pr merge 7")"', self.repo)

    # T79
    def test_shell_c_with_combined_or_preceding_flags_is_parsed(self):
        self.check_ask(
            [
                "bash -lc 'git push origin main'",
                'sh -ec "gh pr merge 7"',
                "zsh -xc 'git push origin main'",
                "bash -l -c 'git push origin main'",
                "bash --noprofile -c 'git push origin main'",
            ],
            self.repo,
        )

    # T80
    def test_shell_flags_without_c_do_not_open_a_script_argument(self):
        self.check_silent(["bash -l ./run.sh", "bash -e deploy.sh"], self.sb.root)


if __name__ == "__main__":
    import unittest

    unittest.main()
