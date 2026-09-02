"""Prose-free evidence registry and ledger primitives for Click.

This module owns deterministic evidence identifiers, initial ledger creation,
ledger-shape validation, and current-revision lookup helpers. It deliberately
does not decide contract completion, verification profiles, Browser policy, or
when a source may transition between states; those decisions remain in the
gate that calls these mechanics.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from typing import Any

if __package__:
    from . import click_dependency_cache, click_host_coverage
else:  # Executed directly from the bundled hooks directory.
    import click_dependency_cache
    import click_host_coverage


EVIDENCE_KINDS = ("argv", "browser", "hosted", "manual", "existing")
EVIDENCE_STATUSES = {"ready", "running", "observed", "passed", "failed", "stale"}
EVIDENCE_STATE_VERSION = 1


def evidence_key(evidence_id: str) -> str:
    """Return the prose-free key persisted for one approved evidence id."""
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


def _fresh_source(kind: str, dependency_patterns: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "kind": kind,
        "dependency_patterns": list(dependency_patterns),
        "dependency_declaration_digest": (
            click_dependency_cache.patterns_digest(dependency_patterns)
            if dependency_patterns
            else ""
        ),
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
        "verified_executable_digest": "",
        "verified_host_coverage": {},
        "verified_at": 0,
        "verified_dependency_provider": "",
        "verified_dependency_manifest_digest": "",
        "verified_dependency_entry_digest": "",
        "verified_dependency_digest": "",
        "verified_dependency_paths": [],
        "verified_dependency_observation_digest": "",
        "verified_dependency_observation": {},
        "dependency_reuse_count": 0,
        "last_dependency_reused_at": 0,
        "last_dependency_reused_from_revision": -1,
    }


def fresh_state(contract: dict[str, Any]) -> dict[str, Any]:
    """Create a prose-free evidence ledger from a validated contract."""
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
            declared_patterns = source.get("dependencies", [])
            normalized_patterns, dependency_error = (
                click_dependency_cache.normalize_patterns(declared_patterns)
                if declared_patterns
                else ((), "")
            )
            if dependency_error or normalized_patterns is None:
                normalized_patterns = ()
            sources[evidence_key(source_id)] = _fresh_source(
                kind, normalized_patterns
            )
    return {
        "version": EVIDENCE_STATE_VERSION,
        "source_count": len(sources),
        "registry_digest": registry_digest(sources),
        "sources": sources,
    }


def register_runtime_sources(
    state: dict[str, Any], source_ids: list[str], *, kind: str = "argv"
) -> tuple[dict[str, Any] | None, str]:
    """Register execution-selected Evidence-mode sources without prose authority."""
    if state.get("status") != "evidence" or kind not in EVIDENCE_KINDS:
        return None, "Dynamic evidence registration requires Evidence mode."
    evidence_state = state.get("evidence_state")
    if not isinstance(evidence_state, dict):
        return None, "Click Evidence registry is unavailable."
    sources = evidence_state.get("sources")
    if not isinstance(sources, dict):
        return None, "Click Evidence registry is unavailable."
    for source_id in source_ids:
        if not isinstance(source_id, str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_-]{0,31}", source_id
        ):
            return None, "Dynamic evidence id is invalid."
        key = evidence_key(source_id)
        existing = sources.get(key)
        if isinstance(existing, dict):
            if existing.get("kind") != kind:
                return None, "Dynamic evidence id is already registered with another kind."
            continue
        # Evidence mode has no approval-bound declaration. Cross-revision reuse
        # may therefore come only from an exact committed repository manifest.
        sources[key] = _fresh_source(kind)
    evidence_state["sources"] = sources
    evidence_state["source_count"] = len(sources)
    evidence_state["registry_digest"] = registry_digest(sources)
    state["evidence_state"] = evidence_state
    return sources, ""


def _dependency_fields_are_valid(source: dict[str, Any]) -> bool:
    patterns = source.get("dependency_patterns", [])
    declaration_digest = source.get("dependency_declaration_digest", "")
    if not isinstance(patterns, list) or not isinstance(declaration_digest, str):
        return False
    if patterns:
        normalized, error = click_dependency_cache.normalize_patterns(patterns)
        if (
            error
            or normalized is None
            or list(normalized) != patterns
            or declaration_digest
            != click_dependency_cache.patterns_digest(normalized)
        ):
            return False
    elif declaration_digest:
        return False

    provider = source.get("verified_dependency_provider", "")
    manifest_digest = source.get("verified_dependency_manifest_digest", "")
    entry_digest = source.get("verified_dependency_entry_digest", "")
    dependency_digest = source.get("verified_dependency_digest", "")
    paths = source.get("verified_dependency_paths", [])
    observation_digest = source.get(
        "verified_dependency_observation_digest", ""
    )
    observation = source.get("verified_dependency_observation", {})
    if not all(
        isinstance(value, str)
        for value in (
            provider,
            manifest_digest,
            entry_digest,
            dependency_digest,
            observation_digest,
        )
    ) or not isinstance(paths, list) or not isinstance(observation, dict):
        return False
    if provider:
        if (
            provider not in click_dependency_cache.PROVIDER_NAMES
            or re.fullmatch(r"[0-9a-f]{64}", entry_digest) is None
            or re.fullmatch(r"[0-9a-f]{64}", dependency_digest) is None
            or manifest_digest
            and re.fullmatch(r"[0-9a-f]{64}", manifest_digest) is None
            or not click_dependency_cache.receipt_paths_are_valid(paths)
            or observation
            and (
                not click_dependency_cache.dependency_observation_is_valid(
                    observation
                )
                or observation_digest
                != click_dependency_cache.dependency_observation_digest(
                    observation
                )
            )
            or not observation
            and observation_digest
        ):
            return False
        if provider == click_dependency_cache.CONTRACT_PROVIDER_NAME:
            if manifest_digest:
                return False
        elif re.fullmatch(r"[0-9a-f]{64}", manifest_digest) is None:
            return False
    elif any(
        (
            manifest_digest,
            entry_digest,
            dependency_digest,
            paths,
            observation_digest,
            observation,
        )
    ):
        return False
    reuse_count = source.get("dependency_reuse_count", 0)
    reused_at = source.get("last_dependency_reused_at", 0)
    reused_from = source.get("last_dependency_reused_from_revision", -1)
    for value in (reuse_count, reused_at, reused_from):
        if not isinstance(value, int) or isinstance(value, bool):
            return False
    if reuse_count < 0 or reused_at < 0 or reused_from < -1:
        return False
    if not provider:
        return reuse_count == 0 and reused_at == 0 and reused_from == -1
    return bool(
        reuse_count == 0
        and reused_at == 0
        and reused_from == -1
        or reuse_count > 0
        and reused_at > 0
        and reused_from >= 0
    )


def _host_coverage_field_is_valid(source: dict[str, Any]) -> bool:
    coverage = source.get("verified_host_coverage", {})
    return bool(
        isinstance(coverage, dict)
        and (not coverage or click_host_coverage.receipt_is_valid(coverage))
    )


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
            or not isinstance(source.get("verified_executable_digest", ""), str)
            or source.get("verified_executable_digest", "")
            and re.fullmatch(
                r"[0-9a-f]{64}",
                str(source.get("verified_executable_digest", "")),
            )
            is None
            or not _dependency_fields_are_valid(source)
            or not _host_coverage_field_is_valid(source)
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
    """Create the prose-free Browser evidence session state."""
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
