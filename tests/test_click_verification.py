from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

from hooks import click_gate, click_verification


class ClickVerificationTests(unittest.TestCase):
    def test_verification_runtime_has_no_gate_host_router_or_service_dependency(self) -> None:
        source = Path(click_verification.__file__).read_text(encoding="utf-8")
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
            "click_service",
            "platform_protocol",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(
                    any(forbidden in name.split(".") for name in imported),
                    imported,
                )
        for required in (
            "click_capability",
            "click_claims",
            "click_dependency_cache",
            "click_evidence",
            "click_host_coverage",
            "click_inspection",
            "click_mutation",
            "click_observation",
            "click_process",
            "click_state",
            "click_verification_meter",
            "click_verification_policy",
        ):
            with self.subTest(required=required):
                self.assertIn(required, imported)

    def test_gate_keeps_verification_compatibility_aliases(self) -> None:
        aliases = {
            "_fresh_verification_state": click_verification.fresh_state,
            "_validate_verification_batch": click_verification.validate_batch,
            "_verification_groups": click_verification.verification_groups,
            "_verification_group_digest": click_verification.group_digest,
            "_file_content_digest": click_verification.file_content_digest,
            "_verification_environment": click_verification.environment,
            "_verification_environment_binding": click_verification.environment_binding,
            "_verification_executable_records": click_verification.executable_records,
            "_verification_environment_digest": click_verification.environment_digest,
            "_verification_receipt_matches": click_verification.receipt_matches,
            "_dependency_receipt_matches": click_verification.dependency_receipt_matches,
            "_minimum_verification_class": click_verification.minimum_class,
            "_git_workspace_snapshot": click_verification.git_workspace_snapshot,
            "_new_untracked_is_suspicious": click_verification.new_untracked_is_suspicious,
        }
        for name, expected in aliases.items():
            with self.subTest(name=name):
                self.assertIs(getattr(click_gate, name), expected)
        self.assertEqual(
            click_gate.VERIFICATION_PROTOCOL_VERSION,
            click_verification.PROTOCOL_VERSION,
        )
        self.assertEqual(
            click_gate.VERIFY_RUNNING_TTL_SECONDS,
            click_verification.RUNNING_TTL_SECONDS,
        )

    def test_verification_entrypoints_and_exact_validation_stay_in_domain(self) -> None:
        source = Path(click_verification.__file__).read_text(encoding="utf-8")
        for required in (
            "def _prepare_verification(",
            "def _claim_verification_run(",
            "def _record_verification_result(",
            "def _release_unclaimed_verification_reservation(",
            "def _run_verification(",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)

        batch, units, error = click_verification.validate_batch(
            json.dumps(
                {
                    "version": 2,
                    "checks": [
                        {
                            "argv": ["python3", "-m", "unittest", "tests.test_one"],
                            "class": "targeted",
                        }
                    ],
                }
            ),
            "focused",
        )
        self.assertEqual(error, "")
        self.assertEqual(units, 1)
        self.assertEqual(batch["checks"][0]["class"], "targeted")

        rejected, _, error = click_verification.validate_batch(
            json.dumps({"version": 2, "commands": ["pytest"]}),
            "focused",
        )
        self.assertIsNone(rejected)
        self.assertEqual(
            error,
            "Click verification uses `checks` with argv arrays and a submitted "
            "`class`; legacy shell-string `commands` are no longer accepted.",
        )


if __name__ == "__main__":
    unittest.main()
