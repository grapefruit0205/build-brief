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
import hmac
import json
import os
import platform
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import zlib
from typing import Any
from urllib.parse import urlsplit, urlunsplit

if __package__:
    from . import (
        click_browser_advisory,
        click_contract,
        click_dependency_cache,
        click_evidence,
        click_process,
        click_verification_meter,
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
    import click_browser_advisory
    import click_contract
    import click_dependency_cache
    import click_evidence
    import click_process
    import click_verification_meter
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
CAPABILITY_PROTOCOL_VERSION = 1
VERIFICATION_PROTOCOL_VERSION = 2
CONTRACT_STATE_SCHEMA_VERSION = 2
INSPECTION_REQUEST_FIELDS = {"version", "commands"}
MUTATION_REQUEST_FIELDS = {"version", "argv"}
SERVICE_REQUEST_FIELDS = {"version", "action", "argv"}
VERIFICATION_BATCH_FIELDS = {"version", "checks"}
VERIFICATION_CHECK_FIELDS = {"evidence_id", "argv", "class"}
EVIDENCE_RESULT_FIELDS = {"version", "evidence_id"}
VERIFICATION_CLASSES = click_verification_meter.VERIFICATION_CLASSES
PYTHON_VERIFICATION_MODULES = {"coverage", "pytest", "unittest"}
DEEP_VERIFICATION_EXECUTABLES = {
    "bandit",
    "cargo-audit",
    "cypress",
    "k6",
    "locust",
    "nox",
    "playwright",
    "semgrep",
    "snyk",
    "tox",
    "trivy",
}
DEEP_VERIFICATION_MARKERS = {
    "audit",
    "bench",
    "coverage",
    "e2e",
    "end-to-end",
    "end_to_end",
    "integration",
    "load-test",
    "load_test",
    "security",
}
MAX_INSPECTION_COMMANDS = 8
MAX_ARGV_ITEMS = 128
MAX_OBSERVATION_OUTPUT_BYTES = 48_000
MAX_OBSERVATION_ENTRIES = 64
MAX_BROWSER_UNIQUE_INPUTS = 256
# Compatibility names for callers that previously treated these advisory
# thresholds as hard maxima.
MAX_BROWSER_TOOL_TIMEOUT_MS = (
    click_browser_advisory.RECOMMENDED_BROWSER_TOOL_TIMEOUT_MS
)
MAX_BROWSER_WAIT_MS = click_browser_advisory.RECOMMENDED_BROWSER_WAIT_MS
BROWSER_RUNNING_TTL_SECONDS = 40
OBSERVATION_RESERVATION_TTL_SECONDS = 30
MUTATION_RUNNING_TTL_SECONDS = 10 * 60
VERIFY_RUNNING_TTL_SECONDS = 60 * 60
EPHEMERAL_STATE_TTL_SECONDS = 7 * 24 * 60 * 60
COMPLETED_CONTRACT_TTL_SECONDS = 30 * 24 * 60 * 60
DEFAULT_MODES = {"on", "manual"}
SHELL_EXECUTABLES = {
    "bash",
    "cmd",
    "cmd.exe",
    "dash",
    "fish",
    "ksh",
    "powershell",
    "powershell.exe",
    "pwsh",
    "sh",
    "zsh",
}

PROCESS_CONTROL_EXECUTABLES = {
    "kill",
    "kill.exe",
    "killall",
    "pkill",
    "pskill",
    "pskill.exe",
    "skill",
    "stop-process",
    "taskkill",
    "taskkill.exe",
    "tskill",
    "tskill.exe",
    "xkill",
}

BROWSER_TOOL_NAMES = {"mcp__node_repl__js"}
BROWSER_WAIT_PATTERNS = click_browser_advisory.BROWSER_WAIT_PATTERNS
MANAGED_SERVICE_EXECUTABLES = {
    "flask",
    "gunicorn",
    "http-server",
    "next",
    "serve",
    "uvicorn",
    "vite",
    "webpack-dev-server",
}
MANAGED_SERVICE_ACTIONS = {"start", "stop"}
MANAGED_SERVICE_SCRIPT_MARKERS = {
    "dev",
    "preview",
    "runserver",
    "serve",
    "start",
}
SERVICE_START_TIMEOUT_SECONDS = 8
SERVICE_STOP_TIMEOUT_SECONDS = 8
MANAGED_SERVICE_MAX_SECONDS = 2 * 60 * 60

VERIFICATION_EXECUTABLES = {
    "bandit",
    "bats",
    "cargo-audit",
    "cypress",
    "jest",
    "k6",
    "locust",
    "nox",
    "playwright",
    "phpunit",
    "pytest",
    "rspec",
    "semgrep",
    "snyk",
    "tox",
    "trivy",
    "vitest",
}
VERIFICATION_NAME_MARKERS = (
    "audit",
    "bench",
    "coverage",
    "e2e",
    "integration-test",
    "integration_test",
    "security",
    "spec",
    "test",
    "validate",
    "verification",
    "verify",
)
TEST_TARGET_SUFFIXES = {
    ".go",
    ".js",
    ".jsx",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".ts",
    ".tsx",
}
TEST_FILTER_OPTIONS = {
    "-k",
    "-m",
    "-run",
    "-t",
    "--filter",
    "--test-name-pattern",
    "--tests-regex",
}
TEST_OPTIONS_WITH_VALUES = TEST_FILTER_OPTIONS | {
    "-p",
    "-r",
    "-s",
    "--basetemp",
    "--confcutdir",
    "--cov",
    "--cov-report",
    "--deselect",
    "--ignore",
    "--junitxml",
    "--maxfail",
    "--package",
    "--project",
    "--rootdir",
    "--test",
}
NEW_SOURCE_PATH_SEGMENTS = {
    "app",
    "config",
    "configs",
    "lib",
    "migration",
    "migrations",
    "src",
}
READ_ONLY_COMMANDS = {
    "basename",
    "cat",
    "cmp",
    "cut",
    "diff",
    "dirname",
    "du",
    "file",
    "find",
    "grep",
    "get-content",
    "head",
    "ls",
    "pwd",
    "readlink",
    "realpath",
    "rg",
    "sed",
    "sort",
    "stat",
    "tail",
    "test",
    "tree",
    "tr",
    "true",
    "type",
    "wc",
    "where",
    "which",
}

READ_ONLY_GIT_SUBCOMMANDS = {
    "check-ignore",
    "describe",
    "diff",
    "for-each-ref",
    "log",
    "ls-files",
    "ls-tree",
    "merge-base",
    "name-rev",
    "remote",
    "rev-parse",
    "show",
    "status",
}

GIT_DIFF_RENDERING_SUBCOMMANDS = {"diff", "log", "show"}
GIT_GLOBAL_ALLOWED_PREFIXES = ("--git-dir=", "--work-tree=")
GIT_GLOBAL_REJECTED_OPTIONS = {"-p", "--paginate", "-c", "--config-env"}
GIT_READ_ONLY_EXACT_OPTIONS = {
    "check-ignore": {
        "-q", "--quiet", "-v", "--verbose", "--stdin", "-z", "--no-index",
        "--non-matching",
    },
    "describe": {
        "--always", "--tags", "--all", "--long", "--exact-match", "--contains",
        "--debug", "--first-parent", "--broken",
    },
    "diff": {
        "--cached", "--staged", "--check", "--quiet", "--exit-code", "--stat",
        "--shortstat", "--numstat", "--name-only", "--name-status", "--summary",
        "--binary", "--patch", "--no-patch", "--raw", "--minimal", "--patience",
        "--histogram", "--no-color", "--relative", "--ignore-space-at-eol",
        "--ignore-all-space", "--ignore-space-change", "--ignore-blank-lines", "-w",
        "-b", "--no-ext-diff", "--no-textconv",
    },
    "for-each-ref": {"--ignore-case", "--omit-empty"},
    "log": {
        "--oneline", "--no-decorate", "--decorate", "--stat", "--shortstat",
        "--numstat", "--name-only", "--name-status", "--summary", "--no-merges",
        "--merges", "--first-parent", "--all", "--branches", "--tags", "--remotes",
        "--reflog", "--reverse", "--topo-order", "--date-order", "--author-date-order",
        "--parents", "--children", "--boundary", "--simplify-by-decoration",
        "--full-history", "--simplify-merges", "--ancestry-path", "--follow",
        "--no-patch", "--patch", "--abbrev-commit", "--no-color", "--no-ext-diff",
        "--no-textconv",
    },
    "ls-files": {
        "--cached", "--deleted", "--modified", "--others", "--ignored", "--stage",
        "--unmerged", "--killed", "--directory", "--no-empty-directory", "--eol",
        "--deduplicate", "--sparse", "--debug", "--exclude-standard", "--error-unmatch",
        "-c", "-d", "-m", "-o", "-i", "-s", "-u", "-k", "-t", "-v", "-f", "-z",
    },
    "ls-tree": {
        "-d", "-r", "-t", "-l", "--long", "-z", "--name-only", "--name-status",
        "--object-only", "--full-name", "--full-tree",
    },
    "merge-base": {"--all", "--octopus", "--independent", "--is-ancestor", "--fork-point"},
    "name-rev": {"--tags", "--all", "--stdin", "--name-only", "--no-undefined", "--always"},
    "remote": {"--all", "--push"},
    "rev-parse": {
        "--verify", "--short", "--abbrev-ref", "--symbolic-full-name", "--show-toplevel",
        "--show-prefix", "--show-cdup", "--git-dir", "--is-inside-work-tree",
        "--is-bare-repository", "--show-object-format", "--sq", "--revs-only",
        "--no-revs", "--flags", "--no-flags", "--quiet", "-q",
    },
    "show": {
        "--stat", "--shortstat", "--numstat", "--name-only", "--name-status", "--summary",
        "--binary", "--patch", "--no-patch", "--raw", "--minimal", "--patience",
        "--histogram", "--no-color", "--relative", "--ignore-space-at-eol",
        "--ignore-all-space", "--ignore-space-change", "--ignore-blank-lines", "-w", "-b",
        "--no-ext-diff", "--no-textconv", "--oneline", "--abbrev-commit",
    },
    "status": {
        "--short", "--porcelain", "--branch", "--show-stash", "--long",
        "--ignored", "--no-renames", "-s", "-b", "-sb",
    },
}
GIT_READ_ONLY_OPTION_PREFIXES = {
    "check-ignore": ("--exclude-standard",),
    "describe": ("--abbrev=", "--candidates=", "--match=", "--exclude="),
    "diff": (
        "--stat=", "--relative=", "--unified=", "--word-diff=", "--word-diff-regex=",
        "--src-prefix=", "--dst-prefix=", "--line-prefix=", "--ignore-submodules=",
        "--submodule=", "--diff-filter=",
    ),
    "for-each-ref": (
        "--sort=", "--count=", "--points-at=", "--merged=", "--no-merged=",
        "--contains=", "--no-contains=",
    ),
    "log": (
        "--date=", "--since=", "--after=", "--until=",
        "--before=", "--author=", "--committer=", "--grep=", "--max-count=", "--skip=",
        "--abbrev=", "--decorate=", "--stat=", "--relative=", "--unified=",
        "--word-diff=", "--word-diff-regex=", "--src-prefix=", "--dst-prefix=",
        "--line-prefix=", "--ignore-submodules=", "--submodule=", "--diff-filter=",
    ),
    "ls-files": (
        "--exclude=", "--exclude-from=", "--exclude-per-directory=",
        "--with-tree=", "--abbrev=",
    ),
    "ls-tree": ("--abbrev=",),
    "name-rev": ("--refs=", "--exclude="),
    "rev-parse": ("--short=", "--abbrev-ref=", "--path-format=", "--disambiguate="),
    "show": (
        "--date=", "--stat=", "--relative=", "--unified=",
        "--word-diff=", "--word-diff-regex=", "--src-prefix=", "--dst-prefix=",
        "--line-prefix=", "--ignore-submodules=", "--submodule=", "--diff-filter=",
    ),
    "status": ("--porcelain=", "--ignored=", "--find-renames="),
}

SHELL_CONTROL_PUNCTUATION = set("();<>|&")
SED_READ_SCRIPT = re.compile(
    r"^\s*(?:\d+|\$)(?:\s*,\s*(?:\d+|\$))?\s*[pq]\s*$"
)


_OUTPUT_ADAPTER: HookOutputAdapter = CodexOutputAdapter()


def _set_output_adapter(adapter: HookOutputAdapter) -> HookOutputAdapter:
    """Select a host serializer and return the previous serializer."""
    global _OUTPUT_ADAPTER
    previous = _OUTPUT_ADAPTER
    _OUTPUT_ADAPTER = adapter
    return previous

RG_OPTIONS_WITH_VALUES = {
    "-g",
    "--glob",
    "--iglob",
    "--ignore-file",
    "--max-depth",
    "--path-separator",
    "--sort",
    "--sortr",
    "-t",
    "--type",
    "-T",
    "--type-not",
}
ENVIRONMENT_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SSH_TARGET = re.compile(r"^[A-Za-z0-9_.-]+(?:@[A-Za-z0-9_.-]+)?$")
SSH_READ_ONLY_GIT_SUBCOMMANDS = {"merge-base", "remote", "rev-parse", "status"}
GIT_REMOTE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


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


def _fresh_mutation_boundary() -> dict[str, Any]:
    return {
        "revision": 0,
        "tool_use_id": "",
        "status": "none",
        "lineage_valid": False,
        "before_root": "",
        "before_digest": "",
        "after_root": "",
        "after_digest": "",
    }


def _fresh_verification_state(contract: dict[str, Any]) -> dict[str, Any]:
    scale = str(contract["verification"]["scale"])
    legacy_unit_limit = click_verification_policy.approved_unit_limit(scale)
    assert legacy_unit_limit is not None
    return {
        "scale": scale,
        # Compatibility state field only. Runtime authority and advice do not
        # depend on this legacy plugin-authored number.
        "unit_limit": legacy_unit_limit,
        "status": "ready",
        "mutation_revision": 0,
        "verified_revision": -1,
        "failed_revision": -1,
        "attempts": 0,
        "unchanged_failure_retries": 0,
        "last_units": 0,
        "last_exit_code": None,
        "last_batch_digest": "",
        "locked_batch_digest": "",
        "runner_token_digest": "",
        "runner_claimed_at": 0,
        "running_evidence_keys": [],
        "running_environment_digests": {},
        "running_environment_binding": [],
        "running_environment_binding_digest": "",
        "running_executable_digests": {},
        "workspace_changed": False,
        "mutation_boundary": _fresh_mutation_boundary(),
        "started_at": 0,
    }


def _evidence_sources(state: dict[str, Any]) -> dict[str, Any] | None:
    """Return the v1 prose-free evidence ledger, or None for legacy state."""
    return click_evidence.sources_from_state(
        state,
        expected_contract_schema_version=CONTRACT_STATE_SCHEMA_VERSION,
    )


def _fresh_service_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "service_id": "",
        "request_digest": "",
        "runner_token_digest": "",
        "runner_claimed_at": 0,
        "supervisor_claimed_at": 0,
        "stop_requested": False,
        "supervisor_pid": 0,
        "child_pid": 0,
        "started_at": 0,
        "last_exit_code": None,
    }


def _fresh_observation_state() -> dict[str, Any]:
    return {"entries": {}}


def _fresh_mutation_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "request_digest": "",
        "runner_token_digest": "",
        "runner_claimed_at": 0,
        "started_at": 0,
        "last_exit_code": None,
    }


def _mutation_is_running(mutation: Any) -> bool:
    if not isinstance(mutation, dict) or mutation.get("status") != "running":
        return False
    # Expiry cannot prove that a claimed child has stopped. Keep a claimed
    # mutation active until it records a result or the user explicitly cancels.
    if mutation.get("runner_claimed_at"):
        return True
    started_at = int(mutation.get("started_at", 0))
    return bool(
        started_at
        and time.time() - started_at <= MUTATION_RUNNING_TTL_SECONDS
    )


def _unclaimed_reservation_is_fresh(value: Any, ttl_seconds: int) -> bool:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return False
    age = time.time() - value
    return 0 <= age <= ttl_seconds


def _observation_is_running(entry: Any) -> bool:
    if not isinstance(entry, dict) or entry.get("status") != "running":
        return False
    claimed_at = entry.get("runner_claimed_at", 0)
    if not isinstance(claimed_at, int) or isinstance(claimed_at, bool):
        return True
    if claimed_at > 0:
        return True
    started_at = entry.get("started_at", 0)
    if not isinstance(started_at, int) or isinstance(started_at, bool):
        return True
    if started_at <= 0 or time.time() < started_at:
        return True
    return _unclaimed_reservation_is_fresh(
        started_at, OBSERVATION_RESERVATION_TTL_SECONDS
    )


def _write_review_state(event: dict[str, Any]) -> None:
    _write_json(
        _review_path(event),
        {
            "status": "review",
            "observations": _fresh_observation_state(),
            "updated_at": int(time.time()),
        },
    )


