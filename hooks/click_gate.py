#!/usr/bin/env python3
"""A small, local contract, mutation-order, and verification-budget guard.

The hook does not judge architecture quality, implementation choices, or Skill
activation. It is fail-open until an explicitly invoked Click Skill arms the
current turn, or until the user explicitly enables strict mode. After an
approved contract, it also meters one final verification batch.
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
VERIFICATION_BATCH_FIELDS = {"commands"}
MAX_CONTRACT_CHARS = 4_000
MAX_VERIFICATION_BATCH_CHARS = 6_000
VERIFY_RUNNING_TTL_SECONDS = 60 * 60
STATE_TTL_SECONDS = 7 * 24 * 60 * 60

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
EXPENSIVE_VERIFICATION_PATTERN = re.compile(
    r"(?:^|[\s/_.:-])(?:audit|bandit|bench(?:mark)?|coverage|cypress|e2e|k6|"
    r"locust|playwright|security|semgrep|snyk|trivy)(?:$|[\s/_.:-])",
    re.IGNORECASE,
)
BROAD_VERIFICATION_PATTERNS = (
    re.compile(r"\bunittest\s+discover\b", re.IGNORECASE),
    re.compile(r"\bgo\s+test\s+\./\.\.\.(?:\s|$)", re.IGNORECASE),
    re.compile(r"\bcargo\s+(?:test|nextest)(?:\s|$).*(?:--workspace|--all)", re.IGNORECASE),
    re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?test\s*$", re.IGNORECASE),
    re.compile(r"\b(?:mvnw?|gradlew?|dotnet)\s+(?:test|check|verify)\s*$", re.IGNORECASE),
)

READ_ONLY_COMMANDS = {
    "basename",
    "cmp",
    "cut",
    "diff",
    "dirname",
    "du",
    "file",
    "find",
    "grep",
    "get-childitem",
    "get-command",
    "get-content",
    "get-item",
    "get-location",
    "head",
    "ls",
    "measure-object",
    "pwd",
    "readlink",
    "realpath",
    "resolve-path",
    "rg",
    "select-string",
    "sed",
    "sort",
    "stat",
    "tail",
    "test",
    "test-path",
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


def _identity_path(event: dict[str, Any], scope: str) -> Path:
    identity = {
        "session_id": str(event.get("session_id", "")),
        "cwd": str(event.get("cwd", "")),
    }
    if scope == "turn":
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
        "started_at": 0,
    }


def _write_contract_state(
    event: dict[str, Any], status: str, digest: str, contract: dict[str, Any]
) -> None:
    _write_json(
        _contract_path(event),
        {
            "status": status,
            "contract_digest": digest,
            "verification": _fresh_verification_state(contract),
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


def _mark_contract_mutated(event: dict[str, Any]) -> str:
    state = _read_contract_state(event)
    if state.get("status") != "approved":
        return ""
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return "Click verification state is unavailable; stage and approve the contract again."
    if verification.get("status") == "running":
        return "Click blocked this mutation while the final verification batch is running."

    verification["mutation_revision"] = int(
        verification.get("mutation_revision", 0)
    ) + 1
    if verification.get("status") == "passed":
        verification["status"] = "stale"
    elif verification.get("status") == "failed":
        verification["status"] = "ready"
        verification["failed_revision"] = -1
        verification["unchanged_failure_retries"] = 0
    state["verification"] = verification
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


def _verification_cost(command: str) -> tuple[int, str]:
    if not command.strip():
        return 0, "Verification commands must be non-empty strings."
    segments = _shell_segments(command)
    if segments is None or len(segments) != 1:
        return (
            0,
            "Each verification entry must be one shell command without chaining, pipes, "
            "redirection, background execution, command substitution, or newlines.",
        )
    normalized = " ".join(segments[0])
    if EXPENSIVE_VERIFICATION_PATTERN.search(normalized):
        return 5, ""
    if any(pattern.search(normalized) for pattern in BROAD_VERIFICATION_PATTERNS):
        return 3, ""
    executable, arguments = _command_parts(segments[0])
    if executable in {"pytest", "cargo"}:
        if executable == "pytest" and not _has_positional_target(arguments):
            return 3, ""
        if executable == "cargo" and arguments[:1] in (["test"], ["nextest"]):
            if len(arguments) == 1:
                return 3, ""
    if executable in {"npm", "pnpm", "yarn", "bun"}:
        meaningful = [item for item in arguments if item not in {"run", "exec", "x"}]
        if meaningful and meaningful[0] == "test":
            return 3, ""
    if executable in {"dotnet", "gradle", "gradlew", "gradlew.bat", "mvn", "mvnw", "mvnw.cmd"}:
        if any(argument in {"test", "check", "verify"} for argument in arguments):
            return 3, ""
    return 1, ""


def _validate_verification_batch(
    raw: str, scale: str
) -> tuple[dict[str, Any] | None, int, str]:
    if len(raw) > MAX_VERIFICATION_BATCH_CHARS:
        return None, 0, "Verification batch must stay under 6,000 characters."
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None, 0, "Verification batch must be valid JSON."
    if not isinstance(value, dict):
        return None, 0, "Verification batch must be a JSON object."
    unknown = sorted(set(value) - VERIFICATION_BATCH_FIELDS)
    if unknown:
        rendered = ", ".join(f"`{field}`" for field in unknown)
        return None, 0, f"Verification batch contains unsupported field(s): {rendered}."
    commands = value.get("commands")
    if not isinstance(commands, list) or not commands:
        return None, 0, "Verification batch `commands` must be a non-empty list."
    if any(not isinstance(command, str) or not command.strip() for command in commands):
        return None, 0, "Every verification command must be a non-empty string."

    units = 0
    for command in commands:
        cost, error = _verification_cost(command)
        if error:
            return None, 0, error
        units += cost
    limit = VERIFICATION_UNIT_LIMITS[scale]
    if units > limit:
        return (
            None,
            units,
            f"The {scale} verification budget allows {limit} unit(s), but this batch "
            f"costs {units}. Remove lower-value checks instead of expanding verification.",
        )
    return {"commands": commands}, units, ""


def _control_request(command: str) -> tuple[str | None, str, str]:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        return None, "", f"Malformed {CONTROL_COMMAND} command: {exc}."
    if not tokens or tokens[0] != CONTROL_COMMAND:
        return None, "", ""
    if len(tokens) == 2 and tokens[1] in {"arm", "bypass"}:
        return tokens[1], "", ""
    if len(tokens) == 3 and tokens[1] == "mode" and tokens[2] in {
        "adaptive",
        "strict",
    }:
        return "mode", tokens[2], ""
    if len(tokens) == 3 and tokens[1] in {"stage", "pass", "verify"}:
        return tokens[1], tokens[2], ""
    return (
        "",
        "",
        f"Use `{CONTROL_COMMAND} arm`, `{CONTROL_COMMAND} stage '<Execution Contract "
        f"JSON>'`, `{CONTROL_COMMAND} pass '<Execution Contract JSON>'`, "
        f"`{CONTROL_COMMAND} verify '<Verification Batch JSON>'`, "
        f"`{CONTROL_COMMAND} bypass`, or `{CONTROL_COMMAND} mode adaptive|strict`.",
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
    return Path(remaining[0]).name.lower(), [item.lower() for item in remaining[1:]]


def _has_positional_target(arguments: list[str]) -> bool:
    return any(not argument.startswith("-") for argument in arguments)


def _is_recognized_verification_tokens(tokens: list[str]) -> bool:
    executable, arguments = _command_parts(tokens)
    if not executable:
        return False
    if executable in VERIFICATION_EXECUTABLES:
        return True
    if executable in {"python", "python3", "py", "pypy", "pypy3"}:
        if len(arguments) >= 2 and arguments[0] == "-m":
            return arguments[1] in {
                "coverage",
                "pytest",
                "unittest",
            }
        script = next((item for item in arguments if not item.startswith("-")), "")
        stem = Path(script).stem.lower()
        return any(marker in stem for marker in VERIFICATION_NAME_MARKERS)
    if executable in {"bash", "sh", "zsh", "pwsh", "powershell", "powershell.exe"}:
        script = next((item for item in arguments if not item.startswith("-")), "")
        stem = Path(script).stem.lower()
        return any(marker in stem for marker in VERIFICATION_NAME_MARKERS)
    if executable in {"npm", "pnpm", "yarn", "bun"}:
        meaningful = [item for item in arguments if item not in {"run", "exec", "x"}]
        target = meaningful[0] if meaningful else ""
        return any(marker in target for marker in VERIFICATION_NAME_MARKERS)
    if executable in {"npx", "pnpx", "bunx"}:
        target = arguments[0] if arguments else ""
        return any(marker in target for marker in VERIFICATION_NAME_MARKERS)
    if executable == "cargo":
        return bool(arguments) and arguments[0] in {"audit", "bench", "nextest", "test"}
    if executable == "go":
        return bool(arguments) and arguments[0] == "test"
    if executable in {"dotnet", "gradle", "gradlew", "gradlew.bat", "mvn", "mvnw", "mvnw.cmd"}:
        return any(
            any(marker in argument for marker in VERIFICATION_NAME_MARKERS)
            for argument in arguments
        )
    if executable in {"make", "gmake", "cmake", "ctest", "pre-commit"}:
        return executable in {"ctest", "pre-commit"} or any(
            any(marker in argument for marker in VERIFICATION_NAME_MARKERS)
            for argument in arguments
        )
    stem = Path(executable).stem.lower()
    return any(marker in stem for marker in VERIFICATION_NAME_MARKERS)


def _is_recognized_verification_command(command: str) -> bool:
    segments = _shell_segments(command)
    if segments:
        return any(_is_recognized_verification_tokens(segment) for segment in segments)
    try:
        fallback = shlex.split(command, posix=True)
    except ValueError:
        return False
    return _is_recognized_verification_tokens(fallback)


def _is_broad_verification_command(command: str) -> bool:
    cost, error = _verification_cost(command)
    return bool(error) or cost >= 3


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
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return "", "Click verification state is unavailable; stage and approve again."
    scale = str(verification.get("scale", ""))
    if scale not in VERIFICATION_UNIT_LIMITS:
        return "", "Approved Click verification scale is invalid; stage and approve again."

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


def _is_read_only_tokens(tokens: list[str]) -> bool:
    if not tokens:
        return False
    while tokens and "=" in tokens[0] and not tokens[0].startswith(("=", "-")):
        name, _, _ = tokens[0].partition("=")
        if not name.replace("_", "a").isalnum():
            break
        tokens.pop(0)
    if not tokens:
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
    if not command.strip():
        return False
    segments = _shell_segments(command)
    return segments is not None and all(_is_read_only_tokens(segment) for segment in segments)


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
                _write_state(event, "armed")
                _allow_rewritten("echo Click mutation gate armed")
                return
            if action == "bypass":
                _prune_state()
                _write_state(event, "bypassed")
                _clear_contract_state(event)
                _allow_rewritten("echo Click bypassed for this turn")
                return
            if action == "mode":
                _prune_state()
                _write_mode(event, value)
                if value == "adaptive":
                    _write_state(event, "idle")
                _allow_rewritten(f"echo Click mode set to {value}")
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
                if action == "stage":
                    if current_status not in {"armed", "staged", "passed"} and not strict:
                        _deny(
                            "Arm Click before staging the execution contract for approval."
                        )
                        return
                    existing_contract = _read_contract_state(event)
                    if (
                        existing_contract.get("status") == "approved"
                        and existing_contract.get("contract_digest") != digest
                    ):
                        _deny(
                            "Click is already executing one approved contract. Keep working "
                            "inside that contract instead of replacing it mid-run. If the "
                            "approved outcome or authority is no longer sufficient, stop and "
                            "report the blocker."
                        )
                        return
                    _write_contract_state(event, "staged", digest, contract)
                    _write_state(event, "staged", digest)
                    _allow_rewritten("echo Click execution contract staged")
                    return

                if current_status != "armed" and not strict:
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
                if staged.get("contract_digest") != digest:
                    _deny(
                        "The execution contract differs from the version staged for user "
                        "approval. Pass the exact staged contract, or replace it before "
                        "approval and show the complete contract again."
                    )
                    return
                staged["status"] = "approved"
                staged["contract_digest"] = digest
                _save_contract_state(event, staged)
                _write_state(event, "passed", digest)
                _allow_rewritten("echo Click mutation gate passed")
                return

    if tool_name == "Bash" and _is_read_only_bash(str(command)):
        return

    status = _read_state(event).get("status")
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
            if tool_name == "Bash" and _is_recognized_verification_command(str(command)):
                if verification_status == "passed":
                    _deny(
                        "The approved final verification already passed. Click blocks "
                        "additional verification until an in-scope mutation makes it stale."
                    )
                    return
                if _is_broad_verification_command(str(command)):
                    _deny(
                        "Run broad, full-suite, security, coverage, benchmark, or end-to-end "
                        "checks through `click-gate verify '<Verification Batch JSON>'` so "
                        "the approved automatic budget can be enforced."
                    )
                    return
                return
            mutation_error = _mark_contract_mutated(event)
            if mutation_error:
                _deny(mutation_error)
        return

    if status in {"armed", "staged"} or _read_mode(event) == "strict":
        _deny(
            "Click blocked this mutation because the activated execution contract has "
            "not been staged, explained plainly, explicitly approved, and matched for the "
            "current turn. Complete outcome, boundary.in_scope, boundary.out_of_scope, "
            "must_hold, build.approach, verification.scale, verification.done_when, and "
            "plain_language; add build.semantics, build.order, or an intermediate gate only "
            "when the work materially requires them; "
            "stage the exact JSON shown to the user, obtain approval, arm the approval turn, "
            "then pass that same JSON. If the user does not want Click for this turn, run "
            "`click-gate bypass`."
        )


def _verification_shell_arguments(command: str) -> list[str]:
    if os.name == "nt":
        return [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ]
    shell = os.environ.get("SHELL", "")
    if not shell or not Path(shell).is_file():
        shell = "/bin/bash" if Path("/bin/bash").is_file() else "/bin/sh"
    return [shell, "-lc" if Path(shell).name in {"bash", "zsh", "ksh"} else "-c", command]


def _record_verification_result(
    path: Path, batch_digest: str, runner_token: str, exit_code: int
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
    if exit_code == 0:
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


def _run_verification(arguments: list[str]) -> int:
    if len(arguments) != 4:
        sys.stderr.write(
            "usage: click_gate.py run-verification <state> <digest> <token> <batch>\n"
        )
        return 2
    state_path = Path(arguments[0])
    batch_digest, runner_token, encoded = arguments[1:]
    try:
        decoded = base64.urlsafe_b64decode(encoded.encode()).decode()
        batch = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        sys.stderr.write("Click verification runner received an invalid batch.\n")
        return 2
    commands = batch.get("commands") if isinstance(batch, dict) else None
    if not isinstance(commands, list) or not commands:
        sys.stderr.write("Click verification runner received no commands.\n")
        return 2

    exit_code = 0
    for index, command in enumerate(commands, start=1):
        if not isinstance(command, str):
            exit_code = 2
            break
        print(f"[Click verification {index}/{len(commands)}] {command}", flush=True)
        try:
            result = subprocess.run(_verification_shell_arguments(command), check=False)
            exit_code = int(result.returncode)
        except OSError as exc:
            sys.stderr.write(f"Click could not start verification: {exc}\n")
            exit_code = 127
        if exit_code != 0:
            break

    if not _record_verification_result(
        state_path, batch_digest, runner_token, exit_code
    ):
        sys.stderr.write("Click could not record the verification result safely.\n")
        return exit_code or 2
    return exit_code


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "run-verification":
        return _run_verification(sys.argv[2:])
    if len(sys.argv) != 2 or sys.argv[1] != "pre-tool":
        sys.stderr.write("usage: click_gate.py pre-tool\n")
        return 1
    try:
        event = _read_event()
        _handle_pre_tool(event)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"click hook error: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
