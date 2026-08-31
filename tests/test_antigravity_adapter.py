from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "hooks" / "antigravity_gate.py"
PLATFORM = ROOT / "platforms" / "antigravity"


class AntigravityAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.plugin_data = root / "plugin-data"
        self.config_home = root / "config"
        self.transcript = root / "transcript.jsonl"
        tests = self.workspace / "tests"
        tests.mkdir()
        (tests / "test_sample.py").write_text(
            "import unittest\n\n"
            "class SampleTests(unittest.TestCase):\n"
            "    def test_true(self):\n"
            "        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        self.environment = os.environ.copy()
        self.environment["PLUGIN_DATA"] = str(self.plugin_data)
        self.environment["CLICK_CONFIG_HOME"] = str(self.config_home)
        self.base = {
            "conversationId": "conversation-1",
            "workspacePaths": [str(self.workspace)],
            "transcriptPath": str(self.transcript),
            "artifactDirectoryPath": str(root / "artifacts"),
            "modelName": "gemini-test",
        }

    def write_user_prompt(self, value: str) -> None:
        self.transcript.write_text(
            json.dumps({"role": "user", "content": value}) + "\n",
            encoding="utf-8",
        )

    def hook(self, mode: str, extra: dict | None = None) -> tuple[int, dict, str]:
        event = {**self.base, **(extra or {})}
        result = subprocess.run(
            [sys.executable, str(SCRIPT), mode],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=self.environment,
            check=False,
        )
        payload = json.loads(result.stdout) if result.stdout else {}
        return result.returncode, payload, result.stderr

    def pre_invocation(self, prompt: str, invocation_num: int = 0) -> dict:
        self.write_user_prompt(prompt)
        code, payload, error = self.hook(
            "pre-invocation",
            {"invocationNum": invocation_num, "initialNumSteps": invocation_num},
        )
        self.assertEqual(code, 0, error)
        return payload

    def stop(self) -> dict:
        code, payload, error = self.hook(
            "stop",
            {
                "executionNum": 1,
                "terminationReason": "model_stop",
                "error": "",
                "fullyIdle": True,
            },
        )
        self.assertEqual(code, 0, error)
        return payload

    def control(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "control", *arguments],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            env=self.environment,
            check=False,
        )

    def launcher_command(self, *arguments: str) -> str:
        argv = [
            str(Path(sys.executable).resolve()),
            str(SCRIPT.resolve()),
            "control",
            *arguments,
        ]
        return shlex.join(argv)

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
            ["git", "add", *tracked_paths], cwd=self.workspace, check=True
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

    def contract(self) -> dict:
        return {
            "outcome": "write one approved file without replanning",
            "boundary": {
                "in_scope": ["one workspace file"],
                "out_of_scope": ["external deployment"],
            },
            "must_hold": ["a later user execution approves the exact staged contract"],
            "build": {"approach": ["use the existing file mutation path"]},
            "verification": {
                "scale": "focused",
                "evidence": [
                    {
                        "id": "E1",
                        "kind": "argv",
                        "description": "workspace unittest suite",
                    }
                ],
                "done_when": [
                    {
                        "condition": "the workspace behavior passes",
                        "primary_evidence": "E1",
                    }
                ],
            },
            "plain_language": "승인된 파일 변경을 수행하고 기존 테스트로 한 번 확인합니다.",
        }

    def stage(self) -> str:
        staged = self.control("stage", json.dumps(self.contract()))
        self.assertEqual(staged.returncode, 0, staged.stderr)
        match = re.search(r"CLICK_CONTRACT_ID=(ctr_[0-9a-f]{32})", staged.stdout)
        self.assertIsNotNone(match, staged.stdout)
        return str(match.group(1))

    def approve(self) -> str:
        context = self.pre_invocation("build the requested feature")
        self.assertIn("injectSteps", context)
        default = self.control("default", "on")
        self.assertEqual(default.returncode, 0, default.stderr)
        contract_id = self.stage()
        same_execution = self.control("pass", contract_id)
        self.assertNotEqual(same_execution.returncode, 0)
        self.assertIn("separate user response", same_execution.stderr)
        self.assertEqual(self.stop().get("decision"), "allow")
        self.pre_invocation("build the requested feature", invocation_num=0)
        no_new_user_entry = self.control("pass", contract_id)
        self.assertNotEqual(no_new_user_entry.returncode, 0)
        next_context = self.pre_invocation("I approve", invocation_num=0)
        self.assertIn(contract_id, json.dumps(next_context))
        passed = self.control("pass", contract_id)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        return contract_id

    def pre_tool(self, name: str, arguments: dict) -> dict:
        code, payload, error = self.hook(
            "pre-tool",
            {"toolCall": {"name": name, "args": arguments}, "stepIdx": 4},
        )
        self.assertEqual(code, 0, error)
        return payload

    def assert_plan_advisory(self, payload: dict, expected_reason: str) -> None:
        self.assertEqual(payload.get("decision"), "allow")
        self.assertIn(expected_reason, payload.get("reason", ""))

    def test_contract_lifecycle_mutation_and_evidence_share_the_core(self) -> None:
        self.approve()
        allowed = self.pre_tool(
            "write_to_file",
            {"TargetFile": str(self.workspace / "app.py"), "CodeContent": "ok"},
        )
        self.assertEqual(allowed.get("decision"), "allow")

        blocked = self.pre_tool(
            "run_command",
            {"CommandLine": "touch surprise.py", "Cwd": str(self.workspace)},
        )
        self.assertEqual(blocked.get("decision"), "deny")
        self.assertIn("click-gate mutate", blocked.get("reason", ""))

        request = {
            "version": 2,
            "checks": [
                {
                    "evidence_id": "E1",
                    "argv": [
                        "python3",
                        "-m",
                        "unittest",
                        "discover",
                        "-s",
                        "tests",
                        "-q",
                    ],
                    "class": "broad",
                }
            ],
        }
        verified = self.control("verify", json.dumps(request))
        self.assertEqual(verified.returncode, 0, verified.stderr)
        states = list((self.plugin_data / "gate-state").glob("session-contract-*.json"))
        self.assertEqual(len(states), 1)
        state = json.loads(states[0].read_text(encoding="utf-8"))
        sources = state["evidence_state"]["sources"]
        self.assertEqual(next(iter(sources.values()))["status"], "passed")

    def test_active_mutation_fails_closed_without_a_contract(self) -> None:
        self.pre_invocation("change the file")
        self.assertEqual(self.control("default", "on").returncode, 0)
        payload = self.pre_tool(
            "replace_file_content",
            {"TargetFile": str(self.workspace / "app.py")},
        )
        self.assertEqual(payload.get("decision"), "deny")
        self.assertIn("execution contract", payload.get("reason", ""))

    def test_missing_context_denies_run_command_but_allows_native_read_tool(self) -> None:
        mutation = self.pre_tool(
            "write_to_file", {"TargetFile": str(self.workspace / "app.py")}
        )
        self.assertEqual(mutation.get("decision"), "deny")
        read = self.pre_tool(
            "run_command",
            {"CommandLine": "git status --short", "Cwd": str(self.workspace)},
        )
        self.assertEqual(read.get("decision"), "deny")
        self.assertIn("control launcher", read.get("reason", ""))
        native_read = self.pre_tool(
            "view_file", {"AbsolutePath": str(self.workspace / "app.py")}
        )
        self.assertEqual(native_read.get("decision"), "allow")

    def test_missing_context_allows_plan_tools_without_granting_mutation(self) -> None:
        for tool_name in ("update_plan", "create_plan"):
            with self.subTest(tool_name=tool_name):
                plan = self.pre_tool(tool_name, {"plan": []})
                self.assertEqual(plan.get("decision"), "allow")

        mutation = self.pre_tool(
            "write_to_file", {"TargetFile": str(self.workspace / "app.py")}
        )
        self.assertEqual(mutation.get("decision"), "deny")
        self.assertIn("PreInvocation context", mutation.get("reason", ""))

    def test_approved_contract_advises_plan_but_still_blocks_replacement(self) -> None:
        self.approve()
        for tool_name in ("update_plan", "create_plan"):
            with self.subTest(tool_name=tool_name):
                plan = self.pre_tool(tool_name, {"plan": []})
                self.assert_plan_advisory(plan, "approved contract")
                self.assertIn("remains authoritative", plan["reason"])

        replacement = self.contract()
        replacement["outcome"] = "replace the approved outcome without new authority"
        blocked = self.control("stage", json.dumps(replacement))
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("already executing one approved contract", blocked.stderr)

    def test_pre_invocation_injects_only_the_exact_absolute_control_launcher(self) -> None:
        payload = self.pre_invocation("inspect the project")
        message = payload["injectSteps"][0]["ephemeralMessage"]
        self.assertIn("exact absolute Click control launcher", message)
        self.assertIn(self.launcher_command(), message)

        exact = self.pre_tool(
            "run_command",
            {
                "CommandLine": self.launcher_command("default", "on"),
                "Cwd": str(self.workspace),
            },
        )
        self.assertEqual(exact.get("decision"), "allow")

        for executable in ("python3", "./python3", str(self.workspace / "python3")):
            with self.subTest(executable=executable):
                shadow = shlex.join(
                    [
                        executable,
                        str(SCRIPT.resolve()),
                        "control",
                        "default",
                        "on",
                    ]
                )
                denied = self.pre_tool(
                    "run_command",
                    {"CommandLine": shadow, "Cwd": str(self.workspace)},
                )
                self.assertEqual(denied.get("decision"), "deny")

        valid = self.launcher_command("default", "on")
        malicious_suffixes = (
            "&&touch unexpected",
            ";touch unexpected",
            " & touch unexpected",
            "|touch unexpected",
            " || touch unexpected",
            ">unexpected",
            " < unexpected",
            " (touch unexpected)",
            "\ntouch unexpected",
            "\rtouch unexpected",
            " $(touch unexpected)",
            " <(printf unexpected)",
            " $CLICK_ACTION",
            " ${CLICK_ACTION}",
            " $((1 + 1))",
            " `touch unexpected`",
            " !-1",
            ' "!!"',
            " *",
            " ?",
            " [ab]",
            " {a,b}",
            " ~",
            " # ignored",
            "\0",
            " '",
            ' "',
            " \\",
        )
        for suffix in malicious_suffixes:
            with self.subTest(suffix=repr(suffix)):
                denied = self.pre_tool(
                    "run_command",
                    {
                        "CommandLine": valid + suffix,
                        "Cwd": str(self.workspace),
                    },
                )
                self.assertEqual(denied.get("decision"), "deny")

        literal = "literal $HOME $(not-run) `not-run`; & | < > ! * ? [x] {a,b} ~ #"
        quoted = self.launcher_command("stage", literal)
        accepted = self.pre_tool(
            "run_command",
            {"CommandLine": quoted, "Cwd": str(self.workspace)},
        )
        self.assertEqual(accepted.get("decision"), "allow")

    @unittest.skipUnless(os.name == "nt", "Windows argv parser regression")
    def test_windows_encoded_runner_round_trips_without_shell_expansion(self) -> None:
        from hooks import antigravity_gate, click_gate

        arguments = [
            str(Path(sys.executable).resolve()),
            str((ROOT / "hooks" / "click_gate.py").resolve()),
            "--state-root",
            r"C:\work space\%PATH%!CLICK!\끝\\",
            "run-verification",
            "encoded-payload",
        ]
        command = click_gate._runner_shell_command(arguments)
        parsed = antigravity_gate._command_argv(command)
        self.assertEqual(parsed[:3], ["py", "-3", arguments[1]])
        self.assertEqual(parsed[3], "--encoded-runner")
        decoded, error = click_gate._decode_runner_transport(parsed[4])
        self.assertEqual(error, "")
        self.assertEqual(decoded, arguments[2:])

        direct = antigravity_gate._runner_command_argv(command)
        self.assertEqual(direct[:2], arguments[:2])
        self.assertEqual(direct[2], "--encoded-runner")
        decoded, error = click_gate._decode_runner_transport(direct[3])
        self.assertEqual(error, "")
        self.assertEqual(decoded, arguments[2:])

    def test_context_denies_native_run_command_reads_but_leaves_hosted_tools_unmatched(self) -> None:
        self.pre_invocation("inspect the project")
        denied = self.pre_tool(
            "run_command",
            {"CommandLine": "git status --short", "Cwd": str(self.workspace)},
        )
        self.assertEqual(denied.get("decision"), "deny")
        self.assertIn("trusted inspection runner", denied.get("reason", ""))

        hooks = json.loads((PLATFORM / "hooks.json").read_text(encoding="utf-8"))
        matcher = hooks["click-tools"]["PreToolUse"][0]["matcher"]
        self.assertIsNone(re.search(matcher, "mcp__example__read"))

    def test_control_inspect_surfaces_broad_inventory_advisory_without_blocking(
        self,
    ) -> None:
        self.initialize_git("tests/test_sample.py")
        self.approve()
        first_request = json.dumps(
            {"version": 1, "commands": [["git", "ls-files"]]}
        )
        second_request = json.dumps(
            {"version": 1, "commands": [["git", "ls-files", "--cached"]]}
        )

        first = self.control("inspect", first_request)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertNotIn("Click advisory", first.stderr)

        second = self.control("inspect", second_request)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("Click advisory", second.stderr)
        self.assertIn("already completed", second.stderr)

        identical = self.control("inspect", first_request)
        self.assertEqual(identical.returncode, 0, identical.stderr)
        self.assertIn("Click advisory", identical.stderr)
        self.assertIn("identical read or search already succeeded", identical.stderr)

    def test_plain_cancel_is_recovered_from_the_transcript(self) -> None:
        self.pre_invocation("build this")
        self.assertEqual(self.control("default", "on").returncode, 0)
        self.stage()
        self.stop()
        self.pre_invocation("@Click cancel")
        cancelled = self.control("cancel")
        self.assertEqual(cancelled.returncode, 0, cancelled.stderr)

    def test_antigravity_manifest_and_hooks_use_documented_shapes(self) -> None:
        manifest = json.loads((PLATFORM / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "click")
        self.assertEqual(
            set(manifest), {"$schema", "name", "description"}
        )
        hooks = json.loads((PLATFORM / "hooks.json").read_text(encoding="utf-8"))
        self.assertIn("PreInvocation", hooks["click-context"])
        self.assertIn("Stop", hooks["click-context"])
        self.assertIn("PreToolUse", hooks["click-tools"])
        self.assertIn("PostToolUse", hooks["click-tools"])
        pre_tool_matcher = re.compile(
            hooks["click-tools"]["PreToolUse"][0]["matcher"]
        )
        for tool_name in (
            "update_plan",
            "create_plan",
            "run_command",
            "write_to_file",
            "replace_file_content",
            "multi_replace_file_content",
        ):
            with self.subTest(tool_name=tool_name):
                self.assertIsNotNone(pre_tool_matcher.fullmatch(tool_name))
        self.assertIsNone(pre_tool_matcher.fullmatch("mcp__example__read"))


if __name__ == "__main__":
    unittest.main()
