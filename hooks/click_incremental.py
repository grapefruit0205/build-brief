#!/usr/bin/env python3
"""Canonical incremental-verification plan records.

This module does not decide whether evidence may be reused.  The verification
runtime supplies decisions only after its existing receipt, dependency, and
safe-change authority checks have completed.  The resulting content-free plan
is the single deterministic source for constructing the runner batch and for
explaining that batch to read-only consumers.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Iterable


PLAN_VERSION = 1
PLAN_FIELD = "incremental_plan"

DECISIONS = frozenset(
    {"run", "reuse-exact", "reuse-dependency", "reuse-safe-change", "not-evaluable"}
)
REUSE_DECISIONS = frozenset(
    {"reuse-exact", "reuse-dependency", "reuse-safe-change"}
)
AUTHORITY_SOURCES = frozenset(
    {
        "runner",
        "exact-receipt",
        "runtime-dependency-observation",
        "repository-safe-change-policy",
        "none",
    }
)
REASON_CODES = frozenset(
    {
        "same-revision-receipt-current",
        "observed-dependencies-unchanged",
        "safe-change-policy-covered",
        "no-passing-evidence",
        "previous-verification-failed",
        "observed-input-changed",
        "check-binding-changed",
        "contract-binding-changed",
        "environment-binding-changed",
        "executable-binding-changed",
        "host-coverage-binding-changed",
        "workspace-ambiguous",
        "mutation-boundary-ambiguous",
        "observer-incomplete",
        "external-input-unmodeled",
        "policy-unavailable",
        "safe-change-policy-not-covered",
        "receipt-invalid",
    }
)

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_DECISION_FIELDS = frozenset(
    {
        "source_key",
        "decision",
        "reason_code",
        "current_revision",
        "previous_revision",
        "check_digest",
        "authority_source",
        "estimated_avoided_ms",
    }
)
_PLAN_FIELDS = frozenset(
    {
        "version",
        "planned_at",
        "current_revision",
        "total_source_count",
        "executed_source_count",
        "authoritative_reuse_count",
        "exact_reuse_count",
        "dependency_reuse_count",
        "safe_change_reuse_count",
        "estimated_avoided_ms",
        "decisions",
    }
)


def _is_integer(value: Any, *, minimum: int = 0) -> bool:
    return bool(
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= minimum
    )


def decision(
    *,
    source_key: str,
    decision: str,
    reason_code: str,
    current_revision: int,
    previous_revision: int,
    check_digest: str,
    authority_source: str,
    estimated_avoided_ms: int = 0,
) -> dict[str, Any]:
    """Build one strict, content-free plan decision."""
    value = {
        "source_key": source_key,
        "decision": decision,
        "reason_code": reason_code,
        "current_revision": current_revision,
        "previous_revision": previous_revision,
        "check_digest": check_digest,
        "authority_source": authority_source,
        "estimated_avoided_ms": estimated_avoided_ms,
    }
    if not decision_is_valid(value):
        raise ValueError("invalid incremental-verification decision")
    return value


def decision_is_valid(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != _DECISION_FIELDS:
        return False
    selected = value.get("decision")
    authority = value.get("authority_source")
    avoided = value.get("estimated_avoided_ms")
    if (
        not isinstance(value.get("source_key"), str)
        or _DIGEST.fullmatch(value["source_key"]) is None
        or selected not in DECISIONS
        or value.get("reason_code") not in REASON_CODES
        or not _is_integer(value.get("current_revision"))
        or not _is_integer(value.get("previous_revision"), minimum=-1)
        or not isinstance(value.get("check_digest"), str)
        or _DIGEST.fullmatch(value["check_digest"]) is None
        or authority not in AUTHORITY_SOURCES
        or not _is_integer(avoided)
    ):
        return False
    expected_authority = {
        "run": "runner",
        "reuse-exact": "exact-receipt",
        "reuse-dependency": "runtime-dependency-observation",
        "reuse-safe-change": "repository-safe-change-policy",
        "not-evaluable": "none",
    }[selected]
    return bool(
        authority == expected_authority
        and (selected in REUSE_DECISIONS or avoided == 0)
    )


def build_plan(
    decisions: Iterable[dict[str, Any]],
    *,
    current_revision: int,
    planned_at: int | None = None,
) -> dict[str, Any]:
    """Build a canonical plan from already-authorized source decisions."""
    normalized = sorted(
        (dict(item) for item in decisions), key=lambda item: item.get("source_key", "")
    )
    if (
        not normalized
        or not _is_integer(current_revision)
        or any(not decision_is_valid(item) for item in normalized)
        or any(item["current_revision"] != current_revision for item in normalized)
        or len({item["source_key"] for item in normalized}) != len(normalized)
    ):
        raise ValueError("invalid incremental-verification plan input")
    counts = {
        selected: sum(item["decision"] == selected for item in normalized)
        for selected in DECISIONS
    }
    timestamp = int(time.time()) if planned_at is None else planned_at
    plan = {
        "version": PLAN_VERSION,
        "planned_at": timestamp,
        "current_revision": current_revision,
        "total_source_count": len(normalized),
        "executed_source_count": counts["run"] + counts["not-evaluable"],
        "authoritative_reuse_count": sum(
            counts[selected] for selected in REUSE_DECISIONS
        ),
        "exact_reuse_count": counts["reuse-exact"],
        "dependency_reuse_count": counts["reuse-dependency"],
        "safe_change_reuse_count": counts["reuse-safe-change"],
        "estimated_avoided_ms": sum(
            item["estimated_avoided_ms"]
            for item in normalized
            if item["decision"] in REUSE_DECISIONS
        ),
        "decisions": normalized,
    }
    if not plan_is_valid(plan):
        raise ValueError("invalid incremental-verification plan")
    return plan


def plan_is_valid(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != _PLAN_FIELDS:
        return False
    decisions = value.get("decisions")
    if (
        value.get("version") != PLAN_VERSION
        or not _is_integer(value.get("planned_at"), minimum=1)
        or not _is_integer(value.get("current_revision"))
        or not isinstance(decisions, list)
        or not decisions
        or any(not decision_is_valid(item) for item in decisions)
        or decisions != sorted(decisions, key=lambda item: item["source_key"])
        or len({item["source_key"] for item in decisions}) != len(decisions)
        or any(
            item["current_revision"] != value["current_revision"]
            for item in decisions
        )
    ):
        return False
    counts = {
        selected: sum(item["decision"] == selected for item in decisions)
        for selected in DECISIONS
    }
    return bool(
        value.get("total_source_count") == len(decisions)
        and value.get("executed_source_count")
        == counts["run"] + counts["not-evaluable"]
        and value.get("authoritative_reuse_count")
        == sum(counts[selected] for selected in REUSE_DECISIONS)
        and value.get("exact_reuse_count") == counts["reuse-exact"]
        and value.get("dependency_reuse_count") == counts["reuse-dependency"]
        and value.get("safe_change_reuse_count") == counts["reuse-safe-change"]
        and value.get("estimated_avoided_ms")
        == sum(
            item["estimated_avoided_ms"]
            for item in decisions
            if item["decision"] in REUSE_DECISIONS
        )
        and all(
            _is_integer(value.get(field))
            for field in (
                "total_source_count",
                "executed_source_count",
                "authoritative_reuse_count",
                "exact_reuse_count",
                "dependency_reuse_count",
                "safe_change_reuse_count",
                "estimated_avoided_ms",
            )
        )
    )


def keys_to_execute(plan: Any) -> set[str]:
    """Return the sources retained in the real runner batch."""
    if not plan_is_valid(plan):
        raise ValueError("invalid incremental-verification plan")
    return {
        item["source_key"]
        for item in plan["decisions"]
        if item["decision"] not in REUSE_DECISIONS
    }


def store_plan(verification: dict[str, Any], plan: dict[str, Any]) -> None:
    if not plan_is_valid(plan):
        raise ValueError("invalid incremental-verification plan")
    # JSON round-tripping prevents callers from retaining mutable aliases.
    verification[PLAN_FIELD] = json.loads(
        json.dumps(plan, sort_keys=True, separators=(",", ":"))
    )


def current_plan(verification: Any) -> dict[str, Any] | None:
    value = verification.get(PLAN_FIELD) if isinstance(verification, dict) else None
    return dict(value) if plan_is_valid(value) else None
