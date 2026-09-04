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
        self.assertEqual(plan["executed_duration_ms"], 0)
        self.assertEqual(click_incremental.keys_to_execute(plan), {"a" * 64, "e" * 64})

    def test_measured_execution_updates_time_without_changing_decisions(self) -> None:
        plan = click_incremental.build_plan(
            [
                self.item("a", "run", "observed-input-changed", "runner"),
                self.item(
                    "b",
                    "reuse-exact",
                    "same-revision-receipt-current",
                    "exact-receipt",
                    avoided=50,
                ),
            ],
            current_revision=12,
            planned_at=1,
        )
        verification: dict[str, object] = {}
        click_incremental.store_plan(verification, plan)

        recorded = click_incremental.record_execution(
            verification, {"a" * 64: 125}
        )

        self.assertTrue(recorded)
        stored = click_incremental.current_plan(verification)
        assert stored is not None
        self.assertEqual(stored["executed_duration_ms"], 125)
        self.assertEqual(
            [item["decision"] for item in stored["decisions"]],
            ["run", "reuse-exact"],
        )
        summary = click_incremental.summary(verification)
        self.assertEqual(summary["executed_source_count"], 1)
        self.assertEqual(summary["authoritative_reuse_count"], 1)
        self.assertEqual(summary["executed_duration_ms"], 125)
        self.assertEqual(summary["estimated_avoided_ms"], 50)
        self.assertNotIn("actual_saved_ms", summary)
        self.assertFalse(any("candidate" in field for field in summary))

    def test_history_drops_oldest_by_age_count_and_size(self) -> None:
        verification: dict[str, object] = {}
        for revision in range(1, 1_006):
            item = click_incremental.decision(
                source_key=f"{revision:064x}",
                decision="run",
                reason_code="no-passing-evidence",
                current_revision=revision,
                previous_revision=revision - 1,
                check_digest="f" * 64,
                authority_source="runner",
            )
            plan = click_incremental.build_plan(
                [item], current_revision=revision, planned_at=revision
            )
            click_incremental.append_plan_history(verification, plan)
        history = click_incremental.current_history(verification)
        self.assertEqual(len(history), click_incremental.MAX_HISTORY_EVENTS)
        self.assertEqual(history[0]["timestamp"], 6)
        self.assertEqual(history[-1]["timestamp"], 1_005)

        recent = click_incremental.prune_history(
            history,
            now=1_005,
            max_events=1_000,
            max_age_seconds=10,
            max_bytes=click_incremental.MAX_HISTORY_BYTES,
        )
        self.assertEqual(recent[0]["timestamp"], 995)
        size_limited = click_incremental.prune_history(
            recent,
            now=1_005,
            max_events=1_000,
            max_age_seconds=10,
            max_bytes=400,
        )
        self.assertLess(len(size_limited), len(recent))
        self.assertEqual(size_limited[-1]["timestamp"], 1_005)

    def test_history_contains_only_bounded_aggregate_fields(self) -> None:
        plan = click_incremental.build_plan(
            [
                self.item(
                    "a",
                    "reuse-safe-change",
                    "safe-change-policy-covered",
                    "repository-safe-change-policy",
                    avoided=40,
                )
            ],
            current_revision=12,
            planned_at=100,
        )
        verification: dict[str, object] = {}
        click_incremental.append_plan_history(verification, plan)
        history = click_incremental.current_history(verification)

        self.assertTrue(click_incremental.history_is_valid(history))
        self.assertEqual(
            set(history[0]),
            {
                "event",
                "source_key",
                "decision",
                "reason",
                "current_revision",
                "previous_revision",
                "estimated_avoided_ms",
                "timestamp",
            },
        )
        encoded = json.dumps(history, sort_keys=True)
        for forbidden in ("argv", "/home/", "prompt", "token", "environment"):
            self.assertNotIn(forbidden, encoded)

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
