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
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import time
from typing import Any


CONTROL_COMMAND = "click-gate"
STRING_FIELDS = ("outcome", "plain_language")
OBJECT_FIELDS = ("boundary", "build", "verification")
CONTRACT_FIELDS = set(STRING_FIELDS) | set(OBJECT_FIELDS) | {"must_hold"}
BOUNDARY_FIELDS = {"in_scope", "out_of_scope"}
BUILD_FIELDS = {"approach", "semantics", "order"}
VERIFICATION_FIELDS = {"scale", "done_when", "intermediate_gate"}
VERIFICATION_SCALES = ("quick", "focused", "full")
VERIFICATION_UNIT_LIMITS = {"quick": 1, "focused": 4, "full": 10}
CAPABILITY_PROTOCOL_VERSION = 1
INSPECTION_REQUEST_FIELDS = {"version", "commands"}
MUTATION_REQUEST_FIELDS = {"version", "argv"}
VERIFICATION_BATCH_FIELDS = {"version", "checks"}
VERIFICATION_CHECK_FIELDS = {"argv", "class"}
VERIFICATION_CLASSES = {"targeted": 1, "broad": 3, "deep": 5}
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
MAX_CAPABILITY_COMMANDS = 8
MAX_ARGV_ITEMS = 128
MAX_CONTRACT_CHARS = 4_000
MAX_CAPABILITY_REQUEST_CHARS = 6_000
MAX_VERIFICATION_BATCH_CHARS = 6_000
MAX_OBSERVATION_OUTPUT_BYTES = 48_000
MAX_OBSERVATION_ENTRIES = 64
OBSERVATION_RUNNING_TTL_SECONDS = 10 * 60
MUTATION_RUNNING_TTL_SECONDS = 10 * 60
VERIFY_RUNNING_TTL_SECONDS = 60 * 60
STATE_TTL_SECONDS = 7 * 24 * 60 * 60
STATE_LOCK_TIMEOUT_SECONDS = 5
STATE_LOCK_STALE_SECONDS = 30
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
    "cat-file",
    "check-ignore",
    "describe",
    "diff",
    "for-each-ref",
    "grep",
    "log",
    "ls-files",
    "ls-tree",
    "name-rev",
    "rev-parse",
    "show",
    "status",
}

SHELL_CONTROL_PUNCTUATION = set("();<>|&")
SED_READ_SCRIPT = re.compile(
    r"^\s*(?:\d+|\$)(?:\s*,\s*(?:\d+|\$))?\s*[pq]\s*$"
)

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


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _deny(reason: str) -> None:
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )


def _allow_rewritten(command: str) -> None:
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": {"command": command},
            }
        }
    )


def _read_event() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid hook input: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("hook input must be a JSON object")
    return value


def _state_root() -> Path:
    configured = os.environ.get("PLUGIN_DATA")
    if configured:
        return Path(configured) / "gate-state"
    return Path(tempfile.gettempdir()) / "click-plugin-data" / "gate-state"


def _preference_path() -> Path:
    configured = os.environ.get("CLICK_CONFIG_HOME")
    if configured:
        return Path(configured) / "preferences.json"
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "Click" / "preferences.json"
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "click" / "preferences.json"
    return Path.home() / ".config" / "click" / "preferences.json"


def _identity_path(event: dict[str, Any], scope: str) -> Path:
    identity = {
        "session_id": str(event.get("session_id", "")),
        "cwd": str(event.get("cwd", "")),
    }
    if scope in {"turn", "review"}:
        identity["turn_id"] = str(event.get("turn_id", ""))
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    name = f"{scope}-{hashlib.sha256(encoded).hexdigest()}.json"
    return _state_root() / name


def _state_path(event: dict[str, Any]) -> Path:
    return _identity_path(event, "turn")


def _mode_path(event: dict[str, Any]) -> Path:
    return _identity_path(event, "session")


def _contract_path(event: dict[str, Any]) -> Path:
    return _identity_path(event, "session-contract")


def _prompt_path(event: dict[str, Any]) -> Path:
    return _identity_path(event, "session-prompt")


def _review_path(event: dict[str, Any]) -> Path:
    return _identity_path(event, "review")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=".gate-",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        temporary = Path(handle.name)
    temporary.chmod(0o600)
    os.replace(temporary, path)


@contextmanager
def _state_lock() -> Any:
    root = _state_root()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = root / ".state.lock"
    deadline = time.monotonic() + STATE_LOCK_TIMEOUT_SECONDS
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            os.write(descriptor, str(os.getpid()).encode())
        except FileExistsError:
            try:
                stale = time.time() - lock_path.stat().st_mtime > STATE_LOCK_STALE_SECONDS
            except OSError:
                stale = False
            if stale:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise OSError("timed out waiting for Click state lock")
            time.sleep(0.025)
    try:
        yield
    finally:
        try:
            os.close(descriptor)
        finally:
            try:
                lock_path.unlink()
            except OSError:
                pass


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


