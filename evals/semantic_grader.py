#!/usr/bin/env python3
"""Deterministically score a structured Build Brief semantic assessment.

The model or human judge supplies semantic findings with evidence. This module
validates that shape, applies correctness as a hard gate, and only then scores
minimum-sufficient design, routing, interaction safety, and proof.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


SCHEMA_VERSION = 1
PASS_THRESHOLD = 80
ACTIVATION_SCORES = {
    "correct": 100,
    "over-activated": 25,
    "missed": 25,
    "not-applicable": 100,
}
MATERIAL_ELEMENT_PENALTIES = {
    "deployable_unit": 30,
    "data_store": 30,
    "queue_or_async_boundary": 25,
    "public_contract": 20,
    "framework_or_dependency": 20,
    "abstraction_layer": 15,
    "configuration_surface": 10,
    "operational_component": 20,
}


class AssessmentError(ValueError):
    """Raised when an assessment cannot be scored safely."""


def _require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssessmentError(f"`{field}` must be an object")
    return value


def _require_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise AssessmentError(f"`{field}` must be an array")
    return value


def _require_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise AssessmentError(f"`{field}` must be a boolean")
    return value


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AssessmentError(f"`{field}` must be a non-empty string")
    return value.strip()


def _validate_finding(value: Any, field: str) -> dict[str, str]:
    finding = _require_object(value, field)
    return {
        "description": _require_text(finding.get("description"), f"{field}.description"),
        "evidence": _require_text(finding.get("evidence"), f"{field}.evidence"),
    }


def _validated_assessment(value: Any) -> dict[str, Any]:
    assessment = _require_object(value, "assessment")
    if assessment.get("schema_version") != SCHEMA_VERSION:
        raise AssessmentError(f"`schema_version` must be {SCHEMA_VERSION}")
    _require_text(assessment.get("case_id"), "case_id")
    _require_text(assessment.get("condition"), "condition")

    checks = _require_list(assessment.get("automated_checks"), "automated_checks")
    validated_checks: list[dict[str, Any]] = []
    for index, raw_check in enumerate(checks):
        check = _require_object(raw_check, f"automated_checks[{index}]")
        validated_checks.append(
            {
                "name": _require_text(check.get("name"), f"automated_checks[{index}].name"),
                "passed": _require_bool(
                    check.get("passed"), f"automated_checks[{index}].passed"
                ),
                "required": _require_bool(
                    check.get("required", True),
                    f"automated_checks[{index}].required",
                ),
                "evidence": _require_text(
                    check.get("evidence"), f"automated_checks[{index}].evidence"
                ),
            }
        )

    judgment = _require_object(assessment.get("semantic_judgment"), "semantic_judgment")
    activation = judgment.get("activation")
    if activation not in ACTIVATION_SCORES:
        raise AssessmentError(
            "`semantic_judgment.activation` must be correct, over-activated, missed, "
            "or not-applicable"
        )
    opt_out = judgment.get("opt_out_honored")
    if opt_out not in {"yes", "no", "not-applicable"}:
        raise AssessmentError(
            "`semantic_judgment.opt_out_honored` must be yes, no, or not-applicable"
        )

    missed = [
        _validate_finding(item, f"semantic_judgment.missed_invariants[{index}]")
        for index, item in enumerate(
            _require_list(
                judgment.get("missed_invariants"),
                "semantic_judgment.missed_invariants",
            )
        )
    ]

    additions: list[dict[str, str]] = []
    for index, raw_addition in enumerate(
        _require_list(
            judgment.get("unjustified_design_elements"),
            "semantic_judgment.unjustified_design_elements",
        )
    ):
        field = f"semantic_judgment.unjustified_design_elements[{index}]"
        addition = _require_object(raw_addition, field)
        element_type = addition.get("type")
        if element_type not in MATERIAL_ELEMENT_PENALTIES:
            raise AssessmentError(
                f"`{field}.type` must be a recognized material design element"
            )
        finding = _validate_finding(addition, field)
        additions.append({"type": str(element_type), **finding})

    return {
        **assessment,
        "automated_checks": validated_checks,
        "semantic_judgment": {
            **judgment,
            "requirements_preserved": _require_bool(
                judgment.get("requirements_preserved"),
                "semantic_judgment.requirements_preserved",
            ),
            "missed_invariants": missed,
            "activation": activation,
            "unwanted_block": _require_bool(
                judgment.get("unwanted_block"),
                "semantic_judgment.unwanted_block",
            ),
            "opt_out_honored": opt_out,
            "proof_complete": _require_bool(
                judgment.get("proof_complete"),
                "semantic_judgment.proof_complete",
            ),
            "unjustified_design_elements": additions,
        },
    }


def score_assessment(value: Any) -> dict[str, Any]:
    """Validate and score an assessment, returning a stable JSON-ready result."""

    assessment = _validated_assessment(value)
    checks = assessment["automated_checks"]
    judgment = assessment["semantic_judgment"]

    failed_checks = [
        check["name"]
        for check in checks
        if check["required"] and not check["passed"]
    ]
    hard_failures: list[str] = []
    if failed_checks:
        hard_failures.append("required automated checks failed")
    if not judgment["requirements_preserved"]:
        hard_failures.append("requested behavior was not preserved")
    if judgment["missed_invariants"]:
        hard_failures.append("material invariants were missed")
    if judgment["unwanted_block"]:
        hard_failures.append("the plugin blocked unselected work")
    if judgment["opt_out_honored"] == "no":
        hard_failures.append("the user's opt-out was not honored")

    penalties = [
        {
            **addition,
            "points": MATERIAL_ELEMENT_PENALTIES[addition["type"]],
        }
        for addition in judgment["unjustified_design_elements"]
    ]
    minimality_score = max(0, 100 - sum(item["points"] for item in penalties))
    routing_score = ACTIVATION_SCORES[judgment["activation"]]
    interaction_score = (
        0
        if judgment["unwanted_block"] or judgment["opt_out_honored"] == "no"
        else 100
    )
    proof_score = 100 if judgment["proof_complete"] else 40

    correctness_passed = not hard_failures
    weighted_score = round(
        minimality_score * 0.55
        + routing_score * 0.20
        + interaction_score * 0.15
        + proof_score * 0.10
    )
    final_score = weighted_score if correctness_passed else 0

    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": assessment["case_id"],
        "condition": assessment["condition"],
        "status": (
            "pass"
            if correctness_passed and final_score >= PASS_THRESHOLD
            else "fail"
        ),
        "score": final_score,
        "correctness_gate": {
            "passed": correctness_passed,
            "hard_failures": hard_failures,
            "failed_checks": failed_checks,
        },
        "dimensions": {
            "minimum_sufficient_design": minimality_score,
            "activation_routing": routing_score,
            "interaction_safety": interaction_score,
            "proof_of_completion": proof_score,
        },
        "overdesign_penalties": penalties,
        "metrics": assessment.get("metrics", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score a structured Build Brief semantic assessment"
    )
    parser.add_argument("assessment", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        value = json.loads(arguments.assessment.read_text(encoding="utf-8"))
        result = score_assessment(value)
    except (OSError, json.JSONDecodeError, AssessmentError) as exc:
        sys.stderr.write(f"semantic grader error: {exc}\n")
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
