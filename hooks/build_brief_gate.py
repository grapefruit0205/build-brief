#!/usr/bin/env python3
"""A small, local mutation-order guard for the Build Brief plugin.

The hook does not judge architecture quality or decide when the Skill should
activate. It is fail-open until an explicitly invoked Build Brief Skill arms
the current turn, or until the user explicitly enables strict mode.
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
STRING_FIELDS = ("plain_language", "boundary")
LIST_FIELDS = (
    "invariants",
    "system_semantics",
    "implementation",
    "phases",
    "steps",
    "tasks",
    "plan",
    "execution_order",
    "minimality",
    "proof",
)
CONTRACT_FIELDS = set(STRING_FIELDS) | set(LIST_FIELDS)
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


def _write_contract_state(event: dict[str, Any], status: str, digest: str) -> None:
    _write_json(
        _contract_path(event),
        {
            "status": status,
            "contract_digest": digest,
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
            "Execution Contract is too large; keep it proportional and under 8,000 characters.",
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

    for field in LIST_FIELDS:
        items = value.get(field)
        if not isinstance(items, list) or not items:
            return None, f"Execution Contract field `{field}` must be a non-empty list."
        if any(not isinstance(item, str) or not item.strip() for item in items):
            return None, f"Every `{field}` item must be a non-empty string."

    return value, ""


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
    if len(tokens) == 3 and tokens[1] in {"stage", "pass"}:
        return tokens[1], tokens[2], ""
    return (
        "",
        "",
        f"Use `{CONTROL_COMMAND} arm`, `{CONTROL_COMMAND} stage '<Execution Contract "
        f"JSON>'`, `{CONTROL_COMMAND} pass '<Execution Contract JSON>'`, "
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
                _allow_rewritten("echo Build Brief mutation gate armed")
                return
            if action == "bypass":
                _prune_state()
                _write_state(event, "bypassed")
                _clear_contract_state(event)
                _allow_rewritten("echo Build Brief bypassed for this turn")
                return
            if action == "mode":
                _prune_state()
                _write_mode(event, value)
                if value == "adaptive":
                    _write_state(event, "idle")
                _allow_rewritten(f"echo Build Brief mode set to {value}")
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
                            "Arm Build Brief before staging the execution contract for approval."
                        )
                        return
                    _write_contract_state(event, "staged", digest)
                    _write_state(event, "staged", digest)
                    _allow_rewritten("echo Build Brief execution contract staged")
                    return

                if current_status != "armed" and not strict:
                    _deny(
                        "Arm Build Brief in the current turn before passing the approved "
                        "execution contract."
                    )
                    return
                staged = _read_contract_state(event)
                if staged.get("status") not in {"staged", "approved"}:
                    _deny(
                        "No staged Build Brief execution contract is available for approval."
                    )
                    return
                if staged.get("contract_digest") != digest:
                    _deny(
                        "The execution contract differs from the version staged for user "
                        "approval. Stage the revision, show both views again, and obtain "
                        "approval before implementation."
                    )
                    return
                _write_contract_state(event, "approved", digest)
                _write_state(event, "passed", digest)
                _allow_rewritten("echo Build Brief mutation gate passed")
                return

    if tool_name == "Bash" and _is_read_only_bash(str(command)):
        return

    status = _read_state(event).get("status")
    if status in {"passed", "bypassed"}:
        return

    if status in {"armed", "staged"} or _read_mode(event) == "strict":
        _deny(
            "Build Brief blocked this mutation because the activated execution contract has "
            "not been staged, explained plainly, explicitly approved, and matched for the "
            "current turn. Complete plain_language, boundary, invariants, system_semantics, "
            "implementation, phases, steps, tasks, plan, execution_order, minimality, and proof; "
            "stage the exact JSON shown to the user, obtain approval, arm the approval turn, "
            "then pass that same JSON. If the user does not want Build Brief for this turn, run "
            "`build-brief-gate bypass`."
        )


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] != "pre-tool":
        sys.stderr.write("usage: build_brief_gate.py pre-tool\n")
        return 1
    try:
        event = _read_event()
        _handle_pre_tool(event)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"build-brief hook error: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
