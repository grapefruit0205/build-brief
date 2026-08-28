from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def replace_regex(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one regex match, found {count}")
    return updated


def edit_hook() -> None:
    path = ROOT / "hooks" / "click_gate.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "STATE_TTL_SECONDS = 7 * 24 * 60 * 60\n",
        "EPHEMERAL_STATE_TTL_SECONDS = 7 * 24 * 60 * 60\n"
        "COMPLETED_CONTRACT_TTL_SECONDS = 30 * 24 * 60 * 60\n",
        "split state TTL constants",
    )

    old_git_block = '''READ_ONLY_GIT_SUBCOMMANDS = {
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
'''
    new_git_block = '''READ_ONLY_GIT_SUBCOMMANDS = {
    "check-ignore",
    "describe",
    "diff",
    "for-each-ref",
    "log",
    "ls-files",
    "ls-tree",
    "name-rev",
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
    "name-rev": {"--tags", "--all", "--stdin", "--name-only", "--no-undefined", "--always"},
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
        "--short", "--porcelain", "--branch", "--show-stash", "--long", "--verbose",
        "--ignored", "--no-renames", "-s", "-b", "-v", "-vv", "-sb",
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
        "--format=", "--sort=", "--count=", "--points-at=", "--merged=", "--no-merged=",
        "--contains=", "--no-contains=",
    ),
    "log": (
        "--format=", "--pretty=", "--date=", "--since=", "--after=", "--until=",
        "--before=", "--author=", "--committer=", "--grep=", "--max-count=", "--skip=",
        "--abbrev=", "--decorate=", "--stat=", "--relative=", "--unified=",
        "--word-diff=", "--word-diff-regex=", "--src-prefix=", "--dst-prefix=",
        "--line-prefix=", "--ignore-submodules=", "--submodule=", "--diff-filter=",
    ),
    "ls-files": (
        "--exclude=", "--exclude-from=", "--exclude-per-directory=", "--format=",
        "--with-tree=", "--abbrev=",
    ),
    "ls-tree": ("--format=", "--abbrev="),
    "name-rev": ("--refs=", "--exclude="),
    "rev-parse": ("--short=", "--abbrev-ref=", "--path-format=", "--disambiguate="),
    "show": (
        "--format=", "--pretty=", "--date=", "--stat=", "--relative=", "--unified=",
        "--word-diff=", "--word-diff-regex=", "--src-prefix=", "--dst-prefix=",
        "--line-prefix=", "--ignore-submodules=", "--submodule=", "--diff-filter=",
    ),
    "status": ("--porcelain=", "--ignored=", "--find-renames="),
}
'''
    text = replace_once(text, old_git_block, new_git_block, "replace Git read-only policy")

    old_prompt_funcs = '''def _record_user_prompt(event: dict[str, Any]) -> None:
    turn_id = str(event.get("turn_id", ""))
    if not turn_id:
        raise ValueError("Click requires the Codex turn_id on UserPromptSubmit")
    _write_json(
        _prompt_path(event),
        {"turn_id": turn_id, "updated_at": int(time.time())},
    )


def _read_user_prompt_turn(event: dict[str, Any]) -> str:
    try:
        value = json.loads(_prompt_path(event).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""
    if not isinstance(value, dict):
        return ""
    return str(value.get("turn_id", ""))
'''
    new_prompt_funcs = '''def _prompt_authorization(prompt: Any) -> str:
    if not isinstance(prompt, str) or not prompt:
        return ""
    first_line = prompt.splitlines()[0] if prompt.splitlines() else ""
    return {
        "@Click bypass": "bypass",
        "@Click cancel": "cancel",
    }.get(first_line, "")


def _record_user_prompt(event: dict[str, Any]) -> str:
    turn_id = str(event.get("turn_id", ""))
    if not turn_id:
        raise ValueError("Click requires the Codex turn_id on UserPromptSubmit")
    authorization = _prompt_authorization(event.get("prompt", ""))
    _write_json(
        _prompt_path(event),
        {
            "turn_id": turn_id,
            "authorization": authorization,
            "updated_at": int(time.time()),
        },
    )
    return authorization


def _read_user_prompt_state(event: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(_prompt_path(event).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_user_prompt_turn(event: dict[str, Any]) -> str:
    return str(_read_user_prompt_state(event).get("turn_id", ""))


def _consume_user_authorization(event: dict[str, Any], expected: str) -> str:
    turn_id = str(event.get("turn_id", ""))
    if not turn_id:
        return f"Click {expected} requires a current Codex turn_id."
    state = _read_user_prompt_state(event)
    if str(state.get("turn_id", "")) != turn_id:
        return (
            f"Click {expected} requires an exact first-line `@Click {expected}` "
            "directive in this user turn."
        )
    if state.get("authorization") != expected:
        return (
            f"Click {expected} requires an exact first-line `@Click {expected}` "
            "directive in this user turn."
        )
    state["authorization"] = ""
    state["updated_at"] = int(time.time())
    _write_json(_prompt_path(event), state)
    return ""
'''
    text = replace_once(text, old_prompt_funcs, new_prompt_funcs, "add user authorization markers")

    old_prune = '''def _prune_state() -> None:
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
'''
    new_prune = '''def _prune_state() -> None:
    root = _state_root()
    if not root.exists():
        return
    now = time.time()
    for candidate in root.glob("*.json"):
        try:
            age = now - candidate.stat().st_mtime
        except OSError:
            continue
        ttl = EPHEMERAL_STATE_TTL_SECONDS
        if candidate.name.startswith("session-contract-"):
            try:
                value = json.loads(candidate.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                value = {}
            if isinstance(value, dict) and _session_contract_is_active(value):
                continue
            if isinstance(value, dict) and _contract_is_completed(value):
                ttl = COMPLETED_CONTRACT_TTL_SECONDS
        if age <= ttl:
            continue
        try:
            candidate.unlink()
        except OSError:
            continue
'''
    text = replace_once(text, old_prune, new_prune, "split prune policy")

    old_control = '''    if len(tokens) == 2 and tokens[1] in {"arm", "bypass", "review"}:
        return tokens[1], "", ""
'''
    new_control = '''    if len(tokens) == 2 and tokens[1] in {"arm", "bypass", "cancel", "review"}:
        return tokens[1], "", ""
'''
    text = replace_once(text, old_control, new_control, "add cancel control command")
    text = replace_once(
        text,
        '        f"`{CONTROL_COMMAND} review`, `{CONTROL_COMMAND} bypass`, "\n',
        '        f"`{CONTROL_COMMAND} review`, `{CONTROL_COMMAND} bypass`, "\n'
        '        f"`{CONTROL_COMMAND} cancel`, "\n',
        "document cancel in control help",
    )

    old_git_subcommand = '''def _git_subcommand(tokens: list[str]) -> str:
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
'''
    new_git_subcommand = '''def _git_option_allowed(subcommand: str, token: str) -> bool:
    if token in GIT_READ_ONLY_EXACT_OPTIONS.get(subcommand, set()):
        return True
    if any(
        token.startswith(prefix)
        for prefix in GIT_READ_ONLY_OPTION_PREFIXES.get(subcommand, ())
    ):
        return True
    if subcommand in GIT_DIFF_RENDERING_SUBCOMMANDS and re.fullmatch(r"-U\\d+", token):
        return True
    if subcommand == "log" and re.fullmatch(r"-\\d+", token):
        return True
    return False


def _parse_read_only_git_tokens(
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
        if argument.startswith("-") and not _git_option_allowed(subcommand, argument):
            return None
    return global_arguments, subcommand, arguments


def _git_subcommand(tokens: list[str]) -> str:
    parsed = _parse_read_only_git_tokens(tokens)
    return parsed[1] if parsed is not None else ""


def _sanitized_git_environment(
    source: dict[str, str] | None = None,
) -> dict[str, str]:
    inherited = os.environ if source is None else source
    environment = {
        key: value
        for key, value in inherited.items()
        if not key.upper().startswith("GIT_")
    }
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    return environment


def _build_read_only_git_argv(tokens: list[str]) -> tuple[list[str] | None, str]:
    parsed = _parse_read_only_git_tokens(tokens)
    if parsed is None:
        return None, "Git argv is outside Click's supported read-only option policy."
    global_arguments, subcommand, arguments = parsed
    forced = ["--no-ext-diff", "--no-textconv"] if subcommand in GIT_DIFF_RENDERING_SUBCOMMANDS else []
    return [
        "git",
        "--no-pager",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        *global_arguments,
        subcommand,
        *forced,
        *arguments,
    ], ""
'''
    text = replace_once(text, old_git_subcommand, new_git_subcommand, "replace Git parser")

    old_git_readonly = '''    executable = Path(tokens[0]).name.lower()
    if executable == "git":
        if _git_subcommand(tokens) not in READ_ONLY_GIT_SUBCOMMANDS:
            return False
        return not any(
            token in {"--ext-diff", "--textconv"}
            or token.startswith("--output")
            or token.startswith("--open-files-in-pager")
            for token in tokens[1:]
        )
'''
    new_git_readonly = '''    executable = Path(tokens[0]).name.lower()
    if executable in {"git", "git.exe"}:
        return _parse_read_only_git_tokens(tokens) is not None
'''
    text = replace_once(text, old_git_readonly, new_git_readonly, "use positive Git policy")

    old_prompt_start = '''def _handle_prompt_submit(event: dict[str, Any]) -> None:
    _prune_state()
    _record_user_prompt(event)
    default_mode = _read_default_mode()
'''
    new_prompt_start = '''def _handle_prompt_submit(event: dict[str, Any]) -> None:
    _prune_state()
    authorization = _record_user_prompt(event)
    default_mode = _read_default_mode()
'''
    text = replace_once(text, old_prompt_start, new_prompt_start, "capture prompt authorization")

    old_emit_prompt = '''    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            }
        }
    )
'''
    new_emit_prompt = '''    if authorization:
        context += (
            f" The user's exact first-line `@Click {authorization}` directive authorizes "
            f"one `click-gate {authorization}` in this turn only. Do not reuse that "
            "authorization in another tool call or later turn."
        )
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            }
        }
    )
'''
    text = replace_once(text, old_emit_prompt, new_emit_prompt, "add auth prompt context")

    old_bypass = '''            if action == "bypass":
                _prune_state()
                _write_state(event, "bypassed")
                _clear_contract_state(event)
                _clear_review_state(event)
                _allow_rewritten("echo Click bypassed for this turn")
                return
'''
    new_bypass = '''            if action == "bypass":
                _prune_state()
                authorization_error = _consume_user_authorization(event, "bypass")
                if authorization_error:
                    _deny(authorization_error)
                    return
                _write_state(event, "bypassed")
                _clear_review_state(event)
                _allow_rewritten("echo Click bypassed for this turn")
                return
            if action == "cancel":
                _prune_state()
                authorization_error = _consume_user_authorization(event, "cancel")
                if authorization_error:
                    _deny(authorization_error)
                    return
                _clear_contract_state(event)
                _clear_review_state(event)
                _write_state(event, "idle")
                _allow_rewritten("echo Click active contract cancelled")
                return
'''
    text = replace_once(text, old_bypass, new_bypass, "authorize bypass and cancel")

    old_status_plan = '''    status = _read_state(event).get("status")
    if _is_plan_tool(tool_name):
'''
    new_status_plan = '''    status = _read_state(event).get("status")
    if status == "bypassed":
        return
    if _is_plan_tool(tool_name):
'''
    text = replace_once(text, old_status_plan, new_status_plan, "make bypass cover one whole turn")

    text = replace_once(
        text,
        '''            "`click-gate bypass`."\n''',
        '''            "`click-gate bypass` only after the current user turn begins with the exact "\n            "first-line directive `@Click bypass`. Use `@Click cancel` plus `click-gate cancel` "\n            "to discard an active contract instead of bypassing it."\n''',
        "update bypass denial guidance",
    )

    old_execute_inspection = '''def _execute_inspection_commands(
    commands: list[list[str]], stdout_file: Any | None = None, stderr_file: Any | None = None
) -> int:
    for argv in commands:
        native_result = _execute_native_get_content(argv, stdout_file, stderr_file)
        if native_result is not None:
            if native_result != 0:
                return native_result
            continue
        exit_code = _execute_argv_commands([argv], stdout_file, stderr_file)
        if exit_code != 0:
            return exit_code
    return 0
'''
    new_execute_inspection = '''def _execute_read_only_git(
    argv: list[str], stdout_file: Any | None, stderr_file: Any | None
) -> int:
    safe_argv, error = _build_read_only_git_argv(argv)
    if error or safe_argv is None:
        _write_runner_stream(
            stderr_file,
            f"Click rejected Git inspection at execution time: {error}\\n".encode(),
            error=True,
        )
        return 2
    try:
        result = subprocess.run(
            safe_argv,
            stdout=stdout_file,
            stderr=stderr_file,
            env=_sanitized_git_environment(),
            check=False,
        )
        return int(result.returncode)
    except OSError as exc:
        _write_runner_stream(
            stderr_file,
            f"Click could not start `git`: {exc}\\n".encode(),
            error=True,
        )
        return 127


def _execute_inspection_commands(
    commands: list[list[str]], stdout_file: Any | None = None, stderr_file: Any | None = None
) -> int:
    for argv in commands:
        native_result = _execute_native_get_content(argv, stdout_file, stderr_file)
        if native_result is not None:
            if native_result != 0:
                return native_result
            continue
        if Path(argv[0]).name.lower() in {"git", "git.exe"}:
            exit_code = _execute_read_only_git(argv, stdout_file, stderr_file)
        else:
            exit_code = _execute_argv_commands([argv], stdout_file, stderr_file)
        if exit_code != 0:
            return exit_code
    return 0
'''
    text = replace_once(text, old_execute_inspection, new_execute_inspection, "dedicated Git executor")

    old_git_capture = '''def _git_capture(cwd: Path, arguments: list[str]) -> bytes | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None
'''
    new_git_capture = '''def _git_capture(cwd: Path, arguments: list[str]) -> bytes | None:
    try:
        result = subprocess.run(
            [
                "git",
                "--no-pager",
                "--no-optional-locks",
                "-c",
                "core.fsmonitor=false",
                *arguments,
            ],
            cwd=cwd,
            env=_sanitized_git_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None
'''
    text = replace_once(text, old_git_capture, new_git_capture, "harden internal Git capture")

    text = replace_once(
        text,
        "def _new_untracked_requires_stale(relative: str) -> bool:\n",
        "def _new_untracked_is_suspicious(relative: str) -> bool:\n",
        "rename new-path classifier",
    )
    old_suspicious_tail = '''    return any(
        parts[index : index + 2] == ["db", "migrate"]
        for index in range(max(0, len(parts) - 1))
    )
'''
    new_suspicious_tail = '''    if any(
        parts[index : index + 2] == ["db", "migrate"]
        for index in range(max(0, len(parts) - 1))
    ):
        return True
    if len(parts) == 1:
        name = parts[0]
        suffix = Path(name).suffix.lower()
        if suffix in {
            ".c", ".cc", ".cpp", ".cs", ".go", ".h", ".hpp", ".java", ".js",
            ".jsx", ".php", ".py", ".rb", ".rs", ".ts", ".tsx",
        }:
            return True
        if name in {
            "cargo.toml", "compose.yaml", "compose.yml", "docker-compose.yaml",
            "docker-compose.yml", "dockerfile", "go.mod", "package-lock.json",
            "package.json", "pnpm-lock.yaml", "pyproject.toml", "requirements.txt",
            "yarn.lock",
        }:
            return True
    return False
'''
    text = replace_once(text, old_suspicious_tail, new_suspicious_tail, "expand suspicious message classifier")

    old_verification_new = '''        suspicious_new = [
            path for path in new_untracked if _new_untracked_requires_stale(path)
        ]
        workspace_changed = (
            after is None
            or after["digest"] != before["digest"]
            or bool(suspicious_new)
        )
'''
    new_verification_new = '''        suspicious_new = [
            path for path in new_untracked if _new_untracked_is_suspicious(path)
        ]
        workspace_changed = (
            after is None
            or after["digest"] != before["digest"]
            or bool(new_untracked)
        )
'''
    text = replace_once(text, old_verification_new, new_verification_new, "fail closed on any new untracked path")
    text = replace_once(
        text,
        '''                    "[Click] New source, configuration, or migration path appeared during "
                    "verification; it is protected as an implementation mutation.\\n"
''',
        '''                    "[Click] A new path looks like source, configuration, or migration "
                    "content; this classification is informational because every new "
                    "non-ignored path already makes verification stale.\\n"
''',
        "make suspicious classification message-only",
    )

    path.write_text(text, encoding="utf-8")


