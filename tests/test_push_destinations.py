"""R2: which branches a `git push` can reach, and which options it may carry."""

from hook_harness import GateCase

UNDETERMINED = "could not be determined"


def protected(name):
    return "protected branch '%s'" % name


class PushDestinationTest(GateCase):
    def setUp(self):
        super().setUp()
        self.basic = self.sb.make_repo()  # branch "feature"

    # T22
    def test_push_to_main_or_master_asks_naming_the_branch(self):
        self.check_ask("git push origin main", self.basic, protected("main"))
        self.check_ask("git push origin master", self.basic, protected("master"))

    # T23
    def test_push_to_an_unprotected_named_branch_is_silent(self):
        self.check_silent("git push origin feature", self.basic)

    # T24
    def test_refspec_forms_that_land_on_main_ask(self):
        self.check_ask(
            [
                "git push origin +main",
                "git push origin feature:main",
                "git push origin HEAD:main",
                "git push origin refs/heads/main",
                "git push origin feature:refs/heads/main",
                "git push origin :main",
            ],
            self.basic,
            protected("main"),
        )

    # T25
    def test_only_the_destination_of_a_refspec_counts(self):
        self.check_silent(
            [
                "git push origin main:feature",
                "git push origin +feature",
                "git push origin refs/heads/feature",
                "git push origin :feature",
            ],
            self.basic,
        )

    # T26
    def test_head_and_at_mean_the_current_branch(self):
        on_main = self.sb.on_main("onmain")
        self.check_ask(
            ["git push origin HEAD", "git push -u origin @"],
            on_main,
            protected("main"),
        )
        self.check_silent(["git push origin HEAD", "git push -u origin @"], self.basic)

    # T27
    def test_tags_are_not_branches(self):
        self.check_silent(
            [
                "git push origin refs/tags/v1.0",
                "git push origin tag v1.0",
                "git push origin tag main",
            ],
            self.basic,
        )

    # T28
    def test_deleting_a_protected_branch_asks(self):
        self.check_ask(
            ["git push origin --delete main", "git push -d origin main"],
            self.basic,
            protected("main"),
        )
        self.check_silent("git push origin --delete feature", self.basic)

    # T29
    def test_push_without_refspec_targets_the_current_branch(self):
        on_main = self.sb.on_main("onmain")
        self.check_ask(
            ["git push", "git push origin"], on_main, protected("main")
        )
        self.check_silent("git push", self.basic)

    # T30
    def test_push_without_refspec_also_targets_the_upstream_branch_name(self):
        to_main = self.sb.upstream("refs/heads/main", name="up_main")
        to_topic = self.sb.upstream("refs/heads/topic", name="up_topic")
        self.check_ask("git push", to_main, protected("main"))
        self.check_silent("git push", to_topic)

    # T31
    def test_all_branches_and_mirror_make_the_destination_undetermined(self):
        self.check_ask(
            [
                "git push origin --all",
                "git push --branches origin",
                "git push --mirror origin",
            ],
            self.basic,
            UNDETERMINED,
        )

    # T32
    def test_wildcards_and_shell_expansion_in_refspecs_ask(self):
        self.check_ask(
            [
                "git push origin 'refs/heads/*:refs/heads/*'",
                "git push origin 'feat/*'",
                'git push origin "$BRANCH"',
                "git push origin ${BRANCH}",
            ],
            self.basic,
            UNDETERMINED,
        )
        self.check_ask(
            [
                'git push origin "$(git branch --show-current)"',
                "git push origin `git branch --show-current`",
            ],
            self.basic,
        )

    # T33
    def test_dry_run_never_asks(self):
        self.check_silent(
            [
                "git push -n origin main",
                "git push --dry-run origin main",
                "git push --dry-run --all",
            ],
            self.basic,
        )

    # T34
    def test_tags_push_is_silent_unless_a_branch_refspec_is_given(self):
        self.check_silent(["git push --tags", "git push origin --tags"], self.basic)
        self.check_ask("git push --tags origin main", self.basic, protected("main"))

    # T35
    def test_detached_head_makes_a_current_branch_push_undetermined(self):
        detached = self.sb.detached("det")
        self.check_ask(
            ["git push", "git push origin HEAD"], detached, UNDETERMINED
        )
        self.check_silent("git push origin feature", detached)

    # T36
    def test_option_values_are_not_taken_for_refspecs(self):
        self.check_silent(
            [
                "git push -o main origin feature",
                "git push --force-with-lease=main origin feature",
            ],
            self.basic,
        )
        self.check_ask(
            "git push --force-with-lease origin main", self.basic, protected("main")
        )

    # T37
    def test_every_push_and_every_refspec_is_checked(self):
        self.check_ask(
            [
                "git push origin feature && git push origin main",
                "git push origin feature main",
            ],
            self.basic,
            protected("main"),
        )

    # T38
    def test_the_remote_name_does_not_matter_for_a_protected_branch(self):
        self.check_ask(
            [
                "git push upstream main",
                "git push https://example.com/o/r.git main",
            ],
            self.basic,
            protected("main"),
        )

    # T86
    def test_values_of_long_options_are_not_refspecs_and_short_option_values_are_checked(self):
        self.check_silent(
            [
                "git push --push-option main origin feature",
                "git push --receive-pack main origin feature",
                "git push --exec main origin feature",
            ],
            self.basic,
        )
        self.check_ask("git push -o ci.skip origin main", self.basic, protected("main"))

    # T87
    def test_repo_option_leaves_the_destination_undetermined(self):
        self.check_ask(
            ["git push --repo=origin", "git push --repo origin feature"],
            self.basic,
            UNDETERMINED,
        )

    # T88
    def test_unknown_options_leave_the_destination_undetermined(self):
        self.check_ask(
            ["git push --frobnicate origin feature", "git push -Z origin feature"],
            self.basic,
            UNDETERMINED,
        )

    # T89
    def test_everyday_options_do_not_turn_a_safe_push_into_an_ask(self):
        options = [
            "-u",
            "--set-upstream",
            "-f",
            "--force",
            "--force-with-lease",
            "--no-verify",
            "-q",
            "-v",
            "--follow-tags",
            "--atomic",
            "-fu",
        ]
        self.check_silent(
            ["git push %s origin feature" % opt for opt in options], self.basic
        )

    # T90
    def test_combined_short_flags_are_checked_flag_by_flag(self):
        self.check_ask("git push -fu origin main", self.basic, protected("main"))
        self.check_silent("git push -nf origin main", self.basic)
        self.check_ask("git push -uZ origin feature", self.basic, UNDETERMINED)

    # T91
    def test_known_options_without_a_value_do_not_ask(self):
        options = [
            "--verbose",
            "--quiet",
            "--porcelain",
            "--force-if-includes",
            "--thin",
            "--progress",
            "--verify",
            "--signed",
            "--signed=if-asked",
            "-4",
            "--ipv4",
            "-6",
            "--ipv6",
            "--force-with-lease=feature:abc123",
        ]
        self.check_silent(
            ["git push %s origin feature" % opt for opt in options], self.basic
        )

    # T92
    def test_no_forms_of_known_options_do_not_ask(self):
        options = [
            "--no-verbose",
            "--no-thin",
            "--no-progress",
            "--no-force",
            "--no-atomic",
            "--no-follow-tags",
            "--no-set-upstream",
            "--no-force-with-lease",
            "--no-signed",
            "--no-verify",
        ]
        self.check_silent(
            ["git push %s origin feature" % opt for opt in options], self.basic
        )

    # T93
    def test_a_separate_option_value_is_not_the_remote_when_no_refspec_follows(self):
        on_main = self.sb.on_main("onmain")
        self.check_ask(
            [
                "git push --recurse-submodules check origin",
                "git push --recurse-submodules=on-demand origin",
                "git push -o ci.skip origin",
                "git push --push-option ci.skip origin",
                "git push --receive-pack /usr/bin/git-receive-pack origin",
                "git push --exec x origin",
            ],
            on_main,
            protected("main"),
        )

    # T94
    def test_attached_option_values_are_not_refspecs(self):
        self.check_silent(
            [
                "git push --recurse-submodules main origin feature",
                "git push -oci.skip origin feature",
                "git push --push-option=main origin feature",
                "git push --receive-pack=main origin feature",
                "git push --exec=main origin feature",
            ],
            self.basic,
        )

    # T95
    def test_prune_leaves_the_destination_undetermined_unless_dry_run(self):
        self.check_ask(
            [
                "git push --prune origin feature",
                "git push --prune origin 'refs/heads/*:refs/heads/*'",
                "git push --prune",
            ],
            self.basic,
            UNDETERMINED,
        )
        self.check_silent("git push -n --prune origin feature", self.basic)

    # T96
    def test_no_dry_run_is_not_known_so_it_asks_and_cannot_cancel_a_dry_run(self):
        self.check_ask("git push -n --no-dry-run origin main", self.basic)
        self.check_ask("git push --no-dry-run origin feature", self.basic, UNDETERMINED)

    # T97
    def test_no_forms_never_consume_a_value(self):
        on_main = self.sb.on_main("onmain")
        self.check_ask(
            ["git push --no-push-option origin", "git push --no-recurse-submodules origin main"],
            on_main,
            protected("main"),
        )

    # T98
    def test_no_forms_of_undetermined_options_do_not_ask_by_themselves(self):
        self.check_silent(
            ["git push --no-all origin feature", "git push --no-prune origin feature"],
            self.basic,
        )

    # T99
    def test_dry_run_with_an_unknown_option_still_asks(self):
        self.check_ask(
            "git push -n --frobnicate origin feature", self.basic, UNDETERMINED
        )


    # T102
    def test_expansion_in_any_word_after_push_leaves_the_destination_undetermined(self):
        self.check_ask(
            [
                "git push $ARGS",
                'git push "$@"',
                'git push "$REMOTE" feature',
                "git push origin feature $EXTRA",
            ],
            self.basic,
            UNDETERMINED,
        )

    # T103
    def test_braces_and_glob_characters_in_a_refspec_leave_it_undetermined(self):
        self.check_ask(
            [
                "git push origin {main,x}",
                "git push origin ma{in,}",
                "git push origin 'feat/?'",
                "git push origin 'rel[ea]se'",
            ],
            self.basic,
            UNDETERMINED,
        )

    # T111
    def test_push_without_refspec_asks_when_config_widens_the_destination(self):
        matching = self.sb.make_repo("matching")
        self.sb.git(matching, "config", "push.default", "matching")
        self.check_ask(
            ["git push", "git push origin"], matching, UNDETERMINED
        )
        self.check_silent("git push origin feature", matching)

        remote_push = self.sb.make_repo("remote_push")
        self.sb.git(
            remote_push, "remote", "add", "origin", "https://example.invalid/o/r.git"
        )
        self.sb.git(
            remote_push, "config", "remote.origin.push",
            "refs/heads/feature:refs/heads/main",
        )
        self.check_ask("git push", remote_push, UNDETERMINED)

        simple = self.sb.make_repo("simple")
        self.sb.git(simple, "config", "push.default", "simple")
        self.check_silent("git push", simple)


if __name__ == "__main__":
    import unittest

    unittest.main()
