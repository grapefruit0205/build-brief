from __future__ import annotations

import json
import unittest

from hooks import click_runtime_state


class ClickRuntimeStateTests(unittest.TestCase):
    def test_view_normalizes_authority_scalars_without_changing_json(self) -> None:
        state = {
            "state_schema_version": 2,
            "status": "approved",
            "runtime_mode": "guarded",
            "contract_digest": "a" * 64,
            "contract_id": "ctr_" + "b" * 32,
            "nested": {"kept": True},
        }
        before = json.dumps(state, sort_keys=True)

        view = click_runtime_state.view(state)

        self.assertTrue(view.execution_authorized)
        self.assertTrue(view.guarded_approved)
        self.assertFalse(view.evidence)
        self.assertEqual(view.state_schema_version, 2)
        self.assertEqual(view.contract_digest, "a" * 64)
        self.assertEqual(view.contract_id, "ctr_" + "b" * 32)
        self.assertEqual(json.dumps(state, sort_keys=True), before)

    def test_view_fails_closed_for_non_mapping_and_malformed_scalars(self) -> None:
        for value in (None, [], "state", {"status": 1, "state_schema_version": True}):
            with self.subTest(value=value):
                view = click_runtime_state.view(value)
                self.assertEqual(view.status, "")
                self.assertFalse(view.execution_authorized)
                self.assertIsNone(view.state_schema_version)

    def test_view_distinguishes_missing_contract_id_from_an_empty_value(self) -> None:
        missing = click_runtime_state.view({"contract_digest": "a" * 64})
        present = click_runtime_state.view(
            {"contract_digest": "a" * 64, "contract_id": ""}
        )

        self.assertFalse(missing.contains("contract_id"))
        self.assertTrue(present.contains("contract_id"))
        self.assertEqual(present.contract_id, "")


if __name__ == "__main__":
    unittest.main()
