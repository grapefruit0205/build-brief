from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from hooks import click_gate, click_lifecycle, click_mode, click_state


class ClickModeTests(unittest.TestCase):
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

    def test_mode_leaf_has_no_upward_runtime_dependency(self) -> None:
        source = Path(click_mode.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
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
            "click_lifecycle",
            "click_host_coverage",
            "click_host_router",
            "platform_protocol",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(
                    any(forbidden in name.split(".") for name in imported),
                    imported,
                )
        self.assertIn(
            'click_import_bootstrap.load_siblings(__package__, "click_state")',
            source,
        )

    def test_session_mode_round_trips_and_falls_back_to_adaptive(self) -> None:
        self.assertEqual(click_mode.read_mode(self.event), "adaptive")

        for value in ("strict", "adaptive"):
            with self.subTest(value=value):
                click_mode.write_mode(self.event, value)
                self.assertEqual(click_mode.read_mode(self.event), value)

        click_state.mode_path(self.event).write_text("not-json", encoding="utf-8")
        self.assertEqual(click_mode.read_mode(self.event), "adaptive")

    def test_public_and_legacy_default_modes_preserve_exact_mapping(self) -> None:
        self.assertEqual(click_mode.read_default_mode(), "evidence")

        cases = (
            ("evidence", "evidence"),
            ("guarded", "guarded"),
            ("off", "off"),
            ("on", "guarded"),
            ("manual", "off"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                click_mode.write_default_mode(value)
                self.assertEqual(click_mode.read_default_mode(), expected)
                stored = json.loads(
                    click_state.preference_path().read_text(encoding="utf-8")
                )
                self.assertEqual(stored["schema_version"], 2)
                self.assertEqual(stored["default_mode"], expected)
                self.assertFalse(stored["migration_notice_pending"])

        with self.assertRaisesRegex(
            ValueError,
            "^unsupported Click default mode: invalid$",
        ):
            click_mode.write_default_mode("invalid")

    def test_legacy_preference_migrates_once_and_consumes_one_notice(self) -> None:
        path = click_state.preference_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        for legacy, expected in (("on", "guarded"), ("manual", "off")):
            with self.subTest(legacy=legacy):
                path.write_text(
                    json.dumps({"default_mode": legacy, "updated_at": 1}),
                    encoding="utf-8",
                )
                self.assertEqual(click_mode.read_default_mode(), expected)
                stored = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(stored["migrated_from"], legacy)
                self.assertTrue(stored["migration_notice_pending"])
                self.assertEqual(click_mode.consume_migration_notice(), legacy)
                self.assertEqual(click_mode.consume_migration_notice(), "")

    def test_lifecycle_and_gate_keep_the_same_mode_compatibility_objects(self) -> None:
        aliases = {
            "_write_mode": click_mode.write_mode,
            "_read_mode": click_mode.read_mode,
            "_write_default_mode": click_mode.write_default_mode,
            "_read_default_mode": click_mode.read_default_mode,
        }
        for name, expected in aliases.items():
            with self.subTest(name=name):
                self.assertIs(getattr(click_gate, name), expected)
        self.assertIs(click_lifecycle.write_mode, click_mode.write_mode)
        self.assertIs(click_lifecycle.read_mode, click_mode.read_mode)
        self.assertIs(
            click_lifecycle.write_default_mode,
            click_mode.write_default_mode,
        )
        self.assertIs(
            click_lifecycle.read_default_mode,
            click_mode.read_default_mode,
        )
        self.assertIs(
            click_lifecycle.consume_migration_notice,
            click_mode.consume_migration_notice,
        )


if __name__ == "__main__":
    unittest.main()
