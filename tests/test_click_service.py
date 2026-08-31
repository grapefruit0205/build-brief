from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

from hooks import click_gate, click_service


class ClickServiceTests(unittest.TestCase):
    def test_service_module_depends_only_on_state_and_process_runtime_leaves(self) -> None:
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
        self.assertIn("click_process", imported)
        self.assertIn("click_state", imported)

    def test_gate_keeps_service_compatibility_aliases(self) -> None:
        aliases = {
            "_fresh_service_state": click_service.fresh_state,
            "_looks_like_managed_service": click_service.looks_like_managed_service,
            "_request_service_stop": click_service.request_stop,
            "_service_snapshot": click_service.service_snapshot,
            "_record_service_fields": click_service.record_service_fields,
            "_claim_service_runner": click_service.claim_service_runner,
        }
        for name, expected in aliases.items():
            with self.subTest(name=name):
                self.assertIs(getattr(click_gate, name), expected)

        self.assertIs(
            click_gate.SERVICE_REQUEST_FIELDS,
            click_service.SERVICE_REQUEST_FIELDS,
        )
        self.assertEqual(
            click_gate.SERVICE_START_TIMEOUT_SECONDS,
            click_service.SERVICE_START_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            click_gate.SERVICE_STOP_TIMEOUT_SECONDS,
            click_service.SERVICE_STOP_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            click_gate.MANAGED_SERVICE_MAX_SECONDS,
            click_service.MANAGED_SERVICE_MAX_SECONDS,
        )

    def test_service_validation_preserves_exact_errors_and_normalization(self) -> None:
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
                value, error = click_gate._validate_service_request(raw)
                self.assertIsNone(value)
                self.assertEqual(error, expected)

        stop, error = click_gate._validate_service_request(
            json.dumps({"version": 1, "action": "stop"})
        )
        self.assertEqual(error, "")
        self.assertEqual(stop, {"version": 1, "action": "stop"})

        start, error = click_gate._validate_service_request(
            json.dumps({"version": 1, "action": "start", "argv": ["vite"]})
        )
        self.assertEqual(error, "")
        self.assertEqual(
            start,
            {"version": 1, "action": "start", "argv": ["vite"]},
        )


if __name__ == "__main__":
    unittest.main()
