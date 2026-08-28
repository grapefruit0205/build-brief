from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


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
CLICK_GATE_SPEC = importlib.util.spec_from_file_location("click_gate_under_test", SCRIPT)
assert CLICK_GATE_SPEC is not None and CLICK_GATE_SPEC.loader is not None
CLICK_GATE = importlib.util.module_from_spec(CLICK_GATE_SPEC)
CLICK_GATE_SPEC.loader.exec_module(CLICK_GATE)


class ClickGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.plugin_data = Path(self.temporary.name) / "plugin-data"
        self.workspace = Path(self.temporary.name) / "workspace"
        self.workspace.mkdir()
        self.submitted_turns: set[str] = set()
        (self.workspace / "verification_fixture.py").write_text(
            "import unittest\n\n"
            "class VerificationFixture(unittest.TestCase):\n"
            "    def test_pass(self):\n"
            "        self.assertTrue(True)\n\n"
            "    def test_fail(self):\n"
            "        self.fail('expected verification failure')\n",
            encoding="utf-8",
        )
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
        environment["CLICK_CONFIG_HOME"] = str(self.plugin_data)
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

    def pre_tool(
        self,
        tool_name: str,
        command: str,
        turn_id: str = "turn-1",
        *,
        submit_prompt: bool = True,
    ) -> dict | None:
        if submit_prompt and turn_id not in self.submitted_turns:
            self.prompt_submit("test user request", turn_id)
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

    def prompt_submit(
        self, prompt: str = "review this code", turn_id: str = "turn-1"
    ) -> dict:
        event = {
            **self.base_event,
            "turn_id": turn_id,
            "hook_event_name": "UserPromptSubmit",
            "prompt": prompt,
        }
        result, payload = self.run_hook("prompt-submit", event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNotNone(payload)
        self.submitted_turns.add(turn_id)
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

    def set_default(self, mode: str, turn_id: str = "turn-1") -> dict:
        payload = self.pre_tool(
            "Bash", f"click-gate default {mode}", turn_id
        )
        self.assertIsNotNone(payload)
        return payload

    def start_review(self, turn_id: str = "turn-1") -> dict:
        payload = self.pre_tool("Bash", "click-gate review", turn_id)
        self.assertIsNotNone(payload)
        return payload

    def verification_argv(self, exit_code: int = 0) -> list[str]:
        test_name = "test_pass" if exit_code == 0 else "test_fail"
        return [
            sys.executable,
            "-m",
            "unittest",
            f"verification_fixture.VerificationFixture.{test_name}",
        ]

    def initialize_git(self, *tracked_paths: str) -> None:
        initialized = subprocess.run(
            ["git", "init", "--quiet"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        subprocess.run(
            ["git", "add", *tracked_paths],
            cwd=self.workspace,
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Click Tests",
                "-c",
                "user.email=click-tests@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "fixture",
            ],
            cwd=self.workspace,
            check=True,
        )

    def read_file_command(self, path: str, fail_hard: bool = False) -> str:
        if os.name == "nt":
            return f"Get-Content -Raw {path}"
        return f"sed -n '1,99999p' {path}"

    def inspect_gate(
        self, commands: list[list[str]], turn_id: str = "turn-1"
    ) -> dict:
        request = {"version": 1, "commands": commands}
        command = f"click-gate inspect {shlex.quote(json.dumps(request))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def mutate_gate(self, argv: list[str], turn_id: str = "turn-2") -> dict:
        request = {"version": 1, "argv": argv}
        command = f"click-gate mutate {shlex.quote(json.dumps(request))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def verification_class(self, command: str) -> str:
        lowered = command.lower()
        if any(marker in lowered for marker in ("playwright", "coverage", "audit")):
            return "deep"
        if any(
            marker in lowered
            for marker in (
                "unittest discover",
                "pytest tests",
                "vitest run",
                "npm test",
            )
        ):
            return "broad"
        return "targeted"

    def verify_gate(
        self, commands: list[str | list[str]], turn_id: str = "turn-2"
    ) -> dict:
        checks = []
        for value in commands:
            if isinstance(value, list):
                argv = value
                rendered = " ".join(value)
            else:
                argv = shlex.split(value, posix=True)
                rendered = value
            checks.append(
                {"argv": argv, "class": self.verification_class(rendered)}
            )
        batch = {"version": 1, "checks": checks}
        command = f"click-gate verify {shlex.quote(json.dumps(batch))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def verify_checks(
        self, checks: list[dict[str, object]], turn_id: str = "turn-2"
    ) -> dict:
        batch = {"version": 1, "checks": checks}
        command = f"click-gate verify {shlex.quote(json.dumps(batch))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def legacy_verify_gate(self, commands: list[str], turn_id: str = "turn-2") -> dict:
        batch = {"version": 1, "commands": commands}
        command = f"click-gate verify {shlex.quote(json.dumps(batch))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def run_rewritten(self, payload: dict) -> subprocess.CompletedProcess[str]:
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        environment = os.environ.copy()
        environment["PLUGIN_DATA"] = str(self.plugin_data)
        environment["CLICK_CONFIG_HOME"] = str(self.plugin_data)
        return subprocess.run(
            command,
            shell=True,
            cwd=self.workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_hook_config_loads_mode_for_each_prompt(self) -> None:
        config = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
        hooks = config["hooks"]
        self.assertNotIn("SessionStart", hooks)
        self.assertIn("UserPromptSubmit", hooks)
        prompt_handler = hooks["UserPromptSubmit"][0]["hooks"][0]
        self.assertTrue(
            prompt_handler["command"].endswith('click_gate.py" prompt-submit')
        )
        self.assertEqual(
            hooks["PreToolUse"][0]["matcher"],
            "^(Bash|apply_patch|Edit|Write|update_plan|functions\\.update_plan)$",
        )
        pre_tool_handler = hooks["PreToolUse"][0]["hooks"][0]
        self.assertTrue(pre_tool_handler["command"].endswith('click_gate.py\" pre-tool'))
        self.assertEqual(prompt_handler["timeout"], 7)
        self.assertEqual(pre_tool_handler["timeout"], 7)

    def test_uninvoked_hook_starts_without_state(self) -> None:
        self.assertFalse((self.plugin_data / "gate-state").exists())

    def test_read_only_bash_is_allowed_before_gate(self) -> None:
        self.assertIsNone(self.pre_tool("Bash", "rg --files"))
        self.assertIsNone(self.pre_tool("Bash", "git status --short"))
        self.assertIsNone(self.pre_tool("Bash", "Get-Content README.md"))
        self.assertIsNone(self.pre_tool("Bash", "sed -n '1,240p' README.md"))
        self.assertIsNone(
            self.pre_tool("Bash", "sed -n '1,20p' README.md && git status --short")
        )
        piped = self.pre_tool("Bash", "rg --files | sort")
        self.assertEqual(piped["hookSpecificOutput"]["permissionDecision"], "deny")
        self.arm_gate()
        piped_after_arm = self.pre_tool("Bash", "git status --short | head -20")
        self.assertEqual(
            piped_after_arm["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_unsupported_powershell_cmdlets_are_not_read_only_capabilities(self) -> None:
        for command in (
            "Get-ChildItem",
            "Get-Command",
            "Get-Item",
            "Get-Location",
            "Measure-Object",
            "Resolve-Path",
            "Select-String",
            "Test-Path",
        ):
            with self.subTest(command=command):
                self.assertFalse(CLICK_GATE._is_read_only_tokens([command]))

    def test_unset_default_blocks_first_mutation_and_requests_one_choice(self) -> None:
        payload = self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("Always ON", reason)
        self.assertIn("Manual", reason)

    def test_structured_inspection_runs_shell_free_and_blocks_repeat(self) -> None:
        self.approve_contract()
        initialized = subprocess.run(
            ["git", "init", "--quiet"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        first = self.inspect_gate([["git", "status", "--short"]], "turn-2")
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        repeated = self.inspect_gate([["git", "status", "--short"]], "turn-2")
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_structured_inspection_rejects_shells_and_write_options(self) -> None:
        for commands in (
            [["bash", "-c", "cat README.md"]],
            [["find", ".", "-delete"]],
            [["sort", "README.md", "-o", "sorted.txt"]],
        ):
            with self.subTest(commands=commands):
                denied = self.inspect_gate(commands)
                self.assertEqual(
                    denied["hookSpecificOutput"]["permissionDecision"], "deny"
                )

    def test_structured_ssh_inspection_accepts_only_bounded_remote_reads(self) -> None:
        allowed = (
            ["ssh", "example-host", "hostname"],
            ["ssh", "user@example-host", "cat", "/etc/os-release"],
            [
                "ssh",
                "example-host",
                "docker",
                "ps",
                "--format",
                "{{.Names}}|{{.Image}}",
            ],
            [
                "ssh",
                "example-host",
                "nvidia-smi",
                "--query-gpu=name,uuid",
                "--format=csv,noheader",
            ],
            ["ssh", "example-host", "systemctl", "is-active", "docker"],
            [
                "ssh",
                "example-host",
                "git",
                "-C",
                "/srv/project",
                "merge-base",
                "HEAD",
                "origin/main",
            ],
            ["ssh", "example-host", "git", "remote"],
            ["ssh", "example-host", "git", "remote", "-v"],
            [
                "ssh",
                "example-host",
                "git",
                "remote",
                "get-url",
                "--all",
                "origin",
            ],
        )
        denied = (
            ["ssh", "-o", "ProxyCommand=helper", "example-host", "hostname"],
            ["ssh", "example-host", "docker ps"],
            ["ssh", "example-host", "sudo", "-n", "true"],
            ["ssh", "example-host", "bash", "-c", "hostname"],
            ["ssh", "example-host", "ssh", "other-host", "hostname"],
            ["ssh", "example-host", "docker", "stop", "service"],
            ["ssh", "example-host", "docker", "exec", "service", "true"],
            ["ssh", "example-host", "systemctl", "restart", "service"],
            ["ssh", "example-host", "nvidia-smi", "-pl", "100"],
            ["ssh", "example-host", "hostname", "replacement"],
            ["ssh", "example-host", "git", "fetch", "origin"],
            [
                "ssh",
                "example-host",
                "git",
                "remote",
                "add",
                "backup",
                "url",
            ],
            [
                "ssh",
                "example-host",
                "git",
                "remote",
                "set-url",
                "origin",
                "url",
            ],
            ["ssh", "example-host", "git", "remote", "get-url"],
            [
                "ssh",
                "example-host",
                "git",
                "remote",
                "get-url",
                "origin",
                "extra",
            ],
        )

        for argv in allowed:
            with self.subTest(allowed=argv):
                self.assertTrue(CLICK_GATE._is_read_only_tokens(argv))
        for argv in denied:
            with self.subTest(denied=argv):
                self.assertFalse(CLICK_GATE._is_read_only_tokens(argv))
                payload = self.inspect_gate([argv])
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "deny"
                )

    def test_git_remote_read_policy_is_narrow_for_local_and_ssh(self) -> None:
        allowed_arguments = (
            ["remote"],
            ["remote", "-v"],
            ["remote", "--verbose"],
            ["remote", "get-url", "origin"],
            ["remote", "get-url", "--push", "origin"],
            ["remote", "get-url", "--all", "--push", "origin"],
        )
        denied_arguments = (
            ["remote", "show", "origin"],
            ["remote", "add", "backup", "url"],
            ["remote", "remove", "origin"],
            ["remote", "rename", "origin", "upstream"],
            ["remote", "set-url", "origin", "url"],
            ["remote", "update"],
            ["remote", "prune", "origin"],
            ["remote", "get-url"],
            ["remote", "get-url", "--all"],
            ["remote", "get-url", "--all", "--all", "origin"],
            ["remote", "get-url", "origin", "--push"],
        )

        for arguments in allowed_arguments:
            with self.subTest(allowed=arguments):
                local = ["git", "-C", "/srv/project", *arguments]
                remote = ["ssh", "example-host", *local]
                self.assertTrue(CLICK_GATE._is_read_only_tokens(local))
                self.assertTrue(CLICK_GATE._is_read_only_tokens(remote))
        for arguments in denied_arguments:
            with self.subTest(denied=arguments):
                local = ["git", "-C", "/srv/project", *arguments]
                remote = ["ssh", "example-host", *local]
                self.assertFalse(CLICK_GATE._is_read_only_tokens(local))
                self.assertFalse(CLICK_GATE._is_read_only_tokens(remote))

    def test_direct_structured_ssh_read_becomes_an_observation(self) -> None:
        self.approve_contract()
        command = (
            "ssh example-host docker ps --format "
            "'{{.Names}}|{{.Image}}'"
        )
        request, broad, error = CLICK_GATE._inspection_request_from_bash(command)
        self.assertEqual(error, "")
        self.assertFalse(broad)
        self.assertEqual(
            request,
            {
                "version": 1,
                "commands": [
                    [
                        "ssh",
                        "example-host",
                        "docker",
                        "ps",
                        "--format",
                        "{{.Names}}|{{.Image}}",
                    ]
                ],
            },
        )
        payload = self.pre_tool("Bash", command, "turn-2")
        rewritten = payload["hookSpecificOutput"]["updatedInput"]["command"]
        self.assertIn("run-observation", rewritten)

        piped = self.pre_tool(
            "Bash",
            "ssh example-host docker ps --format {{.Names}}|{{.Image}}",
            "turn-2",
        )
        self.assertEqual(
            piped["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_structured_ssh_execution_preserves_remote_argv_literals(self) -> None:
        remote_argv = [
            "docker",
            "ps",
            "--format",
            "{{.Names}}|{{.Image}}",
            "--filter",
            "label=owner's service",
        ]
        argv = ["ssh", "example-host", *remote_argv]
        prepared = CLICK_GATE._execution_argv(argv)
        self.assertEqual(prepared[:2], ["ssh", "example-host"])
        self.assertEqual(shlex.split(prepared[2], posix=True), remote_argv)

        with mock.patch.object(CLICK_GATE.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertEqual(CLICK_GATE._execute_argv_commands([argv]), 0)
        self.assertEqual(run.call_args.args[0], prepared)
        self.assertFalse(run.call_args.kwargs["check"])

    def test_structured_ssh_execution_keeps_mutations_explicit(self) -> None:
        remote_argv = ["python3", "tool.py", "--value", "literal|value"]
        prepared = CLICK_GATE._execution_argv(
            ["ssh", "example-host", *remote_argv]
        )
        self.assertEqual(shlex.split(prepared[2], posix=True), remote_argv)
        self.assertFalse(
            CLICK_GATE._is_read_only_tokens(
                ["ssh", "example-host", *remote_argv]
            )
        )

        unsupported = ["ssh", "-p", "2222", "example-host", "hostname"]
        self.assertEqual(CLICK_GATE._execution_argv(unsupported), unsupported)

    def test_structured_ssh_read_is_valid_targeted_verification(self) -> None:
        self.approve_contract()
        payload = self.verify_checks(
            [
                {
                    "argv": ["ssh", "example-host", "hostname"],
                    "class": "targeted",
                }
            ]
        )
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "allow")

    def test_structured_inspection_emulates_get_content_cross_platform(self) -> None:
        (self.workspace / "native.txt").write_text(
            "portable inspection\n", encoding="utf-8"
        )
        payload = self.inspect_gate(
            [["Get-Content", "-Raw", "native.txt"]]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "portable inspection\n")

        for option in ("-Path", "-LiteralPath"):
            with self.subTest(option=option):
                option_payload = self.inspect_gate(
                    [["Get-Content", "-Raw", option, "native.txt"]]
                )
                option_result = self.run_rewritten(option_payload)
                self.assertEqual(option_result.returncode, 0, option_result.stderr)
                self.assertEqual(option_result.stdout, "portable inspection\n")

    def test_get_content_rejects_options_the_native_runner_does_not_implement(self) -> None:
        for option, value in (
            ("-Tail", "10"),
            ("-TotalCount", "10"),
            ("-Encoding", "utf8"),
            ("-ErrorAction", "Stop"),
        ):
            with self.subTest(option=option):
                denied = self.inspect_gate(
                    [["Get-Content", option, value, "native.txt"]]
                )
                self.assertEqual(
                    denied["hookSpecificOutput"]["permissionDecision"], "deny"
                )

    def test_structured_capabilities_reject_environment_assignment_prefixes(self) -> None:
        for label, argv in (
            ("inspection", ["LC_ALL=C", "sort", "README.md"]),
            ("mutation", ["CI=1", "npm", "run", "build"]),
            ("verification", ["CI=1", "npm", "test"]),
        ):
            with self.subTest(label=label):
                normalized, error = CLICK_GATE._validate_argv(argv, label.title())
                self.assertIsNone(normalized)
                self.assertIn("NAME=value", error)

    def test_direct_read_sequence_is_rewritten_as_shell_free_inspection(self) -> None:
        self.approve_contract()
        (self.workspace / "first.txt").write_text("first\n", encoding="utf-8")
        (self.workspace / "second.txt").write_text("second\n", encoding="utf-8")
        if os.name == "nt":
            command = "Get-Content -Raw first.txt && Get-Content -Raw second.txt"
        else:
            command = "sed -n '1,5p' first.txt && sed -n '1,5p' second.txt"
        payload = self.pre_tool("Bash", command, "turn-2")
        rewritten = payload["hookSpecificOutput"]["updatedInput"]["command"]
        self.assertIn("run-observation", rewritten)
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("first", result.stdout)
        self.assertIn("second", result.stdout)

    def test_structured_requests_require_protocol_version_one(self) -> None:
        request = {"version": 2, "commands": [["git", "status", "--short"]]}
        command = f"click-gate inspect {shlex.quote(json.dumps(request))}"
        denied = self.pre_tool("Bash", command)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("version", denied["hookSpecificOutput"]["permissionDecisionReason"])

    def test_structured_mutation_requires_approval_and_rejects_shell_wrapper(self) -> None:
        denied = self.mutate_gate([sys.executable, "-c", "print('no')"])
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.approve_contract()
        shell = self.mutate_gate(["bash", "-c", "touch hidden.txt"])
        self.assertEqual(shell["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_abandoned_structured_mutation_expires_instead_of_blocking_forever(self) -> None:
        self.approve_contract()
        pending = self.mutate_gate([sys.executable, "-c", "print('first')"])
        self.assertEqual(
            pending["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["mutation"]["started_at"] = 0
        state_path.write_text(json.dumps(state), encoding="utf-8")

        recovered = self.mutate_gate(
            [sys.executable, "-c", "print('second')"], "turn-2"
        )
        self.assertEqual(
            recovered["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        result = self.run_rewritten(recovered)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("second", result.stdout)

    def test_active_direct_bash_requires_a_structured_capability(self) -> None:
        self.approve_contract()
        denied = self.pre_tool("Bash", "python3 update_schema.py", "turn-2")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "click-gate mutate",
            denied["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_parallel_observation_results_do_not_leave_running_state(self) -> None:
        self.approve_contract()
        for name in ("a.txt", "b.txt"):
            (self.workspace / name).write_text(name, encoding="utf-8")
        payloads = [
            self.pre_tool("Bash", self.read_file_command(name), "turn-2")
            for name in ("a.txt", "b.txt")
        ]
        environment = os.environ.copy()
        environment["PLUGIN_DATA"] = str(self.plugin_data)
        environment["CLICK_CONFIG_HOME"] = str(self.plugin_data)
        processes = [
            subprocess.Popen(
                payload["hookSpecificOutput"]["updatedInput"]["command"],
                shell=True,
                cwd=self.workspace,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for payload in payloads
        ]
        for process in processes:
            _, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
        states = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ]
        self.assertEqual(len(states), 1)
        entries = states[0]["observations"]["entries"]
        self.assertEqual(len(entries), 2)
        self.assertEqual({entry["status"] for entry in entries.values()}, {"success"})

    def test_manual_default_persists_and_keeps_uninvoked_mutations_fail_open(self) -> None:
        setting = self.set_default("manual")
        self.assertEqual(
            setting["hookSpecificOutput"]["updatedInput"]["command"],
            "echo Click default mode set to Manual",
        )
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch")
        )
        self.assertIsNone(
            self.pre_tool("Bash", "python3 update_schema.py", turn_id="turn-2")
        )

    def test_manual_staged_contract_blocks_next_turn_mutation(self) -> None:
        self.set_default("manual", "turn-0")
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")

        payload = self.pre_tool(
            "apply_patch", "*** Begin Patch\n*** End Patch", turn_id="turn-2"
        )
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "active execution contract",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_manual_incomplete_approved_contract_blocks_later_turn_mutation(self) -> None:
        self.set_default("manual", "turn-0")
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        payload = self.pre_tool(
            "Bash", "python3 update_schema.py", turn_id="turn-3"
        )
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "active execution contract",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_incomplete_approved_contract_blocks_later_turn_root_inventory(self) -> None:
        self.set_default("manual", "turn-0")
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        payload = self.pre_tool("Bash", "rg --files", turn_id="turn-3")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "repository-wide inventory rescan",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_incomplete_approved_contract_tracks_later_turn_direct_reads(self) -> None:
        (self.workspace / "README.md").write_text("hello\n", encoding="utf-8")
        self.approve_contract()
        command = self.read_file_command("README.md")

        first = self.pre_tool("Bash", command, turn_id="turn-3")
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        repeated = self.pre_tool("Bash", command, turn_id="turn-3")
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "identical successful read",
            repeated["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_incomplete_approved_contract_tracks_later_turn_structured_reads(self) -> None:
        (self.workspace / "README.md").write_text("hello\n", encoding="utf-8")
        self.approve_contract()
        commands = [["Get-Content", "-Raw", "README.md"]]

        first = self.inspect_gate(commands, turn_id="turn-3")
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        repeated = self.inspect_gate(commands, turn_id="turn-3")
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_always_on_default_persists_and_gates_later_mutations(self) -> None:
        setting = self.set_default("on")
        self.assertEqual(
            setting["hookSpecificOutput"]["updatedInput"]["command"],
            "echo Click default mode set to Always ON",
        )
        payload = self.pre_tool(
            "apply_patch", "*** Begin Patch\n*** End Patch", turn_id="turn-2"
        )
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "active execution contract",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_default_preference_stays_outside_the_target_repository(self) -> None:
        self.set_default("on")
        preference = self.plugin_data / "preferences.json"
        self.assertTrue(preference.is_file())
        self.assertFalse((self.workspace / "preferences.json").exists())
        stored = json.loads(preference.read_text(encoding="utf-8"))
        self.assertEqual(stored["default_mode"], "on")
        self.assertEqual(set(stored), {"default_mode", "updated_at"})

    def test_prompt_context_reflects_persistent_default(self) -> None:
        unset = self.prompt_submit()["hookSpecificOutput"]["additionalContext"]
        self.assertIn("mode is unset", unset)
        self.assertIn("Always ON (recommended)", unset)

        self.set_default("on")
        always_on = self.prompt_submit()["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Always ON is enabled", always_on)
        self.assertIn("read-only code review", always_on)

        self.set_default("manual")
        manual = self.prompt_submit()["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Manual mode is enabled", manual)
        self.assertIn("explicitly selects", manual)

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
        self.set_default("manual", turn_id="turn-2")
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
            "Bash",
            f"click-gate stage {shlex.quote(json.dumps(missing))}",
            "turn-missing",
        )
        self.assertIn(
            "verification", payload["hookSpecificOutput"]["permissionDecisionReason"]
        )

        for index, scale in enumerate(("quick", "focused", "full"), start=1):
            with self.subTest(scale=scale):
                contract = self.contract()
                contract["verification"]["scale"] = scale
                turn_id = f"turn-scale-{index}"
                self.arm_gate(turn_id)
                payload = self.stage_gate(contract, turn_id)
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "allow"
                )

        invalid = self.contract()
        invalid["verification"]["scale"] = "every-step"
        payload = self.pre_tool(
            "Bash",
            f"click-gate stage {shlex.quote(json.dumps(invalid))}",
            "turn-invalid-scale",
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
        self.arm_gate("turn-gated")
        payload = self.stage_gate(gated, "turn-gated")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "allow")

        invalid_gate = self.contract()
        invalid_gate["verification"]["intermediate_gate"] = ""
        payload = self.pre_tool(
            "Bash",
            f"click-gate stage {shlex.quote(json.dumps(invalid_gate))}",
            "turn-invalid-gate",
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

        command = self.verification_argv()
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

        for command in (
            "pytest tests",
            "python3 -m pytest tests",
            "vitest run",
            "cargo nextest run",
            "cargo test --all",
            "go test ./...",
            "go test ./internal/...",
        ):
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

    def test_hook_raises_underdeclared_verification_to_its_minimum_class(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")

        broad_as_targeted = self.verify_checks(
            [
                {
                    "argv": ["python3", "-m", "unittest", "discover", "-s", "tests"],
                    "class": "targeted",
                }
            ]
        )
        output = broad_as_targeted["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("costs 3", output["permissionDecisionReason"])
        self.assertIn("minimum-class inference", output["permissionDecisionReason"])

        for argv in (
            ["pytest", "-k", "not definitely_missing", "tests"],
            ["pytest", "tests/test_01.py", "tests/test_02.py"],
            [
                "pytest",
                "tests/integration/test_cancel.py::test_duplicate_cancel",
            ],
        ):
            with self.subTest(argv=argv):
                denied = self.verify_checks(
                    [{"argv": argv, "class": "targeted"}]
                )
                reason = denied["hookSpecificOutput"]["permissionDecisionReason"]
                self.assertEqual(
                    denied["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn("costs 3", reason)

    def test_deep_verification_cannot_be_underdeclared_as_broad(self) -> None:
        self.approve_contract()
        payload = self.verify_checks(
            [
                {
                    "argv": ["npx", "playwright", "test"],
                    "class": "broad",
                }
            ]
        )
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("costs 5", output["permissionDecisionReason"])

    def test_verification_classifier_uses_scope_before_kind_markers(self) -> None:
        cases = {
            ("pytest", "-k", "not definitely_missing", "tests"): "broad",
            ("pytest", "-m", "not slow", "tests"): "broad",
            ("pytest", "tests/test_01.py", "tests/test_02.py"): "broad",
            (
                "pytest",
                "tests/integration/test_cancel.py::test_duplicate_cancel",
            ): "broad",
            (
                "pytest",
                "tests/test_security_utils.py::test_parse_header",
            ): "broad",
            ("pytest", "tests/integration"): "deep",
            ("go", "test", "./pkg1", "./pkg2"): "broad",
            ("go", "test", "-run", ".*", "./pkg1"): "broad",
            ("ctest", "-R", ".*"): "broad",
            ("pre-commit", "run", "--files", "a.py", "b.py"): "broad",
            ("pre-commit", "run", "--files", "a.py"): "targeted",
        }
        for argv, expected in cases.items():
            with self.subTest(argv=argv):
                self.assertEqual(
                    CLICK_GATE._minimum_verification_class(list(argv)), expected
                )

    def test_verification_classifier_supports_common_build_and_check_forms(self) -> None:
        cases = {
            ("py", "-3", "-m", "unittest", "pkg.Test.test_one"): "targeted",
            ("uv", "run", "pytest", "tests/test_one.py"): "targeted",
            ("npm", "run", "lint"): "broad",
            ("npm", "run", "build"): "broad",
            ("ruff", "check", "."): "broad",
            ("ruff", "check", "src/one.py"): "targeted",
            ("mypy", "src"): "broad",
            ("mypy", "src/one.py"): "targeted",
            ("tsc", "--noEmit"): "broad",
            ("cargo", "check"): "broad",
            ("cargo", "clippy"): "broad",
            ("go", "vet", "./..."): "broad",
        }
        for argv, expected in cases.items():
            with self.subTest(argv=argv):
                self.assertEqual(
                    CLICK_GATE._minimum_verification_class(list(argv)), expected
                )

    def test_inline_and_direct_python_programs_are_not_verification(self) -> None:
        self.approve_contract()
        for argv in (
            [sys.executable, "-c", "raise SystemExit(0)"],
            [sys.executable, "verify_project.py"],
        ):
            with self.subTest(argv=argv):
                payload = self.verify_checks(
                    [{"argv": argv, "class": "targeted"}]
                )
                output = payload["hookSpecificOutput"]
                self.assertEqual(output["permissionDecision"], "deny")
                self.assertIn("neither read-only nor a recognized check", output["permissionDecisionReason"])

    def test_unknown_verification_wrapper_defaults_to_deep(self) -> None:
        self.approve_contract()
        payload = self.verify_checks(
            [{"argv": ["project-test"], "class": "targeted"}]
        )
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("costs 5", output["permissionDecisionReason"])

    def test_verification_batch_rejects_legacy_shell_strings(self) -> None:
        self.approve_contract()
        payload = self.legacy_verify_gate(
            ["pytest tests/unit && pytest tests/integration"]
        )
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "legacy shell-string",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_successful_final_batch_is_not_repeated_until_code_changes(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")
        command = self.verification_argv()

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

    def test_verification_that_changes_repository_content_cannot_pass(self) -> None:
        (self.workspace / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.workspace / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.workspace / "mutating_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class MutatingTest(unittest.TestCase):\n"
            "    def test_mutates_source(self):\n"
            "        Path('app.py').write_text('VALUE = 2\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "app.py", "mutating_test.py")

        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")
        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "mutating_test.MutatingTest.test_mutates_source",
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("changed protected repository content", result.stderr)

        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        verification = state["verification"]
        self.assertEqual(verification["status"], "failed")
        self.assertTrue(verification["workspace_changed"])
        self.assertEqual(verification["mutation_revision"], 1)
        self.assertNotEqual(
            verification["verified_revision"], verification["mutation_revision"]
        )

        retry = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "mutating_test.MutatingTest.test_mutates_source",
                    ],
                    "class": "targeted",
                }
            ]
        )
        self.assertEqual(retry["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("code mutation", retry["hookSpecificOutput"]["permissionDecisionReason"])

    def test_verification_protects_preexisting_untracked_content(self) -> None:
        (self.workspace / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.workspace / "local-settings.txt").write_text("safe\n", encoding="utf-8")
        (self.workspace / "untracked_mutating_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class UntrackedMutatingTest(unittest.TestCase):\n"
            "    def test_mutates_existing_file(self):\n"
            "        Path('local-settings.txt').write_text('changed\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "untracked_mutating_test.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")

        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        (
                            "untracked_mutating_test.UntrackedMutatingTest."
                            "test_mutates_existing_file"
                        ),
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("changed protected repository content", result.stderr)

    def test_verification_detects_content_committed_during_the_batch(self) -> None:
        (self.workspace / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.workspace / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.workspace / "committing_test.py").write_text(
            "import subprocess\n"
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class CommittingTest(unittest.TestCase):\n"
            "    def test_commits_source_change(self):\n"
            "        Path('app.py').write_text('VALUE = 2\\n', encoding='utf-8')\n"
            "        subprocess.run(['git', 'add', 'app.py'], check=True)\n"
            "        subprocess.run([\n"
            "            'git', '-c', 'user.name=Click Tests', '-c',\n"
            "            'user.email=click-tests@example.invalid', 'commit', '--quiet',\n"
            "            '-m', 'verification mutation'\n"
            "        ], check=True)\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "app.py", "committing_test.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")

        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "committing_test.CommittingTest.test_commits_source_change",
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("changed protected repository content", result.stderr)
        clean_diff = subprocess.run(
            ["git", "diff", "--quiet"], cwd=self.workspace, check=False
        )
        self.assertEqual(clean_diff.returncode, 0)

    def test_new_untracked_verification_artifact_is_not_a_false_mutation(self) -> None:
        (self.workspace / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.workspace / "artifact_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class ArtifactTest(unittest.TestCase):\n"
            "    def test_writes_disposable_report(self):\n"
            "        Path('new-report.tmp').write_text('result\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "artifact_test.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")

        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "artifact_test.ArtifactTest.test_writes_disposable_report",
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("new non-ignored untracked path", result.stderr)
        self.assertTrue((self.workspace / "new-report.tmp").exists())
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["verification"]["status"], "passed")
        self.assertFalse(state["verification"]["workspace_changed"])

    def test_new_source_path_created_during_verification_fails_stale(self) -> None:
        self.assertTrue(CLICK_GATE._new_untracked_requires_stale("src/new_feature.py"))
        self.assertTrue(CLICK_GATE._new_untracked_requires_stale("config/policy.json"))
        self.assertTrue(CLICK_GATE._new_untracked_requires_stale("migration/001.sql"))
        self.assertTrue(
            CLICK_GATE._new_untracked_requires_stale("packages/api/lib/new_rule.py")
        )
        self.assertFalse(CLICK_GATE._new_untracked_requires_stale("new-report.tmp"))
        self.assertFalse(
            CLICK_GATE._new_untracked_requires_stale("reports/app/output.txt")
        )
        (self.workspace / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.workspace / "source_creating_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class SourceCreatingTest(unittest.TestCase):\n"
            "    def test_creates_source(self):\n"
            "        Path('src').mkdir(exist_ok=True)\n"
            "        Path('src/new_feature.py').write_text('VALUE = 1\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "source_creating_test.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")

        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "source_creating_test.SourceCreatingTest.test_creates_source",
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("new non-ignored untracked path", result.stderr)
        self.assertIn("implementation mutation", result.stderr)

    def test_review_mode_needs_no_contract_and_blocks_repeated_successful_reads(self) -> None:
        self.set_default("on")
        review = self.start_review()
        self.assertEqual(
            review["hookSpecificOutput"]["updatedInput"]["command"],
            "echo Click read-only review guard armed",
        )
        (self.workspace / "review.py").write_text("value = 1\n", encoding="utf-8")
        command = self.read_file_command("review.py")
        first = self.pre_tool("Bash", command)
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertEqual(self.run_rewritten(first).returncode, 0)

        repeated = self.pre_tool("Bash", command)
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "identical successful read",
            repeated["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_review_mode_allows_one_root_inventory_then_requires_narrowing(self) -> None:
        self.set_default("on")
        self.start_review()
        (self.workspace / "review.py").write_text("value = 1\n", encoding="utf-8")
        initialized = subprocess.run(
            ["git", "init", "--quiet"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        first = self.pre_tool("Bash", "git ls-files")
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertEqual(self.run_rewritten(first).returncode, 0)

        second = self.pre_tool("Bash", "find . -maxdepth 2 -type f")
        self.assertEqual(second["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "one successful repository-wide inventory",
            second["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_review_mode_is_read_only_and_blocks_plan_churn(self) -> None:
        self.set_default("on")
        self.start_review()
        mutation = self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch")
        self.assertEqual(
            mutation["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn("read-only", mutation["hookSpecificOutput"]["permissionDecisionReason"])

        plan = self.pre_tool("update_plan", "")
        self.assertEqual(plan["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("during read-only review", plan["hookSpecificOutput"]["permissionDecisionReason"])

    def test_simple_read_only_inspection_is_not_tracked_outside_review(self) -> None:
        self.set_default("on")
        (self.workspace / "readme.txt").write_text("hello\n", encoding="utf-8")
        command = self.read_file_command("readme.txt")
        self.assertIsNone(self.pre_tool("Bash", command))
        self.assertIsNone(self.pre_tool("Bash", command))

    def test_always_on_bypass_is_limited_to_the_current_turn(self) -> None:
        self.set_default("on")
        self.bypass_gate()
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch")
        )
        blocked = self.pre_tool(
            "apply_patch", "*** Begin Patch\n*** End Patch", turn_id="turn-2"
        )
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_always_on_can_stage_and_pass_without_explicit_arm(self) -> None:
        self.set_default("on")
        staged = self.stage_gate(turn_id="turn-1")
        self.assertEqual(staged["hookSpecificOutput"]["permissionDecision"], "allow")
        passed = self.pass_gate(turn_id="turn-2")
        self.assertEqual(passed["hookSpecificOutput"]["permissionDecision"], "allow")

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

    def test_identical_cat_read_is_observed_and_blocked(self) -> None:
        (self.workspace / "README.md").write_text("hello\n", encoding="utf-8")
        self.approve_contract()

        first = self.pre_tool("Bash", "cat README.md", "turn-2")
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        completed = self.run_rewritten(first)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "hello")

        repeated = self.pre_tool("Bash", "cat README.md", "turn-2")
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

        verification = self.verify_gate([self.verification_argv()])
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
                    "parallel plan",
                    payload["hookSpecificOutput"]["permissionDecisionReason"],
                )

    def test_armed_contract_workflow_blocks_plan_tool_calls(self) -> None:
        self.arm_gate("turn-1")
        for tool_name in ("update_plan", "functions.update_plan"):
            with self.subTest(tool_name=tool_name):
                payload = self.pre_tool(tool_name, "", "turn-1")
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    "parallel plan",
                    payload["hookSpecificOutput"]["permissionDecisionReason"],
                )

    def test_staged_session_contract_blocks_plan_in_a_later_turn(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        payload = self.pre_tool("update_plan", "", "turn-2")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "parallel plan", payload["hookSpecificOutput"]["permissionDecisionReason"]
        )

    def test_approved_session_contract_blocks_plan_in_a_later_turn(self) -> None:
        self.approve_contract()
        payload = self.pre_tool("update_plan", "", "turn-3")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "parallel plan", payload["hookSpecificOutput"]["permissionDecisionReason"]
        )

    def test_completed_contract_allows_plan_in_a_fresh_uninvoked_turn(self) -> None:
        self.approve_contract()
        verification = self.verify_gate([self.verification_argv()])
        result = self.run_rewritten(verification)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(self.pre_tool("update_plan", "", "turn-3"))

    def test_bypass_allows_plan_in_the_current_turn(self) -> None:
        self.arm_gate("turn-1")
        self.bypass_gate("turn-1")
        self.assertIsNone(self.pre_tool("update_plan", "", "turn-1"))

    def test_running_batch_blocks_parallel_mutation_and_verification(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")
        self.verify_gate([self.verification_argv()])

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
        command = self.verification_argv(exit_code=1)

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
        targeted = self.pre_tool("Bash", "pytest tests/test_inventory.py", "turn-2")
        self.assertEqual(
            targeted["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_uninvoked_verification_remains_fail_open(self) -> None:
        self.set_default("manual")
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

    def test_contract_can_be_replaced_only_after_a_new_user_turn(self) -> None:
        original = self.contract()
        self.arm_gate("turn-1")
        self.stage_gate(original, "turn-1")
        revised = self.contract()
        revised["build"]["approach"] = [
            *revised["build"]["approach"],
            "update approved API documentation",
        ]
        same_turn = self.stage_gate(revised, "turn-1")
        self.assertEqual(
            same_turn["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "already staged", same_turn["hookSpecificOutput"]["permissionDecisionReason"]
        )

        self.arm_gate("turn-2")
        replacement = self.stage_gate(revised, "turn-2")
        self.assertEqual(
            replacement["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        same_turn_pass = self.pass_gate(revised, "turn-2")
        self.assertEqual(
            same_turn_pass["hookSpecificOutput"]["permissionDecision"], "deny"
        )

        self.arm_gate("turn-3")
        payload = self.pass_gate(revised, "turn-3")
        self.assertEqual(
            payload["hookSpecificOutput"]["updatedInput"]["command"],
            "echo Click mutation gate passed",
        )

    def test_identical_staged_contract_cannot_be_restaged_in_a_later_turn(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        self.arm_gate("turn-2")

        repeated = self.stage_gate(turn_id="turn-2")
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "identical Click execution contract is already staged",
            repeated["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_always_on_cannot_stage_and_pass_in_the_same_user_turn(self) -> None:
        self.set_default("on", "turn-1")
        staged = self.stage_gate(turn_id="turn-1")
        self.assertEqual(staged["hookSpecificOutput"]["permissionDecision"], "allow")

        same_turn = self.pass_gate(turn_id="turn-1")
        self.assertEqual(
            same_turn["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "separate user response",
            same_turn["hookSpecificOutput"]["permissionDecisionReason"],
        )

        later_turn = self.pass_gate(turn_id="turn-2")
        self.assertEqual(
            later_turn["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    def test_stage_and_pass_require_a_user_prompt_for_their_exact_turn(self) -> None:
        self.set_default("on", "turn-1")
        stage_command = f"click-gate stage {shlex.quote(json.dumps(self.contract()))}"
        missing_stage_prompt = self.pre_tool(
            "Bash", stage_command, "turn-2", submit_prompt=False
        )
        self.assertEqual(
            missing_stage_prompt["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "UserPromptSubmit",
            missing_stage_prompt["hookSpecificOutput"]["permissionDecisionReason"],
        )

        self.stage_gate(turn_id="turn-2")
        pass_command = f"click-gate pass {shlex.quote(json.dumps(self.contract()))}"
        missing_pass_prompt = self.pre_tool(
            "Bash", pass_command, "turn-3", submit_prompt=False
        )
        self.assertEqual(
            missing_pass_prompt["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "UserPromptSubmit",
            missing_pass_prompt["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_contract_records_staging_and_approval_turns(self) -> None:
        self.approve_contract()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["staged_turn_id"], "turn-1")
        self.assertEqual(state["approved_turn_id"], "turn-2")

    def test_completed_contract_cannot_be_passed_again(self) -> None:
        self.approve_contract()
        verification = self.verify_gate([self.verification_argv()])
        result = self.run_rewritten(verification)
        self.assertEqual(result.returncode, 0, result.stderr)

        self.arm_gate("turn-3")
        replay = self.pass_gate(turn_id="turn-3")
        self.assertEqual(replay["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "already completed",
            replay["hookSpecificOutput"]["permissionDecisionReason"],
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

    def test_failed_contract_cannot_be_replaced(self) -> None:
        self.approve_contract()
        failed = self.verify_gate([self.verification_argv(1)])
        result = self.run_rewritten(failed)
        self.assertEqual(result.returncode, 1)

        replacement = self.contract()
        replacement["outcome"] = "send a purchasing summary"
        self.arm_gate("turn-3")
        payload = self.stage_gate(replacement, "turn-3")
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "final verification",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_stale_completed_contract_cannot_be_replaced(self) -> None:
        self.approve_contract()
        passed = self.verify_gate([self.verification_argv()])
        result = self.run_rewritten(passed)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )

        replacement = self.contract()
        replacement["outcome"] = "send a purchasing summary"
        self.arm_gate("turn-3")
        payload = self.stage_gate(replacement, "turn-3")
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_completed_contract_allows_fresh_next_contract_state(self) -> None:
        self.approve_contract()
        passed = self.verify_gate([self.verification_argv()])
        result = self.run_rewritten(passed)
        self.assertEqual(result.returncode, 0, result.stderr)

        replacement = self.contract()
        replacement["outcome"] = "send a purchasing summary"
        replacement["verification"]["scale"] = "quick"
        self.arm_gate("turn-3")
        payload = self.stage_gate(replacement, "turn-3")
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "staged")
        self.assertEqual(state["verification"]["status"], "ready")
        self.assertEqual(state["verification"]["scale"], "quick")
        self.assertEqual(state["verification"]["mutation_revision"], 0)
        self.assertEqual(state["observations"], {"entries": {}})
        self.assertEqual(state["mutation"]["status"], "idle")

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
        mutation = self.mutate_gate(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; Path('generated.txt').write_text('ok')",
            ],
            "turn-2",
        )
        self.assertEqual(self.run_rewritten(mutation).returncode, 0)
        self.assertEqual(
            (self.workspace / "generated.txt").read_text(encoding="utf-8"), "ok"
        )

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

    def test_structured_mutation_state_does_not_store_command_plaintext(self) -> None:
        self.approve_contract()
        private_body = "mutation-private-marker"
        payload = self.mutate_gate(
            [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    f"Path('generated.txt').write_text('{private_body}')"
                ),
            ],
            "turn-2",
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        state_text = "\n".join(
            path.read_text()
            for path in (self.plugin_data / "gate-state").glob("*.json")
        )
        self.assertIn("request_digest", state_text)
        self.assertNotIn(private_body, state_text)
        self.assertNotIn("generated.txt", state_text)

    def test_gate_pass_does_not_leak_into_a_new_turn(self) -> None:
        self.set_mode("strict")
        self.stage_gate(turn_id="turn-1")
        self.pass_gate(turn_id="turn-2")
        payload = self.pre_tool(
            "apply_patch",
            "*** Begin Patch\n*** End Patch",
            turn_id="turn-3",
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
