#!/usr/bin/env python3
"""Content-free diagnostics for authoritative reuse decisions.

Diagnostics are a read-only explanation of comparisons the verification
runtime already made.  They never decide whether a source runs or is reused.
"""

from __future__ import annotations

import copy
import math
import re
import time
from typing import Any, Iterable


CONTROL_FIELD = "reuse_diagnostics_control"
CONTROL_VERSION = 1
MODES = frozenset({"off", "on"})
DEFAULT_MODE = "on"

DIAGNOSTIC_VERSION = 1
BASELINE_STATUSES = frozenset({"present", "absent", "failed", "unknown"})
CHECK_STATUSES = frozenset({"matched", "mismatched", "not-evaluated"})
CONDITIONS = (
    "prior-success",
    "successor-scope",
    "successor-integrity",
    "receipt-integrity",
    "mutation-boundary",
    "contract-binding",
    "check-binding",
    "workspace-binding",
    "workspace-tree-binding",
    "executable-binding",
    "environment-binding",
    "host-coverage-binding",
    "dependency-observation-complete",
    "external-input-modeled",
    "observed-inputs-unchanged",
    "safe-change-policy-available",
    "safe-change-policy-covered",
)
_PRIMARY_CONDITION = {
    "no-passing-evidence": "prior-success",
    "previous-verification-failed": "prior-success",
    "successor-evidence-scope-mismatch": "successor-scope",
    "successor-evidence-integrity-invalid": "successor-integrity",
    "receipt-invalid": "receipt-integrity",
    "mutation-boundary-ambiguous": "mutation-boundary",
    "contract-binding-changed": "contract-binding",
    "check-binding-changed": "check-binding",
    "workspace-ambiguous": "workspace-tree-binding",
    "executable-binding-changed": "executable-binding",
    "environment-binding-changed": "environment-binding",
    "host-coverage-binding-changed": "host-coverage-binding",
    "observer-incomplete": "dependency-observation-complete",
    "external-input-unmodeled": "external-input-modeled",
    "observed-input-changed": "observed-inputs-unchanged",
    "policy-unavailable": "safe-change-policy-available",
    "safe-change-policy-not-covered": "safe-change-policy-covered",
}

_CONTROL_FIELDS = frozenset({"version", "mode", "updated_at"})
_DIAGNOSTIC_FIELDS = frozenset(
    {
        "version",
        "baseline_status",
        "previous_success_exists",
        "reuse_considered",
        "decision",
        "primary_reason_code",
        "candidate_evaluation",
        "checks",
    }
)
_CHECK_FIELDS = frozenset({"condition", "status", "reason_code"})
_CODE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_BATCH_ID = re.compile(r"^[0-9a-f]{32}$")