def _fresh_verification_state(contract: dict[str, Any]) -> dict[str, Any]:
    scale = str(contract["verification"]["scale"])
    return {
        "scale": scale,
        "unit_limit": VERIFICATION_UNIT_LIMITS[scale],
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
        "workspace_changed": False,
        "started_at": 0,
    }


def _fresh_observation_state() -> dict[str, Any]:
    return {"entries": {}}


def _fresh_mutation_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "request_digest": "",
        "runner_token_digest": "",
        "started_at": 0,
        "last_exit_code": None,
    }


def _mutation_is_running(mutation: Any) -> bool:
    if not isinstance(mutation, dict) or mutation.get("status") != "running":
        return False
    started_at = int(mutation.get("started_at", 0))
    return bool(
        started_at
        and time.time() - started_at <= MUTATION_RUNNING_TTL_SECONDS
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
) -> None:
    _write_json(
        _contract_path(event),
        {
            "status": status,
            "contract_digest": digest,
            "staged_turn_id": str(event.get("turn_id", "")),
            "approved_turn_id": "",
            "verification": _fresh_verification_state(contract),
            "observations": _fresh_observation_state(),
            "mutation": _fresh_mutation_state(),
            "updated_at": int(time.time()),
        },
    )


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


def _record_user_prompt(event: dict[str, Any]) -> None:
    turn_id = str(event.get("turn_id", ""))
    if not turn_id:
        raise ValueError("Click requires the Codex turn_id on UserPromptSubmit")
    _write_json(
        _prompt_path(event),
        {"turn_id": turn_id, "updated_at": int(time.time())},
    )


