from __future__ import annotations

from pathlib import Path
import unittest

from scripts.validate_distribution import _release_notes_error, validate


ROOT = Path(__file__).parents[1]


class DistributionValidationTests(unittest.TestCase):
    def test_public_distribution_is_self_consistent(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_release_notes_allow_only_the_explicit_next_minor_candidate(self) -> None:
        stable = "## v0.21.1 — 2026-08-30\n"
        self.assertEqual(_release_notes_error(stable, "0.21.1"), "")
        current = "## Unreleased v0.22 candidate — evidence\n\n## v0.21.1\n"
        self.assertEqual(_release_notes_error(current, "0.21.1"), "")
        for invalid in (
            "## Unreleased — evidence\n\n## v0.21.1\n",
            "## Unreleased v0.23 candidate\n\n## v0.21.1\n",
            "## Unreleased v0.22 candidate\n## Unreleased v0.22 candidate — two\n## v0.21.1\n",
        ):
            with self.subTest(invalid=invalid):
                self.assertIn("next-minor candidate", _release_notes_error(invalid, "0.21.1"))


if __name__ == "__main__":
    unittest.main()
