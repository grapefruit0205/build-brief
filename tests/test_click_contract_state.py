from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from hooks import (
    click_browser,
    click_contract_state,
    click_incremental,
    click_lifecycle,
    click_mutation,
    click_observation,
    click_service,
    click_state,
    click_verification,
)


class ClickContractStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.plugin_data = Path(self.temporary.name) / "plugin-data"
        self.environment = mock.patch.dict(
            os.environ,
            {"PLUGIN_DATA": str(self.plugin_data)},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.event = {
            "session_id": "session-1",
            "turn_id": "turn-1",
            "cwd": str(Path(self.temporary.name) / "workspace"),
        }

    def test_leaf_depends_only_on_state_and_content_free_measurements(self) -> None:
        source = Path(click_contract_state.__file__).read_text(encoding="utf-8")
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
            "click_host_router",
            "click_lifecycle",
            "click_mutation",
            "click_observation",
            "click_runtime_state",
            "click_service",
            "click_verification",
            "platform_protocol",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(
                    any(forbidden in name.split(".") for name in imported),
                    imported,
                )
        self.assertIn(
            '__package__, "click_state", "click_incremental"',
            source,
        )
        self.assertIn(
            "click_state.write_json(click_state.contract_path(event), state)",
            source,
        )

    def test_read_missing_malformed_and_non_object_state_is_exact(self) -> None:
        expected = {"status": "none", "contract_digest": ""}
        path = click_state.contract_path(self.event)
        self.assertEqual(click_contract_state.read_contract_state(self.event), expected)

        path.parent.mkdir(parents=True, exist_ok=True)
        for payload in ("not-json", "[]", "null", '"state"'):
            with self.subTest(payload=payload):
                path.write_text(payload, encoding="utf-8")
                self.assertEqual(
                    click_contract_state.read_contract_state(self.event),
                    expected,
                )

    def test_save_mutates_timestamp_and_round_trips_the_same_state(self) -> None:
        state = {"status": "staged", "contract_digest": "a" * 64}
        with mock.patch.object(click_contract_state.time, "time", return_value=1234.9):
            click_contract_state.save_contract_state(self.event, state)

        self.assertEqual(state["updated_at"], 1234)
        self.assertEqual(click_contract_state.read_contract_state(self.event), state)
        stored = json.loads(
            click_state.contract_path(self.event).read_text(encoding="utf-8")
        )
        self.assertEqual(stored, state)

    def test_clear_removes_contract_and_its_runner_recovery_mirror(self) -> None:
        state = {
            "status": "approved",
            "contract_digest": "a" * 64,
            "mutation": {
                "status": "running",
                "request_digest": "b" * 64,
                "runner_token_digest": "c" * 64,
            },
        }
        click_contract_state.save_contract_state(self.event, state)
        path = click_state.contract_path(self.event)
        recovery_path = click_state._recovery_snapshot_path(path)
        self.assertTrue(path.exists())
        self.assertTrue(recovery_path.exists())

        click_contract_state.clear_contract_state(self.event)

        self.assertFalse(path.exists())
        self.assertFalse(recovery_path.exists())

    def test_clear_preserves_the_existing_oserror_tolerance(self) -> None:
        path = mock.Mock()
        path.unlink.side_effect = OSError("busy")
        with mock.patch.object(
            click_contract_state.click_state,
            "contract_path",
            return_value=path,
        ):
            click_contract_state.clear_contract_state(self.event)
        path.unlink.assert_called_once_with()

    def test_cancel_archives_only_measurements_without_execution_authority(self) -> None:
        plan = click_incremental.build_plan([click_incremental.decision(
            source_key="1" * 64, check_digest="2" * 64, decision="run",
            reason_code="no-passing-evidence", current_revision=1, previous_revision=-1,
            authority_source="runner",
        )], current_revision=1)
        verification = {}
        click_incremental.store_batch(verification, click_incremental.new_batch(
            plan, batch_id="a" * 32, revision=1, prepared_ms=1.5,
        ))
        click_incremental.mark_started(verification, "1" * 64)
        state = {"status": "approved", "contract_digest": "3" * 64,
                 "runner_token": "private-token", "verification": verification}
        click_contract_state.save_contract_state(self.event, state)
        click_contract_state.clear_contract_state(self.event)
        restored = click_contract_state.read_contract_state(self.event)
        self.assertEqual(restored["status"], "none")
        self.assertEqual(restored["contract_digest"], "")
        self.assertNotIn("private-token", json.dumps(restored))
        batch = click_incremental.current_batch(restored["verification"])
        self.assertEqual(batch["status"], "interrupted")
        self.assertFalse(batch["sources"][0]["completed"])
        self.assertIsNone(batch["sources"][0]["duration_ms"])
        self.assertFalse(click_state.contract_path(self.event).exists())

    def test_cancel_keeps_completed_source_and_marks_only_active_and_future_sources(self) -> None:
        decisions = [
            click_incremental.decision(
                source_key=str(index) * 64,
                check_digest=str(index + 2) * 64,
                decision="run",
                reason_code="no-passing-evidence",
                current_revision=1,
                previous_revision=-1,
                authority_source="runner",
            )
            for index in (1, 2, 3)
        ]
        verification: dict[str, object] = {}
        click_incremental.store_batch(
            verification,
            click_incremental.new_batch(
                click_incremental.build_plan(decisions, current_revision=1),
                batch_id="a" * 32,
                revision=1,
                prepared_ms=1.5,
            ),
        )
        click_incremental.mark_started(verification, "1" * 64)
        click_incremental.mark_completed(
            verification,
            "1" * 64,
            status="passed",
            reason="command-passed",
            duration_ms=11.25,
        )
        click_incremental.mark_started(verification, "2" * 64)
        state = {
            "status": "evidence",
            "contract_digest": "4" * 64,
            "runner_token": "must-not-survive",
            "verification": verification,
        }
        click_contract_state.save_contract_state(self.event, state)

        click_contract_state.clear_contract_state(self.event)

        self.assertFalse(click_state.contract_path(self.event).exists())
        archived = click_contract_state.read_contract_state(self.event)
        self.assertEqual(archived["status"], "none")
        self.assertNotIn("must-not-survive", json.dumps(archived))
        batch = click_incremental.current_batch(archived["verification"])
        assert batch is not None
        first, second, third = batch["sources"]
        self.assertEqual(
            (first["status"], first["completed"], first["duration_ms"]),
            ("passed", True, 11.25),
        )
        self.assertEqual(
            (second["status"], second["completed"]),
            ("interrupted", False),
        )
        self.assertEqual(
            (third["status"], third["completed"]),
            ("not-run", False),
        )

    def test_runtime_domains_share_the_leaf_symbols(self) -> None:
        for module in (
            click_browser,
            click_lifecycle,
            click_mutation,
            click_observation,
            click_service,
            click_verification,
        ):
            with self.subTest(module=module.__name__, operation="read"):
                self.assertIs(
                    module._read_contract_state,
                    click_contract_state.read_contract_state,
                )
            with self.subTest(module=module.__name__, operation="save"):
                self.assertIs(
                    module._save_contract_state,
                    click_contract_state.save_contract_state,
                )

        self.assertIs(
            click_lifecycle.read_contract_state,
            click_contract_state.read_contract_state,
        )
        self.assertIs(
            click_lifecycle.save_contract_state,
            click_contract_state.save_contract_state,
        )
        self.assertIs(
            click_lifecycle.clear_contract_state,
            click_contract_state.clear_contract_state,
        )
        self.assertIs(
            click_contract_state.read_contract_state,
            click_contract_state.read_contract_state,
        )
        self.assertIs(
            click_contract_state.save_contract_state,
            click_contract_state.save_contract_state,
        )
        self.assertIs(
            click_contract_state.clear_contract_state,
            click_contract_state.clear_contract_state,
        )


if __name__ == "__main__":
    unittest.main()
