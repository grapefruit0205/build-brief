from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

from hooks import click_gate, click_mutation


class ClickMutationTests(unittest.TestCase):
    def test_mutation_runtime_has_no_upward_or_sibling_domain_dependency(self) -> None:
        source = Path(click_mutation.__file__).read_text(encoding="utf-8")
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
            "click_gate",
            "click_host_coverage",
            "click_process",
            "click_service",
            "click_verification_meter",
            "click_verification_policy",
            "platform_protocol",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(
                    any(forbidden in name.split(".") for name in imported),
                    imported,
                )
        for required in ("click_dependency_cache", "click_evidence", "click_state"):
            with self.subTest(required=required):
                self.assertIn(required, imported)

    def test_gate_keeps_mutation_compatibility_aliases(self) -> None:
        aliases = {
            "_fresh_mutation_boundary": click_mutation.fresh_boundary,
            "_fresh_mutation_state": click_mutation.fresh_state,
            "_mutation_is_running": click_mutation.is_running,
            "_record_mutation_result": click_mutation.record_result,
        }
        for name, expected in aliases.items():
            with self.subTest(name=name):
                self.assertIs(getattr(click_gate, name), expected)

        self.assertIs(
            click_gate.MUTATION_REQUEST_FIELDS,
            click_mutation.REQUEST_FIELDS,
        )
        self.assertEqual(
            click_gate.MUTATION_RUNNING_TTL_SECONDS,
            click_mutation.RUNNING_TTL_SECONDS,
        )

    def test_mutation_validation_preserves_exact_errors_and_normalization(self) -> None:
        cases = (
            ("{", "Mutation request must be valid JSON."),
            ("[]", "Mutation request must be a JSON object."),
            (
                json.dumps({"version": 2, "argv": ["echo"]}),
                "Mutation request `version` must be 1.",
            ),
            (
                json.dumps({"version": 1, "argv": ["echo"], "z": 1, "a": 2}),
                "Mutation request contains unsupported field(s): `a`, `z`.",
            ),
            (
                json.dumps({"version": 1, "argv": ["vite"]}),
                "Long-running local servers must use `click-gate service` so Click "
                "owns the exact child lifecycle and cannot strand a foreground mutation.",
            ),
        )
        for raw, expected in cases:
            with self.subTest(expected=expected):
                value, error = click_gate._validate_mutation_request(raw)
                self.assertIsNone(value)
                self.assertEqual(error, expected)

        request, error = click_gate._validate_mutation_request(
            json.dumps({"version": 1, "argv": ["python", "build.py"]})
        )
        self.assertEqual(error, "")
        self.assertEqual(
            request,
            {"version": 1, "argv": ["python", "build.py"]},
        )


if __name__ == "__main__":
    unittest.main()
