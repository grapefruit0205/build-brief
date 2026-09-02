"""Dependency snapshots for opt-in cross-revision evidence reuse.

Dependencies may be declared in the approved contract, in a committed
repository manifest, or in both. Patterns use a small deterministic grammar:
``*`` matches inside one path segment, ``**`` as a complete segment crosses
directories, and a trailing slash names a directory prefix. Every unsafe or
ambiguous input fails closed and simply causes the verification check to run.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
import fnmatch
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any


CONFIG_RELATIVE_PATH = ".click/evidence-dependencies.json"
CONFIG_VERSION = 1
CONTRACT_PROVIDER_NAME = "approved-contract-v1"
MANIFEST_PROVIDER_NAME = "repository-manifest-v1"
COMBINED_PROVIDER_NAME = "approved-contract+repository-manifest-v1"
PROVIDER_NAMES = frozenset(
    {
        CONTRACT_PROVIDER_NAME,
        MANIFEST_PROVIDER_NAME,
        COMBINED_PROVIDER_NAME,
    }
)
OBSERVATION_PROVIDER_NAME = "runtime-dependency-observation-v1"
OBSERVATION_STATUSES = frozenset({"complete", "failed", "unavailable"})
OBSERVATION_FIELDS = frozenset(
    {
        "provider",
        "status",
        "paths",
        "external_access",
        "child_processes",
        "process_tree_complete",
    }
)
MAX_CONFIG_BYTES = 256 * 1024

GitCapture = Callable[[Path, list[str]], bytes | None]


def _digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _canonical_config_bytes(value: bytes) -> bytes:
    """Make a committed text manifest stable across Git checkout EOL modes."""
    return value.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _group_digest(checks: list[dict[str, Any]]) -> str:
    payload: list[dict[str, list[str]]] = []
    for check in checks:
        argv = check.get("argv") if isinstance(check, dict) else None
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(item, str) or not item for item in argv)
        ):
            return ""
        payload.append({"argv": list(argv)})
    return _digest({"checks": payload}) if payload else ""


def _manifest_group_digest(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return ""
    checks: list[dict[str, Any]] = []
    for argv in value:
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(item, str) or not item for item in argv)
        ):
            return ""
        checks.append({"argv": list(argv)})
    return _group_digest(checks)


def _valid_pattern(pattern: Any) -> bool:
    if (
        not isinstance(pattern, str)
        or not pattern
        or "\x00" in pattern
        or "\\" in pattern
        or pattern.startswith(("/", "!", "./", "../"))
        or any(character in pattern for character in "?[]")
    ):
        return False
    candidate = pattern[:-1] if pattern.endswith("/") else pattern
    if not candidate or candidate in {".", ".."}:
        return False
    parts = candidate.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    return all("**" not in part or part == "**" for part in parts)


def normalize_patterns(value: Any) -> tuple[tuple[str, ...] | None, str]:
    """Validate and normalize one approved dependency declaration."""
    if not isinstance(value, list) or not value:
        return None, "must be a non-empty list of repository-relative patterns"
    if any(not _valid_pattern(pattern) for pattern in value):
        return (
            None,
            "must use deterministic repository-relative patterns; `*` stays in one "
            "path segment, `**` must be a complete segment, and `?`, character "
            "classes, absolute paths, traversal, and backslashes are not accepted",
        )
    if len(set(value)) != len(value):
        return None, "must not contain duplicate patterns"
    return tuple(sorted(value)), ""


def patterns_digest(patterns: Iterable[str]) -> str:
    normalized, error = normalize_patterns(list(patterns))
    return "" if error or normalized is None else _digest({"patterns": normalized})


def _segment_matches(pattern: str, value: str) -> bool:
    return fnmatch.fnmatchcase(value, pattern)


def _glob_matches(
    pattern_parts: tuple[str, ...], path_parts: tuple[str, ...]
) -> bool:
    @lru_cache(maxsize=None)
    def match(pattern_index: int, path_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return path_index == len(path_parts)
        head = pattern_parts[pattern_index]
        if head == "**":
            return match(pattern_index + 1, path_index) or bool(
                path_index < len(path_parts)
                and match(pattern_index, path_index + 1)
            )
        return bool(
            path_index < len(path_parts)
            and _segment_matches(head, path_parts[path_index])
            and match(pattern_index + 1, path_index + 1)
        )

    return match(0, 0)


def _matches(pattern: str, relative: str) -> bool:
    if pattern.endswith("/"):
        return relative.startswith(pattern)
    return _glob_matches(tuple(pattern.split("/")), tuple(relative.split("/")))


def _pattern_expands_repository_members(pattern: str) -> bool:
    """Return whether a manifest pattern names a set rather than one path.

    A complete runtime observation can safely refine these conservative
    discovery envelopes to the members that the check actually touched.
    Concrete contract and manifest paths remain hard dependencies.
    """
    return pattern.endswith("/") or "*" in pattern


def _safe_relative_path(relative: str, *, directory: bool = False) -> bool:
    candidate = relative[:-1] if directory and relative.endswith("/") else relative
    if not candidate or "\x00" in candidate or "\\" in candidate:
        return False
    path = PurePosixPath(candidate)
    return not path.is_absolute() and all(
        part not in {".", "..", ""} for part in path.parts
    )


def receipt_paths_are_valid(value: Any) -> bool:
    return bool(
        isinstance(value, list)
        and value
        and value == sorted(set(value))
        and all(
            isinstance(relative, str)
            and _safe_relative_path(relative, directory=relative.endswith("/"))
            for relative in value
        )
    )


def observation_paths_are_valid(value: Any) -> bool:
    """Return whether observed paths are canonical repository-relative inputs."""
    return bool(
        isinstance(value, list)
        and value == sorted(set(value))
        and all(
            isinstance(relative, str)
            and _safe_relative_path(relative, directory=relative.endswith("/"))
            for relative in value
        )
    )


def dependency_observation(
    paths: Iterable[str] = (),
    *,
    status: str = "complete",
    external_access: bool = False,
    child_processes: int = 0,
    process_tree_complete: bool = True,
) -> dict[str, Any]:
    """Build one content-free runtime dependency observation receipt.

    The observer reports repository-relative paths only. External input is
    represented as a boolean because absolute host paths must not leak into
    persisted Click state. A completed check may still have an incomplete
    observation; callers must use :func:`dependency_observation_is_complete`
    before reusing evidence.
    """
    if isinstance(paths, (str, bytes)):
        raise ValueError("runtime dependency paths must be an iterable of paths")
    try:
        raw_paths = list(paths)
        normalized_paths = sorted(set(raw_paths))
    except (TypeError, ValueError) as error:
        raise ValueError("invalid runtime dependency observation paths") from error
    receipt = {
        "provider": OBSERVATION_PROVIDER_NAME,
        "status": status,
        "paths": normalized_paths,
        "external_access": external_access,
        "child_processes": child_processes,
        "process_tree_complete": process_tree_complete,
    }
    if not dependency_observation_is_valid(receipt):
        raise ValueError("invalid runtime dependency observation")
    return receipt


def unavailable_dependency_observation(*, failed: bool = False) -> dict[str, Any]:
    """Return an explicit fail-closed observation for an absent/failed tracer."""
    return dependency_observation(
        status="failed" if failed else "unavailable",
        process_tree_complete=False,
    )


def dependency_observation_is_valid(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != OBSERVATION_FIELDS:
        return False
    child_processes = value.get("child_processes")
    return bool(
        value.get("provider") == OBSERVATION_PROVIDER_NAME
        and value.get("status") in OBSERVATION_STATUSES
        and observation_paths_are_valid(value.get("paths"))
        and isinstance(value.get("external_access"), bool)
        and isinstance(child_processes, int)
        and not isinstance(child_processes, bool)
        and child_processes >= 0
        and isinstance(value.get("process_tree_complete"), bool)
    )


def dependency_observation_is_complete(value: Any) -> bool:
    """Return whether runtime observation can safely support evidence reuse."""
    return bool(
        dependency_observation_is_valid(value)
        and value.get("status") == "complete"
        and value.get("external_access") is False
        and value.get("process_tree_complete") is True
    )


def dependency_observation_digest(value: Any) -> str:
    return _digest(value) if dependency_observation_is_valid(value) else ""


def combine_dependency_observations(values: Iterable[Any]) -> dict[str, Any]:
    """Union per-check observations for one evidence source."""
    observations = list(values)
    if not observations:
        return unavailable_dependency_observation()
    if any(not dependency_observation_is_valid(value) for value in observations):
        return unavailable_dependency_observation(failed=True)
    statuses = {str(value["status"]) for value in observations}
    status = (
        "complete"
        if statuses == {"complete"}
        else "failed"
        if "failed" in statuses
        else "unavailable"
    )
    return dependency_observation(
        {
            relative
            for value in observations
            for relative in value["paths"]
        },
        status=status,
        external_access=any(value["external_access"] for value in observations),
        child_processes=sum(value["child_processes"] for value in observations),
        process_tree_complete=all(
            value["process_tree_complete"] for value in observations
        ),
    )


def _inside(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def _dependency_closure(
    root: Path,
    matched: set[str],
    repository_paths: set[str],
) -> set[str] | None:
    """Add safe in-repository symlink targets to the dependency set."""
    root = root.resolve()
    closure = set(matched)
    pending = list(matched)
    while pending:
        relative = pending.pop()
        directory_marker = relative.endswith("/")
        target = root / (relative[:-1] if directory_marker else relative)
        try:
            metadata = target.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return None
        if not stat.S_ISLNK(metadata.st_mode):
            continue
        try:
            link_value = os.readlink(target)
        except OSError:
            return None
        if Path(link_value).is_absolute():
            return None
        try:
            resolved = target.resolve(strict=True)
        except (OSError, RuntimeError):
            return None
        if not _inside(root, resolved):
            return None
        resolved_relative = resolved.relative_to(root).as_posix()
        if resolved.is_file():
            additions = {resolved_relative}
        elif resolved.is_dir():
            prefix = f"{resolved_relative}/" if resolved_relative != "." else ""
            additions = {
                *(
                    {f"{resolved_relative}/"}
                    if resolved_relative != "."
                    else set()
                ),
                *{
                    candidate
                    for candidate in repository_paths
                    if not prefix or candidate.startswith(prefix)
                },
            }
        else:
            return None
        for addition in additions - closure:
            if not _safe_relative_path(
                addition, directory=addition.endswith("/")
            ):
                return None
            closure.add(addition)
            pending.append(addition)
    return closure


def _hash_path(hasher: Any, root: Path, relative: str) -> bool:
    directory_marker = relative.endswith("/")
    candidate = relative[:-1] if directory_marker else relative
    encoded = os.fsencode(relative)
    hasher.update(len(encoded).to_bytes(8, "big"))
    hasher.update(encoded)
    target = root / candidate
    try:
        metadata = target.lstat()
    except FileNotFoundError:
        hasher.update(b"missing")
        return True
    except OSError:
        return False
    hasher.update(str(stat.S_IMODE(metadata.st_mode)).encode())
    if stat.S_ISLNK(metadata.st_mode):
        try:
            link_value = os.readlink(target)
        except OSError:
            return False
        if Path(link_value).is_absolute():
            return False
        hasher.update(b"symlink\0")
        hasher.update(os.fsencode(link_value))
        return True
    if stat.S_ISDIR(metadata.st_mode) and directory_marker:
        hasher.update(b"directory\0")
        try:
            entries = sorted(os.fsencode(entry.name) for entry in target.iterdir())
        except OSError:
            return False
        hasher.update(len(entries).to_bytes(8, "big"))
        for name in entries:
            hasher.update(len(name).to_bytes(8, "big"))
            hasher.update(name)
        return True
    if not stat.S_ISREG(metadata.st_mode):
        return False
    hasher.update(b"file\0")
    try:
        with target.open("rb") as handle:
            while True:
                chunk = handle.read(128 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
    except OSError:
        return False
    return True


def _load_repository(
    cwd: Path,
    git_capture: GitCapture,
) -> tuple[Path, str, dict[str, tuple[str, ...]], set[str]] | None:
    root_output = git_capture(cwd, ["rev-parse", "--show-toplevel"])
    if root_output is None:
        return None
    root = Path(os.fsdecode(root_output.strip()))
    listed = git_capture(
        root,
        ["ls-files", "--cached", "--others", "--exclude-standard", "-z"],
    )
    if listed is None:
        return None
    repository_paths = {os.fsdecode(item) for item in listed.split(b"\0") if item}
    if any(not _safe_relative_path(relative) for relative in repository_paths):
        return None

    committed = git_capture(root, ["show", f"HEAD:{CONFIG_RELATIVE_PATH}"])
    if committed is None:
        # An uncommitted manifest is never dependency authority. Contract-only
        # receipts remain available only when no working-tree manifest exists.
        try:
            (root / CONFIG_RELATIVE_PATH).lstat()
        except FileNotFoundError:
            return root, "", {}, repository_paths
        except OSError:
            return None
        return None
    if len(committed) > MAX_CONFIG_BYTES:
        return None
    # HEAD is the authority boundary. A malformed, deleted, or otherwise
    # modified working-tree copy cannot narrow or replace the committed map.
    # If a verification command reads that copy, a complete runtime observer
    # records the path and its content change still invalidates the receipt.
    canonical_raw = _canonical_config_bytes(committed)
    try:
        value = json.loads(canonical_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or set(value) != {"version", "entries"}:
        return None
    if value.get("version") != CONFIG_VERSION:
        return None
    raw_entries = value.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        return None

    entries: dict[str, tuple[str, ...]] = {}
    for entry in raw_entries:
        if not isinstance(entry, dict) or set(entry) != {"checks", "paths"}:
            return None
        group_digest = _manifest_group_digest(entry.get("checks"))
        paths, error = normalize_patterns(entry.get("paths"))
        if not group_digest or group_digest in entries or error or paths is None:
            return None
        entries[group_digest] = paths
    return (
        root,
        hashlib.sha256(canonical_raw).hexdigest(),
        entries,
        repository_paths,
    )


def receipts_for_groups(
    cwd: Path,
    grouped_checks: dict[str, list[dict[str, Any]]],
    *,
    declarations: dict[str, list[str] | tuple[str, ...]] | None = None,
    observations: dict[str, dict[str, Any]] | None = None,
    git_capture: GitCapture,
) -> dict[str, dict[str, Any]]:
    """Return manifest-plus-observation receipts, or `{}` on ambiguity."""
    loaded = _load_repository(cwd, git_capture)
    if loaded is None:
        return {}
    root, manifest_digest, entries, repository_paths = loaded
    approved = declarations or {}
    observed = observations or {}
    receipts: dict[str, dict[str, Any]] = {}
    for source_key, checks in grouped_checks.items():
        if not isinstance(source_key, str):
            continue
        group_digest = _group_digest(checks)
        manifest_patterns = entries.get(group_digest, ())
        declared_value = approved.get(source_key, ())
        if declared_value:
            declared_patterns, declaration_error = normalize_patterns(
                list(declared_value)
            )
            if declaration_error or declared_patterns is None:
                continue
        else:
            declared_patterns = ()
        if not declared_patterns and not manifest_patterns:
            continue
        if declared_patterns and manifest_patterns:
            provider = COMBINED_PROVIDER_NAME
        elif declared_patterns:
            provider = CONTRACT_PROVIDER_NAME
        else:
            provider = MANIFEST_PROVIDER_NAME
        raw_observation = observed.get(source_key)
        if raw_observation is None:
            observation = unavailable_dependency_observation()
        elif dependency_observation_is_valid(raw_observation):
            observation = {
                **raw_observation,
                "paths": list(raw_observation["paths"]),
            }
        else:
            observation = unavailable_dependency_observation(failed=True)
        # Approval-bound contract paths are always hard dependencies. With a
        # complete runtime observation, expanding repository-manifest patterns
        # act as conservative discovery envelopes; the observation identifies
        # the members actually consumed. Literal manifest paths remain hard
        # inputs so known implicit dependencies are never silently discarded.
        required_manifest_patterns = (
            tuple(
                pattern
                for pattern in manifest_patterns
                if not _pattern_expands_repository_members(pattern)
            )
            if dependency_observation_is_complete(observation)
            else manifest_patterns
        )
        effective_patterns = tuple(
            sorted(set(declared_patterns) | set(required_manifest_patterns))
        )
        matched: set[str] = set()
        valid = True
        for pattern in effective_patterns:
            pattern_matches = {
                relative
                for relative in repository_paths
                if _matches(pattern, relative)
            }
            if not pattern_matches:
                valid = False
                break
            matched.update(pattern_matches)
        if not valid or effective_patterns and not matched:
            continue
        declared_closure = _dependency_closure(root, matched, repository_paths)
        if declared_closure is None:
            continue
        observed_closure = _dependency_closure(
            root, set(observation["paths"]), repository_paths
        )
        if observed_closure is None:
            continue
        resolved_paths = sorted(declared_closure | observed_closure)
        if not resolved_paths:
            continue
        entry_payload = {
            "checks": [check["argv"] for check in checks],
            "contract_paths": list(declared_patterns),
            "manifest_paths": list(manifest_patterns),
        }
        entry_digest = _digest(entry_payload)
        hasher = hashlib.sha256()
        hasher.update(provider.encode())
        hasher.update(entry_digest.encode())
        observation_digest = dependency_observation_digest(observation)
        hasher.update(observation_digest.encode())
        for relative in resolved_paths:
            if not _hash_path(hasher, root, relative):
                valid = False
                break
        if not valid:
            continue
        receipts[source_key] = {
            "provider": provider,
            # The full manifest digest is audit metadata. Matching deliberately
            # uses the relevant normalized entry digest, so unrelated entries
            # may change without invalidating this receipt.
            "manifest_digest": manifest_digest if manifest_patterns else "",
            "entry_digest": entry_digest,
            "dependency_digest": hasher.hexdigest(),
            "resolved_paths": resolved_paths,
            "observation_digest": observation_digest,
            "observation": observation,
        }
    return receipts