def edit_tests() -> None:
    path = ROOT / "tests" / "test_click_gate.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "import tempfile\nimport unittest\n", "import tempfile\nimport time\nimport unittest\n", "test time import")

    old_bypass_helper = '''    def bypass_gate(self, turn_id: str = "turn-1") -> dict:
        payload = self.pre_tool("Bash", "click-gate bypass", turn_id)
        self.assertIsNotNone(payload)
        return payload
'''
    new_bypass_helper = '''    def bypass_gate(self, turn_id: str = "turn-1") -> dict:
        self.prompt_submit("@Click bypass", turn_id)
        payload = self.pre_tool(
            "Bash", "click-gate bypass", turn_id, submit_prompt=False
        )
        self.assertIsNotNone(payload)
        return payload

    def cancel_gate(self, turn_id: str = "turn-1") -> dict:
        self.prompt_submit("@Click cancel", turn_id)
        payload = self.pre_tool(
            "Bash", "click-gate cancel", turn_id, submit_prompt=False
        )
        self.assertIsNotNone(payload)
        return payload
'''
    text = replace_once(text, old_bypass_helper, new_bypass_helper, "authorize test helpers")

    text = replace_once(
        text,
        '''        self.bypass_gate("turn-2")
        self.arm_gate("turn-3")
        self.stage_gate(full, "turn-3")
        self.arm_gate("turn-4")
        self.pass_gate(full, "turn-4")
        expensive = self.verify_gate(
            ["npx playwright test", "python3 -m unittest discover -s tests"],
            "turn-4",
        )
''',
        '''        self.cancel_gate("turn-3")
        self.arm_gate("turn-4")
        self.stage_gate(full, "turn-4")
        self.arm_gate("turn-5")
        self.pass_gate(full, "turn-5")
        expensive = self.verify_gate(
            ["npx playwright test", "python3 -m unittest discover -s tests"],
            "turn-5",
        )
''',
        "replace contract-discarding bypass in budget test",
    )

    text = replace_regex(
        text,
        r'''    def test_new_untracked_verification_artifact_is_not_a_false_mutation\(self\) -> None:\n.*?(?=    def test_new_source_path_created_during_verification_fails_stale)''',
        '''    def test_new_untracked_verification_artifact_fails_stale(self) -> None:
        (self.workspace / ".gitignore").write_text("__pycache__/\\n", encoding="utf-8")
        (self.workspace / "artifact_test.py").write_text(
            "import unittest\\n"
            "from pathlib import Path\\n\\n"
            "class ArtifactTest(unittest.TestCase):\\n"
            "    def test_writes_disposable_report(self):\\n"
            "        Path('new-report.tmp').write_text('result\\\\n', encoding='utf-8')\\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "artifact_test.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")

        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "artifact_test.ArtifactTest.test_writes_disposable_report",
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("new non-ignored untracked path", result.stderr)
        self.assertTrue((self.workspace / "new-report.tmp").exists())
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["verification"]["status"], "failed")
        self.assertTrue(state["verification"]["workspace_changed"])
        self.assertEqual(state["verification"]["mutation_revision"], 1)

''',
        "generic verification artifact now fails stale",
    )
    text = text.replace("_new_untracked_requires_stale", "_new_untracked_is_suspicious")

    text = replace_regex(
        text,
        r'''    def test_bypass_discards_the_staged_contract\(self\) -> None:\n.*?(?=    def test_valid_contract_is_recorded_and_control_command_is_rewritten)''',
        '''    def test_bypass_preserves_the_staged_contract_for_later_turn(self) -> None:
        self.set_default("manual", "turn-0")
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        bypassed = self.bypass_gate("turn-1")
        self.assertEqual(
            bypassed["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIsNone(
            self.pre_tool(
                "apply_patch",
                "*** Begin Patch\\n*** End Patch",
                turn_id="turn-1",
                submit_prompt=False,
            )
        )
        blocked = self.pre_tool(
            "apply_patch", "*** Begin Patch\\n*** End Patch", turn_id="turn-2"
        )
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "active execution contract",
            blocked["hookSpecificOutput"]["permissionDecisionReason"],
        )
        self.arm_gate("turn-2")
        payload = self.pass_gate(turn_id="turn-2")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "allow")

''',
        "bypass preserves active contract",
    )

    helper_anchor = '''    def test_hook_config_loads_mode_for_each_prompt(self) -> None:
'''
    path_helper = '''    def assert_verification_new_path_behavior(
        self,
        relative: str,
        *,
        ignored: bool = False,
        suspicious: bool = False,
    ) -> None:
        ignore_lines = ["__pycache__/"]
        if ignored:
            ignore_lines.append(relative)
        (self.workspace / ".gitignore").write_text(
            "\\n".join(ignore_lines) + "\\n", encoding="utf-8"
        )
        escaped = repr(relative)
        (self.workspace / "new_path_test.py").write_text(
            "import unittest\\n"
            "from pathlib import Path\\n\\n"
            "class NewPathTest(unittest.TestCase):\\n"
            "    def test_writes_path(self):\\n"
            f"        target = Path({escaped})\\n"
            "        target.parent.mkdir(parents=True, exist_ok=True)\\n"
            "        target.write_text('generated\\\\n', encoding='utf-8')\\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "new_path_test.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(contract, "turn-2")
        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "new_path_test.NewPathTest.test_writes_path",
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        if ignored:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("new non-ignored untracked path", result.stderr)
            return
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("new non-ignored untracked path", result.stderr)
        self.assertIn("batch is stale", result.stderr)
        if suspicious:
            self.assertIn("classification is informational", result.stderr)
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["verification"]["status"], "failed")
        self.assertTrue(state["verification"]["workspace_changed"])
        self.assertEqual(state["verification"]["mutation_revision"], 1)

'''
    text = replace_once(text, helper_anchor, path_helper + helper_anchor, "add new-path test helper")

    security_tests = '''    def test_git_read_only_policy_rejects_pager_config_and_removed_subcommands(self) -> None:
        commands = (
            ["git", "-p", "status"],
            ["git", "--paginate", "status"],
            ["git", "-c", "core.pager=cat", "status"],
            ["git", "--config-env=core.pager=PAGER", "status"],
            ["git", "grep", "-Oless", "needle", "."],
            ["git", "grep", "--open-files-in-pager=less", "needle", "."],
            ["git", "cat-file", "--filters", "HEAD:README.md"],
            ["git", "cat-file", "--textconv", "HEAD:README.md"],
            ["git", "show", "--textconv", "HEAD"],
        )
        for argv in commands:
            with self.subTest(argv=argv):
                denied = self.inspect_gate([argv])
                self.assertEqual(
                    denied["hookSpecificOutput"]["permissionDecision"], "deny"
                )

    def test_git_read_only_policy_uses_hardened_executor_shape(self) -> None:
        for argv in (
            ["git", "status", "--short"],
            ["git", "diff", "--check"],
            ["git", "log", "--oneline"],
        ):
            with self.subTest(argv=argv):
                request, _, error = CLICK_GATE._validate_inspection_request(
                    json.dumps({"version": 1, "commands": [argv]})
                )
                self.assertEqual(error, "")
                self.assertIsNotNone(request)
        safe, error = CLICK_GATE._build_read_only_git_argv(
            ["git", "diff", "--check"]
        )
        self.assertEqual(error, "")
        self.assertIsNotNone(safe)
        assert safe is not None
        self.assertIn("--no-pager", safe)
        self.assertIn("--no-optional-locks", safe)
        self.assertIn("core.fsmonitor=false", safe)
        self.assertIn("--no-ext-diff", safe)
        self.assertIn("--no-textconv", safe)

        environment = CLICK_GATE._sanitized_git_environment(
            {
                "PATH": os.environ.get("PATH", ""),
                "GIT_PAGER": "evil-pager",
                "GIT_EXTERNAL_DIFF": "evil-diff",
                "GIT_CONFIG_COUNT": "1",
            }
        )
        self.assertNotIn("GIT_PAGER", environment)
        self.assertNotIn("GIT_EXTERNAL_DIFF", environment)
        self.assertNotIn("GIT_CONFIG_COUNT", environment)
        self.assertEqual(environment["GIT_OPTIONAL_LOCKS"], "0")

    def test_bypass_requires_exact_same_turn_one_use_authorization(self) -> None:
        self.set_default("on", "turn-0")
        denied = self.pre_tool("Bash", "click-gate bypass", "turn-1")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")

        self.prompt_submit("@Click bypass extra", "turn-2")
        malformed = self.pre_tool(
            "Bash", "click-gate bypass", "turn-2", submit_prompt=False
        )
        self.assertEqual(malformed["hookSpecificOutput"]["permissionDecision"], "deny")

        self.prompt_submit("@Click bypass\\nDo this turn without Click.", "turn-3")
        authorized = self.pre_tool(
            "Bash", "click-gate bypass", "turn-3", submit_prompt=False
        )
        self.assertEqual(authorized["hookSpecificOutput"]["permissionDecision"], "allow")
        reused = self.pre_tool(
            "Bash", "click-gate bypass", "turn-3", submit_prompt=False
        )
        self.assertEqual(reused["hookSpecificOutput"]["permissionDecision"], "deny")

        self.prompt_submit("@Click bypass", "turn-4")
        later = self.pre_tool(
            "Bash", "click-gate bypass", "turn-5", submit_prompt=False
        )
        self.assertEqual(later["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_cancel_requires_authorization_and_clears_contract_once(self) -> None:
        self.set_default("manual", "turn-0")
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")

        denied = self.pre_tool("Bash", "click-gate cancel", "turn-2")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        contract_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        self.assertTrue(contract_path.exists())

        self.prompt_submit("@Click cancel", "turn-3")
        cancelled = self.pre_tool(
            "Bash", "click-gate cancel", "turn-3", submit_prompt=False
        )
        self.assertEqual(cancelled["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertFalse(contract_path.exists())
        reused = self.pre_tool(
            "Bash", "click-gate cancel", "turn-3", submit_prompt=False
        )
        self.assertEqual(reused["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(
            self.pre_tool(
                "apply_patch", "*** Begin Patch\\n*** End Patch", turn_id="turn-4"
            )
        )

    def test_manual_incomplete_contract_survives_eight_day_cleanup(self) -> None:
        self.set_default("manual", "turn-0")
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        contract_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        old = time.time() - 8 * 24 * 60 * 60
        os.utime(contract_path, (old, old))

        self.prompt_submit("continue the approved work", "turn-3")
        self.assertTrue(contract_path.exists())
        blocked = self.pre_tool(
            "Bash", "python3 update_schema.py", "turn-3", submit_prompt=False
        )
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "active execution contract",
            blocked["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_verification_root_main_py_fails_stale(self) -> None:
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("main.py"))
        self.assert_verification_new_path_behavior("main.py", suspicious=True)

    def test_verification_root_package_json_fails_stale(self) -> None:
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("package.json"))
        self.assert_verification_new_path_behavior("package.json", suspicious=True)

    def test_verification_root_dockerfile_fails_stale(self) -> None:
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("Dockerfile"))
        self.assert_verification_new_path_behavior("Dockerfile", suspicious=True)

    def test_verification_generic_report_fails_stale(self) -> None:
        self.assertFalse(CLICK_GATE._new_untracked_is_suspicious("generic-report.txt"))
        self.assert_verification_new_path_behavior("generic-report.txt")

    def test_verification_ignored_artifact_does_not_change_snapshot(self) -> None:
        self.assert_verification_new_path_behavior(
            "ignored-artifact.tmp", ignored=True
        )

'''
    text = replace_once(
        text,
        "\n\nif __name__ == \"__main__\":\n    unittest.main()\n",
        "\n\n" + security_tests + "if __name__ == \"__main__\":\n    unittest.main()\n",
        "add focused hardening regressions",
    )
    path.write_text(text, encoding="utf-8")


