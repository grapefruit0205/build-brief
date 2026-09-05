from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess
import sys

from tests.click_gate_test_support import (
    CLICK_EVIDENCE,
    CLICK_VERIFICATION,
    ClickGateTestCase,
    split_runner_command,
)


class ClickVerificationNamesTests(ClickGateTestCase):
    hook_in_process = True

    def definition(
        self,
        *,
        verification_id: str = "auth-unit",
        label: str = "Auth unit tests",
        argv: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "id": verification_id,
            "label": label,
            "class": "targeted",
            "checks": [argv or self.verification_argv()],
        }

    def write_catalog(
        self, definitions: list[dict[str, object]] | None = None
    ) -> Path:
        target = self.workspace / ".click" / "evidence-shards.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "version": 2,
                    "verifications": definitions or [self.definition()],
                    "entries": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return target

    def initialize_named_workspace(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.write_catalog()
        self.initialize_git(
            ".gitignore",
            "verification_fixture.py",
            ".click/evidence-shards.json",
        )

    def commit_all(self, message: str) -> None:
        subprocess.run(["git", "add", "-A"], cwd=self.workspace, check=True)
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
                message,
            ],
            cwd=self.workspace,
            check=True,
        )

    def verify_names(
        self, names: list[str], turn_id: str = "turn-1"
    ) -> dict:
        request = {
            "version": 2,
            "workdir": str(self.workspace),
            "names": names,
        }
        command = f"click-gate verify {shlex.quote(json.dumps(request))}"
        sequence = getattr(self, "verification_request_sequence", 0) + 1
        self.verification_request_sequence = sequence
        payload = self.pre_tool(
            "Bash",
            command,
            turn_id,
            tool_use_id=f"named-verification-{sequence}",
        )
        assert payload is not None
        return payload

    def state(self) -> dict[str, object]:
        candidates = list(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        self.assertEqual(len(candidates), 1)
        return json.loads(candidates[0].read_text(encoding="utf-8"))

    def test_repeated_name_uses_same_definition_and_exact_reuse_path(self) -> None:
        self.initialize_named_workspace()

        first = self.verify_names(["auth-unit"])
        self.assertIn(
            "run-verification",
            split_runner_command(
                first["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )
        self.assertEqual(self.run_rewritten(first).returncode, 0)

        second = self.verify_names(["auth-unit"])

        command = second["hookSpecificOutput"]["updatedInput"]["command"]
        self.assertIn("Click reused", command)
        state = self.state()
        source_key = CLICK_EVIDENCE.evidence_key("auth-unit")
        source = state["evidence_state"]["sources"][source_key]
        self.assertEqual(source["locked_check_digest"], source["verified_check_digest"])
        self.assertEqual(
            state["verification"]["incremental_plan"]["decisions"][0]["decision"],
            "reuse-exact",
        )
        current_batch = CLICK_VERIFICATION.click_incremental.current_batch(
            state["verification"]
        )
        assert current_batch is not None
        self.assertEqual(current_batch["sources"][0]["label"], "Auth unit tests")

    def test_changed_named_argv_is_rechecked_in_a_successor_evidence_task(self) -> None:
        self.initialize_named_workspace()
        baseline = self.verify_names(["auth-unit"])
        self.assertEqual(self.run_rewritten(baseline).returncode, 0)

        self.write_catalog(
            [self.definition(argv=self.verification_argv(exit_code=1))]
        )
        self.commit_all("change exact verification definition")
        self.prompt_submit("follow-up code work", "turn-2")

        changed = self.verify_names(["auth-unit"], "turn-2")

        command = changed["hookSpecificOutput"]["updatedInput"]["command"]
        self.assertIn("run-verification", split_runner_command(command))
        self.assertNotIn("Click reused", command)
        self.assertEqual(self.run_rewritten(changed).returncode, 1)
        state = self.state()
        decision = state["verification"]["incremental_plan"]["decisions"][0]
        self.assertEqual(decision["decision"], "run")
        self.assertEqual(decision["reason_code"], "check-binding-changed")

    def test_catalog_edit_after_preparation_prevents_execution(self) -> None:
        self.initialize_named_workspace()
        prepared = self.verify_names(["auth-unit"])
        target = self.workspace / ".click" / "evidence-shards.json"
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "Auth unit tests", "Changed display label"
            ),
            encoding="utf-8",
        )

        result = self.run_rewritten(prepared)

        self.assertEqual(result.returncode, 2)
        self.assertIn("changed after preparation", result.stderr)
        self.assertNotIn("[Click verification", result.stdout)
        state = self.state()
        source = state["evidence_state"]["sources"][
            CLICK_EVIDENCE.evidence_key("auth-unit")
        ]
        self.assertEqual(source["attempts"], 0)
        self.assertEqual(source["status"], "ready")

    def test_same_name_in_another_workspace_does_not_reuse_results(self) -> None:
        self.initialize_named_workspace()
        baseline = self.verify_names(["auth-unit"])
        self.assertEqual(self.run_rewritten(baseline).returncode, 0)

        other = Path(self.temporary.name) / "other-workspace"
        other.mkdir()
        (other / "verification_fixture.py").write_text(
            (self.workspace / "verification_fixture.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (other / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        original_workspace = self.workspace
        self.workspace = other
        self.base_event["cwd"] = str(other)
        self.write_catalog()
        self.initialize_git(
            ".gitignore",
            "verification_fixture.py",
            ".click/evidence-shards.json",
        )

        second = self.verify_names(["auth-unit"], "other-turn")

        self.assertIn(
            "run-verification",
            split_runner_command(
                second["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )
        self.assertEqual(self.run_rewritten(second).returncode, 0)
        states = list(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        self.assertEqual(len(states), 2)
        self.workspace = original_workspace

    def test_raw_argv_request_remains_supported(self) -> None:
        self.initialize_named_workspace()

        payload = self.verify_gate(
            [self.verification_argv()], evidence_ids=["E1"]
        )

        self.assertIn(
            "run-verification",
            split_runner_command(
                payload["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )
        self.assertEqual(self.run_rewritten(payload).returncode, 0)

    def test_named_broad_definition_uses_existing_shard_runner_path(self) -> None:
        tests = self.workspace / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text("", encoding="utf-8")
        for name in ("alpha", "beta"):
            (tests / f"test_{name}.py").write_text(
                "import unittest\n\n"
                f"class {name.title()}Tests(unittest.TestCase):\n"
                "    def test_pass(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\ntests/__pycache__/\n", encoding="utf-8"
        )
        executable = sys.executable
        parent = [
            executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-q",
        ]
        target = self.workspace / ".click" / "evidence-shards.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "version": 2,
                    "verifications": [
                        {
                            "id": "full-suite",
                            "label": "Full suite",
                            "class": "broad",
                            "checks": [parent],
                        }
                    ],
                    "entries": [
                        {
                            "verification_id": "full-suite",
                            "inventory": ["tests/test_*.py"],
                            "shards": [
                                {
                                    "id": name,
                                    "checks": [
                                        [
                                            executable,
                                            "-m",
                                            "unittest",
                                            f"tests.test_{name}",
                                            "-q",
                                        ]
                                    ],
                                    "covers": [f"tests/test_{name}.py"],
                                }
                                for name in ("alpha", "beta")
                            ],
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.initialize_git(
            ".gitignore",
            "tests/__init__.py",
            "tests/test_alpha.py",
            "tests/test_beta.py",
            ".click/evidence-shards.json",
        )

        payload = self.verify_names(["full-suite"])
        result = self.run_rewritten(payload)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1/2", result.stdout)
        self.assertIn("2/2", result.stdout)
        state = self.state()
        plan = state["verification"]["incremental_plan"]
        self.assertEqual(plan["total_source_count"], 2)
        self.assertNotIn(
            CLICK_EVIDENCE.evidence_key("full-suite"),
            state["evidence_state"]["sources"],
        )

    def test_distinct_names_with_the_same_argv_are_not_merged(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        argv = self.verification_argv()
        self.write_catalog(
            [
                self.definition(
                    verification_id="auth-unit",
                    label="Auth unit",
                    argv=argv,
                ),
                self.definition(
                    verification_id="auth-repeat",
                    label="Auth repeat",
                    argv=argv,
                ),
            ]
        )
        self.initialize_git(
            ".gitignore",
            "verification_fixture.py",
            ".click/evidence-shards.json",
        )

        payload = self.verify_names(["auth-unit", "auth-repeat"])
        result = self.run_rewritten(payload)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1/2", result.stdout)
        self.assertIn("2/2", result.stdout)
        sources = self.state()["evidence_state"]["sources"]
        self.assertIn(CLICK_EVIDENCE.evidence_key("auth-unit"), sources)
        self.assertIn(CLICK_EVIDENCE.evidence_key("auth-repeat"), sources)
        self.assertEqual(len(sources), 2)

    def test_unknown_duplicate_and_shell_like_names_are_rejected(self) -> None:
        self.initialize_named_workspace()

        for names, expected in (
            (["missing"], "Unknown committed verification name"),
            (["auth-unit", "auth-unit"], "must be unique"),
            (["auth-unit;touch-pwned"], "must be unique"),
        ):
            with self.subTest(names=names):
                payload = self.verify_names(names)
                output = payload["hookSpecificOutput"]
                self.assertEqual(output["permissionDecision"], "deny")
                self.assertIn(expected, output["permissionDecisionReason"])
        self.assertFalse((self.workspace / "pwned").exists())

        mixed_request = {
            "version": 2,
            "workdir": str(self.workspace),
            "names": ["auth-unit"],
            "checks": [
                {
                    "evidence_id": "other",
                    "argv": self.verification_argv(),
                    "class": "targeted",
                }
            ],
        }
        mixed = self.pre_tool(
            "Bash",
            "click-gate verify "
            + shlex.quote(json.dumps(mixed_request)),
            "turn-1",
            tool_use_id="named-verification-mixed-shapes",
        )
        assert mixed is not None
        self.assertEqual(
            mixed["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "either `names` or `checks`",
            mixed["hookSpecificOutput"]["permissionDecisionReason"],
        )

        self.write_catalog(
            [
                self.definition(
                    verification_id="unsafe-command",
                    label="Unsafe command",
                    argv=["sh", "-c", "touch pwned"],
                )
            ]
        )
        self.commit_all("add rejected command definition")
        payload = self.verify_names(["unsafe-command"], "turn-2")
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "cannot invoke a shell interpreter",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )
        self.assertFalse((self.workspace / "pwned").exists())

    def test_guarded_approval_and_one_use_runner_boundaries_remain(self) -> None:
        self.initialize_named_workspace()
        contract = self.contract()
        contract["verification"]["evidence"][0]["id"] = "auth-unit"
        contract["verification"]["done_when"][0][
            "primary_evidence"
        ] = "auth-unit"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")

        before_approval = self.verify_names(["auth-unit"], "turn-1")
        self.assertEqual(
            before_approval["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "Pass the approved Click execution contract",
            before_approval["hookSpecificOutput"]["permissionDecisionReason"],
        )

        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        approved = self.verify_names(["auth-unit"], "turn-2")
        first = self.run_rewritten(approved)
        replay = self.run_rewritten(approved)

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(replay.returncode, 2)
        self.assertTrue(
            "replay is blocked" in replay.stderr
            or "no longer authorized" in replay.stderr
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