def _read_user_prompt_turn(event: dict[str, Any]) -> str:
    try:
        value = json.loads(_prompt_path(event).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""
    if not isinstance(value, dict):
        return ""
    return str(value.get("turn_id", ""))


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
    return bool(
        verification.get("status") == "passed"
        and int(verification.get("verified_revision", -1))
        == int(verification.get("mutation_revision", 0))
    )


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

    observations = state.get("observations")
    if isinstance(observations, dict):
        entries = observations.get("entries")
        if isinstance(entries, dict):
            now = time.time()
            for entry in entries.values():
                if not isinstance(entry, dict) or entry.get("status") != "running":
                    continue
                started_at = int(entry.get("started_at", 0))
                if started_at and now - started_at <= OBSERVATION_RUNNING_TTL_SECONDS:
                    return (
                        "Click blocked this mutation while an approved read or search is "
                        "running. Wait for that evidence before changing the implementation."
                    )

    verification["mutation_revision"] = int(
        verification.get("mutation_revision", 0)
    ) + 1
    if verification.get("status") == "passed":
        verification["status"] = "stale"
    elif verification.get("status") == "failed":
        verification["status"] = "ready"
        verification["failed_revision"] = -1
        verification["unchanged_failure_retries"] = 0
        verification["workspace_changed"] = False
    state["verification"] = verification
    state["observations"] = _fresh_observation_state()
    _save_contract_state(event, state)
    return ""


def _prune_state() -> None:
    root = _state_root()
    if not root.exists():
        return
    cutoff = time.time() - STATE_TTL_SECONDS
    for candidate in root.glob("*.json"):
        try:
            if candidate.stat().st_mtime < cutoff:
                candidate.unlink()
        except OSError:
            continue


def _validate_contract(raw: str) -> tuple[dict[str, Any] | None, str]:
    if len(raw) > MAX_CONTRACT_CHARS:
        return (
            None,
            "Execution Contract is too large; keep it compact and under 4,000 characters.",
        )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None, "Execution Contract must be valid JSON."
    if not isinstance(value, dict):
        return None, "Execution Contract must be a JSON object."

    unknown_fields = sorted(set(value) - CONTRACT_FIELDS)
    if unknown_fields:
        rendered = ", ".join(f"`{field}`" for field in unknown_fields)
        return (
            None,
            f"Execution Contract contains unsupported top-level field(s): {rendered}.",
        )

    for field in STRING_FIELDS:
        text = value.get(field)
        if not isinstance(text, str) or not text.strip():
            return None, f"Execution Contract field `{field}` must be a non-empty string."

    must_hold = value.get("must_hold")
    if not isinstance(must_hold, list) or not must_hold:
        return None, "Execution Contract field `must_hold` must be a non-empty list."
    if any(not isinstance(item, str) or not item.strip() for item in must_hold):
        return None, "Every `must_hold` item must be a non-empty string."

    boundary = value.get("boundary")
    if not isinstance(boundary, dict):
        return None, "Execution Contract field `boundary` must be an object."
    unknown_boundary_fields = sorted(set(boundary) - BOUNDARY_FIELDS)
    if unknown_boundary_fields:
        rendered = ", ".join(f"`{field}`" for field in unknown_boundary_fields)
        return None, f"Execution Contract boundary contains unsupported field(s): {rendered}."
    in_scope = boundary.get("in_scope")
    if not isinstance(in_scope, list) or not in_scope:
        return None, "Boundary `in_scope` must be a non-empty list."
    if any(not isinstance(item, str) or not item.strip() for item in in_scope):
        return None, "Every boundary `in_scope` item must be a non-empty string."
    out_of_scope = boundary.get("out_of_scope")
    if not isinstance(out_of_scope, list):
        return None, "Boundary `out_of_scope` must be a list."
    if any(not isinstance(item, str) or not item.strip() for item in out_of_scope):
        return None, "Every boundary `out_of_scope` item must be a non-empty string."

    build = value.get("build")
    if not isinstance(build, dict):
        return None, "Execution Contract field `build` must be an object."
    unknown_build_fields = sorted(set(build) - BUILD_FIELDS)
    if unknown_build_fields:
        rendered = ", ".join(f"`{field}`" for field in unknown_build_fields)
        return None, f"Execution Contract build contains unsupported field(s): {rendered}."
    approach = build.get("approach")
    if not isinstance(approach, list) or not approach:
        return None, "Build `approach` must be a non-empty list."
    if any(not isinstance(item, str) or not item.strip() for item in approach):
        return None, "Every build `approach` item must be a non-empty string."
    for field in ("semantics", "order"):
        if field not in build:
            continue
        items = build[field]
        if not isinstance(items, list) or not items:
            return None, f"Optional build `{field}` must be omitted or a non-empty list."
        if any(not isinstance(item, str) or not item.strip() for item in items):
            return None, f"Every build `{field}` item must be a non-empty string."

    verification = value.get("verification")
    if not isinstance(verification, dict):
        return None, "Execution Contract field `verification` must be an object."
    unknown_verification_fields = sorted(set(verification) - VERIFICATION_FIELDS)
    if unknown_verification_fields:
        rendered = ", ".join(
            f"`{field}`" for field in unknown_verification_fields
        )
        return (
            None,
            f"Execution Contract verification contains unsupported field(s): {rendered}.",
        )
    scale = verification.get("scale")
    if scale not in VERIFICATION_SCALES:
        allowed = ", ".join(VERIFICATION_SCALES)
        return None, f"Verification `scale` must be one of: {allowed}."
    done_when = verification.get("done_when")
    if not isinstance(done_when, list) or not done_when:
        return None, "Verification `done_when` must be a non-empty list."
    if any(not isinstance(item, str) or not item.strip() for item in done_when):
        return None, "Every verification `done_when` item must be a non-empty string."
    if "intermediate_gate" in verification:
        intermediate_gate = verification["intermediate_gate"]
        if not isinstance(intermediate_gate, str) or not intermediate_gate.strip():
            return None, "Optional verification `intermediate_gate` must be omitted or non-empty."

    return value, ""


def _decode_capability_request(
    raw: str, label: str, *, limit: int = MAX_CAPABILITY_REQUEST_CHARS
) -> tuple[dict[str, Any] | None, str]:
    if len(raw) > limit:
        return None, f"{label} request must stay under {limit:,} characters."
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None, f"{label} request must be valid JSON."
    if not isinstance(value, dict):
        return None, f"{label} request must be a JSON object."
    if value.get("version") != CAPABILITY_PROTOCOL_VERSION:
        return (
            None,
            f"{label} request `version` must be {CAPABILITY_PROTOCOL_VERSION}.",
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
    executable = Path(argv[0]).name.lower()
    if executable in SHELL_EXECUTABLES:
        return (
            None,
            f"{label} cannot invoke a shell interpreter. Pass the executable and each "
            "argument directly instead of using `-c` or `-Command`.",
        )
    return argv, ""


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
    if len(commands) > MAX_CAPABILITY_COMMANDS:
        return (
            None,
            False,
            f"Inspection may contain at most {MAX_CAPABILITY_COMMANDS} commands.",
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
    return {"version": CAPABILITY_PROTOCOL_VERSION, "argv": argv}, ""


def _validate_verification_batch(
    raw: str, scale: str
) -> tuple[dict[str, Any] | None, int, str]:
    value, error = _decode_capability_request(
        raw, "Verification batch", limit=MAX_VERIFICATION_BATCH_CHARS
    )
    if error:
        return None, 0, error
    assert value is not None
    if "commands" in value:
        return (
            None,
            0,
            "Click 0.16 verification uses `checks` with argv arrays and a submitted "
            "`class`; legacy shell-string `commands` are no longer accepted.",
        )
    unknown = sorted(set(value) - VERIFICATION_BATCH_FIELDS)
    if unknown:
        rendered = ", ".join(f"`{field}`" for field in unknown)
        return None, 0, f"Verification batch contains unsupported field(s): {rendered}."
    checks = value.get("checks")
    if not isinstance(checks, list) or not checks:
        return None, 0, "Verification batch `checks` must be a non-empty list."
    if len(checks) > MAX_CAPABILITY_COMMANDS:
        return None, 0, f"Verification may contain at most {MAX_CAPABILITY_COMMANDS} checks."
    normalized: list[dict[str, Any]] = []
    units = 0
    for index, check in enumerate(checks, start=1):
        if not isinstance(check, dict):
            return None, 0, f"Verification check {index} must be an object."
        unknown_check = sorted(set(check) - VERIFICATION_CHECK_FIELDS)
        if unknown_check:
            rendered = ", ".join(f"`{field}`" for field in unknown_check)
            return None, 0, f"Verification check {index} has unsupported field(s): {rendered}."
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
        effective_class = str(check_class)
        if VERIFICATION_CLASSES[effective_class] < VERIFICATION_CLASSES[minimum_class]:
            effective_class = minimum_class
        units += VERIFICATION_CLASSES[effective_class]
        normalized.append({"argv": argv, "class": effective_class})
    limit = VERIFICATION_UNIT_LIMITS[scale]
    if units > limit:
        return (
            None,
            units,
            f"The {scale} verification budget allows {limit} unit(s), but this batch "
            f"costs {units} after Hook minimum-class inference. Remove lower-value "
            "checks instead of expanding verification.",
        )
    return {
        "version": CAPABILITY_PROTOCOL_VERSION,
        "checks": normalized,
    }, units, ""


def _control_request(command: str) -> tuple[str | None, str, str]:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        return None, "", f"Malformed {CONTROL_COMMAND} command: {exc}."
    if not tokens or tokens[0] != CONTROL_COMMAND:
        return None, "", ""
    if len(tokens) == 2 and tokens[1] in {"arm", "bypass", "review"}:
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
        "inspect",
        "mutate",
        "stage",
        "pass",
        "verify",
    }:
        return tokens[1], tokens[2], ""
    return (
        "",
        "",
        f"Use `{CONTROL_COMMAND} arm`, `{CONTROL_COMMAND} stage '<Execution Contract "
        f"JSON>'`, `{CONTROL_COMMAND} pass '<Execution Contract JSON>'`, "
        f"`{CONTROL_COMMAND} inspect '<Inspection JSON>'`, "
        f"`{CONTROL_COMMAND} mutate '<Mutation JSON>'`, "
        f"`{CONTROL_COMMAND} verify '<Verification Batch JSON>'`, "
        f"`{CONTROL_COMMAND} review`, `{CONTROL_COMMAND} bypass`, "
        f"`{CONTROL_COMMAND} default on|manual|status`, or "
        f"`{CONTROL_COMMAND} mode adaptive|strict`.",
    )


def _git_subcommand(tokens: list[str]) -> str:
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "-C" and index + 1 < len(tokens):
            index += 2
            continue
        if token.startswith("--git-dir=") or token.startswith("--work-tree="):
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token
    return ""


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


def _is_broad_exploration_command(command: str) -> bool:
    segments = _shell_segments(command)
    return bool(segments) and any(
        _is_broad_exploration_tokens(segment) for segment in segments
    )


def _capability_digest(request: dict[str, Any]) -> str:
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _observation_runner_command(
    state_path: Path, request: dict[str, Any], request_digest: str, runner_token: str
) -> str:
    encoded = base64.urlsafe_b64encode(
        json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()
    ).decode()
    arguments = [
        sys.executable,
        str(Path(__file__).resolve()),
        "run-observation",
        str(state_path),
        request_digest,
        runner_token,
        encoded,
    ]
    return subprocess.list2cmdline(arguments) if os.name == "nt" else shlex.join(arguments)


def _prepare_observation(
    event: dict[str, Any], request: dict[str, Any], broad_inventory: bool, *, review: bool = False
) -> tuple[str, str]:
    if broad_inventory and not review:
        return (
            "",
            "Click blocked a repository-wide inventory rescan after approval. Narrow "
            "the read or search to the approved area. If the approved boundary must "
            "expand, stop and ask the user instead of reopening the whole repository.",
        )

    state_path = _review_path(event) if review else _contract_path(event)
    if review:
        state = _read_review_state(event)
        if state.get("status") != "review":
            return "", "Click review state is unavailable; activate review mode again."
        revision = 0
    else:
        state = _read_contract_state(event)
        if state.get("status") != "approved":
            return "", "Click observation state is unavailable; approve the contract again."
        mutation = state.get("mutation")
        if _mutation_is_running(mutation):
            return "", "Wait for the structured Click mutation to finish before inspection."
        if isinstance(mutation, dict) and mutation.get("status") == "running":
            state["mutation"] = _fresh_mutation_state()
        verification = state.get("verification")
        if not isinstance(verification, dict):
            return "", "Click verification state is unavailable; approve the contract again."
        if verification.get("status") == "running":
            return "", "The final Click verification batch is already running."
        revision = int(verification.get("mutation_revision", 0))

    observations = state.get("observations")
    if not isinstance(observations, dict):
        observations = _fresh_observation_state()
    entries = observations.get("entries")
    if not isinstance(entries, dict):
        entries = {}

    digest = _capability_digest(request)
    if review and broad_inventory:
        for existing in entries.values():
            if (
                isinstance(existing, dict)
                and existing.get("broad_inventory") is True
                and existing.get("status") == "success"
            ):
                return (
                    "",
                    "Click review already completed one successful repository-wide "
                    "inventory. Narrow the next read or search instead of rescanning "
                    "the whole repository.",
                )

    prior = entries.get(digest)
    unchanged_retries = 0
    if isinstance(prior, dict) and int(prior.get("revision", -1)) == revision:
        status = str(prior.get("status", ""))
        unchanged_retries = int(prior.get("unchanged_retries", 0))
        if status == "success":
            return (
                "",
                "Click blocked an identical successful read or search because neither "
                "the implementation nor its evidence changed. Use the existing result "
                "or issue a narrower, materially different query.",
            )
        if status == "running":
            started_at = int(prior.get("started_at", 0))
            if started_at and time.time() - started_at <= OBSERVATION_RUNNING_TTL_SECONDS:
                return "", "The identical Click read or search is already running."
            status = "failed"
        if status in {"failed", "incomplete"}:
            if unchanged_retries >= 1:
                return (
                    "",
                    "The identical read or search already failed or produced incomplete "
                    "evidence twice. Change or narrow the command instead of repeating it.",
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
    return _observation_runner_command(state_path, request, digest, runner_token), ""


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
    return subprocess.list2cmdline(arguments) if os.name == "nt" else shlex.join(arguments)


def _mutation_runner_command(
    event: dict[str, Any], request: dict[str, Any], request_digest: str, runner_token: str
) -> str:
    arguments = [
        sys.executable,
        str(Path(__file__).resolve()),
        "run-mutation",
        str(_contract_path(event)),
        request_digest,
        runner_token,
        _encoded_request(request),
    ]
    return subprocess.list2cmdline(arguments) if os.name == "nt" else shlex.join(arguments)


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
        "started_at": int(time.time()),
        "last_exit_code": None,
    }
    _save_contract_state(event, state)
    return _mutation_runner_command(
        event, request, request_digest, runner_token
    ), ""


def _verification_runner_command(
    event: dict[str, Any], batch: dict[str, Any], batch_digest: str, runner_token: str
) -> str:
    encoded = base64.urlsafe_b64encode(
        json.dumps(batch, ensure_ascii=False, separators=(",", ":")).encode()
    ).decode()
    arguments = [
        sys.executable,
        str(Path(__file__).resolve()),
        "run-verification",
        str(_contract_path(event)),
        batch_digest,
        runner_token,
        encoded,
    ]
    return subprocess.list2cmdline(arguments) if os.name == "nt" else shlex.join(arguments)


def _prepare_verification(
    event: dict[str, Any], raw: str
) -> tuple[str, str]:
    state = _read_contract_state(event)
    if state.get("status") != "approved":
        return "", "Approve the staged Click execution contract before verification."
    mutation = state.get("mutation")
    if _mutation_is_running(mutation):
        return "", "Wait for the structured Click mutation to finish before verification."
    if isinstance(mutation, dict) and mutation.get("status") == "running":
        state["mutation"] = _fresh_mutation_state()
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return "", "Click verification state is unavailable; stage and approve again."
    scale = str(verification.get("scale", ""))
    if scale not in VERIFICATION_UNIT_LIMITS:
        return "", "Approved Click verification scale is invalid; stage and approve again."

    observations = state.get("observations")
    if isinstance(observations, dict):
        entries = observations.get("entries")
        if isinstance(entries, dict):
            now = time.time()
            for entry in entries.values():
                if not isinstance(entry, dict) or entry.get("status") != "running":
                    continue
                started_at = int(entry.get("started_at", 0))
                if started_at and now - started_at <= OBSERVATION_RUNNING_TTL_SECONDS:
                    return (
                        "",
                        "Wait for the approved read or search to finish before starting "
                        "the final verification batch.",
                    )

    batch, units, error = _validate_verification_batch(raw, scale)
    if error:
        return "", error
    assert batch is not None
    canonical = json.dumps(batch, sort_keys=True, separators=(",", ":"))
    batch_digest = hashlib.sha256(canonical.encode()).hexdigest()

    status = str(verification.get("status", "ready"))
    if status == "running":
        started_at = int(verification.get("started_at", 0))
        if started_at and time.time() - started_at <= VERIFY_RUNNING_TTL_SECONDS:
            return "", "The approved Click verification batch is already running."
        status = "failed"
        verification["status"] = status
        verification["last_exit_code"] = 124

    revision = int(verification.get("mutation_revision", 0))
    if status == "passed" and int(verification.get("verified_revision", -1)) == revision:
        return (
            "",
            "The approved final verification batch already passed for the current code. "
            "Click blocks needless successful repetition.",
        )
    locked_digest = str(verification.get("locked_batch_digest", ""))
    if locked_digest and locked_digest != batch_digest:
        return (
            "",
            "The successful Click verification batch is locked. Re-run the same batch only "
            "when a later in-scope mutation makes its result stale.",
        )
    if status == "failed" and int(verification.get("failed_revision", -1)) == revision:
        last_digest = str(verification.get("last_batch_digest", ""))
        retries = int(verification.get("unchanged_failure_retries", 0))
        if last_digest != batch_digest or retries >= 1:
            return (
                "",
                "The final verification batch failed without a subsequent code mutation. "
                "Fix the in-scope cause before retrying; one unchanged transient retry is allowed.",
            )
        verification["unchanged_failure_retries"] = retries + 1

    runner_token = secrets.token_urlsafe(24)
    verification.update(
        {
            "status": "running",
            "attempts": int(verification.get("attempts", 0)) + 1,
            "last_units": units,
            "last_batch_digest": batch_digest,
            "runner_token_digest": hashlib.sha256(runner_token.encode()).hexdigest(),
            "started_at": int(time.time()),
        }
    )
    state["verification"] = verification
    _save_contract_state(event, state)
    return _verification_runner_command(event, batch, batch_digest, runner_token), ""


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


def _is_read_only_tokens(tokens: list[str]) -> bool:
    if not tokens:
        return False
    if ENVIRONMENT_ASSIGNMENT.match(tokens[0]):
        return False

    executable = Path(tokens[0]).name.lower()
    if executable == "git":
        if _git_subcommand(tokens) not in READ_ONLY_GIT_SUBCOMMANDS:
            return False
        return not any(
            token in {"--ext-diff", "--textconv"}
            or token.startswith("--output")
            or token.startswith("--open-files-in-pager")
            for token in tokens[1:]
        )
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


def _is_read_only_bash(command: str) -> bool:
    request, _, _ = _inspection_request_from_bash(command)
    return request is not None


def _inspection_request_from_bash(
    command: str,
) -> tuple[dict[str, Any] | None, bool, str]:
    if not command.strip() or "\n" in command or "\r" in command or "`" in command:
        return None, False, ""
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


def _handle_prompt_submit(event: dict[str, Any]) -> None:
    _prune_state()
    _record_user_prompt(event)
    default_mode = _read_default_mode()
    if default_mode == "on":
        context = (
            "Click Always ON is enabled. For software creation, modification, deletion, "
            "or repair, compile the compact Click contract, explain it plainly, ask once, "
            "and do not pass or mutate until a later UserPromptSubmit turn approves the "
            "exact staged contract. Questions, "
            "explanations, and simple read-only inspection do not need a contract. For a "
            "read-only code review, run `click-gate review` before shell reads/searches; "
            "do not stage a build contract, and reuse successful evidence instead of "
            "repeating reads or repository-wide inventory. During review or approved "
            "implementation use versioned `click-gate inspect`, `click-gate mutate`, and "
            "`click-gate verify` argv requests when direct Bash intent is ambiguous. Use "
            "`click-gate bypass` only when the user explicitly opts out for the current turn."
        )
    elif default_mode == "manual":
        context = (
            "Click Manual mode is enabled. Apply the Click contract workflow only when "
            "the user explicitly selects @Click or $click. Ordinary software work and "
            "code review remain fail-open unless explicitly activated. Once activated, a "
            "staged or incomplete approved session contract remains mutation-locked across "
            "later turns. It must be staged now and passed only after a later "
            "UserPromptSubmit turn."
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
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            }
        }
    )