def edit_skill() -> None:
    path = ROOT / "skills" / "click" / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "- A question about Click is not a mutation request. If the user opts out for one active turn, run `click-gate bypass` and return to the ordinary workflow for that turn.\n",
        "- A question about Click is not a mutation request. A bypass is valid only when the current user prompt's first line is exactly `@Click bypass`; then run `click-gate bypass` once for that turn. Bypass never clears an active contract. If the first line is exactly `@Click cancel`, run `click-gate cancel` once to discard the active contract.\n",
        "skill bypass semantics",
    )
    text = replace_once(
        text,
        "A protected-content change fails stale, every new non-ignored path is reported, and a new source, application, library, configuration, or migration path also fails stale; generic new report artifacts only warn. Git-ignored paths are outside this snapshot.",
        "A protected-content change fails stale, and every new non-ignored untracked path created by verification also fails stale and advances the mutation revision. Source, application, library, configuration, or migration classification is used only to make the warning clearer. Expected generated artifacts should be ignored or produced during the approved mutation phase. Git-ignored paths are outside this snapshot.",
        "skill verification file semantics",
    )
    path.write_text(text, encoding="utf-8")


def edit_modes() -> None:
    path = ROOT / "skills" / "click" / "references" / "modes.md"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "Once a proposal is staged, or approved but incomplete, that session contract blocks ordinary mutations and plan tools across later turns. On the approval or resume turn, arm and pass the exact same contract before editing. Current-revision completion or an explicit per-turn bypass releases unrelated later work.\n",
        "Once a proposal is staged, or approved but incomplete, that session contract blocks ordinary mutations and plan tools across later turns. On the approval or resume turn, arm and pass the exact same contract before editing. Ephemeral turn, review, prompt, and temporary session state may age out after seven days, but staged and approved-incomplete contracts are never removed by that cleanup. A per-turn bypass suspends enforcement only for its authorized turn; it does not release or erase an active contract.\n",
        "manual TTL and bypass docs",
    )
    text = replace_regex(
        text,
        r'''## Per-turn bypass\n.*?(?=\nThe legacy `click-gate mode strict\|adaptive`)''',
        '''## User-authorized bypass and cancel

A bypass is authorized only when the first line of the current user prompt is exactly:

```text
@Click bypass
```

Then run `click-gate bypass` once in that same turn. The authorization marker is one-use and cannot carry into another turn. Bypass leaves any staged or approved-incomplete contract intact; it only suspends Click enforcement for the authorized turn. The persistent Always ON or Manual preference is unchanged.

To discard an active contract, the first line must instead be exactly:

```text
@Click cancel
```

Then run `click-gate cancel` once in that turn. Cancel clears the active contract and review state but does not change the persistent mode. A bare `click-gate bypass` or `click-gate cancel` without its matching user directive is denied.
''',
        "replace bypass docs",
    )
    path.write_text(text, encoding="utf-8")


