#!/usr/bin/env python3
"""Native macOS ``fs_usage`` backend for Shadow Observer v1.

The backend never raises privilege.  When the current process is already
privileged, it starts a PID-filtered system collector before releasing a tiny
launcher that ``exec`` replaces itself with the approved target.  Raw output
is bounded in memory and discarded after it is normalized into the existing
non-authoritative Observer v1 record.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


def _launcher_entry(arguments: list[str]) -> int:
    """Wait for one release byte, then replace this process with the target."""

    if len(arguments) < 2:
        return 126
    fifo = arguments[0]
    target = arguments[1:]
    try:
        descriptor = os.open(fifo, os.O_RDONLY)
        try:
            released = os.read(descriptor, 1)
        finally:
            os.close(descriptor)
        if released != b"1":
            return 126
        os.execvpe(target[0], target, dict(os.environ))
    except (OSError, ValueError):
        return 127
    return 127


# The synchronized launcher must work under ``python -I -S -B`` without
# importing repository or plugin modules before it waits for the collector.
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--launch":
    raise SystemExit(_launcher_entry(sys.argv[2:]))


from collections.abc import Callable, Mapping, Sequence  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
import errno  # noqa: E402
from functools import lru_cache  # noqa: E402
import hashlib  # noqa: E402
import platform  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from typing import Any, BinaryIO  # noqa: E402

if __package__:
    from . import click_dependency_cache, click_observer_common, click_process
else:  # Executed directly from the bundled hooks directory.
    import click_dependency_cache
    import click_observer_common
    import click_process


MAX_RAW_TRACE_BYTES = 4 * 1024 * 1024
COLLECTOR_STARTUP_SECONDS = 0.2
LAUNCH_RELEASE_SECONDS = 1.0
NATIVE_FS_USAGE_PATHS = frozenset({"/usr/bin/fs_usage", "/usr/sbin/fs_usage"})

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
_EVENT = re.compile(
    r"^\s*\d{2}:\d{2}:\d{2}(?:\.\d+)?\s+"
    r"(?P<operation>\S+)\s+(?P<details>.*?)\s+"
    r"\d+\.\d+(?:\s+[A-Z]+)?\s+\S+\s*$"
)
_ABSOLUTE_PATH = re.compile(r"(?<!\S)(/(?:[^\x00\r\n])*?)\s*$")
_OPEN_FLAGS = re.compile(r"\((?P<flags>[A-Z_]{2,32})\)")
_MISSING_ERRNO = re.compile(r"\[\s*2\s*\]")

_READ_OPERATIONS = frozenset(
    {
        "open",
        "openat",
        "pread",
        "pread_nocancel",
        "read",
        "read_nocancel",
        "readv",
    }
)
_METADATA_OPERATIONS = frozenset(
    {
        "access",
        "access_extended",
        "fstat",
        "getattrlist",
        "lstat",
        "lstat64",
        "readlink",
        "stat",
        "stat64",
    }
)
_DIRECTORY_OPERATIONS = frozenset(
    {"getdirentries", "getdirentries64", "readdir"}
)
_EXEC_OPERATIONS = frozenset({"exec", "execve"})
_CHILD_OPERATIONS = frozenset({"fork", "posix_spawn", "posix_spawnp", "vfork"})
_MISSING_MARKERS = ("ENOENT", "Err#2", "No such file")

FallbackExecutor = click_observer_common.FallbackExecutor
BackendResolver = Callable[..., tuple[str | None, str]]
FileDigester = Callable[[Path], str]
NativeBackendProbe = Callable[[str], bool]
SpawnArgv = Callable[..., subprocess.Popen[Any]]
TerminateGroup = Callable[[subprocess.Popen[Any]], int]


@dataclass(frozen=True, slots=True)
class ParsedTrace:
    inputs: tuple[dict[str, Any], ...]
    external_input_count: int
    unresolved_event_count: int
    child_process_count: int
    process_tree_complete: bool
    root_exec_observed: bool


@dataclass(frozen=True, slots=True)
class CollectedExecution:
    exit_code: int
    raw: bytes
    truncated: bool
    failed: bool
    target_started: bool
    command_duration_ms: int
    collector_overhead_ms: int


@dataclass(slots=True)
class _BoundedCapture:
    limit: int
    retained: bytearray = field(default_factory=bytearray)
    truncated: bool = False
    failed: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, chunk: bytes) -> None:
        with self.lock:
            remaining = max(0, self.limit - len(self.retained))
            if remaining:
                self.retained.extend(chunk[:remaining])
            if len(chunk) > remaining:
                self.truncated = True

    def bytes(self) -> bytes:
        with self.lock:
            return bytes(self.retained)


ShadowExecution = click_observer_common.ShadowExecution
Collector = Callable[..., CollectedExecution]


def has_privilege() -> bool:
    """Return whether the process already has the privilege fs_usage needs."""

    try:
        getuid = getattr(os, "geteuid")
        return bool(getuid() == 0)
    except (AttributeError, OSError, TypeError, ValueError):
        return False


@lru_cache(maxsize=4)
def probe_macos_version() -> str:
    """Use the bounded host version as the native collector version."""

    try:
        version = platform.mac_ver()[0]
    except Exception:
        return ""
    return version if isinstance(version, str) and _VERSION.fullmatch(version) else ""


def _file_digest(path: Path) -> str:
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


def _native_fs_usage(executable: str) -> bool:
    try:
        return str(Path(executable).resolve(strict=True)) in NATIVE_FS_USAGE_PATHS
    except (OSError, RuntimeError, TypeError, ValueError):
        return False


def _bounded_add(left: int, right: int) -> int:
    return click_observer_common.bounded_add(left, right)


def _outside_workspace(workspace: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(workspace)
    except ValueError:
        return True
    return False


def _candidate_path(details: str) -> str:
    match = _ABSOLUTE_PATH.search(details)
    if match is None:
        return ""
    value = match.group(1).strip()
    if " -> " in value or "\x00" in value:
        return ""
    return value


def parse_fs_usage(
    raw: bytes,
    *,
    workspace: Path,
    truncated: bool = False,
) -> ParsedTrace:
    """Parse bounded fs_usage text into content-free repository inputs."""

    try:
        root = workspace.resolve(strict=True)
    except (OSError, RuntimeError):
        root = Path(os.path.abspath(workspace))
    inputs: dict[str, dict[str, Any]] = {}
    conflicts: set[str] = set()
    external_digests: set[str] = set()
    unresolved = 1 if truncated else 0
    child_processes = 0
    root_exec_observed = False

    def add_path(path_text: str, *, kind: str, operation: str) -> None:
        nonlocal unresolved
        try:
            candidate = Path(os.path.normpath(path_text))
            if not candidate.is_absolute():
                raise ValueError("not absolute")
        except (OSError, TypeError, ValueError):
            unresolved = _bounded_add(unresolved, 1)
            return
        if _outside_workspace(root, candidate):
            try:
                digest = hashlib.sha256(os.fsencode(candidate)).hexdigest()
            except (OSError, TypeError, UnicodeError, ValueError):
                unresolved = _bounded_add(unresolved, 1)
                return
            if digest not in external_digests:
                if (
                    len(external_digests)
                    >= click_dependency_cache.MAX_SHADOW_OBSERVER_INPUTS
                ):
                    unresolved = _bounded_add(unresolved, 1)
                else:
                    external_digests.add(digest)
            return
        try:
            relative = candidate.relative_to(root).as_posix()
        except ValueError:
            unresolved = _bounded_add(unresolved, 1)
            return
        if not relative or relative == ".":
            unresolved = _bounded_add(unresolved, 1)
            return
        if kind == "directory" and not relative.endswith("/"):
            relative += "/"
        try:
            encoded_relative = relative.encode("utf-8")
        except UnicodeEncodeError:
            unresolved = _bounded_add(unresolved, 1)
            return
        if (
            len(encoded_relative)
            > click_dependency_cache.MAX_SHADOW_OBSERVER_PATH_BYTES
            or "\\" in relative
            or any(
                ord(character) < 32 or ord(character) == 127
                for character in relative
            )
        ):
            unresolved = _bounded_add(unresolved, 1)
            return
        existing = inputs.get(relative)
        if existing is not None and existing["kind"] != kind:
            conflicts.add(relative)
            return
        if existing is None:
            if len(inputs) >= click_dependency_cache.MAX_SHADOW_OBSERVER_INPUTS:
                unresolved = _bounded_add(unresolved, 1)
                return
            existing = {"path": relative, "kind": kind, "operations": []}
            inputs[relative] = existing
        if operation not in existing["operations"]:
            existing["operations"].append(operation)

    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        text = raw.decode("utf-8", errors="replace")
        unresolved = _bounded_add(unresolved, 1)

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("TIMESTAMP", "fs_usage:")):
            continue
        match = _EVENT.match(line)
        if match is None:
            if re.match(r"^\s*\d{2}:\d{2}:\d{2}", line):
                unresolved = _bounded_add(unresolved, 1)
            continue
        operation_name = match.group("operation").rstrip("*").lower()
        details = match.group("details")
        if operation_name in _CHILD_OPERATIONS:
            child_processes = _bounded_add(child_processes, 1)
        if operation_name in _EXEC_OPERATIONS:
            root_exec_observed = True

        observed_operation = ""
        kind = "file"
        ignored_operation = False
        if any(marker in details for marker in _MISSING_MARKERS) or (
            _MISSING_ERRNO.search(details) is not None
        ):
            observed_operation = (
                "read" if operation_name in _READ_OPERATIONS else "metadata"
            )
            kind = "missing"
        elif operation_name in _DIRECTORY_OPERATIONS:
            observed_operation = "enumerate"
            kind = "directory"
        elif operation_name in _EXEC_OPERATIONS or operation_name in _CHILD_OPERATIONS:
            observed_operation = "execute"
        elif operation_name in _METADATA_OPERATIONS:
            observed_operation = "metadata"
        elif operation_name in _READ_OPERATIONS:
            flags = _OPEN_FLAGS.search(details)
            if (
                operation_name in {"open", "openat"}
                and flags is not None
                and "R" not in flags.group("flags")
            ):
                ignored_operation = True
            else:
                observed_operation = "read"

        path_text = _candidate_path(details)
        if observed_operation and path_text:
            add_path(path_text, kind=kind, operation=observed_operation)
        elif observed_operation:
            unresolved = _bounded_add(unresolved, 1)
        elif path_text and operation_name not in {
            "close",
            "fsync",
            "pwrite",
            "write",
            "write_nocancel",
        } and not ignored_operation:
            unresolved = _bounded_add(unresolved, 1)

    for relative in conflicts:
        inputs.pop(relative, None)
        unresolved = _bounded_add(unresolved, 1)
    if not root_exec_observed:
        unresolved = _bounded_add(unresolved, 1)
    normalized_inputs = tuple(
        {
            "path": item["path"],
            "kind": item["kind"],
            "operations": sorted(item["operations"]),
        }
        for _, item in sorted(inputs.items())
    )
    process_tree_complete = bool(
        root_exec_observed
        and child_processes == 0
        and unresolved == 0
        and not truncated
    )
    return ParsedTrace(
        inputs=normalized_inputs,
        external_input_count=len(external_digests),
        unresolved_event_count=unresolved,
        child_process_count=child_processes,
        process_tree_complete=process_tree_complete,
        root_exec_observed=root_exec_observed,
    )


def _create_launch_fifo(workspace: Path) -> tuple[Path, Path] | None:
    try:
        workspace_root = workspace.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    for raw_root in ("/tmp", "/var/tmp"):
        directory: Path | None = None
        fifo: Path | None = None
        try:
            temporary_root = Path(raw_root).resolve(strict=True)
            if not temporary_root.is_dir():
                continue
            if not _outside_workspace(workspace_root, temporary_root):
                continue
            directory = Path(
                tempfile.mkdtemp(prefix="click-shadow-macos-", dir=temporary_root)
            )
            if not _outside_workspace(workspace_root, directory):
                directory.rmdir()
                continue
            directory.chmod(0o700)
            fifo = directory / "launch.pipe"
            os.mkfifo(fifo, mode=0o600)
            return directory, fifo
        except OSError:
            _remove_launch_fifo(directory, fifo)
    return None


def _remove_launch_fifo(directory: Path | None, fifo: Path | None) -> None:
    if fifo is not None:
        try:
            fifo.unlink(missing_ok=True)
        except OSError:
            pass
    if directory is not None:
        try:
            directory.rmdir()
        except OSError:
            pass


def _drain_stream(stream: BinaryIO, capture: _BoundedCapture) -> None:
    try:
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                break
            capture.append(bytes(chunk))
    except (OSError, TypeError, ValueError):
        capture.failed = True
    finally:
        try:
            stream.close()
        except OSError:
            pass


def _release_target(fifo: Path, *, timeout: float = LAUNCH_RELEASE_SECONDS) -> bool:
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() <= deadline:
        try:
            descriptor = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as error:
            if error.errno not in {errno.ENXIO, errno.ENOENT}:
                return False
            time.sleep(0.01)
            continue
        try:
            return os.write(descriptor, b"1") == 1
        except OSError:
            return False
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
    return False


def collect_command(
    argv: Sequence[str],
    *,
    workspace: Path,
    environment: Mapping[str, str],
    executable: str,
    spawn_argv: SpawnArgv = click_process.spawn_argv,
    terminate_group: TerminateGroup = click_process.terminate_process_group,
    capture_limit: int = MAX_RAW_TRACE_BYTES,
    launcher_path: Path | None = None,
) -> CollectedExecution:
    """Collect one PID-scoped trace while executing the target at most once."""

    started = time.monotonic()
    location = _create_launch_fifo(workspace)
    if location is None:
        return CollectedExecution(127, b"", False, True, False, 0, 0)
    directory, fifo = location
    bounded_limit = (
        capture_limit
        if isinstance(capture_limit, int)
        and not isinstance(capture_limit, bool)
        and capture_limit > 0
        else MAX_RAW_TRACE_BYTES
    )
    capture = _BoundedCapture(limit=bounded_limit)
    launcher: subprocess.Popen[Any] | None = None
    collector: subprocess.Popen[Any] | None = None
    readers: list[threading.Thread] = []
    target_started = False
    exit_code = 127
    failed = False
    collector_preparation_ms = 0
    collector_cleanup_started = 0.0
    collector_cleanup_ms = 0
    try:
        helper = (launcher_path or Path(__file__)).resolve(strict=True)
        launcher = spawn_argv(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                str(helper),
                "--launch",
                str(fifo),
                *list(argv),
            ],
            cwd=workspace,
            env=dict(environment),
        )
        collector_started = time.monotonic()
        collector = spawn_argv(
            [
                executable,
                "-w",
                "-f",
                "filesys",
                "-f",
                "pathname",
                "-f",
                "exec",
                str(launcher.pid),
            ],
            cwd=workspace,
            env=dict(environment),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if collector.stdout is None:
            failed = True
        else:
            reader = threading.Thread(
                target=_drain_stream,
                args=(collector.stdout, capture),
                daemon=True,
            )
            reader.start()
            readers.append(reader)
        try:
            collector.wait(timeout=COLLECTOR_STARTUP_SECONDS)
        except subprocess.TimeoutExpired:
            pass
        else:
            failed = True
            return CollectedExecution(
                int(collector.returncode or 1),
                capture.bytes(),
                capture.truncated,
                True,
                False,
                0,
                max(0, int((time.monotonic() - collector_started) * 1000)),
            )
        collector_preparation_ms = max(
            0, int((time.monotonic() - collector_started) * 1000)
        )
        if not _release_target(fifo):
            failed = True
            return CollectedExecution(
                127,
                capture.bytes(),
                capture.truncated,
                True,
                False,
                0,
                collector_preparation_ms,
            )
        target_started = True
        exit_code = int(launcher.wait())
        if collector.poll() is not None:
            failed = True
    except KeyboardInterrupt:
        failed = True
        exit_code = 130
    except (OSError, RuntimeError, subprocess.SubprocessError, TypeError, ValueError):
        failed = True
        if target_started and launcher is not None:
            try:
                exit_code = int(launcher.wait())
            except (OSError, subprocess.SubprocessError, TypeError, ValueError):
                exit_code = 127
    finally:
        collector_cleanup_started = time.monotonic()
        if launcher is not None and launcher.poll() is None:
            try:
                terminate_group(launcher)
            except Exception:
                failed = True
        if collector is not None and collector.poll() is None:
            try:
                terminate_group(collector)
            except Exception:
                failed = True
        for reader in readers:
            reader.join(timeout=1)
            if reader.is_alive():
                capture.failed = True
        _remove_launch_fifo(directory, fifo)
        collector_cleanup_ms = max(
            0, int((time.monotonic() - collector_cleanup_started) * 1000)
        )
    duration_ms = (
        max(0, int((time.monotonic() - started) * 1000)) if target_started else 0
    )
    return CollectedExecution(
        exit_code=exit_code,
        raw=capture.bytes(),
        truncated=capture.truncated,
        failed=bool(failed or capture.failed),
        target_started=target_started,
        command_duration_ms=duration_ms,
        collector_overhead_ms=min(
            _bounded_add(collector_preparation_ms, collector_cleanup_ms),
            duration_ms,
        ),
    )


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
    native_backend_probe: NativeBackendProbe = _native_fs_usage,
    system_version: Callable[[], str] = probe_macos_version,
    privilege_probe: Callable[[], bool] = has_privilege,
    collector: Collector = collect_command,
    spawn_argv: SpawnArgv = click_process.spawn_argv,
    terminate_group: TerminateGroup = click_process.terminate_process_group,
    system_name: str | None = None,
    capture_limit: int = MAX_RAW_TRACE_BYTES,
) -> ShadowExecution:
    """Execute one target and attach best-effort native macOS telemetry."""

    try:
        system = platform.system() if system_name is None else system_name
        privileged = bool(privilege_probe()) if system == "Darwin" else False
    except Exception:
        system = ""
        privileged = False
    if system != "Darwin" or not privileged:
        return click_observer_common.run_unobserved(
            execute_unobserved,
            evidence_key=evidence_key,
            check_digest=check_digest,
            mutation_revision=mutation_revision,
        )

    preparation_started = time.monotonic()
    try:
        executable, resolve_error = resolve_backend("fs_usage", workspace=workspace)
    except Exception:
        executable, resolve_error = None, "backend resolution failed"
    if (
        resolve_error
        or not isinstance(executable, str)
        or not executable
        or not native_backend_probe(executable)
    ):
        preparation_ms = max(0, int((time.monotonic() - preparation_started) * 1000))
        return click_observer_common.fallback_execution(
            execute_unobserved,
            evidence_key=evidence_key,
            check_digest=check_digest,
            mutation_revision=mutation_revision,
            status="unavailable",
            preparation_ms=preparation_ms,
        )
    try:
        digest = digest_file(Path(executable))
        version = system_version()
    except Exception:
        digest = ""
        version = ""
    if (
        not isinstance(digest, str)
        or _DIGEST.fullmatch(digest) is None
        or not isinstance(version, str)
        or _VERSION.fullmatch(version) is None
    ):
        preparation_ms = max(0, int((time.monotonic() - preparation_started) * 1000))
        return click_observer_common.fallback_execution(
            execute_unobserved,
            evidence_key=evidence_key,
            check_digest=check_digest,
            mutation_revision=mutation_revision,
            status="unavailable",
            preparation_ms=preparation_ms,
        )
    preparation_ms = max(0, int((time.monotonic() - preparation_started) * 1000))

    try:
        collected = collector(
            argv,
            workspace=workspace,
            environment=environment,
            executable=executable,
            spawn_argv=spawn_argv,
            terminate_group=terminate_group,
            capture_limit=capture_limit,
        )
    except Exception:
        collected = CollectedExecution(127, b"", False, True, False, 0, 0)
    if not collected.target_started:
        return click_observer_common.fallback_execution(
            execute_unobserved,
            evidence_key=evidence_key,
            check_digest=check_digest,
            mutation_revision=mutation_revision,
            status="failed",
            backend_name="fs_usage",
            backend_version=version,
            backend_digest=digest,
            preparation_ms=_bounded_add(
                preparation_ms, collected.collector_overhead_ms
            ),
        )

    parsing_started = time.monotonic()
    raw_trace = collected.raw
    try:
        parsed = parse_fs_usage(
            raw_trace,
            workspace=observation_root or workspace,
            truncated=collected.truncated or collected.failed,
        )
    except Exception:
        parsed = ParsedTrace((), 0, 1, 0, False, False)
        collected = CollectedExecution(
            collected.exit_code,
            b"",
            collected.truncated,
            True,
            True,
            collected.command_duration_ms,
            collected.collector_overhead_ms,
        )
    finally:
        raw_trace = b""
    parsing_ms = max(0, int((time.monotonic() - parsing_started) * 1000))
    observer_overhead_ms = _bounded_add(
        preparation_ms,
        _bounded_add(collected.collector_overhead_ms, parsing_ms),
    )
    identity_started = time.monotonic()
    try:
        final_digest = digest_file(Path(executable))
    except Exception:
        final_digest = ""
    identity_ms = max(0, int((time.monotonic() - identity_started) * 1000))
    observer_overhead_ms = _bounded_add(observer_overhead_ms, identity_ms)
    if final_digest != digest:
        return ShadowExecution(
            collected.exit_code,
            click_observer_common.record(
                evidence_key=evidence_key,
                check_digest=check_digest,
                mutation_revision=mutation_revision,
                backend_name=None,
                status="unavailable",
                process_tree_complete=False,
                command_duration_ms=collected.command_duration_ms,
                observer_overhead_ms=observer_overhead_ms,
            ),
        )

    status = (
        "failed"
        if collected.failed and not parsed.inputs
        else "partial"
        if collected.failed
        or collected.truncated
        or not parsed.process_tree_complete
        else "complete"
    )
    return ShadowExecution(
        collected.exit_code,
        click_observer_common.record(
            evidence_key=evidence_key,
            check_digest=check_digest,
            mutation_revision=mutation_revision,
            backend_name="fs_usage",
            backend_version=version,
            backend_digest=digest,
            inputs=parsed.inputs,
            status=status,
            external_input_count=parsed.external_input_count,
            unresolved_event_count=parsed.unresolved_event_count,
            child_process_count=parsed.child_process_count,
            process_tree_complete=(
                parsed.process_tree_complete and status == "complete"
            ),
            command_duration_ms=collected.command_duration_ms,
            observer_overhead_ms=observer_overhead_ms,
        ),
    )
