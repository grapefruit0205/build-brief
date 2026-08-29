#!/usr/bin/env python3
"""Validate Click's distributable plugin, skills, and pinned release metadata."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
README_NAMES = ("README.md", "README.ko.md", "README.zh-CN.md")


def _json(path: Path, errors: list[str], root: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.relative_to(root)} is not valid readable JSON: {exc}")
        return None


def _frontmatter(path: Path, errors: list[str], root: Path) -> dict[str, str] | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read {path.relative_to(root)}: {exc}")
        return None
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", content, re.DOTALL)
    if match is None:
        errors.append(f"{path.relative_to(root)} has invalid YAML frontmatter fences")
        return None
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if line[:1].isspace() or ":" not in line:
            errors.append(f"{path.relative_to(root)} uses unsupported nested frontmatter")
            return None
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"\'')
    return fields


def _contains_todo(value: Any) -> bool:
    if isinstance(value, str):
        return "[TODO:" in value
    if isinstance(value, list):
        return any(_contains_todo(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_todo(item) for item in value.values())
    return False


def _validate_skill(root: Path, skill_name: str, errors: list[str]) -> None:
    skill_root = root / "skills" / skill_name
    skill_path = skill_root / "SKILL.md"
    fields = _frontmatter(skill_path, errors, root)
    if fields is None:
        return
    unexpected = set(fields) - {"name", "description", "license", "allowed-tools", "metadata"}
    if unexpected:
        errors.append(f"skills/{skill_name}/SKILL.md has unsupported fields: {sorted(unexpected)}")
    if fields.get("name") != skill_name or SKILL_NAME.fullmatch(fields.get("name", "")) is None:
        errors.append(f"skills/{skill_name}/SKILL.md name must be `{skill_name}`")
    description = fields.get("description", "")
    if not description or len(description) > 1024 or "<" in description or ">" in description:
        errors.append(f"skills/{skill_name}/SKILL.md description is invalid")
    if "[TODO:" in skill_path.read_text(encoding="utf-8"):
        errors.append(f"skills/{skill_name}/SKILL.md contains an unfinished TODO")
    metadata_path = skill_root / "agents" / "openai.yaml"
    try:
        metadata = metadata_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read {metadata_path.relative_to(root)}: {exc}")
        return
    expected_implicit = "true" if skill_name == "click" else "false"
    for marker in (
        "interface:",
        "display_name:",
        "short_description:",
        "default_prompt:",
        f"allow_implicit_invocation: {expected_implicit}",
    ):
        if marker not in metadata:
            errors.append(f"{metadata_path.relative_to(root)} is missing `{marker}`")


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    manifest = _json(root / ".codex-plugin" / "plugin.json", errors, root)
    if not isinstance(manifest, dict):
        return errors
    version = manifest.get("version")
    if manifest.get("name") != "click":
        errors.append("plugin name must be `click`")
    if not isinstance(version, str) or SEMVER.fullmatch(version) is None:
        errors.append("plugin version must be strict stable semver")
        version = "invalid"
    if manifest.get("license") != "MIT":
        errors.append("plugin license must be MIT")
    if _contains_todo(manifest):
        errors.append("plugin manifest contains an unfinished TODO")
    interface = manifest.get("interface", {})
    relative_paths = (
        manifest.get("skills"),
        interface.get("composerIcon") if isinstance(interface, dict) else None,
    )
    for relative in relative_paths:
        if not isinstance(relative, str) or not (root / relative).exists():
            errors.append(f"plugin path does not exist: {relative!r}")

    marketplace = _json(root / ".agents" / "plugins" / "marketplace.json", errors, root)
    try:
        entry = marketplace["plugins"][0]
        source = entry["source"]
    except (KeyError, IndexError, TypeError):
        errors.append("marketplace must contain the Click plugin source")
    else:
        if entry.get("name") != "click":
            errors.append("marketplace plugin name must be `click`")
        if source.get("url") != "https://github.com/grapefruit0205/click.git":
            errors.append("marketplace must use Click's canonical Git URL")
        if source.get("ref") != f"v{version}":
            errors.append(f"marketplace ref must be immutable `v{version}`")

    for skill_name in ("click", "fix"):
        _validate_skill(root, skill_name, errors)

    hook_config = _json(root / "hooks" / "hooks.json", errors, root)
    hooks = hook_config.get("hooks", {}) if isinstance(hook_config, dict) else {}
    required_hooks = {"UserPromptSubmit", "PreToolUse", "PostToolUse", "SessionEnd"}
    if not isinstance(hooks, dict) or not required_hooks.issubset(hooks):
        errors.append(
            "hooks/hooks.json must register UserPromptSubmit, PreToolUse, "
            "PostToolUse, and SessionEnd"
        )
    elif "mcp__node_repl__js" not in json.dumps(hooks, sort_keys=True):
        errors.append("hooks/hooks.json must meter the canonical Browser MCP tool")

    release_notes = (root / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    if f"## v{version}" not in release_notes or "## Unreleased" in release_notes:
        errors.append("release notes must identify the current version and contain no Unreleased heading")
    for readme_name in README_NAMES:
        readme = (root / readme_name).read_text(encoding="utf-8")
        if f"v{version}" not in readme:
            errors.append(f"{readme_name} must identify v{version}")

    for json_path in root.rglob("*.json"):
        _json(json_path, errors, root)
    for directory in ("hooks", "evals", "scripts", "tests"):
        for python_path in (root / directory).rglob("*.py"):
            try:
                compile(
                    python_path.read_text(encoding="utf-8"),
                    str(python_path.relative_to(root)),
                    "exec",
                )
            except (OSError, SyntaxError) as exc:
                errors.append(f"{python_path.relative_to(root)} does not compile: {exc}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Click distribution validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "Click distribution validation passed: plugin, marketplace, Click/Fix "
        "skills, metadata, and Python sources"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