def edit_protocol() -> None:
    path = ROOT / "skills" / "click" / "references" / "capability-protocol.md"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "Every command must match the Hook's read-only argv policy. One request may contain up to eight commands, which run serially and stop on the first failure. The Hook rejects shell interpreters and write-capable options. In active review and implementation it stores only a request digest and result metadata, applies the existing output cap and retry policy, and detects repository-wide inventory from the validated argv.\n",
        "Every command must match the Hook's read-only argv policy. One request may contain up to eight commands, which run serially and stop on the first failure. Git inspection uses subcommand-specific positive option policies rather than a generic subcommand allowlist plus dangerous-option blacklist; `git grep` and `git cat-file` are not currently accepted. Global pagination and config overrides such as `-p`, `--paginate`, `-c`, and `--config-env` are rejected. Accepted Git reads run through a dedicated executor that strips inherited `GIT_*` variables, forces `--no-pager` and `--no-optional-locks`, disables fsmonitor, and adds `--no-ext-diff` plus `--no-textconv` to supported diff-rendering commands. The Hook rejects shell interpreters and write-capable options. In active review and implementation it stores only a request digest and result metadata, applies the existing output cap and retry policy, and detects repository-wide inventory from the validated argv.\n",
        "protocol Git executor docs",
    )
    text = replace_once(
        text,
        "A protected-content change fails stale and increments the mutation revision. Every new non-ignored path is reported; an obvious new source, application, library, configuration, or migration path also fails stale, while a generic report artifact only warns. Git-ignored paths and non-Git worktrees are outside this content snapshot.\n",
        "A protected-content change fails stale and increments the mutation revision. Every new non-ignored untracked path created during the batch also fails stale and advances the mutation revision; source or configuration classification affects only the clarity of the message, not whether the workspace changed. Expected generated artifacts should be ignored or created during the approved mutation phase. Git-ignored paths and non-Git worktrees are outside this content snapshot.\n",
        "protocol fail-closed untracked docs",
    )
    path.write_text(text, encoding="utf-8")


