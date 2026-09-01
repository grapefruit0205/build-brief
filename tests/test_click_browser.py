from __future__ import annotations

import ast
from pathlib import Path
import unittest

from hooks import click_browser, click_gate


class ClickBrowserTests(unittest.TestCase):
    def test_browser_runtime_has_no_upward_policy_or_host_dependency(self) -> None:
        source = Path(click_browser.__file__).read_text(encoding="utf-8")
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
            "click_contract",
            "click_gate",
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
        for required in (
            "click_browser_advisory",
            "click_claims",
            "click_evidence",
            "click_state",
        ):
            with self.subTest(required=required):
                self.assertIn(required, imported)

    def test_gate_does_not_reexport_browser_helpers(self) -> None:
        for name in (
            "_browser_input_error",
            "_browser_running_expires_at",
            "_browser_running_entry_is_active",
            "_browser_attempt_digest",
            "_tool_response_failed",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(click_gate, name))

        self.assertEqual(
            click_gate.MAX_BROWSER_UNIQUE_INPUTS,
            click_browser.MAX_UNIQUE_INPUTS,
        )
        self.assertEqual(
            click_gate.BROWSER_RUNNING_TTL_SECONDS,
            click_browser.RUNNING_TTL_SECONDS,
        )

    def test_browser_helper_behavior_preserves_legacy_and_structured_receipts(self) -> None:
        self.assertEqual(
            click_browser.input_error([]),
            "Browser evidence requires an object tool input.",
        )
        self.assertEqual(click_browser.input_error({}), "")
        self.assertTrue(click_browser.running_entry_is_active(90.0, 100.0))
        self.assertFalse(click_browser.running_entry_is_active(10.0, 100.0))
        self.assertTrue(
            click_browser.running_entry_is_active({"expires_at": 101.0}, 100.0)
        )
        self.assertFalse(
            click_browser.running_entry_is_active({"expires_at": 99.0}, 100.0)
        )

        semantic = {"code": "await page.title()", "timeout_ms": 5000}
        bookkeeping_changed = {
            "code": "  await page.title()\r\n",
            "timeout_ms": 30000,
            "_meta": {"trace": "different"},
        }
        self.assertEqual(
            click_browser.attempt_digest(semantic),
            click_browser.attempt_digest(bookkeeping_changed),
        )


if __name__ == "__main__":
    unittest.main()
