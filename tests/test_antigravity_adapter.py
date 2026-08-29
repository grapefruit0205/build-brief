from __future__ import annotations

import json
import os
from pathlib import Path
import re
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

    def test_missing_pre_invocation_context_denies_mutation_but_allows_read(self) -> None:
        mutation = self.pre_tool(
            "write_to_file", {"TargetFile": str(self.workspace / "app.py")}
        )
        self.assertEqual(mutation.get("decision"), "deny")
        read = self.pre_tool(
            "run_command",
            {"CommandLine": "git status --short", "Cwd": str(self.workspace)},
        )
        self.assertEqual(read.get("decision"), "allow")

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


if __name__ == "__main__":
    unittest.main()