def edit_readme_english() -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "You can later say “Set Click to Always ON,” “Set Click to Manual,” or “Skip Click for this task.” The first two preferences persist outside the target repository; the last bypass applies only to the current turn. Click does not place preference or contract files in your project.\n",
        "You can later say “Set Click to Always ON” or “Set Click to Manual.” Those preferences persist outside the target repository. To bypass Click for exactly one turn, make the first line of that user prompt `@Click bypass`; the Hook authorizes one same-turn `click-gate bypass` and keeps any active contract intact. To discard an active contract, use first-line `@Click cancel`, which authorizes one same-turn `click-gate cancel`. Neither authorization is reusable or carries across turns. Click does not place preference or contract files in your project.\n",
        "English quick-start bypass docs",
    )
    text = replace_once(
        text,
        "| User explicitly opts out | Bypass Click for that turn only |\n",
        "| First line is `@Click bypass` | Authorize one bypass for that turn; keep any active contract |\n"
        "| First line is `@Click cancel` | Authorize one cancel that clears the active contract |\n",
        "English Always ON table",
    )
    text = replace_once(
        text,
        "| No parallel planning | Matched `update_plan` calls are rejected while the workflow is armed, staged, approved but incomplete, or in review—even from a later turn. Bypass or current-revision completion releases ordinary later planning. |\n",
        "| No parallel planning | Matched `update_plan` calls are rejected while the workflow is armed, staged, approved but incomplete, or in review—even from a later turn. A user-authorized bypass releases planning only for that turn; current-revision completion releases ordinary later planning. |\n",
        "English plan bypass semantics",
    )
    text = replace_once(
        text,
        "`inspect` accepts only the Hook's bounded read-only operations. `mutate` requires the exact approved contract and marks prior evidence stale. Ordinary canonical edit tools such as `apply_patch`, `Edit`, and `Write` remain supported mutations without a shell envelope. Malformed requests and shell interpreters fail closed. See [the capability protocol](skills/click/references/capability-protocol.md) for the exact schemas and enforcement boundary.\n",
        "`inspect` accepts only the Hook's bounded read-only operations. Git reads use subcommand-specific positive option policies; `git grep` and `git cat-file` are temporarily excluded. Accepted Git inspection runs with inherited `GIT_*` variables sanitized, `--no-pager`, `--no-optional-locks`, fsmonitor disabled, and `--no-ext-diff` plus `--no-textconv` forced for supported diff-rendering commands. `mutate` requires the exact approved contract and marks prior evidence stale. Ordinary canonical edit tools such as `apply_patch`, `Edit`, and `Write` remain supported mutations without a shell envelope. Malformed requests and shell interpreters fail closed. See [the capability protocol](skills/click/references/capability-protocol.md) for the exact schemas and enforcement boundary.\n",
        "English Git capability docs",
    )
    text = replace_once(
        text,
        "It also reports every new non-ignored untracked path. A new path under an obvious source, application, library, configuration, or migration directory is treated as an implementation mutation and fails stale; a generic newly generated report only produces a warning. Git-ignored paths are not visible to this snapshot. Outside Git this content-diff guard is unavailable; argv validation, shell-free execution, and revision state still apply.\n",
        "It also reports every new non-ignored untracked path. Any such path created during final verification is treated as a workspace change, fails stale, and advances the mutation revision. Source or configuration classification is retained only to make the warning clearer. Expected generated artifacts should be Git-ignored or produced during the approved mutation phase. Git-ignored paths are not visible to this snapshot. Outside Git this content-diff guard is unavailable; argv validation, shell-free execution, and revision state still apply.\n",
        "English verification new-file docs",
    )
    text = replace_once(
        text,
        "The v0.17.0 source candidate currently passes 129 deterministic tests locally.",
        "The current source candidate passes __TEST_COUNT__ deterministic tests locally.",
        "English test count",
    )
    path.write_text(text, encoding="utf-8")


