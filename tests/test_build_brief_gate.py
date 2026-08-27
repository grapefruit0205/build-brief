from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(
    os.environ.get(
        "BUILD_BRIEF_GATE_UNDER_TEST",
        Path(__file__).parents[1] / "hooks" / "build_brief_gate.py",
    )
)
HOOK_CONFIG = Path(
    os.environ.get(
        "BUILD_BRIEF_HOOK_CONFIG_UNDER_TEST",
        Path(__file__).parents[1] / "hooks" / "hooks.json",
    )
)


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

    def contract(self) -> dict:
        return {
            "plain_language": (
                "재고가 임계값 아래로 내려갈 때 같은 상황에서는 알림을 한 번만 보내고, "
                "승인된 순서대로 현재 알림 경로를 수정하고 검증합니다."
            ),
            "boundary": "inventory write path",
            "invariants": ["one alert per threshold crossing"],
            "system_semantics": [
                "deduplicate notification intent at the existing inventory write boundary"
            ],
            "implementation": [
                "extend the existing threshold transition and notification path"
            ],
            "phases": ["change the write path", "verify concurrent behavior"],
            "steps": ["record the threshold transition atomically", "dispatch once"],
            "tasks": ["update inventory logic", "add focused concurrency coverage"],
            "plan": ["preserve the current boundary and change only alert deduplication"],
            "execution_order": ["inventory state change before notification dispatch"],
            "minimality": [
                "reuse the inventory write path and existing notification mechanism"
            ],
            "proof": ["verify concurrent threshold updates notify once"],
        }

    def stage_gate(
        self, contract: dict | None = None, turn_id: str = "turn-1"
    ) -> dict:
        value = contract or self.contract()
        command = f"build-brief-gate stage {shlex.quote(json.dumps(value))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def pass_gate(
        self, contract: dict | None = None, turn_id: str = "turn-2"
    ) -> dict:
        value = contract or self.contract()
        command = f"build-brief-gate pass {shlex.quote(json.dumps(value))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def approve_contract(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

    def arm_gate(self, turn_id: str = "turn-1") -> dict:
        payload = self.pre_tool("Bash", "build-brief-gate arm", turn_id)
        self.assertIsNotNone(payload)
        return payload

    def bypass_gate(self, turn_id: str = "turn-1") -> dict:
        payload = self.pre_tool("Bash", "build-brief-gate bypass", turn_id)
        self.assertIsNotNone(payload)
        return payload

    def set_mode(self, mode: str, turn_id: str = "turn-1") -> dict:
        payload = self.pre_tool(
            "Bash", f"build-brief-gate mode {mode}", turn_id
        )
        self.assertIsNotNone(payload)
        return payload

    def test_hook_config_has_no_session_or_prompt_context_injection(self) -> None:
        config = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
        hooks = config["hooks"]
        self.assertNotIn("SessionStart", hooks)
        self.assertNotIn("UserPromptSubmit", hooks)
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "^(Bash|apply_patch|Edit|Write)$")
        pre_tool_handler = hooks["PreToolUse"][0]["hooks"][0]
        self.assertTrue(pre_tool_handler["command"].endswith('build_brief_gate.py\" pre-tool'))

    def test_uninvoked_hook_starts_without_state(self) -> None:
        self.assertFalse((self.plugin_data / "gate-state").exists())

    def test_read_only_bash_is_allowed_before_gate(self) -> None:
        self.assertIsNone(self.pre_tool("Bash", "rg --files"))
        self.assertIsNone(self.pre_tool("Bash", "git status --short"))
        self.assertIsNone(self.pre_tool("Bash", "Get-ChildItem -Force"))
        self.assertIsNone(self.pre_tool("Bash", "Get-Content README.md"))
        self.assertIsNone(self.pre_tool("Bash", "sed -n '1,240p' README.md"))
        self.assertIsNone(
            self.pre_tool("Bash", "sed -n '1,20p' README.md && git status --short")
        )
        self.assertIsNone(self.pre_tool("Bash", "rg --files | sort"))
        self.arm_gate()
        self.assertIsNone(
            self.pre_tool("Bash", "git status --short | head -20")
        )

    def test_uninvoked_hook_allows_unarmed_mutations(self) -> None:
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch")
        )
        self.assertIsNone(self.pre_tool("Bash", "python3 update_schema.py"))

    def test_armed_gate_denies_apply_patch_before_contract(self) -> None:
        self.arm_gate()
        payload = self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("execution contract", output["permissionDecisionReason"])
        self.assertIn("bypass", output["permissionDecisionReason"])

    def test_armed_gate_denies_mutating_bash_before_contract(self) -> None:
        self.arm_gate()
        payload = self.pre_tool("Bash", "python3 update_schema.py")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_bypass_honors_user_opt_out_after_arm(self) -> None:
        self.arm_gate()
        payload = self.bypass_gate()
        self.assertEqual(
            payload["hookSpecificOutput"]["updatedInput"]["command"],
            "echo Build Brief bypassed for this turn",
        )
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch")
        )

    def test_strict_mode_is_session_wide_and_can_return_to_adaptive(self) -> None:
        self.set_mode("strict")
        payload = self.pre_tool(
            "apply_patch", "*** Begin Patch\n*** End Patch", turn_id="turn-2"
        )
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.set_mode("adaptive", turn_id="turn-2")
        self.assertIsNone(
            self.pre_tool(
                "apply_patch", "*** Begin Patch\n*** End Patch", turn_id="turn-2"
            )
        )

    def test_invalid_contract_is_denied(self) -> None:
        command = (
            "build-brief-gate pass "
            "'{\"plain_language\":\"기존 API 동작을 유지합니다.\",\"boundary\":\"api\"}'"
        )
        payload = self.pre_tool("Bash", command)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("invariants", output["permissionDecisionReason"])

    def test_missing_or_empty_minimality_is_denied(self) -> None:
        base_contract = {
            "plain_language": "기존 저장 동작을 유지하면서 검증만 바로잡습니다.",
            "boundary": "existing settings handler",
            "invariants": ["preserve current save behavior"],
            "system_semantics": ["preserve the existing validation boundary"],
            "implementation": ["update the existing validation branch"],
            "phases": ["change", "verify"],
            "steps": ["adjust the validation", "run focused tests"],
            "tasks": ["update handler", "update test"],
            "plan": ["keep the save path and narrow the validation correction"],
            "execution_order": ["handler change before focused verification"],
            "proof": ["run the focused settings tests"],
        }
        for minimality in (None, [], [""]):
            with self.subTest(minimality=minimality):
                contract = dict(base_contract)
                if minimality is not None:
                    contract["minimality"] = minimality
                command = (
                    "build-brief-gate pass "
                    f"{shlex.quote(json.dumps(contract))}"
                )
                payload = self.pre_tool("Bash", command)
                output = payload["hookSpecificOutput"]
                self.assertEqual(output["permissionDecision"], "deny")
                self.assertIn("minimality", output["permissionDecisionReason"])

    def test_plain_language_explanation_is_required(self) -> None:
        contract = {
            "boundary": "existing settings handler",
            "invariants": ["preserve current save behavior"],
            "system_semantics": ["preserve the existing validation boundary"],
            "minimality": ["reuse the current handler"],
            "proof": ["run the focused settings tests"],
        }
        command = f"build-brief-gate pass {shlex.quote(json.dumps(contract))}"
        payload = self.pre_tool("Bash", command)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("plain_language", output["permissionDecisionReason"])

    def test_all_execution_contract_fields_are_required(self) -> None:
        base_contract = self.contract()
        for field in (
            "implementation",
            "steps",
            "phases",
            "tasks",
            "plan",
            "execution_order",
        ):
            with self.subTest(field=field):
                contract = dict(base_contract)
                del contract[field]
                command = f"build-brief-gate pass {shlex.quote(json.dumps(contract))}"
                payload = self.pre_tool("Bash", command)
                output = payload["hookSpecificOutput"]
                self.assertEqual(output["permissionDecision"], "deny")
                self.assertIn(field, output["permissionDecisionReason"])

    def test_unknown_contract_field_is_rejected(self) -> None:
        contract = {**self.contract(), "surprise_scope": ["rewrite unrelated API"]}
        command = f"build-brief-gate stage {shlex.quote(json.dumps(contract))}"
        payload = self.pre_tool("Bash", command)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("surprise_scope", output["permissionDecisionReason"])

    def test_pass_requires_a_staged_contract(self) -> None:
        self.arm_gate("turn-2")
        payload = self.pass_gate(turn_id="turn-2")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("No staged", output["permissionDecisionReason"])

    def test_stage_requires_explicit_arm(self) -> None:
        payload = self.stage_gate(turn_id="turn-1")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("Arm Build Brief", output["permissionDecisionReason"])

    def test_changed_contract_requires_restaging_and_reapproval(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        revised = self.contract()
        revised["tasks"] = [*revised["tasks"], "rewrite unrelated API"]
        self.arm_gate("turn-2")
        payload = self.pass_gate(revised, "turn-2")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("differs", output["permissionDecisionReason"])

    def test_revised_contract_can_pass_after_restaging_and_reapproval(self) -> None:
        original = self.contract()
        self.arm_gate("turn-1")
        self.stage_gate(original, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(original, "turn-2")

        revised = self.contract()
        revised["tasks"] = [*revised["tasks"], "update approved API documentation"]
        self.stage_gate(revised, "turn-2")
        blocked = self.pre_tool(
            "apply_patch", "*** Begin Patch\n*** End Patch", "turn-2"
        )
        self.assertEqual(
            blocked["hookSpecificOutput"]["permissionDecision"], "deny"
        )

        self.arm_gate("turn-3")
        payload = self.pass_gate(revised, "turn-3")
        self.assertEqual(
            payload["hookSpecificOutput"]["updatedInput"]["command"],
            "echo Build Brief mutation gate passed",
        )

    def test_bypass_discards_the_staged_contract(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        self.bypass_gate("turn-1")
        self.arm_gate("turn-2")
        payload = self.pass_gate(turn_id="turn-2")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("No staged", output["permissionDecisionReason"])

    def test_valid_contract_is_recorded_and_control_command_is_rewritten(self) -> None:
        self.arm_gate("turn-1")
        staged = self.stage_gate(turn_id="turn-1")
        self.assertEqual(
            staged["hookSpecificOutput"]["updatedInput"]["command"],
            "echo Build Brief execution contract staged",
        )
        self.arm_gate("turn-2")
        payload = self.pass_gate(turn_id="turn-2")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "allow")
        self.assertEqual(
            output["updatedInput"]["command"], "echo Build Brief mutation gate passed"
        )
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        self.assertIsNone(self.pre_tool("Bash", "python3 update_schema.py", "turn-2"))

    def test_state_records_a_digest_not_contract_plaintext(self) -> None:
        self.approve_contract()
        state_text = "\n".join(
            path.read_text()
            for path in (self.plugin_data / "gate-state").glob("*.json")
        )
        self.assertIn("contract_digest", state_text)
        self.assertNotIn("inventory write path", state_text)
        self.assertNotIn("threshold crossing", state_text)
        self.assertNotIn("existing notification mechanism", state_text)
        self.assertNotIn("재고가 임계값", state_text)

    def test_gate_pass_does_not_leak_into_a_new_turn(self) -> None:
        self.set_mode("strict")
        self.stage_gate(turn_id="turn-1")
        self.pass_gate(turn_id="turn-1")
        payload = self.pre_tool(
            "apply_patch",
            "*** Begin Patch\n*** End Patch",
            turn_id="turn-2",
        )
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_shell_chaining_is_not_treated_as_read_only(self) -> None:
        self.arm_gate()
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
        self.arm_gate()
        for command in (
            "sed -i s/old/new/ src/app.py",
            "sed -n '1,20w captured.txt' src/app.py",
            "sed -n '1e touch captured.txt' src/app.py",
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
