#!/usr/bin/env python3
"""Codex Hook entrypoint that normalizes equivalent tool names for Click.

Codex clients do not always expose shell execution under the historical `Bash`
name. This adapter maps direct shell/exec surfaces onto Click's canonical Bash
path while leaving the core contract state machine unchanged.
"""

from __future__ import annotations

import io
import json
import sys
from typing import Any

if __package__:
    from . import click_gate, click_host_coverage
else:
    import click_gate
    import click_host_coverage


DIRECT_EXEC_TOOL_NAMES = click_host_coverage.CODEX_DIRECT_EXEC_TOOL_NAMES

# Current Codex Code Mode may not emit Hook events at all for this surface.
# When an event is available, map it onto the conservative command path so an
# active Click workflow fails closed instead of silently bypassing the gate.
CODE_MODE_TOOL_NAMES = click_host_coverage.CODEX_CODE_MODE_TOOL_NAMES


def normalize_event(event: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode != "pre-tool":
        return event
    tool_name = str(event.get("tool_name", ""))
    if tool_name not in DIRECT_EXEC_TOOL_NAMES | CODE_MODE_TOOL_NAMES:
        return event
    normalized = dict(event)
    normalized["tool_name"] = click_host_coverage.CODEX_TOOL_MAP[tool_name]
    return normalized


def route_stdin_event(mode: str) -> None:
    if mode not in {"pre-tool", "post-tool", "prompt-submit", "session-end"}:
        return
    raw = sys.stdin.read()
    if not raw:
        sys.stdin = io.StringIO(raw)
        return
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.stdin = io.StringIO(raw)
        return
    if isinstance(event, dict):
        event = normalize_event(event, mode)
        raw = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    sys.stdin = io.StringIO(raw)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    route_stdin_event(mode)
    return click_gate.main()


if __name__ == "__main__":
    raise SystemExit(main())
