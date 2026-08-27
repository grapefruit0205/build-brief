#!/usr/bin/env python3
"""A small, local mutation-order guard for the Build Brief plugin.

The hook does not judge architecture quality. It only requires a compact,
structured Design Contract before supported local mutation tools run.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import time
from typing import Any


CONTROL_COMMAND = "build-brief-gate"
REQUIRED_FIELDS = ("boundary", "invariants", "implementation", "proof")
MAX_CONTRACT_CHARS = 8_000
STATE_TTL_SECONDS = 7 * 24 * 60 * 60

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
    return Path(tempfile.gettempdir()) / "build-brief-plugin-data" / "gate-state"


def _state_path(event: dict[str, Any]) -> Path:
    identity = {
        "session_id": str(event.get("session_id", "")),
        "turn_id": str(event.get("turn_id", "")),
        "cwd": str(event.get("cwd", "")),
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    name = hashlib.sha256(encoded).hexdigest() + ".json"
    return _state_root() / name


def _write_state(event: dict[str, Any], status: str, contract_digest: str = "") -> None:
    path = _state_path(event)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "status": status,
        "contract_digest": contract_digest,
        "updated_at": int(time.time()),
    }
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


def _read_state(event: dict[str, Any]) -> dict[str, Any]:
    path = _state_path(event)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"status": "pending"}
    return value if isinstance(value, dict) else {"status": "pending"}


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


def _session_context() -> str:
    return (
        "Build Brief mutation policy: before the first supported local write in each turn, "
        "infer a proportional Design Contract from the request and narrow repository evidence, "
        "then run `build-brief-gate pass '<JSON>'` with non-empty `boundary`, `invariants[]`, "
        "`implementation[]`, and `proof[]`. One concise item per field is enough for a trivial "
        "edit. Read-only and non-mutating turns require no command."
    )


def _validate_contract(raw: str) -> tuple[dict[str, Any] | None, str]:
    if len(raw) > MAX_CONTRACT_CHARS:
        return (
            None,
            "Design Contract is too large; keep it proportional and under 8,000 characters.",
        )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None, "Design Contract must be valid JSON."
    if not isinstance(value, dict):
        return None, "Design Contract must be a JSON object."

    boundary = value.get("boundary")
    if not isinstance(boundary, str) or not boundary.strip():
        return None, "Design Contract field `boundary` must be a non-empty string."

    for field in REQUIRED_FIELDS[1:]:
        items = value.get(field)
        if not isinstance(items, list) or not items:
            return None, f"Design Contract field `{field}` must be a non-empty list."
        if any(not isinstance(item, str) or not item.strip() for item in items):
            return None, f"Every `{field}` item must be a non-empty string."

    return value, ""


def _control_payload(command: str) -> tuple[str | None, str]:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        return None, f"Malformed {CONTROL_COMMAND} command: {exc}."
    if not tokens or tokens[0] != CONTROL_COMMAND:
        return None, ""
    if len(tokens) != 3 or tokens[1] != "pass":
        return "", f"Use `{CONTROL_COMMAND} pass '<Design Contract JSON>'`."
    return tokens[2], ""


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
        if token == "&&":
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


def _handle_session() -> None:
    _prune_state()
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": _session_context(),
            }
        }
    )


def _handle_pre_tool(event: dict[str, Any]) -> None:
    tool_name = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

    if tool_name == "Bash":
        control, control_error = _control_payload(str(command))
        if control is not None:
            if control_error:
                _deny(control_error)
                return
            contract, validation_error = _validate_contract(control)
            if validation_error:
                _deny(validation_error)
                return
            assert contract is not None
            canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            _prune_state()
            _write_state(event, "passed", digest)
            _allow_rewritten("echo Build Brief mutation gate passed")
            return

    if _read_state(event).get("status") == "passed":
        return

    if tool_name == "Bash" and _is_read_only_bash(str(command)):
        return

    _deny(
        "Build Brief blocked this mutation because the proportional Design Contract has not "
        "passed for the current turn. Inspect the relevant repository context, define boundary, "
        "invariants, implementation slices, and proof, then run `build-brief-gate pass "
        "'<Design Contract JSON>'` before retrying."
    )


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"session", "pre-tool"}:
        sys.stderr.write("usage: build_brief_gate.py {session|pre-tool}\n")
        return 1
    try:
        event = _read_event()
        if sys.argv[1] == "session":
            _handle_session()
        else:
            _handle_pre_tool(event)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"build-brief hook error: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
