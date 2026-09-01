#!/usr/bin/env python3
"""A local Evidence/Guarded runtime for structured capabilities and receipts.

Evidence is the approval-free default and records host-authorized intent,
mutations, verification, and cache lineage. Guarded binds supported mutations to
one approved contract; Off remains fail-open unless Click is explicitly armed.
The hook does not judge architecture, search strategy, or verification
sufficiency. Structured argv requests execute without a shell.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
from typing import Any

if __package__:
    from . import (
        click_browser,
        click_browser_advisory,
        click_capability,
        click_contract,
        click_evidence,
        click_host_coverage,
        click_host_router,
        click_inspection,
        click_lifecycle,
        click_mutation,
        click_observation,
        click_process,
        click_receipt_runtime,
        click_runner_transport,
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
    import click_host_router
    import click_inspection
    import click_lifecycle
    import click_mutation
    import click_observation
    import click_process
    import click_receipt_runtime
    import click_runner_transport
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


# Compatibility alias for direct callers and the deterministic suite. Contract
# schema validation now lives in the one-way click_contract boundary.
_validate_contract = click_contract.validate_contract

# Compatibility aliases for direct callers and the deterministic suite. The
# managed local-service state machine and runner lifecycle live in the one-way
# click_service boundary; gate wrappers below provide only cross-domain routing.
_looks_like_managed_service = click_service.looks_like_managed_service
_request_service_stop = click_service.request_stop
_service_snapshot = click_service.service_snapshot

# Compatibility aliases for mutation state and direct result recording. The
# gate wrappers below inject host routing and shared execution mechanics into
# the one-way click_mutation boundary.
_fresh_mutation_state = click_mutation.fresh_state
_mutation_is_running = click_mutation.is_running

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


CONTROL_COMMAND = click_lifecycle.CONTROL_COMMAND
CLICK_AUTHORIZATION_PATTERNS = click_lifecycle.CLICK_AUTHORIZATION_PATTERNS
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
CONTRACT_ID_PATTERN = click_lifecycle.CONTRACT_ID_PATTERN
VERIFICATION_SCALES = click_verification_policy.VERIFICATION_SCALES
VERIFICATION_UNIT_LIMITS = click_verification_policy.VERIFICATION_UNIT_LIMITS
CAPABILITY_PROTOCOL_VERSION = click_capability.PROTOCOL_VERSION
VERIFICATION_PROTOCOL_VERSION = click_verification.PROTOCOL_VERSION
CONTRACT_STATE_SCHEMA_VERSION = click_lifecycle.CONTRACT_STATE_SCHEMA_VERSION
INSPECTION_REQUEST_FIELDS = click_inspection.REQUEST_FIELDS
MUTATION_REQUEST_FIELDS = click_mutation.REQUEST_FIELDS
SERVICE_REQUEST_FIELDS = click_service.SERVICE_REQUEST_FIELDS
VERIFICATION_BATCH_FIELDS = click_verification.BATCH_FIELDS
VERIFICATION_CHECK_FIELDS = click_verification.CHECK_FIELDS
EVIDENCE_RESULT_FIELDS = click_lifecycle.EVIDENCE_RESULT_FIELDS
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
EPHEMERAL_STATE_TTL_SECONDS = click_lifecycle.EPHEMERAL_STATE_TTL_SECONDS
COMPLETED_CONTRACT_TTL_SECONDS = click_lifecycle.COMPLETED_CONTRACT_TTL_SECONDS
DEFAULT_MODES = click_lifecycle.DEFAULT_MODES
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


def _write_stdout_payload(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


_OUTPUT_SINK: click_host_router.OutputSink = _write_stdout_payload


def _set_output_adapter(adapter: HookOutputAdapter) -> HookOutputAdapter:
    """Select a host serializer and return the previous serializer."""
    global _OUTPUT_ADAPTER
    previous = _OUTPUT_ADAPTER
    _OUTPUT_ADAPTER = adapter
    return previous


def _set_output_sink(
    sink: click_host_router.OutputSink,
) -> click_host_router.OutputSink:
    """Select a host output sink and return the previous sink."""
    global _OUTPUT_SINK
    previous = _OUTPUT_SINK
    _OUTPUT_SINK = sink
    return previous

RG_OPTIONS_WITH_VALUES = click_inspection.RG_OPTIONS_WITH_VALUES
ENVIRONMENT_ASSIGNMENT = click_capability.ENVIRONMENT_ASSIGNMENT
SSH_TARGET = click_inspection.SSH_TARGET
SSH_READ_ONLY_GIT_SUBCOMMANDS = click_inspection.SSH_READ_ONLY_GIT_SUBCOMMANDS
GIT_REMOTE_NAME = click_inspection.GIT_REMOTE_NAME


def _emit(payload: dict[str, Any]) -> None:
    _OUTPUT_SINK(payload)


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


# Compatibility aliases for approval, prompt-turn, mode, and contract state.
# Host-event routing remains below; lifecycle transitions live in the top
# runtime domain without importing this adapter.
_write_state = click_lifecycle.write_state
_read_state = click_lifecycle.read_state
_write_mode = click_lifecycle.write_mode
_read_mode = click_lifecycle.read_mode
_write_default_mode = click_lifecycle.write_default_mode
_read_default_mode = click_lifecycle.read_default_mode
_evidence_sources = click_lifecycle.evidence_sources
_write_contract_state = click_lifecycle.write_contract_state
_contract_id_from_state = click_lifecycle.contract_id_from_state
_read_contract_state = click_lifecycle.read_contract_state
_clear_contract_state = click_lifecycle.clear_contract_state
_save_contract_state = click_lifecycle.save_contract_state
_prompt_authorization = click_lifecycle.prompt_authorization
_record_user_prompt = click_lifecycle.record_user_prompt
_read_user_prompt_state = click_lifecycle.read_user_prompt_state
_read_user_prompt_turn = click_lifecycle.read_user_prompt_turn
_consume_user_authorization = click_lifecycle.consume_user_authorization
_active_prompt_turn_error = click_lifecycle.active_prompt_turn_error
_contract_is_completed = click_lifecycle.contract_is_completed
_approved_contract_is_active = click_lifecycle.approved_contract_is_active
_session_contract_is_active = click_lifecycle.session_contract_is_active
_ensure_evidence_state = click_lifecycle.ensure_evidence_state


def _mark_contract_mutated(
    event: dict[str, Any], *, host_tool_use: bool = True
) -> str:
    return click_mutation.mark_contract_mutated(
        event,
        expected_contract_schema_version=CONTRACT_STATE_SCHEMA_VERSION,
        observation_is_running=_observation_is_running,
        workspace_snapshot=_git_workspace_snapshot,
        host_tool_use=host_tool_use,
    )


_prune_state = click_lifecycle.prune_state


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


_validate_evidence_result = click_lifecycle.validate_evidence_result
_control_request = click_lifecycle.control_request


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
        render_command=click_runner_transport.render_runner_shell_command,
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
        render_command=click_runner_transport.render_runner_shell_command,
    )


def _inspection_once_runner_command(request: dict[str, Any]) -> str:
    return click_inspection.runner_command(
        request,
        runner_script=Path(__file__).resolve(),
        render_command=click_runner_transport.render_runner_shell_command,
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
        render_command=click_runner_transport.render_runner_shell_command,
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
        render_command=click_runner_transport.render_runner_shell_command,
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
        render_command=click_runner_transport.render_runner_shell_command,
    )


def _prepare_service(event: dict[str, Any], raw: str) -> tuple[str, str]:
    return click_service.prepare_service(
        event,
        raw,
        validate_argv=_validate_argv,
        protocol_version=CAPABILITY_PROTOCOL_VERSION,
        mark_contract_mutated=lambda value: _mark_contract_mutated(
            value, host_tool_use=False
        ),
        runner_script=Path(__file__).resolve(),
        render_command=click_runner_transport.render_runner_shell_command,
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
        render_command=click_runner_transport.render_runner_shell_command,
    )


def _tool_working_directory(event: dict[str, Any]) -> Path:
    event_cwd = Path(str(event.get("cwd", "")))
    tool_input = event.get("tool_input")
    requested = tool_input.get("workdir") if isinstance(tool_input, dict) else None
    if not isinstance(requested, str) or not requested:
        return event_cwd.resolve()
    workdir = Path(requested)
    if not workdir.is_absolute():
        workdir = event_cwd / workdir
    return workdir.resolve()


def _receipt_export_runner_command(event: dict[str, Any]) -> str:
    host_id = click_host_coverage.host_id_from_event(event)
    return click_runner_transport.render_runner_shell_command(
        [
            *_stateful_runner_prefix("run-receipt-export"),
            str(_contract_path(event).resolve()),
            str(_tool_working_directory(event)),
            host_id,
        ]
    )


def _receipt_verify_runner_command(path: str) -> str:
    return click_runner_transport.render_runner_shell_command(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "run-receipt-verify",
            path,
        ]
    )


def _record_evidence_completion(event: dict[str, Any], raw: str) -> tuple[str, str]:
    return click_lifecycle.record_evidence_completion(event, raw)


def _prepare_verification(
    event: dict[str, Any], raw: str
) -> tuple[str, str, str]:
    return click_verification.prepare(
        event,
        raw,
        runner_script=Path(__file__).resolve(),
        render_command=click_runner_transport.render_runner_shell_command,
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
    _emit(_OUTPUT_ADAPTER.context(click_lifecycle.prompt_context(event)))


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
                normalized = click_lifecycle.LEGACY_DEFAULT_MODE_ALIASES.get(
                    value, value
                )
                runtime_state = _read_contract_state(event)
                if (
                    normalized != "evidence"
                    and runtime_state.get("status") == "evidence"
                ):
                    _clear_contract_state(event)
                    _write_state(event, "idle")
                label = {
                    "evidence": "Evidence",
                    "guarded": "Guarded",
                    "off": "Off",
                }[normalized]
                _allow_rewritten(f"echo Click default mode set to {label}")
                return
            if action == "mode":
                _prune_state()
                _write_mode(event, value)
                if value == "adaptive":
                    _write_state(event, "idle")
                _allow_rewritten(f"echo Click mode set to {value}")
                return
            if action == "receipt-export":
                state = _read_contract_state(event)
                if not _contract_is_completed(state):
                    _deny(
                        "Click receipt export requires every declared evidence source "
                        "to be current and every managed service to be stopped."
                    )
                    return
                _allow_rewritten(_receipt_export_runner_command(event))
                return
            if action == "receipt-verify":
                _allow_rewritten(_receipt_verify_runner_command(value))
                return
            if action == "evidence":
                current_status = _read_state(event).get("status")
                runtime_state = _read_contract_state(event)
                evidence_active = runtime_state.get("status") == "evidence"
                if (
                    current_status != "passed"
                    and _read_mode(event) != "strict"
                    and not evidence_active
                ):
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
                runtime_state = _read_contract_state(event)
                approved_session_active = _approved_contract_is_active(runtime_state)
                evidence_active = runtime_state.get("status") == "evidence"
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
                elif current_status == "passed" or approved_session_active or evidence_active:
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
                evidence_active = _read_contract_state(event).get("status") == "evidence"
                if (
                    current_status != "passed"
                    and _read_mode(event) != "strict"
                    and not evidence_active
                ):
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
                evidence_active = _read_contract_state(event).get("status") == "evidence"
                if (
                    current_status != "passed"
                    and _read_mode(event) != "strict"
                    and not evidence_active
                ):
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
                evidence_active = _read_contract_state(event).get("status") == "evidence"
                if (
                    current_status != "passed"
                    and _read_mode(event) != "strict"
                    and not evidence_active
                ):
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
                if action == "stage":
                    rewritten, lifecycle_error = click_lifecycle.stage_contract(
                        event, value
                    )
                else:
                    rewritten, lifecycle_error = click_lifecycle.pass_contract(
                        event, value
                    )
                if lifecycle_error:
                    _deny(lifecycle_error)
                    return
                if action == "stage":
                    contract, projection_error = click_contract.validate_contract(value)
                    contract_id = _contract_id_from_state(_read_contract_state(event))
                    if projection_error or contract is None or not contract_id:
                        _deny(
                            projection_error
                            or "Click could not render the staged approval projection."
                        )
                        return
                    _allow_rewritten_with_advisory(
                        rewritten,
                        click_contract.render_human_view(contract_id, contract),
                    )
                else:
                    _allow_rewritten(rewritten)
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
        runtime_state = _read_contract_state(event)
        approved_session_active = _approved_contract_is_active(runtime_state)
        evidence_active = runtime_state.get("status") == "evidence"
        if status == "passed" or approved_session_active or evidence_active:
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
    runtime_state = _read_contract_state(event)
    session_contract_active = _session_contract_is_active(runtime_state)
    if (
        default_mode == "evidence"
        and not session_contract_active
        and status not in {"armed", "staged"}
        and _read_mode(event) != "strict"
    ):
        runtime_state, recovered = _ensure_evidence_state(event)
        verification = runtime_state.get("verification")
        if isinstance(verification, dict) and verification.get("status") == "running":
            _deny(
                "Click blocked mutation while its exact Evidence verification runner is "
                "active. Wait for that bound result before changing the revision."
            )
            return
        mutation_error = _mark_contract_mutated(event)
        if mutation_error:
            # Evidence is observability, not execution authority. A recovery problem may
            # lower receipt assurance but must not masquerade as a host permission denial.
            _advise(
                "Click Evidence advisory: this host mutation remains authorized by the "
                f"host, but Click could not bind its receipt ({mutation_error})."
            )
        elif recovered:
            _advise(
                "Click Evidence advisory: a new lower-assurance session was created; "
                "history before recovery is excluded from its receipt."
            )
        return

    if (
        session_contract_active
        or status in {"armed", "staged"}
        or _read_mode(event) == "strict"
        or default_mode == "guarded"
    ):
        _deny(
            "Click blocked this mutation because the active execution contract has "
            "not been staged, explained plainly, explicitly approved, and matched for the "
            "current turn. Complete outcome, boundary.in_scope, boundary.out_of_scope, "
            "must_hold, build.approach, verification.scale, verification.evidence, "
            "verification.done_when, and plain_language; add build.semantics, build.order, "
            "or an intermediate gate only "
            "when the work materially requires them; "
            "stage the JSON once, show four human approval sections with optional technical "
            "details and the emitted contract_id, "
            "obtain approval, arm the later approval turn, then pass only that exact id. "
            "Do not resend the JSON. In Guarded mode, arm is optional because the "
            "persistent preference already activates the gate. If the user does not want "
            "Click for this turn, run "
            "`click-gate bypass` only after the current user turn begins with a recognized "
            "first-line `@Click bypass` directive or trusted Click autocomplete mention. "
            "Use the corresponding `@Click cancel` form plus `click-gate cancel` to discard "
            "an active contract instead of bypassing it."
        )


_HOST_ROUTER = click_host_router.HostRouter(
    click_host_router.HostHandlers(
        pre_tool=_handle_pre_tool,
        post_tool=_handle_post_tool,
        prompt_submit=_handle_prompt_submit,
        session_end=_handle_session_end,
    ),
    set_output_adapter=_set_output_adapter,
    set_output_sink=_set_output_sink,
)


def host_router() -> click_host_router.HostRouter:
    """Return the supported routing interface used by bundled host adapters."""
    return _HOST_ROUTER


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


def _run_receipt_export(arguments: list[str]) -> int:
    if len(arguments) != 3:
        sys.stderr.write(
            "usage: click_gate.py run-receipt-export <state> <cwd> <host>\n"
        )
        return 2
    state_path = Path(arguments[0])
    workspace = Path(arguments[1])
    host_id = arguments[2]
    if not _managed_contract_path(state_path) or not workspace.is_absolute():
        sys.stderr.write("Click receipt export received an invalid state or workspace.\n")
        return 2
    try:
        workspace = workspace.resolve(strict=True)
    except (OSError, RuntimeError):
        sys.stderr.write("Click receipt export workspace could not be resolved.\n")
        return 2
    with _state_lock():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            sys.stderr.write("Click receipt export could not read contract state.\n")
            return 2
        if not isinstance(state, dict) or not _contract_is_completed(state):
            sys.stderr.write("Click receipt export requires a completed contract.\n")
            return 2
        envelope, error = click_receipt_runtime.build_envelope(
            state,
            workspace_snapshot=_git_workspace_snapshot(workspace),
            host_coverage=click_host_coverage.receipt(host_id),
            expected_contract_schema_version=CONTRACT_STATE_SCHEMA_VERSION,
        )
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    assert envelope is not None
    sys.stdout.write(click_receipt_runtime.render_envelope(envelope) + "\n")
    return 0


def _run_receipt_verify(arguments: list[str]) -> int:
    if len(arguments) != 1:
        sys.stderr.write("usage: click_gate.py run-receipt-verify <path>\n")
        return 2
    report, error = click_receipt_runtime.verify_file(Path(arguments[0]))
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    assert report is not None
    sys.stdout.write(
        json.dumps(
            report,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    )
    return 0


STATEFUL_RUNNER_ACTIONS = {
    "run-observation",
    "run-mutation",
    "run-receipt-export",
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
        decoded, transport_error = click_runner_transport.decode_runner_transport(
            arguments[1]
        )
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
    if arguments and arguments[0] == "run-receipt-export":
        return _run_receipt_export(arguments[1:])
    if arguments and arguments[0] == "run-receipt-verify":
        return _run_receipt_verify(arguments[1:])
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
        with _state_lock():
            _HOST_ROUTER.dispatch(arguments[0], event)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"click hook error: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
