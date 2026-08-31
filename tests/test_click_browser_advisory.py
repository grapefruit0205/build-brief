from __future__ import annotations

import ast
from pathlib import Path
import unittest

from hooks import click_browser_advisory


class ClickBrowserAdvisoryTests(unittest.TestCase):
    def test_advisory_module_is_an_independent_leaf_boundary(self) -> None:
        source = Path(click_browser_advisory.__file__).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                parent = node.module or ""
                imported.add(parent)
                imported.update(
                    f"{parent}.{alias.name}".strip(".") for alias in node.names
                )

        forbidden = {
            "click_contract",
            "click_evidence",
            "click_gate",
            "click_process",
            "click_state",
            "platform_protocol",
        }
        self.assertTrue(
            all(
                not any(part in forbidden for part in name.split("."))
                for name in imported
            ),
            imported,
        )
        self.assertIn("does not grant or deny Browser authority", source)

    def test_timing_thresholds_produce_guidance_without_a_decision(self) -> None:
        advisories = click_browser_advisory.input_advisories(
            {
                "code": "await page.waitForTimeout(55000)",
                "timeout_ms": 60_000,
            }
        )
        self.assertEqual(len(advisories), 2)
        self.assertTrue(all(value.startswith("Click advisory:") for value in advisories))
        self.assertIn("above 30 seconds", advisories[0])
        self.assertIn("above five seconds", advisories[1])
        self.assertEqual(
            click_browser_advisory.longest_declared_runtime_ms(
                {
                    "code": "await page.waitForTimeout(55000)",
                    "timeout_ms": 60_000,
                }
            ),
            60_000,
        )

    def test_repeat_guidance_uses_observed_results_not_model_identity(self) -> None:
        succeeded = {
            "status": "failed",
            "attempts": 3,
            "successful_attempts": 1,
            "failed_attempts": 2,
        }
        failed = {
            "status": "failed",
            "attempts": 2,
            "successful_attempts": 0,
            "failed_attempts": 2,
        }
        self.assertIn(
            "already succeeded",
            click_browser_advisory.repeat_advisory(succeeded),
        )
        self.assertIn(
            "failed or produced incomplete evidence twice",
            click_browser_advisory.repeat_advisory(failed),
        )
        self.assertEqual(click_browser_advisory.repeat_advisory(None), "")


if __name__ == "__main__":
    unittest.main()
