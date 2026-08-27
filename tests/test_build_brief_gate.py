from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "hooks" / "build_brief_gate.py"
HOOK_CONFIG = Path(__file__).parents[1] / "hooks" / "hooks.json"


class BuildBriefGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.plugin_data = Path(self.temporary.name) / "plugin-data"
        self.base_event = {
            "session_id": "session-1",
            "turn_id": "turn-1",
            "cwd": "/workspace/project",
            "model": "test-model",
            "permission_mode": "default",
        }

    def run_hook(
        self, mode: str, event: dict
    ) -> tuple[subprocess.CompletedProcess[str], dict | None]:
        environment = os.environ.copy()
        environment["PLUGIN_DATA"] = str(self.plugin_data)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), mode],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )
        payload = json.loads(result.stdout) if result.stdout else None
        return result, payload

    def start_session(self) -> dict:
        event = {
            "session_id": self.base_event["session_id"],
            "cwd": self.base_event["cwd"],
            "model": self.base_event["model"],
            "permission_mode": self.base_event["permission_mode"],
            "hook_event_name": "SessionStart",
            "source": "startup",
        }
        result, payload = self.run_hook("session", event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNotNone(payload)
        return payload

    def pre_tool(self, tool_name: str, command: str, turn_id: str = "turn-1") -> dict | None:
        event = {
            **self.base_event,
            "turn_id": turn_id,
            "hook_event_name": "PreToolUse",
            "tool_name": tool_name,
            "tool_use_id": "tool-1",
            "tool_input": {"command": command},
        }
        result, payload = self.run_hook("pre-tool", event)
        self.assertEqual(result.returncode, 0, result.stderr)
        return payload

    def pass_gate(self, turn_id: str = "turn-1") -> dict:
        contract = {
            "boundary": "inventory write path",
            "invariants": ["one alert per threshold crossing"],
            "implementation": ["record a deduplicated notification intent"],
            "proof": ["verify concurrent threshold updates notify once"],
        }
        command = f"build-brief-gate pass {shlex.quote(json.dumps(contract))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def test_hook_config_avoids_per_prompt_context_accumulation(self) -> None:
        config = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
        hooks = config["hooks"]
        self.assertIn("SessionStart", hooks)
        self.assertNotIn("UserPromptSubmit", hooks)
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "^(Bash|apply_patch|Edit|Write)$")
        session_handler = hooks["SessionStart"][0]["hooks"][0]
        pre_tool_handler = hooks["PreToolUse"][0]["hooks"][0]
        self.assertTrue(session_handler["command"].endswith('build_brief_gate.py\" session'))
        self.assertTrue(pre_tool_handler["command"].endswith('build_brief_gate.py\" pre-tool'))

    def test_session_adds_compact_context_without_per_turn_state(self) -> None:
        payload = self.start_session()
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        self.assertIn("build-brief-gate pass", output["additionalContext"])
        self.assertLess(len(output["additionalContext"].split()), 80)
        self.assertFalse((self.plugin_data / "gate-state").exists())

    def test_read_only_bash_is_allowed_before_gate(self) -> None:
        self.start_session()
        self.assertIsNone(self.pre_tool("Bash", "rg --files"))
        self.assertIsNone(self.pre_tool("Bash", "git status --short"))
        self.assertIsNone(self.pre_tool("Bash", "Get-ChildItem -Force"))
        self.assertIsNone(self.pre_tool("Bash", "Get-Content README.md"))

    def test_apply_patch_is_denied_before_gate(self) -> None:
        self.start_session()
        payload = self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("Design Contract", output["permissionDecisionReason"])

    def test_mutating_bash_is_denied_before_gate(self) -> None:
        self.start_session()
        payload = self.pre_tool("Bash", "python3 update_schema.py")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_invalid_contract_is_denied(self) -> None:
        self.start_session()
        command = "build-brief-gate pass '{\"boundary\":\"api\"}'"
        payload = self.pre_tool("Bash", command)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("invariants", output["permissionDecisionReason"])

    def test_valid_contract_is_recorded_and_control_command_is_rewritten(self) -> None:
        self.start_session()
        payload = self.pass_gate()
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "allow")
        self.assertEqual(
            output["updatedInput"]["command"], "echo Build Brief mutation gate passed"
        )
        self.assertIsNone(self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch"))
        self.assertIsNone(self.pre_tool("Bash", "python3 update_schema.py"))

    def test_state_records_a_digest_not_contract_plaintext(self) -> None:
        self.start_session()
        self.pass_gate()
        state_text = next((self.plugin_data / "gate-state").glob("*.json")).read_text()
        self.assertIn("contract_digest", state_text)
        self.assertNotIn("inventory write path", state_text)
        self.assertNotIn("threshold crossing", state_text)

    def test_gate_pass_does_not_leak_into_a_new_turn(self) -> None:
        self.start_session()
        self.pass_gate()
        payload = self.pre_tool(
            "apply_patch",
            "*** Begin Patch\n*** End Patch",
            turn_id="turn-2",
        )
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_shell_chaining_is_not_treated_as_read_only(self) -> None:
        self.start_session()
        for command in (
            "rg --files && python3 update_schema.py",
            "rg --files | tee captured.txt",
            "rg --files & python3 update_schema.py",
            "rg pattern <(python3 generate_input.py)",
        ):
            with self.subTest(command=command):
                payload = self.pre_tool("Bash", command)
                self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_write_capable_options_are_not_treated_as_read_only(self) -> None:
        self.start_session()
        for command in (
            "sed -i s/old/new/ src/app.py",
            "find . -fprint output.txt",
            "find . -fprint0 output.txt",
            "sort input.txt --output=result.txt",
            "sort input.txt --compress-program=update_schema.py",
            "diff old new --output=changes.txt",
            "tree -o inventory.txt",
            "rg --pre update_schema.py pattern .",
            "git diff --output=changes.txt",
            "file --compile custom.magic",
        ):
            with self.subTest(command=command):
                payload = self.pre_tool("Bash", command)
                self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