def _handle_pre_tool(event: dict[str, Any]) -> None:
    tool_name = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

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
                _write_state(event, "bypassed")
                _clear_contract_state(event)
                _clear_review_state(event)
                _allow_rewritten("echo Click bypassed for this turn")
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
                    rewritten, inspection_error = _prepare_observation(
                        event,
                        request,
                        broad_inventory,
                        review=True,
                    )
                    if inspection_error:
                        _deny(inspection_error)
                        return
                elif current_status == "passed" or approved_session_active:
                    rewritten, inspection_error = _prepare_observation(
                        event,
                        request,
                        broad_inventory,
                    )
                    if inspection_error:
                        _deny(inspection_error)
                        return
                else:
                    rewritten = _inspection_once_runner_command(request)
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
            if action == "verify":
                current_status = _read_state(event).get("status")
                if current_status != "passed" and _read_mode(event) != "strict":
                    _deny(
                        "Pass the approved Click execution contract in the current turn "
                        "before starting its final verification batch."
                    )
                    return
                rewritten, verification_error = _prepare_verification(event, value)
                if verification_error:
                    _deny(verification_error)
                    return
                _allow_rewritten(rewritten)
                return
            if action in {"stage", "pass"}:
                contract, validation_error = _validate_contract(value)
                if validation_error:
                    _deny(validation_error)
                    return
                assert contract is not None
                canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"))
                digest = hashlib.sha256(canonical.encode()).hexdigest()
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
                        _deny(
                            "The identical Click execution contract is already staged. "
                            "Pass it after the user's approval instead of staging it again."
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
                            "replan, or replace it mid-run. Finish its current revision and "
                            "final verification before staging the next contract. If the "
                            "approved outcome or authority is no longer sufficient, stop and "
                            "report the blocker."
                        )
                        return
                    _write_contract_state(event, "staged", digest, contract)
                    _write_state(event, "staged", digest)
                    _allow_rewritten("echo Click execution contract staged")
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
                        "This Click contract already completed final verification. Stage a "
                        "fresh contract and obtain a new user response before another mutation."
                    )
                    return
                if staged.get("contract_digest") != digest:
                    _deny(
                        "The execution contract differs from the version staged for user "
                        "approval. Pass the exact staged contract, or replace it before "
                        "approval and show the complete contract again."
                    )
                    return
                if staged.get("status") == "staged":
                    staged["approved_turn_id"] = current_turn_id
                staged["status"] = "approved"
                staged["contract_digest"] = digest
                _save_contract_state(event, staged)
                _write_state(event, "passed", digest)
                _allow_rewritten("echo Click mutation gate passed")
                return

    status = _read_state(event).get("status")
    if _is_plan_tool(tool_name):
        contract_state = _read_contract_state(event)
        session_contract_active = _session_contract_is_active(contract_state)
        if status in {"armed", "staged", "passed"} or session_contract_active:
            _deny(
                "Click blocked a parallel plan while its compact contract workflow is active. "
                "Show or implement the one contract directly; only a later user response can "
                "revise a staged proposal, and only the user can change an approved boundary."
            )
        elif status == "review":
            _deny(
                "Click blocked a plan during read-only review. Report findings from the "
                "evidence already gathered; a later implementation request uses a separate "
                "compact contract."
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
            rewritten, observation_error = _prepare_observation(
                event, inspection_request, broad_inventory
            )
            if observation_error:
                _deny(observation_error)
                return
            _allow_rewritten(rewritten)
        elif status == "review":
            rewritten, observation_error = _prepare_observation(
                event, inspection_request, broad_inventory, review=True
            )
            if observation_error:
                _deny(observation_error)
                return
            _allow_rewritten(rewritten)
        return

    if tool_name == "Bash" and status in {"passed", "review"}:
        if inspection_parse_error:
            _deny(inspection_parse_error)
            return
        if status == "review":
            _deny(
                "Click review accepts only structured read-only argv operations. Use "
                "`click-gate inspect '<Inspection JSON>'`; mutation and replanning remain "
                "blocked during review."
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
                "Click 0.16 final checks use `click-gate verify` with argv-based `checks` "
                "and an explicit targeted, broad, or deep class."
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
            "must_hold, build.approach, verification.scale, verification.done_when, and "
            "plain_language; add build.semantics, build.order, or an intermediate gate only "
            "when the work materially requires them; "
            "stage the exact JSON shown to the user, obtain approval, arm the approval turn, "
            "then pass that same JSON. In Always ON mode, arm is optional because the "
            "persistent preference already activates the gate. If the user does not want "
            "Click for this turn, run "
            "`click-gate bypass`."
        )


def _record_verification_result(
    path: Path,
    batch_digest: str,
    runner_token: str,
    exit_code: int,
    workspace_changed: bool = False,
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

    revision = int(verification.get("mutation_revision", 0))
    verification["runner_token_digest"] = ""
    verification["started_at"] = 0
    verification["last_exit_code"] = exit_code
    verification["workspace_changed"] = workspace_changed
    if workspace_changed:
        revision += 1
        verification["mutation_revision"] = revision
        verification["status"] = "failed"
        verification["failed_revision"] = revision
        verification["unchanged_failure_retries"] = 1
        state["observations"] = _fresh_observation_state()
    elif exit_code == 0:
        verification["status"] = "passed"
        verification["verified_revision"] = revision
        verification["failed_revision"] = -1
        verification["unchanged_failure_retries"] = 0
        verification["locked_batch_digest"] = batch_digest
    else:
        verification["status"] = "failed"
        verification["failed_revision"] = revision
    state["verification"] = verification
    state["updated_at"] = int(time.time())
    _write_json(path, state)
    return True


def _record_observation_result(
    path: Path,
    command_digest: str,
    runner_token: str,
    exit_code: int,
    output_bytes: int,
    incomplete: bool,
) -> bool:
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

    entry["runner_token_digest"] = ""
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


def _copy_limited_output(handle: Any, target: Any, remaining: int) -> int:
    copied = 0
    while copied < remaining:
        chunk = handle.read(min(16_384, remaining - copied))
        if not chunk:
            break
        target.write(chunk)
        target.flush()
        copied += len(chunk)
    return copied


def _decode_encoded_request(encoded: str, label: str) -> tuple[str, str]:
    try:
        return base64.urlsafe_b64decode(encoded.encode()).decode(), ""
    except (ValueError, UnicodeDecodeError):
        return "", f"Click {label} runner received an invalid request."


def _execute_argv_commands(
    commands: list[list[str]], stdout_file: Any | None = None, stderr_file: Any | None = None
) -> int:
    exit_code = 0
    for argv in commands:
        try:
            result = subprocess.run(
                argv,
                stdout=stdout_file,
                stderr=stderr_file,
                check=False,
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


def _execute_inspection_commands(
    commands: list[list[str]], stdout_file: Any | None = None, stderr_file: Any | None = None
) -> int:
    for argv in commands:
        native_result = _execute_native_get_content(argv, stdout_file, stderr_file)
        if native_result is not None:
            if native_result != 0:
                return native_result
            continue
        exit_code = _execute_argv_commands([argv], stdout_file, stderr_file)
        if exit_code != 0:
            return exit_code
    return 0


def _run_inspection_request(
    request: dict[str, Any], state_result: tuple[Path, str, str] | None = None
) -> int:
    commands = request["commands"]
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
    request, _, error = _validate_inspection_request(raw)
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    assert request is not None
    if _capability_digest(request) != request_digest:
        sys.stderr.write("Click observation runner request digest did not match.\n")
        return 2
    return _run_inspection_request(
        request, (state_path, request_digest, runner_token)
    )


def _record_mutation_result(
    path: Path, request_digest: str, runner_token: str, exit_code: int
) -> bool:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
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
    mutation.update(
        {
            "status": "passed" if exit_code == 0 else "failed",
            "runner_token_digest": "",
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
    request, error = _validate_mutation_request(raw)
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    assert request is not None
    if _capability_digest(request) != request_digest:
        sys.stderr.write("Click mutation runner request digest did not match.\n")
        return 2
    exit_code = _execute_argv_commands([request["argv"]])
    with _state_lock():
        recorded = _record_mutation_result(
            state_path, request_digest, runner_token, exit_code
        )
    if not recorded:
        sys.stderr.write("Click could not record the mutation result safely.\n")
        return exit_code or 2
    return exit_code


def _git_capture(cwd: Path, arguments: list[str]) -> bytes | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
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


def _new_untracked_requires_stale(relative: str) -> bool:
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
    return any(
        parts[index : index + 2] == ["db", "migrate"]
        for index in range(max(0, len(parts) - 1))
    )


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
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        scale = str(state["verification"]["scale"])
    except (FileNotFoundError, KeyError, TypeError, json.JSONDecodeError, OSError):
        sys.stderr.write("Click verification runner could not read its approved scale.\n")
        return 2
    batch, _, error = _validate_verification_batch(raw, scale)
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    assert batch is not None
    if _capability_digest(batch) != batch_digest:
        sys.stderr.write("Click verification runner batch digest did not match.\n")
        return 2
    checks = batch["checks"]
    before = _git_workspace_snapshot(Path.cwd())

    exit_code = 0
    for index, check in enumerate(checks, start=1):
        argv = check["argv"]
        rendered = subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)
        print(
            f"[Click verification {index}/{len(checks)}:{check['class']}] {rendered}",
            flush=True,
        )
        exit_code = _execute_argv_commands([argv])
        if exit_code != 0:
            break

    workspace_changed = False
    if before is not None:
        after = _git_workspace_snapshot(
            Path.cwd(), list(before["protected_untracked"])
        )
        new_untracked: list[str] = []
        if after is not None:
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
            path for path in new_untracked if _new_untracked_requires_stale(path)
        ]
        workspace_changed = (
            after is None
            or after["digest"] != before["digest"]
            or bool(suspicious_new)
        )
        if workspace_changed:
            if suspicious_new:
                sys.stderr.write(
                    "[Click] New source, configuration, or migration path appeared during "
                    "verification; it is protected as an implementation mutation.\n"
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
            batch_digest,
            runner_token,
            exit_code,
            workspace_changed=workspace_changed,
        )
    if not recorded:
        sys.stderr.write("Click could not record the verification result safely.\n")
        return exit_code or 2
    return exit_code


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "run-inspection-once":
        return _run_inspection_once(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "run-observation":
        return _run_observation(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "run-mutation":
        return _run_mutation(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "run-verification":
        return _run_verification(sys.argv[2:])
    if len(sys.argv) != 2 or sys.argv[1] not in {"pre-tool", "prompt-submit"}:
        sys.stderr.write("usage: click_gate.py pre-tool|prompt-submit\n")
        return 1
    try:
        event = _read_event()
        if sys.argv[1] == "prompt-submit":
            with _state_lock():
                _handle_prompt_submit(event)
        else:
            with _state_lock():
                _handle_pre_tool(event)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"click hook error: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
