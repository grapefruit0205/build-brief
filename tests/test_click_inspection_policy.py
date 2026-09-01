from __future__ import annotations

import ast
from pathlib import Path
import unittest

from hooks import click_inspection, click_inspection_policy


class ClickInspectionPolicyTests(unittest.TestCase):
    def test_policy_leaf_has_no_runtime_or_upward_dependency(self) -> None:
        source = Path(click_inspection_policy.__file__).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported.add(module)
                imported.update(
                    f"{module}.{alias.name}".strip(".") for alias in node.names
                )

        for forbidden in (
            "click_inspection",
            "click_process",
            "click_state",
            "click_observation",
            "click_lifecycle",
            "click_gate",
            "click_host_coverage",
            "click_host_router",
            "platform_protocol",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(
                    any(forbidden in name.split(".") for name in imported),
                    imported,
                )
        self.assertIn("click_capability", imported)

    def test_inspection_facade_reexports_exact_policy_objects(self) -> None:
        constants = (
            "REQUEST_FIELDS",
            "READ_ONLY_COMMANDS",
            "READ_ONLY_GIT_SUBCOMMANDS",
            "GIT_DIFF_RENDERING_SUBCOMMANDS",
            "GIT_GLOBAL_ALLOWED_PREFIXES",
            "GIT_GLOBAL_REJECTED_OPTIONS",
            "GIT_READ_ONLY_EXACT_OPTIONS",
            "GIT_READ_ONLY_OPTION_PREFIXES",
            "SED_READ_SCRIPT",
            "RG_OPTIONS_WITH_VALUES",
            "SSH_TARGET",
            "SSH_READ_ONLY_GIT_SUBCOMMANDS",
            "GIT_REMOTE_NAME",
        )
        functions = (
            "validate_request",
            "git_option_allowed",
            "is_read_only_git_remote_arguments",
            "parse_read_only_git_tokens",
            "git_subcommand",
            "build_read_only_git_argv",
            "is_read_only_sed",
            "get_content_paths",
            "is_read_only_pdfinfo",
            "is_stdout_only_pdftotext",
            "structured_ssh_parts",
            "is_path_qualified_executable",
            "is_local_read_only_tokens",
            "is_read_only_tokens",
            "direct_command_tokens",
            "request_from_bash",
            "is_read_only_bash",
            "targets_repository_root",
            "is_broad_exploration_tokens",
        )
        for name in (*constants, *functions):
            with self.subTest(name=name):
                self.assertIs(
                    getattr(click_inspection, name),
                    getattr(click_inspection_policy, name),
                )
        self.assertEqual(
            click_inspection.MAX_COMMANDS,
            click_inspection_policy.MAX_COMMANDS,
        )

    def test_runtime_functions_remain_outside_the_policy_leaf(self) -> None:
        source = Path(click_inspection_policy.__file__).read_text(encoding="utf-8")
        for excluded in (
            "def resolve_read_only_executable(",
            "def sanitized_read_only_environment(",
            "def execute_argv_commands(",
            "def execute_read_only_git(",
            "def redact_git_remote_output(",
            "def runner_command(",
            "def run_once(",
        ):
            with self.subTest(excluded=excluded):
                self.assertNotIn(excluded, source)


if __name__ == "__main__":
    unittest.main()
