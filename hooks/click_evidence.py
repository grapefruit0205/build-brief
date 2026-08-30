"""Content-free evidence registry and ledger primitives for Click.

This module owns deterministic evidence identifiers, initial ledger creation,
ledger-shape validation, and current-revision lookup helpers. It deliberately
does not decide contract completion, verification budgets, Browser policy, or
when a source may transition between states; those decisions remain in the
gate that calls these mechanics.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from typing import Any


EVIDENCE_KINDS = ("argv", "browser", "hosted", "manual", "existing")
EVIDENCE_STATUSES = {"ready", "running", "observed", "passed", "failed", "stale"}
EVIDENCE_STATE_VERSION = 1


def evidence_key(evidence_id: str) -> str:
    """Return the content-free key persisted for one approved evidence id."""
    return hashlib.sha256(evidence_id.encode()).hexdigest()


def registry_digest(sources: dict[str, Any]) -> str:
    """Bind the persisted source keys and kinds without storing contract prose."""
    registry = sorted(
        (key, str(source.get("kind", "")))
        for key, source in sources.items()
        if isinstance(key, str) and isinstance(source, dict)
    )
    payload = json.dumps(registry, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def fresh_state(contract: dict[str, Any]) -> dict[str, Any]:
    """Create a new content-free evidence ledger from a validated contract."""
    verification = contract.get("verification")
    declared = verification.get("evidence") if isinstance(verification, dict) else []
    sources: dict[str, Any] = {}
    if isinstance(declared, list):
        for source in declared:
            if not isinstance(source, dict):
                continue
            source_id = source.get("id")
            kind = source.get("kind")
            if not isinstance(source_id, str) or kind not in EVIDENCE_KINDS:
                continue
            sources[evidence_key(source_id)] = {
                "kind": kind,
                "status": "ready",
                "verified_revision": -1,
                "attempts": 0,
                "unchanged_failure_retries": 0,
                "last_exit_code": None,
                "last_check_digest": "",
                "locked_check_digest": "",
                "reserved_units": 0,
                "reserved_check_digest": "",
                "verified_contract_digest": "",
                "verified_check_digest": "",
                "verified_units": 0,
                "verified_root": "",
                "verified_tree_digest": "",
                "verified_environment_digest": "",
                "verified_at": 0,
            }
    return {
        "version": EVIDENCE_STATE_VERSION,
        "source_count": len(sources),
        "registry_digest": registry_digest(sources),
        "sources": sources,
    }


def sources_from_state(
    state: dict[str, Any],
    *,
    expected_contract_schema_version: int,
) -> dict[str, Any] | None:
    """Return a valid ledger, `{}` for malformed state, or `None` for legacy state."""
    if (
        "state_schema_version" in state
        and state.get("state_schema_version") != expected_contract_schema_version
    ):
        return {}
    if "evidence_state" not in state:
        if "state_schema_version" in state:
            return {}
        return None
    evidence_state = state.get("evidence_state")
    if (
        not isinstance(evidence_state, dict)
        or evidence_state.get("version") != EVIDENCE_STATE_VERSION
    ):
        return {}
    sources = evidence_state.get("sources")
    if not isinstance(sources, dict):
        return {}
    for key, source in sources.items():
        reserved_units = source.get("reserved_units", 0) if isinstance(source, dict) else 0
        reserved_digest = (
            source.get("reserved_check_digest", "")
            if isinstance(source, dict)
            else ""
        )
        if (
            not isinstance(key, str)
            or not re.fullmatch(r"[0-9a-f]{64}", key)
            or not isinstance(source, dict)
            or source.get("kind") not in EVIDENCE_KINDS
            or source.get("status") not in EVIDENCE_STATUSES
            or not isinstance(source.get("verified_revision"), int)
            or isinstance(source.get("verified_revision"), bool)
            or not isinstance(source.get("attempts"), int)
            or isinstance(source.get("attempts"), bool)
            or not isinstance(source.get("unchanged_failure_retries"), int)
            or isinstance(source.get("unchanged_failure_retries"), bool)
            or source.get("attempts", -1) < 0
            or source.get("unchanged_failure_retries", -1) < 0
            or source.get("last_exit_code") is not None
            and (
                not isinstance(source.get("last_exit_code"), int)
                or isinstance(source.get("last_exit_code"), bool)
            )
            or not isinstance(source.get("last_check_digest"), str)
            or not isinstance(source.get("locked_check_digest"), str)
            or (
                "reserved_units" in source
                and (
                    not isinstance(source.get("reserved_units"), int)
                    or isinstance(source.get("reserved_units"), bool)
                    or source.get("reserved_units", -1) < 0
                )
            )
            or (
                "reserved_check_digest" in source
                and (
                    not isinstance(source.get("reserved_check_digest"), str)
                    or source.get("reserved_check_digest")
                    and not re.fullmatch(
                        r"[0-9a-f]{64}", source.get("reserved_check_digest", "")
                    )
                )
            )
            or (reserved_units == 0) != (reserved_digest == "")
        ):
            return {}
    source_count = evidence_state.get("source_count")
    stored_digest = evidence_state.get("registry_digest")
    if (
        not isinstance(source_count, int)
        or isinstance(source_count, bool)
        or source_count != len(sources)
        or not isinstance(stored_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", stored_digest)
        or not secrets.compare_digest(stored_digest, registry_digest(sources))
    ):
        return {}
    return sources


def is_current(source: Any, revision: int) -> bool:
    """Return whether one source passed for the exact current mutation revision."""
    return bool(
        isinstance(source, dict)
        and source.get("status") == "passed"
        and int(source.get("verified_revision", -1)) == revision
    )


def keys_for_kind(sources: dict[str, Any], kind: str) -> set[str]:
    """Return the persisted keys registered for one evidence kind."""
    return {
        key
        for key, source in sources.items()
        if isinstance(source, dict) and source.get("kind") == kind
    }


def browser_source_id(contract: dict[str, Any]) -> str:
    """Return the one Browser evidence id from a validated contract, if any."""
    verification = contract.get("verification")
    evidence = verification.get("evidence") if isinstance(verification, dict) else []
    if not isinstance(evidence, list):
        return ""
    for source in evidence:
        if isinstance(source, dict) and source.get("kind") == "browser":
            source_id = source.get("id")
            return source_id if isinstance(source_id, str) else ""
    return ""


def browser_required(contract: dict[str, Any]) -> bool:
    """Return whether the validated registry assigns a Browser source."""
    return bool(browser_source_id(contract))


def fresh_external_state(
    contract: dict[str, Any] | None = None,
    *,
    required: bool | None = None,
    source_key: str | None = None,
) -> dict[str, Any]:
    """Create the content-free Browser evidence session state."""
    source_id = browser_source_id(contract or {})
    browser_source_key = (
        evidence_key(source_id)
        if source_key is None and source_id
        else (source_key or "")
    )
    browser_is_required = (
        bool(browser_source_key) if required is None else required
    )
    return {
        "browser_required": browser_is_required,
        "browser_source_key": browser_source_key,
        "browser_status": "ready" if browser_is_required else "not-required",
        "browser_calls": 0,
        "browser_seconds": 0.0,
        "browser_running": {},
        "browser_attempts": {},
        "last_browser_error": "",
    }
