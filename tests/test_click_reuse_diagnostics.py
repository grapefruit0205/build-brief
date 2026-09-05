from __future__ import annotations

import copy
import json
import unittest

from hooks import click_incremental, click_reuse_diagnostics


SOURCE = "a" * 64
CHECK = "b" * 64


class ClickReuseDiagnosticsTests(unittest.TestCase):
    def facts(
        self, *mismatches: tuple[str, str], baseline: str = "present"
    ) -> dict[str, object]:
        if baseline == "present":
            source = {
                "status": "stale",
                "verified_at": 1,
                "verified_revision": 1,
                "verified_check_digest": CHECK,
                "last_exit_code": 0,
            }
        elif baseline == "failed":
            source = {"status": "failed", "last_exit_code": 1}
        else:
            source = {"status": "ready", "verified_revision": -1}
        facts = click_reuse_diagnostics.begin(source)
        for condition, reason in mismatches:
            click_reuse_diagnostics.record(
                facts, condition, False, reason_code=reason
            )
        return facts

    def decision(
        self,
        *,
        source: str = SOURCE,
        reason: str = "environment-binding-changed",
        diagnostic: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return click_incremental.decision(
            source_key=source,
            decision="run",
            reason_code=reason,
            current_revision=2,
            previous_revision=1,
            check_digest=CHECK,
            authority_source="runner",
            reuse_diagnostic=diagnostic,
        )

    def batch(
        self,
        *,
        suffix: str,
        diagnostic: dict[str, object],
        outcome: str,
        duration_ms: float | None,
    ) -> dict[str, object]:
        source = suffix * 64
        plan = click_incremental.build_plan(
            [self.decision(
                source=source,
                reason=str(diagnostic["primary_reason_code"]),
                diagnostic=diagnostic,
            )],
            current_revision=2,
            planned_at=10,
        )
        state: dict[str, object] = {}
        click_incremental.store_batch(
            state,
            click_incremental.new_batch(
                plan,
                batch_id=suffix * 32,
                revision=2,
                prepared_ms=1,
            ),
        )
        if outcome in {"passed", "failed"}:
            click_incremental.mark_started(state, source)
            click_incremental.mark_completed(
                state,
                source,
                status=outcome,
                reason=f"command-{outcome}",
                duration_ms=duration_ms,
            )
            click_incremental.record_execution(
                state,
                {source: duration_ms},
                source_results={
                    source: {
                        "status": outcome,
                        "started": True,
                        "completed": True,
                        "reason_code": f"command-{outcome}",
                    }
                },
                exit_code=0 if outcome == "passed" else 1,
                runner_duration_ms=duration_ms,
            )
        elif outcome == "interrupted":
            click_incremental.mark_started(state, source)
            click_incremental.interrupt_batch(state)
        elif outcome == "not-run":
            click_incremental.reject_batch(state)
        batch = click_incremental.current_batch(state)
        assert batch is not None
        return batch

    def test_control_defaults_on_and_never_claims_execution_authority(self) -> None:
        verification: dict[str, object] = {}
        self.assertEqual(click_reuse_diagnostics.mode(verification), "on")
        self.assertEqual(
            click_reuse_diagnostics.projection(verification),
            {
                "mode": "on",
                "enabled": True,
                "authoritative": False,
                "affects_execution": False,
            },
        )
        click_reuse_diagnostics.set_mode(verification, "off", updated_at=4)
        self.assertFalse(click_reuse_diagnostics.enabled(verification))

    def test_frozen_diagnostic_keeps_all_mismatches_and_uninspected_checks(self) -> None:
        facts = self.facts(
            ("environment-binding", "environment-binding-changed"),
            ("executable-binding", "executable-binding-changed"),
        )
        click_reuse_diagnostics.record(facts, "check-binding", True)
        diagnostic = click_reuse_diagnostics.freeze(
            facts,
            decision="run",
            primary_reason_code="executable-binding-changed",
        )

        self.assertTrue(click_reuse_diagnostics.diagnostic_is_valid(diagnostic))
        checks = {item["condition"]: item for item in diagnostic["checks"]}
        self.assertEqual(checks["check-binding"]["status"], "matched")
        self.assertEqual(
            checks["environment-binding"],
            {
                "condition": "environment-binding",
                "status": "mismatched",
                "reason_code": "environment-binding-changed",
            },
        )
        self.assertEqual(
            checks["observed-inputs-unchanged"]["status"], "not-evaluated"
        )
        self.assertEqual(diagnostic["candidate_evaluation"], "not-evaluated")

    def test_first_run_and_previous_failure_are_distinct_causes(self) -> None:
        first_run = click_reuse_diagnostics.freeze(
            self.facts(baseline="absent"),
            decision="run",
            primary_reason_code="no-passing-evidence",
        )
        previous_failure = click_reuse_diagnostics.freeze(
            self.facts(baseline="failed"),
            decision="run",
            primary_reason_code="previous-verification-failed",
        )

        self.assertEqual(first_run["baseline_status"], "absent")
        self.assertEqual(previous_failure["baseline_status"], "failed")
        self.assertNotEqual(
            first_run["primary_reason_code"],
            previous_failure["primary_reason_code"],
        )

    def test_diagnostics_on_and_off_leave_the_execution_plan_unchanged(self) -> None:
        facts = self.facts(
            ("environment-binding", "environment-binding-changed")
        )
        diagnostic = click_reuse_diagnostics.freeze(
            facts,
            decision="run",
            primary_reason_code="environment-binding-changed",
        )
        without = click_incremental.build_plan(
            [self.decision()], current_revision=2, planned_at=1
        )
        with_diagnostics = click_incremental.build_plan(
            [self.decision(diagnostic=diagnostic)],
            current_revision=2,
            planned_at=1,
        )

        self.assertEqual(click_incremental.keys_to_execute(without), {SOURCE})
        self.assertEqual(
            click_incremental.keys_to_execute(with_diagnostics), {SOURCE}
        )
        self.assertEqual(
            {
                key: value
                for key, value in with_diagnostics["decisions"][0].items()
                if key != "reuse_diagnostic"
            },
            without["decisions"][0],
        )
        self.assertEqual(without["version"], 2)
        self.assertEqual(with_diagnostics["version"], 3)

    def test_aggregate_deduplicates_sources_and_does_not_sum_overlapping_causes(self) -> None:
        multi = click_reuse_diagnostics.freeze(
            self.facts(
                ("environment-binding", "environment-binding-changed"),
                ("executable-binding", "executable-binding-changed"),
            ),
            decision="run",
            primary_reason_code="executable-binding-changed",
        )
        passed = self.batch(
            suffix="1", diagnostic=multi, outcome="passed", duration_ms=12.5
        )
        failed = self.batch(
            suffix="2", diagnostic=multi, outcome="failed", duration_ms=3.5
        )
        interrupted = self.batch(
            suffix="3", diagnostic=multi, outcome="interrupted", duration_ms=None
        )
        not_run = self.batch(
            suffix="4", diagnostic=multi, outcome="not-run", duration_ms=None
        )

        aggregate = click_reuse_diagnostics.aggregate(
            [passed, copy.deepcopy(passed), failed, interrupted, not_run]
        )

        self.assertTrue(click_reuse_diagnostics.aggregate_is_valid(aggregate))
        self.assertEqual(aggregate["diagnosed_source_count"], 4)
        self.assertEqual(aggregate["deduplicated"]["baseline_present_count"], 4)
        self.assertEqual(aggregate["deduplicated"]["passed_source_count"], 1)
        self.assertEqual(
            aggregate["deduplicated"]["observed_passed_execution_ms"], 12.5
        )
        self.assertEqual(aggregate["deduplicated"]["failed_source_count"], 1)
        self.assertEqual(aggregate["deduplicated"]["interrupted_source_count"], 1)
        self.assertEqual(aggregate["deduplicated"]["not_run_source_count"], 1)
        self.assertEqual(aggregate["deduplicated"]["incomplete_measurement_count"], 1)
        self.assertTrue(aggregate["cause_costs_overlap"])
        self.assertEqual(len(aggregate["causes"]), 2)
        self.assertTrue(
            all(
                cause["observed_passed_execution_ms"] == 12.5
                and cause["multiple_cause_source_count"] == 4
                for cause in aggregate["causes"]
            )
        )

    def test_unknown_duration_is_not_zero_but_measured_zero_is_preserved(self) -> None:
        diagnostic = click_reuse_diagnostics.freeze(
            self.facts(("environment-binding", "environment-binding-changed")),
            decision="run",
            primary_reason_code="environment-binding-changed",
        )
        interrupted = self.batch(
            suffix="5", diagnostic=diagnostic, outcome="interrupted", duration_ms=None
        )
        unknown = click_reuse_diagnostics.aggregate([interrupted])
        self.assertIsNone(
            unknown["causes"][0]["observed_passed_execution_ms"]
        )

        zero = self.batch(
            suffix="6", diagnostic=diagnostic, outcome="passed", duration_ms=0
        )
        measured = click_reuse_diagnostics.aggregate([zero])
        self.assertEqual(
            measured["causes"][0]["observed_passed_execution_ms"], 0
        )
        self.assertEqual(
            measured["causes"][0]["measured_passed_source_count"], 1
        )

    def test_rejected_reuse_plan_is_not_counted_as_actual_reuse(self) -> None:
        diagnostic = click_reuse_diagnostics.freeze(
            self.facts(),
            decision="reuse-exact",
            primary_reason_code="same-revision-receipt-current",
        )
        plan = click_incremental.build_plan(
            [
                click_incremental.decision(
                    source_key=SOURCE,
                    decision="reuse-exact",
                    reason_code="same-revision-receipt-current",
                    current_revision=2,
                    previous_revision=2,
                    check_digest=CHECK,
                    authority_source="exact-receipt",
                    reuse_diagnostic=diagnostic,
                )
            ],
            current_revision=2,
            planned_at=1,
        )
        state: dict[str, object] = {}
        click_incremental.store_batch(
            state,
            click_incremental.new_batch(
                plan,
                batch_id="7" * 32,
                revision=2,
                prepared_ms=1,
            ),
        )
        self.assertTrue(click_incremental.reject_batch(state))

        aggregate = click_reuse_diagnostics.aggregate(
            click_incremental.batch_history(state)
        )
        self.assertEqual(aggregate["reused_source_count"], 0)
        self.assertEqual(aggregate["unapplied_reuse_source_count"], 1)

    def test_diagnostics_store_no_raw_command_environment_token_or_path(self) -> None:
        diagnostic = click_reuse_diagnostics.freeze(
            self.facts(("environment-binding", "environment-binding-changed")),
            decision="run",
            primary_reason_code="environment-binding-changed",
        )
        encoded = json.dumps(diagnostic, sort_keys=True)
        for forbidden in (
            "raw_argv",
            "ACCESS_TOKEN",
            "super-secret",
            "/home/private/project",
            "python3 -m unittest",
        ):
            self.assertNotIn(forbidden, encoded)


if __name__ == "__main__":
    unittest.main()
