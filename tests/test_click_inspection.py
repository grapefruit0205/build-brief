from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

from hooks import click_gate, click_inspection, click_inspection_policy


class ClickInspectionTests(unittest.TestCase):
    def test_inspection_depends_only_on_policy_capability_and_process_leaves(self) -> None:
        source = Path(click_inspection.__file__).read_text(encoding="utf-8")
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
            "click_browser",
            "click_contract",
            "click_evidence",
            "click_gate",
            "click_mutation",
            "click_observation",
            "click_service",
            "click_state",
            "click_verification_policy",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(
                    any(forbidden in name.split(".") for name in imported),
                    imported,
                )
        self.assertIn("click_capability", imported)
        self.assertIn("click_inspection_policy", imported)
        self.assertIn("click_process", imported)

    def test_gate_keeps_inspection_compatibility_aliases(self) -> None:
        aliases = {
            "_validate_inspection_request": click_inspection.validate_request,
            "_parse_read_only_git_tokens": click_inspection.parse_read_only_git_tokens,
            "_build_read_only_git_argv": click_inspection.build_read_only_git_argv,
            "_is_read_only_tokens": click_inspection.is_read_only_tokens,
            "_direct_command_tokens": click_inspection.direct_command_tokens,
            "_inspection_request_from_bash": click_inspection.request_from_bash,
            "_workspace_boundary": click_inspection.workspace_boundary,
            "_resolve_read_only_executable": click_inspection.resolve_read_only_executable,
            "_execution_argv": click_inspection.execution_argv,
            "_execute_argv_commands": click_inspection.execute_argv_commands,
            "_execute_inspection_commands": click_inspection.execute_commands,
        }
        for name, expected in aliases.items():
            with self.subTest(name=name):
                self.assertIs(getattr(click_gate, name), expected)
        self.assertIs(
            click_gate.INSPECTION_REQUEST_FIELDS,
            click_inspection.REQUEST_FIELDS,
        )
        self.assertEqual(
            click_gate.MAX_INSPECTION_COMMANDS,
            click_inspection.MAX_COMMANDS,
        )

    def test_inspection_validation_preserves_exact_errors_and_scope(self) -> None:
        cases = (
            ("{", "Inspection request must be valid JSON."),
            ("[]", "Inspection request must be a JSON object."),
            (
                json.dumps({"version": 2, "commands": [["cat", "README.md"]]}),
                "Inspection request `version` must be 1.",
            ),
            (
                json.dumps({"version": 1, "commands": [["cat", "README.md"]], "z": 1}),
                "Inspection request contains unsupported field(s): `z`.",
            ),
            (
                json.dumps({"version": 1, "commands": [["python", "tool.py"]]}),
                "Inspection command 1 is not a supported read-only argv operation.",
            ),
        )
        for raw, expected in cases:
            with self.subTest(expected=expected):
                request, broad, error = click_inspection_policy.validate_request(raw)
                self.assertIsNone(request)
                self.assertFalse(broad)
                self.assertEqual(error, expected)

        request, broad, error = click_inspection_policy.validate_request(
            json.dumps({"version": 1, "commands": [["rg", "--files"]]})
        )
        self.assertEqual(error, "")
        self.assertTrue(broad)
        self.assertEqual(request, {"version": 1, "commands": [["rg", "--files"]]})


if __name__ == "__main__":
    unittest.main()