_OUTCOME_COUNT_FIELDS = (
    "passed_source_count",
    "failed_source_count",
    "interrupted_source_count",
    "not_run_source_count",
    "pending_source_count",
)
_MEASURED_COUNT_FIELDS = (
    "measured_passed_source_count",
    "measured_failed_source_count",
    "measured_interrupted_source_count",
)
_DURATION_FIELDS = (
    "observed_passed_execution_ms",
    "observed_failed_execution_ms",
    "observed_interrupted_execution_ms",
)
_DEDUPLICATED_FIELDS = frozenset(
    {
        *_OUTCOME_COUNT_FIELDS,
        *_MEASURED_COUNT_FIELDS,
        *_DURATION_FIELDS,
        "baseline_present_count",
        "incomplete_measurement_count",
    }
)
_CAUSE_FIELDS = frozenset(
    {
        "reason_code",
        "source_count",
        "single_cause_source_count",
        "multiple_cause_source_count",
        *_DEDUPLICATED_FIELDS,
    }
)
_AGGREGATE_FIELDS = frozenset(
    {
        "diagnosed_source_count",
        "blocked_source_count",
        "reused_source_count",
        "unapplied_reuse_source_count",
        "not_evaluated_check_count",
        "cause_costs_overlap",
        "deduplicated",
        "causes",
    }
)


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_duration(value: Any) -> bool:
    return bool(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def fresh_state() -> dict[str, Any]:
    return {"version": CONTROL_VERSION, "mode": DEFAULT_MODE, "updated_at": 0}


def control_is_valid(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == _CONTROL_FIELDS
        and value.get("version") == CONTROL_VERSION
        and value.get("mode") in MODES
        and _is_count(value.get("updated_at"))
    )


def mode(verification: Any) -> str:
    value = verification.get(CONTROL_FIELD) if isinstance(verification, dict) else None
    # Older state files predate this optional, non-authoritative telemetry.
    return str(value["mode"]) if control_is_valid(value) else DEFAULT_MODE


def enabled(verification: Any) -> bool:
    return mode(verification) == "on"


def set_mode(
    verification: dict[str, Any], selected: str, *, updated_at: int | None = None
) -> None:
    if selected not in MODES:
        raise ValueError("reuse diagnostics mode must be off or on")
    timestamp = int(time.time()) if updated_at is None else updated_at
    value = {"version": CONTROL_VERSION, "mode": selected, "updated_at": timestamp}
    if not control_is_valid(value):
        raise ValueError("reuse diagnostics timestamp is invalid")
    verification[CONTROL_FIELD] = value


def projection(verification: Any) -> dict[str, Any]:
    selected = mode(verification)
    return {
        "mode": selected,
        "enabled": selected == "on",
        "authoritative": False,
        "affects_execution": False,
    }


def baseline_status(source: Any) -> str:
    if not isinstance(source, dict):
        return "unknown"
    status = source.get("status")
    if status == "failed" or (
        isinstance(source.get("last_exit_code"), int)
        and not isinstance(source.get("last_exit_code"), bool)
        and source.get("last_exit_code") != 0
    ):
        return "failed"
    verified_at = source.get("verified_at")
    verified_revision = source.get("verified_revision")
    verified_check = source.get("verified_check_digest")
    if (
        status in {"passed", "stale", "observed"}
        and isinstance(verified_at, int)
        and not isinstance(verified_at, bool)
        and verified_at > 0
        and isinstance(verified_revision, int)
        and not isinstance(verified_revision, bool)
        and verified_revision >= 0
        and isinstance(verified_check, str)
        and _DIGEST.fullmatch(verified_check)
    ):
        return "present"
    if status in {"ready", None} and verified_revision in {-1, None}:
        return "absent"
    return "unknown"


def begin(source: Any) -> dict[str, Any]:
    status = baseline_status(source)
    reason = (
        "previous-verification-failed"
        if status == "failed"
        else "no-passing-evidence"
    )
    checks: dict[str, dict[str, str]] = {}
    if status == "present":
        checks["prior-success"] = {
            "condition": "prior-success",
            "status": "matched",
            "reason_code": "",
        }
    elif status in {"absent", "failed"}:
        checks["prior-success"] = {
            "condition": "prior-success",
            "status": "mismatched",
            "reason_code": reason,
        }
    return {
        "baseline_status": status,
        "reuse_considered": status == "present",
        "checks": checks,
    }


def mark_previous_success(facts: dict[str, Any]) -> None:
    facts["baseline_status"] = "present"
    facts["reuse_considered"] = True
    record(facts, "prior-success", True)


def mark_considered(facts: dict[str, Any]) -> None:
    facts["reuse_considered"] = True


def record(
    facts: dict[str, Any],
    condition: str,
    matched: bool | None,
    *,
    reason_code: str = "",
) -> None:
    if condition not in CONDITIONS:
        raise ValueError("unknown reuse diagnostic condition")
    status = "not-evaluated" if matched is None else "matched" if matched else "mismatched"
    if status == "mismatched":
        if not isinstance(reason_code, str) or _CODE.fullmatch(reason_code) is None:
            raise ValueError("mismatched diagnostic checks require a stable reason code")
    elif reason_code:
        raise ValueError("only mismatched diagnostic checks may carry a reason code")
    facts.setdefault("checks", {})[condition] = {
        "condition": condition,
        "status": status,
        "reason_code": reason_code,
    }


def freeze(
    facts: dict[str, Any], *, decision: str, primary_reason_code: str
) -> dict[str, Any]:
    status = facts.get("baseline_status", "unknown")
    checks_by_condition = copy.deepcopy(facts.get("checks", {}))
    primary_condition = _PRIMARY_CONDITION.get(primary_reason_code)
    if (
        decision not in {"reuse-exact", "reuse-dependency", "reuse-safe-change"}
        and primary_condition is not None
        and not any(
            item.get("status") == "mismatched"
            and item.get("reason_code") == primary_reason_code
            for item in checks_by_condition.values()
        )
    ):
        # The authoritative reason is itself an evaluated fact even when an
        # earlier batch-wide branch prevented source-local comparisons.
        checks_by_condition[primary_condition] = {
            "condition": primary_condition,
            "status": "mismatched",
            "reason_code": primary_reason_code,
        }
    checks = [
        copy.deepcopy(
            checks_by_condition.get(
                condition,
                {
                    "condition": condition,
                    "status": "not-evaluated",
                    "reason_code": "",
                },
            )
        )
        for condition in CONDITIONS
    ]
    value = {
        "version": DIAGNOSTIC_VERSION,
        "baseline_status": status,
        "previous_success_exists": status == "present",
        "reuse_considered": bool(facts.get("reuse_considered", False)),
        "decision": decision,
        "primary_reason_code": primary_reason_code,
        # Phase 1 reports current blockers; it does not speculate about or
        # enable alternative reuse rules.
        "candidate_evaluation": "not-evaluated",
        "checks": checks,
    }
    if not diagnostic_is_valid(value):
        raise ValueError("invalid frozen reuse diagnostic")
    return value


def diagnostic_is_valid(
    value: Any, *, allowed_reasons: set[str] | frozenset[str] | None = None
) -> bool:
    if (
        not isinstance(value, dict)
        or set(value) != _DIAGNOSTIC_FIELDS
        or value.get("version") != DIAGNOSTIC_VERSION
        or value.get("baseline_status") not in BASELINE_STATUSES
        or not isinstance(value.get("previous_success_exists"), bool)
        or value["previous_success_exists"]
        != (value.get("baseline_status") == "present")
        or not isinstance(value.get("reuse_considered"), bool)
        or not isinstance(value.get("decision"), str)
        or _CODE.fullmatch(value["decision"]) is None
        or not isinstance(value.get("primary_reason_code"), str)
        or _CODE.fullmatch(value["primary_reason_code"]) is None
        or value.get("candidate_evaluation") != "not-evaluated"
        or not isinstance(value.get("checks"), list)
        or len(value["checks"]) != len(CONDITIONS)
    ):
        return False
    if allowed_reasons is not None and value["primary_reason_code"] not in allowed_reasons:
        return False
    if value["reuse_considered"] and value["baseline_status"] == "absent":
        return False
    for condition, check in zip(CONDITIONS, value["checks"]):
        if (
            not isinstance(check, dict)
            or set(check) != _CHECK_FIELDS
            or check.get("condition") != condition
            or check.get("status") not in CHECK_STATUSES
            or not isinstance(check.get("reason_code"), str)
        ):
            return False
        reason = check["reason_code"]
        if check["status"] == "mismatched":
            if _CODE.fullmatch(reason) is None:
                return False
            if allowed_reasons is not None and reason not in allowed_reasons:
                return False
        elif reason:
            return False
    return True


def _empty_outcomes() -> dict[str, Any]:
    return {
        **{field: 0 for field in _OUTCOME_COUNT_FIELDS},
        **{field: 0 for field in _MEASURED_COUNT_FIELDS},
        **{field: None for field in _DURATION_FIELDS},
        "baseline_present_count": 0,
        "incomplete_measurement_count": 0,
    }


def _outcome(status: str) -> str:
    if status == "passed":
        return "passed"
    if status == "failed":
        return "failed"
    if status == "interrupted":
        return "interrupted"
    if status == "not-run":
        return "not_run"
    return "pending"


def _add_outcome(target: dict[str, Any], source: dict[str, Any]) -> None:
    outcome = _outcome(str(source.get("status", "unknown")))
    target[f"{outcome}_source_count"] += 1
    diagnostic = source.get("reuse_diagnostic")
    if isinstance(diagnostic, dict) and diagnostic.get("previous_success_exists") is True:
        target["baseline_present_count"] += 1
    duration = source.get("duration_ms")
    if outcome in {"passed", "failed", "interrupted"}:
        if _is_duration(duration):
            count_key = f"measured_{outcome}_source_count"
            duration_key = f"observed_{outcome}_execution_ms"
            target[count_key] += 1
            target[duration_key] = (target[duration_key] or 0) + duration
        elif source.get("started") is True:
            target["incomplete_measurement_count"] += 1


def aggregate(batches: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate diagnosed outcomes without double-counting source durations."""
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for batch in batches:
        if not isinstance(batch, dict) or _BATCH_ID.fullmatch(str(batch.get("batch_id", ""))) is None:
            continue
        for source in batch.get("sources", []):
            if not isinstance(source, dict):
                continue
            diagnostic = source.get("reuse_diagnostic")
            source_key = source.get("source_key")
            if (
                diagnostic_is_valid(diagnostic)
                and isinstance(source_key, str)
                and _DIGEST.fullmatch(source_key)
            ):
                unique[(batch["batch_id"], source_key)] = source

    deduplicated = _empty_outcomes()
    causes: dict[str, dict[str, Any]] = {}
    blocked_count = 0
    reused_count = 0
    unapplied_reuse_count = 0
    not_evaluated = 0
    for source in unique.values():
        diagnostic = source["reuse_diagnostic"]
        reasons = sorted(
            {
                check["reason_code"]
                for check in diagnostic["checks"]
                if check["status"] == "mismatched"
            }
        )
        not_evaluated += sum(
            check["status"] == "not-evaluated" for check in diagnostic["checks"]
        )
        if source.get("decision") in {"reuse-exact", "reuse-dependency", "reuse-safe-change"}:
            if source.get("status") == "reused":
                reused_count += 1
            else:
                # A frozen reuse decision is not an actual reuse result until
                # the batch witnesses application. Rejection and pending state
                # remain visible without inflating reuse outcomes.
                unapplied_reuse_count += 1
            continue
        else:
            blocked_count += 1
        _add_outcome(deduplicated, source)
        for reason in reasons:
            cause = causes.setdefault(
                reason,
                {
                    "reason_code": reason,
                    "source_count": 0,
                    "single_cause_source_count": 0,
                    "multiple_cause_source_count": 0,
                    **_empty_outcomes(),
                },
            )
            cause["source_count"] += 1
            cause[
                "single_cause_source_count"
                if len(reasons) == 1
                else "multiple_cause_source_count"
            ] += 1
            _add_outcome(cause, source)

    ordered = sorted(
        causes.values(),
        key=lambda item: (
            item["observed_passed_execution_ms"] is None,
            -(item["observed_passed_execution_ms"] or 0),
            -item["source_count"],
            item["reason_code"],
        ),
    )
    return {
        "diagnosed_source_count": len(unique),
        "blocked_source_count": blocked_count,
        "reused_source_count": reused_count,
        "unapplied_reuse_source_count": unapplied_reuse_count,
        "not_evaluated_check_count": not_evaluated,
        "cause_costs_overlap": True,
        "deduplicated": deduplicated,
        "causes": ordered,
    }


def aggregate_is_valid(value: Any) -> bool:
    if (
        not isinstance(value, dict)
        or set(value) != _AGGREGATE_FIELDS
        or not all(
            _is_count(value.get(field))
            for field in (
                "diagnosed_source_count",
                "blocked_source_count",
                "reused_source_count",
                "unapplied_reuse_source_count",
                "not_evaluated_check_count",
            )
        )
        or value.get("cause_costs_overlap") is not True
        or value["blocked_source_count"]
        + value["reused_source_count"]
        + value["unapplied_reuse_source_count"]
        != value["diagnosed_source_count"]
        or not _outcome_projection_is_valid(value.get("deduplicated"), _DEDUPLICATED_FIELDS)
        or not isinstance(value.get("causes"), list)
    ):
        return False
    for cause in value["causes"]:
        if (
            not isinstance(cause, dict)
            or set(cause) != _CAUSE_FIELDS
            or not isinstance(cause.get("reason_code"), str)
            or _CODE.fullmatch(cause["reason_code"]) is None
            or not _is_count(cause.get("source_count"))
            or not _is_count(cause.get("single_cause_source_count"))
            or not _is_count(cause.get("multiple_cause_source_count"))
            or cause["single_cause_source_count"] + cause["multiple_cause_source_count"]
            != cause["source_count"]
            or not _outcome_projection_is_valid(cause, _CAUSE_FIELDS)
        ):
            return False
    return True


def _outcome_projection_is_valid(value: Any, fields: frozenset[str]) -> bool:
    if not isinstance(value, dict):
        return False
    for field in _OUTCOME_COUNT_FIELDS + _MEASURED_COUNT_FIELDS + (
        "baseline_present_count",
        "incomplete_measurement_count",
    ):
        if field in fields and not _is_count(value.get(field)):
            return False
    for field in _DURATION_FIELDS:
        if field in fields and value.get(field) is not None and not _is_duration(value[field]):
            return False
    return True
