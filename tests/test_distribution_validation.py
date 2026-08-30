from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.validate_distribution import _release_notes_error, validate


ROOT = Path(__file__).parents[1]


class DistributionValidationTests(unittest.TestCase):
    def test_public_distribution_is_self_consistent(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_source_and_antigravity_gate_load_only_sibling_runtime_modules(self) -> None:
        hook_directories = (
            ROOT / "hooks",
            ROOT / "dist" / "antigravity" / "hooks",
        )
        with tempfile.TemporaryDirectory() as temporary:
            isolated = Path(temporary)
            event = {
                "session_id": "distribution-smoke",
                "turn_id": "turn-1",
                "cwd": str(isolated),
                "prompt": "inspect the project",
            }
            for index, hook_directory in enumerate(hook_directories):
                with self.subTest(hook_directory=hook_directory):
                    environment = os.environ.copy()
                    environment.update(
                        {
                            "PLUGIN_DATA": str(isolated / f"plugin-data-{index}"),
                            "CLICK_CONFIG_HOME": str(isolated / f"config-{index}"),
                            "PYTHONNOUSERSITE": "1",
                            "PYTHONPATH": str(hook_directory.resolve()),
                        }
                    )
                    result = subprocess.run(
                        [
                            sys.executable,
                            str((hook_directory / "click_gate.py").resolve()),
                            "prompt-submit",
                        ],
                        input=json.dumps(event),
                        cwd=isolated,
                        env=environment,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIsInstance(json.loads(result.stdout), dict)

    def test_release_notes_allow_only_the_explicit_next_minor_candidate(self) -> None:
        stable = "## v0.22.0 — 2026-08-30\n"
        self.assertEqual(_release_notes_error(stable, "0.22.0"), "")
        current = "## Unreleased v0.23 candidate — evidence\n\n## v0.22.0\n"
        self.assertEqual(_release_notes_error(current, "0.22.0"), "")
        for invalid in (
            "## Unreleased — evidence\n\n## v0.22.0\n",
            "## Unreleased v0.24 candidate\n\n## v0.22.0\n",
            "## Unreleased v0.23 candidate\n## Unreleased v0.23 candidate — two\n## v0.22.0\n",
        ):
            with self.subTest(invalid=invalid):
                self.assertIn("next-minor candidate", _release_notes_error(invalid, "0.22.0"))


if __name__ == "__main__":
    unittest.main()
