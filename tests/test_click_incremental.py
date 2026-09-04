from __future__ import annotations

import json
import unittest

from hooks import click_incremental


class ClickIncrementalPlanTests(unittest.TestCase):
    def item(
        self,
        suffix: str,
        selected: str,
        reason: str,
        authority: str,
        *,
        avoided: int = 0,
    ) -> dict[str, object]:
        return click_incremental.decision(
            source_key=suffix * 64,
            decision=selected,
            reason_code=reason,
            current_revision=12,
            previous_revision=11,
            check_digest=("f" if suffix != "f" else "e") * 64,
            authority_source=authority,
            estimated_avoided_ms=avoided,
        )

    def test_canonical_plan_drives_only_non_reused_sources_into_runner(self) -> None:
        plan = click_incremental.build_plan(
            [
                self.item(
                    "a",
                    "run",
                    "observed-input-changed",
                    "runner",
                ),
                self.item(
                    "b",
                    "reuse-exact",
                    "same-revision-receipt-current",
                    "exact-receipt",
                    avoided=800,
                ),
                self.item(
                    "c",
                    "reuse-dependency",
                    "observed-dependencies-unchanged",
                    "runtime-dependency-observation",
                    avoided=1_200,
                ),
                self.item(
                    "d",
                    "reuse-safe-change",
                    "safe-change-policy-covered",
                    "repository-safe-change-policy",
                    avoided=400,
                ),
                self.item(
                    "e",
                    "not-evaluable",
                    "observer-incomplete",
                    "none",
                ),
            ],
            current_revision=12,
            planned_at=1,
        )

        self.assertTrue(click_incremental.plan_is_valid(plan))
        self.assertEqual(plan["total_source_count"], 5)
        self.assertEqual(plan["executed_source_count"], 2)
        self.assertEqual(plan["authoritative_reuse_count"], 3)
        self.assertEqual(plan["exact_reuse_count"], 1)
        self.assertEqual(plan["dependency_reuse_count"], 1)
        self.assertEqual(plan["safe_change_reuse_count"], 1)
        self.assertEqual(plan["estimated_avoided_ms"], 2_400)
        self.assertEqual(click_incremental.keys_to_execute(plan), {"a" * 64, "e" * 64})

    def test_plan_contains_no_argv_paths_or_natural_language_authority(self) -> None:
        plan = click_incremental.build_plan(
            [
                self.item(
                    "a",
                    "reuse-exact",
                    "same-revision-receipt-current",
                    "exact-receipt",
                )
            ],
            current_revision=12,
            planned_at=1,
        )
        encoded = json.dumps(plan, sort_keys=True)

        for forbidden in ("argv", "/home/", "prompt", "token", "src/auth/token.py"):
            self.assertNotIn(forbidden, encoded)

    def test_non_reuse_decision_cannot_claim_avoided_time_or_reuse_authority(self) -> None:
        with self.assertRaises(ValueError):
            click_incremental.decision(
                source_key="a" * 64,
                decision="run",
                reason_code="observed-input-changed",
                current_revision=1,
                previous_revision=0,
                check_digest="b" * 64,
                authority_source="exact-receipt",
                estimated_avoided_ms=1,
            )


if __name__ == "__main__":
    unittest.main()
