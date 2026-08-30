from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
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
sys.path.insert(0, str(SCRIPT.parent.resolve()))
try:
    CLICK_GATE_SPEC.loader.exec_module(CLICK_GATE)
finally:
    sys.path.pop(0)

CLICK_PROCESS = CLICK_GATE.click_process


def mark_git_boundary(root: Path) -> None:
    marker = root / ".git"
    marker.mkdir(parents=True)
    (marker / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (marker / "objects").mkdir()


def split_runner_command(command: str) -> list[str]:
    if os.name != "nt":
        return shlex.split(command, posix=True)
    import ctypes

    argument_count = ctypes.c_int()
    shell32 = ctypes.windll.shell32
    shell32.CommandLineToArgvW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_int),
    ]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    argv = shell32.CommandLineToArgvW(
        command, ctypes.byref(argument_count)
    )
    if not argv:
        raise OSError("CommandLineToArgvW failed")
    try:
        parsed = [argv[index] for index in range(argument_count.value)]
    finally:
        kernel32 = ctypes.windll.kernel32
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        kernel32.LocalFree(ctypes.cast(argv, ctypes.c_void_p))
    if len(parsed) == 4 and parsed[2] == "--encoded-runner":
        decoded, error = CLICK_GATE._decode_runner_transport(parsed[3])
        if error or decoded is None:
            raise ValueError(error or "invalid runner transport")
        return [*parsed[:2], *decoded]
    return parsed


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

    def tool_hook(
        self,
        mode: str,
        tool_name: str,
        tool_input: dict[str, object],
        *,
        turn_id: str = "turn-2",
        tool_use_id: str = "browser-tool-1",
        tool_response: dict[str, object] | None = None,
    ) -> dict | None:
        event = {
            **self.base_event,
            "turn_id": turn_id,
            "hook_event_name": "PreToolUse" if mode == "pre-tool" else "PostToolUse",
            "tool_name": tool_name,
            "tool_use_id": tool_use_id,
            "tool_input": tool_input,
        }
        if tool_response is not None:
            event["tool_response"] = tool_response
        result, payload = self.run_hook(mode, event)
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
                "evidence": [
                    {
                        "id": "E1",
                        "kind": "argv",
                        "description": "focused concurrent threshold tests",
                    }
                ],
                "done_when": [
                    {
                        "condition": "one alert is sent per threshold crossing",
                        "primary_evidence": "E1",
                    }
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

    def active_contract_id(self) -> str:
        state_paths = list(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        if not state_paths:
            return "ctr_" + ("0" * 32)
        state = json.loads(state_paths[0].read_text(encoding="utf-8"))
        contract_id = CLICK_GATE._contract_id_from_state(state)
        self.assertRegex(contract_id, r"^ctr_[0-9a-f]{32}$")
        return contract_id

    def pass_gate(
        self, contract_id: str | None = None, turn_id: str = "turn-2"
    ) -> dict:
        if contract_id is not None and not isinstance(contract_id, str):
            raise TypeError("pass_gate accepts only a contract_id string")
        contract_id = contract_id or self.active_contract_id()
        command = f"click-gate pass {contract_id}"
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
        self.prompt_submit("@Click bypass", turn_id)
        payload = self.pre_tool(
            "Bash", "click-gate bypass", turn_id, submit_prompt=False
        )
        self.assertIsNotNone(payload)
        return payload

    def cancel_gate(self, turn_id: str = "turn-1") -> dict:
        self.prompt_submit("@Click cancel", turn_id)
        payload = self.pre_tool(
            "Bash", "click-gate cancel", turn_id, submit_prompt=False
        )
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
        self,
        commands: list[str | list[str]],
        turn_id: str = "turn-2",
        evidence_ids: list[str] | None = None,
    ) -> dict:
        checks = []
        for index, value in enumerate(commands):
            if isinstance(value, list):
                argv = value
                rendered = " ".join(value)
            else:
                argv = shlex.split(value, posix=True)
                rendered = value
            checks.append(
                {
                    "evidence_id": evidence_ids[index] if evidence_ids else "E1",
                    "argv": argv,
                    "class": self.verification_class(rendered),
                }
            )
        batch = {"version": 2, "checks": checks}
        command = f"click-gate verify {shlex.quote(json.dumps(batch))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def verify_checks(
        self,
        checks: list[dict[str, object]],
        turn_id: str = "turn-2",
        *,
        bind_default: bool = True,
    ) -> dict:
        normalized = [
            ({"evidence_id": "E1", **check} if bind_default else dict(check))
            for check in checks
        ]
        batch = {"version": 2, "checks": normalized}
        command = f"click-gate verify {shlex.quote(json.dumps(batch))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def complete_evidence(
        self, evidence_id: str, turn_id: str = "turn-2"
    ) -> dict:
        request = {"version": 1, "evidence_id": evidence_id}
        command = f"click-gate evidence {shlex.quote(json.dumps(request))}"
        payload = self.pre_tool("Bash", command, turn_id)
        self.assertIsNotNone(payload)
        return payload

    def legacy_verify_gate(self, commands: list[str], turn_id: str = "turn-2") -> dict:
        batch = {"version": 2, "commands": commands}
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

    def assert_verification_new_path_behavior(
        self,
        relative: str,
        *,
        ignored: bool = False,
        suspicious: bool = False,
    ) -> None:
        ignore_lines = ["__pycache__/"]
        if ignored:
            ignore_lines.append(relative)
        (self.workspace / ".gitignore").write_text(
            "\n".join(ignore_lines) + "\n", encoding="utf-8"
        )
        escaped = repr(relative)
        (self.workspace / "new_path_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class NewPathTest(unittest.TestCase):\n"
            "    def test_writes_path(self):\n"
            f"        target = Path({escaped})\n"
            "        target.parent.mkdir(parents=True, exist_ok=True)\n"
            "        target.write_text('generated\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "new_path_test.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "new_path_test.NewPathTest.test_writes_path",
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        if ignored:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("new non-ignored untracked path", result.stderr)
            return
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("new non-ignored untracked path", result.stderr)
        self.assertIn("batch is stale", result.stderr)
        if suspicious:
            self.assertIn("classification is informational", result.stderr)
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["verification"]["status"], "failed")
        self.assertTrue(state["verification"]["workspace_changed"])
        self.assertEqual(state["verification"]["mutation_revision"], 1)

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
            "^(Bash|apply_patch|Edit|Write|update_plan|functions\\.update_plan|mcp__node_repl__js)$",
        )
        pre_tool_handler = hooks["PreToolUse"][0]["hooks"][0]
        self.assertTrue(pre_tool_handler["command"].endswith('click_gate.py\" pre-tool'))
        self.assertEqual(prompt_handler["timeout"], 7)
        self.assertEqual(pre_tool_handler["timeout"], 7)
        self.assertEqual(
            hooks["PostToolUse"][0]["matcher"], "^mcp__node_repl__js$"
        )
        self.assertTrue(
            hooks["PostToolUse"][0]["hooks"][0]["command"].endswith(
                'click_gate.py" post-tool'
            )
        )
        self.assertTrue(
            hooks["SessionEnd"][0]["hooks"][0]["command"].endswith(
                'click_gate.py" session-end'
            )
        )

    def test_uninvoked_hook_starts_without_state(self) -> None:
        self.assertFalse((self.plugin_data / "gate-state").exists())

    def test_read_only_bash_is_rewritten_before_gate(self) -> None:
        for command in (
            "rg --files",
            "Get-Content README.md",
            "sed -n '1,240p' README.md",
        ):
            with self.subTest(command=command):
                payload = self.pre_tool("Bash", command)
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "allow"
                )
                self.assertIn(
                    "run-inspection-once",
                    split_runner_command(
                        payload["hookSpecificOutput"]["updatedInput"]["command"]
                    ),
                )

        initialized = subprocess.run(
            ["git", "init", "--quiet"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        git_read = self.pre_tool("Bash", "git status --short")
        self.assertEqual(
            git_read["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "run-inspection-once",
            split_runner_command(
                git_read["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )
        self.assertEqual(self.run_rewritten(git_read).returncode, 0)

        mixed_read = self.pre_tool(
            "Bash", "sed -n '1,20p' README.md && git status --short"
        )
        self.assertEqual(
            mixed_read["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "run-inspection-once",
            split_runner_command(
                mixed_read["hookSpecificOutput"]["updatedInput"]["command"]
            ),
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

    def test_read_only_capability_rejects_path_qualified_executables(self) -> None:
        for executable in (
            "./cat",
            r".\cat",
            r"C:cat.exe",
            r"C:\tools\cat.exe",
            "C:/tools/cat.exe",
            r"\\server\share\cat.exe",
        ):
            with self.subTest(executable=executable):
                self.assertTrue(
                    CLICK_GATE._is_path_qualified_executable(executable)
                )
        for argv in (
            ["./cat", "README.md"],
            ["../cat", "README.md"],
            ["/tmp/cat", "README.md"],
            ["/usr/bin/cat", "README.md"],
            [r".\cat", "README.md"],
            [r"C:cat.exe", "README.md"],
            [r"C:\tools\cat.exe", "README.md"],
            ["C:/tools/cat.exe", "README.md"],
            [r"\\server\share\cat.exe", "README.md"],
            ["./git", "status", "--short"],
        ):
            with self.subTest(argv=argv):
                self.assertFalse(CLICK_GATE._is_read_only_tokens(argv))

    def test_windows_direct_command_tokenization_preserves_paths(self) -> None:
        cases = {
            r"Get-Content -LiteralPath C:\repo\README.md": [
                "Get-Content",
                "-LiteralPath",
                r"C:\repo\README.md",
            ],
            r'Get-Content -LiteralPath "C:\Program Files\README.md"': [
                "Get-Content",
                "-LiteralPath",
                r"C:\Program Files\README.md",
            ],
            r'Get-Content -LiteralPath "\\server\share\README.md"': [
                "Get-Content",
                "-LiteralPath",
                r"\\server\share\README.md",
            ],
            r"Get-Content README.md && rg needle src": [
                "Get-Content",
                "README.md",
                "&&",
                "rg",
                "needle",
                "src",
            ],
            r"Get-Content README.md | rg needle": [
                "Get-Content",
                "README.md",
                "|",
                "rg",
                "needle",
            ],
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                tokens, error = CLICK_GATE._direct_command_tokens(
                    command, windows=True
                )
                self.assertEqual(error, "")
                self.assertEqual(tokens, expected)

        request, broad, error = CLICK_GATE._inspection_request_from_bash(
            r'Get-Content -LiteralPath "C:\Program Files\README.md"',
            windows=True,
        )
        self.assertEqual(error, "")
        self.assertFalse(broad)
        self.assertEqual(
            request["commands"][0],
            ["Get-Content", "-LiteralPath", r"C:\Program Files\README.md"],
        )
        self.assertEqual(
            CLICK_GATE._windows_shell_quote(r"C:\plugin&data\gate-state"),
            r'"C:\plugin&data\gate-state"',
        )

    def test_windows_runner_transport_hides_shell_expansion_tokens(self) -> None:
        arguments = [
            r"C:\Program Files\Python\python.exe",
            r"C:\Users\safe user\.codex\click_gate.py",
            "--state-root",
            r"C:\work\%PATH%!CLICK!\gate-state",
            "run-mutation",
            r"C:\work\%PATH%!CLICK!\gate-state\session-contract-1.json",
            "digest",
            "token",
            "encoded-request",
        ]
        with mock.patch.object(CLICK_GATE.os, "name", "nt"):
            command = CLICK_GATE._runner_shell_command(arguments)
        self.assertIn('"--encoded-runner"', command)
        self.assertNotIn("%PATH%", command)
        self.assertNotIn("!CLICK!", command)
        encoded = command.rsplit('"', 2)[1]
        decoded, error = CLICK_GATE._decode_runner_transport(encoded)
        self.assertEqual(error, "")
        self.assertEqual(decoded, arguments[2:])

    def test_windows_runner_refuses_expandable_launcher_paths(self) -> None:
        with mock.patch.object(CLICK_GATE.os, "name", "nt"):
            for launcher in (
                r"C:\%PATH%\python.exe",
                r"C:\!CLICK!\python.exe",
                r"C:\$profile\python.exe",
                r"C:\`profile\python.exe",
            ):
                with self.subTest(launcher=launcher):
                    self.assertEqual(
                        CLICK_GATE._runner_shell_command(
                            [launcher, r"C:\click_gate.py", "run-inspection-once", "x"]
                        ),
                        "exit 2",
                    )

    def test_runner_transport_rejects_malformed_or_oversized_payloads(self) -> None:
        for encoded in ("not-base64%", CLICK_GATE._encode_runner_transport([])):
            with self.subTest(encoded=encoded):
                decoded, error = CLICK_GATE._decode_runner_transport(encoded)
                self.assertIsNone(decoded)
                self.assertTrue(error)

        bomb = CLICK_GATE.base64.urlsafe_b64encode(
            CLICK_GATE.zlib.compress(b'"' + b"x" * 30_000 + b'"')
        ).decode()
        decoded, error = CLICK_GATE._decode_runner_transport(bomb)
        self.assertIsNone(decoded)
        self.assertIn("bounded payload", error)

    def test_inspection_never_executes_a_path_qualified_read_only_name(self) -> None:
        with mock.patch.object(CLICK_GATE.subprocess, "run") as run:
            run.return_value.returncode = 0
            exit_code = CLICK_GATE._execute_inspection_commands(
                [["./cat", "README.md"]], workspace=self.workspace
            )
        self.assertEqual(exit_code, 2)
        run.assert_not_called()

    def test_inspection_rejects_a_workspace_path_shadow(self) -> None:
        mark_git_boundary(self.workspace)
        fake = self.workspace / ("cat.exe" if os.name == "nt" else "cat")
        fake.write_text("not a real reader\n", encoding="utf-8")
        with (
            mock.patch("shutil.which", return_value=str(fake)),
            mock.patch.object(CLICK_GATE.subprocess, "run") as run,
        ):
            run.return_value.returncode = 0
            exit_code = CLICK_GATE._execute_inspection_commands(
                [["cat", "README.md"]], workspace=self.workspace
            )
        self.assertEqual(exit_code, 2)
        run.assert_not_called()

    def test_inspection_rewrites_a_trusted_bare_executable(self) -> None:
        mark_git_boundary(self.workspace)
        trusted_root = Path(self.temporary.name) / "trusted-bin"
        trusted_root.mkdir()
        trusted = trusted_root / ("cat.exe" if os.name == "nt" else "cat")
        trusted.write_text("trusted fixture\n", encoding="utf-8")
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {
                    "LD_PRELOAD": "/tmp/inject.so",
                    "DYLD_INSERT_LIBRARIES": "/tmp/inject.dylib",
                    "GCONV_PATH": "/tmp/gconv",
                    "LOCPATH": "/tmp/locale",
                },
            ),
            mock.patch("shutil.which", return_value=str(trusted)) as which,
            mock.patch.object(CLICK_GATE.subprocess, "run") as run,
        ):
            run.return_value.returncode = 0
            exit_code = CLICK_GATE._execute_inspection_commands(
                [["cat", "README.md"]], workspace=self.workspace
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(run.call_args.args[0][0], str(trusted.resolve()))
        self.assertEqual(which.call_count, 2)
        sanitized_path = which.call_args_list[1].kwargs["path"]
        self.assertNotIn(str(self.workspace), sanitized_path)
        self.assertEqual(run.call_args.kwargs["env"]["PATH"], sanitized_path)
        for key in (
            "LD_PRELOAD",
            "DYLD_INSERT_LIBRARIES",
            "GCONV_PATH",
            "LOCPATH",
        ):
            self.assertNotIn(key, run.call_args.kwargs["env"])

    def test_inspection_rejects_a_symlink_into_the_workspace(self) -> None:
        mark_git_boundary(self.workspace)
        target = self.workspace / ("cat.exe" if os.name == "nt" else "cat")
        target.write_text("workspace target\n", encoding="utf-8")
        link_root = Path(self.temporary.name) / "linked-bin"
        link_root.mkdir()
        link = link_root / target.name
        try:
            link.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        with (
            mock.patch("shutil.which", return_value=str(link)),
            mock.patch.object(CLICK_GATE.subprocess, "run") as run,
        ):
            run.return_value.returncode = 0
            exit_code = CLICK_GATE._execute_inspection_commands(
                [["cat", "README.md"]], workspace=self.workspace
            )
        self.assertEqual(exit_code, 2)
        run.assert_not_called()

    def test_inspection_rejects_a_workspace_symlink_to_a_trusted_binary(self) -> None:
        mark_git_boundary(self.workspace)
        trusted_root = Path(self.temporary.name) / "trusted-target"
        trusted_root.mkdir()
        target = trusted_root / ("cat.exe" if os.name == "nt" else "cat")
        target.write_text("trusted target\n", encoding="utf-8")
        link = self.workspace / target.name
        try:
            link.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        with (
            mock.patch("shutil.which", return_value=str(link)),
            mock.patch.object(CLICK_GATE.subprocess, "run") as run,
        ):
            run.return_value.returncode = 0
            exit_code = CLICK_GATE._execute_inspection_commands(
                [["cat", "README.md"]], workspace=self.workspace
            )
        self.assertEqual(exit_code, 2)
        run.assert_not_called()

    def test_sanitized_path_drops_relative_and_workspace_entries(self) -> None:
        mark_git_boundary(self.workspace)
        outside = Path(self.temporary.name) / "outside-bin"
        outside.mkdir()
        workspace_bin = self.workspace / "bin"
        workspace_bin.mkdir()
        workspace_link = self.workspace / "linked-bin"
        try:
            workspace_link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        source = os.pathsep.join(
            ["", ".", "relative-bin", str(workspace_bin), str(workspace_link), str(outside)]
        )
        sanitized = CLICK_GATE._sanitized_executable_path(
            source, workspace=self.workspace
        ).split(os.pathsep)
        self.assertEqual(sanitized, [str(outside.resolve())])

    def test_read_only_resolution_excludes_the_containing_repository(self) -> None:
        repository = self.workspace / "repository"
        repository.mkdir()
        mark_git_boundary(repository)
        nested = repository / "packages" / "app"
        nested.mkdir(parents=True)
        sibling_bin = repository / "tools"
        sibling_bin.mkdir()
        fake = sibling_bin / ("cat.exe" if os.name == "nt" else "cat")
        fake.write_text("repository-owned reader\n", encoding="utf-8")

        with mock.patch("shutil.which", return_value=str(fake)):
            executable, error = CLICK_GATE._resolve_read_only_executable(
                "cat", workspace=nested
            )

        self.assertIsNone(executable)
        self.assertIn("workspace", error)

    def test_workspace_boundary_ignores_an_invalid_git_named_ancestor(self) -> None:
        ancestor = Path(self.temporary.name) / "invalid-ancestor"
        (ancestor / ".git").mkdir(parents=True)
        nested = ancestor / "nested" / "workspace"
        nested.mkdir(parents=True)
        self.assertEqual(CLICK_GATE._workspace_boundary(nested), nested.resolve())
        self.assertFalse(CLICK_GATE._git_metadata_present(nested))

    def test_sanitized_path_fails_closed_on_a_symlink_loop(self) -> None:
        mark_git_boundary(self.workspace)
        first = Path(self.temporary.name) / "loop-a"
        second = Path(self.temporary.name) / "loop-b"
        try:
            first.symlink_to(second)
            second.symlink_to(first)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")

        sanitized = CLICK_GATE._sanitized_executable_path(
            str(first), workspace=self.workspace
        )
        self.assertEqual(sanitized, "")

    def test_workspace_containment_uses_filesystem_identity_for_aliases(self) -> None:
        alias = Path(self.temporary.name) / "workspace-alias"
        try:
            alias.symlink_to(self.workspace, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        self.assertTrue(CLICK_GATE._path_is_within(alias, self.workspace))

    def test_read_only_child_environments_strip_loader_injection(self) -> None:
        mark_git_boundary(self.workspace)
        source = {
            "PATH": os.pathsep.join([str(self.workspace), "/usr/bin"]),
            "HOME": str(Path(self.temporary.name) / "home"),
            "LD_PRELOAD": "/tmp/inject.so",
            "DYLD_INSERT_LIBRARIES": "/tmp/inject.dylib",
            "GCONV_PATH": "/tmp/gconv",
            "LOCPATH": "/tmp/locale",
            "GIT_EXTERNAL_DIFF": "/tmp/helper",
        }
        with mock.patch.dict(CLICK_GATE.os.environ, source, clear=True):
            read_environment = CLICK_GATE._sanitized_read_only_environment(
                workspace=self.workspace
            )
        git_environment = CLICK_GATE._sanitized_git_environment(
            source, workspace=self.workspace
        )

        for environment in (read_environment, git_environment):
            self.assertEqual(environment["HOME"], source["HOME"])
            for key in (
                "LD_PRELOAD",
                "DYLD_INSERT_LIBRARIES",
                "GCONV_PATH",
                "LOCPATH",
            ):
                self.assertNotIn(key, environment)
            self.assertNotIn(str(self.workspace), environment["PATH"])
        self.assertNotIn("GIT_EXTERNAL_DIFF", git_environment)

    def test_git_and_ssh_inspection_execute_verified_absolute_binaries(self) -> None:
        mark_git_boundary(self.workspace)
        trusted_root = Path(self.temporary.name) / "trusted-tools"
        trusted_root.mkdir()
        names = {
            "git": trusted_root / ("git.exe" if os.name == "nt" else "git"),
            "ssh": trusted_root / ("ssh.exe" if os.name == "nt" else "ssh"),
        }
        for path in names.values():
            path.write_text("trusted fixture\n", encoding="utf-8")

        def resolved(name: str, path: str | None = None) -> str | None:
            return str(names[name.lower().removesuffix(".exe")])

        with (
            mock.patch("shutil.which", side_effect=resolved),
            mock.patch.object(CLICK_GATE.subprocess, "run") as run,
        ):
            run.return_value.returncode = 0
            self.assertEqual(
                CLICK_GATE._execute_inspection_commands(
                    [["git", "status", "--short"]], workspace=self.workspace
                ),
                0,
            )
            self.assertEqual(
                CLICK_GATE._execute_inspection_commands(
                    [["ssh", "example-host", "git", "status", "--short"]],
                    workspace=self.workspace,
                ),
                0,
            )
        self.assertEqual(run.call_args_list[0].args[0][0], str(names["git"].resolve()))
        self.assertEqual(run.call_args_list[1].args[0][0], str(names["ssh"].resolve()))

    def test_structured_ssh_inspection_reuses_bounded_git_policy(self) -> None:
        allowed = (
            ["ssh", "example-host", "git", "status", "--short"],
            ["ssh.exe", "example-host", "git", "status", "--short"],
            ["ssh", "user@example-host", "git", "rev-parse", "HEAD"],
            ["ssh", "example-host", "git", "merge-base", "HEAD", "origin/main"],
            ["ssh", "example-host", "git", "remote", "get-url", "origin"],
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
            ["ssh", "-o", "ProxyCommand=helper", "example-host", "git", "status"],
            ["/tmp/ssh", "example-host", "git", "status"],
            ["ssh", "example-host", "git status"],
            ["ssh", "example-host", "hostname"],
            ["ssh", "example-host", "docker", "ps"],
            ["ssh", "example-host", "systemctl", "status", "service"],
            ["ssh", "example-host", "nvidia-smi", "-L"],
            ["ssh", "example-host", "sudo", "-n", "true"],
            ["ssh", "example-host", "bash", "-c", "git status"],
            ["ssh", "example-host", "ssh", "other-host", "git", "status"],
            ["ssh", "example-host", "git", "fetch"],
            ["ssh", "example-host", "git", "log", "-1"],
            ["ssh", "example-host", "git", "rev-parse", "origin/main"],
            ["ssh", "example-host", "git", "remote", "-v"],
            ["ssh", "example-host", "git", "remote", "set-url", "origin", "x"],
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

    def test_direct_structured_ssh_read_becomes_an_observation(self) -> None:
        self.approve_contract()
        command = "ssh example-host git status --short"
        request, broad, error = CLICK_GATE._inspection_request_from_bash(command)
        self.assertEqual(error, "")
        self.assertFalse(broad)
        self.assertEqual(
            request,
            {
                "version": 1,
                "commands": [
                    ["ssh", "example-host", "git", "status", "--short"]
                ],
            },
        )
        payload = self.pre_tool("Bash", command, "turn-2")
        rewritten = payload["hookSpecificOutput"]["updatedInput"]["command"]
        self.assertIn("run-observation", split_runner_command(rewritten))

        piped = self.pre_tool(
            "Bash",
            "ssh example-host git status --short | head -1",
            "turn-2",
        )
        self.assertEqual(
            piped["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_structured_ssh_execution_preserves_remote_argv_literals(self) -> None:
        remote_argv = [
            "git",
            "merge-base",
            "HEAD",
            "literal|value;still-one-argument",
        ]
        argv = ["ssh", "example-host", *remote_argv]
        prepared = CLICK_GATE._execution_argv(argv)
        safe_git_argv, error = CLICK_GATE._build_read_only_git_argv(remote_argv)
        self.assertEqual(error, "")
        self.assertEqual(prepared[:4], ["ssh", "-n", "-F", "none"])
        self.assertIn("BatchMode=yes", prepared)
        self.assertIn("StrictHostKeyChecking=yes", prepared)
        self.assertIn("ConnectTimeout=10", prepared)
        self.assertIn("ConnectionAttempts=1", prepared)
        self.assertIn("ServerAliveInterval=5", prepared)
        self.assertIn("ServerAliveCountMax=1", prepared)
        self.assertIn("NumberOfPasswordPrompts=0", prepared)
        self.assertIn("UpdateHostKeys=no", prepared)
        self.assertIn("PermitLocalCommand=no", prepared)
        self.assertIn("ClearAllForwardings=yes", prepared)
        self.assertEqual(prepared[-2], "example-host")
        self.assertEqual(shlex.split(prepared[-1], posix=True), safe_git_argv)

        with mock.patch.object(CLICK_GATE.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertEqual(CLICK_GATE._execute_argv_commands([argv]), 0)
        self.assertEqual(run.call_args.args[0], prepared)
        self.assertFalse(run.call_args.kwargs["check"])

    def test_structured_ssh_execution_keeps_mutations_explicit(self) -> None:
        remote_argv = ["python3", "tool.py", "--value", "literal|value"]
        argv = ["ssh", "example-host", *remote_argv]
        self.assertEqual(CLICK_GATE._execution_argv(argv), argv)
        self.assertFalse(
            CLICK_GATE._is_read_only_tokens(argv)
        )

        unsupported = ["ssh", "-p", "2222", "example-host", "git", "status"]
        self.assertEqual(CLICK_GATE._execution_argv(unsupported), unsupported)

    def test_structured_ssh_read_is_valid_targeted_verification(self) -> None:
        self.approve_contract()
        payload = self.verify_checks(
            [
                {
                    "argv": ["ssh", "example-host", "git", "status", "--short"],
                    "class": "targeted",
                }
            ]
        )
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "allow")

    def test_git_remote_output_redacts_credentials_and_query_tokens(self) -> None:
        output = CLICK_GATE._redact_git_remote_output(
            b"https://user:token@example.com/repo.git?access_token=secret\n"
            b"ssh://user:password@example.com/repo.git#secret\n"
            b"token@example.com:owner/repo.git\n"
        )
        self.assertEqual(
            output,
            b"https://example.com/repo.git\n"
            b"ssh://example.com/repo.git\n"
            b"example.com:owner/repo.git\n",
        )
        self.assertNotIn(b"token", output)
        self.assertNotIn(b"password", output)
        self.assertNotIn(b"secret", output)

    def test_structured_ssh_remote_url_is_redacted_before_output(self) -> None:
        argv = ["ssh", "example-host", "git", "remote", "get-url", "origin"]
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            with mock.patch.object(CLICK_GATE.subprocess, "run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = b"https://user:secret@example.com/repo.git\n"
                run.return_value.stderr = b""
                self.assertEqual(
                    CLICK_GATE._execute_argv_commands([argv], stdout_file, stderr_file),
                    0,
                )
            stdout_file.seek(0)
            self.assertEqual(stdout_file.read(), b"https://example.com/repo.git\n")

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

    def test_structured_capabilities_reject_process_control_executables(self) -> None:
        for argv in (
            ["kill", "1234"],
            ["/usr/bin/PKILL", "-f", "codex"],
            ["killall", "node"],
            ["pskill.exe", "codex.exe"],
            [r"C:\Windows\System32\taskkill.exe", "/IM", "codex.exe"],
            ["tskill.exe", "1234"],
            ["Stop-Process", "-Id", "1234"],
        ):
            with self.subTest(argv=argv):
                normalized, error = CLICK_GATE._validate_argv(argv, "Mutation")
                self.assertIsNone(normalized)
                self.assertIn("process-control executable", error)

        normalized, error = CLICK_GATE._validate_argv(
            ["kill-switch-check", "--help"], "Mutation"
        )
        self.assertEqual(normalized, ["kill-switch-check", "--help"])
        self.assertEqual(error, "")

    def test_subprocess_isolation_kwargs_are_platform_specific(self) -> None:
        with mock.patch.object(CLICK_PROCESS.os, "name", "posix"):
            self.assertEqual(
                CLICK_GATE._isolated_subprocess_kwargs(),
                {"start_new_session": True},
            )
        with (
            mock.patch.object(CLICK_PROCESS.os, "name", "nt"),
            mock.patch.object(
                CLICK_PROCESS.subprocess,
                "CREATE_NEW_PROCESS_GROUP",
                512,
                create=True,
            ),
        ):
            self.assertEqual(
                CLICK_GATE._isolated_subprocess_kwargs(),
                {"creationflags": 512},
            )

    def test_all_click_subprocesses_use_isolated_process_groups(self) -> None:
        isolated = {"start_new_session": True}
        with (
            mock.patch.object(
                CLICK_PROCESS,
                "isolated_subprocess_kwargs",
                return_value=isolated,
            ) as isolation,
            mock.patch.object(CLICK_PROCESS.subprocess, "run") as run,
        ):
            run.return_value.returncode = 0
            run.return_value.stdout = b"captured\n"
            self.assertEqual(
                CLICK_GATE._execute_argv_commands([["echo", "ok"]]), 0
            )
            self.assertEqual(
                CLICK_GATE._execute_read_only_git(
                    ["git", "status", "--short"], None, None
                ),
                0,
            )
            self.assertEqual(
                CLICK_GATE._git_capture(self.workspace, ["status", "--short"]),
                b"captured\n",
            )

        self.assertEqual(isolation.call_count, 3)
        self.assertEqual(len(run.call_args_list), 3)
        for call in run.call_args_list:
            with self.subTest(argv=call.args[0]):
                self.assertTrue(call.kwargs["start_new_session"])

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
        self.assertIn("run-observation", split_runner_command(rewritten))
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

    def test_structured_mutation_rejects_process_control_executable(self) -> None:
        self.approve_contract()
        process_control = self.mutate_gate(["pkill", "-f", "codex"])
        self.assertEqual(
            process_control["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "process-control executable",
            process_control["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_executable_policy_normalizes_windows_aliases(self) -> None:
        cases = {
            "bash.exe": "shell interpreter",
            "SH.EXE.": "shell interpreter",
            "pwsh.exe ": "shell interpreter",
            r"C:\Windows\System32\taskkill.exe.": "process-control executable",
            "pkill.exe": "process-control executable",
        }
        for executable, expected in cases.items():
            with self.subTest(executable=executable):
                argv, error = CLICK_GATE._validate_argv(
                    [executable, "ignored"], "Mutation"
                )
                self.assertIsNone(argv)
                self.assertIn(expected, error)

    @unittest.skipIf(os.name == "nt", "POSIX session IDs are not available on Windows")
    def test_structured_mutation_runs_in_a_new_posix_session(self) -> None:
        self.approve_contract()
        payload = self.mutate_gate(
            [
                sys.executable,
                "-c",
                (
                    "import os; "
                    "print(os.getpid(), os.getsid(0), os.getsid(os.getppid()))"
                ),
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        child_pid, child_session, parent_session = map(int, result.stdout.split())
        self.assertEqual(child_pid, child_session)
        self.assertNotEqual(child_session, parent_session)

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

    def test_claimed_mutation_never_auto_expires_while_result_is_unknown(self) -> None:
        mutation = {
            "status": "running",
            "runner_claimed_at": 1,
            "started_at": int(time.time()) - 10_000,
        }
        with mock.patch.object(CLICK_GATE.time, "time", return_value=20_000):
            self.assertTrue(CLICK_GATE._mutation_is_running(mutation))

    def test_mutation_runner_claims_authorization_before_execution(self) -> None:
        self.approve_contract()
        payload = self.mutate_gate([sys.executable, "-c", "print('claimed')"])
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        tokens = split_runner_command(command)
        self.assertEqual(tokens[2], "--state-root")
        self.assertEqual(tokens[4], "run-mutation")
        arguments = tokens[5:]

        tampered = [arguments[0], arguments[1], "wrong-token", arguments[3]]
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ, {"PLUGIN_DATA": str(self.plugin_data)}
            ),
            mock.patch.object(CLICK_GATE, "_execute_argv_commands") as execute,
        ):
            self.assertEqual(CLICK_GATE._run_mutation(tampered), 2)
        execute.assert_not_called()

    def test_mutation_runner_blocks_replay_before_a_second_execution(self) -> None:
        self.approve_contract()
        payload = self.mutate_gate([sys.executable, "-c", "print('once')"])
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        arguments = split_runner_command(command)[5:]

        with (
            mock.patch.dict(
                CLICK_GATE.os.environ, {"PLUGIN_DATA": str(self.plugin_data)}
            ),
            mock.patch.object(
                CLICK_GATE, "_execute_argv_commands", return_value=0
            ) as execute,
        ):
            self.assertEqual(CLICK_GATE._run_mutation(arguments), 0)
            self.assertEqual(CLICK_GATE._run_mutation(arguments), 2)
        self.assertEqual(execute.call_count, 1)

    def test_rewritten_mutation_uses_bound_root_not_ambient_plugin_data(self) -> None:
        self.plugin_data = Path(self.temporary.name) / "plugin%PATH%!CLICK!&data"
        self.approve_contract()
        payload = self.mutate_gate(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; Path('bound-root.txt').write_text('ok')",
            ]
        )
        environment = os.environ.copy()
        environment["PLUGIN_DATA"] = str(Path(self.temporary.name) / "wrong-root")
        environment["CLICK_CONFIG_HOME"] = environment["PLUGIN_DATA"]
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        result = subprocess.run(
            command,
            shell=True,
            cwd=self.workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.workspace / "bound-root.txt").read_text(encoding="utf-8"),
            "ok",
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["mutation"]["status"], "passed")

    def test_mutation_runner_rejects_invalid_state_before_execution(self) -> None:
        self.approve_contract()
        payload = self.mutate_gate([sys.executable, "-c", "print('blocked')"])
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        arguments = split_runner_command(command)[5:]
        state_path = Path(arguments[0])
        original = json.loads(state_path.read_text(encoding="utf-8"))

        variants: list[tuple[str, dict]] = []
        staged = json.loads(json.dumps(original))
        staged["status"] = "staged"
        variants.append(("top-level status", staged))
        finished = json.loads(json.dumps(original))
        finished["mutation"]["status"] = "passed"
        variants.append(("mutation status", finished))
        digest = json.loads(json.dumps(original))
        digest["mutation"]["request_digest"] = "0" * 64
        variants.append(("stored digest", digest))
        claimed = json.loads(json.dumps(original))
        claimed["mutation"]["runner_claimed_at"] = 1
        variants.append(("replay claim", claimed))
        malformed = json.loads(json.dumps(original))
        malformed["mutation"]["runner_claimed_at"] = True
        variants.append(("malformed claim", malformed))
        expired = json.loads(json.dumps(original))
        expired["mutation"]["started_at"] = int(time.time()) - 10_000
        variants.append(("expired reservation", expired))
        future = json.loads(json.dumps(original))
        future["mutation"]["started_at"] = int(time.time()) + 60
        variants.append(("future reservation", future))

        with mock.patch.dict(
            CLICK_GATE.os.environ, {"PLUGIN_DATA": str(self.plugin_data)}
        ):
            for label, state in variants:
                with self.subTest(label=label):
                    state_path.write_text(json.dumps(state), encoding="utf-8")
                    with mock.patch.object(
                        CLICK_GATE, "_execute_argv_commands"
                    ) as execute:
                        self.assertEqual(CLICK_GATE._run_mutation(arguments), 2)
                    execute.assert_not_called()

    def test_mutation_runner_rejects_unmanaged_state_before_execution(self) -> None:
        self.approve_contract()
        payload = self.mutate_gate([sys.executable, "-c", "print('blocked')"])
        arguments = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )[5:]
        managed = Path(arguments[0])
        unmanaged = Path(self.temporary.name) / "copied-contract.json"
        unmanaged.write_text(managed.read_text(encoding="utf-8"), encoding="utf-8")
        arguments[0] = str(unmanaged)
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ, {"PLUGIN_DATA": str(self.plugin_data)}
            ),
            mock.patch.object(CLICK_GATE, "_execute_argv_commands") as execute,
        ):
            self.assertEqual(CLICK_GATE._run_mutation(arguments), 2)
        execute.assert_not_called()

    def test_mutation_result_requires_a_claim(self) -> None:
        self.approve_contract()
        payload = self.mutate_gate([sys.executable, "-c", "print('claimless')"])
        arguments = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )[5:]
        with mock.patch.dict(
            CLICK_GATE.os.environ, {"PLUGIN_DATA": str(self.plugin_data)}
        ):
            self.assertFalse(
                CLICK_GATE._record_mutation_result(
                    Path(arguments[0]), arguments[1], arguments[2], 0
                )
            )

    def test_active_direct_bash_requires_a_structured_capability(self) -> None:
        self.approve_contract()
        denied = self.pre_tool("Bash", "python3 update_schema.py", "turn-2")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "click-gate mutate",
            denied["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_state_lock_retries_windows_permission_contention(self) -> None:
        with mock.patch.dict(
            CLICK_GATE.os.environ,
            {"PLUGIN_DATA": str(self.plugin_data)},
        ):
            lock_root = self.plugin_data / "gate-state"
            lock_root.mkdir(parents=True)
            lock_path = lock_root / ".state.lock"
            lock_path.write_text("competing-process", encoding="utf-8")
            real_open = CLICK_GATE.os.open
            attempts = 0

            def open_with_windows_contention(
                path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                flags: int,
                mode: int = 0o777,
            ) -> int:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise PermissionError(13, "Permission denied", str(path))
                return real_open(path, flags, mode)

            def release_competing_lock(_: float) -> None:
                lock_path.unlink()

            with (
                mock.patch.object(
                    CLICK_GATE.os,
                    "open",
                    side_effect=open_with_windows_contention,
                ),
                mock.patch.object(
                    CLICK_GATE.time,
                    "sleep",
                    side_effect=release_competing_lock,
                ),
            ):
                with CLICK_GATE._state_lock():
                    self.assertTrue(lock_path.exists())

            self.assertEqual(attempts, 2)
            self.assertFalse(lock_path.exists())

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

    def test_observation_runner_rejects_unmanaged_state_before_execution(self) -> None:
        unmanaged = Path(self.temporary.name) / "session-contract-copied.json"
        unmanaged.write_text("{}", encoding="utf-8")
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
                clear=True,
            ),
            mock.patch.object(CLICK_GATE, "_run_inspection_request") as execute,
        ):
            result = CLICK_GATE._run_observation(
                [str(unmanaged), "digest", "token", "encoded"]
            )
        self.assertEqual(result, 2)
        execute.assert_not_called()

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

    def test_incomplete_approved_contract_resume_reuses_the_same_id(self) -> None:
        self.set_default("manual", "turn-0")
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        contract_id = self.active_contract_id()
        self.arm_gate("turn-2")
        self.pass_gate(contract_id, "turn-2")

        context = self.prompt_submit("계속 진행해줘", "turn-3")["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn(f"incomplete approved contract_id is `{contract_id}`", context)
        self.arm_gate("turn-3")
        resumed = self.pass_gate(contract_id, "turn-3")
        self.assertEqual(
            resumed["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["contract_id"], contract_id)
        self.assertEqual(state["approved_turn_id"], "turn-2")

    def test_incomplete_approved_contract_allows_one_later_turn_root_inventory(self) -> None:
        self.initialize_git("verification_fixture.py")
        self.set_default("manual", "turn-0")
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        first = self.pre_tool("Bash", "git ls-files", turn_id="turn-3")
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        parallel = self.pre_tool(
            "Bash", "find . -maxdepth 2 -type f", turn_id="turn-3"
        )
        self.assertEqual(
            parallel["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "already running",
            parallel["hookSpecificOutput"]["permissionDecisionReason"],
        )
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        repeated = self.pre_tool("Bash", "git ls-files", turn_id="turn-3")
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "already completed one successful repository-wide inventory",
            repeated["hookSpecificOutput"]["permissionDecisionReason"],
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
        inspection = self.pre_tool("Bash", "rg --files")
        self.assertEqual(
            inspection["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "run-inspection-once",
            split_runner_command(
                inspection["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )

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
            "click-gate stage "
            "'{\"outcome\":\"API 동작을 수정합니다.\","
            "\"plain_language\":\"기존 API 동작을 유지합니다.\","
            "\"boundary\":{\"in_scope\":[\"api\"],\"out_of_scope\":[]}}'"
        )
        payload = self.pre_tool("Bash", command)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("must_hold", output["permissionDecisionReason"])

    def test_contract_requires_structured_evidence_references(self) -> None:
        cases: list[tuple[str, dict, str]] = []

        missing_evidence = self.contract()
        del missing_evidence["verification"]["evidence"]
        cases.append(("missing evidence", missing_evidence, "evidence"))

        inline_string = self.contract()
        inline_string["verification"]["done_when"] = [
            "behavior works — primary evidence: one browser session"
        ]
        cases.append(("inline string", inline_string, "inline evidence strings"))

        duplicate_id = self.contract()
        duplicate_id["verification"]["evidence"].append(
            {
                "id": "E1",
                "kind": "manual",
                "description": "manual observation",
            }
        )
        cases.append(("duplicate id", duplicate_id, "must be unique"))

        unknown_reference = self.contract()
        unknown_reference["verification"]["done_when"][0][
            "primary_evidence"
        ] = "E-missing"
        cases.append(("unknown reference", unknown_reference, "unknown evidence id"))

        unsupported_kind = self.contract()
        unsupported_kind["verification"]["evidence"][0]["kind"] = "vector-match"
        cases.append(("unsupported kind", unsupported_kind, "kind must be one of"))

        unused_source = self.contract()
        unused_source["verification"]["evidence"].append(
            {
                "id": "E2",
                "kind": "hosted",
                "description": "hosted deployment status",
            }
        )
        cases.append(("unused source", unused_source, "are unused"))

        for label, contract, expected in cases:
            with self.subTest(label=label):
                value, error = CLICK_GATE._validate_contract(json.dumps(contract))
                self.assertIsNone(value)
                self.assertIn(expected, error)

    def test_one_structured_evidence_source_can_cover_multiple_conditions(self) -> None:
        contract = self.contract()
        contract["verification"]["done_when"].append(
            {
                "condition": "the existing inventory write remains compatible",
                "primary_evidence": "E1",
            }
        )
        value, error = CLICK_GATE._validate_contract(json.dumps(contract))
        self.assertEqual(error, "")
        self.assertEqual(value, contract)

    def test_contract_rejects_more_argv_reservations_than_scale_can_hold(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        contract["verification"]["evidence"].append(
            {"id": "E2", "kind": "argv", "description": "second local check"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "compatibility remains", "primary_evidence": "E2"}
        )
        value, error = CLICK_GATE._validate_contract(json.dumps(contract))
        self.assertIsNone(value)
        self.assertIn("cannot fit 2 argv evidence sources", error)

        full = self.contract()
        full["verification"]["scale"] = "full"
        for index in range(2, 10):
            evidence_id = f"E{index}"
            full["verification"]["evidence"].append(
                {"id": evidence_id, "kind": "argv", "description": f"check {index}"}
            )
            full["verification"]["done_when"].append(
                {"condition": f"condition {index}", "primary_evidence": evidence_id}
            )
        value, error = CLICK_GATE._validate_contract(json.dumps(full))
        self.assertEqual(error, "")
        self.assertEqual(value, full)

        for index in range(10, 12):
            evidence_id = f"E{index}"
            full["verification"]["evidence"].append(
                {"id": evidence_id, "kind": "argv", "description": f"check {index}"}
            )
            full["verification"]["done_when"].append(
                {"condition": f"condition {index}", "primary_evidence": evidence_id}
            )
        value, error = CLICK_GATE._validate_contract(json.dumps(full))
        self.assertIsNone(value)
        self.assertIn("cannot fit 11 argv evidence sources", error)

    def test_verification_check_requires_a_declared_argv_evidence_id(self) -> None:
        self.approve_contract()
        check = {"argv": self.verification_argv(), "class": "targeted"}

        missing = self.verify_checks([check], bind_default=False)
        self.assertEqual(
            missing["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "evidence_id",
            missing["hookSpecificOutput"]["permissionDecisionReason"],
        )

        old_batch = {
            "version": 1,
            "checks": [{"evidence_id": "E1", **check}],
        }
        old_request = self.pre_tool(
            "Bash",
            f"click-gate verify {shlex.quote(json.dumps(old_batch))}",
            "turn-2",
        )
        self.assertEqual(
            old_request["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "version` must be 2",
            old_request["hookSpecificOutput"]["permissionDecisionReason"],
        )

        unknown = self.verify_checks(
            [{"evidence_id": "E9", **check}], bind_default=False
        )
        self.assertEqual(
            unknown["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "unknown evidence id",
            unknown["hookSpecificOutput"]["permissionDecisionReason"],
        )

        browser_contract = self.contract()
        browser_contract["verification"]["evidence"] = [
            {"id": "E-browser", "kind": "browser", "description": "one session"}
        ]
        browser_contract["verification"]["done_when"] = [
            {"condition": "the page works", "primary_evidence": "E-browser"}
        ]
        sources = CLICK_GATE._fresh_evidence_state(browser_contract)["sources"]
        raw = json.dumps(
            {
                "version": 2,
                "checks": [
                    {
                        "evidence_id": "E-browser",
                        "argv": self.verification_argv(),
                        "class": "targeted",
                    }
                ],
            }
        )
        value, _, error = CLICK_GATE._validate_verification_batch(
            raw, "focused", sources
        )
        self.assertIsNone(value)
        self.assertIn("not `argv`", error)

    def test_verification_batches_may_cover_unresolved_sources_incrementally(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E2", "kind": "argv", "description": "compatibility check"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "compatibility remains", "primary_evidence": "E2"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        first = self.verify_gate([self.verification_argv()])
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        sources = state["evidence_state"]["sources"]
        self.assertEqual(
            sources[CLICK_GATE._evidence_key("E1")]["status"], "passed"
        )
        self.assertEqual(
            sources[CLICK_GATE._evidence_key("E2")]["status"], "ready"
        )
        self.assertEqual(state["verification"]["status"], "ready")
        self.assertFalse(CLICK_GATE._contract_is_completed(state))

        reused = self.verify_gate([self.verification_argv()])
        self.assertEqual(
            reused["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "reused 1 current unchanged-tree",
            reused["hookSpecificOutput"]["updatedInput"]["command"],
        )

        non_adjacent = self.verify_gate(
            [
                self.verification_argv(),
                self.verification_argv(),
                self.verification_argv(),
            ],
            evidence_ids=["E1", "E2", "E1"],
        )
        self.assertEqual(
            non_adjacent["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "must be adjacent",
            non_adjacent["hookSpecificOutput"]["permissionDecisionReason"],
        )

        batch = self.verify_gate([self.verification_argv()], evidence_ids=["E2"])
        self.assertEqual(self.run_rewritten(batch).returncode, 0)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        revision = state["verification"]["mutation_revision"]
        sources = state["evidence_state"]["sources"]
        for evidence_id in ("E1", "E2"):
            source = sources[CLICK_GATE._evidence_key(evidence_id)]
            self.assertEqual(source["status"], "passed")
            self.assertEqual(source["verified_revision"], revision)
        self.assertTrue(CLICK_GATE._contract_is_completed(state))

    def test_partial_argv_batch_records_each_evidence_source(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E2", "kind": "argv", "description": "failing regression"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "regression passes", "primary_evidence": "E2"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        batch = self.verify_gate(
            [self.verification_argv(), self.verification_argv(1)],
            evidence_ids=["E1", "E2"],
        )
        self.assertEqual(self.run_rewritten(batch).returncode, 1)
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        sources = state["evidence_state"]["sources"]
        self.assertEqual(
            sources[CLICK_GATE._evidence_key("E1")]["status"], "passed"
        )
        self.assertEqual(
            sources[CLICK_GATE._evidence_key("E2")]["status"], "failed"
        )
        self.assertFalse(CLICK_GATE._contract_is_completed(state))

        retry = self.verify_gate(
            [self.verification_argv(1)], evidence_ids=["E2"]
        )
        self.assertEqual(self.run_rewritten(retry).returncode, 1)
        blocked = self.verify_gate(
            [self.verification_argv(1)], evidence_ids=["E2"]
        )
        self.assertEqual(
            blocked["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "failed twice",
            blocked["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_partial_batch_retries_only_unresolved_source_to_completion(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n.transient-marker\n", encoding="utf-8"
        )
        (self.workspace / "transient_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class TransientTest(unittest.TestCase):\n"
            "    def test_passes_on_retry(self):\n"
            "        marker = Path('.transient-marker')\n"
            "        if not marker.exists():\n"
            "            marker.write_text('retry\\n', encoding='utf-8')\n"
            "            self.fail('transient failure')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "transient_test.py")
        transient_argv = [
            sys.executable,
            "-m",
            "unittest",
            "transient_test.TransientTest.test_passes_on_retry",
        ]
        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E2", "kind": "argv", "description": "transient regression"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "transient regression passes", "primary_evidence": "E2"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        first = self.verify_gate(
            [self.verification_argv(), transient_argv],
            evidence_ids=["E1", "E2"],
        )
        self.assertEqual(self.run_rewritten(first).returncode, 1)
        retry = self.verify_gate([transient_argv], evidence_ids=["E2"])
        self.assertEqual(self.run_rewritten(retry).returncode, 0)

        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        revision = state["verification"]["mutation_revision"]
        for evidence_id in ("E1", "E2"):
            source = state["evidence_state"]["sources"][
                CLICK_GATE._evidence_key(evidence_id)
            ]
            self.assertEqual(source["status"], "passed")
            self.assertEqual(source["verified_revision"], revision)
        self.assertTrue(CLICK_GATE._contract_is_completed(state))

    def test_non_argv_evidence_can_complete_without_a_local_batch(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {"id": "E-hosted", "kind": "hosted", "description": "host status"},
            {"id": "E-manual", "kind": "manual", "description": "manual check"},
            {"id": "E-existing", "kind": "existing", "description": "current proof"},
        ]
        contract["verification"]["done_when"] = [
            {"condition": "host is ready", "primary_evidence": "E-hosted"},
            {"condition": "operator checked it", "primary_evidence": "E-manual"},
            {"condition": "current proof remains valid", "primary_evidence": "E-existing"},
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        for evidence_id in ("E-hosted", "E-manual"):
            completed = self.complete_evidence(evidence_id)
            self.assertEqual(
                completed["hookSpecificOutput"]["permissionDecision"], "allow"
            )
            state_path = next(
                (self.plugin_data / "gate-state").glob("session-contract-*.json")
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertFalse(CLICK_GATE._contract_is_completed(state))

        completed = self.complete_evidence("E-existing")
        self.assertEqual(completed["hookSpecificOutput"]["permissionDecision"], "allow")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(CLICK_GATE._contract_is_completed(state))

    def test_argv_evidence_cannot_be_completed_by_attestation(self) -> None:
        self.approve_contract()
        denied = self.complete_evidence("E1")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("click-gate verify", denied["hookSpecificOutput"]["permissionDecisionReason"])

    def test_mixed_evidence_requires_every_source_and_mutation_stales_all(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E-manual", "kind": "manual", "description": "operator check"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "operator view is correct", "primary_evidence": "E-manual"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        verification = self.verify_gate([self.verification_argv()])
        self.assertEqual(self.run_rewritten(verification).returncode, 0)
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(CLICK_GATE._contract_is_completed(state))

        self.complete_evidence("E-manual")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(CLICK_GATE._contract_is_completed(state))

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(CLICK_GATE._contract_is_completed(state))
        for source in state["evidence_state"]["sources"].values():
            self.assertIn(source["status"], {"stale", "ready"})

    def test_contract_allows_only_one_browser_evidence_source(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {
                "id": "E-browser-1",
                "kind": "browser",
                "description": "first browser session",
            },
            {
                "id": "E-browser-2",
                "kind": "browser",
                "description": "second browser session",
            },
        ]
        contract["verification"]["done_when"] = [
            {"condition": "first view works", "primary_evidence": "E-browser-1"},
            {"condition": "second view works", "primary_evidence": "E-browser-2"},
        ]
        value, error = CLICK_GATE._validate_contract(json.dumps(contract))
        self.assertIsNone(value)
        self.assertIn("at most one Browser evidence source", error)

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
        command = f"click-gate stage {shlex.quote(json.dumps(contract))}"
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
                command = f"click-gate stage {shlex.quote(json.dumps(contract))}"
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
        self.pass_gate(turn_id="turn-2")

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
            "run-verification",
            split_runner_command(
                allowed["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )

    def test_split_argv_batches_share_one_cumulative_budget(self) -> None:
        (self.workspace / "empty_tests").mkdir()
        (self.workspace / "empty_tests" / "test_pass.py").write_text(
            "import unittest\n\n"
            "class PassingTest(unittest.TestCase):\n"
            "    def test_pass(self):\n"
            "        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E2", "kind": "argv", "description": "second broad check"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "second broad check passes", "primary_evidence": "E2"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        broad_argv = [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "empty_tests",
        ]

        first = self.verify_gate([broad_argv], evidence_ids=["E1"])
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        second = self.verify_gate([broad_argv], evidence_ids=["E2"])
        self.assertEqual(
            second["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "reservations would total 6",
            second["hookSpecificOutput"]["permissionDecisionReason"],
        )

        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        sources = state["evidence_state"]["sources"]
        self.assertEqual(
            sources[CLICK_GATE._evidence_key("E1")]["reserved_units"], 3
        )
        self.assertEqual(
            sources[CLICK_GATE._evidence_key("E2")]["reserved_units"], 0
        )

    def test_broad_and_expensive_checks_consume_more_budget(self) -> None:
        quick = self.contract()
        quick["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(quick, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
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
        self.cancel_gate("turn-3")
        self.arm_gate("turn-4")
        self.stage_gate(full, "turn-4")
        self.arm_gate("turn-5")
        self.pass_gate(turn_id="turn-5")
        expensive = self.verify_gate(
            ["npx playwright test", "python3 -m unittest discover -s tests"],
            "turn-5",
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
        self.pass_gate(turn_id="turn-2")

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
            ("node", "--check", "src/one.js"): "targeted",
            ("node", "--test", "tests/one.test.js"): "targeted",
            ("node", "--test"): "broad",
        }
        for argv, expected in cases.items():
            with self.subTest(argv=argv):
                self.assertEqual(
                    CLICK_GATE._minimum_verification_class(list(argv)), expected
                )
        self.assertIsNone(
            CLICK_GATE._minimum_verification_class(
                ["node", "--eval", "process.exit(0)"]
            )
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
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
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
            repeated["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "reused 1 current unchanged-tree",
            repeated["hookSpecificOutput"]["updatedInput"]["command"],
        )

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        stale_retry = self.verify_gate([command])
        self.assertEqual(
            stale_retry["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "run-verification",
            split_runner_command(
                stale_retry["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )

    def test_current_receipt_reruns_when_the_git_tree_changes_out_of_band(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        self.approve_contract()
        command = self.verification_argv()
        first = self.verify_gate([command])
        self.assertEqual(self.run_rewritten(first).returncode, 0)

        with (self.workspace / "verification_fixture.py").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write("\n# changed outside the matched mutation tools\n")

        repeated = self.verify_gate([command])
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "run-verification",
            split_runner_command(
                repeated["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["verification"]["mutation_revision"], 1)

    def test_current_receipt_reruns_when_the_execution_environment_changes(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        self.approve_contract()
        command = self.verification_argv()
        first = self.verify_gate([command])
        self.assertEqual(self.run_rewritten(first).returncode, 0)

        with mock.patch.dict(os.environ, {"CLICK_TEST_ENVIRONMENT": "changed"}):
            repeated = self.verify_gate([command])
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "run-verification",
            split_runner_command(
                repeated["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )

    def test_verification_environment_ignores_shell_bookkeeping(self) -> None:
        stable = {
            "PATH": os.environ.get("PATH", os.defpath),
            "CLICK_TEST_ENVIRONMENT": "stable",
        }
        with mock.patch.object(CLICK_GATE.os, "environ", stable):
            expected = CLICK_GATE._verification_environment(cwd=self.workspace)
        noisy = {
            **stable,
            "_": "launcher",
            "__CF_USER_TEXT_ENCODING": "0x1F5:0x0:0x0",
            "CMDCMDLINE": "cmd.exe /c runner",
            "COMMAND_MODE": "unix2003",
            "LC_CTYPE": "UTF-8",
            "PROMPT": "$P$G",
            "SHLVL": "2",
            "=C:": "C:\\runner",
        }
        with mock.patch.object(CLICK_GATE.os, "environ", noisy):
            actual = CLICK_GATE._verification_environment(cwd=self.workspace)

        self.assertEqual(actual, expected)
        self.assertEqual(actual["CLICK_TEST_ENVIRONMENT"], "stable")

    def test_receipt_fingerprint_resolves_relative_path_from_runner_cwd(self) -> None:
        tools = self.workspace / "tools"
        tools.mkdir()
        executable_name = "receipt-check.exe" if os.name == "nt" else "receipt-check"
        executable = tools / executable_name
        executable.write_bytes(b"receipt-check executable\n")
        executable.chmod(0o755)
        environment = os.environ.copy()
        environment["PATH"] = "tools"

        digest = CLICK_GATE._verification_environment_digest(
            [{"argv": [executable_name], "class": "targeted"}],
            cwd=self.workspace,
            environment=environment,
        )

        self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_rewritten_verification_runner_is_claimed_before_execution(self) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        tokens = split_runner_command(command)
        self.assertEqual(tokens[2], "--state-root")
        self.assertEqual(
            Path(tokens[3]).resolve(),
            (self.plugin_data / "gate-state").resolve(),
        )
        self.assertEqual(tokens[4], "run-verification")

        environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "CLICK_CONFIG_HOME": str(self.plugin_data),
        }
        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(CLICK_GATE, "_git_workspace_snapshot", return_value=None),
            mock.patch.object(CLICK_GATE, "_git_metadata_present", return_value=False),
            mock.patch.object(
                CLICK_GATE, "_execute_argv_commands", return_value=0
            ) as execute,
        ):
            self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 0)
            self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 2)
        self.assertEqual(execute.call_count, 1)

    def test_verification_runner_rejects_tampered_source_reservation(self) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        tokens = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )
        state_path = Path(tokens[5])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        source = state["evidence_state"]["sources"][CLICK_GATE._evidence_key("E1")]
        source["reserved_check_digest"] = "0" * 64
        state_path.write_text(json.dumps(state), encoding="utf-8")

        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(CLICK_GATE, "_execute_argv_commands") as execute,
        ):
            self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 2)
        execute.assert_not_called()

    def test_source_reservation_survives_mutation_and_prevents_check_swapping(self) -> None:
        self.approve_contract()
        first = self.verify_gate([self.verification_argv(1)])
        self.assertEqual(self.run_rewritten(first).returncode, 1)
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )

        changed = self.verify_gate([self.verification_argv()])
        self.assertEqual(
            changed["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "reserved to a different exact check set",
            changed["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_rewritten_verification_uses_bound_root_not_ambient_plugin_data(self) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        environment = os.environ.copy()
        environment.pop("PLUGIN_DATA", None)
        environment.pop("CLICK_CONFIG_HOME", None)
        first = subprocess.run(
            command,
            shell=True,
            cwd=self.workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        replay = subprocess.run(
            command,
            shell=True,
            cwd=self.workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(replay.returncode, 2)
        self.assertIn("no longer authorized", replay.stderr)

    def test_verification_runner_rejects_stale_or_future_reservation_before_execution(self) -> None:
        for label, started_at in (
            (
                "expired",
                int(time.time()) - CLICK_GATE.VERIFY_RUNNING_TTL_SECONDS - 1,
            ),
            ("future", int(time.time()) + 60),
        ):
            with self.subTest(label=label):
                self.plugin_data = Path(self.temporary.name) / f"plugin-{label}"
                self.submitted_turns.clear()
                self.approve_contract()
                payload = self.verify_gate([self.verification_argv()])
                tokens = split_runner_command(
                    payload["hookSpecificOutput"]["updatedInput"]["command"]
                )
                state_path = Path(tokens[5])
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state["verification"]["started_at"] = started_at
                state_path.write_text(json.dumps(state), encoding="utf-8")
                with (
                    mock.patch.dict(
                        CLICK_GATE.os.environ,
                        {"PLUGIN_DATA": str(self.plugin_data)},
                    ),
                    mock.patch.object(
                        CLICK_GATE, "_execute_argv_commands"
                    ) as execute,
                ):
                    self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 2)
                execute.assert_not_called()

    def test_verification_fails_closed_when_git_snapshot_cannot_be_established(self) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        tokens = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(CLICK_GATE, "_git_workspace_snapshot", return_value=None),
            mock.patch.object(CLICK_GATE, "_git_metadata_present", return_value=True),
            mock.patch.object(CLICK_GATE, "_execute_argv_commands") as execute,
        ):
            self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 2)
        execute.assert_not_called()

    def test_claimed_verification_never_auto_expires_while_result_is_unknown(self) -> None:
        self.approve_contract()
        first = self.verify_gate([self.verification_argv()])
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["verification"]["runner_claimed_at"] = 1
        state["verification"]["started_at"] = 1
        state_path.write_text(json.dumps(state), encoding="utf-8")

        repeated = self.verify_gate([self.verification_argv()])
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "already running",
            repeated["hookSpecificOutput"]["permissionDecisionReason"],
        )
        current = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(current["verification"]["status"], "running")
        self.assertEqual(current["verification"]["runner_claimed_at"], 1)

    def test_stateful_runner_prefix_rejects_non_gate_state_root(self) -> None:
        self.approve_contract()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        arguments, error = CLICK_GATE._runner_arguments(
            [
                "--state-root",
                str(self.plugin_data.resolve()),
                "run-verification",
                str(state_path),
            ]
        )
        self.assertEqual(arguments, [])
        self.assertIn("invalid", error)

    def test_stateful_runner_requires_one_canonical_bound_state_root(self) -> None:
        self.approve_contract()
        state_root = (self.plugin_data / "gate-state").resolve()
        state_path = next(state_root.glob("session-contract-*.json")).resolve()

        for action in CLICK_GATE.STATEFUL_RUNNER_ACTIONS:
            with self.subTest(action=action):
                with mock.patch.dict(
                    CLICK_GATE.os.environ,
                    {"PLUGIN_DATA": str(Path(self.temporary.name) / "wrong-root")},
                ):
                    arguments, error = CLICK_GATE._runner_arguments(
                        ["--state-root", str(state_root), action, str(state_path)]
                    )
                    self.assertEqual(error, "")
                    self.assertEqual(arguments[:2], [action, str(state_path)])
                    self.assertEqual(
                        CLICK_GATE.os.environ["PLUGIN_DATA"],
                        str(state_root.parent),
                    )

        bare, error = CLICK_GATE._runner_arguments(
            ["run-mutation", str(state_path)]
        )
        self.assertEqual(bare, [])
        self.assertIn("requires", error)

        relative, error = CLICK_GATE._runner_arguments(
            ["--state-root", "gate-state", "run-mutation", str(state_path)]
        )
        self.assertEqual(relative, [])
        self.assertIn("invalid", error)

        missing_root = Path(self.temporary.name) / "missing" / "gate-state"
        missing, error = CLICK_GATE._runner_arguments(
            [
                "--state-root",
                str(missing_root),
                "run-mutation",
                str(state_path),
            ]
        )
        self.assertEqual(missing, [])
        self.assertIn("could not be resolved", error)

        other_root = Path(self.temporary.name) / "other" / "gate-state"
        other_root.mkdir(parents=True)
        mismatched, error = CLICK_GATE._runner_arguments(
            [
                "--state-root",
                str(other_root.resolve()),
                "run-mutation",
                str(state_path),
            ]
        )
        self.assertEqual(mismatched, [])
        self.assertIn("does not match", error)

        alias = Path(self.temporary.name) / "gate-state-alias"
        try:
            alias.symlink_to(state_root, target_is_directory=True)
        except OSError:
            alias = None
        if alias is not None:
            symlinked, error = CLICK_GATE._runner_arguments(
                ["--state-root", str(alias), "run-mutation", str(state_path)]
            )
            self.assertEqual(symlinked, [])
            self.assertIn("invalid", error)

        state_alias = Path(self.temporary.name) / "session-contract-alias.json"
        try:
            state_alias.symlink_to(state_path)
        except OSError:
            state_alias = None
        if state_alias is not None:
            aliased_state, error = CLICK_GATE._runner_arguments(
                [
                    "--state-root",
                    str(state_root),
                    "run-mutation",
                    str(state_alias),
                ]
            )
            self.assertEqual(aliased_state, [])
            self.assertIn("does not match", error)

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
        self.pass_gate(turn_id="turn-2")
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

    def test_workspace_changing_failure_does_not_mark_unrun_evidence_executed(self) -> None:
        (self.workspace / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.workspace / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.workspace / "mutating_failure_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class MutatingFailureTest(unittest.TestCase):\n"
            "    def test_mutates_then_fails(self):\n"
            "        Path('app.py').write_text('VALUE = 2\\n', encoding='utf-8')\n"
            "        self.fail('expected failure after mutation')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "app.py", "mutating_failure_test.py")

        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E2", "kind": "argv", "description": "unrun compatibility check"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "compatibility remains", "primary_evidence": "E2"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        payload = self.verify_gate(
            [
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "mutating_failure_test.MutatingFailureTest.test_mutates_then_fails",
                ],
                self.verification_argv(),
            ],
            evidence_ids=["E1", "E2"],
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 1, result.stderr)
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        sources = state["evidence_state"]["sources"]
        executed = sources[CLICK_GATE._evidence_key("E1")]
        unrun = sources[CLICK_GATE._evidence_key("E2")]
        self.assertEqual((executed["status"], executed["attempts"]), ("failed", 1))
        self.assertEqual((unrun["status"], unrun["attempts"]), ("ready", 0))
        self.assertEqual(unrun["unchanged_failure_retries"], 0)

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
        self.pass_gate(turn_id="turn-2")

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
        self.pass_gate(turn_id="turn-2")

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

    def test_new_untracked_verification_artifact_fails_stale(self) -> None:
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
        self.pass_gate(turn_id="turn-2")

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
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("new non-ignored untracked path", result.stderr)
        self.assertTrue((self.workspace / "new-report.tmp").exists())
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["verification"]["status"], "failed")
        self.assertTrue(state["verification"]["workspace_changed"])
        self.assertEqual(state["verification"]["mutation_revision"], 1)

    def test_new_source_path_created_during_verification_fails_stale(self) -> None:
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("src/new_feature.py"))
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("config/policy.json"))
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("migration/001.sql"))
        self.assertTrue(
            CLICK_GATE._new_untracked_is_suspicious("packages/api/lib/new_rule.py")
        )
        self.assertFalse(CLICK_GATE._new_untracked_is_suspicious("new-report.tmp"))
        self.assertFalse(
            CLICK_GATE._new_untracked_is_suspicious("reports/app/output.txt")
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
        self.pass_gate(turn_id="turn-2")

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
        self.assertIn("classification is informational", result.stderr)

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
        first = self.pre_tool("Bash", command)
        second = self.pre_tool("Bash", command)
        for payload in (first, second):
            self.assertEqual(
                payload["hookSpecificOutput"]["permissionDecision"], "allow"
            )
            self.assertIn(
                "run-inspection-once",
                split_runner_command(
                    payload["hookSpecificOutput"]["updatedInput"]["command"]
                ),
            )

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

    def test_approved_boundary_allows_one_inventory_then_blocks_rescans(self) -> None:
        (self.workspace / "threshold.txt").write_text(
            "threshold\n", encoding="utf-8"
        )
        self.initialize_git("threshold.txt", "verification_fixture.py")
        self.approve_contract()
        first = self.pre_tool("Bash", "git ls-files", "turn-2")
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        parallel = self.pre_tool(
            "Bash", "find . -maxdepth 2 -type f", "turn-2"
        )
        self.assertEqual(
            parallel["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "already running",
            parallel["hookSpecificOutput"]["permissionDecisionReason"],
        )
        self.assertEqual(self.run_rewritten(first).returncode, 0)

        repeated = self.pre_tool("Bash", "ls -R", "turn-2")
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "already completed one successful repository-wide inventory",
            repeated["hookSpecificOutput"]["permissionDecisionReason"],
        )

        for command in (
            "git ls-files -- src",
            "git ls-tree -r HEAD -- src",
        ):
            with self.subTest(command=command):
                payload = self.pre_tool("Bash", command, "turn-2")
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "allow"
                )
                self.run_rewritten(payload)

        targeted = self.pre_tool(
            "Bash", "Get-Content -Raw threshold.txt", "turn-2"
        )
        self.assertEqual(
            targeted["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertEqual(self.run_rewritten(targeted).returncode, 0)

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        after_mutation = self.pre_tool("Bash", "git ls-files", "turn-2")
        self.assertEqual(
            after_mutation["hookSpecificOutput"]["permissionDecision"], "allow"
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
        self.pass_gate(turn_id="turn-2")
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

    def test_unclaimed_expired_verification_does_not_consume_source_attempt(self) -> None:
        self.approve_contract()
        self.verify_gate([self.verification_argv()])
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["verification"]["started_at"] = (
            int(time.time()) - CLICK_GATE.VERIFY_RUNNING_TTL_SECONDS - 1
        )
        self.assertEqual(state["verification"]["runner_claimed_at"], 0)
        original_source = state["evidence_state"]["sources"][
            CLICK_GATE._evidence_key("E1")
        ]
        reserved_digest = original_source["reserved_check_digest"]
        reserved_units = original_source["reserved_units"]
        state_path.write_text(json.dumps(state), encoding="utf-8")

        retry = self.verify_gate([self.verification_argv()])
        self.assertEqual(retry["hookSpecificOutput"]["permissionDecision"], "allow")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        source = state["evidence_state"]["sources"][CLICK_GATE._evidence_key("E1")]
        self.assertEqual(source["status"], "running")
        self.assertEqual(source["attempts"], 0)
        self.assertEqual(source["unchanged_failure_retries"], 0)
        self.assertEqual(source["reserved_check_digest"], reserved_digest)
        self.assertEqual(source["reserved_units"], reserved_units)

    def test_failed_batch_allows_one_unchanged_retry_then_requires_mutation(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
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

    def test_pass_accepts_only_a_well_formed_contract_id(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        self.arm_gate("turn-2")

        malformed = self.pre_tool("Bash", "click-gate pass contract-123", "turn-2")
        self.assertEqual(
            malformed["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "exactly 32 lowercase hexadecimal",
            malformed["hookSpecificOutput"]["permissionDecisionReason"],
        )

        legacy = self.pre_tool(
            "Bash",
            f"click-gate pass {shlex.quote(json.dumps(self.contract()))}",
            "turn-2",
        )
        self.assertEqual(legacy["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "contract_id", legacy["hookSpecificOutput"]["permissionDecisionReason"]
        )
        self.assertIn(
            "not the Execution Contract JSON",
            legacy["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_prompt_context_exposes_only_the_active_contract_id(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        contract_id = self.active_contract_id()

        context = self.prompt_submit("승인합니다", "turn-2")["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn(f"active staged contract_id is `{contract_id}`", context)
        self.assertIn(f"click-gate pass {contract_id}", context)
        self.assertIn("never resend the contract JSON", context)
        self.assertNotIn("inventory", context)

    def test_prompt_context_migrates_pre_ledger_staged_contract(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        del state["evidence_state"]
        del state["state_schema_version"]
        state_path.write_text(json.dumps(state), encoding="utf-8")

        context = self.prompt_submit("승인합니다", "turn-2")["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn("predates evidence-id completion tracking", context)
        self.assertIn("click-gate cancel", context)
        self.assertNotIn("click-gate pass", context)

    def test_prompt_context_migrates_pre_ledger_approved_contract(self) -> None:
        self.approve_contract()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        del state["evidence_state"]
        del state["state_schema_version"]
        state_path.write_text(json.dumps(state), encoding="utf-8")

        context = self.prompt_submit("계속해줘", "turn-3")["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn("predates evidence-id completion tracking", context)
        self.assertIn("click-gate cancel", context)
        self.assertNotIn("click-gate pass", context)

    def test_pre_id_staged_state_gets_a_digest_derived_compatibility_id(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        del state["contract_id"]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        compatibility_id = f"ctr_{state['contract_digest'][:32]}"

        context = self.prompt_submit("승인합니다", "turn-2")["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn(compatibility_id, context)
        self.arm_gate("turn-2")
        passed = self.pass_gate(compatibility_id, "turn-2")
        self.assertEqual(passed["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_incomplete_pre_ledger_contract_requires_cancel_and_restage(self) -> None:
        self.approve_contract()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        del state["evidence_state"]
        del state["state_schema_version"]
        state_path.write_text(json.dumps(state), encoding="utf-8")

        verification = self.verify_gate([self.verification_argv()])
        self.assertEqual(
            verification["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "predates evidence-id completion tracking",
            verification["hookSpecificOutput"]["permissionDecisionReason"],
        )
        mutation = self.pre_tool(
            "apply_patch", "*** Begin Patch\n*** End Patch", "turn-2"
        )
        self.assertEqual(
            mutation["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_pre_ledger_staged_contract_is_rejected_at_pass(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        contract_id = self.active_contract_id()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        del state["evidence_state"]
        del state["state_schema_version"]
        state_path.write_text(json.dumps(state), encoding="utf-8")

        self.arm_gate("turn-2")
        denied = self.pass_gate(contract_id, "turn-2")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "predates evidence-id completion tracking",
            denied["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_current_staged_contract_missing_ledger_is_rejected_at_pass(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        contract_id = self.active_contract_id()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        del state["evidence_state"]
        state_path.write_text(json.dumps(state), encoding="utf-8")

        self.arm_gate("turn-2")
        denied = self.pass_gate(contract_id, "turn-2")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "unavailable or malformed",
            denied["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_completed_pre_ledger_contract_keeps_rollover_compatibility(self) -> None:
        self.approve_contract()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        del state["evidence_state"]
        del state["state_schema_version"]
        state["verification"]["status"] = "passed"
        state["verification"]["verified_revision"] = state["verification"][
            "mutation_revision"
        ]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        self.assertTrue(CLICK_GATE._contract_is_completed(state))

        replacement = self.contract()
        replacement["outcome"] = "send a purchasing summary"
        self.arm_gate("turn-3")
        staged = self.stage_gate(replacement, "turn-3")
        self.assertEqual(staged["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_current_schema_missing_ledger_fails_closed_even_if_global_passed(self) -> None:
        self.approve_contract()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            state["state_schema_version"], CLICK_GATE.CONTRACT_STATE_SCHEMA_VERSION
        )
        del state["evidence_state"]
        state["verification"]["status"] = "passed"
        state["verification"]["verified_revision"] = state["verification"][
            "mutation_revision"
        ]
        state_path.write_text(json.dumps(state), encoding="utf-8")

        self.assertFalse(CLICK_GATE._contract_is_completed(state))
        replacement = self.contract()
        replacement["outcome"] = "send a purchasing summary"
        self.arm_gate("turn-3")
        staged = self.stage_gate(replacement, "turn-3")
        self.assertEqual(staged["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_unknown_state_schema_fails_closed_with_valid_ledger(self) -> None:
        self.approve_contract()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        source = state["evidence_state"]["sources"][CLICK_GATE._evidence_key("E1")]
        source["status"] = "passed"
        source["verified_revision"] = state["verification"]["mutation_revision"]
        state["state_schema_version"] = 999
        state_path.write_text(json.dumps(state), encoding="utf-8")

        self.assertFalse(CLICK_GATE._contract_is_completed(state))
        replacement = self.contract()
        replacement["outcome"] = "send a purchasing summary"
        self.arm_gate("turn-3")
        staged = self.stage_gate(replacement, "turn-3")
        self.assertEqual(staged["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_malformed_current_evidence_ledger_fails_closed(self) -> None:
        self.approve_contract()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["evidence_state"] = {"version": 1, "sources": {}}
        state_path.write_text(json.dumps(state), encoding="utf-8")
        self.assertFalse(CLICK_GATE._contract_is_completed(state))

        mutation = self.pre_tool(
            "apply_patch", "*** Begin Patch\n*** End Patch", "turn-2"
        )
        self.assertEqual(
            mutation["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "malformed", mutation["hookSpecificOutput"]["permissionDecisionReason"]
        )

    def test_partial_evidence_ledger_entry_loss_fails_closed(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E-manual", "kind": "manual", "description": "operator check"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "operator view is correct", "primary_evidence": "E-manual"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        del state["evidence_state"]["sources"][
            CLICK_GATE._evidence_key("E-manual")
        ]
        remaining = state["evidence_state"]["sources"][CLICK_GATE._evidence_key("E1")]
        remaining["status"] = "passed"
        remaining["verified_revision"] = state["verification"]["mutation_revision"]
        state_path.write_text(json.dumps(state), encoding="utf-8")

        self.assertFalse(CLICK_GATE._contract_is_completed(state))
        verification = self.verify_gate([self.verification_argv()])
        self.assertEqual(
            verification["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "malformed", verification["hookSpecificOutput"]["permissionDecisionReason"]
        )

    def test_malformed_stored_id_does_not_fall_back_to_the_digest(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        compatibility_id = f"ctr_{state['contract_digest'][:32]}"
        state["contract_id"] = "broken"
        state_path.write_text(json.dumps(state), encoding="utf-8")

        context = self.prompt_submit("승인합니다", "turn-2")["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertNotIn(compatibility_id, context)
        self.arm_gate("turn-2")
        denied = self.pass_gate(compatibility_id, "turn-2")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "no recoverable contract_id",
            denied["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_pass_rejects_corrupted_staged_digest(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        contract_id = self.active_contract_id()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["contract_digest"] = "broken"
        state_path.write_text(json.dumps(state), encoding="utf-8")

        context = self.prompt_submit("승인합니다", "turn-2")["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertNotIn(contract_id, context)

        self.arm_gate("turn-2")
        denied = self.pass_gate(contract_id, "turn-2")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "digest is unavailable or invalid",
            denied["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_stage_requires_explicit_arm(self) -> None:
        payload = self.stage_gate(turn_id="turn-1")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("Arm Click", output["permissionDecisionReason"])

    def test_pass_rejects_an_id_different_from_the_staged_contract(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        self.arm_gate("turn-2")
        payload = self.pass_gate("ctr_" + ("f" * 32), "turn-2")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("contract_id differs", output["permissionDecisionReason"])

    def test_contract_id_cannot_cross_session_or_working_directory(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        contract_id = self.active_contract_id()
        original_event = self.base_event

        for identity_change, turn_id in (
            ({"session_id": "session-2"}, "turn-other-session"),
            ({"cwd": str(self.workspace / "other")}, "turn-other-cwd"),
        ):
            with self.subTest(identity_change=identity_change):
                self.base_event = {**original_event, **identity_change}
                self.arm_gate(turn_id)
                denied = self.pass_gate(contract_id, turn_id)
                self.assertEqual(
                    denied["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    "No staged",
                    denied["hookSpecificOutput"]["permissionDecisionReason"],
                )
        self.base_event = original_event

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
        same_turn_pass = self.pass_gate(turn_id="turn-2")
        self.assertEqual(
            same_turn_pass["hookSpecificOutput"]["permissionDecision"], "deny"
        )

        self.arm_gate("turn-3")
        payload = self.pass_gate(turn_id="turn-3")
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
        pass_command = f"click-gate pass {self.active_contract_id()}"
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
        self.pass_gate(turn_id="turn-2")

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
            "every declared source",
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
        completed_id = self.active_contract_id()
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
        self.assertRegex(state["contract_id"], r"^ctr_[0-9a-f]{32}$")
        self.assertNotEqual(state["contract_id"], completed_id)
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

    def test_revised_stage_invalidates_the_previous_contract_id(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        previous_id = self.active_contract_id()
        changed = self.contract()
        changed["verification"]["scale"] = "full"
        self.arm_gate("turn-2")
        replacement = self.stage_gate(changed, "turn-2")
        self.assertEqual(
            replacement["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        current_id = self.active_contract_id()
        self.assertNotEqual(previous_id, current_id)
        self.arm_gate("turn-3")
        payload = self.pass_gate(previous_id, "turn-3")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("contract_id differs", output["permissionDecisionReason"])
        accepted = self.pass_gate(current_id, "turn-3")
        self.assertEqual(
            accepted["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    def test_bypass_preserves_the_staged_contract_for_later_turn(self) -> None:
        self.set_default("manual", "turn-0")
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        bypassed = self.bypass_gate("turn-1")
        self.assertEqual(
            bypassed["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIsNone(
            self.pre_tool(
                "apply_patch",
                "*** Begin Patch\n*** End Patch",
                turn_id="turn-1",
                submit_prompt=False,
            )
        )
        blocked = self.pre_tool(
            "apply_patch", "*** Begin Patch\n*** End Patch", turn_id="turn-2"
        )
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "active execution contract",
            blocked["hookSpecificOutput"]["permissionDecisionReason"],
        )
        self.arm_gate("turn-2")
        payload = self.pass_gate(turn_id="turn-2")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_valid_contract_is_recorded_and_control_command_is_rewritten(self) -> None:
        self.arm_gate("turn-1")
        staged = self.stage_gate(turn_id="turn-1")
        contract_id = self.active_contract_id()
        self.assertEqual(
            staged["hookSpecificOutput"]["updatedInput"]["command"],
            f"echo CLICK_CONTRACT_ID={contract_id}",
        )
        self.assertNotIn("inventory", contract_id)
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
        self.assertRegex(state_text, r'"contract_id":"ctr_[0-9a-f]{32}"')
        self.assertIn('"scale":"focused"', state_text)
        self.assertIn('"unit_limit":4', state_text)
        self.assertNotIn("inventory write path", state_text)
        self.assertNotIn("threshold crossing", state_text)
        self.assertNotIn("existing notification mechanism", state_text)
        self.assertNotIn("재고가 임계값", state_text)
        self.assertNotIn('"E1"', state_text)
        self.assertIn(CLICK_GATE._evidence_key("E1"), state_text)
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


    def test_git_read_only_policy_rejects_pager_config_and_removed_subcommands(self) -> None:
        commands = (
            ["git", "-p", "status"],
            ["git", "--paginate", "status"],
            ["git", "-c", "core.pager=cat", "status"],
            ["git", "--config-env=core.pager=PAGER", "status"],
            ["git", "grep", "-Oless", "needle", "."],
            ["git", "grep", "--open-files-in-pager=less", "needle", "."],
            ["git", "cat-file", "--filters", "HEAD:README.md"],
            ["git", "cat-file", "--textconv", "HEAD:README.md"],
            ["git", "show", "--textconv", "HEAD"],
            ["git", "log", "--format=%G?", "-1"],
            ["git", "log", "--pretty=format:%H", "-1"],
            ["git", "show", "--format=%H", "HEAD"],
            ["git", "show", "--show-signature", "HEAD"],
            ["git", "for-each-ref", "--format=%(objectname)", "refs/heads"],
            ["git", "ls-files", "--format=%(objectname)"],
            ["git", "ls-tree", "--format=%(objectname)", "HEAD"],
            ["git", "status", "--verbose"],
            ["git", "status", "-v"],
            ["git", "status", "-vv"],
            ["git", "remote"],
            ["git", "remote", "-v"],
            ["git", "remote", "set-url", "origin", "https://example.com/repo.git"],
            ["git", "remote", "add", "backup", "https://example.com/repo.git"],
        )
        for argv in commands:
            with self.subTest(argv=argv):
                denied = self.inspect_gate([argv])
                self.assertEqual(
                    denied["hookSpecificOutput"]["permissionDecision"], "deny"
                )

    def test_git_read_only_policy_uses_hardened_executor_shape(self) -> None:
        for argv in (
            ["git", "status", "--short"],
            ["git", "diff", "--check"],
            ["git", "log", "--oneline"],
            ["git", "merge-base", "HEAD", "origin/main"],
            ["git", "remote", "get-url", "origin"],
        ):
            with self.subTest(argv=argv):
                request, _, error = CLICK_GATE._validate_inspection_request(
                    json.dumps({"version": 1, "commands": [argv]})
                )
                self.assertEqual(error, "")
                self.assertIsNotNone(request)
        safe, error = CLICK_GATE._build_read_only_git_argv(
            ["git", "diff", "--check"]
        )
        self.assertEqual(error, "")
        self.assertIsNotNone(safe)
        assert safe is not None
        self.assertIn("--no-pager", safe)
        self.assertIn("--no-optional-locks", safe)
        self.assertIn("core.fsmonitor=false", safe)
        self.assertIn("diff.external=", safe)
        self.assertIn("log.showSignature=false", safe)
        self.assertIn("format.pretty=medium", safe)
        self.assertIn("--no-ext-diff", safe)
        self.assertIn("--no-textconv", safe)

        environment = CLICK_GATE._sanitized_git_environment(
            {
                "PATH": os.environ.get("PATH", ""),
                "GIT_PAGER": "evil-pager",
                "GIT_EXTERNAL_DIFF": "evil-diff",
                "GIT_CONFIG_COUNT": "1",
            }
        )
        self.assertNotIn("GIT_PAGER", environment)
        self.assertNotIn("GIT_EXTERNAL_DIFF", environment)
        self.assertNotIn("GIT_CONFIG_COUNT", environment)
        self.assertEqual(environment["GIT_OPTIONAL_LOCKS"], "0")
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)

    def test_bypass_requires_exact_same_turn_one_use_authorization(self) -> None:
        self.set_default("on", "turn-0")
        denied = self.pre_tool("Bash", "click-gate bypass", "turn-1")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")

        self.prompt_submit("@Click bypass extra", "turn-2")
        malformed = self.pre_tool(
            "Bash", "click-gate bypass", "turn-2", submit_prompt=False
        )
        self.assertEqual(malformed["hookSpecificOutput"]["permissionDecision"], "deny")

        self.prompt_submit(
            "[@Click](plugin://click@click) BYPASS\nDo this turn without Click.",
            "turn-3",
        )
        authorized = self.pre_tool(
            "Bash", "click-gate bypass", "turn-3", submit_prompt=False
        )
        self.assertEqual(authorized["hookSpecificOutput"]["permissionDecision"], "allow")
        reused = self.pre_tool(
            "Bash", "click-gate bypass", "turn-3", submit_prompt=False
        )
        self.assertEqual(reused["hookSpecificOutput"]["permissionDecision"], "deny")

        self.prompt_submit("@Click bypass", "turn-4")
        later = self.pre_tool(
            "Bash", "click-gate bypass", "turn-5", submit_prompt=False
        )
        self.assertEqual(later["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_cancel_requires_authorization_and_clears_contract_once(self) -> None:
        self.set_default("manual", "turn-0")
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")

        denied = self.pre_tool("Bash", "click-gate cancel", "turn-2")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        contract_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        self.assertTrue(contract_path.exists())

        self.prompt_submit("@click cancel", "turn-3")
        cancelled = self.pre_tool(
            "Bash", "click-gate cancel", "turn-3", submit_prompt=False
        )
        self.assertEqual(cancelled["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertFalse(contract_path.exists())
        reused = self.pre_tool(
            "Bash", "click-gate cancel", "turn-3", submit_prompt=False
        )
        self.assertEqual(reused["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(
            self.pre_tool(
                "apply_patch", "*** Begin Patch\n*** End Patch", turn_id="turn-4"
            )
        )

    def test_prompt_authorization_accepts_only_allowlisted_first_line_forms(self) -> None:
        accepted = {
            "@Click bypass": "bypass",
            "@click BYPASS": "bypass",
            "  [@Click](plugin://click@click) bypass  \nContinue with the task.": "bypass",
            "[@click](plugin://click@click) CANCEL\nContinue with the task.": "cancel",
        }
        for prompt, expected in accepted.items():
            with self.subTest(prompt=prompt):
                self.assertEqual(CLICK_GATE._prompt_authorization(prompt), expected)

        rejected = (
            "@Click bypass extra",
            "[@Click](plugin://click@click) bypass,",
            "[@Click](plugin://other@click) bypass",
            "[@Other](plugin://click@click) bypass",
            "[@Click](plugin://click@CLICK) bypass",
            "Please use @Click bypass",
            "`@Click bypass`",
            "Continue with the task.\n@Click bypass",
        )
        for prompt in rejected:
            with self.subTest(prompt=prompt):
                self.assertEqual(CLICK_GATE._prompt_authorization(prompt), "")

    def test_manual_incomplete_contract_survives_eight_day_cleanup(self) -> None:
        self.set_default("manual", "turn-0")
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        contract_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        old = time.time() - 8 * 24 * 60 * 60
        os.utime(contract_path, (old, old))

        self.prompt_submit("continue the approved work", "turn-3")
        self.assertTrue(contract_path.exists())
        blocked = self.pre_tool(
            "Bash", "python3 update_schema.py", "turn-3", submit_prompt=False
        )
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "active execution contract",
            blocked["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_browser_evidence_requires_an_assigned_primary_source(self) -> None:
        self.approve_contract()
        denied = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            {"code": "await page.title()", "timeout_ms": 5000},
        )
        self.assertEqual(
            denied["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "kind `browser`",
            denied["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_browser_response_classifier_requires_meaningful_success(self) -> None:
        for response in (
            {},
            {"content": []},
            {"content": [{"type": "text", "text": ""}]},
            {"output": None},
            {"result": ""},
            {"status": "cancelled", "content": ["diagnostic"]},
        ):
            with self.subTest(response=response):
                self.assertTrue(CLICK_GATE._tool_response_failed(response))
        for response in (
            {"status": "success"},
            {"status": "completed"},
            {"content": [{"type": "text", "text": "ready"}]},
            {"result": False},
        ):
            with self.subTest(response=response):
                self.assertFalse(CLICK_GATE._tool_response_failed(response))

    def test_lost_browser_post_event_expires_and_allows_bounded_retry(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {"id": "E-browser", "kind": "browser", "description": "one session"}
        ]
        contract["verification"]["done_when"] = [
            {"condition": "the page works", "primary_evidence": "E-browser"}
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="lost-browser-post",
            )
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["external_evidence"]["browser_running"]["lost-browser-post"] = (
            time.time() - CLICK_GATE.BROWSER_RUNNING_TTL_SECONDS - 1
        )
        state_path.write_text(json.dumps(state), encoding="utf-8")

        invalid_retry = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            {"code": "await page.title()", "timeout_ms": 60000},
            tool_use_id="invalid-browser-retry",
        )
        self.assertEqual(
            invalid_retry["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["external_evidence"]["browser_running"], {})
        self.assertEqual(state["external_evidence"]["browser_status"], "failed")

        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="browser-retry",
            )
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["external_evidence"]["browser_calls"], 2)
        self.assertIn(
            "browser-retry", state["external_evidence"]["browser_running"]
        )

    def test_browser_primary_source_uses_structured_kind_not_localized_text(self) -> None:
        conditions = (
            "layout works",
            "레이아웃이 동작한다",
            "布局正常",
            "レイアウトが動作する",
        )
        for condition in conditions:
            with self.subTest(condition=condition):
                contract = self.contract()
                contract["verification"]["evidence"] = [
                    {
                        "id": "E-browser",
                        "kind": "browser",
                        "description": "one representative session",
                    }
                ]
                contract["verification"]["done_when"] = [
                    {
                        "condition": condition,
                        "primary_evidence": "E-browser",
                    }
                ]
                self.assertTrue(CLICK_GATE._browser_evidence_required(contract))

        non_browser = self.contract()
        non_browser["verification"]["evidence"][0]["description"] = (
            "a local test whose name happens to contain browser"
        )
        self.assertFalse(CLICK_GATE._browser_evidence_required(non_browser))

    def test_browser_evidence_deduplicates_success_without_a_three_call_cap(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {
                "id": "E-browser",
                "kind": "browser",
                "description": "one representative input and layout session",
            }
        ]
        contract["verification"]["done_when"] = [
            {
                "condition": "input and responsive layout work",
                "primary_evidence": "E-browser",
            }
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        timed = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            {"code": "await page.waitForTimeout(55000)", "timeout_ms": 60000},
        )
        self.assertEqual(timed["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("timeouts may not exceed", timed["hookSpecificOutput"]["permissionDecisionReason"])

        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="browser-1",
            )
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="browser-1",
                tool_response={"status": "success"},
            )
        )

        duplicate = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            {
                "code": "  await page.title()\r\n",
                "timeout_ms": 12000,
                "_meta": {"trace": "different bookkeeping"},
            },
            tool_use_id="browser-duplicate",
        )
        self.assertEqual(
            duplicate["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "already collected this successful Browser interaction",
            duplicate["hookSpecificOutput"]["permissionDecisionReason"],
        )

        for index in range(2, 7):
            tool_id = f"browser-{index}"
            code = f"await page.locator('main').count(); // {index}"
            self.assertIsNone(
                self.tool_hook(
                    "pre-tool",
                    "mcp__node_repl__js",
                    {"code": code, "timeout_ms": 5000},
                    tool_use_id=tool_id,
                )
            )
            self.assertIsNone(
                self.tool_hook(
                    "post-tool",
                    "mcp__node_repl__js",
                    {"code": code, "timeout_ms": 5000},
                    tool_use_id=tool_id,
                    tool_response={"status": "success"},
                )
            )

    def test_browser_failure_retry_is_per_input_and_observed_is_monotonic(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {
                "id": "E-browser",
                "kind": "browser",
                "description": "one representative browser session",
            }
        ]
        contract["verification"]["done_when"] = [
            {
                "condition": "the representative session works",
                "primary_evidence": "E-browser",
            }
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        successful_input = {"code": "await page.title()", "timeout_ms": 5000}
        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                successful_input,
                tool_use_id="browser-success",
            )
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                successful_input,
                tool_use_id="browser-success",
                tool_response={"status": "success"},
            )
        )

        failing_input = {"code": "await missing.locator()", "timeout_ms": 5000}
        for attempt in range(2):
            tool_id = f"browser-failure-{attempt}"
            self.assertIsNone(
                self.tool_hook(
                    "pre-tool",
                    "mcp__node_repl__js",
                    failing_input,
                    tool_use_id=tool_id,
                )
            )
            self.assertIsNone(
                self.tool_hook(
                    "post-tool",
                    "mcp__node_repl__js",
                    failing_input,
                    tool_use_id=tool_id,
                    tool_response={"status": "error", "isError": True},
                )
            )

        blocked = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            failing_input,
            tool_use_id="browser-failure-blocked",
        )
        self.assertEqual(
            blocked["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "already failed twice",
            blocked["hookSpecificOutput"]["permissionDecisionReason"],
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        source = state["evidence_state"]["sources"][
            CLICK_GATE._evidence_key("E-browser")
        ]
        self.assertEqual(state["external_evidence"]["browser_status"], "observed")
        self.assertEqual(source["status"], "observed")

    def test_browser_primary_source_is_required_for_contract_completion(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {
                "id": "E-browser",
                "kind": "browser",
                "description": "one representative visual integration session",
            }
        ]
        contract["verification"]["done_when"] = [
            {
                "condition": "visual integration works",
                "primary_evidence": "E-browser",
            }
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            state["external_evidence"]["browser_source_key"],
            CLICK_GATE._evidence_key("E-browser"),
        )
        self.assertFalse(CLICK_GATE._contract_is_completed(state))
        premature = self.complete_evidence("E-browser")
        self.assertEqual(
            premature["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "successful current-revision Browser call",
            premature["hookSpecificOutput"]["permissionDecisionReason"],
        )

        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="completion-browser",
            )
        )
        self.tool_hook(
            "post-tool",
            "mcp__node_repl__js",
            {"code": "await page.title()", "timeout_ms": 5000},
            tool_use_id="completion-browser",
            tool_response={"status": "success"},
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(CLICK_GATE._contract_is_completed(state))
        completed = self.complete_evidence("E-browser")
        self.assertEqual(
            completed["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(CLICK_GATE._contract_is_completed(state))
        repeated = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            {"code": "await page.title()", "timeout_ms": 5000},
            tool_use_id="completion-browser-2",
        )
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "contract is complete",
            repeated["hookSpecificOutput"]["permissionDecisionReason"],
        )
        self.prompt_submit("open an unrelated browser reference", "turn-3")
        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                turn_id="turn-3",
                tool_use_id="unrelated-browser",
            )
        )

    def test_empty_browser_tool_response_is_not_completion_evidence(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {"id": "E-browser", "kind": "browser", "description": "one session"}
        ]
        contract["verification"]["done_when"] = [
            {"condition": "the page works", "primary_evidence": "E-browser"}
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="empty-browser-response",
            )
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="empty-browser-response",
                tool_response={},
            )
        )
        denied = self.complete_evidence("E-browser")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "successful current-revision Browser call",
            denied["hookSpecificOutput"]["permissionDecisionReason"],
        )
        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="cancelled-browser-response",
            )
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="cancelled-browser-response",
                tool_response={"status": "cancelled", "content": ["diagnostic"]},
            )
        )
        denied = self.complete_evidence("E-browser")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_managed_service_start_runner_is_one_use_and_preclaimed(self) -> None:
        self.approve_contract()
        request = {
            "version": 1,
            "action": "start",
            "argv": [sys.executable, "-m", "http.server", "0"],
        }
        runner_token = self.id()
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(
                CLICK_GATE.secrets,
                "token_urlsafe",
                side_effect=["service-id", runner_token],
            ),
        ):
            _, error = CLICK_GATE._prepare_service(
                self.base_event, json.dumps(request)
            )
        self.assertEqual(error, "")
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        normalized, error = CLICK_GATE._validate_service_request(json.dumps(request))
        self.assertEqual(error, "")
        self.assertIsNotNone(normalized)
        assert normalized is not None
        arguments = [
            str(state_path),
            "service-id",
            runner_token,
            str(self.workspace.resolve()),
            CLICK_GATE._encoded_request(normalized),
        ]

        def launch_supervisor(*_args: object, **_kwargs: object) -> mock.Mock:
            with CLICK_GATE._state_lock():
                self.assertTrue(
                    CLICK_GATE._record_service_fields(
                        state_path,
                        "service-id",
                        expected_statuses=("launching",),
                        status="running",
                    )
                )
            return mock.Mock()

        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(
                CLICK_PROCESS,
                "spawn_argv",
                side_effect=launch_supervisor,
            ) as popen,
        ):
            tampered = [*arguments]
            tampered[2] = "wrong-token"
            self.assertEqual(CLICK_GATE._run_service_start(tampered), 2)
            self.assertEqual(CLICK_GATE._run_service_start(arguments), 0)
            self.assertEqual(CLICK_GATE._run_service_start(arguments), 2)
        self.assertEqual(popen.call_count, 1)

    def test_managed_service_rejects_stale_or_future_start_before_launch(self) -> None:
        for label, started_at in (
            (
                "expired",
                int(time.time()) - CLICK_GATE.SERVICE_START_TIMEOUT_SECONDS * 2 - 1,
            ),
            ("future", int(time.time()) + 60),
        ):
            with self.subTest(label=label):
                self.plugin_data = Path(self.temporary.name) / f"service-{label}"
                self.submitted_turns.clear()
                self.approve_contract()
                request = {
                    "version": 1,
                    "action": "start",
                    "argv": [sys.executable, "-m", "http.server", "0"],
                }
                runner_token = f"service-{label}-token"
                with (
                    mock.patch.dict(
                        CLICK_GATE.os.environ,
                        {"PLUGIN_DATA": str(self.plugin_data)},
                    ),
                    mock.patch.object(
                        CLICK_GATE.secrets,
                        "token_urlsafe",
                        side_effect=[f"service-{label}-id", runner_token],
                    ),
                ):
                    CLICK_GATE._prepare_service(self.base_event, json.dumps(request))
                state_path = next(
                    (self.plugin_data / "gate-state").glob("session-contract-*.json")
                ).resolve()
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state["service"]["started_at"] = started_at
                state_path.write_text(json.dumps(state), encoding="utf-8")
                normalized, error = CLICK_GATE._validate_service_request(
                    json.dumps(request)
                )
                self.assertEqual(error, "")
                assert normalized is not None
                arguments = [
                    str(state_path),
                    f"service-{label}-id",
                    runner_token,
                    str(self.workspace.resolve()),
                    CLICK_GATE._encoded_request(normalized),
                ]
                with (
                    mock.patch.dict(
                        CLICK_GATE.os.environ,
                        {"PLUGIN_DATA": str(self.plugin_data)},
                    ),
                    mock.patch.object(CLICK_PROCESS, "spawn_argv") as popen,
                ):
                    self.assertEqual(CLICK_GATE._run_service_start(arguments), 2)
                popen.assert_not_called()

    def test_managed_service_supervisor_launch_is_one_use(self) -> None:
        self.approve_contract()
        request = {
            "version": 1,
            "action": "start",
            "argv": [sys.executable, "-m", "http.server", "0"],
        }
        runner_token = self.id()
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(
                CLICK_GATE.secrets,
                "token_urlsafe",
                side_effect=["service-id", runner_token],
            ),
        ):
            CLICK_GATE._prepare_service(self.base_event, json.dumps(request))
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        normalized, error = CLICK_GATE._validate_service_request(json.dumps(request))
        self.assertEqual(error, "")
        assert normalized is not None
        cwd_raw = str(self.workspace.resolve())
        arguments = [
            str(state_path),
            "service-id",
            runner_token,
            cwd_raw,
            CLICK_GATE._encoded_request(normalized),
        ]
        child = mock.Mock()
        child.pid = 12345
        child.poll.return_value = 0
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            CLICK_GATE._state_lock(),
        ):
            self.assertEqual(
                CLICK_GATE._claim_service_runner(
                    state_path,
                    "service-id",
                    normalized,
                    cwd_raw,
                    runner_token,
                    supervisor=False,
                ),
                "",
            )
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(
                CLICK_PROCESS, "spawn_argv", return_value=child
            ) as popen,
            mock.patch.object(CLICK_GATE.time, "sleep"),
        ):
            self.assertEqual(CLICK_GATE._run_service_supervisor(arguments), 2)
            self.assertEqual(CLICK_GATE._run_service_supervisor(arguments), 2)
        self.assertEqual(popen.call_count, 1)

    def test_managed_service_rejects_stale_supervisor_before_launch(self) -> None:
        self.approve_contract()
        request = {
            "version": 1,
            "action": "start",
            "argv": [sys.executable, "-m", "http.server", "0"],
        }
        runner_token = self.id()
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(
                CLICK_GATE.secrets,
                "token_urlsafe",
                side_effect=["stale-supervisor-id", runner_token],
            ),
        ):
            CLICK_GATE._prepare_service(self.base_event, json.dumps(request))
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        normalized, error = CLICK_GATE._validate_service_request(json.dumps(request))
        self.assertEqual(error, "")
        assert normalized is not None
        cwd_raw = str(self.workspace.resolve())
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            CLICK_GATE._state_lock(),
        ):
            self.assertEqual(
                CLICK_GATE._claim_service_runner(
                    state_path,
                    "stale-supervisor-id",
                    normalized,
                    cwd_raw,
                    runner_token,
                    supervisor=False,
                ),
                "",
            )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["service"]["runner_claimed_at"] = (
            int(time.time()) - CLICK_GATE.SERVICE_START_TIMEOUT_SECONDS * 2 - 1
        )
        state_path.write_text(json.dumps(state), encoding="utf-8")
        arguments = [
            str(state_path),
            "stale-supervisor-id",
            runner_token,
            cwd_raw,
            CLICK_GATE._encoded_request(normalized),
        ]
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(CLICK_PROCESS, "spawn_argv") as popen,
        ):
            self.assertEqual(CLICK_GATE._run_service_supervisor(arguments), 2)
        popen.assert_not_called()

    def test_managed_service_cancellation_before_claim_prevents_launch(self) -> None:
        self.approve_contract()
        request = {
            "version": 1,
            "action": "start",
            "argv": [sys.executable, "-m", "http.server", "0"],
        }
        runner_token = self.id()
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(
                CLICK_GATE.secrets,
                "token_urlsafe",
                side_effect=["service-id", runner_token],
            ),
        ):
            CLICK_GATE._prepare_service(self.base_event, json.dumps(request))
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        normalized, error = CLICK_GATE._validate_service_request(json.dumps(request))
        self.assertEqual(error, "")
        assert normalized is not None
        arguments = [
            str(state_path),
            "service-id",
            runner_token,
            str(self.workspace.resolve()),
            CLICK_GATE._encoded_request(normalized),
        ]
        state_path.unlink()
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(CLICK_PROCESS, "spawn_argv") as popen,
        ):
            self.assertEqual(CLICK_GATE._run_service_start(arguments), 2)
        popen.assert_not_called()

    def test_long_running_local_server_uses_managed_service_lifecycle(self) -> None:
        self.approve_contract()
        argv = [sys.executable, "-m", "http.server", "0", "--bind", "127.0.0.1"]
        mutation = self.mutate_gate(argv)
        self.assertEqual(
            mutation["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "click-gate service",
            mutation["hookSpecificOutput"]["permissionDecisionReason"],
        )

        start_request = {"version": 1, "action": "start", "argv": argv}
        start = self.pre_tool(
            "Bash",
            f"click-gate service {shlex.quote(json.dumps(start_request))}",
            "turn-2",
        )
        self.assertEqual(start["hookSpecificOutput"]["permissionDecision"], "allow")
        start_result = self.run_rewritten(start)
        self.assertEqual(start_result.returncode, 0, start_result.stderr)

        stop_request = {"version": 1, "action": "stop"}
        stop = self.pre_tool(
            "Bash",
            f"click-gate service {shlex.quote(json.dumps(stop_request))}",
            "turn-2",
        )
        self.assertEqual(stop["hookSpecificOutput"]["permissionDecision"], "allow")
        stop_result = self.run_rewritten(stop)
        self.assertEqual(stop_result.returncode, 0, stop_result.stderr)
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["service"]["status"], "stopped")

        restart = self.pre_tool(
            "Bash",
            f"click-gate service {shlex.quote(json.dumps(start_request))}",
            "turn-2",
        )
        restart_result = self.run_rewritten(restart)
        self.assertEqual(restart_result.returncode, 0, restart_result.stderr)
        end_event = {
            **self.base_event,
            "hook_event_name": "SessionEnd",
        }
        end_result, end_payload = self.run_hook("session-end", end_event)
        self.assertEqual(end_result.returncode, 0, end_result.stderr)
        self.assertIsNone(end_payload)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state["service"]["status"] == "stopped":
                break
            time.sleep(0.05)
        self.assertEqual(state["service"]["status"], "stopped")

    def test_verification_root_main_py_fails_stale(self) -> None:
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("main.py"))
        self.assert_verification_new_path_behavior("main.py", suspicious=True)

    def test_verification_root_package_json_fails_stale(self) -> None:
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("package.json"))
        self.assert_verification_new_path_behavior("package.json", suspicious=True)

    def test_verification_root_dockerfile_fails_stale(self) -> None:
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("Dockerfile"))
        self.assert_verification_new_path_behavior("Dockerfile", suspicious=True)

    def test_verification_generic_report_fails_stale(self) -> None:
        self.assertFalse(CLICK_GATE._new_untracked_is_suspicious("generic-report.txt"))
        self.assert_verification_new_path_behavior("generic-report.txt")

    def test_verification_ignored_artifact_does_not_change_snapshot(self) -> None:
        self.assert_verification_new_path_behavior(
            "ignored-artifact.tmp", ignored=True
        )

if __name__ == "__main__":
    unittest.main()
