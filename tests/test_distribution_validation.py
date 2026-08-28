from __future__ import annotations

from pathlib import Path
import unittest

from scripts.validate_distribution import validate


ROOT = Path(__file__).parents[1]


class DistributionValidationTests(unittest.TestCase):
    def test_public_distribution_is_self_consistent(self) -> None:
        self.assertEqual(validate(ROOT), [])


if __name__ == "__main__":
    unittest.main()
