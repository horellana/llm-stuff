"""R3: release-manager may only run in plan mode without asking."""

from hook_harness import OMIT, GateCase, payload, run_hook

RM = "release-manager"
PLAN_MODE = "plan mode"


class ReleaseRuleTest(GateCase):
    def check_agent_silent(self, subagent_type, prompts):
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assert_silent(self.run_agent(subagent_type, prompt))

    def check_agent_ask(self, prompts, *substrings, section=True):
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assert_ask(
                    self.run_agent(RM, prompt), *substrings, section=section
                )

    # T67
    def test_plan_mode_is_silent(self):
        self.check_agent_silent(RM, ["mode: plan\nTarget: staging"])

    # T68
    def test_plan_mode_ignores_case_whitespace_blank_lines_and_crlf(self):
        self.check_agent_silent(
            RM,
            [
                "MODE: PLAN\nTarget: staging",
                "  Mode: Plan  \nTarget: staging",
                "\n\n   \nmode: plan\nTarget: staging",
                "mode: plan\r\nTarget: staging",
            ],
        )

    # T69
    def test_execute_mode_asks_naming_the_agent_and_plan_mode(self):
        self.check_agent_ask(["mode: execute staging\nTarget: staging"], RM, PLAN_MODE)

    # T70
    def test_a_prompt_without_a_mode_line_asks(self):
        self.check_agent_ask(
            ["Deploy v1.2 to staging", "", "   \n  ", OMIT], RM, PLAN_MODE
        )
        self.check_agent_ask([None, 42], section=False)

    # T71
    def test_only_the_exact_plan_mode_line_passes(self):
        self.check_agent_ask(
            ["mode: plan staging", "mode: planning", "mode:plan", "# mode: plan"],
            RM,
            PLAN_MODE,
        )

    # T72
    def test_only_the_first_non_blank_line_counts(self):
        self.check_agent_ask(["Release v1.2\nmode: plan"], RM, PLAN_MODE)

    # T73
    def test_other_subagent_types_get_no_opinion(self):
        prompts = ["mode: execute production", "git push origin main"]
        for subagent_type in ["reviewer", "pr-manager", OMIT]:
            with self.subTest(subagent_type=subagent_type):
                self.check_agent_silent(subagent_type, prompts)

    # T74
    def test_malformed_agent_tool_input_gives_no_opinion(self):
        data = payload("Agent", "x", self.sb.root)
        self.assert_silent(run_hook(data, env=self.sb.env()))


if __name__ == "__main__":
    import unittest

    unittest.main()