def edit_readme_korean() -> None:
    path = ROOT / "README.ko.md"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "나중에 “Click을 Always ON으로 설정해줘”, “Click을 Manual로 설정해줘”, “이번 작업은 Click 없이 해줘”라고 말해 바꿀 수 있습니다. 앞의 두 설정은 대상 저장소 밖 사용자 설정에 유지되고, 마지막 우회는 현재 turn에만 적용됩니다. Click은 프로젝트 안에 설정이나 계약 파일을 만들지 않습니다.\n",
        "나중에 “Click을 Always ON으로 설정해줘” 또는 “Click을 Manual로 설정해줘”라고 바꿀 수 있고, 이 설정은 대상 저장소 밖에 유지됩니다. 정확히 한 turn만 우회하려면 사용자 프롬프트 첫 줄을 `@Click bypass`로 쓰며, Hook은 같은 turn의 `click-gate bypass` 한 번만 승인하고 active 계약은 그대로 보존합니다. active 계약 자체를 버리려면 첫 줄에 `@Click cancel`을 쓰고 같은 turn의 `click-gate cancel` 한 번을 사용합니다. 두 권한은 재사용하거나 다음 turn으로 가져갈 수 없습니다. Click은 프로젝트 안에 설정이나 계약 파일을 만들지 않습니다.\n",
        "Korean quick-start bypass docs",
    )
    text = replace_once(
        text,
        "| 사용자가 명시적으로 제외 | 현재 turn에서만 Click 우회 |\n",
        "| 첫 줄이 `@Click bypass` | 해당 turn의 우회 한 번을 승인하고 active 계약은 유지 |\n"
        "| 첫 줄이 `@Click cancel` | active 계약을 지우는 cancel 한 번을 승인 |\n",
        "Korean Always ON table",
    )
    text = replace_once(
        text,
        "| 병렬 계획 금지 | workflow가 armed·staged·승인 후 미완료·review 상태인 동안 이후 turn에서도 `update_plan`을 거부합니다. bypass하거나 현재 revision 검증을 완료하면 이후 일반 계획은 다시 허용합니다. |\n",
        "| 병렬 계획 금지 | workflow가 armed·staged·승인 후 미완료·review 상태인 동안 이후 turn에서도 `update_plan`을 거부합니다. 사용자 승인 bypass는 그 turn의 계획만 허용하고, 현재 revision 검증을 완료해야 이후 일반 계획이 다시 허용됩니다. |\n",
        "Korean plan bypass semantics",
    )
    text = replace_once(
        text,
        "`inspect`는 Hook이 허용한 제한된 읽기 전용 작업만 받습니다. `mutate`는 정확한 계약 승인이 있어야 하고 이전 근거를 오래된 것으로 표시합니다. `apply_patch`, `Edit`, `Write` 같은 명확한 편집 도구는 shell envelope 없이 그대로 지원합니다. 잘못된 요청과 shell interpreter는 fail-closed로 거부합니다. 정확한 schema와 적용 경계는 [capability protocol](skills/click/references/capability-protocol.md)에 있습니다.\n",
        "`inspect`는 Hook이 허용한 제한된 읽기 전용 작업만 받습니다. Git 조회는 subcommand별 positive option policy를 사용하며 `git grep`과 `git cat-file`은 현재 제외합니다. 허용된 Git 조회는 상속된 `GIT_*` 변수를 제거하고 `--no-pager`, `--no-optional-locks`, fsmonitor 비활성화를 강제하며, 지원되는 diff 출력 명령에는 `--no-ext-diff`와 `--no-textconv`도 강제로 붙입니다. `mutate`는 정확한 계약 승인이 있어야 하고 이전 근거를 오래된 것으로 표시합니다. `apply_patch`, `Edit`, `Write` 같은 명확한 편집 도구는 shell envelope 없이 그대로 지원합니다. 잘못된 요청과 shell interpreter는 fail-closed로 거부합니다. 정확한 schema와 적용 경계는 [capability protocol](skills/click/references/capability-protocol.md)에 있습니다.\n",
        "Korean Git capability docs",
    )
    text = replace_once(
        text,
        "검증 뒤 새로 생긴 non-ignored untracked 경로는 모두 경고합니다. source·app·lib·config·migration처럼 명백한 구현 경로 아래 새 파일은 mutation으로 보고 stale 실패시키며, 일반 report 산출물은 경고만 합니다. Git에서 ignored인 경로는 이 snapshot으로 볼 수 없습니다. Git 밖에서는 content-diff 안전망을 사용할 수 없지만 argv 검증, shell 없는 실행, revision 상태 검사는 계속 적용됩니다.\n",
        "검증 뒤 새로 생긴 non-ignored untracked 경로는 모두 보고하며, 경로 종류와 무관하게 workspace 변경으로 처리해 stale 실패시키고 mutation revision을 올립니다. source·config처럼 의심스러운 분류는 메시지를 더 명확하게 보여주는 데만 사용합니다. 검증 중 생성이 예상되는 산출물은 Git ignore 대상으로 두거나 승인된 mutation 단계에서 미리 생성해야 합니다. Git에서 ignored인 경로는 이 snapshot으로 볼 수 없습니다. Git 밖에서는 content-diff 안전망을 사용할 수 없지만 argv 검증, shell 없는 실행, revision 상태 검사는 계속 적용됩니다.\n",
        "Korean verification new-file docs",
    )
    text = replace_once(
        text,
        "v0.17.0 소스 후보는 현재 로컬에서 결정적 테스트 129개를 통과했습니다.",
        "현재 소스 후보는 로컬에서 결정적 테스트 __TEST_COUNT__개를 통과합니다.",
        "Korean test count",
    )
    path.write_text(text, encoding="utf-8")


