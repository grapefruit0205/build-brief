#!/usr/bin/env python3
"""Filesystem identity, persistence, and locking for Click hook state.

This module is intentionally unaware of contracts, capabilities, runners, and
evidence semantics.  It is the lowest-level storage boundary shared by the
Codex and Antigravity adapters.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Iterator


STATE_LOCK_TIMEOUT_SECONDS = 5
STATE_LOCK_STALE_SECONDS = 30


def state_root() -> Path:
    configured = os.environ.get("PLUGIN_DATA")
    if configured:
        return Path(configured) / "gate-state"
    return Path(tempfile.gettempdir()) / "click-plugin-data" / "gate-state"


def preference_path() -> Path:
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


def identity_path(event: dict[str, Any], scope: str) -> Path:
    identity = {
        "session_id": str(event.get("session_id", "")),
        "cwd": str(event.get("cwd", "")),
    }
    if scope in {"turn", "review"}:
        identity["turn_id"] = str(event.get("turn_id", ""))
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    name = f"{scope}-{hashlib.sha256(encoded).hexdigest()}.json"
    return state_root() / name


def state_path(event: dict[str, Any]) -> Path:
    return identity_path(event, "turn")


def mode_path(event: dict[str, Any]) -> Path:
    return identity_path(event, "session")


def contract_path(event: dict[str, Any]) -> Path:
    return identity_path(event, "session-contract")


def prompt_path(event: dict[str, Any]) -> Path:
    return identity_path(event, "session-prompt")


def review_path(event: dict[str, Any]) -> Path:
    return identity_path(event, "review")


def managed_state_path(path: Path, prefixes: tuple[str, ...]) -> bool:
    """Return whether *path* is one canonical managed state file."""
    try:
        if not path.is_absolute():
            return False
        resolved_path = path.resolve(strict=True)
        lexical_path = Path(os.path.abspath(path))
        resolved_root = state_root().resolve(strict=True)
        return (
            lexical_path == resolved_path
            and resolved_path.parent == resolved_root
            and resolved_path.name.startswith(prefixes)
            and resolved_path.suffix == ".json"
        )
    except (OSError, RuntimeError):
        return False


def write_json(path: Path, payload: dict[str, Any]) -> None:
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
def state_lock() -> Iterator[None]:
    root = state_root()
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
        except (FileExistsError, PermissionError) as exc:
            # Windows can report an O_EXCL collision as EACCES while another
            # process still owns the lock file. Treat that specific shape as
            # contention and retry instead of failing the observation runner.
            if (
                isinstance(exc, PermissionError)
                and os.name != "nt"
                and not lock_path.exists()
            ):
                raise
            try:
                stale = time.time() - lock_path.stat().st_mtime > STATE_LOCK_STALE_SECONDS
            except OSError:
                stale = False
            if stale:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                else:
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
