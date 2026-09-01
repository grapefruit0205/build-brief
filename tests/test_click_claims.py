from __future__ import annotations

import copy
import unittest

from hooks import click_claims


def _digest(character: str) -> str:
    return character * 64


class ClickClaimLedgerTests(unittest.TestCase):
    def state(self) -> dict[str, object]:
        return {
            "contract_digest": _digest("a"),
            "capability_ledger": click_claims.fresh_state(),
        }

    def test_one_use_claim_commits_without_persisting_token_digest(self) -> None:
        state = self.state()
        claim_digest, error = click_claims.record_claim(
            state,
            capability="verification",
            claim_mode="one-use-runner",
            request_digest=_digest("b"),
            token_digest=_digest("c"),
            mutation_revision=2,
            claimed_at=10,
        )

        self.assertEqual(error, "")
        self.assertRegex(claim_digest, r"^[0-9a-f]{64}$")
        self.assertNotIn(_digest("c"), repr(state["capability_ledger"]))
        self.assertTrue(
            click_claims.complete_claim(
                state,
                capability="verification",
                claim_mode="one-use-runner",
                request_digest=_digest("b"),
                mutation_revision=2,
                exit_code=0,
                completed_at=11,
            )
        )
        self.assertFalse(
            click_claims.complete_claim(
                state,
                capability="verification",
                claim_mode="one-use-runner",
                request_digest=_digest("b"),
                mutation_revision=2,
                exit_code=0,
                completed_at=12,
            )
        )

    def test_host_tool_use_is_distinct_and_can_record_observation(self) -> None:
        state = self.state()
        binding = click_claims.host_binding_digest("tool-1")
        _, error = click_claims.record_claim(
            state,
            capability="mutation",
            claim_mode="host-tool-use",
            request_digest=_digest("d"),
            binding_digest=binding,
            mutation_revision=1,
            claimed_at=3,
        )
        self.assertEqual(error, "")
        self.assertTrue(
            click_claims.complete_claim(
                state,
                capability="mutation",
                claim_mode="host-tool-use",
                request_digest=_digest("d"),
                binding_digest=binding,
                mutation_revision=1,
                exit_code=None,
                completed_at=4,
            )
        )
        entries, error = click_claims.receipt_entries(state)
        self.assertEqual(error, "")
        assert entries is not None
        self.assertEqual(entries[0]["result"]["status"], "observed")

    def test_backfilled_or_active_history_cannot_be_exported(self) -> None:
        state = {"contract_digest": _digest("a")}
        _, error = click_claims.record_claim(
            state,
            capability="observation",
            claim_mode="one-use-runner",
            request_digest=_digest("e"),
            token_digest=_digest("f"),
            mutation_revision=0,
            claimed_at=1,
        )
        self.assertEqual(error, "")
        entries, error = click_claims.receipt_entries(state)
        self.assertIsNone(entries)
        self.assertIn("predates", error)

    def test_unknown_fields_and_duplicate_claim_digests_fail_closed(self) -> None:
        state = self.state()
        for request in (_digest("1"), _digest("2")):
            _, error = click_claims.record_claim(
                state,
                capability="verification",
                claim_mode="one-use-runner",
                request_digest=request,
                token_digest=_digest("3"),
                mutation_revision=0,
                claimed_at=1,
            )
            self.assertEqual(error, "")
        ledger = copy.deepcopy(state["capability_ledger"])
        ledger["entries"][1]["claim_digest"] = ledger["entries"][0]["claim_digest"]
        normalized, error = click_claims.validate_ledger(ledger)
        self.assertIsNone(normalized)
        self.assertIn("unique", error)


if __name__ == "__main__":
    unittest.main()
