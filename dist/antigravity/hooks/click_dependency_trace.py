#!/usr/bin/env python3
"""Compatibility facade and cross-platform selector for Shadow Observer v1.

Callers keep the established ``click_dependency_trace`` surface while common
record handling, backend selection, and Linux collection have independent
owners. Unsupported platforms execute the real command once without a
collector and record honest unavailable telemetry.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
import platform
import subprocess
from typing import Any

if __package__:
    from . import (
        click_observer_backend,
        click_observer_common,
        click_observer_linux,
    )
else:  # Executed directly from the bundled hooks directory.
    import click_observer_backend
    import click_observer_common
    import click_observer_linux


SHADOW_STATE_VERSION = click_observer_common.SHADOW_STATE_VERSION
SHADOW_STATE_FIELD = click_observer_common.SHADOW_STATE_FIELD
MAX_SHADOW_STATE_RECORDS = click_observer_common.MAX_SHADOW_STATE_RECORDS
MAX_RAW_TRACE_BYTES = click_observer_linux.MAX_RAW_TRACE_BYTES
MAX_BACKEND_VERSION_BYTES = click_observer_linux.MAX_BACKEND_VERSION_BYTES
STRACE_STRING_LIMIT = click_observer_linux.STRACE_STRING_LIMIT
STRACE_TRACE_EXPRESSION = click_observer_linux.STRACE_TRACE_EXPRESSION

BackendCapability = click_observer_backend.BackendCapability
ObserverBackend = click_observer_backend.ObserverBackend
ShadowExecution = click_observer_common.ShadowExecution
ParsedTrace = click_observer_linux.ParsedTrace

FallbackExecutor = click_observer_common.FallbackExecutor
BackendResolver = click_observer_linux.BackendResolver
FileDigester = click_observer_linux.FileDigester
BackendProbe = click_observer_linux.BackendProbe
SpawnArgv = click_observer_linux.SpawnArgv

select_backend = click_observer_backend.select_backend
run_unobserved = click_observer_common.run_unobserved
combine_records = click_observer_common.combine_records
fresh_state = click_observer_common.fresh_state
state_is_valid = click_observer_common.state_is_valid
records_from_verification = click_observer_common.records_from_verification
store_records = click_observer_common.store_records
advisory = click_observer_common.advisory

# Keep the intentionally tested Linux compatibility helpers on the old facade.
probe_strace_version = click_observer_linux.probe_strace_version
parse_strace = click_observer_linux.parse_strace
_already_traced = click_observer_linux._already_traced
_file_digest = click_observer_linux._file_digest
click_process = click_observer_linux.click_process


def run_command(
    argv: Sequence[str],
    *,
    workspace: Path,
    observation_root: Path | None = None,
    environment: Mapping[str, str],
    evidence_key: str,
    check_digest: str,
    mutation_revision: int,
    execute_unobserved: FallbackExecutor,
    resolve_backend: BackendResolver,
    digest_file: FileDigester = _file_digest,
    probe_version: BackendProbe = probe_strace_version,
    spawn_argv: SpawnArgv = click_observer_linux.click_process.spawn_argv,
    terminate_group: Callable[[subprocess.Popen[Any]], int] = (
        click_observer_linux.click_process.terminate_process_group
    ),
    system_name: str | None = None,
    already_traced: Callable[[], bool] = _already_traced,
    capture_limit: int = MAX_RAW_TRACE_BYTES,
) -> ShadowExecution:
    """Select one backend and execute the target exactly once."""

    try:
        system = platform.system() if system_name is None else system_name
        capability = select_backend(system)
    except Exception:
        capability = BackendCapability(
            system="",
            backend_name=None,
            status="unavailable",
            reason="capability-detection-failed",
        )
    if capability.status != "available" or capability.backend_name != "strace":
        return run_unobserved(
            execute_unobserved,
            evidence_key=evidence_key,
            check_digest=check_digest,
            mutation_revision=mutation_revision,
        )
    return click_observer_linux.run_command(
        argv,
        workspace=workspace,
        observation_root=observation_root,
        environment=environment,
        evidence_key=evidence_key,
        check_digest=check_digest,
        mutation_revision=mutation_revision,
        execute_unobserved=execute_unobserved,
        resolve_backend=resolve_backend,
        digest_file=digest_file,
        probe_version=probe_version,
        spawn_argv=spawn_argv,
        terminate_group=terminate_group,
        system_name=system,
        already_traced=already_traced,
        capture_limit=capture_limit,
    )