def _read_review_state(event: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(_review_path(event).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"status": "none"}
    return value if isinstance(value, dict) else {"status": "none"}


def _save_review_state(event: dict[str, Any], state: dict[str, Any]) -> None:
    state["updated_at"] = int(time.time())
    _write_json(_review_path(event), state)


def _clear_review_state(event: dict[str, Any]) -> None:
    try:
        _review_path(event).unlink()
    except OSError:
        pass


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
    state = _read_contract_state(event)
    if state.get("status") != "approved":
        return ""
    mutation = state.get("mutation")
    if _mutation_is_running(mutation):
        return "Click blocked a second mutation while a structured mutation is running."
    if isinstance(mutation, dict) and mutation.get("status") == "running":
        state["mutation"] = _fresh_mutation_state()
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return "Click verification state is unavailable; stage and approve the contract again."
    if verification.get("status") == "running":
        return "Click blocked this mutation while the final verification batch is running."
    sources = _evidence_sources(state)
    if sources is None:
        return (
            "This active contract predates evidence-id completion tracking. Cancel it, "
            "stage the proposal again, and obtain fresh approval before mutation."
        )
    if not sources:
        return (
            "Click evidence state is unavailable or malformed; cancel and stage the "
            "contract again before changing the implementation."
        )

    observations = state.get("observations")
    if isinstance(observations, dict):
        entries = observations.get("entries")
        if isinstance(entries, dict):
            for entry in entries.values():
                if _observation_is_running(entry):
                    return (
                        "Click blocked this mutation while an approved read or search is "
                        "running. Wait for that evidence before changing the implementation."
                    )

    previous_revision = int(verification.get("mutation_revision", 0))
    workspace = Path(str(event.get("cwd", ""))).resolve()
    snapshot = _git_workspace_snapshot(workspace)
    snapshot_root = (
        os.path.normcase(str(snapshot.get("root", "")))
        if isinstance(snapshot, dict)
        else ""
    )
    snapshot_digest = (
        str(snapshot.get("digest", "")) if isinstance(snapshot, dict) else ""
    )
    reusable_sources = [
        source
        for source in sources.values()
        if isinstance(source, dict)
        and source.get("verified_dependency_provider")
        in click_dependency_cache.PROVIDER_NAMES
        and isinstance(source.get("verified_revision"), int)
        and not isinstance(source.get("verified_revision"), bool)
        and int(source.get("verified_revision", -1)) >= 0
    ]
    current_receipts = [
        source
        for source in reusable_sources
        if source.get("status") == "passed"
        and int(source.get("verified_revision", -1)) == previous_revision
    ]
    prior_boundary = verification.get("mutation_boundary")
    if current_receipts:
        lineage_valid = bool(
            snapshot_root
            and snapshot_digest
            and all(
                source.get("verified_root") == snapshot_root
                and source.get("verified_tree_digest") == snapshot_digest
                for source in current_receipts
            )
        )
    elif reusable_sources:
        lineage_valid = bool(
            isinstance(prior_boundary, dict)
            and prior_boundary.get("status") == "recorded"
            and prior_boundary.get("lineage_valid") is True
            and prior_boundary.get("revision") == previous_revision
            and prior_boundary.get("after_root") == snapshot_root
            and prior_boundary.get("after_digest") == snapshot_digest
        )
    else:
        lineage_valid = bool(snapshot_root and snapshot_digest)

    revision = previous_revision + 1
    verification["mutation_revision"] = revision
    tool_use_id = str(event.get("tool_use_id", ""))
    verification["mutation_boundary"] = {
        "revision": revision,
        "tool_use_id": tool_use_id,
        "status": (
            "running"
            if tool_use_id and lineage_valid and snapshot_root and snapshot_digest
            else "invalid"
        ),
        "lineage_valid": lineage_valid,
        "before_root": snapshot_root,
        "before_digest": snapshot_digest,
        "after_root": "",
        "after_digest": "",
    }
    if verification.get("status") == "passed":
        verification["status"] = "stale"
    elif verification.get("status") == "failed":
        verification["status"] = "ready"
        verification["failed_revision"] = -1
        verification["unchanged_failure_retries"] = 0
        verification["workspace_changed"] = False
    state["verification"] = verification
    for source in sources.values():
        if not isinstance(source, dict):
            continue
        was_passed = source.get("status") == "passed"
        source["status"] = "stale" if was_passed else "ready"
        source["unchanged_failure_retries"] = 0
        source["last_exit_code"] = None
        if not source.get("locked_check_digest"):
            source["last_check_digest"] = ""
    external = state.get("external_evidence")
    browser_required = bool(
        isinstance(external, dict) and external.get("browser_required") is True
    )
    browser_source_key = (
        str(external.get("browser_source_key", ""))
        if isinstance(external, dict)
        else ""
    )
    if not browser_source_key and isinstance(external, dict):
        legacy_source_id = str(external.get("browser_source_id", ""))
        browser_source_key = _evidence_key(legacy_source_id) if legacy_source_id else ""
    state["external_evidence"] = _fresh_external_evidence_state(
        required=browser_required,
        source_key=browser_source_key,
    )
    state["observations"] = _fresh_observation_state()
    _save_contract_state(event, state)
    return ""


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


def _decode_capability_request(
    raw: str,
    label: str,
    *,
    version: int = CAPABILITY_PROTOCOL_VERSION,
) -> tuple[dict[str, Any] | None, str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None, f"{label} request must be valid JSON."
    if not isinstance(value, dict):
        return None, f"{label} request must be a JSON object."
    if value.get("version") != version:
        return (
            None,
            f"{label} request `version` must be {version}.",
        )
    return value, ""


def _validate_argv(value: Any, label: str) -> tuple[list[str] | None, str]:
    if not isinstance(value, list) or not value:
        return None, f"{label} `argv` must be a non-empty string list."
    if len(value) > MAX_ARGV_ITEMS:
        return None, f"{label} `argv` may contain at most {MAX_ARGV_ITEMS} items."
    if any(
        not isinstance(item, str) or not item or "\x00" in item for item in value
    ):
        return None, f"Every {label} `argv` item must be a non-empty NUL-free string."
    argv = list(value)
    if ENVIRONMENT_ASSIGNMENT.match(argv[0]):
        return (
            None,
            f"{label} cannot use a NAME=value environment prefix. Pass direct argv; "
            "a future protocol may add an explicit environment field.",
        )
    executable = _policy_executable_name(argv[0])
    if executable in SHELL_EXECUTABLES:
        return (
            None,
            f"{label} cannot invoke a shell interpreter. Pass the executable and each "
            "argument directly instead of using `-c` or `-Command`.",
        )
    if executable in PROCESS_CONTROL_EXECUTABLES:
        return (
            None,
            f"{label} cannot invoke the process-control executable `{executable}`. "
            "Use a target-specific lifecycle command that cannot terminate Codex or "
            "unrelated processes.",
        )
    return argv, ""


def _policy_executable_name(value: str) -> str:
    """Normalize Win32 executable aliases before policy comparisons."""
    executable = value.replace("\\", "/").rsplit("/", 1)[-1].lower()
    executable = executable.rstrip(" .")
    if executable.endswith(".exe"):
        executable = executable[:-4].rstrip(" .")
    return executable


def _looks_like_managed_service(argv: list[str]) -> bool:
    executable = Path(argv[0]).name.lower()
    if executable.endswith(".exe"):
        executable = executable[:-4]
    arguments = [argument.lower() for argument in argv[1:]]
    if executable in MANAGED_SERVICE_EXECUTABLES:
        return True
    if executable == "py" or re.fullmatch(r"(?:python|pypy)\d*(?:\.\d+)?", executable):
        if executable == "py" and arguments and re.fullmatch(
            r"-\d+(?:\.\d+)?(?:-\d+)?", arguments[0]
        ):
            arguments = arguments[1:]
        if len(arguments) >= 2 and arguments[:2] == ["-m", "http.server"]:
            return True
        return any(marker in arguments for marker in {"runserver"})
    if executable in {"npm", "pnpm", "yarn", "bun"}:
        meaningful = {
            argument
            for argument in arguments
            if argument not in {"run", "exec", "x", "--"}
            and not argument.startswith("-")
        }
        return bool(meaningful & MANAGED_SERVICE_SCRIPT_MARKERS)
    if executable in {"npx", "pnpx", "bunx"}:
        return any(
            Path(argument).name.lower() in MANAGED_SERVICE_EXECUTABLES
            for argument in arguments
            if not argument.startswith("-")
        )
    return any(marker in arguments for marker in {"runserver"})


def _validate_inspection_request(
    raw: str,
) -> tuple[dict[str, Any] | None, bool, str]:
    value, error = _decode_capability_request(raw, "Inspection")
    if error:
        return None, False, error
    assert value is not None
    unknown = sorted(set(value) - INSPECTION_REQUEST_FIELDS)
    if unknown:
        rendered = ", ".join(f"`{field}`" for field in unknown)
        return None, False, f"Inspection request contains unsupported field(s): {rendered}."
    commands = value.get("commands")
    if not isinstance(commands, list) or not commands:
        return None, False, "Inspection `commands` must be a non-empty argv-list list."
    if len(commands) > MAX_INSPECTION_COMMANDS:
        return (
            None,
            False,
            f"Inspection may contain at most {MAX_INSPECTION_COMMANDS} commands.",
        )
    normalized: list[list[str]] = []
    broad = False
    for index, raw_argv in enumerate(commands, start=1):
        argv, argv_error = _validate_argv(raw_argv, f"Inspection command {index}")
        if argv_error:
            return None, False, argv_error
        assert argv is not None
        if not _is_read_only_tokens(list(argv)):
            return (
                None,
                False,
                f"Inspection command {index} is not a supported read-only argv operation.",
            )
        broad = broad or _is_broad_exploration_tokens(argv)
        normalized.append(argv)
    return {"version": CAPABILITY_PROTOCOL_VERSION, "commands": normalized}, broad, ""


def _validate_mutation_request(raw: str) -> tuple[dict[str, Any] | None, str]:
    value, error = _decode_capability_request(raw, "Mutation")
    if error:
        return None, error
    assert value is not None
    unknown = sorted(set(value) - MUTATION_REQUEST_FIELDS)
    if unknown:
        rendered = ", ".join(f"`{field}`" for field in unknown)
        return None, f"Mutation request contains unsupported field(s): {rendered}."
    argv, argv_error = _validate_argv(value.get("argv"), "Mutation")
    if argv_error:
        return None, argv_error
    assert argv is not None
    if _looks_like_managed_service(argv):
        return (
            None,
            "Long-running local servers must use `click-gate service` so Click owns "
            "the exact child lifecycle and cannot strand a foreground mutation.",
        )
    return {"version": CAPABILITY_PROTOCOL_VERSION, "argv": argv}, ""


def _validate_service_request(raw: str) -> tuple[dict[str, Any] | None, str]:
    value, error = _decode_capability_request(raw, "Managed service")
    if error:
        return None, error
    assert value is not None
    unknown = sorted(set(value) - SERVICE_REQUEST_FIELDS)
    if unknown:
        rendered = ", ".join(f"`{field}`" for field in unknown)
        return None, f"Managed service request contains unsupported field(s): {rendered}."
    action = value.get("action")
    if action not in MANAGED_SERVICE_ACTIONS:
        allowed = ", ".join(sorted(MANAGED_SERVICE_ACTIONS))
        return None, f"Managed service `action` must be one of: {allowed}."
    if action == "stop":
        if "argv" in value:
            return None, "Managed service stop must omit `argv`."
        return {"version": CAPABILITY_PROTOCOL_VERSION, "action": "stop"}, ""
    argv, argv_error = _validate_argv(value.get("argv"), "Managed service")
    if argv_error:
        return None, argv_error
    assert argv is not None
    if not _looks_like_managed_service(argv):
        return (
            None,
            "Managed service start accepts a recognizable local development server, "
            "not an arbitrary detached command.",
        )
    return {
        "version": CAPABILITY_PROTOCOL_VERSION,
        "action": "start",
        "argv": argv,
    }, ""


def _validate_verification_batch(
    raw: str,
    scale: str,
    evidence_sources: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, int, str]:
    value, error = _decode_capability_request(
        raw,
        "Verification batch",
        version=VERIFICATION_PROTOCOL_VERSION,
    )
    if error:
        return None, 0, error
    assert value is not None
    if "commands" in value:
        return (
            None,
            0,
            "Click verification uses `checks` with argv arrays and a submitted "
            "`class`; legacy shell-string `commands` are no longer accepted.",
        )
    unknown = sorted(set(value) - VERIFICATION_BATCH_FIELDS)
    if unknown:
        rendered = ", ".join(f"`{field}`" for field in unknown)
        return None, 0, f"Verification batch contains unsupported field(s): {rendered}."
    checks = value.get("checks")
    if not isinstance(checks, list) or not checks:
        return None, 0, "Verification batch `checks` must be a non-empty list."
    normalized: list[dict[str, Any]] = []
    units = 0
    for index, check in enumerate(checks, start=1):
        if not isinstance(check, dict):
            return None, 0, f"Verification check {index} must be an object."
        unknown_check = sorted(set(check) - VERIFICATION_CHECK_FIELDS)
        if unknown_check:
            rendered = ", ".join(f"`{field}`" for field in unknown_check)
            return None, 0, f"Verification check {index} has unsupported field(s): {rendered}."
        evidence_id = check.get("evidence_id")
        if evidence_sources is not None:
            if not isinstance(evidence_id, str) or not EVIDENCE_ID_PATTERN.fullmatch(
                evidence_id
            ):
                return (
                    None,
                    0,
                    f"Verification check {index} `evidence_id` must name one declared "
                    "argv evidence source.",
                )
            source = evidence_sources.get(_evidence_key(evidence_id))
            if not isinstance(source, dict):
                return (
                    None,
                    0,
                    f"Verification check {index} references unknown evidence id "
                    f"`{evidence_id}`.",
                )
            if source.get("kind") != "argv":
                return (
                    None,
                    0,
                    f"Verification check {index} evidence `{evidence_id}` has kind "
                    f"`{source.get('kind')}`, not `argv`.",
                )
        elif evidence_id is not None and (
            not isinstance(evidence_id, str)
            or not EVIDENCE_ID_PATTERN.fullmatch(evidence_id)
        ):
            return None, 0, f"Verification check {index} `evidence_id` is invalid."
        argv, argv_error = _validate_argv(check.get("argv"), f"Verification check {index}")
        if argv_error:
            return None, 0, argv_error
        assert argv is not None
        read_only = _is_read_only_tokens(list(argv))
        minimum_class = (
            "broad" if read_only and _is_broad_exploration_tokens(argv) else "targeted"
        ) if read_only else _minimum_verification_class(argv)
        if minimum_class is None:
            return (
                None,
                0,
                f"Verification check {index} is neither read-only nor a recognized check.",
            )
        check_class = check.get("class")
        if check_class not in VERIFICATION_CLASSES:
            allowed = ", ".join(VERIFICATION_CLASSES)
            return None, 0, f"Verification check {index} `class` must be one of: {allowed}."
        effective_class = click_verification_meter.effective_class(
            check_class, minimum_class
        )
        assert effective_class is not None
        effective_units = click_verification_meter.class_units(effective_class)
        assert effective_units is not None
        units += effective_units
        normalized_check: dict[str, Any] = {
            "argv": argv,
            "class": effective_class,
        }
        if isinstance(evidence_id, str):
            normalized_check["evidence_id"] = evidence_id
        normalized.append(normalized_check)
    return {
        "version": VERIFICATION_PROTOCOL_VERSION,
        "checks": normalized,
    }, units, ""


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


def _verification_groups(
    batch: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], str]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    completed_groups: set[str] = set()
    active_group = ""
    for check in batch["checks"]:
        source_key = _evidence_key(str(check["evidence_id"]))
        if source_key != active_group:
            if source_key in completed_groups:
                return {}, (
                    "Checks for one argv evidence id must be adjacent in a verification "
                    "batch so partial failure can be recorded deterministically."
                )
            if active_group:
                completed_groups.add(active_group)
            active_group = source_key
        grouped.setdefault(source_key, []).append(check)
    return grouped, ""


def _verification_group_digest(checks: list[dict[str, Any]]) -> str:
    # Receipt identity is the executable request, not Click's compatibility
    # class or legacy unit heuristic.
    payload = [{"argv": check["argv"]} for check in checks]
    return _capability_digest({"checks": payload})


def _verification_group_units(checks: list[dict[str, Any]]) -> int:
    units = click_verification_meter.total_units(check["class"] for check in checks)
    assert units is not None
    return units


def _file_content_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
    except OSError:
        return ""
    return hasher.hexdigest()


def _verification_environment(*, cwd: Path) -> dict[str, str]:
    # Shell launchers add bookkeeping variables that do not change check
    # semantics and are not stable across the Hook process and its rewritten
    # runner. Keep user/project variables fingerprinted, but canonicalize these
    # launcher-owned values so an unchanged receipt remains portable.
    volatile = {
        "_",
        "__CF_USER_TEXT_ENCODING",
        "CMDCMDLINE",
        "CLICK_CONFIG_HOME",
        "COMMAND_MODE",
        "LC_CTYPE",
        "OLDPWD",
        "PROMPT",
        "PROMPT_COMMAND",
        "PS1",
        "PS2",
        "PLUGIN_DATA",
        "PLUGIN_ROOT",
        "SHLVL",
    }
    environment = {
        str(key): str(value)
        for key, value in os.environ.items()
        if str(key).upper() not in volatile and not str(key).startswith("=")
    }
    environment["PWD"] = str(cwd.resolve())
    return environment


def _verification_environment_key(key: str) -> str:
    return key.upper() if os.name == "nt" else key


def _verification_environment_hmac(
    runner_token: str, domain: str, value: str
) -> str:
    secret = hashlib.sha256(runner_token.encode()).digest()
    message = f"click-verification-{domain}\0{value}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _verification_environment_binding(
    environment: dict[str, str], runner_token: str
) -> list[dict[str, str]]:
    records = []
    for key, value in environment.items():
        normalized_key = _verification_environment_key(str(key))
        records.append(
            {
                "key_digest": _verification_environment_hmac(
                    runner_token, "key", normalized_key
                ),
                "value_digest": _verification_environment_hmac(
                    runner_token, "value", f"{normalized_key}\0{value}"
                ),
            }
        )
    return sorted(records, key=lambda item: item["key_digest"])


def _verification_environment_binding_digest(
    binding: Any, runner_token: str
) -> str:
    try:
        canonical = json.dumps(
            binding, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError):
        return ""
    return _verification_environment_hmac(runner_token, "binding", canonical)


def _verification_environment_binding_is_authentic(
    binding: Any, digest: Any, runner_token: str
) -> bool:
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return False
    expected = _verification_environment_binding_digest(binding, runner_token)
    return bool(expected and secrets.compare_digest(digest, expected))


