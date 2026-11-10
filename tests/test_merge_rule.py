"""R1: merging pull requests needs the user's approval."""

from hook_harness import GateCase

MERGE = "Merging is the user's call"


class MergeRuleTest(GateCase):
    def setUp(self):
        super().setUp()
        self.cwd = self.sb.root

    # T14
    def test_gh_pr_merge_asks_citing_the_rule_and_section(self):
        self.check_ask("gh pr merge 7", self.cwd, MERGE)

    # T15
    def test_gh_pr_merge_asks_with_any_flags_including_auto(self):
        self.check_ask(
            [
                "gh pr merge --auto --squash 7",
                "gh pr merge 7 --merge --delete-branch",
                "gh pr merge",
            ],
            self.cwd,
            MERGE,
        )

    # T16
    def test_gh_api_to_a_merge_path_segment_asks(self):
        self.check_ask(
            [
                "gh api -X PUT repos/o/r/pulls/7/merge",
                "gh api repos/o/r/pulls/7/merge",
                "gh api --method PUT /repos/o/r/pulls/7/merge",
            ],
            self.cwd,
            MERGE,
        )

    # T17
    def test_gh_api_to_the_merges_endpoint_asks(self):
        self.check_ask(
            "gh api repos/o/r/merges -f base=main -f head=feature", self.cwd, MERGE
        )

    # T18
    def test_gh_api_graphql_merge_mutations_ask(self):
        self.check_ask(
            [
                "gh api graphql -f query='mutation { mergePullRequest(input: "
                '{pullRequestId: "X"}) { clientMutationId } }\'',
                "gh api graphql -f query='mutation { enablePullRequestAutoMerge(input: "
                '{pullRequestId: "X"}) { clientMutationId } }\'',
            ],
            self.cwd,
            MERGE,
        )

    # T19
    def test_everyday_gh_commands_stay_silent(self):
        self.check_silent(
            [
                "gh pr view 7",
                "gh pr list",
                "gh pr create --title t --body b",
                "gh api repos/o/r/pulls/7",
            ],
            self.cwd,
        )

    # T20
    def test_merge_detection_needs_the_exact_segment_or_mutation_name(self):
        self.check_silent(
            [
                "gh api repos/o/merge-tools/issues",
                "gh api graphql -f query='query { repository(owner:\"o\", name:\"r\") "
                "{ pullRequest(number: 7) { mergeable } } }'",
                "gh api graphql -f query='mutation { addComment(input:{}) "
                "{ clientMutationId } }'",
            ],
            self.cwd,
        )

    # T21
    def test_merge_is_recognised_behind_prefixes_and_absolute_paths(self):
        self.check_ask(
            [
                "sudo gh pr merge 7",
                "GH_REPO=o/r gh pr merge 7",
                "env GH_TOKEN=x gh pr merge 7",
                "/opt/homebrew/bin/gh pr merge 7",
            ],
            self.cwd,
            MERGE,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
