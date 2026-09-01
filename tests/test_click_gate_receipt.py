from __future__ import annotations

from click_gate_test_support import (
    ClickGateTestCase,
    json,
    shlex,
    split_runner_command,
    unittest,
)


class ClickGateReceiptTests(ClickGateTestCase):
    def test_export_uses_bash_workdir_for_final_workspace(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        # Codex may keep session identity at the task root while Bash executes
        # the rewritten command in its explicit workdir.
        host_cwd = self.workspace.parent / "host-cwd"
        host_cwd.mkdir()
        self.base_event["cwd"] = str(host_cwd)
        self.approve_contract()

        batch = {
            "version": 2,
            "checks": [
                {
                    "evidence_id": "E1",
                    "argv": self.verification_argv(),
                    "class": "targeted",
                }
            ],
        }
        verification = self.tool_hook(
            "pre-tool",
            "Bash",
            {
                "command": (
                    f"click-gate verify {shlex.quote(json.dumps(batch))}"
                ),
                "workdir": str(self.workspace),
            },
            turn_id="turn-2",
            tool_use_id="verification-tool",
        )
        self.assertIsNotNone(verification)
        assert verification is not None
        verified = self.run_rewritten(verification)
        self.assertEqual(verified.returncode, 0, verified.stderr)

        export = self.tool_hook(
            "pre-tool",
            "Bash",
            {
                "command": "click-gate receipt export",
                "workdir": str(self.workspace),
            },
            turn_id="turn-2",
            tool_use_id="receipt-tool",
        )
        self.assertIsNotNone(export)
        assert export is not None
        exported = self.run_rewritten(export)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        envelope = json.loads(exported.stdout)
        self.assertEqual(
            envelope["receipt"]["execution"]["workspace"]["assurance"],
            "git-protected-tree",
        )

    def test_export_requires_completion_then_verify_runs_offline(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        self.approve_contract()

        blocked = self.pre_tool("Bash", "click-gate receipt export", "turn-2")
        self.assertEqual(
            blocked["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "every declared evidence source",
            blocked["hookSpecificOutput"]["permissionDecisionReason"],
        )

        verification = self.verify_gate([self.verification_argv()], "turn-2")
        verified = self.run_rewritten(verification)
        self.assertEqual(verified.returncode, 0, verified.stderr)

        export = self.pre_tool("Bash", "click-gate receipt export", "turn-2")
        self.assertIn(
            "run-receipt-export",
            split_runner_command(export["hookSpecificOutput"]["updatedInput"]["command"]),
        )
        exported = self.run_rewritten(export)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        envelope = json.loads(exported.stdout)
        self.assertEqual(envelope["assurance"], "unsigned-integrity-only")
        self.assertEqual(
            envelope["receipt"]["contract"]["approved_turn_id"], "turn-2"
        )
        self.assertEqual(
            envelope["receipt"]["capabilities"][-1]["capability"],
            "verification",
        )
        self.assertRegex(
            envelope["receipt"]["evidence"][0]["executable_digest"],
            r"^[0-9a-f]{64}$",
        )

        receipt_path = self.workspace / "completion-receipt.json"
        receipt_path.write_text(json.dumps(envelope), encoding="utf-8")
        verify = self.pre_tool(
            "Bash",
            f"click-gate receipt verify {receipt_path}",
            "turn-2",
        )
        checked = self.run_rewritten(verify)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        report = json.loads(checked.stdout)
        self.assertEqual(report["status"], "valid")
        self.assertEqual(report["assurance"], "unsigned-integrity-only")

        envelope["receipt_digest"] = "0" * 64
        receipt_path.write_text(json.dumps(envelope), encoding="utf-8")
        invalid = self.pre_tool(
            "Bash",
            f"click-gate receipt verify {receipt_path}",
            "turn-2",
        )
        rejected = self.run_rewritten(invalid)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("does not match", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