def _verification_environment_from_binding(
    binding: Any,
    runner_token: str,
    current_environment: dict[str, str],
) -> tuple[dict[str, str] | None, bool, str]:
    if not isinstance(binding, list) or not binding or len(binding) > 4096:
        return None, False, "Click verification runner environment binding was malformed."
    expected: dict[str, str] = {}
    for record in binding:
        if not isinstance(record, dict) or set(record) != {
            "key_digest",
            "value_digest",
        }:
            return None, False, "Click verification runner environment binding was malformed."
        key_digest = record.get("key_digest")
        value_digest = record.get("value_digest")
        if (
            not isinstance(key_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", key_digest)
            or not isinstance(value_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", value_digest)
            or key_digest in expected
        ):
            return None, False, "Click verification runner environment binding was malformed."
        expected[key_digest] = value_digest

    projected: dict[str, str] = {}
    matched: set[str] = set()
    drifted = False
    for key, value in current_environment.items():
        normalized_key = _verification_environment_key(str(key))
        key_digest = _verification_environment_hmac(
            runner_token, "key", normalized_key
        )
        expected_value = expected.get(key_digest)
        if expected_value is None:
            continue
        current_value = _verification_environment_hmac(
            runner_token, "value", f"{normalized_key}\0{value}"
        )
        if not secrets.compare_digest(expected_value, current_value):
            drifted = True
        projected[str(key)] = str(value)
        matched.add(key_digest)
    if matched != set(expected):
        drifted = True
    return projected, drifted, ""


def _executable_search_path(environment: dict[str, str], *, cwd: Path) -> str:
    """Resolve relative PATH entries as the verification child will from its cwd."""
    entries: list[str] = []
    for raw_entry in environment.get("PATH", os.defpath).split(os.pathsep):
        entry = Path(raw_entry) if raw_entry else cwd
        if not entry.is_absolute():
            entry = cwd / entry
        entries.append(str(entry.resolve()))
    return os.pathsep.join(entries)


def _verification_executable_records(
    checks: list[dict[str, Any]], *, cwd: Path, environment: dict[str, str] | None = None
) -> list[dict[str, Any]] | None:
    effective_environment = environment or _verification_environment(cwd=cwd)
    search_path = _executable_search_path(effective_environment, cwd=cwd)
    executables: list[dict[str, Any]] = []
    for check in checks:
        argv = check.get("argv")
        executable = str(argv[0]) if isinstance(argv, list) and argv else ""
        candidate = Path(executable)
        if executable and (
            candidate.is_absolute() or _is_path_qualified_executable(executable)
        ):
            selected = candidate if candidate.is_absolute() else cwd / candidate
            resolved = shutil.which(str(selected))
        else:
            resolved = shutil.which(executable, path=search_path)
        item: dict[str, Any] = {"name": Path(executable).name.lower()}
        if resolved:
            try:
                resolved_candidate = Path(resolved)
                if not resolved_candidate.is_absolute():
                    resolved_candidate = cwd / resolved_candidate
                execution_path = Path(os.path.abspath(resolved_candidate))
                path = execution_path.resolve(strict=True)
                metadata = path.stat()
                item.update(
                    {
                        "selected_path": os.path.normcase(str(execution_path)),
                        "path": os.path.normcase(str(path)),
                        "size": int(metadata.st_size),
                        "mtime_ns": int(metadata.st_mtime_ns),
                        "content_digest": _file_content_digest(path),
                        "_execution_path": str(execution_path),
                    }
                )
            except (OSError, RuntimeError):
                item["path"] = "unresolved"
        else:
            item["path"] = "missing"
        executables.append(item)
    if any(
        not isinstance(item.get("content_digest"), str)
        or not item.get("content_digest")
        for item in executables
    ):
        return None
    return executables


def _verification_executable_payload(
    executables: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in executable.items()
            if key != "_execution_path"
        }
        for executable in executables
    ]


def _verification_environment_digest_from_records(
    executables: list[dict[str, Any]],
    *,
    cwd: Path,
    environment: dict[str, str],
) -> str:
    environment_payload = json.dumps(
        sorted(
            (
                _verification_environment_key(str(key)),
                str(value),
            )
            for key, value in environment.items()
        ),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    payload = {
        "cwd": os.path.normcase(str(cwd.resolve())),
        "os_name": os.name,
        "platform": sys.platform,
        "machine": platform.machine(),
        "python": list(sys.version_info[:3]),
        "executables": _verification_executable_payload(executables),
        "environment_digest": hashlib.sha256(environment_payload).hexdigest(),
    }
    return _capability_digest(payload)


def _verification_environment_digest(
    checks: list[dict[str, Any]], *, cwd: Path, environment: dict[str, str] | None = None
) -> str:
    effective_environment = environment or _verification_environment(cwd=cwd)
    executables = _verification_executable_records(
        checks, cwd=cwd, environment=effective_environment
    )
    if executables is None:
        return ""
    return _verification_environment_digest_from_records(
        executables, cwd=cwd, environment=effective_environment
    )


def _verification_receipt_matches(
    source: dict[str, Any],
    *,
    contract_digest: str,
    revision: int,
    group_digest: str,
    git_root: str,
    tree_digest: str,
    environment_digest: str,
) -> bool:
    if not all(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in (
            contract_digest,
            group_digest,
            tree_digest,
            environment_digest,
        )
    ):
        return False
    verified_at = source.get("verified_at", 0)
    if (
        not isinstance(verified_at, int)
        or isinstance(verified_at, bool)
        or verified_at <= 0
    ):
        return False
    return bool(
        source.get("status") == "passed"
        and int(source.get("verified_revision", -1)) == revision
        and source.get("verified_contract_digest") == contract_digest
        and source.get("verified_check_digest") == group_digest
        and source.get("verified_root") == git_root
        and source.get("verified_tree_digest") == tree_digest
        and source.get("verified_environment_digest") == environment_digest
    )


def _dependency_declarations(
    sources: dict[str, Any], source_keys: set[str]
) -> dict[str, list[str]]:
    declarations: dict[str, list[str]] = {}
    for source_key in source_keys:
        source = sources.get(source_key)
        patterns = source.get("dependency_patterns", []) if isinstance(source, dict) else []
        if isinstance(patterns, list) and patterns:
            declarations[source_key] = list(patterns)
    return declarations


def _dependency_receipt_is_valid(receipt: Any) -> bool:
    if not isinstance(receipt, dict):
        return False
    provider = receipt.get("provider")
    manifest_digest = receipt.get("manifest_digest")
    entry_digest = receipt.get("entry_digest")
    dependency_digest = receipt.get("dependency_digest")
    manifest_is_valid = bool(
        isinstance(manifest_digest, str)
        and (
            provider == click_dependency_cache.CONTRACT_PROVIDER_NAME
            and not manifest_digest
            or provider
            in {
                click_dependency_cache.MANIFEST_PROVIDER_NAME,
                click_dependency_cache.COMBINED_PROVIDER_NAME,
            }
            and re.fullmatch(r"[0-9a-f]{64}", manifest_digest)
        )
    )
    return bool(
        provider in click_dependency_cache.PROVIDER_NAMES
        and manifest_is_valid
        and isinstance(entry_digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", entry_digest)
        and isinstance(dependency_digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", dependency_digest)
        and click_dependency_cache.receipt_paths_are_valid(
            receipt.get("resolved_paths")
        )
    )


def _dependency_receipt_matches(
    source: dict[str, Any],
    receipt: Any,
    *,
    contract_digest: str,
    revision: int,
    group_digest: str,
    git_root: str,
    environment_digest: str,
) -> bool:
    if not _dependency_receipt_is_valid(receipt):
        return False
    if not all(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in (contract_digest, group_digest, environment_digest)
    ):
        return False
    verified_revision = source.get("verified_revision", -1)
    verified_at = source.get("verified_at", 0)
    if (
        not isinstance(verified_revision, int)
        or isinstance(verified_revision, bool)
        or verified_revision < 0
        or verified_revision >= revision
        or not isinstance(verified_at, int)
        or isinstance(verified_at, bool)
        or verified_at <= 0
        or not isinstance(source.get("verified_tree_digest"), str)
        or re.fullmatch(
            r"[0-9a-f]{64}", str(source.get("verified_tree_digest", ""))
        )
        is None
    ):
        return False
    return bool(
        source.get("status") == "stale"
        and source.get("verified_contract_digest") == contract_digest
        and source.get("verified_check_digest") == group_digest
        and source.get("verified_root") == git_root
        and source.get("verified_environment_digest") == environment_digest
        and source.get("verified_dependency_provider") == receipt["provider"]
        # The full manifest digest is audit metadata. The normalized relevant
        # entry is the authority boundary, so unrelated settings may change.
        and source.get("verified_dependency_entry_digest")
        == receipt["entry_digest"]
        and source.get("verified_dependency_digest")
        == receipt["dependency_digest"]
        and source.get("verified_dependency_paths")
        == receipt["resolved_paths"]
    )


def _clear_dependency_receipt(source: dict[str, Any]) -> None:
    source["verified_dependency_provider"] = ""
    source["verified_dependency_manifest_digest"] = ""
    source["verified_dependency_entry_digest"] = ""
    source["verified_dependency_digest"] = ""
    source["verified_dependency_paths"] = []
    source["dependency_reuse_count"] = 0
    source["last_dependency_reused_at"] = 0
    source["last_dependency_reused_from_revision"] = -1


def _store_dependency_receipt(
    source: dict[str, Any], receipt: Any
) -> None:
    _clear_dependency_receipt(source)
    if not _dependency_receipt_is_valid(receipt):
        return
    source["verified_dependency_provider"] = receipt["provider"]
    source["verified_dependency_manifest_digest"] = receipt["manifest_digest"]
    source["verified_dependency_entry_digest"] = receipt["entry_digest"]
    source["verified_dependency_digest"] = receipt["dependency_digest"]
    source["verified_dependency_paths"] = list(receipt["resolved_paths"])


def _promote_dependency_receipt(
    source: dict[str, Any],
    receipt: dict[str, Any],
    *,
    revision: int,
    tree_digest: str,
) -> None:
    prior_revision = int(source.get("verified_revision", -1))
    source["status"] = "passed"
    source["verified_revision"] = revision
    source["verified_tree_digest"] = tree_digest
    source["verified_dependency_manifest_digest"] = receipt["manifest_digest"]
    source["verified_dependency_paths"] = list(receipt["resolved_paths"])
    source["last_exit_code"] = 0
    source["unchanged_failure_retries"] = 0
    source["dependency_reuse_count"] = int(
        source.get("dependency_reuse_count", 0)
    ) + 1
    source["last_dependency_reused_at"] = int(time.time()) or 1
    source["last_dependency_reused_from_revision"] = prior_revision


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


def _git_option_allowed(subcommand: str, token: str) -> bool:
    if token in GIT_READ_ONLY_EXACT_OPTIONS.get(subcommand, set()):
        return True
    if any(
        token.startswith(prefix)
        for prefix in GIT_READ_ONLY_OPTION_PREFIXES.get(subcommand, ())
    ):
        return True
    if subcommand in GIT_DIFF_RENDERING_SUBCOMMANDS and re.fullmatch(r"-U\d+", token):
        return True
    if subcommand == "log" and re.fullmatch(r"-\d+", token):
        return True
    return False


def _is_read_only_git_remote_arguments(arguments: list[str]) -> bool:
    if not arguments or arguments[0] != "get-url":
        return False
    remote_names = [
        argument
        for argument in arguments[1:]
        if argument not in {"--", "--all", "--push"}
    ]
    return (
        len(remote_names) == 1
        and GIT_REMOTE_NAME.fullmatch(remote_names[0]) is not None
    )


def _parse_read_only_git_tokens(
    tokens: list[str],
) -> tuple[list[str], str, list[str]] | None:
    if not tokens or Path(tokens[0]).name.lower() not in {"git", "git.exe"}:
        return None
    global_arguments: list[str] = []
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "-C":
            if index + 1 >= len(tokens):
                return None
            global_arguments.extend([token, tokens[index + 1]])
            index += 2
            continue
        if token.startswith(GIT_GLOBAL_ALLOWED_PREFIXES):
            global_arguments.append(token)
            index += 1
            continue
        if token in {"--no-pager", "--no-optional-locks"}:
            index += 1
            continue
        if (
            token in GIT_GLOBAL_REJECTED_OPTIONS
            or token.startswith("--config-env=")
            or (token.startswith("-c") and token != "-C")
        ):
            return None
        if token.startswith("-"):
            return None
        subcommand = token
        break
    else:
        return None

    if subcommand not in READ_ONLY_GIT_SUBCOMMANDS:
        return None
    arguments = tokens[index + 1 :]
    options_finished = False
    for argument in arguments:
        if options_finished:
            continue
        if argument == "--":
            options_finished = True
            continue
        if argument.startswith("-") and not _git_option_allowed(subcommand, argument):
            return None
    if subcommand == "remote" and not _is_read_only_git_remote_arguments(arguments):
        return None
    return global_arguments, subcommand, arguments


def _git_subcommand(tokens: list[str]) -> str:
    parsed = _parse_read_only_git_tokens(tokens)
    return parsed[1] if parsed is not None else ""


def _sanitized_git_environment(
    source: dict[str, str] | None = None,
    *,
    workspace: Path | None = None,
) -> dict[str, str]:
    inherited = os.environ if source is None else source
    environment = {
        key: value
        for key, value in inherited.items()
        if not key.upper().startswith("GIT_")
        and key.upper() != "PATH"
        and not _unsafe_inherited_environment_key(key)
    }
    environment["PATH"] = _sanitized_executable_path(
        inherited.get("PATH", ""), workspace=workspace
    )
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    return environment


def _build_read_only_git_argv(tokens: list[str]) -> tuple[list[str] | None, str]:
    parsed = _parse_read_only_git_tokens(tokens)
    if parsed is None:
        return None, "Git argv is outside Click's supported read-only option policy."
    global_arguments, subcommand, arguments = parsed
    forced = ["--no-ext-diff", "--no-textconv"] if subcommand in GIT_DIFF_RENDERING_SUBCOMMANDS else []
    safe_config = [
        "-c",
        "core.fsmonitor=false",
        "-c",
        "diff.external=",
        "-c",
        "log.showSignature=false",
        "-c",
        "format.pretty=medium",
    ]
    return [
        "git",
        "--no-pager",
        "--no-optional-locks",
        *safe_config,
        *global_arguments,
        subcommand,
        *forced,
        *arguments,
    ], ""


def _shell_segments(command: str) -> list[list[str]] | None:
    if "\n" in command or "\r" in command or "`" in command:
        return None
    try:
        lexer = shlex.shlex(
            command,
            posix=True,
            punctuation_chars="".join(sorted(SHELL_CONTROL_PUNCTUATION)),
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None

    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in {"&&", "|"}:
            if not segments[-1]:
                return None
            segments.append([])
            continue
        if token and set(token).issubset(SHELL_CONTROL_PUNCTUATION):
            return None
        segments[-1].append(token)
    if not segments[-1]:
        return None
    return segments


def _command_parts(tokens: list[str]) -> tuple[str, list[str]]:
    remaining = list(tokens)
    while remaining and "=" in remaining[0] and not remaining[0].startswith(("=", "-")):
        name, _, _ = remaining[0].partition("=")
        if not name.replace("_", "a").isalnum():
            break
        remaining.pop(0)
    if not remaining:
        return "", []
    executable = Path(remaining[0]).name.lower()
    if executable.endswith(".exe"):
        executable = executable[:-4]
    return executable, [item.lower() for item in remaining[1:]]


def _contains_deep_verification_marker(values: list[str]) -> bool:
    joined = " ".join(values)
    return any(marker in joined for marker in DEEP_VERIFICATION_MARKERS)


def _arguments_have_filter(arguments: list[str]) -> bool:
    return any(
        argument in TEST_FILTER_OPTIONS
        or any(argument.startswith(f"{option}=") for option in TEST_FILTER_OPTIONS)
        for argument in arguments
    )


def _verification_targets(
    arguments: list[str], *, skip_words: set[str] | None = None
) -> list[str]:
    skip_words = skip_words or set()
    targets: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            targets.extend(
                item for item in arguments[index + 1 :] if item not in skip_words
            )
            break
        if argument in TEST_OPTIONS_WITH_VALUES:
            index += 2
            continue
        if argument.startswith("-") or argument in skip_words:
            index += 1
            continue
        targets.append(argument)
        index += 1
    return targets


def _scope_with_kind_floor(scope: str, values: list[str]) -> str:
    if not _contains_deep_verification_marker(values):
        return scope
    return "broad" if scope == "targeted" else "deep"


def _minimum_test_runner_class(runner: str, arguments: list[str]) -> str:
    if runner == "unittest" and "discover" in arguments:
        return _scope_with_kind_floor("broad", [runner, *arguments])
    if _arguments_have_filter(arguments):
        return _scope_with_kind_floor("broad", [runner, *arguments])
    broad_targets = {".", "./", "...", "./...", "all", "test", "tests", "spec"}
    targets = _verification_targets(arguments, skip_words={"run", "exec", "x"})
    scope = "broad"
    if len(targets) == 1:
        target = targets[0]
        normalized = target.rstrip("/\\")
        if normalized not in broad_targets and (
            "::" in target
            or Path(normalized).suffix.lower() in TEST_TARGET_SUFFIXES
            or (runner == "unittest" and "." in normalized)
        ):
            scope = "targeted"
    return _scope_with_kind_floor(scope, [runner, *arguments])


def _minimum_verification_class(
    tokens: list[str], *, wrapper_depth: int = 0
) -> str | None:
    executable, arguments = _command_parts(tokens)
    if not executable:
        return None
    if executable in DEEP_VERIFICATION_EXECUTABLES:
        return "deep"
    if executable in {"python", "python3", "py", "pypy", "pypy3"}:
        if executable == "py" and arguments and re.fullmatch(
            r"-\d+(?:\.\d+)?(?:-\d+)?", arguments[0]
        ):
            arguments = arguments[1:]
        if len(arguments) < 2 or arguments[0] != "-m":
            return None
        module = arguments[1]
        if module not in PYTHON_VERIFICATION_MODULES:
            return None
        if module == "coverage":
            return "deep"
        return _minimum_test_runner_class(module, arguments[2:])
    if executable == "uv":
        if wrapper_depth >= 2 or not arguments or arguments[0] != "run":
            return None
        nested = arguments[1:]
        while nested and nested[0].startswith("-"):
            nested = nested[1:]
        return _minimum_verification_class(nested, wrapper_depth=wrapper_depth + 1)
    if executable in VERIFICATION_EXECUTABLES:
        if executable in {"bats", "jest", "phpunit", "pytest", "rspec", "vitest"}:
            return _minimum_test_runner_class(executable, arguments)
        return "broad"
    if executable == "node":
        if any(
            argument in {"-e", "--eval", "-p", "--print"}
            or argument.startswith(("--eval=", "--print="))
            for argument in arguments
        ):
            return None
        if arguments[:1] == ["--check"]:
            targets = [argument for argument in arguments[1:] if not argument.startswith("-")]
            return (
                "targeted"
                if len(targets) == 1
                and Path(targets[0]).suffix.lower() in {".cjs", ".js", ".mjs"}
                else None
            )
        if "--test" in arguments:
            test_arguments = [argument for argument in arguments if argument != "--test"]
            return _minimum_test_runner_class("node", test_arguments)
        return None
    if executable in {"npm", "pnpm", "yarn", "bun"}:
        meaningful = [item for item in arguments if item not in {"run", "exec", "x"}]
        target = meaningful[0] if meaningful else ""
        if not (
            any(marker in target for marker in VERIFICATION_NAME_MARKERS)
            or target in {"build", "check", "lint", "typecheck", "type-check"}
        ):
            return None
        return "deep" if _contains_deep_verification_marker(meaningful) else "broad"
    if executable in {"npx", "pnpx", "bunx"}:
        target_index = next(
            (index for index, argument in enumerate(arguments) if not argument.startswith("-")),
            -1,
        )
        if target_index < 0:
            return None
        target = arguments[target_index]
        nested_arguments = arguments[target_index + 1 :]
        if target in DEEP_VERIFICATION_EXECUTABLES:
            return "deep"
        if target in {"jest", "pytest", "vitest"}:
            return _minimum_test_runner_class(target, nested_arguments)
        if target in VERIFICATION_EXECUTABLES:
            return "broad"
        if any(marker in target for marker in VERIFICATION_NAME_MARKERS):
            return "deep"
        return None
    if executable == "cargo":
        if not arguments or arguments[0] not in {
            "audit",
            "bench",
            "check",
            "clippy",
            "nextest",
            "test",
        }:
            return None
        if arguments[0] in {"audit", "bench"}:
            return "deep"
        if arguments[0] in {"check", "clippy", "nextest"}:
            return "broad"
        test_targets = [
            argument
            for argument in arguments[1:]
            if not argument.startswith("-") and argument not in {"all", "workspace"}
        ]
        return "targeted" if len(test_targets) == 1 else "broad"
    if executable == "go":
        if not arguments or arguments[0] not in {"test", "vet"}:
            return None
        if arguments[0] == "vet":
            return "broad"
        if _arguments_have_filter(arguments[1:]):
            return "broad"
        targets = [argument for argument in arguments[1:] if not argument.startswith("-")]
        recursive = any(target == "./..." or target.endswith("/...") for target in targets)
        return "targeted" if len(targets) == 1 and not recursive else "broad"
    if executable == "ruff":
        if not arguments or arguments[0] != "check":
            return None
        targets = _verification_targets(arguments[1:])
        return (
            "targeted"
            if len(targets) == 1
            and Path(targets[0].rstrip("/\\")).suffix.lower() in TEST_TARGET_SUFFIXES
            else "broad"
        )
    if executable == "mypy":
        targets = _verification_targets(arguments)
        return (
            "targeted"
            if len(targets) == 1 and Path(targets[0]).suffix.lower() == ".py"
            else "broad"
        )
    if executable == "tsc":
        return "broad" if "--noemit" in arguments else None
    if executable in {"dotnet", "gradle", "gradlew", "gradlew.bat", "mvn", "mvnw", "mvnw.cmd"}:
        if not any(
            any(marker in argument for marker in VERIFICATION_NAME_MARKERS)
            for argument in arguments
        ):
            return None
        if _contains_deep_verification_marker(arguments):
            return "deep"
        return "targeted" if any("filter" in item for item in arguments) else "broad"
    if executable in {"make", "gmake", "cmake", "ctest", "pre-commit"}:
        recognized = executable in {"ctest", "pre-commit"} or any(
            any(marker in argument for marker in VERIFICATION_NAME_MARKERS)
            for argument in arguments
        )
        if not recognized:
            return None
        if _contains_deep_verification_marker(arguments):
            return "deep"
        if executable == "ctest" and any(item in {"-r", "--tests-regex"} for item in arguments):
            return _scope_with_kind_floor("broad", arguments)
        if executable == "pre-commit" and "--files" in arguments:
            file_index = arguments.index("--files") + 1
            files = [item for item in arguments[file_index:] if not item.startswith("-")]
            return "targeted" if len(files) == 1 else "broad"
        return "broad"
    stem = Path(executable).stem.lower()
    if any(marker in stem for marker in VERIFICATION_NAME_MARKERS):
        return "deep"
    return None


def _is_recognized_verification_tokens(tokens: list[str]) -> bool:
    return _minimum_verification_class(tokens) is not None


def _is_recognized_verification_command(command: str) -> bool:
    segments = _shell_segments(command)
    if segments:
        return any(_is_recognized_verification_tokens(segment) for segment in segments)
    try:
        fallback = shlex.split(command, posix=True)
    except ValueError:
        return False
    return _is_recognized_verification_tokens(fallback)


def _positional_arguments(
    arguments: list[str], options_with_values: set[str] | None = None
) -> list[str]:
    value_options = options_with_values or set()
    positions: list[str] = []
    skip_value = False
    options_finished = False
    for argument in arguments:
        lowered = argument.lower()
        if skip_value:
            skip_value = False
            continue
        if not options_finished and lowered == "--":
            options_finished = True
            continue
        if not options_finished and lowered in value_options:
            skip_value = True
            continue
        if not options_finished and any(
            lowered.startswith(f"{option}=") for option in value_options
        ):
            continue
        if not options_finished and lowered.startswith("-"):
            continue
        positions.append(lowered)
    return positions


def _targets_repository_root(targets: list[str]) -> bool:
    if not targets:
        return True
    return any(target.rstrip("/\\") in {"", ".", ".."} for target in targets)


def _is_broad_exploration_tokens(tokens: list[str]) -> bool:
    executable, arguments = _command_parts(tokens)
    if executable == "rg" and "--files" in arguments:
        targets = _positional_arguments(arguments, RG_OPTIONS_WITH_VALUES)
        return _targets_repository_root(targets)
    if executable == "find":
        targets = _positional_arguments(arguments)
        return _targets_repository_root(targets[:1])
    if executable == "tree":
        targets = _positional_arguments(arguments)
        return _targets_repository_root(targets)
    if executable == "ls":
        recursive = any(
            argument in {"-r", "--recursive"}
            for argument in arguments
        )
        if not recursive:
            return False
        targets = _positional_arguments(arguments)
        return _targets_repository_root(targets)
    if executable == "git":
        subcommand = _git_subcommand(tokens)
        if subcommand == "ls-files":
            index = tokens.index(subcommand)
            targets = _positional_arguments(
                [item.lower() for item in tokens[index + 1 :]]
            )
            return _targets_repository_root(targets)
        if subcommand == "ls-tree":
            index = tokens.index(subcommand)
            remainder = [item.lower() for item in tokens[index + 1 :]]
            if "--" not in remainder:
                return True
            targets = remainder[remainder.index("--") + 1 :]
            return _targets_repository_root(targets)
    return False


def _capability_digest(request: dict[str, Any]) -> str:
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


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
    encoded = base64.urlsafe_b64encode(
        json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()
    ).decode()
    arguments = [
        *_stateful_runner_prefix("run-observation"),
        str(state_path.resolve()),
        request_digest,
        runner_token,
        encoded,
    ]
    return _runner_shell_command(arguments)


def _prepare_observation(
    event: dict[str, Any],
    request: dict[str, Any],
    broad_inventory: bool,
    *,
    review: bool = False,
) -> tuple[str, str, str]:
    state_path = _review_path(event) if review else _contract_path(event)
    if review:
        state = _read_review_state(event)
        if state.get("status") != "review":
            return (
                "",
                "Click review state is unavailable; activate review mode again.",
                "",
            )
        revision = 0
    else:
        state = _read_contract_state(event)
        if state.get("status") != "approved":
            return (
                "",
                "Click observation state is unavailable; approve the contract again.",
                "",
            )
        mutation = state.get("mutation")
        if _mutation_is_running(mutation):
            return (
                "",
                "Wait for the structured Click mutation to finish before inspection.",
                "",
            )
        if isinstance(mutation, dict) and mutation.get("status") == "running":
            state["mutation"] = _fresh_mutation_state()
        verification = state.get("verification")
        if not isinstance(verification, dict):
            return (
                "",
                "Click verification state is unavailable; approve the contract again.",
                "",
            )
        if verification.get("status") == "running":
            return "", "The final Click verification batch is already running.", ""
        revision = int(verification.get("mutation_revision", 0))

    observations = state.get("observations")
    if not isinstance(observations, dict):
        observations = _fresh_observation_state()
    entries = observations.get("entries")
    if not isinstance(entries, dict):
        entries = {}

    digest = _capability_digest(request)
    advisories: list[str] = []
    if broad_inventory:
        prior_broad_success = False
        prior_broad_running = False
        for existing_digest, existing in entries.items():
            if not (
                existing_digest != digest
                and isinstance(existing, dict)
                and existing.get("broad_inventory") is True
                and int(existing.get("revision", -1)) == revision
            ):
                continue
            existing_status = str(existing.get("status", ""))
            if existing_status == "success":
                prior_broad_success = True
            elif existing_status == "running" and _observation_is_running(existing):
                prior_broad_running = True
        if prior_broad_success:
            advisories.append(
                "Click advisory: a repository-wide inventory already completed for this "
                "revision. This additional broad inventory is allowed through the same "
                "read-only runner, but reuse existing results or narrow the query when "
                "practical."
            )
        elif prior_broad_running:
            advisories.append(
                "Click advisory: another repository-wide inventory is already running for "
                "this revision. This distinct broad inventory is allowed through the same "
                "read-only runner, but waiting or narrowing avoids redundant work."
            )

    prior = entries.get(digest)
    unchanged_retries = 0
    if isinstance(prior, dict) and int(prior.get("revision", -1)) == revision:
        status = str(prior.get("status", ""))
        unchanged_retries = int(prior.get("unchanged_retries", 0))
        if status == "success":
            advisories.append(
                "Click advisory: this identical read or search already succeeded for the "
                "current revision. A fresh, separately authorized one-use runner is "
                "allowed, but reuse the existing result or narrow the query when practical."
            )
        if status == "running":
            if _observation_is_running(prior):
                return (
                    "",
                    "An exact observation runner for this request is already active. Wait "
                    "for it to record a result before issuing a fresh authorization.",
                    "",
                )
            status = "failed"
        if status in {"failed", "incomplete"}:
            if unchanged_retries >= 1:
                advisories.append(
                    "Click advisory: this identical read or search already failed or "
                    "produced incomplete output twice for the current revision. A fresh, "
                    "separately authorized retry is allowed, but repair, narrow, or change "
                    "the request when practical."
                )
            unchanged_retries += 1

    runner_token = secrets.token_urlsafe(24)
    entries[digest] = {
        "revision": revision,
        "status": "running",
        "attempts": int(prior.get("attempts", 0)) + 1
        if isinstance(prior, dict)
        else 1,
        "unchanged_retries": unchanged_retries,
        "runner_token_digest": hashlib.sha256(runner_token.encode()).hexdigest(),
        "runner_claimed_at": 0,
        "started_at": int(time.time()),
        "last_exit_code": None,
        "output_bytes": 0,
        "broad_inventory": broad_inventory,
    }
    while len(entries) > MAX_OBSERVATION_ENTRIES:
        entries.pop(next(iter(entries)))
    observations["entries"] = entries
    state["observations"] = observations
    if review:
        _save_review_state(event, state)
    else:
        _save_contract_state(event, state)
    return (
        _observation_runner_command(state_path, request, digest, runner_token),
        "",
        "\n".join(advisories),
    )


def _encoded_request(request: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()
    ).decode()


def _inspection_once_runner_command(request: dict[str, Any]) -> str:
    arguments = [
        sys.executable,
        str(Path(__file__).resolve()),
        "run-inspection-once",
        _encoded_request(request),
    ]
    return _runner_shell_command(arguments)


def _mutation_runner_command(
    event: dict[str, Any], request: dict[str, Any], request_digest: str, runner_token: str
) -> str:
    arguments = [
        *_stateful_runner_prefix("run-mutation"),
        str(_contract_path(event).resolve()),
        request_digest,
        runner_token,
        _encoded_request(request),
    ]
    return _runner_shell_command(arguments)


def _prepare_mutation(event: dict[str, Any], raw: str) -> tuple[str, str]:
    state = _read_contract_state(event)
    if state.get("status") != "approved":
        return "", "Approve the staged Click execution contract before mutation."
    request, error = _validate_mutation_request(raw)
    if error:
        return "", error
    assert request is not None
    mutation_error = _mark_contract_mutated(event)
    if mutation_error:
        return "", mutation_error

    state = _read_contract_state(event)
    request_digest = _capability_digest(request)
    runner_token = secrets.token_urlsafe(24)
    state["mutation"] = {
        "status": "running",
        "request_digest": request_digest,
        "runner_token_digest": hashlib.sha256(runner_token.encode()).hexdigest(),
        "runner_claimed_at": 0,
        "started_at": int(time.time()),
        "last_exit_code": None,
    }
    _save_contract_state(event, state)
    return _mutation_runner_command(
        event, request, request_digest, runner_token
    ), ""


def _service_runner_command(
    event: dict[str, Any],
    request: dict[str, Any],
    service_id: str,
    runner_token: str = "",
) -> str:
    arguments = [
        *_stateful_runner_prefix(
            "run-service-start" if request["action"] == "start" else "run-service-stop"
        ),
        str(_contract_path(event).resolve()),
        service_id,
    ]
    if request["action"] == "start":
        arguments.extend(
            [
                runner_token,
                str(Path(str(event.get("cwd", ""))).resolve()),
                _encoded_request(request),
            ]
        )
    return _runner_shell_command(arguments)


def _request_service_stop(event: dict[str, Any]) -> bool:
    state = _read_contract_state(event)
    service = state.get("service")
    if not isinstance(service, dict) or service.get("status") not in {
        "starting",
        "launching",
        "running",
        "stopping",
    }:
        return False
    service["status"] = "stopping"
    service["stop_requested"] = True
    state["service"] = service
    _save_contract_state(event, state)
    return True


def _prepare_service(event: dict[str, Any], raw: str) -> tuple[str, str]:
    request, error = _validate_service_request(raw)
    if error:
        return "", error
    assert request is not None
    state = _read_contract_state(event)
    if state.get("status") != "approved":
        return "", "Approve the staged Click execution contract before managing a service."
    service = state.get("service")
    if not isinstance(service, dict):
        service = _fresh_service_state()
    if request["action"] == "stop":
        if service.get("status") not in {
            "starting",
            "launching",
            "running",
            "stopping",
        }:
            return "echo Click managed service already stopped", ""
        service["status"] = "stopping"
        service["stop_requested"] = True
        state["service"] = service
        _save_contract_state(event, state)
        return _service_runner_command(event, request, str(service["service_id"])), ""

    if service.get("status") in {"starting", "launching", "running", "stopping"}:
        started_at = int(service.get("started_at", 0))
        if not (
            service.get("status") == "starting"
            and started_at
            and time.time() - started_at > SERVICE_START_TIMEOUT_SECONDS * 2
        ):
            return "", "One Click-managed local service is already active. Stop it first."
    mutation_error = _mark_contract_mutated(event)
    if mutation_error:
        return "", mutation_error
    state = _read_contract_state(event)
    service_id = secrets.token_urlsafe(24)
    runner_token = secrets.token_urlsafe(24)
    cwd_raw = str(Path(str(event.get("cwd", ""))).resolve())
    request_digest = _capability_digest({"request": request, "cwd": cwd_raw})
    state["service"] = {
        "status": "starting",
        "service_id": service_id,
        "request_digest": request_digest,
        "runner_token_digest": hashlib.sha256(runner_token.encode()).hexdigest(),
        "runner_claimed_at": 0,
        "supervisor_claimed_at": 0,
        "stop_requested": False,
        "supervisor_pid": 0,
        "child_pid": 0,
        "started_at": int(time.time()),
        "last_exit_code": None,
    }
    _save_contract_state(event, state)
    return _service_runner_command(event, request, service_id, runner_token), ""


def _verification_runner_command(
    event: dict[str, Any], batch: dict[str, Any], batch_digest: str, runner_token: str
) -> str:
    encoded = base64.urlsafe_b64encode(
        json.dumps(batch, ensure_ascii=False, separators=(",", ":")).encode()
    ).decode()
    arguments = [
        *_stateful_runner_prefix("run-verification"),
        str(_contract_path(event).resolve()),
        batch_digest,
        runner_token,
        encoded,
    ]
    return _runner_shell_command(arguments)


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
        external = state.get("external_evidence")
        browser_running = (
            external.get("browser_running")
            if isinstance(external, dict)
            else None
        )
        if isinstance(browser_running, dict) and browser_running:
            return "", "Wait for the running Browser interaction before finalizing evidence."
        if (
            not isinstance(external, dict)
            or external.get("browser_source_key") != source_key
            or external.get("browser_status") != "observed"
            or source.get("status") != "observed"
            or int(source.get("verified_revision", -1)) != revision
        ):
            return (
                "",
                f"Browser evidence `{evidence_id}` can complete only after a successful "
                "current-revision Browser call in its metered session.",
            )
        external["browser_status"] = "passed"
        state["external_evidence"] = external
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
    state = _read_contract_state(event)
    if state.get("status") != "approved":
        return "", "Approve the staged Click execution contract before verification.", ""
    mutation = state.get("mutation")
    if _mutation_is_running(mutation):
        return (
            "",
            "Wait for the structured Click mutation to finish before verification.",
            "",
        )
    if isinstance(mutation, dict) and mutation.get("status") == "running":
        state["mutation"] = _fresh_mutation_state()
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return (
            "",
            "Click verification state is unavailable; stage and approve again.",
            "",
        )
    prior_verification_changed_workspace = (
        verification.get("workspace_changed") is True
    )
    scale = str(verification.get("scale", ""))
    if not click_verification_policy.is_profile(scale):
        return (
            "",
            "Approved Click verification scale is invalid; stage and approve again.",
            "",
        )
    verification_advisories: list[str] = []
    sources = _evidence_sources(state)
    if sources is None:
        return (
            "",
            "This active contract predates evidence-id completion tracking. Cancel it, "
            "stage the proposal again, and obtain fresh approval.",
            "",
        )
    if not sources:
        return (
            "",
            "Click evidence state is unavailable or malformed; cancel and restage.",
            "",
        )

    observations = state.get("observations")
    if isinstance(observations, dict):
        entries = observations.get("entries")
        if isinstance(entries, dict):
            for entry in entries.values():
                if _observation_is_running(entry):
                    return (
                        "",
                        "Wait for the approved read or search to finish before starting "
                        "the final verification batch.",
                        "",
                    )

    batch, units, error = _validate_verification_batch(raw, scale, sources)
    if error:
        return "", error, ""
    assert batch is not None
    status = str(verification.get("status", "ready"))
    if status == "running":
        claimed_at = verification.get("runner_claimed_at", 0)
        if not isinstance(claimed_at, int) or isinstance(claimed_at, bool):
            return "", "Click verification runner claim state is malformed.", ""
        if claimed_at > 0:
            return "", "The approved Click verification batch is already running.", ""
        started_at = int(verification.get("started_at", 0))
        if started_at and time.time() - started_at <= VERIFY_RUNNING_TTL_SECONDS:
            return "", "The approved Click verification batch is already running.", ""
        status = "failed"
        verification["status"] = status
        verification["last_exit_code"] = 124
        for source_key in verification.get("running_evidence_keys", []):
            source = sources.get(source_key)
            if isinstance(source, dict) and source.get("status") == "running":
                source["status"] = "ready"
                source["last_exit_code"] = None
        verification["running_evidence_keys"] = []
        verification["running_environment_digests"] = {}
        verification["running_environment_binding"] = []
        verification["running_environment_binding_digest"] = ""
        verification["running_executable_digests"] = {}
        verification["runner_claimed_at"] = 0

    revision = int(verification.get("mutation_revision", 0))
    argv_keys = _evidence_keys_for_kind(sources, "argv")
    grouped_checks, grouping_error = _verification_groups(batch)
    if grouping_error:
        return "", grouping_error, ""
    requested_keys = set(grouped_checks)
    unassigned_keys = requested_keys - argv_keys
    if unassigned_keys:
        return (
            "",
            "A verification batch may contain only declared argv evidence; "
            f"{len(unassigned_keys)} source(s) were unassigned or non-argv.",
            "",
        )

    group_digests: dict[str, str] = {}
    group_units: dict[str, int] = {}
    for source_key, checks in grouped_checks.items():
        group_digest = _verification_group_digest(checks)
        group_digests[source_key] = group_digest
        group_units[source_key] = _verification_group_units(checks)
        source = sources[source_key]
        reserved_digest = str(source.get("reserved_check_digest", ""))
        if reserved_digest and reserved_digest != group_digest:
            return (
                "",
                "An argv evidence source is already reserved to a different exact "
                "check set for this contract. Reuse that set or stage a new contract.",
                "",
            )
        locked_digest = str(source.get("locked_check_digest", ""))
        if locked_digest and locked_digest != group_digest:
            return (
                "",
                "A previously successful argv evidence source is locked to its exact "
                "check set. Re-run that set after the relevant mutation.",
                "",
            )
        last_digest = str(source.get("last_check_digest", ""))
        if last_digest and last_digest != group_digest:
            return (
                "",
                "An argv evidence source changed its check set without an intervening "
                "mutation. Fix the implementation or reuse the original check set.",
                "",
            )

    for source_key, requested_units in group_units.items():
        source = sources[source_key]
        # Retain the derived unit field for state-schema compatibility only.
        # Exact check-group identity comes from reserved_check_digest.
        source["reserved_units"] = requested_units
        if not str(source.get("reserved_check_digest", "")):
            source["reserved_check_digest"] = group_digests[source_key]

    current_requested = {
        source_key
        for source_key in requested_keys
        if _evidence_is_current(sources.get(source_key), revision)
    }
    dependency_candidates = {
        source_key
        for source_key in requested_keys
        if isinstance(sources.get(source_key), dict)
        and sources[source_key].get("status") == "stale"
        and isinstance(sources[source_key].get("verified_revision"), int)
        and not isinstance(sources[source_key].get("verified_revision"), bool)
        and 0 <= int(sources[source_key].get("verified_revision", -1)) < revision
        and sources[source_key].get("verified_dependency_provider")
        in click_dependency_cache.PROVIDER_NAMES
    }
    reused_keys: set[str] = set()
    dependency_reused_keys: set[str] = set()
    if current_requested or dependency_candidates:
        workspace = Path(str(event.get("cwd", ""))).resolve()
        snapshot = _git_workspace_snapshot(workspace)
        if snapshot is None:
            for source_key in current_requested:
                source = sources[source_key]
                source["status"] = "ready"
                source["verified_revision"] = -1
        else:
            contract_digest = str(state.get("contract_digest", ""))
            git_root = os.path.normcase(str(snapshot.get("root", "")))
            tree_digest = str(snapshot.get("digest", ""))
            mutation_boundary = verification.get("mutation_boundary")
            if dependency_candidates and not (
                isinstance(mutation_boundary, dict)
                and mutation_boundary.get("status") == "recorded"
                and mutation_boundary.get("lineage_valid") is True
                and mutation_boundary.get("revision") == revision
                and mutation_boundary.get("after_root") == git_root
                and mutation_boundary.get("after_digest") == tree_digest
            ):
                # A missing PostToolUse receipt or any later workspace drift is
                # outside the observable approved mutation boundary. Rerun.
                dependency_candidates = set()
            tree_changed = any(
                isinstance(sources[source_key].get("verified_root"), str)
                and bool(sources[source_key].get("verified_root"))
                and (
                    sources[source_key].get("verified_root") != git_root
                    or sources[source_key].get("verified_tree_digest") != tree_digest
                )
                for source_key in current_requested
            )
            if tree_changed:
                revision += 1
                verification["mutation_revision"] = revision
                verification["status"] = "ready"
                verification["verified_revision"] = -1
                verification["failed_revision"] = -1
                verification["workspace_changed"] = True
                for source in sources.values():
                    if not isinstance(source, dict):
                        continue
                    if source.get("status") in {"passed", "observed"}:
                        source["status"] = "stale"
                    else:
                        source["status"] = "ready"
                    source["verified_revision"] = -1
                    source["unchanged_failure_retries"] = 0
                    source["last_exit_code"] = None
                external = state.get("external_evidence")
                browser_required = bool(
                    isinstance(external, dict)
                    and external.get("browser_required") is True
                )
                browser_source_key = (
                    str(external.get("browser_source_key", ""))
                    if isinstance(external, dict)
                    else ""
                )
                state["external_evidence"] = _fresh_external_evidence_state(
                    required=browser_required,
                    source_key=browser_source_key,
                )
                state["observations"] = _fresh_observation_state()
            else:
                for source_key in current_requested:
                    source = sources[source_key]
                    environment_digest = _verification_environment_digest(
                        grouped_checks[source_key], cwd=workspace
                    )
                    if _verification_receipt_matches(
                        source,
                        contract_digest=contract_digest,
                        revision=revision,
                        group_digest=group_digests[source_key],
                        git_root=git_root,
                        tree_digest=tree_digest,
                        environment_digest=environment_digest,
                    ):
                        reused_keys.add(source_key)
                    else:
                        source["status"] = "ready"
                        source["verified_revision"] = -1
                        source["last_exit_code"] = None
                candidate_checks = {
                    source_key: grouped_checks[source_key]
                    for source_key in dependency_candidates
                }
                dependency_receipts = (
                    click_dependency_cache.receipts_for_groups(
                        workspace,
                        candidate_checks,
                        declarations=_dependency_declarations(
                            sources, dependency_candidates
                        ),
                        git_capture=_git_capture,
                    )
                    if candidate_checks
                    else {}
                )
                for source_key in dependency_candidates:
                    source = sources[source_key]
                    receipt = dependency_receipts.get(source_key)
                    environment_digest = _verification_environment_digest(
                        grouped_checks[source_key], cwd=workspace
                    )
                    if _dependency_receipt_matches(
                        source,
                        receipt,
                        contract_digest=contract_digest,
                        revision=revision,
                        group_digest=group_digests[source_key],
                        git_root=git_root,
                        environment_digest=environment_digest,
                    ):
                        assert isinstance(receipt, dict)
                        _promote_dependency_receipt(
                            source,
                            receipt,
                            revision=revision,
                            tree_digest=tree_digest,
                        )
                        reused_keys.add(source_key)
                        dependency_reused_keys.add(source_key)

    unresolved_keys = {
        key for key in argv_keys if not _evidence_is_current(sources.get(key), revision)
    }
    pending_keys = requested_keys - reused_keys
    repeated_keys = pending_keys - unresolved_keys
    if repeated_keys:
        return (
            "",
            "A verification batch may contain only unresolved declared argv evidence or "
            "an exact reusable success receipt.",
            "",
        )

    if not pending_keys:
        all_argv_current = bool(argv_keys) and all(
            _evidence_is_current(sources.get(source_key), revision)
            for source_key in argv_keys
        )
        verification["status"] = "passed" if all_argv_current else "ready"
        verification["verified_revision"] = revision if all_argv_current else -1
        verification["failed_revision"] = -1
        verification["last_exit_code"] = 0
        verification["last_units"] = 0
        state["verification"] = verification
        _save_contract_state(event, state)
        exact_reused = len(reused_keys - dependency_reused_keys)
        dependency_reused = len(dependency_reused_keys)
        if exact_reused and dependency_reused:
            reuse_message = (
                f"Click reused {exact_reused} current unchanged-tree and "
                f"{dependency_reused} dependency-safe cross-revision verification "
                "receipt(s)"
            )
        elif dependency_reused:
            reuse_message = (
                f"Click reused {dependency_reused} dependency-safe cross-revision "
                "verification receipt(s)"
            )
        else:
            reuse_message = (
                f"Click reused {exact_reused} current unchanged-tree verification "
                "receipt(s)"
            )
        return (
            f"echo {reuse_message}",
            "",
            "",
        )

    batch = {
        "version": VERIFICATION_PROTOCOL_VERSION,
        "checks": [
            check
            for check in batch["checks"]
            if _evidence_key(str(check["evidence_id"])) in pending_keys
        ],
    }
    units = sum(group_units[source_key] for source_key in pending_keys)
    requested_keys = pending_keys

    if prior_verification_changed_workspace:
        return (
            "",
            "The previous verification changed protected repository content. Use an "
            "approved code mutation to repair or reconcile the workspace before running "
            "verification again.",
            "",
        )

    retried_failed_sources = 0
    for source_key in requested_keys:
        source = sources[source_key]
        source_status = str(source.get("status", "ready"))
        if source_status == "failed":
            retries = int(source.get("unchanged_failure_retries", 0))
            if retries >= 1:
                retried_failed_sources += 1
            source["unchanged_failure_retries"] = retries + 1

    if retried_failed_sources:
        verification_advisories.append(
            "Click advisory: "
            f"{retried_failed_sources} argv evidence source(s) already failed twice "
            "without a subsequent code mutation. This fresh, separately authorized "
            "retry is allowed, but fix the in-scope cause before repeating it when "
            "practical."
        )

    canonical = json.dumps(batch, sort_keys=True, separators=(",", ":"))
    batch_digest = hashlib.sha256(canonical.encode()).hexdigest()
    workspace = Path(str(event.get("cwd", ""))).resolve()
    prepared_environment = _verification_environment(cwd=workspace)
    runner_token = secrets.token_urlsafe(24)
    running_environment_binding = _verification_environment_binding(
        prepared_environment, runner_token
    )
    running_environment_binding_digest = (
        _verification_environment_binding_digest(
            running_environment_binding, runner_token
        )
    )
    running_environment_digests: dict[str, str] = {}
    running_executable_digests: dict[str, str] = {}
    for source_key in requested_keys:
        executable_records = _verification_executable_records(
            grouped_checks[source_key],
            cwd=workspace,
            environment=prepared_environment,
        )
        if executable_records is None:
            return (
                "",
                "Click could not resolve and fingerprint every verification "
                "executable before issuing the runner.",
                "",
            )
        running_environment_digests[source_key] = (
            _verification_environment_digest_from_records(
                executable_records,
                cwd=workspace,
                environment=prepared_environment,
            )
        )
        running_executable_digests[source_key] = _capability_digest(
            {
                "executables": _verification_executable_payload(
                    executable_records
                )
            }
        )
    for source_key in requested_keys:
        group_digest = group_digests[source_key]
        source = sources[source_key]
        source["status"] = "running"
        source["last_check_digest"] = group_digest

    verification.update(
        {
            "status": "running",
            "attempts": int(verification.get("attempts", 0)) + 1,
            "last_units": units,
            "last_batch_digest": batch_digest,
            "runner_token_digest": hashlib.sha256(runner_token.encode()).hexdigest(),
            "runner_claimed_at": 0,
            "running_evidence_keys": sorted(requested_keys),
            "running_environment_digests": running_environment_digests,
            "running_environment_binding": running_environment_binding,
            "running_environment_binding_digest": (
                running_environment_binding_digest
            ),
            "running_executable_digests": running_executable_digests,
            "started_at": int(time.time()),
        }
    )
    state["verification"] = verification
    _save_contract_state(event, state)
    return (
        _verification_runner_command(event, batch, batch_digest, runner_token),
        "",
        "\n".join(verification_advisories),
    )


def _is_read_only_sed(tokens: list[str]) -> bool:
    index = 1
    quiet = False
    script = ""
    while index < len(tokens) and not script:
        token = tokens[index]
        if token in {"-n", "--quiet", "--silent"}:
            quiet = True
        elif token in {"-e", "--expression"}:
            index += 1
            if index >= len(tokens):
                return False
            script = tokens[index]
        elif token.startswith("-e") and len(token) > 2:
            script = token[2:]
        elif token.startswith("-"):
            return False
        else:
            script = token
        index += 1

    if not quiet or not script or not SED_READ_SCRIPT.fullmatch(script):
        return False
    if index < len(tokens) and tokens[index] == "--":
        index += 1
    return index < len(tokens) and all(not token.startswith("-") for token in tokens[index:])


def _get_content_paths(tokens: list[str]) -> list[str] | None:
    if not tokens or Path(tokens[0]).name.lower() != "get-content":
        return None
    paths: list[str] = []
    index = 1
    while index < len(tokens):
        argument = tokens[index]
        lowered = argument.lower()
        if lowered == "-raw":
            index += 1
            continue
        if lowered in {"-path", "-literalpath"}:
            if index + 1 >= len(tokens):
                return None
            paths.append(tokens[index + 1])
            index += 2
            continue
        if argument.startswith("-"):
            return None
        paths.append(argument)
        index += 1
    return paths or None


def _structured_ssh_parts(tokens: list[str]) -> tuple[str, list[str]] | None:
    if len(tokens) < 4 or Path(tokens[0]).name.lower() not in {"ssh", "ssh.exe"}:
        return None
    target = tokens[1]
    remote_argv = tokens[2:]
    if target.startswith("-") or not SSH_TARGET.fullmatch(target):
        return None
    if remote_argv[0] != "git":
        return None
    parsed = _parse_read_only_git_tokens(remote_argv)
    if parsed is None or parsed[1] not in SSH_READ_ONLY_GIT_SUBCOMMANDS:
        return None
    if parsed[1] == "rev-parse":
        positional = [
            argument
            for argument in parsed[2]
            if argument != "--" and not argument.startswith("-")
        ]
        if positional != ["HEAD"]:
            return None
    return target, remote_argv


def _is_path_qualified_executable(value: str) -> bool:
    return "/" in value or "\\" in value or bool(re.match(r"^[A-Za-z]:", value))


def _is_local_read_only_tokens(tokens: list[str]) -> bool:
    if not tokens:
        return False
    if ENVIRONMENT_ASSIGNMENT.match(tokens[0]):
        return False
    if _is_path_qualified_executable(tokens[0]):
        return False

    executable = tokens[0].lower()
    if executable in {"git", "git.exe"}:
        return _parse_read_only_git_tokens(tokens) is not None
    if executable not in READ_ONLY_COMMANDS:
        return False
    if executable == "get-content":
        return _get_content_paths(tokens) is not None
    if executable == "sed":
        return _is_read_only_sed(tokens)
    if executable == "file" and any(
        token in {"-C", "--compile"} for token in tokens[1:]
    ):
        return False
    if executable == "find" and any(
        token
        in {
            "-delete",
            "-exec",
            "-execdir",
            "-fls",
            "-fprint",
            "-fprint0",
            "-fprintf",
            "-ok",
            "-okdir",
        }
        for token in tokens[1:]
    ):
        return False
    if executable == "rg" and any(
        token == "--pre" or token.startswith("--pre=") for token in tokens[1:]
    ):
        return False
    if executable in {"diff", "sort", "tree"} and any(
        token == "-o" or token.startswith("-o") or token.startswith("--output")
        for token in tokens[1:]
    ):
        return False
    if executable == "sort" and any(
        token.startswith("--compress-program") for token in tokens[1:]
    ):
        return False
    return True


def _is_read_only_tokens(tokens: list[str]) -> bool:
    if not tokens:
        return False
    if _is_path_qualified_executable(tokens[0]):
        return False
    if tokens[0].lower() in {"ssh", "ssh.exe"}:
        return _structured_ssh_parts(tokens) is not None
    return _is_local_read_only_tokens(tokens)


def _is_read_only_bash(command: str) -> bool:
    request, _, _ = _inspection_request_from_bash(command)
    return request is not None


def _direct_command_tokens(
    command: str, *, windows: bool | None = None
) -> tuple[list[str] | None, str]:
    windows_tokens = os.name == "nt" if windows is None else windows
    try:
        lexer = shlex.shlex(
            command,
            posix=not windows_tokens,
            punctuation_chars="".join(sorted(SHELL_CONTROL_PUNCTUATION)),
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None, ""
    if not windows_tokens:
        return tokens, ""

    normalized_tokens: list[str] = []
    for token in tokens:
        if (
            len(token) >= 2
            and token[0] == token[-1]
            and token[0] in {'"', "'"}
        ):
            token = token[1:-1]
        if '"' in token or "'" in token:
            return (
                None,
                "Click could not safely normalize this Windows command line. "
                "Use `click-gate inspect` with explicit argv JSON.",
            )
        normalized_tokens.append(token)
    return normalized_tokens, ""


def _inspection_request_from_bash(
    command: str, *, windows: bool | None = None
) -> tuple[dict[str, Any] | None, bool, str]:
    if not command.strip() or "\n" in command or "\r" in command or "`" in command:
        return None, False, ""
    tokens, token_error = _direct_command_tokens(command, windows=windows)
    if token_error:
        return None, False, token_error
    if tokens is None:
        return None, False, ""

    commands: list[list[str]] = [[]]
    for token in tokens:
        if token == "&&":
            if not commands[-1]:
                return None, False, ""
            commands.append([])
            continue
        if token == "|":
            return (
                None,
                False,
                "Click structured inspection does not execute pipelines. Pass direct argv "
                "commands or narrow the read instead.",
            )
        if token and set(token).issubset(SHELL_CONTROL_PUNCTUATION):
            return None, False, ""
        commands[-1].append(token)
    if not commands[-1]:
        return None, False, ""
    raw = json.dumps(
        {"version": CAPABILITY_PROTOCOL_VERSION, "commands": commands},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    request, broad, error = _validate_inspection_request(raw)
    if error and "not a supported read-only argv operation" in error:
        return None, False, ""
    return request, broad, error


def _is_plan_tool(tool_name: str) -> bool:
    normalized = tool_name.lower().replace("::", "__").replace(".", "__")
    return normalized.split("__")[-1] == "update_plan"


def _browser_input_error(tool_input: Any) -> str:
    if not isinstance(tool_input, dict):
        return "Browser evidence requires an object tool input."
    return ""


def _browser_running_expires_at(tool_input: Any, started_at: float) -> float:
    declared_seconds = (
        click_browser_advisory.longest_declared_runtime_ms(tool_input) / 1000.0
    )
    return started_at + max(BROWSER_RUNNING_TTL_SECONDS, declared_seconds + 10.0)


def _browser_running_entry_is_active(entry: Any, now: float) -> bool:
    if isinstance(entry, (int, float)) and not isinstance(entry, bool):
        return now - float(entry) <= BROWSER_RUNNING_TTL_SECONDS
    if not isinstance(entry, dict):
        return False
    expires_at = entry.get("expires_at")
    if isinstance(expires_at, (int, float)) and not isinstance(expires_at, bool):
        return now <= float(expires_at)
    started_at = entry.get("started_at")
    return bool(
        isinstance(started_at, (int, float))
        and not isinstance(started_at, bool)
        and now - float(started_at) <= BROWSER_RUNNING_TTL_SECONDS
    )


def _browser_attempt_digest(tool_input: Any) -> str:
    if isinstance(tool_input, dict) and isinstance(tool_input.get("code"), str):
        code = str(tool_input["code"]).replace("\r\n", "\n").strip()
        return _capability_digest({"code": code})
    if isinstance(tool_input, dict):
        semantic = {
            key: value
            for key, value in tool_input.items()
            if key not in {"_meta", "annotations", "timeout", "timeout_ms"}
        }
        return _capability_digest({"tool_input": semantic})
    return _capability_digest({"tool_input": tool_input})


def _tool_response_failed(response: Any) -> bool:
    if not isinstance(response, dict):
        return True
    if response.get("isError") is True or response.get("is_error") is True:
        return True
    if "status" in response:
        status = str(response.get("status", "")).lower()
        return status not in {
            "complete",
            "completed",
            "ok",
            "pass",
            "passed",
            "success",
            "succeeded",
        }
    # MCP responses may omit a status while still returning structured content.
    # Empty containers, empty strings, and null acknowledgements prove nothing.
    def meaningful(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (bytes, bytearray)):
            return bool(value)
        if isinstance(value, dict):
            metadata_keys = {
                "_meta",
                "annotations",
                "mimeType",
                "mime_type",
                "role",
                "type",
            }
            return any(
                meaningful(item)
                for key, item in value.items()
                if key not in metadata_keys
            )
        if isinstance(value, (list, tuple, set)):
            return any(meaningful(item) for item in value)
        return True

    return not any(
        meaningful(response.get(key)) for key in {"content", "output", "result"}
    )


def _prepare_browser_evidence(event: dict[str, Any]) -> tuple[bool, str, str]:
    state = _read_contract_state(event)
    if state.get("status") not in {"staged", "approved"}:
        return False, "", ""
    if state.get("status") != "approved":
        return (
            True,
            "Approve the staged Click contract before collecting browser evidence.",
            "",
        )
    if _contract_is_completed(state):
        if _read_state(event).get("status") != "passed":
            return False, "", ""
        return (
            True,
            "The approved Click contract is complete. Reuse its evidence instead of "
            "starting a shadow browser verification session.",
            "",
        )
    external = state.get("external_evidence")
    if not isinstance(external, dict) or external.get("browser_required") is not True:
        return (
            True,
            "Browser work has no referenced verification evidence source with kind "
            "`browser` in this contract. Use the cheaper assigned source instead of "
            "adding shadow verification.",
            "",
        )
    sources = _evidence_sources(state)
    if sources is None:
        return (
            True,
            "This active contract predates evidence-id completion tracking. Cancel it, "
            "stage the proposal again, and obtain fresh approval.",
            "",
        )
    source_key = str(external.get("browser_source_key", ""))
    source = sources.get(source_key) if sources else None
    if not isinstance(source, dict) or source.get("kind") != "browser":
        return True, "Click Browser evidence state is unavailable or malformed.", ""
    mutation = state.get("mutation")
    if _mutation_is_running(mutation):
        return (
            True,
            "Wait for the structured mutation to finish before browser evidence.",
            "",
        )
    verification = state.get("verification")
    if isinstance(verification, dict) and verification.get("status") == "running":
        return (
            True,
            "Wait for the final argv verification batch before browser evidence.",
            "",
        )
    revision = (
        int(verification.get("mutation_revision", 0))
        if isinstance(verification, dict)
        else 0
    )
    if _evidence_is_current(source, revision):
        return (
            True,
            "The assigned Browser evidence already completed for the current revision. "
            "Reuse it instead of replaying the session.",
            "",
        )
    running = external.get("browser_running")
    if isinstance(running, dict) and running:
        already_observed = bool(
            external.get("browser_status") == "observed"
            or source.get("status") == "observed"
        )
        now = time.time()
        if any(
            _browser_running_entry_is_active(running_entry, now)
            for running_entry in running.values()
        ):
            return (
                True,
                "One browser evidence call is already running; keep the session serial.",
                "",
            )
        attempts = external.get("browser_attempts")
        if not isinstance(attempts, dict):
            attempts = {}
        for running_entry in running.values():
            if not isinstance(running_entry, dict):
                continue
            attempt_digest = str(running_entry.get("attempt_digest", ""))
            attempt = attempts.get(attempt_digest)
            if isinstance(attempt, dict) and attempt.get("status") == "running":
                attempt["status"] = "failed"
                attempt["failed_attempts"] = int(
                    attempt.get("failed_attempts", 0)
                ) + 1
        external["browser_running"] = {}
        external["browser_attempts"] = attempts
        external["browser_status"] = "observed" if already_observed else "failed"
        external["last_browser_error"] = "post-tool-timeout"
        if not already_observed:
            source["status"] = "failed"
            source["verified_revision"] = -1
            source["last_exit_code"] = 124
        state["external_evidence"] = external
        _save_contract_state(event, state)
    input_error = _browser_input_error(event.get("tool_input"))
    if input_error:
        return True, input_error, ""
    advisories = list(
        click_browser_advisory.input_advisories(event.get("tool_input"))
    )
    tool_use_id = str(event.get("tool_use_id", ""))
    if not tool_use_id:
        return (
            True,
            "Browser evidence requires a stable tool_use_id for PostToolUse accounting.",
            "",
        )
    attempt_digest = _browser_attempt_digest(event.get("tool_input"))
    attempts = external.get("browser_attempts")
    if not isinstance(attempts, dict):
        attempts = {}
    prior_attempt = attempts.get(attempt_digest)
    repeat_advisory = click_browser_advisory.repeat_advisory(prior_attempt)
    if repeat_advisory:
        advisories.append(repeat_advisory)
    unchanged_retries = 0
    if isinstance(prior_attempt, dict):
        prior_status = str(prior_attempt.get("status", ""))
        unchanged_retries = int(prior_attempt.get("unchanged_retries", 0))
        if prior_status in {"failed", "incomplete"}:
            unchanged_retries += 1
    previous_successes = (
        int(prior_attempt.get("successful_attempts", 0))
        if isinstance(prior_attempt, dict)
        else 0
    )
    if (
        isinstance(prior_attempt, dict)
        and prior_attempt.get("status") == "success"
        and previous_successes == 0
    ):
        previous_successes = 1
    previous_failures = (
        int(prior_attempt.get("failed_attempts", 0))
        if isinstance(prior_attempt, dict)
        else 0
    )
    if isinstance(prior_attempt, dict):
        attempts.pop(attempt_digest, None)
    compacted = False
    while len(attempts) >= MAX_BROWSER_UNIQUE_INPUTS:
        attempts.pop(next(iter(attempts)))
        compacted = True
    if compacted:
        advisories.append(
            "Click advisory: older Browser attempt guidance was compacted to keep "
            "receipt state bounded. This call remains tracked, and the current source "
            "and revision receipt are unchanged."
        )
    already_observed = bool(
        external.get("browser_status") == "observed"
        or source.get("status") == "observed"
    )
    attempts[attempt_digest] = {
        "status": "running",
        "attempts": int(prior_attempt.get("attempts", 0)) + 1
        if isinstance(prior_attempt, dict)
        else 1,
        "unchanged_retries": unchanged_retries,
        "successful_attempts": previous_successes,
        "failed_attempts": previous_failures,
    }
    calls = int(external.get("browser_calls", 0))
    external["browser_calls"] = calls + 1
    external["browser_status"] = "observed" if already_observed else "running"
    started_at = time.time()
    external["browser_running"] = {
        tool_use_id: {
            "started_at": started_at,
            "expires_at": _browser_running_expires_at(
                event.get("tool_input"), started_at
            ),
            "attempt_digest": attempt_digest,
        }
    }
    external["browser_attempts"] = attempts
    external["last_browser_error"] = ""
    if not already_observed:
        source["status"] = "running"
    state["external_evidence"] = external
    _save_contract_state(event, state)
    return True, "", "\n".join(advisories)


def _record_mutation_boundary(event: dict[str, Any]) -> None:
    state = _read_contract_state(event)
    if state.get("status") != "approved":
        return
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return
    boundary = verification.get("mutation_boundary")
    if (
        not isinstance(boundary, dict)
        or boundary.get("status") != "running"
        or boundary.get("tool_use_id") != str(event.get("tool_use_id", ""))
        or boundary.get("revision") != verification.get("mutation_revision")
    ):
        return
    snapshot = _git_workspace_snapshot(
        Path(str(event.get("cwd", ""))).resolve()
    )
    if snapshot is None:
        boundary["status"] = "invalid"
        boundary["lineage_valid"] = False
    else:
        boundary["status"] = "recorded"
        boundary["after_root"] = os.path.normcase(str(snapshot.get("root", "")))
        boundary["after_digest"] = str(snapshot.get("digest", ""))
    verification["mutation_boundary"] = boundary
    state["verification"] = verification
    _save_contract_state(event, state)


def _handle_post_tool(event: dict[str, Any]) -> None:
    if str(event.get("tool_name", "")) not in BROWSER_TOOL_NAMES:
        _record_mutation_boundary(event)
        return
    state = _read_contract_state(event)
    if state.get("status") != "approved":
        return
    external = state.get("external_evidence")
    if not isinstance(external, dict):
        return
    running = external.get("browser_running")
    tool_use_id = str(event.get("tool_use_id", ""))
    if not isinstance(running, dict) or tool_use_id not in running:
        return
    running_entry = running.pop(tool_use_id)
    if isinstance(running_entry, dict):
        started_at = float(running_entry.get("started_at", 0.0))
        attempt_digest = str(running_entry.get("attempt_digest", ""))
    else:
        started_at = float(running_entry)
        attempt_digest = _browser_attempt_digest(event.get("tool_input"))
    duration = max(0.0, time.time() - started_at)
    total = float(external.get("browser_seconds", 0.0)) + duration
    external["browser_seconds"] = round(total, 3)
    external["browser_running"] = running
    sources = _evidence_sources(state)
    source_key = str(external.get("browser_source_key", ""))
    source = sources.get(source_key) if sources else None
    verification = state.get("verification")
    revision = (
        int(verification.get("mutation_revision", 0))
        if isinstance(verification, dict)
        else 0
    )
    attempts = external.get("browser_attempts")
    if not isinstance(attempts, dict):
        attempts = {}
    attempt = attempts.get(attempt_digest)
    if not isinstance(attempt, dict):
        attempt = {
            "attempts": 1,
            "unchanged_retries": 0,
            "successful_attempts": 0,
            "failed_attempts": 0,
        }
        attempts[attempt_digest] = attempt
    if _tool_response_failed(event.get("tool_response")):
        attempt["status"] = "failed"
        attempt["failed_attempts"] = int(attempt.get("failed_attempts", 0)) + 1
        already_observed = bool(
            external.get("browser_status") == "observed"
            or isinstance(source, dict)
            and source.get("status") == "observed"
        )
        external["browser_status"] = "observed" if already_observed else "failed"
        external["last_browser_error"] = "tool-error"
        if isinstance(source, dict) and not already_observed:
            source["status"] = "failed"
            source["verified_revision"] = -1
            source["last_exit_code"] = 1
    else:
        attempt["status"] = "success"
        attempt["successful_attempts"] = int(
            attempt.get("successful_attempts", 0)
        ) + 1
        external["browser_status"] = "observed"
        external["last_browser_error"] = ""
        if isinstance(source, dict):
            source["status"] = "observed"
            source["verified_revision"] = revision
            source["last_exit_code"] = 0
    external["browser_attempts"] = attempts
    state["external_evidence"] = external
    _save_contract_state(event, state)


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
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return False
    if verification.get("status") != "running":
        return False
    if verification.get("last_batch_digest") != batch_digest:
        return False
    token_digest = hashlib.sha256(runner_token.encode()).hexdigest()
    if not secrets.compare_digest(
        str(verification.get("runner_token_digest", "")), token_digest
    ):
        return False
    claimed_at = verification.get("runner_claimed_at", 0)
    if (
        not isinstance(claimed_at, int)
        or isinstance(claimed_at, bool)
        or claimed_at <= 0
    ):
        return False

    revision = int(verification.get("mutation_revision", 0))
    verification["runner_token_digest"] = ""
    verification["runner_claimed_at"] = 0
    verification["started_at"] = 0
    verification["last_exit_code"] = exit_code
    verification["workspace_changed"] = workspace_changed
    sources = _evidence_sources(state)
    if sources is None or not sources:
        return False
    running_keys = {
        key
        for key in verification.get("running_evidence_keys", [])
        if isinstance(key, str)
    }
    prepared_environment_digests = verification.get(
        "running_environment_digests"
    )
    prepared_executable_digests = verification.get(
        "running_executable_digests"
    )
    for prepared in (
        prepared_environment_digests,
        prepared_executable_digests,
    ):
        if (
            not isinstance(prepared, dict)
            or set(prepared) != running_keys
            or any(
                not isinstance(value, str)
                or not re.fullmatch(r"[0-9a-f]{64}", value)
                for value in prepared.values()
            )
        ):
            return False
    running_environment_binding = verification.get("running_environment_binding")
    if not _verification_environment_binding_is_authentic(
        running_environment_binding,
        verification.get("running_environment_binding_digest"),
        runner_token,
    ):
        return False
    _, _, binding_error = _verification_environment_from_binding(
        running_environment_binding,
        runner_token,
        _verification_environment(cwd=Path.cwd()),
    )
    if binding_error:
        return False
    if (
        environment_digests is not None
        and environment_digests != prepared_environment_digests
    ):
        return False
    environment_digests = prepared_environment_digests
    checks = batch.get("checks")
    if not isinstance(checks, list):
        return False
    positions: dict[str, list[int]] = {}
    for index, check in enumerate(checks):
        if not isinstance(check, dict) or not isinstance(check.get("evidence_id"), str):
            return False
        source_key = _evidence_key(str(check["evidence_id"]))
        positions.setdefault(source_key, []).append(index)
    if set(positions) != running_keys:
        return False
    grouped_checks, grouping_error = _verification_groups(batch)
    if grouping_error or set(grouped_checks) != running_keys:
        return False
    dependency_receipts = (
        click_dependency_cache.receipts_for_groups(
            Path(workspace_root),
            grouped_checks,
            declarations=_dependency_declarations(sources, running_keys),
            git_capture=_git_capture,
        )
        if not workspace_changed and workspace_root and workspace_digest
        else {}
    )
    verification["running_evidence_keys"] = []
    verification["running_environment_digests"] = {}
    verification["running_environment_binding"] = []
    verification["running_environment_binding_digest"] = ""
    verification["running_executable_digests"] = {}
    if workspace_changed:
        previous_revision = revision
        revision += 1
        verification["mutation_revision"] = revision
        verification["status"] = "failed"
        verification["failed_revision"] = revision
        verification["unchanged_failure_retries"] = 1
        state["observations"] = _fresh_observation_state()
        for source_key, source in sources.items():
            if not isinstance(source, dict):
                continue
            check_positions = positions.get(source_key)
            source_ran = bool(
                check_positions
                and (
                    min(check_positions) < succeeded_count
                    or (exit_code != 0 and min(check_positions) == succeeded_count)
                )
            )
            was_current = _evidence_is_current(source, previous_revision)
            if check_positions and source_ran:
                source["status"] = "failed"
                source["attempts"] = int(source.get("attempts", 0)) + 1
                source["unchanged_failure_retries"] = 1
                source["last_exit_code"] = exit_code
            elif check_positions:
                # A preceding check stopped the batch before this source executed.
                source["status"] = "ready"
                source["unchanged_failure_retries"] = 0
                source["last_exit_code"] = None
            else:
                source["status"] = "stale" if was_current else "ready"
                source["unchanged_failure_retries"] = 0
                source["last_exit_code"] = None
            source["verified_revision"] = -1
        external = state.get("external_evidence")
        browser_required = bool(
            isinstance(external, dict) and external.get("browser_required") is True
        )
        browser_source_key = (
            str(external.get("browser_source_key", ""))
            if isinstance(external, dict)
            else ""
        )
        state["external_evidence"] = _fresh_external_evidence_state(
            required=browser_required,
            source_key=browser_source_key,
        )
    else:
        for source_key, check_positions in positions.items():
            source = sources.get(source_key)
            if not isinstance(source, dict):
                return False
            first_position = min(check_positions)
            source_ran = first_position < succeeded_count or (
                exit_code != 0 and first_position == succeeded_count
            )
            if source_ran:
                source["attempts"] = int(source.get("attempts", 0)) + 1
            if all(position < succeeded_count for position in check_positions):
                source["status"] = "passed"
                source["verified_revision"] = revision
                source["last_exit_code"] = 0
                source["unchanged_failure_retries"] = 0
                source["locked_check_digest"] = str(
                    source.get("last_check_digest", "")
                )
                environment_digest = str(
                    environment_digests.get(source_key, "")
                )
                check_digest = str(source.get("last_check_digest", ""))
                reserved_units = int(source.get("reserved_units", 0))
                if (
                    workspace_root
                    and workspace_digest
                    and environment_digest
                    and check_digest
                ):
                    source["verified_contract_digest"] = str(
                        state.get("contract_digest", "")
                    )
                    source["verified_check_digest"] = check_digest
                    source["verified_units"] = reserved_units
                    source["verified_root"] = os.path.normcase(workspace_root)
                    source["verified_tree_digest"] = workspace_digest
                    source["verified_environment_digest"] = environment_digest
                    source["verified_at"] = int(time.time())
                    _store_dependency_receipt(
                        source, dependency_receipts.get(source_key)
                    )
                else:
                    source["verified_contract_digest"] = ""
                    source["verified_check_digest"] = ""
                    source["verified_units"] = 0
                    source["verified_root"] = ""
                    source["verified_tree_digest"] = ""
                    source["verified_environment_digest"] = ""
                    source["verified_at"] = 0
                    _clear_dependency_receipt(source)
            elif source_ran:
                source["status"] = "failed"
                source["verified_revision"] = -1
                source["last_exit_code"] = exit_code
            else:
                source["status"] = "ready"
                source["verified_revision"] = -1
                source["last_exit_code"] = None

        argv_keys = _evidence_keys_for_kind(sources, "argv")
        if argv_keys and all(
            _evidence_is_current(sources.get(source_key), revision)
            for source_key in argv_keys
        ):
            verification["status"] = "passed"
            verification["verified_revision"] = revision
            verification["failed_revision"] = -1
            verification["unchanged_failure_retries"] = 0
            verification["locked_batch_digest"] = batch_digest
        else:
            verification["status"] = "failed" if exit_code != 0 else "ready"
            verification["verified_revision"] = -1
            verification["failed_revision"] = revision if exit_code != 0 else -1
    state["verification"] = verification
    state["updated_at"] = int(time.time())
    _write_json(path, state)
    return True


def _claim_observation_run(
    path: Path, raw: str, command_digest: str, runner_token: str
) -> tuple[dict[str, Any] | None, str]:
    """Atomically authorize one observation runner before any read executes."""
    if not _managed_observation_path(path):
        return None, "Click observation runner received an unmanaged state path."
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None, "Click observation runner could not read its managed state."
    status = state.get("status")
    if status not in {"approved", "review"}:
        return None, "Click observation runner is no longer authorized to execute."
    observations = state.get("observations")
    if not isinstance(observations, dict):
        return None, "Click observation state is unavailable or malformed."
    entries = observations.get("entries")
    if not isinstance(entries, dict):
        return None, "Click observation state is unavailable or malformed."
    entry = entries.get(command_digest)
    if not isinstance(entry, dict) or entry.get("status") != "running":
        return None, "Click observation runner is no longer authorized to execute."

    expected_revision = 0
    if status == "approved":
        verification = state.get("verification")
        if not isinstance(verification, dict):
            return None, "Click observation revision state is unavailable."
        mutation_revision = verification.get("mutation_revision", 0)
        if not isinstance(mutation_revision, int) or isinstance(
            mutation_revision, bool
        ):
            return None, "Click observation revision state is malformed."
        expected_revision = mutation_revision
    if entry.get("revision") != expected_revision:
        return None, "Click observation runner revision is stale."

    token_digest = hashlib.sha256(runner_token.encode()).hexdigest()
    if not secrets.compare_digest(
        str(entry.get("runner_token_digest", "")), token_digest
    ):
        return None, "Click observation runner token did not match active state."
    claimed_at = entry.get("runner_claimed_at", 0)
    if not isinstance(claimed_at, int) or isinstance(claimed_at, bool):
        return None, "Click observation runner claim state is malformed."
    if claimed_at:
        return None, "Click observation runner was already claimed; replay is blocked."
    if not _unclaimed_reservation_is_fresh(
        entry.get("started_at", 0), OBSERVATION_RESERVATION_TTL_SECONDS
    ):
        return None, "Click observation runner authorization expired before execution."

    request, _, error = _validate_inspection_request(raw)
    if error:
        return None, error
    assert request is not None
    if _capability_digest(request) != command_digest:
        return None, "Click observation runner request digest did not match."

    entry["runner_claimed_at"] = int(time.time()) or 1
    entries[command_digest] = entry
    observations["entries"] = entries
    state["observations"] = observations
    state["updated_at"] = int(time.time())
    _write_json(path, state)
    return request, ""


def _record_observation_result(
    path: Path,
    command_digest: str,
    runner_token: str,
    exit_code: int,
    output_bytes: int,
    incomplete: bool,
) -> bool:
    if not _managed_observation_path(path):
        return False
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    if state.get("status") not in {"approved", "review"}:
        return False
    observations = state.get("observations")
    if not isinstance(observations, dict):
        return False
    entries = observations.get("entries")
    if not isinstance(entries, dict):
        return False
    entry = entries.get(command_digest)
    if not isinstance(entry, dict) or entry.get("status") != "running":
        return False
    token_digest = hashlib.sha256(runner_token.encode()).hexdigest()
    if not secrets.compare_digest(
        str(entry.get("runner_token_digest", "")), token_digest
    ):
        return False
    claimed_at = entry.get("runner_claimed_at", 0)
    if (
        not isinstance(claimed_at, int)
        or isinstance(claimed_at, bool)
        or claimed_at <= 0
    ):
        return False

    entry["runner_token_digest"] = ""
    entry["runner_claimed_at"] = 0
    entry["started_at"] = 0
    entry["last_exit_code"] = exit_code
    entry["output_bytes"] = output_bytes
    if exit_code != 0:
        entry["status"] = "failed"
    elif incomplete:
        entry["status"] = "incomplete"
    else:
        entry["status"] = "success"
    entries[command_digest] = entry
    observations["entries"] = entries
    state["observations"] = observations
    state["updated_at"] = int(time.time())
    _write_json(path, state)
    return True


def _decode_encoded_request(encoded: str, label: str) -> tuple[str, str]:
    try:
        return base64.urlsafe_b64decode(encoded.encode()).decode(), ""
    except (ValueError, UnicodeDecodeError):
        return "", f"Click {label} runner received an invalid request."


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        pass

    # `relative_to` is lexical and can miss case aliases on a case-insensitive
    # filesystem. Compare filesystem identity for existing ancestors as well.
    try:
        root_stat = root.stat()
        current = path if path.is_dir() else path.parent
        for candidate in (current, *current.parents):
            if os.path.samestat(candidate.stat(), root_stat):
                return True
    except OSError:
        pass
    return False


def _valid_git_worktree_marker(marker: Path) -> bool:
    """Recognize real Git metadata, not an unrelated empty ancestor named .git."""
    try:
        if marker.is_dir():
            return (marker / "HEAD").is_file() and (
                (marker / "objects").is_dir() or (marker / "commondir").is_file()
            )
        if not marker.is_file():
            return False
        first_line = marker.read_text(encoding="utf-8", errors="strict").splitlines()[0]
        if not first_line.lower().startswith("gitdir:"):
            return False
        target = Path(first_line.split(":", 1)[1].strip())
        if not target.is_absolute():
            target = marker.parent / target
        target = target.resolve(strict=True)
        return (target / "HEAD").is_file() and (
            (target / "objects").is_dir() or (target / "commondir").is_file()
        )
    except (IndexError, OSError, RuntimeError, UnicodeError):
        return False


def _workspace_boundary(workspace: Path | None = None) -> Path:
    candidate = workspace or Path.cwd()
    try:
        current = candidate.resolve()
    except (OSError, RuntimeError):
        current = Path(os.path.abspath(candidate))
    for possible in (current, *current.parents):
        marker = possible / ".git"
        if _valid_git_worktree_marker(marker):
            return possible
    return current


def _git_metadata_present(workspace: Path | None = None) -> bool:
    root = _workspace_boundary(workspace)
    return _valid_git_worktree_marker(root / ".git")


def _unsafe_inherited_environment_key(key: str) -> bool:
    upper = key.upper()
    return upper.startswith(("LD_", "DYLD_")) or upper in {
        "GCONV_PATH",
        "LOCPATH",
    }


def _sanitized_executable_path(
    source: str | None = None, *, workspace: Path | None = None
) -> str:
    root = _workspace_boundary(workspace)
    value = os.environ.get("PATH", "") if source is None else source
    entries: list[str] = []
    seen: set[str] = set()
    for raw_entry in value.split(os.pathsep):
        normalized_entry = raw_entry.strip()
        if (
            len(normalized_entry) >= 2
            and normalized_entry[0] == normalized_entry[-1]
            and normalized_entry[0] in {'"', "'"}
        ):
            normalized_entry = normalized_entry[1:-1]
        normalized_entry = os.path.expandvars(normalized_entry)
        if not normalized_entry or not os.path.isabs(normalized_entry):
            continue
        lexical = Path(os.path.abspath(normalized_entry))
        if _path_is_within(lexical, root):
            continue
        try:
            resolved = Path(normalized_entry).resolve()
        except (OSError, RuntimeError):
            continue
        if _path_is_within(resolved, root):
            continue
        rendered = str(resolved)
        key = os.path.normcase(rendered)
        if key in seen:
            continue
        seen.add(key)
        entries.append(rendered)
    return os.pathsep.join(entries)


def _resolve_read_only_executable(
    executable: str, *, workspace: Path | None = None
) -> tuple[str | None, str]:
    if _is_path_qualified_executable(executable):
        return None, "read-only executables must use an unqualified trusted name"
    root = _workspace_boundary(workspace)

    inherited = shutil.which(executable)
    if inherited is not None:
        inherited_lexical = Path(os.path.abspath(inherited))
        if _path_is_within(inherited_lexical, root):
            return None, "the inherited executable path is inside the workspace"
        try:
            inherited_path = Path(inherited).resolve(strict=True)
        except (OSError, RuntimeError):
            return None, "the inherited executable path could not be resolved safely"
        if _path_is_within(inherited_path, root):
            return None, "the inherited executable resolves inside the workspace"

    sanitized_path = _sanitized_executable_path(workspace=root)
    resolved = shutil.which(executable, path=sanitized_path)
    if resolved is None:
        return None, "the executable was not found on Click's sanitized PATH"
    resolved_lexical = Path(os.path.abspath(resolved))
    if _path_is_within(resolved_lexical, root):
        return None, "the executable path is inside the workspace"
    try:
        resolved_path = Path(resolved).resolve(strict=True)
    except (OSError, RuntimeError):
        return None, "the executable path could not be resolved safely"
    if _path_is_within(resolved_path, root):
        return None, "the executable resolves inside the workspace"
    if not resolved_path.is_file():
        return None, "the executable does not resolve to a regular file"
    return str(resolved_path), ""


def _sanitized_read_only_environment(
    *, workspace: Path | None = None
) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() != "PATH" and not _unsafe_inherited_environment_key(key)
    }
    environment["PATH"] = _sanitized_executable_path(workspace=workspace)
    return environment


def _execution_argv(argv: list[str]) -> list[str]:
    parts = _structured_ssh_parts(argv)
    if parts is None:
        return argv
    target, remote_argv = parts
    safe_git_argv, error = _build_read_only_git_argv(remote_argv)
    if error or safe_git_argv is None:
        return argv
    return [
        argv[0],
        "-n",
        "-F",
        "none",
        "-o",
        "BatchMode=yes",
        "-o",
        "KbdInteractiveAuthentication=no",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "NumberOfPasswordPrompts=0",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "UpdateHostKeys=no",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=1",
        "-o",
        "ClearAllForwardings=yes",
        "-o",
        "ForwardAgent=no",
        "-o",
        "PermitLocalCommand=no",
        "-o",
        "RemoteCommand=none",
        "-o",
        "RequestTTY=no",
        target,
        shlex.join(safe_git_argv),
    ]


def _is_git_remote_output_request(argv: list[str]) -> bool:
    parts = _structured_ssh_parts(argv)
    git_argv = parts[1] if parts is not None else argv
    return _git_subcommand(git_argv) == "remote"


def _redact_git_remote_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        if "://" not in value:
            return value
        scheme, remainder = value.split("://", 1)
        remainder = remainder.rsplit("@", 1)[-1]
        return f"{scheme}://{remainder.split('?', 1)[0].split('#', 1)[0]}"
    if parsed.scheme and parsed.netloc:
        netloc = parsed.netloc.rsplit("@", 1)[-1]
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    if re.fullmatch(r"[^/@\s]+@[^/\s:]+:.+", value):
        return value.rsplit("@", 1)[-1].split("?", 1)[0].split("#", 1)[0]
    return value


def _redact_git_remote_output(data: bytes) -> bytes:
    lines = []
    for line in data.decode("utf-8", errors="replace").splitlines(keepends=True):
        value = line.rstrip("\r\n")
        lines.append(_redact_git_remote_url(value) + line[len(value) :])
    return "".join(lines).encode()


def _execute_argv_commands(
    commands: list[list[str]],
    stdout_file: Any | None = None,
    stderr_file: Any | None = None,
    *,
    trusted_read_only: bool = False,
    workspace: Path | None = None,
    environment: dict[str, str] | None = None,
) -> int:
    exit_code = 0
    for argv in commands:
        try:
            redact = _is_git_remote_output_request(argv)
            execution_argv = _execution_argv(argv)
            if trusted_read_only:
                executable, error = _resolve_read_only_executable(
                    argv[0], workspace=workspace
                )
                if error or executable is None:
                    _write_runner_stream(
                        stderr_file,
                        (
                            "Click rejected the read-only executable at execution time: "
                            f"{error}.\n"
                        ).encode(),
                        error=True,
                    )
                    return 2
                execution_argv[0] = executable
            result = click_process.run_argv(
                execution_argv,
                stdout=subprocess.PIPE if redact else stdout_file,
                stderr=subprocess.PIPE if redact else stderr_file,
                env=(
                    _sanitized_read_only_environment(workspace=workspace)
                    if trusted_read_only
                    else environment
                ),
            )
            if redact:
                _write_runner_stream(
                    stdout_file, _redact_git_remote_output(result.stdout or b"")
                )
                _write_runner_stream(
                    stderr_file,
                    _redact_git_remote_output(result.stderr or b""),
                    error=True,
                )
            exit_code = int(result.returncode)
        except OSError as exc:
            message = f"Click could not start `{argv[0]}`: {exc}\n"
            if stderr_file is None:
                sys.stderr.write(message)
            else:
                stderr_file.write(message.encode())
            exit_code = 127
        if exit_code != 0:
            break
    return exit_code


def _write_runner_stream(handle: Any | None, data: bytes, *, error: bool = False) -> None:
    if handle is not None:
        handle.write(data)
        return
    target = sys.stderr.buffer if error else sys.stdout.buffer
    target.write(data)
    target.flush()


def _execute_native_get_content(
    argv: list[str], stdout_file: Any | None, stderr_file: Any | None
) -> int | None:
    if Path(argv[0]).name.lower() != "get-content":
        return None
    paths = _get_content_paths(argv)
    if paths is None:
        _write_runner_stream(
            stderr_file,
            (
                b"Click Get-Content inspection supports only positional paths, "
                b"-Path, -LiteralPath, and -Raw.\n"
            ),
            error=True,
        )
        return 2
    try:
        for path in paths:
            _write_runner_stream(stdout_file, Path(path).read_bytes())
    except OSError as exc:
        _write_runner_stream(
            stderr_file, f"Click could not read {path}: {exc}\n".encode(), error=True
        )
        return 1
    return 0


def _execute_read_only_git(
    argv: list[str],
    stdout_file: Any | None,
    stderr_file: Any | None,
    *,
    workspace: Path | None = None,
) -> int:
    safe_argv, error = _build_read_only_git_argv(argv)
    if error or safe_argv is None:
        _write_runner_stream(
            stderr_file,
            f"Click rejected Git inspection at execution time: {error}\n".encode(),
            error=True,
        )
        return 2
    executable, executable_error = _resolve_read_only_executable(
        argv[0], workspace=workspace
    )
    if executable_error or executable is None:
        _write_runner_stream(
            stderr_file,
            (
                "Click rejected the Git executable at execution time: "
                f"{executable_error}.\n"
            ).encode(),
            error=True,
        )
        return 2
    safe_argv[0] = executable
    try:
        redact = _is_git_remote_output_request(argv)
        result = click_process.run_argv(
            safe_argv,
            stdout=subprocess.PIPE if redact else stdout_file,
            stderr=subprocess.PIPE if redact else stderr_file,
            env=_sanitized_git_environment(workspace=workspace),
        )
        if redact:
            _write_runner_stream(
                stdout_file, _redact_git_remote_output(result.stdout or b"")
            )
            _write_runner_stream(
                stderr_file,
                _redact_git_remote_output(result.stderr or b""),
                error=True,
            )
        return int(result.returncode)
    except OSError as exc:
        _write_runner_stream(
            stderr_file,
            f"Click could not start `git`: {exc}\n".encode(),
            error=True,
        )
        return 127


def _execute_inspection_commands(
    commands: list[list[str]],
    stdout_file: Any | None = None,
    stderr_file: Any | None = None,
    *,
    workspace: Path | None = None,
) -> int:
    for argv in commands:
        native_result = _execute_native_get_content(argv, stdout_file, stderr_file)
        if native_result is not None:
            if native_result != 0:
                return native_result
            continue
        if argv[0].lower() in {"git", "git.exe"}:
            exit_code = _execute_read_only_git(
                argv, stdout_file, stderr_file, workspace=workspace
            )
        else:
            exit_code = _execute_argv_commands(
                [argv],
                stdout_file,
                stderr_file,
                trusted_read_only=True,
                workspace=workspace,
            )
        if exit_code != 0:
            return exit_code
    return 0


def _run_inspection_request(
    request: dict[str, Any], state_result: tuple[Path, str, str] | None = None
) -> int:
    commands = request["commands"]
    recorded_result = False
    try:
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            exit_code = _execute_inspection_commands(commands, stdout_file, stderr_file)

            stdout_bytes = stdout_file.tell()
            stderr_bytes = stderr_file.tell()
            output_bytes = stdout_bytes + stderr_bytes
            incomplete = output_bytes > MAX_OBSERVATION_OUTPUT_BYTES
            if state_result is not None:
                state_path, request_digest, runner_token = state_result
                with _state_lock():
                    recorded = _record_observation_result(
                        state_path,
                        request_digest,
                        runner_token,
                        exit_code,
                        output_bytes,
                        incomplete,
                    )
                if not recorded:
                    sys.stderr.write("Click could not record the observation result safely.\n")
                    return exit_code or 2
                recorded_result = True

            stdout_file.seek(0)
            stderr_file.seek(0)
            remaining = MAX_OBSERVATION_OUTPUT_BYTES
            if exit_code == 0:
                remaining -= _copy_limited_output(
                    stdout_file, sys.stdout.buffer, remaining
                )
                _copy_limited_output(stderr_file, sys.stderr.buffer, remaining)
            else:
                remaining -= _copy_limited_output(
                    stderr_file, sys.stderr.buffer, remaining
                )
                _copy_limited_output(stdout_file, sys.stdout.buffer, remaining)
            if incomplete:
                sys.stderr.write(
                    "\n[Click] Read/search output exceeded 48,000 bytes. Narrow or "
                    "paginate the next command; one unchanged retry is available.\n"
                )
    except OSError as exc:
        if state_result is not None and not recorded_result:
            state_path, request_digest, runner_token = state_result
            with _state_lock():
                recorded = _record_observation_result(
                    state_path,
                    request_digest,
                    runner_token,
                    127,
                    0,
                    False,
                )
            if not recorded:
                sys.stderr.write("Click could not record the observation failure safely.\n")
        sys.stderr.write(f"Click observation runner failed: {exc}\n")
        return 127
    return exit_code


def _run_inspection_once(arguments: list[str]) -> int:
    if len(arguments) != 1:
        sys.stderr.write("usage: click_gate.py run-inspection-once <request>\n")
        return 2
    raw, error = _decode_encoded_request(arguments[0], "inspection")
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    request, _, error = _validate_inspection_request(raw)
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    assert request is not None
    return _run_inspection_request(request)


def _run_observation(arguments: list[str]) -> int:
    if len(arguments) != 4:
        sys.stderr.write(
            "usage: click_gate.py run-observation <state> <digest> <token> <request>\n"
        )
        return 2
    state_path = Path(arguments[0])
    request_digest, runner_token, encoded = arguments[1:]
    raw, error = _decode_encoded_request(encoded, "observation")
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    with _state_lock():
        request, error = _claim_observation_run(
            state_path, raw, request_digest, runner_token
        )
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    assert request is not None
    return _run_inspection_request(
        request, (state_path, request_digest, runner_token)
    )


def _claim_mutation_run(
    path: Path, raw: str, request_digest: str, runner_token: str
) -> tuple[dict[str, Any] | None, str]:
    """Atomically authorize one mutation runner before any side effect."""
    if not _managed_contract_path(path):
        return None, "Click mutation runner received an unmanaged state path."
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None, "Click mutation runner could not read its contract state."
    if not isinstance(state, dict) or state.get("status") != "approved":
        return None, "Click mutation runner is no longer authorized to execute."
    mutation = state.get("mutation")
    if not isinstance(mutation, dict) or mutation.get("status") != "running":
        return None, "Click mutation runner is no longer authorized to execute."
    if mutation.get("request_digest") != request_digest:
        return None, "Click mutation runner request digest did not match active state."
    token_digest = hashlib.sha256(runner_token.encode()).hexdigest()
    if not secrets.compare_digest(
        str(mutation.get("runner_token_digest", "")), token_digest
    ):
        return None, "Click mutation runner token did not match active state."
    claimed_at = mutation.get("runner_claimed_at", 0)
    if not isinstance(claimed_at, int) or isinstance(claimed_at, bool):
        return None, "Click mutation runner claim state is malformed."
    if claimed_at:
        return None, "Click mutation runner was already claimed; replay is blocked."
    if not _unclaimed_reservation_is_fresh(
        mutation.get("started_at", 0), MUTATION_RUNNING_TTL_SECONDS
    ):
        return None, "Click mutation runner authorization expired before execution."

    request, error = _validate_mutation_request(raw)
    if error:
        return None, error
    assert request is not None
    if _capability_digest(request) != request_digest:
        return None, "Click mutation runner request digest did not match."

    mutation["runner_claimed_at"] = int(time.time()) or 1
    state["mutation"] = mutation
    state["updated_at"] = int(time.time())
    _write_json(path, state)
    return request, ""


def _record_mutation_result(
    path: Path, request_digest: str, runner_token: str, exit_code: int
) -> bool:
    if not _managed_contract_path(path):
        return False
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    if not isinstance(state, dict) or state.get("status") != "approved":
        return False
    mutation = state.get("mutation")
    if not isinstance(mutation, dict) or mutation.get("status") != "running":
        return False
    if mutation.get("request_digest") != request_digest:
        return False
    token_digest = hashlib.sha256(runner_token.encode()).hexdigest()
    if not secrets.compare_digest(
        str(mutation.get("runner_token_digest", "")), token_digest
    ):
        return False
    claimed_at = mutation.get("runner_claimed_at", 0)
    if (
        not isinstance(claimed_at, int)
        or isinstance(claimed_at, bool)
        or not claimed_at
    ):
        return False
    mutation.update(
        {
            "status": "passed" if exit_code == 0 else "failed",
            "runner_token_digest": "",
            "runner_claimed_at": 0,
            "started_at": 0,
            "last_exit_code": exit_code,
        }
    )
    state["mutation"] = mutation
    state["updated_at"] = int(time.time())
    _write_json(path, state)
    return True


def _run_mutation(arguments: list[str]) -> int:
    if len(arguments) != 4:
        sys.stderr.write(
            "usage: click_gate.py run-mutation <state> <digest> <token> <request>\n"
        )
        return 2
    state_path = Path(arguments[0])
    request_digest, runner_token, encoded = arguments[1:]
    raw, error = _decode_encoded_request(encoded, "mutation")
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    with _state_lock():
        request, error = _claim_mutation_run(
            state_path, raw, request_digest, runner_token
        )
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    assert request is not None
    exit_code = _execute_argv_commands([request["argv"]])
    with _state_lock():
        recorded = _record_mutation_result(
            state_path, request_digest, runner_token, exit_code
        )
    if not recorded:
        sys.stderr.write("Click could not record the mutation result safely.\n")
        return exit_code or 2
    return exit_code


def _managed_contract_path(path: Path) -> bool:
    return _managed_state_path(path, ("session-contract-",))


def _managed_observation_path(path: Path) -> bool:
    return _managed_state_path(path, ("session-contract-", "review-"))


def _service_snapshot(path: Path, service_id: str) -> dict[str, Any] | None:
    if not _managed_contract_path(path):
        return None
    state: Any = None
    for attempt in range(5):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            break
        except PermissionError:
            # Windows may briefly deny a reader while another process replaces
            # the state file. Do not mistake that sharing collision for a
            # missing or stopped managed service.
            if attempt == 4:
                return None
            time.sleep(0.02)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
    if not isinstance(state, dict) or state.get("status") != "approved":
        return None
    service = state.get("service")
    if not isinstance(service, dict) or service.get("service_id") != service_id:
        return None
    return dict(service)


def _record_service_fields(
    path: Path,
    service_id: str,
    *,
    expected_statuses: tuple[str, ...] | None = None,
    **fields: Any,
) -> bool:
    if not _managed_contract_path(path):
        return False
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    if not isinstance(state, dict) or state.get("status") != "approved":
        return False
    service = state.get("service")
    if not isinstance(service, dict) or service.get("service_id") != service_id:
        return False
    if expected_statuses is not None and service.get("status") not in expected_statuses:
        return False
    service.update(fields)
    state["service"] = service
    state["updated_at"] = int(time.time())
    _write_json(path, state)
    return True


def _claim_service_runner(
    path: Path,
    service_id: str,
    request: dict[str, Any],
    cwd_raw: str,
    runner_token: str,
    *,
    supervisor: bool,
) -> str:
    if not _managed_contract_path(path):
        return "Click managed service runner received an unmanaged state path."
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "Click managed service runner could not read its contract state."
    if not isinstance(state, dict) or state.get("status") != "approved":
        return "Click managed service runner is no longer authorized to execute."
    service = state.get("service")
    expected_status = "launching" if supervisor else "starting"
    if (
        not isinstance(service, dict)
        or service.get("service_id") != service_id
        or service.get("status") != expected_status
        or service.get("stop_requested") is True
    ):
        return "Click managed service runner is no longer authorized to execute."
    request_digest = _capability_digest({"request": request, "cwd": cwd_raw})
    if service.get("request_digest") != request_digest:
        return "Click managed service runner request digest did not match active state."
    token_digest = hashlib.sha256(runner_token.encode()).hexdigest()
    if not secrets.compare_digest(
        str(service.get("runner_token_digest", "")), token_digest
    ):
        return "Click managed service runner token did not match active state."
    runner_claimed_at = service.get("runner_claimed_at", 0)
    supervisor_claimed_at = service.get("supervisor_claimed_at", 0)
    for claimed_at in (runner_claimed_at, supervisor_claimed_at):
        if not isinstance(claimed_at, int) or isinstance(claimed_at, bool):
            return "Click managed service runner claim state is malformed."
    if supervisor:
        if runner_claimed_at <= 0 or supervisor_claimed_at > 0:
            return "Click managed service supervisor was already claimed or not launched."
        if not _unclaimed_reservation_is_fresh(
            runner_claimed_at, SERVICE_START_TIMEOUT_SECONDS * 2
        ):
            return "Click managed service supervisor authorization expired before launch."
        service["supervisor_claimed_at"] = int(time.time()) or 1
    else:
        if runner_claimed_at > 0 or supervisor_claimed_at > 0:
            return "Click managed service start runner was already claimed."
        if not _unclaimed_reservation_is_fresh(
            service.get("started_at", 0), SERVICE_START_TIMEOUT_SECONDS * 2
        ):
            return "Click managed service start authorization expired before launch."
        service["runner_claimed_at"] = int(time.time()) or 1
        service["status"] = "launching"
    state["service"] = service
    state["updated_at"] = int(time.time())
    _write_json(path, state)
    return ""


def _run_service_supervisor(arguments: list[str]) -> int:
    if len(arguments) != 5:
        return 2
    state_path = Path(arguments[0])
    service_id, runner_token, cwd_raw, encoded = arguments[1:]
    raw, error = _decode_encoded_request(encoded, "managed service")
    if error:
        return 2
    request, error = _validate_service_request(raw)
    if error or request is None or request.get("action") != "start":
        return 2
    with _state_lock():
        claim_error = _claim_service_runner(
            state_path,
            service_id,
            request,
            cwd_raw,
            runner_token,
            supervisor=True,
        )
    if claim_error:
        return 2
    cwd = Path(cwd_raw)
    if not cwd.is_dir():
        with _state_lock():
            _record_service_fields(
                state_path,
                service_id,
                expected_statuses=("launching",),
                status="failed",
                last_exit_code=2,
            )
        return 2
    try:
        child = click_process.spawn_argv(
            _execution_argv(request["argv"]),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError:
        with _state_lock():
            _record_service_fields(
                state_path,
                service_id,
                expected_statuses=("launching",),
                status="failed",
                last_exit_code=127,
                stop_requested=False,
            )
        return 127

    time.sleep(0.2)
    early_exit = child.poll()
    with _state_lock():
        recorded = _record_service_fields(
            state_path,
            service_id,
            expected_statuses=("launching",),
            status="failed" if early_exit is not None else "running",
            supervisor_pid=os.getpid(),
            child_pid=child.pid,
            last_exit_code=int(early_exit) if early_exit is not None else None,
        )
    if early_exit is not None or not recorded:
        if early_exit is None:
            _terminate_managed_child(child)
        return int(early_exit or 2)

    started = time.monotonic()
    stop_requested = False
    while True:
        exit_code = child.poll()
        if exit_code is not None:
            break
        snapshot = _service_snapshot(state_path, service_id)
        if snapshot is None or snapshot.get("stop_requested") is True:
            stop_requested = True
            exit_code = _terminate_managed_child(child)
            break
        if time.monotonic() - started >= MANAGED_SERVICE_MAX_SECONDS:
            stop_requested = True
            exit_code = _terminate_managed_child(child)
            break
        time.sleep(0.2)

    with _state_lock():
        _record_service_fields(
            state_path,
            service_id,
            expected_statuses=("running", "stopping", "launching"),
            status="stopped" if stop_requested else "failed",
            stop_requested=False,
            child_pid=0,
            supervisor_pid=0,
            last_exit_code=int(exit_code or 0),
        )
    return int(exit_code or 0)


def _run_service_start(arguments: list[str]) -> int:
    if len(arguments) != 5:
        sys.stderr.write(
            "usage: click_gate.py run-service-start "
            "<state> <id> <token> <cwd> <request>\n"
        )
        return 2
    state_path = Path(arguments[0])
    service_id, runner_token, cwd_raw, encoded = arguments[1:]
    raw, error = _decode_encoded_request(encoded, "managed service")
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    request, error = _validate_service_request(raw)
    if error or request is None or request.get("action") != "start":
        sys.stderr.write(f"{error or 'Managed service start request is invalid.'}\n")
        return 2
    with _state_lock():
        claim_error = _claim_service_runner(
            state_path,
            service_id,
            request,
            cwd_raw,
            runner_token,
            supervisor=False,
        )
    if claim_error:
        sys.stderr.write(f"{claim_error}\n")
        return 2
    supervisor = [
        *_stateful_runner_prefix("run-service-supervisor"),
        str(state_path.resolve()),
        service_id,
        runner_token,
        cwd_raw,
        encoded,
    ]
    try:
        click_process.spawn_argv(
            supervisor,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        with _state_lock():
            _record_service_fields(
                state_path,
                service_id,
                expected_statuses=("launching",),
                status="failed",
                last_exit_code=127,
            )
        sys.stderr.write(f"Click could not start the managed service supervisor: {exc}\n")
        return 127
    deadline = time.monotonic() + SERVICE_START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        snapshot = _service_snapshot(state_path, service_id)
        if snapshot is None:
            return 2
        if snapshot.get("status") == "running":
            sys.stdout.write("Click managed service started\n")
            return 0
        if snapshot.get("status") == "failed":
            sys.stderr.write("Click managed service exited during startup.\n")
            return int(snapshot.get("last_exit_code") or 2)
        if snapshot.get("status") in {"stopping", "stopped"}:
            return 2
        time.sleep(0.05)
    with _state_lock():
        _record_service_fields(
            state_path,
            service_id,
            expected_statuses=("launching", "starting"),
            status="stopping",
            stop_requested=True,
        )
    sys.stderr.write("Click managed service did not start within its bounded timeout.\n")
    return 2


def _run_service_stop(arguments: list[str]) -> int:
    if len(arguments) != 2:
        sys.stderr.write("usage: click_gate.py run-service-stop <state> <id>\n")
        return 2
    state_path = Path(arguments[0])
    service_id = arguments[1]
    deadline = time.monotonic() + SERVICE_STOP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        snapshot = _service_snapshot(state_path, service_id)
        if snapshot is not None and snapshot.get("status") in {
            "failed",
            "idle",
            "stopped",
        }:
            sys.stdout.write("Click managed service stopped\n")
            return 0
        time.sleep(0.05)
    sys.stderr.write("Click managed service did not stop within its bounded timeout.\n")
    return 2


def _git_capture(cwd: Path, arguments: list[str]) -> bytes | None:
    executable, error = _resolve_read_only_executable("git", workspace=cwd)
    if error or executable is None:
        return None
    try:
        result = click_process.run_argv(
            [
                executable,
                "--no-pager",
                "--no-optional-locks",
                "-c",
                "core.fsmonitor=false",
                *arguments,
            ],
            cwd=cwd,
            env=_sanitized_git_environment(workspace=cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def _hash_workspace_path(hasher: Any, root: Path, relative: str) -> None:
    encoded_path = os.fsencode(relative)
    hasher.update(len(encoded_path).to_bytes(8, "big"))
    hasher.update(encoded_path)
    target = root / relative
    try:
        metadata = target.lstat()
    except OSError:
        hasher.update(b"missing")
        return
    hasher.update(str(metadata.st_mode).encode())
    if target.is_symlink():
        try:
            hasher.update(os.fsencode(os.readlink(target)))
        except OSError:
            hasher.update(b"unreadable-link")
        return
    if not target.is_file():
        hasher.update(b"non-file")
        return
    try:
        with target.open("rb") as handle:
            while True:
                chunk = handle.read(128 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
    except OSError:
        hasher.update(b"unreadable-file")


def _git_workspace_snapshot(
    cwd: Path, protected_untracked: list[str] | None = None
) -> dict[str, Any] | None:
    root_output = _git_capture(cwd, ["rev-parse", "--show-toplevel"])
    if root_output is None:
        return None
    root = Path(os.fsdecode(root_output.strip()))
    has_head = _git_capture(root, ["rev-parse", "--verify", "HEAD"]) is not None
    diff_commands = (
        [["diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--"]]
        if has_head
        else [
            ["diff", "--binary", "--no-ext-diff", "--no-textconv", "--cached", "--"],
            ["diff", "--binary", "--no-ext-diff", "--no-textconv", "--"],
        ]
    )
    hasher = hashlib.sha256()
    if has_head:
        head_tree = _git_capture(root, ["rev-parse", "HEAD^{tree}"])
        if head_tree is None:
            return None
        hasher.update(len(head_tree).to_bytes(8, "big"))
        hasher.update(head_tree)
    for arguments in diff_commands:
        diff = _git_capture(root, arguments)
        if diff is None:
            return None
        hasher.update(len(diff).to_bytes(8, "big"))
        hasher.update(diff)

    untracked_output = _git_capture(
        root, ["ls-files", "--others", "--exclude-standard", "-z"]
    )
    if untracked_output is None:
        return None
    current_untracked = [
        os.fsdecode(item) for item in untracked_output.split(b"\0") if item
    ]
    if protected_untracked is None:
        protected_untracked = [*current_untracked]
    for relative in sorted(protected_untracked):
        _hash_workspace_path(hasher, root, relative)
    return {
        "root": str(root),
        "digest": hasher.hexdigest(),
        "protected_untracked": protected_untracked,
        "current_untracked": current_untracked,
    }


def _new_untracked_is_suspicious(relative: str) -> bool:
    parts = [part.lower() for part in Path(relative).parts if part not in {"", "."}]
    if not parts:
        return False
    if parts[0] in NEW_SOURCE_PATH_SEGMENTS:
        return True
    if any(
        part in {"config", "configs", "migration", "migrations", "src"}
        for part in parts
    ):
        return True
    for index, part in enumerate(parts):
        if part not in {"app", "lib"}:
            continue
        if index >= 2 and parts[index - 2] in {
            "apps",
            "modules",
            "packages",
            "services",
        }:
            return True
    if any(
        parts[index : index + 2] == ["db", "migrate"]
        for index in range(max(0, len(parts) - 1))
    ):
        return True
    if len(parts) == 1:
        name = parts[0]
        suffix = Path(name).suffix.lower()
        if suffix in {
            ".c", ".cc", ".cpp", ".cs", ".go", ".h", ".hpp", ".java", ".js",
            ".jsx", ".php", ".py", ".rb", ".rs", ".ts", ".tsx",
        }:
            return True
        if name in {
            "cargo.toml", "compose.yaml", "compose.yml", "docker-compose.yaml",
            "docker-compose.yml", "dockerfile", "go.mod", "package-lock.json",
            "package.json", "pnpm-lock.yaml", "pyproject.toml", "requirements.txt",
            "yarn.lock",
        }:
            return True
    return False


def _claim_verification_run(
    state_path: Path,
    raw: str,
    batch_digest: str,
    runner_token: str,
) -> tuple[dict[str, Any] | None, str]:
    """Atomically bind one runner invocation before any check can execute."""
    if not _managed_contract_path(state_path):
        return None, "Click verification runner received an unmanaged state path."
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None, "Click verification runner could not read its contract state."
    if not isinstance(state, dict) or state.get("status") != "approved":
        return None, "Click verification runner is no longer authorized to execute."
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return None, "Click verification runner could not read its approved scale."
    if verification.get("status") != "running":
        return None, "Click verification runner is no longer authorized to execute."
    if verification.get("last_batch_digest") != batch_digest:
        return None, "Click verification runner batch digest did not match active state."
    token_digest = hashlib.sha256(runner_token.encode()).hexdigest()
    if not secrets.compare_digest(
        str(verification.get("runner_token_digest", "")), token_digest
    ):
        return None, "Click verification runner token did not match active state."
    claimed_at = verification.get("runner_claimed_at", 0)
    if not isinstance(claimed_at, int) or isinstance(claimed_at, bool):
        return None, "Click verification runner claim state is malformed."
    if claimed_at:
        return None, "Click verification runner was already claimed; replay is blocked."
    if not _unclaimed_reservation_is_fresh(
        verification.get("started_at", 0), VERIFY_RUNNING_TTL_SECONDS
    ):
        return None, "Click verification runner authorization expired before execution."

    scale = str(verification.get("scale", ""))
    if not click_verification_policy.is_profile(scale):
        return None, "Click verification runner could not read its approved scale."
    sources = _evidence_sources(state)
    if sources is None or not sources:
        return None, "Click verification runner could not read its evidence ledger."
    batch, _, error = _validate_verification_batch(raw, scale, sources)
    if error:
        return None, error
    assert batch is not None
    if _capability_digest(batch) != batch_digest:
        return None, "Click verification runner batch digest did not match."
    running_keys = {
        key
        for key in verification.get("running_evidence_keys", [])
        if isinstance(key, str)
    }
    batch_keys = {
        _evidence_key(str(check["evidence_id"])) for check in batch["checks"]
    }
    if not running_keys or batch_keys != running_keys:
        return None, "Click verification runner evidence binding did not match active state."

    grouped_checks, grouping_error = _verification_groups(batch)
    if grouping_error:
        return None, grouping_error
    prepared_environment_digests = verification.get("running_environment_digests")
    prepared_executable_digests = verification.get("running_executable_digests")
    for prepared in (prepared_environment_digests, prepared_executable_digests):
        if (
            not isinstance(prepared, dict)
            or set(prepared) != running_keys
            or any(
                not isinstance(value, str)
                or not re.fullmatch(r"[0-9a-f]{64}", value)
                for value in prepared.values()
            )
        ):
            return None, "Click verification runner context binding was malformed."
    running_environment_binding = verification.get("running_environment_binding")
    if not _verification_environment_binding_is_authentic(
        running_environment_binding,
        verification.get("running_environment_binding_digest"),
        runner_token,
    ):
        return None, "Click verification runner environment binding was malformed."
    verification_environment, environment_rebound, binding_error = (
        _verification_environment_from_binding(
            running_environment_binding,
            runner_token,
            _verification_environment(cwd=Path.cwd()),
        )
    )
    if binding_error:
        return None, binding_error
    assert verification_environment is not None
    for source_key, checks in grouped_checks.items():
        source = sources.get(source_key)
        if not isinstance(source, dict):
            return None, "Click verification runner source reservation is unavailable."
        expected_digest = _verification_group_digest(checks)
        if source.get("reserved_check_digest") != expected_digest:
            return None, "Click verification runner source reservation did not match."
        executable_records = _verification_executable_records(
            checks,
            cwd=Path.cwd(),
            environment=verification_environment,
        )
        if executable_records is None:
            return None, "Click verification executable changed before execution."
        current_executable_digest = _capability_digest(
            {
                "executables": _verification_executable_payload(
                    executable_records
                )
            }
        )
        current_environment_digest = _verification_environment_digest_from_records(
            executable_records,
            cwd=Path.cwd(),
            environment=verification_environment,
        )
        if not secrets.compare_digest(
            str(prepared_executable_digests.get(source_key, "")),
            current_executable_digest,
        ):
            return None, "Click verification executable changed before execution."
        if not secrets.compare_digest(
            str(prepared_environment_digests.get(source_key, "")),
            current_environment_digest,
        ):
            prepared_environment_digests[source_key] = current_environment_digest
            environment_rebound = True
        for check, record in zip(checks, executable_records):
            execution_path = record.get("_execution_path")
            if not isinstance(execution_path, str) or not execution_path:
                return None, "Click verification executable binding was malformed."
            approved_argv = list(check["argv"])
            execution_argv = list(approved_argv)
            execution_argv[0] = execution_path
            # Preserve the approved identity privately while keeping the
            # established claim API's executable-pinned argv behavior.
            check["_click_approved_argv"] = approved_argv
            check["argv"] = execution_argv
    verification["runner_claimed_at"] = int(time.time()) or 1
    verification["running_environment_digests"] = prepared_environment_digests
    state["verification"] = verification
    state["updated_at"] = int(time.time())
    _write_json(state_path, state)
    batch["_click_verification_environment"] = verification_environment
    batch["_click_verification_environment_rebound"] = environment_rebound
    return batch, ""


def _release_unclaimed_verification_reservation(
    state_path: Path, batch_digest: str, runner_token: str
) -> bool:
    """Release one authenticated reservation when admission failed pre-check."""
    if not _managed_contract_path(state_path):
        return False
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    if not isinstance(state, dict) or state.get("status") != "approved":
        return False
    verification = state.get("verification")
    if not isinstance(verification, dict) or verification.get("status") != "running":
        return False
    if verification.get("last_batch_digest") != batch_digest:
        return False
    token_digest = hashlib.sha256(runner_token.encode()).hexdigest()
    if not secrets.compare_digest(
        str(verification.get("runner_token_digest", "")), token_digest
    ):
        return False
    claimed_at = verification.get("runner_claimed_at", 0)
    if (
        not isinstance(claimed_at, int)
        or isinstance(claimed_at, bool)
        or claimed_at != 0
    ):
        return False
    sources = _evidence_sources(state)
    if sources is None or not sources:
        return False
    running_keys = verification.get("running_evidence_keys")
    if not isinstance(running_keys, list) or not running_keys:
        return False
    for source_key in running_keys:
        source = sources.get(source_key) if isinstance(source_key, str) else None
        if not isinstance(source, dict) or source.get("status") != "running":
            return False

    for source_key in running_keys:
        source = sources[source_key]
        source["status"] = "ready"
        source["last_exit_code"] = None
    verification.update(
        {
            "status": "ready",
            "runner_token_digest": "",
            "runner_claimed_at": 0,
            "running_evidence_keys": [],
            "running_environment_digests": {},
            "running_environment_binding": [],
            "running_environment_binding_digest": "",
            "running_executable_digests": {},
            "started_at": 0,
            "last_exit_code": None,
        }
    )
    state["verification"] = verification
    state["updated_at"] = int(time.time())
    _write_json(state_path, state)
    return True


def _run_verification(arguments: list[str]) -> int:
    if len(arguments) != 4:
        sys.stderr.write(
            "usage: click_gate.py run-verification <state> <digest> <token> <batch>\n"
        )
        return 2
    state_path = Path(arguments[0])
    batch_digest, runner_token, encoded = arguments[1:]
    raw, error = _decode_encoded_request(encoded, "verification")
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    with _state_lock():
        batch, error = _claim_verification_run(
            state_path, raw, batch_digest, runner_token
        )
        if error:
            _release_unclaimed_verification_reservation(
                state_path, batch_digest, runner_token
            )
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    assert batch is not None
    checks = batch["checks"]
    grouped_checks, grouping_error = _verification_groups(batch)
    if grouping_error:
        sys.stderr.write(f"{grouping_error}\n")
        return 2
    verification_environment = batch.pop("_click_verification_environment", None)
    if not isinstance(verification_environment, dict):
        sys.stderr.write(
            "Click verification runner lost its prepared environment binding.\n"
        )
        return 2
    environment_rebound = batch.pop(
        "_click_verification_environment_rebound", False
    )
    if environment_rebound:
        print(
            "[Click] Verification runner environment changed after preparation; "
            "rebound to the current canonical environment.",
            flush=True,
        )
    before = _git_workspace_snapshot(Path.cwd())
    snapshot_failed = before is None and _git_metadata_present(Path.cwd())
    if snapshot_failed:
        sys.stderr.write(
            "[Click] Verification could not establish a protected Git workspace "
            "snapshot. No check was executed.\n"
        )

    exit_code = 2 if snapshot_failed else 0
    succeeded_count = 0
    if not snapshot_failed:
        for index, check in enumerate(checks, start=1):
            argv = check["argv"]
            rendered = (
                subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)
            )
            print(
                f"[Click verification {index}/{len(checks)}:{check['evidence_id']}:"
                f"{check['class']}] {rendered}",
                flush=True,
            )
            exit_code = _execute_argv_commands(
                [argv], environment=verification_environment
            )
            if exit_code != 0:
                break
            succeeded_count += 1

    for check in checks:
        approved_argv = check.pop("_click_approved_argv", None)
        if isinstance(approved_argv, list) and approved_argv:
            check["argv"] = approved_argv

    workspace_changed = False
    workspace_root = ""
    workspace_digest = ""
    if before is not None:
        after = _git_workspace_snapshot(
            Path.cwd(), list(before["protected_untracked"])
        )
        new_untracked: list[str] = []
        if after is not None:
            workspace_root = str(after.get("root", ""))
            workspace_digest = str(after.get("digest", ""))
            new_untracked = sorted(
                set(after["current_untracked"]) - set(before["current_untracked"])
            )
            if new_untracked:
                rendered_paths = ", ".join(new_untracked[:8])
                if len(new_untracked) > 8:
                    rendered_paths += f", and {len(new_untracked) - 8} more"
                sys.stderr.write(
                    "[Click] Verification created new non-ignored untracked path(s): "
                    f"{rendered_paths}. Review them before keeping the result.\n"
                )
        suspicious_new = [
            path for path in new_untracked if _new_untracked_is_suspicious(path)
        ]
        workspace_changed = (
            after is None
            or after["digest"] != before["digest"]
            or bool(new_untracked)
        )
        if workspace_changed:
            if suspicious_new:
                sys.stderr.write(
                    "[Click] A new path looks like source, configuration, or migration "
                    "content; this classification is informational because every new "
                    "non-ignored path already makes verification stale.\n"
                )
            sys.stderr.write(
                "[Click] Verification changed protected repository content. "
                "The batch is stale; perform or restore that change through the approved "
                "mutation path before verifying again.\n"
            )
            if exit_code == 0:
                exit_code = 3

    with _state_lock():
        recorded = _record_verification_result(
            state_path,
            batch,
            batch_digest,
            runner_token,
            exit_code,
            succeeded_count,
            workspace_changed=workspace_changed,
            workspace_root=workspace_root if not workspace_changed else "",
            workspace_digest=workspace_digest if not workspace_changed else "",
        )
    if not recorded:
        sys.stderr.write("Click could not record the verification result safely.\n")
        return exit_code or 2
    return exit_code


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
