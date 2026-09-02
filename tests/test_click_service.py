from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

from hooks import click_capability, click_service


class ClickServiceTests(unittest.TestCase):
    def test_service_module_depends_only_on_contract_state_and_process_leaves(self) -> None:
        source = Path(click_service.__file__).read_text(encoding="utf-8")
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
            "click_browser_advisory",
            "click_contract",
            "click_dependency_cache",
            "click_evidence",
            "click_gate",
            "click_host_coverage",
            "click_verification_meter",
            "click_verification_policy",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(
                    any(forbidden in name.split(".") for name in imported),
                    imported,
                )
        self.assertIn("click_claims", imported)
        self.assertIn("click_contract_state", imported)
        self.assertIn("click_process", imported)
        self.assertIn("click_state", imported)

    def test_service_validation_preserves_exact_errors_and_normalization(self) -> None:
        def validate(raw: str):
            return click_service.validate_request(
                raw,
                validate_argv=click_capability.validate_argv,
                protocol_version=click_capability.PROTOCOL_VERSION,
            )

        cases = (
            ("{", "Managed service request must be valid JSON."),
            ("[]", "Managed service request must be a JSON object."),
            (
                json.dumps({"version": 2, "action": "stop"}),
                "Managed service request `version` must be 1.",
            ),
            (
                json.dumps(
                    {"version": 1, "action": "stop", "z": 1, "a": 2}
                ),
                "Managed service request contains unsupported field(s): `a`, `z`.",
            ),
            (
                json.dumps({"version": 1, "action": "restart"}),
                "Managed service `action` must be one of: start, stop.",
            ),
            (
                json.dumps({"version": 1, "action": "stop", "argv": ["vite"]}),
                "Managed service stop must omit `argv`.",
            ),
            (
                json.dumps({"version": 1, "action": "start", "argv": ["echo"]}),
                "Managed service start accepts a recognizable local development "
                "server, not an arbitrary detached command.",
            ),
        )
        for raw, expected in cases:
            with self.subTest(expected=expected):
                value, error = validate(raw)
                self.assertIsNone(value)
                self.assertEqual(error, expected)

        stop, error = validate(json.dumps({"version": 1, "action": "stop"}))
        self.assertEqual(error, "")
        self.assertEqual(stop, {"version": 1, "action": "stop"})

        start, error = validate(
            json.dumps({"version": 1, "action": "start", "argv": ["vite"]})
        )
        self.assertEqual(error, "")
        self.assertEqual(
            start,
            {"version": 1, "action": "start", "argv": ["vite"]},
        )


if __name__ == "__main__":
    unittest.main()