def write_release_notes() -> None:
    path = ROOT / "RELEASE_NOTES.md"
    path.write_text(
        """# Release notes\n\n## Unreleased — enforcement-boundary hardening\n\nThis candidate hardens Click without expanding product scope.\n\n- Git inspection now uses subcommand-specific positive option policies and a dedicated sanitized executor. `git grep` and `git cat-file` are temporarily excluded; pager/config override paths are rejected; inherited `GIT_*` variables are stripped; supported diff rendering is forced through `--no-ext-diff` and `--no-textconv`.\n- `click-gate bypass` now requires an exact first-line `@Click bypass` directive, is same-turn and one-use, and does not clear an active contract. `@Click cancel` separately authorizes one `click-gate cancel` that clears active contract state.\n- Seven-day cleanup applies only to ephemeral state. Staged and approved-incomplete contracts do not expire automatically; completed contracts use a longer cleanup TTL.\n- Final verification now fails stale for every newly created non-ignored untracked path. Source/config classification affects messaging only; expected generated artifacts should be ignored or created during the approved mutation phase.\n\n## Verification\n\n- __TEST_COUNT__ deterministic tests pass locally.\n- Focused regressions cover Git pager/config execution paths, removed Git subcommands, same-turn one-use bypass/cancel authorization, eight-day Manual incomplete-contract persistence, root-level source/config files, generic reports, and ignored verification artifacts.\n- The runtime remains standard-library-only and keeps external state content-free.\n\nThis is a release-note draft for the next Click release; it does not publish a new version or claim new A/B benchmark results.\n""",
        encoding="utf-8",
    )


def main() -> None:
    edit_hook()
    edit_tests()
    edit_skill()
    edit_modes()
    edit_protocol()
    edit_readme_english()
    edit_readme_korean()
    write_release_notes()


if __name__ == "__main__":
    main()
