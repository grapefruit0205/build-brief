from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from hooks import (
    click_claims,
    click_evidence,
    click_host_coverage,
    click_receipt_runtime,
)


def _digest(character: str) -> str:
    return character * 64


class ClickReceiptRuntimeTests(unittest.TestCase):
    def completed_state(self, root: Path) -> tuple[dict[str, object], dict[str, object]]:
        contract = {
            "verification": {
                "evidence": [
                    {"id": "E1", "kind": "argv", "description": "tests"}
                ]
            }
        }
        evidence_state = click_evidence.fresh_state(contract)
        source = next(iter(evidence_state["sources"].values()))
        coverage = click_host_coverage.receipt("codex")
        assert coverage is not None
        source.update(
            {
                "status": "passed",
                "verified_revision": 2,
                "last_exit_code": 0,
                "verified_contract_digest": _digest("a"),
                "verified_check_digest": _digest("b"),
                "verified_root": str(root.resolve()),
                "verified_tree_digest": _digest("c"),
                "verified_environment_digest": _digest("d"),
                "verified_executable_digest": _digest("e"),
                "verified_host_coverage": coverage,
                "verified_at": 20,
            }
        )
        state: dict[str, object] = {
            "state_schema_version": 2,
            "status": "approved",
            "contract_id": "ctr_0123456789abcdef0123456789abcdef",
            "contract_digest": _digest("a"),
            "staged_turn_id": "turn-stage",
            "approved_turn_id": "turn-approve",
            "verification": {"status": "passed", "mutation_revision": 2},
            "evidence_state": evidence_state,
            "capability_ledger": click_claims.fresh_state(),
            "mutation": {"status": "passed"},
            "observations": {"entries": {}},
            "service": {"status": "idle"},
        }
        _, error = click_claims.record_claim(
            state,
            capability="verification",
            claim_mode="one-use-runner",
            request_digest=_digest("f"),
            token_digest=_digest("1"),
            mutation_revision=2,
            claimed_at=18,
        )
        self.assertEqual(error, "")
        self.assertTrue(
            click_claims.complete_claim(
                state,
                capability="verification",
                claim_mode="one-use-runner",
                request_digest=_digest("f"),
                mutation_revision=2,
                exit_code=0,
                completed_at=19,
            )
        )
        return state, coverage

    def test_build_binds_final_state_without_exporting_root_or_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, coverage = self.completed_state(root)
            envelope, error = click_receipt_runtime.build_envelope(
                state,
                workspace_snapshot={"root": str(root), "digest": _digest("c")},
                host_coverage=coverage,
                expected_contract_schema_version=2,
            )

            self.assertEqual(error, "")
            assert envelope is not None
            rendered = click_receipt_runtime.render_envelope(envelope)
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("runner_token", rendered)
            receipt = envelope["receipt"]
            self.assertEqual(receipt["execution"]["mutation_revision"], 2)
            self.assertEqual(receipt["capabilities"][0]["capability"], "verification")
            self.assertEqual(receipt["evidence"][0]["executable_digest"], _digest("e"))

    def test_workspace_drift_or_active_claim_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, coverage = self.completed_state(root)
            envelope, error = click_receipt_runtime.build_envelope(
                state,
                workspace_snapshot={"root": str(root), "digest": _digest("9")},
                host_coverage=coverage,
                expected_contract_schema_version=2,
            )
            self.assertIsNone(envelope)
            self.assertIn("drifted", error)

            active = copy.deepcopy(state)
            active["mutation"] = {"status": "running"}
            envelope, error = click_receipt_runtime.build_envelope(
                active,
                workspace_snapshot={"root": str(root), "digest": _digest("c")},
                host_coverage=coverage,
                expected_contract_schema_version=2,
            )
            self.assertIsNone(envelope)
            self.assertIn("active", error)

    def test_verify_file_is_offline_strict_and_unsigned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, coverage = self.completed_state(root)
            envelope, error = click_receipt_runtime.build_envelope(
                state,
                workspace_snapshot={"root": str(root), "digest": _digest("c")},
                host_coverage=coverage,
                expected_contract_schema_version=2,
            )
            self.assertEqual(error, "")
            assert envelope is not None
            path = root / "receipt.json"
            path.write_text(json.dumps(envelope), encoding="utf-8")

            report, error = click_receipt_runtime.verify_file(path)
            self.assertEqual(error, "")
            assert report is not None
            self.assertEqual(report["status"], "valid")
            self.assertEqual(report["assurance"], "unsigned-integrity-only")

            envelope["receipt_digest"] = _digest("0")
            path.write_text(json.dumps(envelope), encoding="utf-8")
            report, error = click_receipt_runtime.verify_file(path)
            self.assertIsNone(report)
            self.assertIn("does not match", error)


if __name__ == "__main__":
    unittest.main()
