#!/usr/bin/env python3
"""Shell-free operating-system process mechanics for Click runners.

This module deliberately knows nothing about contracts, capabilities, trusted
executables, Git/SSH policy, state claims, or evidence. Callers must complete
those decisions before passing an argv sequence here.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import signal
import subprocess
from typing import Any, Mapping, Sequence


_target_start = ContextVar("click_target_start", default=None)


@contextmanager
def observe_target_start(callback):
    """Observe target admission only, never collector/probe subprocesses."""
    token = _target_start.set(callback)
    try:
        yield
    finally:
        _target_start.reset(token)


def target_started() -> None:
    callback = _target_start.get()
    if callback is not None:
        try:
            callback()
        except Exception:
            pass  # Measurement cannot fail or repeat an authorized command.


def isolated_subprocess_kwargs() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def run_argv(
    argv: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    stdin: Any | None = None,
    stdout: Any | None = None,
    stderr: Any | None = None,
    timeout: float | None = None,
    target: bool = False,
) -> subprocess.CompletedProcess[Any]:
    """Run one already-authorized argv without a shell in an isolated group."""
    command = list(argv)
    child = spawn_argv(
        command,
        cwd=cwd,
        env=env,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )
    if target:
        target_started()
    try:
        captured_stdout, captured_stderr = child.communicate(timeout=timeout)
    except BaseException:
        terminate_process_group(child)
        raise
    return subprocess.CompletedProcess(
        command,
        int(child.returncode),
        captured_stdout,
        captured_stderr,
    )


def spawn_argv(
    argv: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    stdin: Any | None = None,
    stdout: Any | None = None,
    stderr: Any | None = None,
    close_fds: bool = True,
) -> subprocess.Popen[Any]:
    """Spawn one already-authorized argv without a shell in an isolated group."""
    return subprocess.Popen(
        list(argv),
        cwd=cwd,
        env=env,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        close_fds=close_fds,
        shell=False,
        **isolated_subprocess_kwargs(),
    )


def terminate_process_group(
    child: subprocess.Popen[Any], *, grace_seconds: float = 3.0
) -> int:
    """Stop an isolated child group, escalating once when graceful stop fails."""
    if child.poll() is not None:
        return int(child.returncode or 0)
    try:
        if os.name == "nt":
            ctrl_break = getattr(signal, "CTRL_BREAK_EVENT", None)
            if ctrl_break is not None:
                child.send_signal(ctrl_break)
            else:
                child.terminate()
        else:
            os.killpg(child.pid, signal.SIGTERM)
        return int(child.wait(timeout=grace_seconds))
    except (OSError, subprocess.TimeoutExpired):
        try:
            if os.name == "nt":
                child.kill()
            else:
                os.killpg(child.pid, signal.SIGKILL)
            return int(child.wait(timeout=grace_seconds))
        except (OSError, subprocess.TimeoutExpired):
            return 1


def copy_limited_output(
    source: Any,
    target: Any,
    remaining: int,
    *,
    chunk_size: int = 16_384,
) -> int:
    """Copy at most *remaining* bytes and return the number actually copied."""
    copied = 0
    while copied < remaining:
        chunk = source.read(min(chunk_size, remaining - copied))
        if not chunk:
            break
        target.write(chunk)
        target.flush()
        copied += len(chunk)
    return copied
