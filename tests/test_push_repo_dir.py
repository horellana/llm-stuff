"""R2: which repository a push applies to (cwd, `git -C`, an earlier `cd`)."""

import os

from hook_harness import GateCase, Sandbox, process_dir

UNDETERMINED = "could not be determined"
PROD = "protected branch 'prod'"


class PushRepoDirTest(GateCase):
    # T49
    def test_dash_C_switches_to_the_repo_it_names(self):
        a, _b = self.sb.siblings()
        self.check_ask("git -C ../b push origin prod", a, PROD)

    # T50
    def test_relative_dash_C_options_compose(self):
        a, _b = self.sb.siblings()
        self.check_ask("git -C .. -C b push origin prod", a, PROD)

    # T51
    def test_the_dash_C_repo_is_used_not_the_cwd_repo(self):
        a, _b = self.sb.siblings(a_text="Integration branch: dev", b_text=None)
        self.check_silent("git -C ../b push origin dev", a)

    # T52
    def test_an_earlier_cd_on_the_same_line_switches_repo(self):
        a, b = self.sb.siblings()
        self.check_ask(
            [
                "cd ../b && git push origin prod",
                "cd ../b; git push origin prod",
                "cd %s && git push origin prod" % b,
            ],
            a,
            PROD,
        )

    def test_an_earlier_quoted_cd_into_a_path_with_a_space_switches_repo(self):
        spaced = Sandbox(space=True)
        self.addCleanup(spaced.cleanup)
        a, b = spaced.siblings()
        self.assertIn(" ", b)
        self.check_ask(
            'cd "%s" && git push origin prod' % b, a, PROD, env=spaced.env()
        )

    # T53
    def test_cd_and_dash_C_compose(self):
        a, _b = self.sb.siblings()
        self.check_ask("cd .. && git -C b push origin prod", a, PROD)

    # T54
    def test_a_cd_after_the_push_does_not_change_its_repo(self):
        a, _b = self.sb.siblings()
        self.check_silent("git push origin prod; cd ../b", a)

    # T55
    def test_git_dir_work_tree_and_shell_expansion_make_the_repo_unknown(self):
        repo = self.sb.make_repo()
        self.check_ask(
            [
                "git --git-dir=.git push origin feature",
                "git --git-dir .git push origin feature",
                "git --work-tree=. push origin feature",
                'git -C "$D" push origin feature',
                'cd "$D" && git push origin feature',
                "cd `pwd` && git push origin feature",
            ],
            repo,
            UNDETERMINED,
        )

    # T56
    def test_a_repo_that_cannot_be_resolved_asks(self):
        repo = self.sb.make_repo()
        self.check_ask(
            "git -C ./does-not-exist push origin feature", repo, UNDETERMINED
        )
        with self.subTest(case="cwd does not exist"):
            self.check_ask(
                "git push origin feature", self.sb.path("nope"), UNDETERMINED
            )

    # T57
    def test_command_text_is_never_executed_while_resolving_the_directory(self):
        repo = self.sb.make_repo()
        self.check_ask(
            [
                'git -C "$(touch MARK1)" push origin feature',
                'cd "$(touch MARK2)" && git push origin feature',
            ],
            repo,
        )
        found = []
        for base in (self.sb.root, process_dir()):
            for dirpath, dirnames, filenames in os.walk(base):
                for name in dirnames + filenames:
                    if name in ("MARK1", "MARK2"):
                        found.append(os.path.join(dirpath, name))
        self.assertEqual(found, [])

    # T75
    def test_a_directory_that_is_not_a_repo_cannot_be_resolved(self):
        plain = self.sb.path("plain")
        os.makedirs(plain)
        self.check_ask("git push origin feature", plain, UNDETERMINED)
        repo = self.sb.make_repo()
        self.check_ask("git -C %s push origin feature" % plain, repo, UNDETERMINED)

    # T83
    def test_cd_with_no_argument_or_tilde_goes_to_home(self):
        a, b = self.sb.siblings()
        env = self.sb.env(home=b)
        self.check_ask(
            ["cd && git push origin prod", "cd ~ && git push origin prod"],
            a,
            PROD,
            env=env,
        )

    # T84
    def test_tilde_paths_expand_in_cd_and_dash_C(self):
        a, _b = self.sb.siblings()
        env = self.sb.env(home=self.sb.root)
        self.check_ask(
            ["cd ~/b && git push origin prod", "git -C ~/b push origin prod"],
            a,
            PROD,
            env=env,
        )

    def test_tilde_dash_C_uses_the_target_repo_not_the_cwd_repo(self):
        a, _b = self.sb.siblings(a_text="Integration branch: dev", b_text=None)
        self.sb.make_repo("c")
        env = self.sb.env(home=self.sb.root)
        self.check_silent("git -C ~/c push origin dev", a, env=env)

    # T85
    def test_cd_dash_and_tilde_user_make_the_directory_unknown(self):
        repo = self.sb.make_repo()
        self.check_ask(
            [
                "cd - && git push origin feature",
                "cd ~root && git push origin feature",
                "git -C ~nobody/x push origin feature",
            ],
            repo,
            UNDETERMINED,
        )


    # T109
    def test_git_dir_or_work_tree_assigned_before_git_makes_the_repo_unknown(self):
        repo = self.sb.make_repo()
        self.check_ask(
            [
                "GIT_DIR=/tmp/x/.git git push origin feature",
                "GIT_WORK_TREE=/tmp/x git push origin feature",
                "env GIT_DIR=/tmp/x/.git git push origin feature",
            ],
            repo,
            UNDETERMINED,
        )
        self.check_silent("GIT_TRACE=1 git push origin feature", repo)

    # T110
    def test_cd_inside_a_subshell_does_not_leak_past_the_parenthesis(self):
        a, _b = self.sb.siblings()
        self.check_ask("(cd ../b && git push origin prod)", a, PROD)
        self.check_silent(
            [
                "(cd ../b); git push origin prod",
                "echo $(cd ../b); git push origin prod",
            ],
            a,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
