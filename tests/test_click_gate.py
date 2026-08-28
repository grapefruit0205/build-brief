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
        "CLICK_GATE_UNDER_TEST",
        Path(__file__).parents[1] / "hooks" / "click_gate.py",
    )
)
HOOK_CONFIG = Path(
    os.environ.get(
        "CLICK_HOOK_CONFIG_UNDER_TEST",
        Path(__file__).parents[1] / "hooks" / "hooks.json",
    )
)


class ClickGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.plugin_data = Path(self.temporary.name) / "plugin-data"
        self.workspace = Path(self.temporary.name) / "workspace"
        self.workspace.mkdir()
        self.base_event = {
            "session_id": "session-1",
            "turn_id": "turn-1",
            "cwd": str(self.workspace),
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
            "outcome": "send one alert when inventory crosses below its threshold",
            "boundary": {
                "in_scope": ["inventory threshold transition and notification path"],
                "out_of_scope": ["unrelated inventory and purchasing behavior"],
            },
            "must_hold": [
                "send at most one alert per threshold crossing",
                "preserve the existing inventory write behavior",
            ],
            "build": {
                "approach": [
                    "extend the existing threshold transition and notification path"
                ],
                "semantics": [
                    "deduplicate notification intent at the inventory write boundary"
                ],
                "order": ["record the inventory transition before dispatching the alert"],
            },
            "verification": {
                "scale": "focused",
                "done_when": [
                    "focused concurrent threshold tests send one alert per crossing"
                ],
            },
            "plain_language": (
                "재고가 임계값 아래로 내려갈 때 같은 상황에서는 알림을 한 번만 보내고, "
                "승인된 순서대로 현재 알림 경로를 수정하고 검증합니다."
            ),
        }

    def stage_gate(
        self, contract: dict | None = None, turn_id: str = "turn-1"
    ) -> dict:
        value = contract or self.contract()
        command = f"click-gate stage {shlex.quote(json.dumps(value))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def pass_gate(
        self, contract: dict | None = None, turn_id: str = "turn-2"
    ) -> dict:
        value = contract or self.contract()
        command = f"click-gate pass {shlex.quote(json.dumps(value))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def approve_contract(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

    def arm_gate(self, turn_id: str = "turn-1") -> dict:
        payload = self.pre_tool("Bash", "click-gate arm", turn_id)
        self.assertIsNotNone(payload)
        return payload

    def bypass_gate(self, turn_id: str = "turn-1") -> dict:
        payload = self.pre_tool("Bash", "click-gate bypass", turn_id)
        self.assertIsNotNone(payload)
        return payload

    def set_mode(self, mode: str, turn_id: str = "turn-1") -> dict:
        payload = self.pre_tool(
            "Bash", f"click-gate mode {mode}", turn_id
        )
        self.assertIsNotNone(payload)
        return payload

    def verification_command(self, exit_code: int = 0) -> str:
        arguments = [sys.executable, "-c", f"raise SystemExit({exit_code})"]
        return subprocess.list2cmdline(arguments) if os.name == "nt" else shlex.join(arguments)

    def read_file_command(self, path: str, fail_hard: bool = False) -> str:
        if os.name == "nt":
            error_action = " -ErrorAction Stop" if fail_hard else ""
            return f"Get-Content -Raw{error_action} {path}"
        return f"sed -n '1,99999p' {path}"

    def verify_gate(
        self, commands: list[str], turn_id: str = "turn-2"
    ) -> dict:
        batch = {"commands": commands}
        command = f"click-gate verify {shlex.quote(json.dumps(batch))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def run_rewritten(self, payload: dict) -> subprocess.CompletedProcess[str]:
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        environment = os.environ.copy()
        environment["PLUGIN_DATA"] = str(self.plugin_data)
        return subprocess.run(
            command,
            shell=True,
            cwd=self.workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_hook_config_has_no_session_or_prompt_context_injection(self) -> None:
        config = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
        hooks = config["hooks"]
        self.assertNotIn("SessionStart", hooks)
        self.assertNotIn("UserPromptSubmit", hooks)
        self.assertEqual(
            hooks["PreToolUse"][0]["matcher"],
            "^(Bash|apply_patch|Edit|Write|update_plan|functions\\.update_plan)$",
        )
        pre_tool_handler = hooks["PreToolUse"][0]["hooks"][0]
        self.assertTrue(pre_tool_handler["command"].endswith('click_gate.py\" pre-tool'))

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

    def test_uninvoked_plan_and_exploration_remain_fail_open(self) -> None:
        self.assertIsNone(self.pre_tool("update_plan", ""))
        self.assertIsNone(self.pre_tool("Bash", "rg --files"))

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
            "echo Click bypassed for this turn",
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
            "click-gate pass "
            "'{\"outcome\":\"API 동작을 수정합니다.\","
            "\"plain_language\":\"기존 API 동작을 유지합니다.\","
            "\"boundary\":{\"in_scope\":[\"api\"],\"out_of_scope\":[]}}'"
        )
        payload = self.pre_tool("Bash", command)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("must_hold", output["permissionDecisionReason"])

    def test_optional_build_constraints_are_omitted_or_non_empty(self) -> None:
        compact = self.contract()
        compact["build"] = {"approach": compact["build"]["approach"]}
        self.arm_gate()
        payload = self.stage_gate(compact)
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "allow")

        for field in ("semantics", "order"):
            with self.subTest(field=field):
                invalid = self.contract()
                invalid["build"] = {**invalid["build"], field: []}
                payload = self.pre_tool(
                    "Bash",
                    f"click-gate stage {shlex.quote(json.dumps(invalid))}",
                )
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    field,
                    payload["hookSpecificOutput"]["permissionDecisionReason"],
                )

    def test_plain_language_explanation_is_required(self) -> None:
        contract = self.contract()
        del contract["plain_language"]
        command = f"click-gate pass {shlex.quote(json.dumps(contract))}"
        payload = self.pre_tool("Bash", command)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("plain_language", output["permissionDecisionReason"])

    def test_all_compact_contract_areas_are_required(self) -> None:
        base_contract = self.contract()
        for field in (
            "outcome",
            "boundary",
            "must_hold",
            "build",
            "verification",
            "plain_language",
        ):
            with self.subTest(field=field):
                contract = dict(base_contract)
                del contract[field]
                command = f"click-gate pass {shlex.quote(json.dumps(contract))}"
                payload = self.pre_tool("Bash", command)
                output = payload["hookSpecificOutput"]
                self.assertEqual(output["permissionDecision"], "deny")
                self.assertIn(field, output["permissionDecisionReason"])

    def test_boundary_requires_scope_but_allows_no_explicit_exclusion(self) -> None:
        compact = self.contract()
        compact["boundary"]["out_of_scope"] = []
        self.arm_gate()
        payload = self.stage_gate(compact)
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "allow")

        for field in ("in_scope", "out_of_scope"):
            with self.subTest(field=field):
                invalid = self.contract()
                del invalid["boundary"][field]
                payload = self.pre_tool(
                    "Bash",
                    f"click-gate stage {shlex.quote(json.dumps(invalid))}",
                )
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    field,
                    payload["hookSpecificOutput"]["permissionDecisionReason"],
                )

    def test_verification_is_required_and_bounded(self) -> None:
        missing = self.contract()
        del missing["verification"]
        payload = self.pre_tool(
            "Bash", f"click-gate stage {shlex.quote(json.dumps(missing))}"
        )
        self.assertIn(
            "verification", payload["hookSpecificOutput"]["permissionDecisionReason"]
        )

        for scale in ("quick", "focused", "full"):
            with self.subTest(scale=scale):
                contract = self.contract()
                contract["verification"]["scale"] = scale
                self.arm_gate()
                payload = self.stage_gate(contract)
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "allow"
                )

        invalid = self.contract()
        invalid["verification"]["scale"] = "every-step"
        payload = self.pre_tool(
            "Bash", f"click-gate stage {shlex.quote(json.dumps(invalid))}"
        )
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "quick, focused, full",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )

        gated = self.contract()
        gated["verification"]["intermediate_gate"] = (
            "confirm immediately before applying the irreversible migration"
        )
        self.arm_gate()
        payload = self.stage_gate(gated)
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "allow")

        invalid_gate = self.contract()
        invalid_gate["verification"]["intermediate_gate"] = ""
        payload = self.pre_tool(
            "Bash", f"click-gate stage {shlex.quote(json.dumps(invalid_gate))}"
        )
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "intermediate_gate",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_quick_budget_accepts_one_command_and_rejects_two(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")

        command = self.verification_command()
        denied = self.verify_gate([command, command])
        self.assertEqual(
            denied["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "allows 1 unit",
            denied["hookSpecificOutput"]["permissionDecisionReason"],
        )
        allowed = self.verify_gate([command])
        self.assertEqual(
            allowed["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "run-verification", allowed["hookSpecificOutput"]["updatedInput"]["command"]
        )

    def test_broad_and_expensive_checks_consume_more_budget(self) -> None:
        quick = self.contract()
        quick["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(quick, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(quick, "turn-2")
        broad = self.verify_gate(["python3 -m unittest discover -s tests"])
        self.assertEqual(
            broad["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn("costs 3", broad["hookSpecificOutput"]["permissionDecisionReason"])

        for command in ("pytest tests", "python3 -m pytest tests", "vitest run"):
            with self.subTest(command=command):
                denied = self.verify_gate([command])
                self.assertEqual(
                    denied["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    "costs 3",
                    denied["hookSpecificOutput"]["permissionDecisionReason"],
                )

        full = self.contract()
        full["verification"]["scale"] = "full"
        self.bypass_gate("turn-2")
        self.arm_gate("turn-3")
        self.stage_gate(full, "turn-3")
        self.arm_gate("turn-4")
        self.pass_gate(full, "turn-4")
        expensive = self.verify_gate(
            ["npx playwright test", "python3 -m unittest discover -s tests"],
            "turn-4",
        )
        self.assertEqual(
            expensive["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    def test_verification_batch_rejects_shell_chaining(self) -> None:
        self.approve_contract()
        payload = self.verify_gate(["pytest tests/unit && pytest tests/integration"])
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "without chaining",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_successful_final_batch_is_not_repeated_until_code_changes(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")
        command = self.verification_command()

        first = self.verify_gate([command])
        completed = self.run_rewritten(first)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        state_text = "\n".join(
            path.read_text()
            for path in (self.plugin_data / "gate-state").glob("*.json")
        )
        self.assertNotIn("raise SystemExit", state_text)
        repeated = self.verify_gate([command])
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "already passed",
            repeated["hookSpecificOutput"]["permissionDecisionReason"],
        )

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        stale_retry = self.verify_gate([command])
        self.assertEqual(
            stale_retry["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    def test_identical_successful_read_is_blocked_until_mutation(self) -> None:
        (self.workspace / "README.md").write_text("hello\n", encoding="utf-8")
        self.approve_contract()
        command = self.read_file_command("README.md")

        first = self.pre_tool("Bash", command, "turn-2")
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        completed = self.run_rewritten(first)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "hello")

        repeated = self.pre_tool("Bash", command, "turn-2")
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "identical successful read",
            repeated["hookSpecificOutput"]["permissionDecisionReason"],
        )

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        after_mutation = self.pre_tool("Bash", command, "turn-2")
        self.assertEqual(
            after_mutation["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    def test_observation_digest_normalizes_shell_spacing(self) -> None:
        (self.workspace / "README.md").write_text("hello\n", encoding="utf-8")
        self.approve_contract()

        first = self.pre_tool(
            "Bash", "sed -n '1,99999p' README.md", "turn-2"
        )
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        repeated = self.pre_tool(
            "Bash", "sed   -n   '1,99999p'   README.md", "turn-2"
        )
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "identical successful read",
            repeated["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_running_observation_blocks_mutation_and_final_verification(self) -> None:
        (self.workspace / "README.md").write_text("hello\n", encoding="utf-8")
        self.approve_contract()
        observation = self.pre_tool(
            "Bash", self.read_file_command("README.md"), "turn-2"
        )
        self.assertEqual(
            observation["hookSpecificOutput"]["permissionDecision"], "allow"
        )

        mutation = self.pre_tool(
            "apply_patch", "*** Begin Patch\n*** End Patch", "turn-2"
        )
        self.assertEqual(
            mutation["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "read or search is running",
            mutation["hookSpecificOutput"]["permissionDecisionReason"],
        )

        verification = self.verify_gate([self.verification_command()])
        self.assertEqual(
            verification["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "read or search to finish",
            verification["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_failed_or_incomplete_read_gets_one_unchanged_retry(self) -> None:
        self.approve_contract()
        missing = self.read_file_command("missing.txt", fail_hard=True)

        first_failure = self.pre_tool("Bash", missing, "turn-2")
        self.assertNotEqual(self.run_rewritten(first_failure).returncode, 0)
        retry_failure = self.pre_tool("Bash", missing, "turn-2")
        self.assertNotEqual(self.run_rewritten(retry_failure).returncode, 0)
        blocked_failure = self.pre_tool("Bash", missing, "turn-2")
        self.assertEqual(
            blocked_failure["hookSpecificOutput"]["permissionDecision"], "deny"
        )

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        (self.workspace / "large.txt").write_text(
            "x" * 60_000, encoding="utf-8"
        )
        large = self.read_file_command("large.txt")
        first_large = self.pre_tool("Bash", large, "turn-2")
        completed = self.run_rewritten(first_large)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("exceeded 48,000 bytes", completed.stderr)
        retry_large = self.pre_tool("Bash", large, "turn-2")
        self.assertEqual(
            retry_large["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertEqual(self.run_rewritten(retry_large).returncode, 0)
        blocked_large = self.pre_tool("Bash", large, "turn-2")
        self.assertEqual(
            blocked_large["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_approved_boundary_blocks_repository_wide_inventory_rescans(self) -> None:
        self.approve_contract()
        for command in (
            "rg --files",
            "find . -maxdepth 2 -type f",
            "tree",
            "ls -R",
            "Get-ChildItem -Recurse -Path .",
            "git ls-files",
            "rg --files . src",
        ):
            with self.subTest(command=command):
                payload = self.pre_tool("Bash", command, "turn-2")
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    "repository-wide inventory rescan",
                    payload["hookSpecificOutput"]["permissionDecisionReason"],
                )

        for command in (
            "rg --files src",
            "find src -type f",
            "Get-ChildItem -Recurse -Path src",
        ):
            with self.subTest(command=command):
                payload = self.pre_tool("Bash", command, "turn-2")
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "allow"
                )

        targeted = self.pre_tool("Bash", "rg threshold .", "turn-2")
        self.assertEqual(
            targeted["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    def test_approved_contract_blocks_new_plan_tool_calls(self) -> None:
        self.approve_contract()
        for tool_name in ("update_plan", "functions.update_plan"):
            with self.subTest(tool_name=tool_name):
                payload = self.pre_tool(tool_name, "", "turn-2")
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    "new plan after approval",
                    payload["hookSpecificOutput"]["permissionDecisionReason"],
                )

    def test_running_batch_blocks_parallel_mutation_and_verification(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")
        self.verify_gate([self.verification_command()])

        for tool_name, command in (
            ("apply_patch", "*** Begin Patch\n*** End Patch"),
            ("Bash", "pytest tests/test_inventory.py"),
        ):
            with self.subTest(tool_name=tool_name):
                payload = self.pre_tool(tool_name, command, "turn-2")
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    "verification batch is running",
                    payload["hookSpecificOutput"]["permissionDecisionReason"],
                )

    def test_failed_batch_allows_one_unchanged_retry_then_requires_mutation(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")
        command = self.verification_command(exit_code=1)

        first = self.verify_gate([command])
        self.assertEqual(self.run_rewritten(first).returncode, 1)
        transient_retry = self.verify_gate([command])
        self.assertEqual(self.run_rewritten(transient_retry).returncode, 1)
        blocked = self.verify_gate([command])
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "subsequent code mutation",
            blocked["hookSpecificOutput"]["permissionDecisionReason"],
        )

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        after_fix = self.verify_gate([command])
        self.assertEqual(after_fix["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_broad_checks_must_use_the_budgeted_runner_after_approval(self) -> None:
        self.approve_contract()
        for command in (
            "python3 -m unittest discover -s tests",
            "pytest tests",
            "python3 -m pytest tests",
            "vitest run",
            "pytest tests/unit && pytest tests/integration",
            "pytest tests/unit > verification.txt",
            "npm test -- --runInBand",
        ):
            with self.subTest(command=command):
                payload = self.pre_tool("Bash", command, "turn-2")
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    "click-gate verify",
                    payload["hookSpecificOutput"]["permissionDecisionReason"],
                )
        self.assertIsNone(
            self.pre_tool("Bash", "pytest tests/test_inventory.py", "turn-2")
        )

    def test_uninvoked_verification_remains_fail_open(self) -> None:
        self.assertIsNone(
            self.pre_tool("Bash", "python3 -m unittest discover -s tests")
        )

    def test_unknown_contract_field_is_rejected(self) -> None:
        contract = {**self.contract(), "surprise_scope": ["rewrite unrelated API"]}
        command = f"click-gate stage {shlex.quote(json.dumps(contract))}"
        payload = self.pre_tool("Bash", command)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("surprise_scope", output["permissionDecisionReason"])

    def test_contract_size_is_capped_to_prevent_planning_bloat(self) -> None:
        contract = self.contract()
        contract["outcome"] = "x" * 4_000
        command = f"click-gate stage {shlex.quote(json.dumps(contract))}"
        payload = self.pre_tool("Bash", command)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("4,000", output["permissionDecisionReason"])

    def test_legacy_verbose_contract_fields_are_rejected(self) -> None:
        for field in (
            "invariants",
            "system_semantics",
            "implementation",
            "phases",
            "steps",
            "tasks",
            "plan",
            "execution_order",
            "minimality",
            "proof",
        ):
            with self.subTest(field=field):
                contract = {**self.contract(), field: ["legacy duplicate"]}
                command = f"click-gate stage {shlex.quote(json.dumps(contract))}"
                payload = self.pre_tool("Bash", command)
                output = payload["hookSpecificOutput"]
                self.assertEqual(output["permissionDecision"], "deny")
                self.assertIn(field, output["permissionDecisionReason"])

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
        self.assertIn("Arm Click", output["permissionDecisionReason"])

    def test_pass_rejects_a_contract_different_from_the_staged_contract(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        revised = self.contract()
        revised["build"]["approach"] = [
            *revised["build"]["approach"],
            "rewrite unrelated API",
        ]
        self.arm_gate("turn-2")
        payload = self.pass_gate(revised, "turn-2")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("differs", output["permissionDecisionReason"])

    def test_contract_can_be_replaced_before_approval(self) -> None:
        original = self.contract()
        self.arm_gate("turn-1")
        self.stage_gate(original, "turn-1")
        revised = self.contract()
        revised["build"]["approach"] = [
            *revised["build"]["approach"],
            "update approved API documentation",
        ]
        self.stage_gate(revised, "turn-1")
        self.arm_gate("turn-2")
        payload = self.pass_gate(revised, "turn-2")
        self.assertEqual(
            payload["hookSpecificOutput"]["updatedInput"]["command"],
            "echo Click mutation gate passed",
        )

    def test_approved_contract_cannot_be_replaced_mid_run(self) -> None:
        original = self.contract()
        self.arm_gate("turn-1")
        self.stage_gate(original, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(original, "turn-2")

        replacement = self.contract()
        replacement["build"]["approach"] = [
            *replacement["build"]["approach"],
            "rewrite unrelated API",
        ]
        payload = self.stage_gate(replacement, "turn-2")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("one approved contract", output["permissionDecisionReason"])

    def test_approved_contract_cannot_be_restaged_unchanged(self) -> None:
        self.approve_contract()
        payload = self.stage_gate(turn_id="turn-2")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("Do not restage", output["permissionDecisionReason"])

    def test_verification_change_requires_the_exact_staged_contract(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        changed = self.contract()
        changed["verification"]["scale"] = "full"
        self.arm_gate("turn-2")
        payload = self.pass_gate(changed, "turn-2")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("differs", output["permissionDecisionReason"])

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
            "echo Click execution contract staged",
        )
        self.arm_gate("turn-2")
        payload = self.pass_gate(turn_id="turn-2")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "allow")
        self.assertEqual(
            output["updatedInput"]["command"], "echo Click mutation gate passed"
        )
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        self.assertIsNone(self.pre_tool("Bash", "python3 update_schema.py", "turn-2"))

    def test_state_records_a_digest_not_contract_plaintext(self) -> None:
        self.approve_contract()
        (self.workspace / "private-marker.txt").write_text(
            "private marker\n", encoding="utf-8"
        )
        observation = self.pre_tool(
            "Bash", self.read_file_command("private-marker.txt"), "turn-2"
        )
        self.assertEqual(self.run_rewritten(observation).returncode, 0)
        state_text = "\n".join(
            path.read_text()
            for path in (self.plugin_data / "gate-state").glob("*.json")
        )
        self.assertIn("contract_digest", state_text)
        self.assertIn('"scale":"focused"', state_text)
        self.assertIn('"unit_limit":4', state_text)
        self.assertNotIn("inventory write path", state_text)
        self.assertNotIn("threshold crossing", state_text)
        self.assertNotIn("existing notification mechanism", state_text)
        self.assertNotIn("재고가 임계값", state_text)
        self.assertNotIn("private-marker.txt", state_text)
        self.assertNotIn("private marker", state_text)

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
