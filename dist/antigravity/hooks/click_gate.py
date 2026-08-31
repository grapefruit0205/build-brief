#!/usr/bin/env python3
"""A local contract, structured-capability, anti-loop, and verification guard.

The hook does not judge architecture quality or implementation choices. It can
persist an Always ON or Manual preference outside the target repository. Always
ON gates supported software mutations behind one approved Click contract;
Manual remains fail-open until Click is explicitly armed. A read-only review
mode applies the observation anti-loop without requiring a build contract.
During active work, supported shell intent is expressed as versioned argv requests
and executed without a shell by inspect, mutate, and verify runners.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import time
import zlib
from typing import Any

if __package__:
    from . import (
        click_browser,
        click_browser_advisory,
        click_capability,
        click_contract,
        click_evidence,
        click_host_coverage,
        click_inspection,
        click_mutation,
        click_observation,
        click_process,
        click_service,
        click_verification,
        click_verification_policy,
    )
    from .click_state import (
        STATE_LOCK_STALE_SECONDS,
        STATE_LOCK_TIMEOUT_SECONDS,
        contract_path as _contract_path,
        identity_path as _identity_path,
        managed_state_path as _managed_state_path,
        mode_path as _mode_path,
        preference_path as _preference_path,
        prompt_path as _prompt_path,
        review_path as _review_path,
        state_lock as _state_lock,
        state_path as _state_path,
        state_root as _state_root,
        write_json as _write_json,
    )
    from .platform_protocol import CodexOutputAdapter, HookOutputAdapter
else:  # Executed directly from the bundled hooks directory.
    import click_browser
    import click_browser_advisory
    import click_capability
    import click_contract
    import click_evidence
    import click_host_coverage
    import click_inspection
    import click_mutation
    import click_observation
    import click_process
    import click_service
    import click_verification
    import click_verification_policy
    from click_state import (
        STATE_LOCK_STALE_SECONDS,
        STATE_LOCK_TIMEOUT_SECONDS,
        contract_path as _contract_path,
        identity_path as _identity_path,
        managed_state_path as _managed_state_path,
        mode_path as _mode_path,
        preference_path as _preference_path,
        prompt_path as _prompt_path,
        review_path as _review_path,
        state_lock as _state_lock,
        state_path as _state_path,
        state_root as _state_root,
        write_json as _write_json,
    )
    from platform_protocol import CodexOutputAdapter, HookOutputAdapter


# Compatibility aliases for direct callers and the existing deterministic
# suite. Runtime process mechanics live in the one-way click_process boundary.
_copy_limited_output = click_process.copy_limited_output
_isolated_subprocess_kwargs = click_process.isolated_subprocess_kwargs
_terminate_managed_child = click_process.terminate_process_group

# Compatibility aliases for direct callers and the deterministic suite. The
# gate owns policy and transition timing; prose-free registry mechanics live
# in the one-way click_evidence boundary.
_evidence_key = click_evidence.evidence_key
_evidence_registry_digest = click_evidence.registry_digest
_fresh_evidence_state = click_evidence.fresh_state
_evidence_is_current = click_evidence.is_current
_evidence_keys_for_kind = click_evidence.keys_for_kind
_browser_evidence_source_id = click_evidence.browser_source_id
_browser_evidence_required = click_evidence.browser_required
_fresh_external_evidence_state = click_evidence.fresh_external_state

# Compatibility alias for direct callers and the deterministic suite. Contract
# schema validation now lives in the one-way click_contract boundary.
_validate_contract = click_contract.validate_contract

# Compatibility aliases for direct callers and the deterministic suite. The
# managed local-service state machine and runner lifecycle live in the one-way
# click_service boundary; gate wrappers below provide only cross-domain routing.
_fresh_service_state = click_service.fresh_state
_looks_like_managed_service = click_service.looks_like_managed_service
_request_service_stop = click_service.request_stop
_service_snapshot = click_service.service_snapshot
_record_service_fields = click_service.record_service_fields
_claim_service_runner = click_service.claim_service_runner

# Compatibility aliases for Browser receipt helpers. Admission and PostToolUse
# state transitions live in click_browser; the gate keeps only host routing and
# supplies cross-domain lifecycle predicates.
_browser_input_error = click_browser.input_error
_browser_running_expires_at = click_browser.running_expires_at
_browser_running_entry_is_active = click_browser.running_entry_is_active
_browser_attempt_digest = click_browser.attempt_digest
_tool_response_failed = click_browser.response_failed

# Compatibility aliases for mutation state and direct result recording. The
# gate wrappers below inject host routing and shared execution mechanics into
# the one-way click_mutation boundary.
_fresh_mutation_boundary = click_mutation.fresh_boundary
_fresh_mutation_state = click_mutation.fresh_state
_mutation_is_running = click_mutation.is_running
_record_mutation_result = click_mutation.record_result

# Compatibility aliases for shared shell-free capability validation. These
# leaves are used by inspection, mutation, service, and verification without
# importing the gate or one another.
_decode_capability_request = click_capability.decode_request
_validate_argv = click_capability.validate_argv
_policy_executable_name = click_capability.policy_executable_name
_shell_segments = click_capability.shell_segments
_command_parts = click_capability.command_parts
_positional_arguments = click_capability.positional_arguments
_capability_digest = click_capability.digest
_encoded_request = click_capability.encode_request
_decode_encoded_request = click_capability.decode_encoded_request

# Compatibility aliases for read-only admission and hardened execution. The
# stateful reservation and receipt lifecycle lives separately in observation.
_validate_inspection_request = click_inspection.validate_request
_git_option_allowed = click_inspection.git_option_allowed
_is_read_only_git_remote_arguments = click_inspection.is_read_only_git_remote_arguments
_parse_read_only_git_tokens = click_inspection.parse_read_only_git_tokens
_git_subcommand = click_inspection.git_subcommand
_sanitized_git_environment = click_inspection.sanitized_git_environment
_build_read_only_git_argv = click_inspection.build_read_only_git_argv
_targets_repository_root = click_inspection.targets_repository_root
_is_broad_exploration_tokens = click_inspection.is_broad_exploration_tokens
_is_read_only_sed = click_inspection.is_read_only_sed
_get_content_paths = click_inspection.get_content_paths
_structured_ssh_parts = click_inspection.structured_ssh_parts
_is_path_qualified_executable = click_inspection.is_path_qualified_executable
_is_local_read_only_tokens = click_inspection.is_local_read_only_tokens
_is_read_only_tokens = click_inspection.is_read_only_tokens
_is_read_only_bash = click_inspection.is_read_only_bash
_direct_command_tokens = click_inspection.direct_command_tokens
_inspection_request_from_bash = click_inspection.request_from_bash
_path_is_within = click_inspection.path_is_within
_valid_git_worktree_marker = click_inspection.valid_git_worktree_marker
_workspace_boundary = click_inspection.workspace_boundary
_git_metadata_present = click_inspection.git_metadata_present
_unsafe_inherited_environment_key = click_inspection.unsafe_inherited_environment_key
_sanitized_executable_path = click_inspection.sanitized_executable_path
_resolve_read_only_executable = click_inspection.resolve_read_only_executable
_sanitized_read_only_environment = click_inspection.sanitized_read_only_environment
_execution_argv = click_inspection.execution_argv
_is_git_remote_output_request = click_inspection.is_git_remote_output_request
_redact_git_remote_url = click_inspection.redact_git_remote_url
_redact_git_remote_output = click_inspection.redact_git_remote_output
_execute_argv_commands = click_inspection.execute_argv_commands
_write_runner_stream = click_inspection.write_runner_stream
_execute_native_get_content = click_inspection.execute_native_get_content
_execute_read_only_git = click_inspection.execute_read_only_git
_execute_inspection_commands = click_inspection.execute_commands

# Compatibility aliases for observation state and result receipts. Cross-domain
# runner wrappers remain below so existing patch points are resolved at call time.
_fresh_observation_state = click_observation.fresh_state
_unclaimed_reservation_is_fresh = click_observation.unclaimed_reservation_is_fresh
_observation_is_running = click_observation.is_running
_write_review_state = click_observation.write_review_state
_read_review_state = click_observation.read_review_state
_save_review_state = click_observation.save_review_state
_clear_review_state = click_observation.clear_review_state
_managed_observation_path = click_observation.managed_path
_record_observation_result = click_observation.record_result

# Compatibility aliases for verification classification, fingerprints,
# receipts, and protected workspace snapshots. Thin wrappers below preserve
# gate patch points while delegating the complete runner lifecycle.
_fresh_verification_state = click_verification.fresh_state
_validate_verification_batch = click_verification.validate_batch
_verification_groups = click_verification.verification_groups
_verification_group_digest = click_verification.group_digest
_verification_group_units = click_verification.group_units
_file_content_digest = click_verification.file_content_digest
_verification_environment = click_verification.environment
_verification_environment_key = click_verification.environment_key
_verification_environment_hmac = click_verification._verification_environment_hmac
_verification_environment_binding = click_verification.environment_binding
_verification_environment_binding_digest = click_verification.environment_binding_digest
_verification_environment_binding_is_authentic = (
    click_verification.environment_binding_is_authentic
)
_verification_host_coverage_binding_digest = (
    click_verification.host_coverage_binding_digest
)
_verification_host_coverage_binding_is_authentic = (
    click_verification.host_coverage_binding_is_authentic
)
_verification_environment_from_binding = click_verification.environment_from_binding
_executable_search_path = click_verification._executable_search_path
_verification_executable_records = click_verification.executable_records
_verification_executable_payload = click_verification.executable_payload
_verification_environment_digest_from_records = (
    click_verification.environment_digest_from_records
)
_verification_environment_digest = click_verification.environment_digest
_verification_receipt_matches = click_verification.receipt_matches
_dependency_declarations = click_verification.dependency_declarations
_dependency_receipt_is_valid = click_verification.dependency_receipt_is_valid
_dependency_receipt_matches = click_verification.dependency_receipt_matches
_clear_dependency_receipt = click_verification.clear_dependency_receipt
_store_dependency_receipt = click_verification.store_dependency_receipt
_promote_dependency_receipt = click_verification.promote_dependency_receipt
_contains_deep_verification_marker = (
    click_verification._contains_deep_verification_marker
)
_arguments_have_filter = click_verification._arguments_have_filter
_verification_targets = click_verification._verification_targets
_scope_with_kind_floor = click_verification._scope_with_kind_floor
_minimum_test_runner_class = click_verification._minimum_test_runner_class
_minimum_verification_class = click_verification.minimum_class
_is_recognized_verification_tokens = click_verification.is_recognized_tokens
_is_recognized_verification_command = click_verification.is_recognized_command
_git_capture = click_verification.git_capture
_hash_workspace_path = click_verification.hash_workspace_path
_git_workspace_snapshot = click_verification.git_workspace_snapshot
_new_untracked_is_suspicious = click_verification.new_untracked_is_suspicious


CONTROL_COMMAND = "click-gate"
CLICK_AUTHORIZATION_PATTERNS = (
    re.compile(r"(?i:@click)[ \t]+(?P<action>(?i:bypass|cancel))"),
    re.compile(
        r"\[(?i:@click)\]\(plugin://click@click\)[ \t]+"
        r"(?P<action>(?i:bypass|cancel))"
    ),
)
STRING_FIELDS = click_contract.STRING_FIELDS
OBJECT_FIELDS = click_contract.OBJECT_FIELDS
CONTRACT_FIELDS = click_contract.CONTRACT_FIELDS
BOUNDARY_FIELDS = click_contract.BOUNDARY_FIELDS
BUILD_FIELDS = click_contract.BUILD_FIELDS
VERIFICATION_FIELDS = click_contract.VERIFICATION_FIELDS
EVIDENCE_SOURCE_FIELDS = click_contract.EVIDENCE_SOURCE_FIELDS
DONE_WHEN_FIELDS = click_contract.DONE_WHEN_FIELDS
EVIDENCE_KINDS = click_evidence.EVIDENCE_KINDS
EVIDENCE_STATUSES = click_evidence.EVIDENCE_STATUSES
EVIDENCE_ID_PATTERN = click_contract.EVIDENCE_ID_PATTERN
CONTRACT_ID_PATTERN = re.compile(r"^ctr_[0-9a-f]{32}$")
VERIFICATION_SCALES = click_verification_policy.VERIFICATION_SCALES
VERIFICATION_UNIT_LIMITS = click_verification_policy.VERIFICATION_UNIT_LIMITS
CAPABILITY_PROTOCOL_VERSION = click_capability.PROTOCOL_VERSION
VERIFICATION_PROTOCOL_VERSION = click_verification.PROTOCOL_VERSION
CONTRACT_STATE_SCHEMA_VERSION = 2
INSPECTION_REQUEST_FIELDS = click_inspection.REQUEST_FIELDS
MUTATION_REQUEST_FIELDS = click_mutation.REQUEST_FIELDS
SERVICE_REQUEST_FIELDS = click_service.SERVICE_REQUEST_FIELDS
VERIFICATION_BATCH_FIELDS = click_verification.BATCH_FIELDS
VERIFICATION_CHECK_FIELDS = click_verification.CHECK_FIELDS
EVIDENCE_RESULT_FIELDS = {"version", "evidence_id"}
VERIFICATION_CLASSES = click_verification.VERIFICATION_CLASSES
PYTHON_VERIFICATION_MODULES = click_verification.PYTHON_VERIFICATION_MODULES
DEEP_VERIFICATION_EXECUTABLES = click_verification.DEEP_VERIFICATION_EXECUTABLES
DEEP_VERIFICATION_MARKERS = click_verification.DEEP_VERIFICATION_MARKERS
MAX_INSPECTION_COMMANDS = click_inspection.MAX_COMMANDS
MAX_ARGV_ITEMS = click_capability.MAX_ARGV_ITEMS
MAX_OBSERVATION_OUTPUT_BYTES = click_observation.MAX_OUTPUT_BYTES
MAX_OBSERVATION_ENTRIES = click_observation.MAX_ENTRIES
MAX_BROWSER_UNIQUE_INPUTS = click_browser.MAX_UNIQUE_INPUTS
# Compatibility names for callers that previously treated these advisory
# thresholds as hard maxima.
MAX_BROWSER_TOOL_TIMEOUT_MS = (
    click_browser_advisory.RECOMMENDED_BROWSER_TOOL_TIMEOUT_MS
)
MAX_BROWSER_WAIT_MS = click_browser_advisory.RECOMMENDED_BROWSER_WAIT_MS
BROWSER_RUNNING_TTL_SECONDS = click_browser.RUNNING_TTL_SECONDS
OBSERVATION_RESERVATION_TTL_SECONDS = click_observation.RESERVATION_TTL_SECONDS
MUTATION_RUNNING_TTL_SECONDS = click_mutation.RUNNING_TTL_SECONDS
VERIFY_RUNNING_TTL_SECONDS = click_verification.RUNNING_TTL_SECONDS
EPHEMERAL_STATE_TTL_SECONDS = 7 * 24 * 60 * 60
COMPLETED_CONTRACT_TTL_SECONDS = 30 * 24 * 60 * 60
DEFAULT_MODES = {"on", "manual"}
SHELL_EXECUTABLES = click_capability.SHELL_EXECUTABLES
PROCESS_CONTROL_EXECUTABLES = click_capability.PROCESS_CONTROL_EXECUTABLES

BROWSER_TOOL_NAMES = click_host_coverage.CODEX_BROWSER_TOOL_NAMES
BROWSER_WAIT_PATTERNS = click_browser_advisory.BROWSER_WAIT_PATTERNS
MANAGED_SERVICE_EXECUTABLES = click_service.MANAGED_SERVICE_EXECUTABLES
MANAGED_SERVICE_ACTIONS = click_service.MANAGED_SERVICE_ACTIONS
MANAGED_SERVICE_SCRIPT_MARKERS = click_service.MANAGED_SERVICE_SCRIPT_MARKERS
SERVICE_START_TIMEOUT_SECONDS = click_service.SERVICE_START_TIMEOUT_SECONDS
SERVICE_STOP_TIMEOUT_SECONDS = click_service.SERVICE_STOP_TIMEOUT_SECONDS
MANAGED_SERVICE_MAX_SECONDS = click_service.MANAGED_SERVICE_MAX_SECONDS

VERIFICATION_EXECUTABLES = click_verification.VERIFICATION_EXECUTABLES
VERIFICATION_NAME_MARKERS = click_verification.VERIFICATION_NAME_MARKERS
TEST_TARGET_SUFFIXES = click_verification.TEST_TARGET_SUFFIXES
TEST_FILTER_OPTIONS = click_verification.TEST_FILTER_OPTIONS
TEST_OPTIONS_WITH_VALUES = click_verification.TEST_OPTIONS_WITH_VALUES
NEW_SOURCE_PATH_SEGMENTS = click_verification.NEW_SOURCE_PATH_SEGMENTS
READ_ONLY_COMMANDS = click_inspection.READ_ONLY_COMMANDS
READ_ONLY_GIT_SUBCOMMANDS = click_inspection.READ_ONLY_GIT_SUBCOMMANDS
GIT_DIFF_RENDERING_SUBCOMMANDS = click_inspection.GIT_DIFF_RENDERING_SUBCOMMANDS
GIT_GLOBAL_ALLOWED_PREFIXES = click_inspection.GIT_GLOBAL_ALLOWED_PREFIXES
GIT_GLOBAL_REJECTED_OPTIONS = click_inspection.GIT_GLOBAL_REJECTED_OPTIONS
GIT_READ_ONLY_EXACT_OPTIONS = click_inspection.GIT_READ_ONLY_EXACT_OPTIONS
GIT_READ_ONLY_OPTION_PREFIXES = click_inspection.GIT_READ_ONLY_OPTION_PREFIXES
SHELL_CONTROL_PUNCTUATION = click_capability.SHELL_CONTROL_PUNCTUATION
SED_READ_SCRIPT = click_inspection.SED_READ_SCRIPT


_OUTPUT_ADAPTER: HookOutputAdapter = CodexOutputAdapter()


def _set_output_adapter(adapter: HookOutputAdapter) -> HookOutputAdapter:
    """Select a host serializer and return the previous serializer."""
    global _OUTPUT_ADAPTER
    previous = _OUTPUT_ADAPTER
    _OUTPUT_ADAPTER = adapter
    return previous

RG_OPTIONS_WITH_VALUES = click_inspection.RG_OPTIONS_WITH_VALUES
ENVIRONMENT_ASSIGNMENT = click_capability.ENVIRONMENT_ASSIGNMENT
SSH_TARGET = click_inspection.SSH_TARGET
SSH_READ_ONLY_GIT_SUBCOMMANDS = click_inspection.SSH_READ_ONLY_GIT_SUBCOMMANDS
GIT_REMOTE_NAME = click_inspection.GIT_REMOTE_NAME


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _deny(reason: str) -> None:
    _emit(_OUTPUT_ADAPTER.deny(reason))


def _advise(value: str) -> None:
    _emit(_OUTPUT_ADAPTER.advisory(value))


def _allow_rewritten(command: str) -> None:
    _emit(_OUTPUT_ADAPTER.allow(command))


def _allow_rewritten_with_advisory(command: str, value: str) -> None:
    _emit(_OUTPUT_ADAPTER.allow_with_advisory(command, value))


def _read_event() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid hook input: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("hook input must be a JSON object")
    return value


def _write_state(event: dict[str, Any], status: str, contract_digest: str = "") -> None:
    payload = {
        "status": status,
        "contract_digest": contract_digest,
        "updated_at": int(time.time()),
    }
    _write_json(_state_path(event), payload)


def _read_state(event: dict[str, Any]) -> dict[str, Any]:
    path = _state_path(event)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"status": "idle"}
    return value if isinstance(value, dict) else {"status": "idle"}


def _write_mode(event: dict[str, Any], mode: str) -> None:
    _write_json(
        _mode_path(event),
        {"mode": mode, "updated_at": int(time.time())},
    )


def _read_mode(event: dict[str, Any]) -> str:
    try:
        value = json.loads(_mode_path(event).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "adaptive"
    if isinstance(value, dict) and value.get("mode") in {"adaptive", "strict"}:
        return str(value["mode"])
    return "adaptive"


def _write_default_mode(mode: str) -> None:
    if mode not in DEFAULT_MODES:
        raise ValueError(f"unsupported Click default mode: {mode}")
    _write_json(
        _preference_path(),
        {"default_mode": mode, "updated_at": int(time.time())},
    )


def _read_default_mode() -> str:
    try:
        value = json.loads(_preference_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "unset"
    if isinstance(value, dict) and value.get("default_mode") in DEFAULT_MODES:
        return str(value["default_mode"])
    return "unset"





def _evidence_sources(state: dict[str, Any]) -> dict[str, Any] | None:
    """Return the v1 prose-free evidence ledger, or None for legacy state."""
    return click_evidence.sources_from_state(
        state,
        expected_contract_schema_version=CONTRACT_STATE_SCHEMA_VERSION,
    )




def _write_contract_state(
    event: dict[str, Any], status: str, digest: str, contract: dict[str, Any]
) -> str:
    contract_id = f"ctr_{secrets.token_hex(16)}"
    _write_json(
        _contract_path(event),
        {
            "state_schema_version": CONTRACT_STATE_SCHEMA_VERSION,
            "status": status,
            "contract_digest": digest,
            "contract_id": contract_id,
            "staged_turn_id": str(event.get("turn_id", "")),
            "approved_turn_id": "",
            "verification": _fresh_verification_state(contract),
            "evidence_state": _fresh_evidence_state(contract),
            "external_evidence": _fresh_external_evidence_state(contract),
            "observations": _fresh_observation_state(),
            "mutation": _fresh_mutation_state(),
            "service": _fresh_service_state(),
            "updated_at": int(time.time()),
        },
    )
    return contract_id


def _contract_id_from_state(state: dict[str, Any]) -> str:
    digest = state.get("contract_digest")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return ""
    contract_id = state.get("contract_id")
    if "contract_id" in state:
        return (
            contract_id
            if isinstance(contract_id, str)
            and CONTRACT_ID_PATTERN.fullmatch(contract_id)
            else ""
        )
    # Compatibility only for a staged or incomplete state created before ids existed.
    return f"ctr_{digest[:32]}"


def _read_contract_state(event: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(_contract_path(event).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"status": "none", "contract_digest": ""}
    return value if isinstance(value, dict) else {"status": "none", "contract_digest": ""}


def _clear_contract_state(event: dict[str, Any]) -> None:
    try:
        _contract_path(event).unlink()
    except OSError:
        pass


def _save_contract_state(event: dict[str, Any], state: dict[str, Any]) -> None:
    state["updated_at"] = int(time.time())
    _write_json(_contract_path(event), state)


def _prompt_authorization(prompt: Any) -> str:
    if not isinstance(prompt, str) or not prompt:
        return ""
    first_line = prompt.splitlines()[0].strip() if prompt.splitlines() else ""
    for pattern in CLICK_AUTHORIZATION_PATTERNS:
        match = pattern.fullmatch(first_line)
        if match:
            return match.group("action").lower()
    return ""


def _record_user_prompt(event: dict[str, Any]) -> str:
    turn_id = str(event.get("turn_id", ""))
    if not turn_id:
        raise ValueError("Click requires the Codex turn_id on UserPromptSubmit")
    authorization = _prompt_authorization(event.get("prompt", ""))
    _write_json(
        _prompt_path(event),
        {
            "turn_id": turn_id,
            "authorization": authorization,
            "updated_at": int(time.time()),
        },
    )
    return authorization


def _read_user_prompt_state(event: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(_prompt_path(event).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_user_prompt_turn(event: dict[str, Any]) -> str:
    return str(_read_user_prompt_state(event).get("turn_id", ""))


def _consume_user_authorization(event: dict[str, Any], expected: str) -> str:
    turn_id = str(event.get("turn_id", ""))
    if not turn_id:
        return f"Click {expected} requires a current Codex turn_id."
    state = _read_user_prompt_state(event)
    if str(state.get("turn_id", "")) != turn_id:
        return (
            f"Click {expected} requires a recognized first-line Click directive "
            "or trusted `plugin://click@click` autocomplete mention in this user turn."
        )
    if state.get("authorization") != expected:
        return (
            f"Click {expected} requires a recognized first-line Click directive "
            "or trusted `plugin://click@click` autocomplete mention in this user turn."
        )
    state["authorization"] = ""
    state["updated_at"] = int(time.time())
    _write_json(_prompt_path(event), state)
    return ""


def _active_prompt_turn_error(event: dict[str, Any]) -> str:
    turn_id = str(event.get("turn_id", ""))
    if not turn_id:
        return "Click cannot prove approval because this tool call has no Codex turn_id."
    if _read_user_prompt_turn(event) != turn_id:
        return (
            "Click can stage or approve a contract only in a turn that began with a "
            "UserPromptSubmit event. Ask the user to respond, then retry in that turn."
        )
    return ""


def _contract_is_completed(state: dict[str, Any]) -> bool:
    if state.get("status") != "approved":
        return False
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return False
    revision = int(verification.get("mutation_revision", 0))
    sources = _evidence_sources(state)
    if sources is None:
        # Compatibility for an active contract staged before the evidence ledger existed.
        local_verification_passed = bool(
            verification.get("status") == "passed"
            and int(verification.get("verified_revision", -1)) == revision
        )
        if not local_verification_passed:
            return False
        external = state.get("external_evidence")
        if isinstance(external, dict) and external.get("browser_required") is True:
            if external.get("browser_status") != "passed":
                return False
    else:
        if not sources or any(
            not _evidence_is_current(source, revision)
            for source in sources.values()
        ):
            return False
    service = state.get("service")
    if isinstance(service, dict) and service.get("status") in {
        "starting",
        "launching",
        "running",
        "stopping",
    }:
        return False
    return True


def _approved_contract_is_active(state: dict[str, Any]) -> bool:
    return bool(
        state.get("status") == "approved"
        and not _contract_is_completed(state)
    )


def _session_contract_is_active(state: dict[str, Any]) -> bool:
    return bool(
        state.get("status") == "staged"
        or _approved_contract_is_active(state)
    )


def _mark_contract_mutated(event: dict[str, Any]) -> str:
    return click_mutation.mark_contract_mutated(
        event,
        expected_contract_schema_version=CONTRACT_STATE_SCHEMA_VERSION,
        observation_is_running=_observation_is_running,
        workspace_snapshot=_git_workspace_snapshot,
    )


def _prune_state() -> None:
    root = _state_root()
    if not root.exists():
        return
    now = time.time()
    for candidate in root.glob("*.json"):
        try:
            age = now - candidate.stat().st_mtime
        except (OSError, RuntimeError):
            continue
        ttl = EPHEMERAL_STATE_TTL_SECONDS
        if candidate.name.startswith("session-contract-"):
            try:
                value = json.loads(candidate.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                value = {}
            if isinstance(value, dict) and _session_contract_is_active(value):
                continue
            if isinstance(value, dict) and _contract_is_completed(value):
                ttl = COMPLETED_CONTRACT_TTL_SECONDS
        if age <= ttl:
            continue
        try:
            candidate.unlink()
        except OSError:
            continue




def _validate_mutation_request(raw: str) -> tuple[dict[str, Any] | None, str]:
    return click_mutation.validate_request(
        raw,
        validate_argv=_validate_argv,
        looks_like_managed_service=_looks_like_managed_service,
        protocol_version=CAPABILITY_PROTOCOL_VERSION,
    )

def _validate_service_request(raw: str) -> tuple[dict[str, Any] | None, str]:
    return click_service.validate_request(
        raw,
        validate_argv=_validate_argv,
        protocol_version=CAPABILITY_PROTOCOL_VERSION,
    )




def _validate_evidence_result(raw: str) -> tuple[str, str]:
    value, error = _decode_capability_request(raw, "Evidence completion")
    if error:
        return "", error
    assert value is not None
    unknown = sorted(set(value) - EVIDENCE_RESULT_FIELDS)
    if unknown:
        rendered = ", ".join(f"`{field}`" for field in unknown)
        return "", f"Evidence completion contains unsupported field(s): {rendered}."
    evidence_id = value.get("evidence_id")
    if not isinstance(evidence_id, str) or not EVIDENCE_ID_PATTERN.fullmatch(
        evidence_id
    ):
        return "", "Evidence completion `evidence_id` must name one declared source."
    return evidence_id, ""




def _control_request(command: str) -> tuple[str | None, str, str]:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        return None, "", f"Malformed {CONTROL_COMMAND} command: {exc}."
    if not tokens or tokens[0] != CONTROL_COMMAND:
        return None, "", ""
    if len(tokens) == 2 and tokens[1] in {"arm", "bypass", "cancel", "review"}:
        return tokens[1], "", ""
    if len(tokens) == 3 and tokens[1] == "default" and tokens[2] in {
        "on",
        "manual",
        "status",
    }:
        return "default", tokens[2], ""
    if len(tokens) == 3 and tokens[1] == "mode" and tokens[2] in {
        "adaptive",
        "strict",
    }:
        return "mode", tokens[2], ""
    if len(tokens) == 3 and tokens[1] in {
        "evidence",
        "inspect",
        "mutate",
        "service",
        "stage",
        "pass",
        "verify",
    }:
        return tokens[1], tokens[2], ""
    return (
        "",
        "",
        f"Use `{CONTROL_COMMAND} arm`, `{CONTROL_COMMAND} stage '<Execution Contract "
        f"JSON>'`, `{CONTROL_COMMAND} pass <contract_id>`, "
        f"`{CONTROL_COMMAND} inspect '<Inspection JSON>'`, "
        f"`{CONTROL_COMMAND} mutate '<Mutation JSON>'`, "
        f"`{CONTROL_COMMAND} service '<Managed Service JSON>'`, "
        f"`{CONTROL_COMMAND} evidence '<Evidence Completion JSON>'`, "
        f"`{CONTROL_COMMAND} verify '<Verification Batch JSON>'`, "
        f"`{CONTROL_COMMAND} review`, `{CONTROL_COMMAND} bypass`, "
        f"`{CONTROL_COMMAND} cancel`, "
        f"`{CONTROL_COMMAND} default on|manual|status`, or "
        f"`{CONTROL_COMMAND} mode adaptive|strict`.",
    )







def _windows_shell_quote(argument: str) -> str:
    """Quote one argv item for cmd.exe while preserving CRT argv decoding."""
    if any(character in argument for character in ("\0", "\r", "\n")):
        raise ValueError("Click runner arguments cannot contain control characters.")
    result = ['"']
    backslashes = 0
    for character in argument:
        if character == "\\":
            backslashes += 1
            continue
        if character == '"':
            result.append("\\" * (backslashes * 2 + 1))
            result.append('"')
            backslashes = 0
            continue
        if backslashes:
            result.append("\\" * backslashes)
            backslashes = 0
        result.append(character)
    if backslashes:
        result.append("\\" * (backslashes * 2))
    result.append('"')
    return "".join(result)


MAX_RUNNER_TRANSPORT_BYTES = 24_000
WINDOWS_COMMAND_LINE_LIMIT = 8_191


def _encode_runner_transport(arguments: list[str]) -> str:
    raw = json.dumps(arguments, ensure_ascii=False, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(zlib.compress(raw, level=9)).decode()


def _decode_runner_transport(encoded: str) -> tuple[list[str] | None, str]:
    try:
        compressed = base64.b64decode(
            encoded.encode(), altchars=b"-_", validate=True
        )
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(compressed, MAX_RUNNER_TRANSPORT_BYTES + 1)
        if (
            len(raw) > MAX_RUNNER_TRANSPORT_BYTES
            or not decompressor.eof
            or decompressor.unconsumed_tail
            or decompressor.unused_data
        ):
            return None, "Click runner transport exceeded its bounded payload."
        value = json.loads(raw.decode())
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError, zlib.error):
        return None, "Click runner transport was malformed."
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or "\x00" in item for item in value)
    ):
        return None, "Click runner transport did not contain a valid argv list."
    return value, ""


def _windows_launcher_path_is_safe(value: str) -> bool:
    # Arguments after the launcher are encoded. These characters remain unsafe
    # in the two launcher paths because cmd.exe and PowerShell expand them even
    # inside double quotes under some configurations.
    return not any(character in value for character in ("%", "!", "$", "`"))


def _runner_shell_command(arguments: list[str]) -> str:
    if os.name == "nt":
        if len(arguments) < 3 or not all(
            _windows_launcher_path_is_safe(argument) for argument in arguments[:2]
        ):
            return "exit 2"
        transported = [
            arguments[1],
            "--encoded-runner",
            _encode_runner_transport(arguments[2:]),
        ]
        # hooks.json already requires the Windows py launcher. Reuse its bare
        # command form here so the rewritten runner is valid in both cmd.exe
        # and PowerShell; a quoted executable path in command position is only
        # an expression in PowerShell unless prefixed with its call operator.
        command = "py -3 " + " ".join(
            _windows_shell_quote(argument) for argument in transported
        )
        if len(command) > WINDOWS_COMMAND_LINE_LIMIT:
            return "exit 2"
        return command
    return shlex.join(arguments)


def _stateful_runner_prefix(action: str) -> list[str]:
    """Bind a rewritten runner to the state root selected by the Hook process."""
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "--state-root",
        str(_state_root().resolve()),
        action,
    ]


def _observation_runner_command(
    state_path: Path, request: dict[str, Any], request_digest: str, runner_token: str
) -> str:
    return click_observation.runner_command(
        state_path,
        request,
        request_digest,
        runner_token,
        runner_script=Path(__file__).resolve(),
        render_command=_runner_shell_command,
    )


def _prepare_observation(
    event: dict[str, Any],
    request: dict[str, Any],
    broad_inventory: bool,
    *,
    review: bool = False,
) -> tuple[str, str, str]:
    return click_observation.prepare(
        event,
        request,
        broad_inventory,
        review=review,
        mutation_is_running=_mutation_is_running,
        fresh_mutation_state=_fresh_mutation_state,
        runner_script=Path(__file__).resolve(),
        render_command=_runner_shell_command,
    )


def _inspection_once_runner_command(request: dict[str, Any]) -> str:
    return click_inspection.runner_command(
        request,
        runner_script=Path(__file__).resolve(),
        render_command=_runner_shell_command,
    )


def _mutation_runner_command(
    event: dict[str, Any], request: dict[str, Any], request_digest: str, runner_token: str
) -> str:
    return click_mutation.runner_command(
        event,
        request,
        request_digest,
        runner_token,
        runner_script=Path(__file__).resolve(),
        render_command=_runner_shell_command,
    )


def _prepare_mutation(event: dict[str, Any], raw: str) -> tuple[str, str]:
    return click_mutation.prepare(
        event,
        raw,
        validate_argv=_validate_argv,
        looks_like_managed_service=_looks_like_managed_service,
        protocol_version=CAPABILITY_PROTOCOL_VERSION,
        expected_contract_schema_version=CONTRACT_STATE_SCHEMA_VERSION,
        observation_is_running=_observation_is_running,
        workspace_snapshot=_git_workspace_snapshot,
        runner_script=Path(__file__).resolve(),
        render_command=_runner_shell_command,
    )

def _service_runner_command(
    event: dict[str, Any],
    request: dict[str, Any],
    service_id: str,
    runner_token: str = "",
) -> str:
    return click_service.service_runner_command(
        event,
        request,
        service_id,
        runner_token=runner_token,
        runner_script=Path(__file__).resolve(),
        render_command=_runner_shell_command,
    )


def _prepare_service(event: dict[str, Any], raw: str) -> tuple[str, str]:
    return click_service.prepare_service(
        event,
        raw,
        validate_argv=_validate_argv,
        protocol_version=CAPABILITY_PROTOCOL_VERSION,
        mark_contract_mutated=_mark_contract_mutated,
        runner_script=Path(__file__).resolve(),
        render_command=_runner_shell_command,
    )


def _verification_runner_command(
    event: dict[str, Any], batch: dict[str, Any], batch_digest: str, runner_token: str
) -> str:
    return click_verification.runner_command(
        event,
        batch,
        batch_digest,
        runner_token,
        runner_script=Path(__file__).resolve(),
        render_command=_runner_shell_command,
    )


def _record_evidence_completion(event: dict[str, Any], raw: str) -> tuple[str, str]:
    evidence_id, error = _validate_evidence_result(raw)
    if error:
        return "", error
    state = _read_contract_state(event)
    if state.get("status") != "approved":
        return "", "Approve the staged Click execution contract before recording evidence."
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return "", "Click verification state is unavailable; stage and approve again."
    if verification.get("status") == "running":
        return "", "Wait for the final argv verification batch before recording evidence."
    mutation = state.get("mutation")
    if _mutation_is_running(mutation):
        return "", "Wait for the structured Click mutation before recording evidence."

    sources = _evidence_sources(state)
    if sources is None:
        return (
            "",
            "This active contract predates evidence-id completion tracking. Cancel it, "
            "stage the proposal again, and obtain fresh approval.",
        )
    if not sources:
        return "", "Click evidence state is unavailable or malformed; cancel and restage."
    source_key = _evidence_key(evidence_id)
    source = sources.get(source_key)
    if not isinstance(source, dict):
        return "", f"Evidence completion references unknown id `{evidence_id}`."
    kind = str(source.get("kind", ""))
    if kind == "argv":
        return (
            "",
            f"Evidence `{evidence_id}` has kind `argv`; execute it through "
            "`click-gate verify` instead of attesting it.",
        )

    revision = int(verification.get("mutation_revision", 0))
    if _evidence_is_current(source, revision):
        return (
            "",
            f"Evidence `{evidence_id}` already completed for the current revision; "
            "reuse it instead of recording it twice.",
        )
    if kind == "browser":
        browser_error = click_browser.finalize_evidence(
            state,
            evidence_id=evidence_id,
            source_key=source_key,
            source=source,
            revision=revision,
        )
        if browser_error:
            return "", browser_error
    elif kind not in {"hosted", "manual", "existing"}:
        return "", f"Evidence `{evidence_id}` has unsupported completion kind `{kind}`."

    source["status"] = "passed"
    source["verified_revision"] = revision
    source["attempts"] = int(source.get("attempts", 0)) + 1
    source["last_exit_code"] = 0
    _save_contract_state(event, state)
    return f"echo Click evidence {evidence_id} completed for revision {revision}", ""


def _prepare_verification(
    event: dict[str, Any], raw: str
) -> tuple[str, str, str]:
    return click_verification.prepare(
        event,
        raw,
        runner_script=Path(__file__).resolve(),
        render_command=_runner_shell_command,
        git_workspace_snapshot=_git_workspace_snapshot,
        git_capture=_git_capture,
    )



def _is_plan_tool(tool_name: str) -> bool:
    normalized = tool_name.lower().replace("::", "__").replace(".", "__")
    return normalized.split("__")[-1] == "update_plan"


def _prepare_browser_evidence(event: dict[str, Any]) -> tuple[bool, str, str]:
    return click_browser.prepare(
        event,
        expected_contract_schema_version=CONTRACT_STATE_SCHEMA_VERSION,
        contract_is_completed=_contract_is_completed,
        mutation_is_running=_mutation_is_running,
    )


def _record_mutation_boundary(event: dict[str, Any]) -> None:
    click_mutation.record_boundary(
        event,
        workspace_snapshot=_git_workspace_snapshot,
    )


def _handle_post_tool(event: dict[str, Any]) -> None:
    if str(event.get("tool_name", "")) not in BROWSER_TOOL_NAMES:
        _record_mutation_boundary(event)
        return
    click_browser.record_result(
        event,
        expected_contract_schema_version=CONTRACT_STATE_SCHEMA_VERSION,
    )


def _handle_prompt_submit(event: dict[str, Any]) -> None:
    _prune_state()
    authorization = _record_user_prompt(event)
    default_mode = _read_default_mode()
    if default_mode == "on":
        context = (
            "Click Always ON is enabled. For software creation, modification, deletion, "
            "or repair, compile the compact Click contract, explain it plainly, ask once, "
            "and do not pass or mutate until a later UserPromptSubmit turn approves the "
            "staged contract_id. Questions, "
            "explanations, and simple read-only inspection do not need a contract. For a "
            "read-only code review, run `click-gate review` before shell reads/searches; "
            "do not stage a build contract, reuse exact successful evidence, and prefer "
            "focused follow-up after broad repository context. During review or approved "
            "implementation use versioned `click-gate inspect`, `click-gate mutate`, and "
            "`click-gate verify` version-2 evidence-bound argv requests when direct Bash "
            "intent is ambiguous; use `click-gate evidence` to finalize an observed "
            "Browser source or attest a collected hosted, manual, or existing source; use "
            "`click-gate service` start/stop for a recognizable long-running local server. "
            "Browser MCP work requires one referenced verification evidence source with "
            "kind `browser`; calls remain serial and receipt-bound while repeat and timing "
            "guidance is advisory. Use "
            "`click-gate bypass` only when the user explicitly opts out for the current turn."
        )
    elif default_mode == "manual":
        context = (
            "Click Manual mode is enabled. Apply the Click contract workflow only when "
            "the user explicitly selects @Click or $click. Ordinary software work and "
            "code review remain fail-open unless explicitly activated. Once activated, a "
            "staged or incomplete approved session contract remains mutation-locked across "
            "later turns. Stage the contract JSON once, then pass only its emitted "
            "contract_id after a later UserPromptSubmit turn. Approved Browser evidence is "
            "metered and long-running "
            "local servers use `click-gate service` start/stop."
        )
    else:
        context = (
            "Click is installed but its default mode is unset. Do not interrupt questions, "
            "explanations, code review, or simple read-only inspection. Before the first "
            "software creation, modification, deletion, or repair, ask once whether to use "
            "Always ON (recommended) or Manual. After the answer, run `click-gate default "
            "on` or `click-gate default manual`. Always ON gates later mutations behind one "
            "compact approval; Manual applies Click only when explicitly selected."
        )
    contract_state = _read_contract_state(event)
    contract_id = _contract_id_from_state(contract_state)
    contract_status = contract_state.get("status")
    contract_completed = _contract_is_completed(contract_state)
    contract_sources = (
        _evidence_sources(contract_state)
        if contract_status in {"staged", "approved"}
        else {}
    )
    if (
        contract_status in {"staged", "approved"}
        and not contract_completed
        and contract_sources is None
    ):
        context += (
            " The active contract predates evidence-id completion tracking and cannot "
            "be resumed safely. Do not pass it. Ask the user to start a turn with "
            "`@Click cancel`, run `click-gate cancel`, then stage and approve a fresh "
            "contract."
        )
    elif (
        contract_status in {"staged", "approved"}
        and not contract_completed
        and not contract_sources
    ):
        context += (
            " The active contract evidence state is unavailable or malformed. Do not "
            "pass it. Ask the user to start a turn with `@Click cancel`, run "
            "`click-gate cancel`, then stage and approve a fresh contract."
        )
    elif contract_status == "staged" and contract_id:
        context += (
            f" The active staged contract_id is `{contract_id}`. Treat that id as the "
            "approval target. If and only if this user response explicitly approves the "
            f"shown proposal, pass it with `click-gate pass {contract_id}`; never resend "
            "the contract JSON."
        )
    elif _approved_contract_is_active(contract_state) and contract_id:
        context += (
            f" The incomplete approved contract_id is `{contract_id}`. To resume its "
            f"implementation in this turn, use `click-gate pass {contract_id}` after "
            "arming when Manual mode requires it; do not restage or resend the JSON."
        )
    if authorization:
        context += (
            f" The user's exact first-line `@Click {authorization}` directive authorizes "
            f"one `click-gate {authorization}` in this turn only. Do not reuse that "
            "authorization in another tool call or later turn."
        )
    _emit(_OUTPUT_ADAPTER.context(context))


def _handle_session_end(event: dict[str, Any]) -> None:
    _request_service_stop(event)


def _handle_pre_tool(event: dict[str, Any]) -> None:
    tool_name = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

    if tool_name in BROWSER_TOOL_NAMES:
        handled, browser_error, browser_advisory = _prepare_browser_evidence(event)
        if handled and browser_error:
            _deny(browser_error)
        elif handled and browser_advisory:
            _advise(browser_advisory)
        return

    if tool_name == "Bash":
        action, value, control_error = _control_request(str(command))
        if action is not None:
            if control_error:
                _deny(control_error)
                return
            if action == "arm":
                _prune_state()
                _clear_review_state(event)
                _write_state(event, "armed")
                _allow_rewritten("echo Click mutation gate armed")
                return
            if action == "bypass":
                _prune_state()
                authorization_error = _consume_user_authorization(event, "bypass")
                if authorization_error:
                    _deny(authorization_error)
                    return
                _write_state(event, "bypassed")
                _clear_review_state(event)
                _allow_rewritten("echo Click bypassed for this turn")
                return
            if action == "cancel":
                _prune_state()
                authorization_error = _consume_user_authorization(event, "cancel")
                if authorization_error:
                    _deny(authorization_error)
                    return
                _request_service_stop(event)
                _clear_contract_state(event)
                _clear_review_state(event)
                _write_state(event, "idle")
                _allow_rewritten("echo Click active contract cancelled")
                return
            if action == "review":
                _prune_state()
                current_status = _read_state(event).get("status")
                if current_status in {"armed", "staged", "passed"}:
                    _deny(
                        "Click cannot enter read-only review mode while a build contract "
                        "is active in this turn. Finish or explicitly bypass that workflow."
                    )
                    return
                _write_review_state(event)
                _write_state(event, "review")
                _allow_rewritten("echo Click read-only review guard armed")
                return
            if action == "default":
                _prune_state()
                if value == "status":
                    current = _read_default_mode()
                    _allow_rewritten(f"echo Click default mode: {current}")
                    return
                _write_default_mode(value)
                label = "Always ON" if value == "on" else "Manual"
                _allow_rewritten(f"echo Click default mode set to {label}")
                return
            if action == "mode":
                _prune_state()
                _write_mode(event, value)
                if value == "adaptive":
                    _write_state(event, "idle")
                _allow_rewritten(f"echo Click mode set to {value}")
                return
            if action == "evidence":
                current_status = _read_state(event).get("status")
                if current_status != "passed" and _read_mode(event) != "strict":
                    _deny(
                        "Pass the approved Click execution contract before recording "
                        "its declared completion evidence."
                    )
                    return
                rewritten, evidence_error = _record_evidence_completion(event, value)
                if evidence_error:
                    _deny(evidence_error)
                    return
                _allow_rewritten(rewritten)
                return
            if action == "inspect":
                request, broad_inventory, inspection_error = (
                    _validate_inspection_request(value)
                )
                if inspection_error:
                    _deny(inspection_error)
                    return
                assert request is not None
                current_status = _read_state(event).get("status")
                approved_session_active = _approved_contract_is_active(
                    _read_contract_state(event)
                )
                if current_status == "review":
                    (
                        rewritten,
                        inspection_error,
                        inspection_advisory,
                    ) = _prepare_observation(
                        event, request, broad_inventory, review=True
                    )
                    if inspection_error:
                        _deny(inspection_error)
                        return
                elif current_status == "passed" or approved_session_active:
                    (
                        rewritten,
                        inspection_error,
                        inspection_advisory,
                    ) = _prepare_observation(
                        event, request, broad_inventory
                    )
                    if inspection_error:
                        _deny(inspection_error)
                        return
                else:
                    rewritten = _inspection_once_runner_command(request)
                    inspection_advisory = ""
                if inspection_advisory:
                    _allow_rewritten_with_advisory(rewritten, inspection_advisory)
                else:
                    _allow_rewritten(rewritten)
                return
            if action == "mutate":
                current_status = _read_state(event).get("status")
                if current_status != "passed" and _read_mode(event) != "strict":
                    _deny(
                        "Pass the approved Click execution contract in the current turn "
                        "before starting a structured mutation."
                    )
                    return
                rewritten, mutation_error = _prepare_mutation(event, value)
                if mutation_error:
                    _deny(mutation_error)
                    return
                _allow_rewritten(rewritten)
                return
            if action == "service":
                current_status = _read_state(event).get("status")
                if current_status != "passed" and _read_mode(event) != "strict":
                    _deny(
                        "Pass the approved Click execution contract in the current turn "
                        "before managing its local development service."
                    )
                    return
                rewritten, service_error = _prepare_service(event, value)
                if service_error:
                    _deny(service_error)
                    return
                _allow_rewritten(rewritten)
                return
            if action == "verify":
                current_status = _read_state(event).get("status")
                if current_status != "passed" and _read_mode(event) != "strict":
                    _deny(
                        "Pass the approved Click execution contract in the current turn "
                        "before starting its final verification batch."
                    )
                    return
                (
                    rewritten,
                    verification_error,
                    verification_advisory,
                ) = _prepare_verification(event, value)
                if verification_error:
                    _deny(verification_error)
                    return
                if verification_advisory:
                    _allow_rewritten_with_advisory(
                        rewritten, verification_advisory
                    )
                else:
                    _allow_rewritten(rewritten)
                return
            if action in {"stage", "pass"}:
                contract: dict[str, Any] | None = None
                digest = ""
                if action == "stage":
                    contract, validation_error = _validate_contract(value)
                    if validation_error:
                        _deny(validation_error)
                        return
                    assert contract is not None
                    canonical = json.dumps(
                        contract, sort_keys=True, separators=(",", ":")
                    )
                    digest = hashlib.sha256(canonical.encode()).hexdigest()
                elif not CONTRACT_ID_PATTERN.fullmatch(value):
                    if value.lstrip().startswith("{"):
                        _deny(
                            "Click pass accepts the staged `contract_id`, not the Execution "
                            "Contract JSON. Use `click-gate pass ctr_<32 hex characters>` "
                            "after the later approval response."
                        )
                    else:
                        _deny(
                            "Click `contract_id` must use `ctr_` followed by exactly 32 "
                            "lowercase hexadecimal characters."
                        )
                    return
                _prune_state()

                current_status = _read_state(event).get("status")
                strict = _read_mode(event) == "strict"
                always_on = _read_default_mode() == "on"
                prompt_turn_error = _active_prompt_turn_error(event)
                if prompt_turn_error:
                    _deny(prompt_turn_error)
                    return
                current_turn_id = str(event.get("turn_id", ""))
                if action == "stage":
                    if (
                        current_status not in {"armed", "staged", "passed"}
                        and not strict
                        and not always_on
                    ):
                        _deny(
                            "Arm Click before staging the execution contract for approval."
                        )
                        return
                    existing_contract = _read_contract_state(event)
                    if (
                        existing_contract.get("status") == "staged"
                        and existing_contract.get("contract_digest") == digest
                    ):
                        existing_id = _contract_id_from_state(existing_contract)
                        _deny(
                            "The identical Click execution contract is already staged. "
                            f"Its contract_id is `{existing_id}`; pass that id after the "
                            "user's approval instead of staging it again."
                        )
                        return
                    if (
                        existing_contract.get("status") == "staged"
                        and existing_contract.get("staged_turn_id") == current_turn_id
                    ):
                        _deny(
                            "Click already staged a contract in this user turn. Show that "
                            "exact proposal and wait; a revised contract may be staged only "
                            "after the user's next response."
                        )
                        return
                    if (
                        existing_contract.get("status") == "approved"
                        and not _contract_is_completed(existing_contract)
                    ):
                        _deny(
                            "Click is already executing one approved contract. Do not restage, "
                            "replan, or replace it mid-run. Finish every declared source for "
                            "its current revision before staging the next contract. If the "
                            "approved outcome or authority is no longer sufficient, stop and "
                            "report the blocker."
                        )
                        return
                    contract_id = _write_contract_state(
                        event, "staged", digest, contract
                    )
                    _write_state(event, "staged", digest)
                    _allow_rewritten(f"echo CLICK_CONTRACT_ID={contract_id}")
                    return

                if current_status != "armed" and not strict and not always_on:
                    _deny(
                        "Arm Click in the current turn before passing the approved "
                        "execution contract."
                    )
                    return
                staged = _read_contract_state(event)
                if staged.get("status") not in {"staged", "approved"}:
                    _deny(
                        "No staged Click execution contract is available for approval."
                    )
                    return
                if staged.get("status") == "staged":
                    staged_turn_id = str(staged.get("staged_turn_id", ""))
                    if not staged_turn_id or staged_turn_id == current_turn_id:
                        _deny(
                            "Click requires one separate user response after the contract is "
                            "staged. Show the proposal now and pass it only from the next "
                            "UserPromptSubmit turn."
                        )
                        return
                elif _contract_is_completed(staged):
                    _deny(
                        "This Click contract already completed its current-revision evidence. Stage a "
                        "fresh contract and obtain a new user response before another mutation."
                    )
                    return
                staged_sources = _evidence_sources(staged)
                if staged_sources is None:
                    _deny(
                        "This staged Click contract predates evidence-id completion "
                        "tracking. Cancel it, stage the proposal again, and obtain fresh "
                        "approval instead of passing an unrecoverable contract."
                    )
                    return
                if not staged_sources:
                    _deny(
                        "The staged Click evidence state is unavailable or malformed. "
                        "Cancel it, stage the proposal again, and obtain fresh approval."
                    )
                    return
                staged_digest = staged.get("contract_digest")
                if not isinstance(staged_digest, str) or not re.fullmatch(
                    r"[0-9a-f]{64}", staged_digest
                ):
                    _deny(
                        "The staged Click contract digest is unavailable or invalid. Cancel "
                        "it explicitly, then stage and show the contract again."
                    )
                    return
                expected_id = _contract_id_from_state(staged)
                if not expected_id:
                    _deny(
                        "The staged Click contract has no recoverable contract_id. Cancel "
                        "it explicitly, then stage and show the contract again."
                    )
                    return
                if value != expected_id:
                    _deny(
                        "The contract_id differs from the proposal staged for user approval. "
                        "Pass the exact id emitted by stage, or replace the proposal before "
                        "approval and show both contract views again."
                    )
                    return
                if staged.get("status") == "staged":
                    staged["approved_turn_id"] = current_turn_id
                staged["status"] = "approved"
                staged["contract_id"] = expected_id
                digest = staged_digest
                _save_contract_state(event, staged)
                _write_state(event, "passed", digest)
                _allow_rewritten("echo Click mutation gate passed")
                return

    status = _read_state(event).get("status")
    if status == "bypassed":
        return
    if _is_plan_tool(tool_name):
        contract_state = _read_contract_state(event)
        session_contract_active = _session_contract_is_active(contract_state)
        if status in {"armed", "staged", "passed"} or session_contract_active:
            _advise(
                "Click advisory: the Click contract workflow remains authoritative. Use the "
                "host plan only to track progress; it cannot authorize mutation; replace a "
                "staged or approved contract; widen the approved outcome, boundary, must-hold "
                "conditions, or evidence commitments; or satisfy evidence. Obtain new user "
                "approval before changing those commitments."
            )
        elif status == "review":
            _advise(
                "Click advisory: this remains a read-only review. A host plan may organize "
                "findings but does not authorize mutation; obtain a new approved contract "
                "before changing files."
            )
        return

    inspection_request: dict[str, Any] | None = None
    broad_inventory = False
    inspection_parse_error = ""
    if tool_name == "Bash":
        inspection_request, broad_inventory, inspection_parse_error = (
            _inspection_request_from_bash(str(command))
        )
    if tool_name == "Bash" and inspection_request is not None:
        approved_session_active = _approved_contract_is_active(
            _read_contract_state(event)
        )
        if status == "passed" or approved_session_active:
            (
                rewritten,
                observation_error,
                observation_advisory,
            ) = _prepare_observation(
                event, inspection_request, broad_inventory
            )
            if observation_error:
                _deny(observation_error)
                return
            if observation_advisory:
                _allow_rewritten_with_advisory(rewritten, observation_advisory)
            else:
                _allow_rewritten(rewritten)
        elif status == "review":
            (
                rewritten,
                observation_error,
                observation_advisory,
            ) = _prepare_observation(
                event, inspection_request, broad_inventory, review=True
            )
            if observation_error:
                _deny(observation_error)
                return
            if observation_advisory:
                _allow_rewritten_with_advisory(rewritten, observation_advisory)
            else:
                _allow_rewritten(rewritten)
        else:
            _allow_rewritten(_inspection_once_runner_command(inspection_request))
        return

    if tool_name == "Bash" and status in {"passed", "review"}:
        if inspection_parse_error:
            _deny(inspection_parse_error)
            return
        if status == "review":
            _deny(
                "Click review accepts only structured read-only argv operations. Use "
                "`click-gate inspect '<Inspection JSON>'`; mutation remains blocked during "
                "review, while host plan tools remain non-authoritative advisory."
            )
            return
        contract_state = _read_contract_state(event)
        verification = contract_state.get("verification")
        if isinstance(verification, dict) and verification.get("status") == "running":
            _deny(
                "The final Click verification batch is running. Wait for it to finish "
                "before starting another command or mutating the implementation."
            )
            return
        if _is_recognized_verification_command(str(command)):
            _deny(
                "Click final checks use protocol-v2 `click-gate verify` with evidence-bound "
                "argv `checks` and an explicit targeted, broad, or deep class."
            )
            return
        _deny(
            "Click does not guess whether this Bash command mutates the workspace. Use "
            "`click-gate inspect` for read-only argv operations or `click-gate mutate` "
            "for an approved implementation command."
        )
        return

    if status == "review":
        _deny(
            "Click review mode is read-only. Report the review findings without changing "
            "the project. If the user asks for a fix, leave review mode and use a compact "
            "Click build contract, or bypass Click for that turn when the user requests it."
        )
        return

    if status in {"passed", "bypassed"}:
        if status == "passed":
            contract_state = _read_contract_state(event)
            verification = contract_state.get("verification")
            verification_status = (
                str(verification.get("status", ""))
                if isinstance(verification, dict)
                else ""
            )
            if verification_status == "running":
                _deny(
                    "The final Click verification batch is running. Wait for it to finish "
                    "before starting another command or mutating the implementation."
                )
                return
            mutation_error = _mark_contract_mutated(event)
            if mutation_error:
                _deny(mutation_error)
        return

    default_mode = _read_default_mode()
    session_contract_active = _session_contract_is_active(
        _read_contract_state(event)
    )
    if default_mode == "unset" and status == "idle":
        _deny(
            "Click needs its one-time default before the first software mutation. Ask the "
            "user to choose Always ON (recommended) or Manual, then run `click-gate default "
            "on` or `click-gate default manual`. Do not ask for this choice during questions, "
            "explanations, code review, or simple read-only inspection."
        )
        return

    if (
        session_contract_active
        or status in {"armed", "staged"}
        or _read_mode(event) == "strict"
        or default_mode == "on"
    ):
        _deny(
            "Click blocked this mutation because the active execution contract has "
            "not been staged, explained plainly, explicitly approved, and matched for the "
            "current turn. Complete outcome, boundary.in_scope, boundary.out_of_scope, "
            "must_hold, build.approach, verification.scale, verification.evidence, "
            "verification.done_when, and plain_language; add build.semantics, build.order, "
            "or an intermediate gate only "
            "when the work materially requires them; "
            "stage the JSON once, show the emitted contract_id with both contract views, "
            "obtain approval, arm the later approval turn, then pass only that exact id. "
            "Do not resend the JSON. In Always ON mode, arm is optional because the "
            "persistent preference already activates the gate. If the user does not want "
            "Click for this turn, run "
            "`click-gate bypass` only after the current user turn begins with a recognized "
            "first-line `@Click bypass` directive or trusted Click autocomplete mention. "
            "Use the corresponding `@Click cancel` form plus `click-gate cancel` to discard "
            "an active contract instead of bypassing it."
        )


def _record_verification_result(
    path: Path,
    batch: dict[str, Any],
    batch_digest: str,
    runner_token: str,
    exit_code: int,
    succeeded_count: int,
    workspace_changed: bool = False,
    workspace_root: str = "",
    workspace_digest: str = "",
    environment_digests: dict[str, str] | None = None,
) -> bool:
    return click_verification.record_result(
        path,
        batch,
        batch_digest,
        runner_token,
        exit_code,
        succeeded_count,
        workspace_changed=workspace_changed,
        workspace_root=workspace_root,
        workspace_digest=workspace_digest,
        environment_digests=environment_digests,
        git_capture=_git_capture,
    )


def _claim_observation_run(
    path: Path, raw: str, command_digest: str, runner_token: str
) -> tuple[dict[str, Any] | None, str]:
    return click_observation.claim_run(
        path,
        raw,
        command_digest,
        runner_token,
        protocol_version=CAPABILITY_PROTOCOL_VERSION,
    )


def _run_inspection_request(
    request: dict[str, Any], state_result: tuple[Path, str, str] | None = None
) -> int:
    return click_observation.run_request(
        request,
        state_result,
        execute_commands=_execute_inspection_commands,
    )


def _run_inspection_once(arguments: list[str]) -> int:
    return click_inspection.run_once(
        arguments,
        run_request=_run_inspection_request,
        protocol_version=CAPABILITY_PROTOCOL_VERSION,
    )


def _run_observation(arguments: list[str]) -> int:
    return click_observation.run(
        arguments,
        run_inspection_request=_run_inspection_request,
        protocol_version=CAPABILITY_PROTOCOL_VERSION,
    )


def _claim_mutation_run(
    path: Path, raw: str, request_digest: str, runner_token: str
) -> tuple[dict[str, Any] | None, str]:
    return click_mutation.claim_run(
        path,
        raw,
        request_digest,
        runner_token,
        validate_argv=_validate_argv,
        looks_like_managed_service=_looks_like_managed_service,
        protocol_version=CAPABILITY_PROTOCOL_VERSION,
    )


def _run_mutation(arguments: list[str]) -> int:
    return click_mutation.run(
        arguments,
        validate_argv=_validate_argv,
        looks_like_managed_service=_looks_like_managed_service,
        protocol_version=CAPABILITY_PROTOCOL_VERSION,
        execute_commands=_execute_argv_commands,
    )


def _managed_contract_path(path: Path) -> bool:
    return _managed_state_path(path, ("session-contract-",))


def _run_service_supervisor(arguments: list[str]) -> int:
    return click_service.run_service_supervisor(
        arguments,
        validate_argv=_validate_argv,
        protocol_version=CAPABILITY_PROTOCOL_VERSION,
        execution_argv=_execution_argv,
    )


def _run_service_start(arguments: list[str]) -> int:
    return click_service.run_service_start(
        arguments,
        validate_argv=_validate_argv,
        protocol_version=CAPABILITY_PROTOCOL_VERSION,
        runner_script=Path(__file__).resolve(),
    )


def _run_service_stop(arguments: list[str]) -> int:
    return click_service.run_service_stop(
        arguments,
        snapshot_reader=_service_snapshot,
    )




def _claim_verification_run(
    state_path: Path,
    raw: str,
    batch_digest: str,
    runner_token: str,
) -> tuple[dict[str, Any] | None, str]:
    return click_verification.claim_run(
        state_path,
        raw,
        batch_digest,
        runner_token,
        file_content_digest=_file_content_digest,
    )


def _release_unclaimed_verification_reservation(
    state_path: Path, batch_digest: str, runner_token: str
) -> bool:
    return click_verification.release_unclaimed_reservation(
        state_path, batch_digest, runner_token
    )


def _run_verification(arguments: list[str]) -> int:
    return click_verification.run(
        arguments,
        file_content_digest=_file_content_digest,
        git_workspace_snapshot=_git_workspace_snapshot,
        git_metadata_present=_git_metadata_present,
        execute_commands=_execute_argv_commands,
        git_capture=_git_capture,
    )


STATEFUL_RUNNER_ACTIONS = {
    "run-observation",
    "run-mutation",
    "run-service-start",
    "run-service-stop",
    "run-service-supervisor",
    "run-verification",
}


def _runner_arguments(arguments: list[str]) -> tuple[list[str], str]:
    """Adopt only an explicit absolute gate-state root for internal runners."""
    if not arguments:
        return arguments, ""
    if arguments[0] in STATEFUL_RUNNER_ACTIONS:
        return [], "Click stateful runner requires an explicit state-root binding."
    if arguments[0] != "--state-root":
        return arguments, ""
    if len(arguments) < 4 or arguments[2] not in STATEFUL_RUNNER_ACTIONS:
        return [], "Click runner state-root binding is malformed."
    state_root = Path(arguments[1])
    if not state_root.is_absolute():
        return [], "Click runner state-root binding is invalid."
    try:
        resolved = state_root.resolve(strict=True)
    except (OSError, RuntimeError):
        return [], "Click runner state-root binding could not be resolved."
    if resolved.name != "gate-state" or state_root != resolved:
        return [], "Click runner state-root binding is invalid."
    state_path = Path(arguments[3])
    if not state_path.is_absolute():
        return [], "Click runner state path is invalid."
    try:
        resolved_state = state_path.resolve(strict=True)
    except (OSError, RuntimeError):
        return [], "Click runner state path could not be resolved."
    if state_path != resolved_state or resolved_state.parent != resolved:
        return [], "Click runner state path does not match its bound state root."
    os.environ["PLUGIN_DATA"] = str(resolved.parent)
    return arguments[2:], ""


def main() -> int:
    arguments = sys.argv[1:]
    if arguments and arguments[0] == "--encoded-runner":
        if len(arguments) != 2:
            sys.stderr.write("Click runner transport was malformed.\n")
            return 2
        decoded, transport_error = _decode_runner_transport(arguments[1])
        if transport_error or decoded is None:
            sys.stderr.write(f"{transport_error}\n")
            return 2
        arguments = decoded
    arguments, runner_error = _runner_arguments(arguments)
    if runner_error:
        sys.stderr.write(f"{runner_error}\n")
        return 2
    if arguments and arguments[0] == "run-inspection-once":
        return _run_inspection_once(arguments[1:])
    if arguments and arguments[0] == "run-observation":
        return _run_observation(arguments[1:])
    if arguments and arguments[0] == "run-mutation":
        return _run_mutation(arguments[1:])
    if arguments and arguments[0] == "run-service-start":
        return _run_service_start(arguments[1:])
    if arguments and arguments[0] == "run-service-stop":
        return _run_service_stop(arguments[1:])
    if arguments and arguments[0] == "run-service-supervisor":
        return _run_service_supervisor(arguments[1:])
    if arguments and arguments[0] == "run-verification":
        return _run_verification(arguments[1:])
    if len(arguments) != 1 or arguments[0] not in {
        "post-tool",
        "pre-tool",
        "prompt-submit",
        "session-end",
    }:
        sys.stderr.write(
            "usage: click_gate.py pre-tool|post-tool|prompt-submit|session-end\n"
        )
        return 1
    try:
        event = _read_event()
        if arguments[0] == "prompt-submit":
            with _state_lock():
                _handle_prompt_submit(event)
        elif arguments[0] == "post-tool":
            with _state_lock():
                _handle_post_tool(event)
        elif arguments[0] == "session-end":
            with _state_lock():
                _handle_session_end(event)
        else:
            with _state_lock():
                _handle_pre_tool(event)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"click hook error: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
