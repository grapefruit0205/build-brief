from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "incremental_verification.py"


class IncrementalVerificationBenchmarkTests(unittest.TestCase):
    def test_fixture_emits_measured_and_estimated_values_separately(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(BENCHMARK),
                "--iterations",
                "1",
                "--workload-rounds",
                "2000",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["total_source_count"], 4)
        self.assertEqual(payload["executed_source_count"], 1)
        self.assertEqual(payload["reused_source_count"], 3)
        self.assertGreater(payload["full_verification_duration_ms"], 0)
        self.assertGreater(payload["incremental_verification_duration_ms"], 0)
        self.assertGreater(payload["estimated_avoided_duration_ms"], 0)
        self.assertEqual(payload["observer_overhead_ms"], 0)
        self.assertEqual(payload["shadow_contradiction_count"], 0)
        self.assertEqual(payload["duration_measurement"], "wall-clock-measured")
        self.assertEqual(
            payload["estimated_avoided_duration_basis"],
            "most-recent-successful-full-run",
        )
        self.assertNotIn("actual_saved", result.stdout)


if __name__ == "__main__":
    unittest.main()
