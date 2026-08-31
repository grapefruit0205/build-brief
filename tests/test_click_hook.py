from __future__ import annotations

import unittest

from hooks import click_hook


class ClickHookRoutingTests(unittest.TestCase):
    def test_direct_exec_aliases_normalize_to_canonical_bash_path(self) -> None:
        for tool_name in click_hook.DIRECT_EXEC_TOOL_NAMES:
            with self.subTest(tool_name=tool_name):
                event = {
                    "tool_name": tool_name,
                    "tool_input": {"command": "click-gate default status"},
                }
                normalized = click_hook.normalize_event(event, "pre-tool")
                self.assertEqual(normalized["tool_name"], "Bash")
                self.assertEqual(normalized["tool_input"], event["tool_input"])

    def test_code_mode_aliases_fail_into_the_same_conservative_gate_when_visible(self) -> None:
        for tool_name in click_hook.CODE_MODE_TOOL_NAMES:
            with self.subTest(tool_name=tool_name):
                event = {
                    "tool_name": tool_name,
                    "tool_input": {"command": "return tools.exec_command(...)"},
                }
                normalized = click_hook.normalize_event(event, "pre-tool")
                self.assertEqual(normalized["tool_name"], "Bash")

    def test_non_pre_tool_events_and_unrelated_tools_are_unchanged(self) -> None:
        event = {"tool_name": "mcp__node_repl__js", "tool_input": {"code": "1"}}
        self.assertIs(click_hook.normalize_event(event, "post-tool"), event)
        self.assertIs(click_hook.normalize_event(event, "pre-tool"), event)


if __name__ == "__main__":
    unittest.main()
