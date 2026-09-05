from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
import tempfile
from unittest import mock

from benchmarks.incremental_verification import Fixture, _fixture_runner_argv, comparison_delta, distribution, main
from hooks import click_incremental


ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "incremental_verification.py"


class IncrementalVerificationBenchmarkTests(unittest.TestCase):
    def test_windows_fixture_runner_keeps_the_preflight_interpreter_and_capability(self) -> None:
        argv = ["py", "-3", str(BENCHMARK), "--encoded-runner", "transport-fixture"]
        with mock.patch("benchmarks.incremental_verification._split", return_value=argv):
            self.assertEqual(_fixture_runner_argv("rendered runner"), [sys.executable, *argv[2:]])
        self.assertEqual(argv[:2], ["py", "-3"])
        direct = [sys.executable, str(BENCHMARK), "run-verification", "transport-fixture"]
        with mock.patch("benchmarks.incremental_verification._split", return_value=direct):
            self.assertEqual(_fixture_runner_argv("direct runner"), direct)

    def test_stdout_json_round_trips_with_a_legacy_windows_encoding(self) -> None:
        payload = {"label": "검증 묶음"}
        raw = io.BytesIO()
        with (
            io.TextIOWrapper(raw, encoding="cp1252") as output,
            mock.patch("benchmarks.incremental_verification.run_benchmark", return_value=payload),
            mock.patch("benchmarks.incremental_verification.sys.stdout", output),
        ):
            self.assertEqual(main(["--iterations", "1", "--warmups", "0"]), 0)
            output.flush()
            self.assertEqual(json.loads(raw.getvalue().decode("ascii")), payload)

    def test_fixture_emits_measured_and_estimated_values_separately(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(BENCHMARK),
                "--iterations",
                "1",
                "--warmups", "0",
                "--mode", "guarded",
                "--scenario", "unchanged",
                "--scenario", "docs",
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
        self.assertEqual(payload["version"], 2)
        self.assertEqual(payload["conditions"]["authority"], "real-hooks-and-one-use-runner")
        self.assertEqual({sample["comparison"] for sample in payload["samples"]}, {"same-shards", "parent-suite"})
        for sample in payload["samples"]:
            measured = sample["incremental"]
            diagnostic = json.dumps({
                "scenario": sample["scenario"], "comparison": sample["comparison"],
                "sources": [{key: item.get(key) for key in
                             ("decision", "reason_code", "status", "execution_reason_code")}
                            for item in measured["batch"]["sources"]],
            }, ensure_ascii=True, sort_keys=True)
            self.assertEqual(measured["executed_source_count"], 0, diagnostic)
            self.assertEqual(measured["reused_source_count"], 2)
            self.assertGreater(measured["wall_ms"], 0)
            self.assertGreater(measured["estimated_avoided_ms"], 0)
            self.assertTrue(click_incremental.batch_is_valid(measured["batch"]))
            expected = "reuse-exact" if sample["scenario"] == "unchanged" else "reuse-safe-change"
            self.assertEqual({item["decision"] for item in measured["batch"]["sources"]}, {expected})
            self.assertAlmostEqual(sample["delta_ms"], sample["baseline"]["wall_ms"] - measured["wall_ms"])
        self.assertEqual(payload["observer_overhead_ms"], 0)
        self.assertEqual(payload["shadow_contradiction_count"], 0)
        self.assertNotIn("actual_saved", result.stdout)
        self.assertNotIn("runner_token", result.stdout)
        self.assertNotIn("raw_argv", result.stdout)

    def test_first_run_failure_and_evidence_session_boundary_are_honest(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory), 20)
            first = fixture.verify()
            self.assertEqual(first["executed_source_count"], 2)
            self.assertEqual(first["reused_source_count"], 0)
            fixture.change("first-failure")
            failed = fixture.verify()
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["executed_source_count"], 1)
            self.assertEqual(failed["not_run_source_count"], 1)
            self.assertEqual(failed["reused_source_count"], 0)
            self.assertEqual(failed["estimated_avoided_ms"], 0)

    def test_partial_reuse_uses_real_successor_evidence_and_runs_the_other_shard(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                Path(directory), 20, mode="evidence", partial_policy=True
            )
            baseline = fixture.verify()
            self.assertEqual(baseline["status"], "passed")
            origin_session = fixture.state()["evidence_session_id"]

            fixture.change("partial-reuse")
            current_session = fixture.state()["evidence_session_id"]
            self.assertNotEqual(current_session, origin_session)
            result = fixture.verify()

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["executed_source_count"], 1)
            self.assertEqual(result["reused_source_count"], 1)
            self.assertEqual(result["not_run_source_count"], 0)
            decisions = {
                item["label"]: (
                    item["decision"], item["status"], item["reason_code"]
                )
                for item in result["batch"]["sources"]
            }
            self.assertEqual(
                decisions["alpha"],
                (
                    "reuse-safe-change",
                    "reused",
                    "successor-evidence-safe-change-covered",
                ),
            )
            self.assertEqual(decisions["beta"][0:2], ("run", "passed"))
            alpha = next(
                item for item in result["batch"]["sources"]
                if item["label"] == "alpha"
            )
            self.assertEqual(
                alpha["reuse_origin"]["evidence_session_id"], origin_session
            )
            beta = next(
                item for item in result["batch"]["sources"]
                if item["label"] == "beta"
            )
            self.assertIsNone(beta["reuse_origin"])

    def test_negative_delta_zero_baseline_and_variation(self):
        self.assertEqual(comparison_delta(10, 15), {"delta_ms": -5, "delta_percent": -50})
        self.assertEqual(comparison_delta(0, 2), {"delta_ms": -2, "delta_percent": None})
        self.assertEqual(distribution([-10, 0, 5]), {"median": 0, "min": -10, "max": 5})
        self.assertIsNone(distribution([])["median"])


if __name__ == "__main__":
    unittest.main()
