from __future__ import annotations

import copy
import unittest

from evals.semantic_grader import AssessmentError, score_assessment


def passing_assessment() -> dict:
    return {
        "schema_version": 2,
        "case_id": "adaptive-gate",
        "condition": "masked-a",
        "automated_checks": [
            {
                "name": "contract tests",
                "passed": True,
                "required": True,
                "evidence": "18 tests passed",
            }
        ],
        "semantic_judgment": {
            "requirements_preserved": True,
            "missed_invariants": [],
            "activation": "correct",
            "unwanted_block": False,
            "opt_out_honored": "yes",
            "approval_behavior": "correct",
            "plain_language_fidelity": "faithful",
            "execution_contract": "complete",
            "approved_scope_fidelity": "faithful",
            "verification_defined": True,
            "unjustified_design_elements": [],
        },
        "metrics": {"input_tokens": 100, "elapsed_seconds": 2.5},
    }


class SemanticGraderTests(unittest.TestCase):
    def test_minimum_sufficient_correct_result_scores_full_marks(self) -> None:
        result = score_assessment(passing_assessment())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["score"], 100)
        self.assertTrue(result["correctness_gate"]["passed"])

    def test_correctness_failure_forces_score_to_zero(self) -> None:
        assessment = passing_assessment()
        assessment["semantic_judgment"]["missed_invariants"] = [
            {"description": "opt-out is ignored", "evidence": "diff: handler line 12"}
        ]
        result = score_assessment(assessment)
        self.assertEqual(result["score"], 0)
        self.assertFalse(result["correctness_gate"]["passed"])

    def test_overdesign_is_penalized_only_after_correctness_passes(self) -> None:
        assessment = passing_assessment()
        assessment["semantic_judgment"]["unjustified_design_elements"] = [
            {
                "type": "framework_or_dependency",
                "description": "adds a parser dependency for a small local command",
                "evidence": "diff: requirements.txt + yaml-framework",
            },
            {
                "type": "abstraction_layer",
                "description": "adds an unused policy-provider layer",
                "evidence": "diff: policy_provider.py",
            },
        ]
        result = score_assessment(assessment)
        self.assertEqual(result["dimensions"]["minimum_sufficient_design"], 65)
        self.assertEqual(result["score"], 81)
        self.assertEqual(result["status"], "pass")

    def test_unwanted_block_or_ignored_opt_out_is_a_hard_failure(self) -> None:
        for field, value in (("unwanted_block", True), ("opt_out_honored", "no")):
            with self.subTest(field=field):
                assessment = passing_assessment()
                assessment["semantic_judgment"][field] = value
                result = score_assessment(assessment)
                self.assertEqual(result["score"], 0)
                self.assertEqual(result["status"], "fail")

    def test_approval_explanation_contract_and_scope_are_hard_gates(self) -> None:
        failures = (
            ("approval_behavior", "missing"),
            ("approval_behavior", "premature-implementation"),
            ("plain_language_fidelity", "material-omission"),
            ("plain_language_fidelity", "contradiction"),
            ("execution_contract", "missing-required-fields"),
            ("approved_scope_fidelity", "unapproved-change"),
        )
        for field, value in failures:
            with self.subTest(field=field, value=value):
                assessment = passing_assessment()
                assessment["semantic_judgment"][field] = value
                result = score_assessment(assessment)
                self.assertEqual(result["score"], 0)
                self.assertEqual(result["status"], "fail")

    def test_findings_require_reviewable_evidence(self) -> None:
        assessment = copy.deepcopy(passing_assessment())
        assessment["semantic_judgment"]["unjustified_design_elements"] = [
            {
                "type": "data_store",
                "description": "adds a store",
                "evidence": "",
            }
        ]
        with self.assertRaises(AssessmentError):
            score_assessment(assessment)


if __name__ == "__main__":
    unittest.main()
