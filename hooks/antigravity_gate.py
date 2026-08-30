#!/usr/bin/env python3
"""Google Antigravity adapter and capability launcher for Click.

Antigravity and Codex expose different Hook payloads. This adapter normalizes
Antigravity lifecycle events into Click's canonical event shape while keeping
the contract state machine and shell-free runners in ``click_gate.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any, Callable

if __package__:
    from . import click_gate, click_state
    from .platform_protocol import AntigravityOutputAdapter, CodexOutputAdapter
else:  # Executed directly from the bundled hooks directory.
    import click_gate
    import click_state
    from platform_protocol import AntigravityOutputAdapter, CodexOutputAdapter


ANTIGRAVITY_TOOL_MAP = {
    "run_command": "Bash",
    "write_to_file": "Write",
    "replace_file_content": "Edit",
    "multi_replace_file_content": "Edit",
    "update_plan": "update_plan",
    "create_plan": "update_plan",
}
ANTIGRAVITY_MUTATION_TOOLS = {
    "run_command",
    "write_to_file",
    "replace_file_content",
    "multi_replace_file_content",
    "update_plan",
    "create_plan",
}
MAX_TRANSCRIPT_BYTES = 1_000_000


def _configure_storage() -> None:
    root = Path.home() / ".gemini" / "click"
    os.environ.setdefault("PLUGIN_DATA", str(root / "plugin-data"))
    os.environ.setdefault("CLICK_CONFIG_HOME", str(root / "config"))


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _read_raw_event() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid Antigravity hook input: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Antigravity hook input must be a JSON object")
    return value


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Antigravity requires a non-empty {label}")
    return value.strip()


def _conversation_id(raw: dict[str, Any]) -> str:
    return _required_string(raw.get("conversationId"), "conversationId")


def _workspace(raw: dict[str, Any]) -> str:
    values = raw.get("workspacePaths")
    if not isinstance(values, list):
        raise ValueError("Antigravity workspacePaths must be an array")
    for value in values:
        if isinstance(value, str) and value.strip():
            return str(Path(value).expanduser().resolve())
    raise ValueError("Antigravity requires at least one workspace path")


def _context_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _lifecycle_path(conversation_id: str) -> Path:
    return click_state.state_root() / (
        f"antigravity-lifecycle-{_context_digest(conversation_id)}.json"
    )


def _workspace_context_path(workspace: str) -> Path:
    normalized = str(Path(workspace).expanduser().resolve())
    return click_state.state_root() / (
        f"antigravity-workspace-{_context_digest(normalized)}.json"
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [_content_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("text", "content", "message", "value"):
            text = _content_text(value.get(key))
            if text:
                return text
    return ""


def _user_message(value: Any) -> str:
    if isinstance(value, list):
        for item in reversed(value):
            found = _user_message(item)
            if found:
                return found
        return ""
    if not isinstance(value, dict):
        return ""
    direct = value.get("userMessage")
    if isinstance(direct, str) and direct.strip():
        return direct
    marker = " ".join(
        str(value.get(key, "")).lower()
        for key in ("role", "author", "type", "kind", "source")
    )
    if "user" in marker or "human" in marker:
        for key in ("content", "text", "message", "value", "parts"):
            text = _content_text(value.get(key))
            if text.strip():
                return text
    for item in reversed(list(value.values())):
        found = _user_message(item)
        if found:
            return found
    return ""


def _latest_user_prompt(transcript_path: Any) -> tuple[str, str]:
    if not isinstance(transcript_path, str) or not transcript_path:
        return "", ""
    path = Path(transcript_path).expanduser()
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - MAX_TRANSCRIPT_BYTES))
            data = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return "", ""
    lines = data.splitlines()
    for index, line in reversed(list(enumerate(lines))):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        found = _user_message(value)
        if found:
            fingerprint = hashlib.sha256(
                f"{size}:{index}:".encode() + line.encode()
            ).hexdigest()
            return found, fingerprint
    return "", ""


def _canonical_event(context: dict[str, Any], *, prompt: str = "") -> dict[str, Any]:
    return {
        "platform": "antigravity",
        "session_id": f"antigravity:{context['conversation_id']}",
        "turn_id": str(context["turn_id"]),
        "cwd": str(context["workspace"]),
        "model": str(context.get("model_name", "")),
        "permission_mode": "antigravity",
        "prompt": prompt,
    }


def _capture(
    adapter: Any,
    handler: Callable[[dict[str, Any]], None],
    event: dict[str, Any],
) -> dict[str, Any]:
    outputs: list[dict[str, Any]] = []
    previous_emit = click_gate._emit
    previous_adapter = click_gate._set_output_adapter(adapter)
    click_gate._emit = outputs.append
    try:
        handler(event)
    finally:
        click_gate._emit = previous_emit
        click_gate._set_output_adapter(previous_adapter)
    return outputs[-1] if outputs else {}


def _record_pre_invocation(raw: dict[str, Any]) -> dict[str, Any]:
    conversation_id = _conversation_id(raw)
    workspace = _workspace(raw)
    lifecycle_path = _lifecycle_path(conversation_id)
    with click_state.state_lock():
        lifecycle = _read_json(lifecycle_path)
        prompt, prompt_fingerprint = _latest_user_prompt(raw.get("transcriptPath"))
        epoch = int(lifecycle.get("execution_epoch", 0))
        awaiting_next = lifecycle.get("awaiting_next_execution") is True
        if epoch < 1:
            epoch = 1
            awaiting_next = False
        elif (
            awaiting_next
            and prompt_fingerprint
            and prompt_fingerprint != lifecycle.get("prompt_fingerprint")
        ):
            epoch += 1
            awaiting_next = False
        context = {
            "conversation_id": conversation_id,
            "workspace": workspace,
            "turn_id": f"ag-execution-{epoch}",
            "model_name": str(raw.get("modelName", "")),
            "transcript_path": str(raw.get("transcriptPath", "")),
            "execution_epoch": epoch,
            "invocation_num": raw.get("invocationNum"),
            "prompt_fingerprint": prompt_fingerprint,
            "awaiting_next_execution": awaiting_next,
            "updated_at": int(time.time()),
        }
        click_state.write_json(lifecycle_path, context)
        click_state.write_json(_workspace_context_path(workspace), context)
        event = _canonical_event(context, prompt=prompt)
        payload = _capture(
            AntigravityOutputAdapter(), click_gate._handle_prompt_submit, event
        )
        steps = payload.get("injectSteps") if isinstance(payload, dict) else None
        if isinstance(steps, list) and steps and isinstance(steps[0], dict):
            message = str(steps[0].get("ephemeralMessage", ""))
            steps[0]["ephemeralMessage"] = (
                "Use this exact absolute Click control launcher for this installation: `"
                f"{_control_launcher_command()}`. "
                + message
            )
        return payload


def _context_for_raw(raw: dict[str, Any]) -> dict[str, Any]:
    return _read_json(_lifecycle_path(_conversation_id(raw)))


def _context_for_cwd(cwd: Path) -> dict[str, Any]:
    candidate = cwd.expanduser().resolve()
    for path in (candidate, *candidate.parents):
        context = _read_json(_workspace_context_path(str(path)))
        if context:
            return context
    return {}


def _control_launcher_prefix() -> list[str]:
    interpreter = Path(sys.executable).resolve(strict=True)
    script = Path(__file__).resolve(strict=True)
    if os.name == "nt" and not all(
        click_gate._windows_launcher_path_is_safe(str(path))
        for path in (interpreter, script)
    ):
        raise ValueError(
            "Click's installed Antigravity launcher path contains shell-expansion "
            "characters and cannot be invoked safely."
        )
    return [str(interpreter), str(script), "control"]


def _control_launcher_command() -> str:
    # Antigravity documents run_command as a Bash command on every host. Keep
    # the injected form in that grammar even when the host process is Windows.
    return shlex.join(_control_launcher_prefix())


def _windows_command_argv(command: str) -> list[str]:
    import ctypes

    argument_count = ctypes.c_int()
    shell32 = ctypes.windll.shell32
    shell32.CommandLineToArgvW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_int),
    ]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    argv = shell32.CommandLineToArgvW(command, ctypes.byref(argument_count))
    if not argv:
        raise ValueError("Windows could not parse Click's runner command.")
    try:
        return [argv[index] for index in range(argument_count.value)]
    finally:
        kernel32 = ctypes.windll.kernel32
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        kernel32.LocalFree(ctypes.cast(argv, ctypes.c_void_p))


def _command_argv(command: str) -> list[str]:
    return _windows_command_argv(command) if os.name == "nt" else shlex.split(command)


def _runner_command_argv(command: str) -> list[str]:
    argv = _command_argv(command)
    if os.name == "nt" and argv[:2] == ["py", "-3"]:
        # Codex needs a shell-portable bare launcher, while Antigravity runs
        # the returned command directly without a shell. Preserve its active
        # interpreter instead of adding a separate py-launcher dependency.
        return [str(Path(sys.executable).resolve(strict=True)), *argv[2:]]
    return argv


def _antigravity_bash_tokens(command: str) -> list[str] | None:
    """Parse one expansion-free Antigravity Bash command.

    Antigravity cannot replace run_command input after a Hook allows it. The
    launcher must therefore reject shell control and expansion syntax before
    comparing argv, including operators glued to an otherwise valid argument.
    Single-quoted data stays literal; dollar/backtick expansion inside double
    quotes is deliberately outside the accepted subset.
    """
    if not command or any(character in command for character in ("\0", "\r", "\n")):
        return None

    state = "unquoted"
    escaped = False
    expandable_unquoted = set("$`!*?[]{}~#")
    for character in command:
        if state == "single":
            if character == "'":
                state = "unquoted"
            continue
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if state == "double":
            if character == '"':
                state = "unquoted"
            elif character in {"$", "`", "!"}:
                return None
            continue
        if character == "'":
            state = "single"
        elif character == '"':
            state = "double"
        elif character in expandable_unquoted:
            return None
    if escaped or state != "unquoted":
        return None

    try:
        lexer = shlex.shlex(
            command,
            posix=True,
            punctuation_chars="".join(sorted(click_gate.SHELL_CONTROL_PUNCTUATION)),
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None
    if not tokens or any(
        token and set(token).issubset(click_gate.SHELL_CONTROL_PUNCTUATION)
        for token in tokens
    ):
        return None
    return tokens


def _launcher_tokens(command: str, _cwd: str) -> list[str] | None:
    try:
        prefix = _control_launcher_prefix()
    except (OSError, ValueError):
        return None
    tokens = _antigravity_bash_tokens(command)
    if tokens is None:
        return None
    if len(tokens) <= len(prefix) or tokens[: len(prefix)] != prefix:
        return None
    return tokens


def _native_run_command_read_denial() -> dict[str, str]:
    return {
        "decision": "deny",
        "reason": (
            "Antigravity cannot safely rewrite a native run_command read into Click's "
            "trusted inspection runner. Use the exact injected control launcher with "
            "`inspect`; native file/search tools and unrelated MCP or Skill tools remain "
            "available."
        ),
    }


def _pre_tool(raw: dict[str, Any]) -> dict[str, Any]:
    tool_call = raw.get("toolCall")
    if not isinstance(tool_call, dict):
        return {"decision": "deny", "reason": "Antigravity toolCall is required."}
    tool_name = str(tool_call.get("name", ""))
    arguments = tool_call.get("args")
    if not isinstance(arguments, dict):
        arguments = {}
    context = _context_for_raw(raw)
    if not context:
        if tool_name not in ANTIGRAVITY_MUTATION_TOOLS:
            return {"decision": "allow"}
        command = str(arguments.get("CommandLine", ""))
        if tool_name == "run_command" and click_gate._is_read_only_bash(command):
            return _native_run_command_read_denial()
        return {
            "decision": "deny",
            "reason": "Click has no current Antigravity PreInvocation context.",
        }

    event = _canonical_event(context)
    event.update(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": ANTIGRAVITY_TOOL_MAP.get(tool_name, tool_name),
            "tool_use_id": f"ag:{raw.get('stepIdx', '')}:{tool_name}",
            "tool_input": arguments,
        }
    )
    if tool_name == "run_command":
        command = str(arguments.get("CommandLine", ""))
        event["tool_input"] = {"command": command}
        if _launcher_tokens(command, str(context["workspace"])) is not None:
            return {"decision": "allow"}
        if click_gate._is_read_only_bash(command):
            return _native_run_command_read_denial()
    with click_state.state_lock():
        payload = _capture(
            AntigravityOutputAdapter(), click_gate._handle_pre_tool, event
        )
    return payload or {"decision": "allow"}


def _post_tool(raw: dict[str, Any]) -> dict[str, Any]:
    # Antigravity's documented PostToolUse payload exposes errors but not tool
    # results, and no Browser tool is currently bound to Click evidence.
    return {}


def _stop(raw: dict[str, Any]) -> dict[str, Any]:
    context = _context_for_raw(raw)
    if context:
        with click_state.state_lock():
            _capture(
                AntigravityOutputAdapter(),
                click_gate._handle_session_end,
                _canonical_event(context),
            )
            if (
                raw.get("fullyIdle") is True
                and raw.get("terminationReason") == "model_stop"
            ):
                context["awaiting_next_execution"] = True
                context["last_stop_execution_num"] = raw.get("executionNum")
                context["updated_at"] = int(time.time())
                click_state.write_json(
                    _lifecycle_path(str(context["conversation_id"])), context
                )
                click_state.write_json(
                    _workspace_context_path(str(context["workspace"])), context
                )
    return {"decision": "allow"}


def _control(arguments: list[str]) -> int:
    if not arguments:
        sys.stderr.write("usage: antigravity_gate.py control <click action> [value]\n")
        return 2
    context = _context_for_cwd(Path.cwd())
    if not context:
        sys.stderr.write(
            "Click has no Antigravity PreInvocation context for this workspace.\n"
        )
        return 2
    event = _canonical_event(context)
    event.update(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_use_id": f"ag-control:{time.time_ns()}",
            "tool_input": {"command": shlex.join(["click-gate", *arguments])},
        }
    )
    with click_state.state_lock():
        payload = _capture(CodexOutputAdapter(), click_gate._handle_pre_tool, event)
    output = payload.get("hookSpecificOutput") if isinstance(payload, dict) else None
    if not isinstance(output, dict):
        return 0
    if output.get("permissionDecision") == "deny":
        sys.stderr.write(str(output.get("permissionDecisionReason", "Click denied")) + "\n")
        return 2
    updated = output.get("updatedInput")
    command = updated.get("command") if isinstance(updated, dict) else None
    if not isinstance(command, str) or not command:
        return 0
    try:
        argv = _runner_command_argv(command)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"Click produced an invalid runner command: {exc}\n")
        return 2
    try:
        completed = subprocess.run(argv, cwd=Path.cwd(), check=False)
    except OSError as exc:
        sys.stderr.write(f"Click could not start its structured runner: {exc}\n")
        return 2
    return int(completed.returncode)


def main() -> int:
    _configure_storage()
    if len(sys.argv) >= 2 and sys.argv[1] == "control":
        return _control(sys.argv[2:])
    if len(sys.argv) != 2 or sys.argv[1] not in {
        "pre-invocation",
        "pre-tool",
        "post-tool",
        "stop",
    }:
        sys.stderr.write(
            "usage: antigravity_gate.py "
            "pre-invocation|pre-tool|post-tool|stop|control ...\n"
        )
        return 2
    try:
        raw = _read_raw_event()
        if sys.argv[1] == "pre-invocation":
            payload = _record_pre_invocation(raw)
        elif sys.argv[1] == "pre-tool":
            payload = _pre_tool(raw)
        elif sys.argv[1] == "post-tool":
            payload = _post_tool(raw)
        else:
            payload = _stop(raw)
    except (OSError, ValueError) as exc:
        if sys.argv[1] == "pre-tool":
            payload = {"decision": "deny", "reason": f"Click adapter error: {exc}"}
        elif sys.argv[1] == "stop":
            payload = {"decision": "allow"}
        else:
            payload = {
                "injectSteps": [
                    {"ephemeralMessage": f"Click adapter error: {exc}"}
                ]
            }
    _emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
