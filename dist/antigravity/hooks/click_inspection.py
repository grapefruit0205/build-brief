"""Shell-free read-only admission and hardened inspection execution for Click.

This module owns the portable read/search capability, including Git and SSH
normalization, executable trust boundaries, and output redaction. Observation
receipts and contract state remain outside this boundary.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any
from urllib.parse import urlsplit, urlunsplit

if __package__:
    from . import click_capability, click_process
else:  # Executed directly from the bundled hooks directory.
    import click_capability
    import click_process


REQUEST_FIELDS = {"version", "commands"}
MAX_COMMANDS = 8
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
    "pdfinfo",
    "pdftotext",
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
    "check-ignore",
    "describe",
    "diff",
    "for-each-ref",
    "log",
    "ls-files",
    "ls-tree",
    "merge-base",
    "name-rev",
    "remote",
    "rev-parse",
    "show",
    "status",
}
GIT_DIFF_RENDERING_SUBCOMMANDS = {"diff", "log", "show"}
GIT_GLOBAL_ALLOWED_PREFIXES = ("--git-dir=", "--work-tree=")
GIT_GLOBAL_REJECTED_OPTIONS = {"-p", "--paginate", "-c", "--config-env"}
GIT_READ_ONLY_EXACT_OPTIONS = {
    "check-ignore": {
        "-q", "--quiet", "-v", "--verbose", "--stdin", "-z", "--no-index",
        "--non-matching",
    },
    "describe": {
        "--always", "--tags", "--all", "--long", "--exact-match", "--contains",
        "--debug", "--first-parent", "--broken",
    },
    "diff": {
        "--cached", "--staged", "--check", "--quiet", "--exit-code", "--stat",
        "--shortstat", "--numstat", "--name-only", "--name-status", "--summary",
        "--binary", "--patch", "--no-patch", "--raw", "--minimal", "--patience",
        "--histogram", "--no-color", "--relative", "--ignore-space-at-eol",
        "--ignore-all-space", "--ignore-space-change", "--ignore-blank-lines", "-w",
        "-b", "--no-ext-diff", "--no-textconv",
    },
    "for-each-ref": {"--ignore-case", "--omit-empty"},
    "log": {
        "--oneline", "--no-decorate", "--decorate", "--stat", "--shortstat",
        "--numstat", "--name-only", "--name-status", "--summary", "--no-merges",
        "--merges", "--first-parent", "--all", "--branches", "--tags", "--remotes",
        "--reflog", "--reverse", "--topo-order", "--date-order", "--author-date-order",
        "--parents", "--children", "--boundary", "--simplify-by-decoration",
        "--full-history", "--simplify-merges", "--ancestry-path", "--follow",
        "--no-patch", "--patch", "--abbrev-commit", "--no-color", "--no-ext-diff",
        "--no-textconv",
    },
    "ls-files": {
        "--cached", "--deleted", "--modified", "--others", "--ignored", "--stage",
        "--unmerged", "--killed", "--directory", "--no-empty-directory", "--eol",
        "--deduplicate", "--sparse", "--debug", "--exclude-standard", "--error-unmatch",
        "-c", "-d", "-m", "-o", "-i", "-s", "-u", "-k", "-t", "-v", "-f", "-z",
    },
    "ls-tree": {
        "-d", "-r", "-t", "-l", "--long", "-z", "--name-only", "--name-status",
        "--object-only", "--full-name", "--full-tree",
    },
    "merge-base": {"--all", "--octopus", "--independent", "--is-ancestor", "--fork-point"},
    "name-rev": {"--tags", "--all", "--stdin", "--name-only", "--no-undefined", "--always"},
    "remote": {"--all", "--push"},
    "rev-parse": {
        "--verify", "--short", "--abbrev-ref", "--symbolic-full-name", "--show-toplevel",
        "--show-prefix", "--show-cdup", "--git-dir", "--is-inside-work-tree",
        "--is-bare-repository", "--show-object-format", "--sq", "--revs-only",
        "--no-revs", "--flags", "--no-flags", "--quiet", "-q",
    },
    "show": {
        "--stat", "--shortstat", "--numstat", "--name-only", "--name-status", "--summary",
        "--binary", "--patch", "--no-patch", "--raw", "--minimal", "--patience",
        "--histogram", "--no-color", "--relative", "--ignore-space-at-eol",
        "--ignore-all-space", "--ignore-space-change", "--ignore-blank-lines", "-w", "-b",
        "--no-ext-diff", "--no-textconv", "--oneline", "--abbrev-commit",
    },
    "status": {
        "--short", "--porcelain", "--branch", "--show-stash", "--long",
        "--ignored", "--no-renames", "-s", "-b", "-sb",
    },
}
GIT_READ_ONLY_OPTION_PREFIXES = {
    "check-ignore": ("--exclude-standard",),
    "describe": ("--abbrev=", "--candidates=", "--match=", "--exclude="),
    "diff": (
        "--stat=", "--relative=", "--unified=", "--word-diff=", "--word-diff-regex=",
        "--src-prefix=", "--dst-prefix=", "--line-prefix=", "--ignore-submodules=",
        "--submodule=", "--diff-filter=",
    ),
    "for-each-ref": (
        "--sort=", "--count=", "--points-at=", "--merged=", "--no-merged=",
        "--contains=", "--no-contains=",
    ),
    "log": (
        "--date=", "--since=", "--after=", "--until=", "--before=", "--author=",
        "--committer=", "--grep=", "--max-count=", "--skip=", "--abbrev=",
        "--decorate=", "--stat=", "--relative=", "--unified=", "--word-diff=",
        "--word-diff-regex=", "--src-prefix=", "--dst-prefix=", "--line-prefix=",
        "--ignore-submodules=", "--submodule=", "--diff-filter=",
    ),
    "ls-files": (
        "--exclude=", "--exclude-from=", "--exclude-per-directory=",
        "--with-tree=", "--abbrev=",
    ),
    "ls-tree": ("--abbrev=",),
    "name-rev": ("--refs=", "--exclude="),
    "rev-parse": ("--short=", "--abbrev-ref=", "--path-format=", "--disambiguate="),
    "show": (
        "--date=", "--stat=", "--relative=", "--unified=", "--word-diff=",
        "--word-diff-regex=", "--src-prefix=", "--dst-prefix=", "--line-prefix=",
        "--ignore-submodules=", "--submodule=", "--diff-filter=",
    ),
    "status": ("--porcelain=", "--ignored=", "--find-renames="),
}
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
SSH_TARGET = re.compile(r"^[A-Za-z0-9_.-]+(?:@[A-Za-z0-9_.-]+)?$")
SSH_READ_ONLY_GIT_SUBCOMMANDS = {"merge-base", "remote", "rev-parse", "status"}
GIT_REMOTE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


RunRequest = Callable[[dict[str, Any]], int]
RenderRunnerCommand = Callable[[list[str]], str]


def validate_request(
    raw: str, *, protocol_version: int = click_capability.PROTOCOL_VERSION
) -> tuple[dict[str, Any] | None, bool, str]:
    value, error = click_capability.decode_request(
        raw, "Inspection", version=protocol_version
    )
    if error:
        return None, False, error
    assert value is not None
    unknown = sorted(set(value) - REQUEST_FIELDS)
    if unknown:
        rendered = ", ".join(f"`{field}`" for field in unknown)
        return None, False, f"Inspection request contains unsupported field(s): {rendered}."
    commands = value.get("commands")
    if not isinstance(commands, list) or not commands:
        return None, False, "Inspection `commands` must be a non-empty argv-list list."
    if len(commands) > MAX_COMMANDS:
        return None, False, f"Inspection may contain at most {MAX_COMMANDS} commands."
    normalized: list[list[str]] = []
    broad = False
    for index, raw_argv in enumerate(commands, start=1):
        argv, argv_error = click_capability.validate_argv(
            raw_argv, f"Inspection command {index}"
        )
        if argv_error:
            return None, False, argv_error
        assert argv is not None
        if not is_read_only_tokens(list(argv)):
            return (
                None,
                False,
                f"Inspection command {index} is not a supported read-only argv operation.",
            )
        broad = broad or is_broad_exploration_tokens(argv)
        normalized.append(argv)
    return {"version": protocol_version, "commands": normalized}, broad, ""


def git_option_allowed(subcommand: str, token: str) -> bool:
    if token in GIT_READ_ONLY_EXACT_OPTIONS.get(subcommand, set()):
        return True
    if any(
        token.startswith(prefix)
        for prefix in GIT_READ_ONLY_OPTION_PREFIXES.get(subcommand, ())
    ):
        return True
    if subcommand in GIT_DIFF_RENDERING_SUBCOMMANDS and re.fullmatch(r"-U\d+", token):
        return True
    if subcommand == "log" and re.fullmatch(r"-\d+", token):
        return True
    return False


def is_read_only_git_remote_arguments(arguments: list[str]) -> bool:
    if not arguments or arguments[0] != "get-url":
        return False
    remote_names = [
        argument
        for argument in arguments[1:]
        if argument not in {"--", "--all", "--push"}
    ]
    return len(remote_names) == 1 and GIT_REMOTE_NAME.fullmatch(remote_names[0]) is not None


def parse_read_only_git_tokens(
    tokens: list[str],
) -> tuple[list[str], str, list[str]] | None:
    if not tokens or Path(tokens[0]).name.lower() not in {"git", "git.exe"}:
        return None
    global_arguments: list[str] = []
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "-C":
            if index + 1 >= len(tokens):
                return None
            global_arguments.extend([token, tokens[index + 1]])
            index += 2
            continue
        if token.startswith(GIT_GLOBAL_ALLOWED_PREFIXES):
            global_arguments.append(token)
            index += 1
            continue
        if token in {"--no-pager", "--no-optional-locks"}:
            index += 1
            continue
        if (
            token in GIT_GLOBAL_REJECTED_OPTIONS
            or token.startswith("--config-env=")
            or (token.startswith("-c") and token != "-C")
        ):
            return None
        if token.startswith("-"):
            return None
        subcommand = token
        break
    else:
        return None

    if subcommand not in READ_ONLY_GIT_SUBCOMMANDS:
        return None
    arguments = tokens[index + 1 :]
    options_finished = False
    for argument in arguments:
        if options_finished:
            continue
        if argument == "--":
            options_finished = True
            continue
        if argument.startswith("-") and not git_option_allowed(subcommand, argument):
            return None
    if subcommand == "remote" and not is_read_only_git_remote_arguments(arguments):
        return None
    return global_arguments, subcommand, arguments


def git_subcommand(tokens: list[str]) -> str:
    parsed = parse_read_only_git_tokens(tokens)
    return parsed[1] if parsed is not None else ""


def build_read_only_git_argv(tokens: list[str]) -> tuple[list[str] | None, str]:
    parsed = parse_read_only_git_tokens(tokens)
    if parsed is None:
        return None, "Git argv is outside Click's supported read-only option policy."
    global_arguments, subcommand, arguments = parsed
    forced = (
        ["--no-ext-diff", "--no-textconv"]
        if subcommand in GIT_DIFF_RENDERING_SUBCOMMANDS
        else []
    )
    safe_config = [
        "-c",
        "core.fsmonitor=false",
        "-c",
        "diff.external=",
        "-c",
        "log.showSignature=false",
        "-c",
        "format.pretty=medium",
    ]
    return [
        "git",
        "--no-pager",
        "--no-optional-locks",
        *safe_config,
        *global_arguments,
        subcommand,
        *forced,
        *arguments,
    ], ""


def is_read_only_sed(tokens: list[str]) -> bool:
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


def get_content_paths(tokens: list[str]) -> list[str] | None:
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


def is_read_only_pdfinfo(tokens: list[str]) -> bool:
    """Accept metadata output only; pdfinfo has no output-file operand."""
    return bool(
        len(tokens) >= 2
        and Path(tokens[0]).name.lower() == "pdfinfo"
        and any(argument and not argument.startswith("-") for argument in tokens[1:])
    )


def is_stdout_only_pdftotext(tokens: list[str]) -> bool:
    """Require the explicit stdout operand so the default .txt write is impossible."""
    return bool(
        len(tokens) >= 3
        and Path(tokens[0]).name.lower() == "pdftotext"
        and tokens[-1] == "-"
        and any(argument and not argument.startswith("-") for argument in tokens[1:-1])
    )


def structured_ssh_parts(tokens: list[str]) -> tuple[str, list[str]] | None:
    if len(tokens) < 4 or Path(tokens[0]).name.lower() not in {"ssh", "ssh.exe"}:
        return None
    target = tokens[1]
    remote_argv = tokens[2:]
    if target.startswith("-") or not SSH_TARGET.fullmatch(target):
        return None
    if remote_argv[0] != "git":
        return None
    parsed = parse_read_only_git_tokens(remote_argv)
    if parsed is None or parsed[1] not in SSH_READ_ONLY_GIT_SUBCOMMANDS:
        return None
    if parsed[1] == "rev-parse":
        positional = [
            argument
            for argument in parsed[2]
            if argument != "--" and not argument.startswith("-")
        ]
        if positional != ["HEAD"]:
            return None
    return target, remote_argv


def is_path_qualified_executable(value: str) -> bool:
    return "/" in value or "\\" in value or bool(re.match(r"^[A-Za-z]:", value))


def is_local_read_only_tokens(tokens: list[str]) -> bool:
    if not tokens:
        return False
    if click_capability.ENVIRONMENT_ASSIGNMENT.match(tokens[0]):
        return False
    if is_path_qualified_executable(tokens[0]):
        return False
    executable = tokens[0].lower()
    if executable in {"git", "git.exe"}:
        return parse_read_only_git_tokens(tokens) is not None
    if executable not in READ_ONLY_COMMANDS:
        return False
    if executable == "get-content":
        return get_content_paths(tokens) is not None
    if executable == "pdfinfo":
        return is_read_only_pdfinfo(tokens)
    if executable == "pdftotext":
        return is_stdout_only_pdftotext(tokens)
    if executable == "sed":
        return is_read_only_sed(tokens)
    if executable == "file" and any(token in {"-C", "--compile"} for token in tokens[1:]):
        return False
    if executable == "find" and any(
        token in {
            "-delete", "-exec", "-execdir", "-fls", "-fprint", "-fprint0",
            "-fprintf", "-ok", "-okdir",
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


def is_read_only_tokens(tokens: list[str]) -> bool:
    if not tokens:
        return False
    if is_path_qualified_executable(tokens[0]):
        return False
    if tokens[0].lower() in {"ssh", "ssh.exe"}:
        return structured_ssh_parts(tokens) is not None
    return is_local_read_only_tokens(tokens)


def direct_command_tokens(
    command: str, *, windows: bool | None = None
) -> tuple[list[str] | None, str]:
    windows_tokens = os.name == "nt" if windows is None else windows
    try:
        lexer = shlex.shlex(
            command,
            posix=not windows_tokens,
            punctuation_chars="".join(sorted(click_capability.SHELL_CONTROL_PUNCTUATION)),
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None, ""
    if not windows_tokens:
        return tokens, ""
    normalized_tokens: list[str] = []
    for token in tokens:
        if len(token) >= 2 and token[0] == token[-1] and token[0] in {'"', "'"}:
            token = token[1:-1]
        if '"' in token or "'" in token:
            return (
                None,
                "Click could not safely normalize this Windows command line. "
                "Use `click-gate inspect` with explicit argv JSON.",
            )
        normalized_tokens.append(token)
    return normalized_tokens, ""


def request_from_bash(
    command: str,
    *,
    windows: bool | None = None,
    protocol_version: int = click_capability.PROTOCOL_VERSION,
) -> tuple[dict[str, Any] | None, bool, str]:
    if not command.strip() or "\n" in command or "\r" in command or "`" in command:
        return None, False, ""
    tokens, token_error = direct_command_tokens(command, windows=windows)
    if token_error:
        return None, False, token_error
    if tokens is None:
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
        if token and set(token).issubset(click_capability.SHELL_CONTROL_PUNCTUATION):
            return None, False, ""
        commands[-1].append(token)
    if not commands[-1]:
        return None, False, ""
    raw = json.dumps(
        {"version": protocol_version, "commands": commands},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    request, broad, error = validate_request(raw, protocol_version=protocol_version)
    if error and "not a supported read-only argv operation" in error:
        return None, False, ""
    return request, broad, error


def is_read_only_bash(command: str) -> bool:
    request, _, _ = request_from_bash(command)
    return request is not None


def targets_repository_root(targets: list[str]) -> bool:
    if not targets:
        return True
    return any(target.rstrip("/\\") in {"", ".", ".."} for target in targets)


def is_broad_exploration_tokens(tokens: list[str]) -> bool:
    executable, arguments = click_capability.command_parts(tokens)
    if executable == "rg" and "--files" in arguments:
        targets = click_capability.positional_arguments(arguments, RG_OPTIONS_WITH_VALUES)
        return targets_repository_root(targets)
    if executable == "find":
        targets = click_capability.positional_arguments(arguments)
        return targets_repository_root(targets[:1])
    if executable == "tree":
        targets = click_capability.positional_arguments(arguments)
        return targets_repository_root(targets)
    if executable == "ls":
        recursive = any(argument in {"-r", "--recursive"} for argument in arguments)
        if not recursive:
            return False
        targets = click_capability.positional_arguments(arguments)
        return targets_repository_root(targets)
    if executable == "git":
        subcommand = git_subcommand(tokens)
        if subcommand == "ls-files":
            index = tokens.index(subcommand)
            targets = click_capability.positional_arguments(
                [item.lower() for item in tokens[index + 1 :]]
            )
            return targets_repository_root(targets)
        if subcommand == "ls-tree":
            index = tokens.index(subcommand)
            remainder = [item.lower() for item in tokens[index + 1 :]]
            if "--" not in remainder:
                return True
            targets = remainder[remainder.index("--") + 1 :]
            return targets_repository_root(targets)
    return False


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        pass
    try:
        root_stat = root.stat()
        current = path if path.is_dir() else path.parent
        for candidate in (current, *current.parents):
            if os.path.samestat(candidate.stat(), root_stat):
                return True
    except OSError:
        pass
    return False


def valid_git_worktree_marker(marker: Path) -> bool:
    """Recognize real Git metadata, not an unrelated empty ancestor named .git."""
    try:
        if marker.is_dir():
            return (marker / "HEAD").is_file() and (
                (marker / "objects").is_dir() or (marker / "commondir").is_file()
            )
        if not marker.is_file():
            return False
        first_line = marker.read_text(encoding="utf-8", errors="strict").splitlines()[0]
        if not first_line.lower().startswith("gitdir:"):
            return False
        target = Path(first_line.split(":", 1)[1].strip())
        if not target.is_absolute():
            target = marker.parent / target
        target = target.resolve(strict=True)
        return (target / "HEAD").is_file() and (
            (target / "objects").is_dir() or (target / "commondir").is_file()
        )
    except (IndexError, OSError, RuntimeError, UnicodeError):
        return False


def workspace_boundary(workspace: Path | None = None) -> Path:
    candidate = workspace or Path.cwd()
    try:
        current = candidate.resolve()
    except (OSError, RuntimeError):
        current = Path(os.path.abspath(candidate))
    for possible in (current, *current.parents):
        if valid_git_worktree_marker(possible / ".git"):
            return possible
    return current


def git_metadata_present(workspace: Path | None = None) -> bool:
    root = workspace_boundary(workspace)
    return valid_git_worktree_marker(root / ".git")


def unsafe_inherited_environment_key(key: str) -> bool:
    upper = key.upper()
    return upper.startswith(("LD_", "DYLD_")) or upper in {"GCONV_PATH", "LOCPATH"}


def sanitized_executable_path(
    source: str | None = None, *, workspace: Path | None = None
) -> str:
    root = workspace_boundary(workspace)
    value = os.environ.get("PATH", "") if source is None else source
    entries: list[str] = []
    seen: set[str] = set()
    for raw_entry in value.split(os.pathsep):
        normalized_entry = raw_entry.strip()
        if (
            len(normalized_entry) >= 2
            and normalized_entry[0] == normalized_entry[-1]
            and normalized_entry[0] in {'"', "'"}
        ):
            normalized_entry = normalized_entry[1:-1]
        normalized_entry = os.path.expandvars(normalized_entry)
        if not normalized_entry or not os.path.isabs(normalized_entry):
            continue
        lexical = Path(os.path.abspath(normalized_entry))
        if path_is_within(lexical, root):
            continue
        try:
            resolved = Path(normalized_entry).resolve()
        except (OSError, RuntimeError):
            continue
        if path_is_within(resolved, root):
            continue
        rendered = str(resolved)
        key = os.path.normcase(rendered)
        if key in seen:
            continue
        seen.add(key)
        entries.append(rendered)
    return os.pathsep.join(entries)


def resolve_read_only_executable(
    executable: str, *, workspace: Path | None = None
) -> tuple[str | None, str]:
    if is_path_qualified_executable(executable):
        return None, "read-only executables must use an unqualified trusted name"
    root = workspace_boundary(workspace)
    inherited = shutil.which(executable)
    if inherited is not None:
        inherited_lexical = Path(os.path.abspath(inherited))
        if path_is_within(inherited_lexical, root):
            return None, "the inherited executable path is inside the workspace"
        try:
            inherited_path = Path(inherited).resolve(strict=True)
        except (OSError, RuntimeError):
            return None, "the inherited executable path could not be resolved safely"
        if path_is_within(inherited_path, root):
            return None, "the inherited executable resolves inside the workspace"
    sanitized_path = sanitized_executable_path(workspace=root)
    resolved = shutil.which(executable, path=sanitized_path)
    if resolved is None:
        return None, "the executable was not found on Click's sanitized PATH"
    resolved_lexical = Path(os.path.abspath(resolved))
    if path_is_within(resolved_lexical, root):
        return None, "the executable path is inside the workspace"
    try:
        resolved_path = Path(resolved).resolve(strict=True)
    except (OSError, RuntimeError):
        return None, "the executable path could not be resolved safely"
    if path_is_within(resolved_path, root):
        return None, "the executable resolves inside the workspace"
    if not resolved_path.is_file():
        return None, "the executable does not resolve to a regular file"
    return str(resolved_path), ""


def sanitized_read_only_environment(*, workspace: Path | None = None) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() != "PATH" and not unsafe_inherited_environment_key(key)
    }
    environment["PATH"] = sanitized_executable_path(workspace=workspace)
    return environment


def sanitized_git_environment(
    source: dict[str, str] | None = None, *, workspace: Path | None = None
) -> dict[str, str]:
    inherited = os.environ if source is None else source
    environment = {
        key: value
        for key, value in inherited.items()
        if not key.upper().startswith("GIT_")
        and key.upper() != "PATH"
        and not unsafe_inherited_environment_key(key)
    }
    environment["PATH"] = sanitized_executable_path(
        inherited.get("PATH", ""), workspace=workspace
    )
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    return environment


def execution_argv(argv: list[str]) -> list[str]:
    parts = structured_ssh_parts(argv)
    if parts is None:
        return argv
    target, remote_argv = parts
    safe_git_argv, error = build_read_only_git_argv(remote_argv)
    if error or safe_git_argv is None:
        return argv
    return [
        argv[0], "-n", "-F", "none",
        "-o", "BatchMode=yes",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "PasswordAuthentication=no",
        "-o", "NumberOfPasswordPrompts=0",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "UpdateHostKeys=no",
        "-o", "ConnectTimeout=10",
        "-o", "ConnectionAttempts=1",
        "-o", "ServerAliveInterval=5",
        "-o", "ServerAliveCountMax=1",
        "-o", "ClearAllForwardings=yes",
        "-o", "ForwardAgent=no",
        "-o", "PermitLocalCommand=no",
        "-o", "RemoteCommand=none",
        "-o", "RequestTTY=no",
        target,
        shlex.join(safe_git_argv),
    ]


def is_git_remote_output_request(argv: list[str]) -> bool:
    parts = structured_ssh_parts(argv)
    git_argv = parts[1] if parts is not None else argv
    return git_subcommand(git_argv) == "remote"


def redact_git_remote_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        if "://" not in value:
            return value
        scheme, remainder = value.split("://", 1)
        remainder = remainder.rsplit("@", 1)[-1]
        return f"{scheme}://{remainder.split('?', 1)[0].split('#', 1)[0]}"
    if parsed.scheme and parsed.netloc:
        netloc = parsed.netloc.rsplit("@", 1)[-1]
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    if re.fullmatch(r"[^/@\s]+@[^/\s:]+:.+", value):
        return value.rsplit("@", 1)[-1].split("?", 1)[0].split("#", 1)[0]
    return value


def redact_git_remote_output(data: bytes) -> bytes:
    lines = []
    for line in data.decode("utf-8", errors="replace").splitlines(keepends=True):
        value = line.rstrip("\r\n")
        lines.append(redact_git_remote_url(value) + line[len(value) :])
    return "".join(lines).encode()


def write_runner_stream(handle: Any | None, data: bytes, *, error: bool = False) -> None:
    if handle is not None:
        handle.write(data)
        return
    target = sys.stderr.buffer if error else sys.stdout.buffer
    target.write(data)
    target.flush()


def execute_argv_commands(
    commands: list[list[str]],
    stdout_file: Any | None = None,
    stderr_file: Any | None = None,
    *,
    trusted_read_only: bool = False,
    workspace: Path | None = None,
    environment: dict[str, str] | None = None,
) -> int:
    exit_code = 0
    for argv in commands:
        try:
            redact = is_git_remote_output_request(argv)
            prepared = execution_argv(argv)
            if trusted_read_only:
                executable, error = resolve_read_only_executable(argv[0], workspace=workspace)
                if error or executable is None:
                    write_runner_stream(
                        stderr_file,
                        (
                            "Click rejected the read-only executable at execution time: "
                            f"{error}.\n"
                        ).encode(),
                        error=True,
                    )
                    return 2
                prepared[0] = executable
            result = click_process.run_argv(
                prepared,
                stdout=subprocess.PIPE if redact else stdout_file,
                stderr=subprocess.PIPE if redact else stderr_file,
                env=(
                    sanitized_read_only_environment(workspace=workspace)
                    if trusted_read_only
                    else environment
                ),
            )
            if redact:
                write_runner_stream(stdout_file, redact_git_remote_output(result.stdout or b""))
                write_runner_stream(
                    stderr_file,
                    redact_git_remote_output(result.stderr or b""),
                    error=True,
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


def execute_native_get_content(
    argv: list[str], stdout_file: Any | None, stderr_file: Any | None
) -> int | None:
    if Path(argv[0]).name.lower() != "get-content":
        return None
    paths = get_content_paths(argv)
    if paths is None:
        write_runner_stream(
            stderr_file,
            b"Click Get-Content inspection supports only positional paths, "
            b"-Path, -LiteralPath, and -Raw.\n",
            error=True,
        )
        return 2
    try:
        for path in paths:
            write_runner_stream(stdout_file, Path(path).read_bytes())
    except OSError as exc:
        write_runner_stream(
            stderr_file, f"Click could not read {path}: {exc}\n".encode(), error=True
        )
        return 1
    return 0


def execute_read_only_git(
    argv: list[str],
    stdout_file: Any | None,
    stderr_file: Any | None,
    *,
    workspace: Path | None = None,
) -> int:
    safe_argv, error = build_read_only_git_argv(argv)
    if error or safe_argv is None:
        write_runner_stream(
            stderr_file,
            f"Click rejected Git inspection at execution time: {error}\n".encode(),
            error=True,
        )
        return 2
    executable, executable_error = resolve_read_only_executable(argv[0], workspace=workspace)
    if executable_error or executable is None:
        write_runner_stream(
            stderr_file,
            (
                "Click rejected the Git executable at execution time: "
                f"{executable_error}.\n"
            ).encode(),
            error=True,
        )
        return 2
    safe_argv[0] = executable
    try:
        redact = is_git_remote_output_request(argv)
        result = click_process.run_argv(
            safe_argv,
            stdout=subprocess.PIPE if redact else stdout_file,
            stderr=subprocess.PIPE if redact else stderr_file,
            env=sanitized_git_environment(workspace=workspace),
        )
        if redact:
            write_runner_stream(stdout_file, redact_git_remote_output(result.stdout or b""))
            write_runner_stream(
                stderr_file,
                redact_git_remote_output(result.stderr or b""),
                error=True,
            )
        return int(result.returncode)
    except OSError as exc:
        write_runner_stream(
            stderr_file, f"Click could not start `git`: {exc}\n".encode(), error=True
        )
        return 127


def execute_commands(
    commands: list[list[str]],
    stdout_file: Any | None = None,
    stderr_file: Any | None = None,
    *,
    workspace: Path | None = None,
) -> int:
    for argv in commands:
        native_result = execute_native_get_content(argv, stdout_file, stderr_file)
        if native_result is not None:
            if native_result != 0:
                return native_result
            continue
        if argv[0].lower() in {"git", "git.exe"}:
            exit_code = execute_read_only_git(
                argv, stdout_file, stderr_file, workspace=workspace
            )
        else:
            exit_code = execute_argv_commands(
                [argv],
                stdout_file,
                stderr_file,
                trusted_read_only=True,
                workspace=workspace,
            )
        if exit_code != 0:
            return exit_code
    return 0


def runner_command(
    request: dict[str, Any],
    *,
    runner_script: Path,
    render_command: RenderRunnerCommand,
) -> str:
    return render_command(
        [
            sys.executable,
            str(runner_script),
            "run-inspection-once",
            click_capability.encode_request(request),
        ]
    )


def run_once(
    arguments: list[str],
    *,
    run_request: RunRequest,
    protocol_version: int = click_capability.PROTOCOL_VERSION,
) -> int:
    if len(arguments) != 1:
        sys.stderr.write("usage: click_gate.py run-inspection-once <request>\n")
        return 2
    raw, error = click_capability.decode_encoded_request(arguments[0], "inspection")
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    request, _, error = validate_request(raw, protocol_version=protocol_version)
    if error:
        sys.stderr.write(f"{error}\n")
        return 2
    assert request is not None
    return run_request(request)
