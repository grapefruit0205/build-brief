from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from hooks import (
    click_dependency_cache,
    click_dependency_trace,
    click_shadow_intelligence,
)


EVIDENCE_KEY = "a" * 64
CHECK_DIGEST = "b" * 64
ENVIRONMENT_DIGEST = "c" * 64
EXECUTABLE_DIGEST = "d" * 64
HOST_DIGEST = "e" * 64
BACKEND_DIGEST = "f" * 64


class ClickShadowIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name).resolve()
        (self.workspace / "src").mkdir()
        (self.workspace / "src" / "input.py").write_text(
            "PRIVATE-CONTENT\n", encoding="utf-8"
        )

    def record(
        self,
        *,
        inputs: list[dict[str, object]] | None = None,
        revision: int = 1,
        exit_duration: int = 1200,
        external: int = 0,
        backend_digest: str = BACKEND_DIGEST,
    ) -> dict[str, object]:
        return click_dependency_cache.shadow_observer_record(
            evidence_key=EVIDENCE_KEY,
            check_digest=CHECK_DIGEST,
            mutation_revision=revision,
            backend_name="strace",
            backend_version="6.8",
            backend_digest=backend_digest,
            inputs=inputs
            or [
                {
                    "path": "src/input.py",
                    "kind": "file",
                    "operations": ["read"],
                }
            ],
            external_input_count=external,
            command_duration_ms=exit_duration,
            observer_overhead_ms=12,
        )

    def baseline(self, record: dict[str, object] | None = None) -> dict[str, object]:
        baseline = click_shadow_intelligence.build_baseline(
            record or self.record(),
            workspace=self.workspace,
            environment_digest=ENVIRONMENT_DIGEST,
            executable_digest=EXECUTABLE_DIGEST,
            host_coverage_digest=HOST_DIGEST,
        )
        self.assertIsNotNone(baseline)
        assert baseline is not None
        return baseline

    def prediction(
        self,
        baseline: dict[str, object] | None = None,
        **changes: object,
    ) -> dict[str, object]:
        arguments = {
            "workspace": self.workspace,
            "evidence_key": EVIDENCE_KEY,
            "check_digest": CHECK_DIGEST,
            "mutation_revision": 2,
            "environment_digest": ENVIRONMENT_DIGEST,
            "executable_digest": EXECUTABLE_DIGEST,
            "host_coverage_digest": HOST_DIGEST,
            "prepared_at": 10,
        }
        arguments.update(changes)
        return click_shadow_intelligence.predict(
            self.baseline() if baseline is None else baseline,
            **arguments,
        )

    def test_baseline_is_canonical_content_free_and_non_authoritative(self) -> None:
        baseline = self.baseline(self.record(external=2))

        self.assertTrue(click_shadow_intelligence.baseline_is_valid(baseline))
        self.assertFalse(baseline["authoritative"])
        self.assertFalse(baseline["reuse_authorized"])
        self.assertEqual(baseline["limitations"], ["external-inputs-unmodeled"])
        encoded = json.dumps(baseline, sort_keys=True)
        self.assertNotIn("PRIVATE-CONTENT", encoded)
        self.assertNotIn(str(self.workspace), encoded)

    def test_first_run_is_not_evaluable_without_a_baseline(self) -> None:
        prediction = click_shadow_intelligence.predict(
            {},
            workspace=self.workspace,
            evidence_key=EVIDENCE_KEY,
            check_digest=CHECK_DIGEST,
            mutation_revision=1,
            environment_digest=ENVIRONMENT_DIGEST,
            executable_digest=EXECUTABLE_DIGEST,
            host_coverage_digest=HOST_DIGEST,
            prepared_at=10,
        )

        self.assertTrue(click_shadow_intelligence.prediction_is_valid(prediction))
        self.assertEqual(prediction["decision"], "not-evaluable")
        self.assertEqual(prediction["reason"], "no-baseline")

    def test_unchanged_inputs_are_only_a_shadow_reuse_candidate(self) -> None:
        prediction = self.prediction(self.baseline(self.record(external=3)))

        self.assertEqual(prediction["decision"], "reuse-candidate")
        self.assertEqual(prediction["reason"], "observed-inputs-unchanged")
        self.assertEqual(prediction["limitations"], ["external-inputs-unmodeled"])
        self.assertFalse(prediction["authoritative"])
        self.assertFalse(prediction["reuse_authorized"])

    def test_file_change_requires_a_shadow_rerun(self) -> None:
        baseline = self.baseline()
        (self.workspace / "src" / "input.py").write_text("changed\n", encoding="utf-8")

        prediction = self.prediction(baseline)

        self.assertEqual(prediction["decision"], "rerun-required")
        self.assertEqual(prediction["reason"], "observed-input-changed")
        self.assertEqual(prediction["changed_inputs"], ["src/input.py"])

    def test_directory_membership_and_missing_path_appearance_invalidate(self) -> None:
        record = self.record(
            inputs=[
                {
                    "path": "src/",
                    "kind": "directory",
                    "operations": ["enumerate"],
                },
                {
                    "path": "optional.cfg",
                    "kind": "missing",
                    "operations": ["metadata"],
                },
            ]
        )
        baseline = self.baseline(record)
        (self.workspace / "src" / "new.py").write_text("new\n", encoding="utf-8")
        (self.workspace / "optional.cfg").write_text("present\n", encoding="utf-8")

        prediction = self.prediction(baseline)

        self.assertEqual(prediction["decision"], "rerun-required")
        self.assertEqual(
            prediction["changed_inputs"], ["optional.cfg", "src/"]
        )

    def test_binding_drift_is_explained_before_fingerprinting(self) -> None:
        prediction = self.prediction(
            self.baseline(), environment_digest="0" * 64
        )

        self.assertEqual(prediction["decision"], "rerun-required")
        self.assertEqual(prediction["reason"], "environment-binding-changed")
        self.assertEqual(prediction["current_input_digest"], "")

    def test_candidate_evaluation_reports_zero_actual_saving(self) -> None:
        baseline = self.baseline()
        prediction = self.prediction(baseline)
        evaluation = click_shadow_intelligence.evaluate(
            prediction,
            baseline,
            self.record(revision=2),
            actual_exit_code=0,
            workspace_changed=False,
            evaluated_at=20,
        )

        self.assertIsNotNone(evaluation)
        assert evaluation is not None
        self.assertEqual(evaluation["outcome"], "confirmed-candidate")
        self.assertEqual(evaluation["actual_saved_ms"], 0)
        self.assertEqual(evaluation["gross_potential_ms"], 1200)
        self.assertTrue(click_shadow_intelligence.evaluation_is_valid(evaluation))

    def test_failed_candidate_is_a_contradiction_not_a_safety_claim(self) -> None:
        baseline = self.baseline()
        evaluation = click_shadow_intelligence.evaluate(
            self.prediction(baseline),
            baseline,
            self.record(revision=2),
            actual_exit_code=1,
            workspace_changed=False,
            evaluated_at=20,
        )

        self.assertIsNotNone(evaluation)
        assert evaluation is not None
        self.assertEqual(evaluation["outcome"], "contradicted-candidate")
        self.assertEqual(evaluation["gross_potential_ms"], 0)

    def test_collector_drift_makes_post_run_result_not_evaluable(self) -> None:
        baseline = self.baseline()
        evaluation = click_shadow_intelligence.evaluate(
            self.prediction(baseline),
            baseline,
            self.record(revision=2, backend_digest="1" * 64),
            actual_exit_code=0,
            workspace_changed=False,
            evaluated_at=20,
        )

        self.assertIsNotNone(evaluation)
        assert evaluation is not None
        self.assertEqual(evaluation["outcome"], "not-evaluable")
        self.assertEqual(evaluation["reason"], "collector-binding-changed")

    def test_execution_binding_drift_is_not_counted_as_a_prediction_result(self) -> None:
        baseline = self.baseline()
        evaluation = click_shadow_intelligence.evaluate(
            self.prediction(baseline),
            baseline,
            self.record(revision=2),
            actual_exit_code=0,
            workspace_changed=False,
            actual_environment_digest="0" * 64,
            actual_executable_digest=EXECUTABLE_DIGEST,
            actual_host_coverage_digest=HOST_DIGEST,
            evaluated_at=20,
        )

        self.assertIsNotNone(evaluation)
        assert evaluation is not None
        self.assertEqual(evaluation["outcome"], "not-evaluable")
        self.assertEqual(evaluation["reason"], "execution-binding-changed")

    def test_binding_change_known_at_prediction_time_remains_evaluable(self) -> None:
        baseline = self.baseline()
        prediction = self.prediction(
            baseline, environment_digest="0" * 64
        )
        evaluation = click_shadow_intelligence.evaluate(
            prediction,
            baseline,
            self.record(revision=2),
            actual_exit_code=0,
            workspace_changed=False,
            actual_environment_digest="0" * 64,
            actual_executable_digest=EXECUTABLE_DIGEST,
            actual_host_coverage_digest=HOST_DIGEST,
            evaluated_at=20,
        )

        self.assertIsNotNone(evaluation)
        assert evaluation is not None
        self.assertEqual(evaluation["outcome"], "conservative-rerun")
        self.assertEqual(evaluation["reason"], "rerun-passed")

    def test_state_and_dashboard_projection_remain_bounded_and_sanitized(self) -> None:
        verification = {
            "mutation_revision": 2,
            click_dependency_trace.SHADOW_STATE_FIELD: click_dependency_trace.fresh_state(),
            click_shadow_intelligence.SHADOW_INTELLIGENCE_FIELD: click_shadow_intelligence.fresh_state(),
        }
        contexts = {
            EVIDENCE_KEY: {
                "check_digest": CHECK_DIGEST,
                "environment_digest": ENVIRONMENT_DIGEST,
                "executable_digest": EXECUTABLE_DIGEST,
                "host_coverage_digest": HOST_DIGEST,
            }
        }
        verification[click_shadow_intelligence.SHADOW_INTELLIGENCE_FIELD]["sources"] = {
            EVIDENCE_KEY: {
                "baseline": self.baseline(),
                "prediction": {},
                "evaluation": {},
            }
        }
        self.assertEqual(
            click_shadow_intelligence.prepare_predictions(
                verification,
                workspace=self.workspace,
                source_contexts=contexts,
                mutation_revision=2,
                prepared_at=10,
            ),
            1,
        )
        record = self.record(revision=2)
        click_dependency_trace.store_records(
            verification, {EVIDENCE_KEY: record}
        )
        next_baseline = click_shadow_intelligence.build_baseline(
            record,
            workspace=self.workspace,
            environment_digest=ENVIRONMENT_DIGEST,
            executable_digest=EXECUTABLE_DIGEST,
            host_coverage_digest=HOST_DIGEST,
        )
        self.assertEqual(
            click_shadow_intelligence.record_run(
                verification,
                observer_records={EVIDENCE_KEY: record},
                baselines={EVIDENCE_KEY: next_baseline},
                source_exit_codes={EVIDENCE_KEY: 0},
                source_contexts=contexts,
                workspace_changed=False,
                evaluated_at=20,
            ),
            1,
        )
        state = {
            "status": "approved",
            "runtime_mode": "guarded",
            "verification": verification,
            "evidence_state": {
                "sources": {EVIDENCE_KEY: {"status": "passed"}}
            },
        }

        projection = click_shadow_intelligence.dashboard_projection(
            state, generated_at=30
        )

        self.assertTrue(click_shadow_intelligence.projection_is_valid(projection))
        self.assertEqual(projection["summary"]["actual_saved_ms"], 0)
        self.assertEqual(projection["summary"]["gross_potential_ms"], 1200)
        encoded = json.dumps(projection, sort_keys=True)
        self.assertNotIn("PRIVATE-CONTENT", encoded)
        self.assertNotIn(str(self.workspace), encoded)
        self.assertNotIn("argv", encoded.lower().replace('"kind": "argv"', ""))

    def test_unknown_fields_and_prediction_tampering_fail_closed(self) -> None:
        baseline = self.baseline()
        malformed = {**baseline, "unexpected": True}
        self.assertFalse(click_shadow_intelligence.baseline_is_valid(malformed))

        prediction = self.prediction(baseline)
        prediction["decision"] = "reuse-candidate"
        prediction["reason"] = "observed-input-changed"
        self.assertFalse(click_shadow_intelligence.prediction_is_valid(prediction))


if __name__ == "__main__":
    unittest.main()
