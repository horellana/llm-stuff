"""R2: how the set of protected branches of a repository is built."""

import os

from hook_harness import GateCase


def protected(name):
    return "protected branch '%s'" % name


class ProtectedBranchesTest(GateCase):
    # T39
    def test_branches_declared_in_claude_md_are_protected(self):
        repo = self.sb.declared()
        self.check_ask("git push origin dev", repo, protected("dev"))
        self.check_ask("git push origin prod", repo, protected("prod"))

    # T40
    def test_declared_name_wrapped_in_backticks_is_protected(self):
        repo = self.sb.make_repo()
        self.sb.declare(repo, "Production branch: `release`")
        self.check_ask("git push origin release", repo, protected("release"))

    # T41
    def test_declarations_in_dot_claude_claude_md_are_read(self):
        repo = self.sb.make_repo()
        self.sb.declare(repo, "Integration branch: staging", where=".claude/CLAUDE.md")
        self.check_ask("git push origin staging", repo, protected("staging"))

    # T42
    def test_declarations_of_both_files_are_combined(self):
        repo = self.sb.make_repo()
        self.sb.declare(repo, "Integration branch: dev")
        self.sb.declare(repo, "Integration branch: qa", where=".claude/CLAUDE.md")
        self.check_ask("git push origin dev", repo, protected("dev"))
        self.check_ask("git push origin qa", repo, protected("qa"))

    # T43
    def test_main_stays_protected_when_other_branches_are_declared(self):
        self.check_ask("git push origin main", self.sb.declared(), protected("main"))

    # T44
    def test_branch_names_match_exactly_not_by_prefix(self):
        self.check_silent(
            [
                "git push origin develop",
                "git push origin dev2",
                "git push origin feature/dev",
            ],
            self.sb.declared(),
        )

    # T45
    def test_declarations_come_from_the_repo_top_level_not_the_cwd(self):
        repo = self.sb.declared()
        deeper = os.path.join(repo, "sub", "deeper")
        os.makedirs(deeper)
        self.check_ask("git push origin dev", deeper, protected("dev"))

    # T46
    def test_claude_md_in_a_sub_directory_declares_nothing(self):
        repo = self.sb.make_repo()
        self.sb.declare(repo, "Integration branch: dev", where="docs/CLAUDE.md")
        self.check_silent("git push origin dev", repo)

    # T47
    def test_the_remote_default_branch_is_protected(self):
        clone = self.sb.remote()
        self.check_ask("git push origin trunk", clone, protected("trunk"))
        self.check_silent("git push origin feature", clone)

    # T48
    def test_a_dangling_remote_head_is_ignored_without_crashing(self):
        repo = self.sb.make_repo()
        self.sb.git(repo, "remote", "add", "origin", "https://example.invalid/o/r.git")
        self.sb.git(
            repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/gone"
        )
        self.check_silent("git push origin feature", repo)

    # T81
    def test_declarations_are_read_tolerantly_and_never_ignored(self):
        variants = [
            ("  Integration branch: dev", "dev"),
            ("- Integration branch: dev", "dev"),
            ("* Production branch: prod", "prod"),
            ("**Production branch:** prod", "prod"),
            ("**Production branch: prod**", "prod"),
            ("integration BRANCH: dev", "dev"),
            ("- **Production branch:** `prod`", "prod"),
        ]
        for index, (line, name) in enumerate(variants):
            with self.subTest(declaration=line):
                repo = self.sb.make_repo("variant%d" % index)
                self.sb.declare(repo, line)
                self.check_ask("git push origin %s" % name, repo, protected(name))

    # T82
    def test_the_declared_name_is_the_first_token_after_the_colon(self):
        repo = self.sb.make_repo()
        self.sb.declare(repo, "Production branch: prod (deploys nightly)")
        self.check_ask("git push origin prod", repo, protected("prod"))
        self.check_silent("git push origin nightly", repo)


    # T108
    def test_punctuation_after_a_declared_name_is_ignored(self):
        variants = [
            ("Production branch: prod.", "prod"),
            ("Integration branch: `dev`, then main", "dev"),
            ("Production branch: prod;", "prod"),
            ("Production branch: prod)", "prod"),
        ]
        for index, (line, name) in enumerate(variants):
            with self.subTest(declaration=line):
                repo = self.sb.make_repo("punct%d" % index)
                self.sb.declare(repo, line)
                self.check_ask("git push origin %s" % name, repo, protected(name))


if __name__ == "__main__":
    import unittest

    unittest.main()
