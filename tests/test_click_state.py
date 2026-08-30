from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from hooks import click_gate, click_state


class ClickStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.plugin_data = Path(self.temporary.name) / "plugin-data"
        self.config_home = Path(self.temporary.name) / "config"
        self.environment = mock.patch.dict(
            os.environ,
            {
                "PLUGIN_DATA": str(self.plugin_data),
                "CLICK_CONFIG_HOME": str(self.config_home),
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.event = {
            "session_id": "session-1",
            "turn_id": "turn-1",
            "cwd": str(Path(self.temporary.name) / "workspace"),
        }

    def test_identity_paths_preserve_session_and_turn_scopes(self) -> None:
        next_turn = {**self.event, "turn_id": "turn-2"}

        self.assertNotEqual(
            click_state.state_path(self.event), click_state.state_path(next_turn)
        )
        self.assertNotEqual(
            click_state.review_path(self.event), click_state.review_path(next_turn)
        )
        for resolver in (
            click_state.mode_path,
            click_state.contract_path,
            click_state.prompt_path,
        ):
            with self.subTest(resolver=resolver.__name__):
                self.assertEqual(resolver(self.event), resolver(next_turn))

        paths = (
            click_state.state_path(self.event),
            click_state.mode_path(self.event),
            click_state.contract_path(self.event),
            click_state.prompt_path(self.event),
            click_state.review_path(self.event),
        )
        for path in paths:
            with self.subTest(path=path.name):
                self.assertEqual(path.parent, click_state.state_root())
                self.assertNotIn("session-1", path.name)
                self.assertNotIn("turn-1", path.name)

    def test_write_json_atomically_replaces_content(self) -> None:
        path = click_state.state_root() / "sample.json"
        click_state.write_json(path, {"status": "first"})
        click_state.write_json(path, {"status": "second", "revision": 2})

        self.assertEqual(
            json.loads(path.read_text(encoding="utf-8")),
            {"status": "second", "revision": 2},
        )
        self.assertEqual(list(path.parent.glob(".gate-*")), [])
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_managed_state_paths_reject_external_relative_and_symlink_paths(self) -> None:
        managed = click_state.state_root() / "session-contract-managed.json"
        click_state.write_json(managed, {"status": "approved"})
        self.assertTrue(
            click_state.managed_state_path(managed, ("session-contract-",))
        )
        self.assertFalse(
            click_state.managed_state_path(
                Path("session-contract-managed.json"), ("session-contract-",)
            )
        )

        external = Path(self.temporary.name) / "session-contract-external.json"
        external.write_text("{}", encoding="utf-8")
        self.assertFalse(
            click_state.managed_state_path(external, ("session-contract-",))
        )
        link = click_state.state_root() / "session-contract-link.json"
        try:
            link.symlink_to(external)
        except (NotImplementedError, OSError):
            pass
        else:
            self.assertFalse(
                click_state.managed_state_path(link, ("session-contract-",))
            )

    def test_click_gate_keeps_compatibility_aliases_for_state_primitives(self) -> None:
        aliases = {
            "_state_root": click_state.state_root,
            "_preference_path": click_state.preference_path,
            "_identity_path": click_state.identity_path,
            "_state_path": click_state.state_path,
            "_mode_path": click_state.mode_path,
            "_contract_path": click_state.contract_path,
            "_managed_state_path": click_state.managed_state_path,
            "_prompt_path": click_state.prompt_path,
            "_review_path": click_state.review_path,
            "_write_json": click_state.write_json,
            "_state_lock": click_state.state_lock,
        }
        for name, expected in aliases.items():
            with self.subTest(name=name):
                self.assertIs(getattr(click_gate, name), expected)
        self.assertEqual(
            click_gate.STATE_LOCK_TIMEOUT_SECONDS,
            click_state.STATE_LOCK_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            click_gate.STATE_LOCK_STALE_SECONDS,
            click_state.STATE_LOCK_STALE_SECONDS,
        )

    def test_state_module_does_not_depend_on_click_gate(self) -> None:
        source = Path(click_state.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import click_gate", source)
        self.assertNotIn("from hooks import click_gate", source)


if __name__ == "__main__":
    unittest.main()
