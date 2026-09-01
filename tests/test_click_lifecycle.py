from __future__ import annotations

import ast
from pathlib import Path
import unittest

from hooks import click_gate, click_lifecycle


class ClickLifecycleTests(unittest.TestCase):
    def test_lifecycle_has_no_gate_or_host_adapter_dependency(self) -> None:
        source = Path(click_lifecycle.__file__).read_text(encoding="utf-8")
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
            "click_gate",
            "click_host_coverage",
            "platform_protocol",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(
                    any(forbidden in name.split(".") for name in imported),
                    imported,
                )
        for required in (
            "click_browser",
            "click_capability",
            "click_claims",
            "click_contract",
            "click_evidence",
            "click_mutation",
            "click_observation",
            "click_runtime_state",
            "click_service",
            "click_state",
            "click_verification",
        ):
            with self.subTest(required=required):
                self.assertIn(required, imported)

    def test_gate_keeps_lifecycle_compatibility_aliases(self) -> None:
        aliases = {
            "_write_state": click_lifecycle.write_state,
            "_read_state": click_lifecycle.read_state,
            "_write_mode": click_lifecycle.write_mode,
            "_read_mode": click_lifecycle.read_mode,
            "_write_default_mode": click_lifecycle.write_default_mode,
            "_read_default_mode": click_lifecycle.read_default_mode,
            "_evidence_sources": click_lifecycle.evidence_sources,
            "_write_contract_state": click_lifecycle.write_contract_state,
            "_contract_id_from_state": click_lifecycle.contract_id_from_state,
            "_read_contract_state": click_lifecycle.read_contract_state,
            "_clear_contract_state": click_lifecycle.clear_contract_state,
            "_save_contract_state": click_lifecycle.save_contract_state,
            "_prompt_authorization": click_lifecycle.prompt_authorization,
            "_record_user_prompt": click_lifecycle.record_user_prompt,
            "_read_user_prompt_state": click_lifecycle.read_user_prompt_state,
            "_read_user_prompt_turn": click_lifecycle.read_user_prompt_turn,
            "_consume_user_authorization": click_lifecycle.consume_user_authorization,
            "_active_prompt_turn_error": click_lifecycle.active_prompt_turn_error,
            "_contract_is_completed": click_lifecycle.contract_is_completed,
            "_approved_contract_is_active": click_lifecycle.approved_contract_is_active,
            "_session_contract_is_active": click_lifecycle.session_contract_is_active,
            "_prune_state": click_lifecycle.prune_state,
            "_validate_evidence_result": click_lifecycle.validate_evidence_result,
            "_control_request": click_lifecycle.control_request,
        }
        for name, expected in aliases.items():
            with self.subTest(name=name):
                self.assertIs(getattr(click_gate, name), expected)
        self.assertIs(
            click_gate.CONTRACT_ID_PATTERN,
            click_lifecycle.CONTRACT_ID_PATTERN,
        )
        self.assertEqual(
            click_gate.CONTRACT_STATE_SCHEMA_VERSION,
            click_lifecycle.CONTRACT_STATE_SCHEMA_VERSION,
        )

    def test_control_and_authorization_error_text_stay_in_lifecycle(self) -> None:
        self.assertEqual(
            click_lifecycle.control_request("click-gate arm"),
            ("arm", "", ""),
        )
        self.assertEqual(
            click_lifecycle.control_request("click-gate receipt export"),
            ("receipt-export", "", ""),
        )
        self.assertEqual(
            click_lifecycle.control_request(
                "click-gate receipt verify 'completion receipt.json'"
            ),
            ("receipt-verify", "completion receipt.json", ""),
        )
        self.assertEqual(
            click_lifecycle.control_request(
                r"click-gate receipt verify C:\temp\completion-receipt.json"
            ),
            ("receipt-verify", r"C:\temp\completion-receipt.json", ""),
        )
        self.assertEqual(
            click_lifecycle.control_request("click-gate stage 'unterminated"),
            (
                None,
                "",
                "Malformed click-gate command: No closing quotation.",
            ),
        )
        self.assertEqual(
            click_lifecycle.prompt_authorization("@Click bypass\ncontinue"),
            "bypass",
        )
        self.assertEqual(
            click_lifecycle.prompt_authorization("please @Click bypass"),
            "",
        )

    def test_gate_retains_event_and_runner_routing(self) -> None:
        source = Path(click_gate.__file__).read_text(encoding="utf-8")
        for required in (
            "def _handle_pre_tool(",
            "def _handle_post_tool(",
            "def _handle_prompt_submit(",
            "def _handle_session_end(",
            "def _runner_arguments(",
            "def main(",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        for extracted in (
            "def _write_state(",
            "def _write_contract_state(",
            "def _contract_is_completed(",
            "def _control_request(",
        ):
            with self.subTest(extracted=extracted):
                self.assertNotIn(extracted, source)


if __name__ == "__main__":
    unittest.main()
