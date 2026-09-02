from __future__ import annotations

from collections import Counter
import errno
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest import mock

from benchmarks.evidence_reuse import run_benchmark
from benchmarks.evidence_reuse.manifests import MANIFEST_VARIANTS
from benchmarks.evidence_reuse.profiles import PROFILES, PROFILES_BY_NAME
from benchmarks.evidence_reuse.runtime_observations import (
    capture_baseline_observation,
)
from benchmarks.evidence_reuse.runner import (
    RuntimeTools,
    _checks,
    _remove_tree,
    runtime_available,
)
from benchmarks.evidence_reuse.scenarios import C_NATIVE, MUTATIONS, mutation_ids


RUNTIMES_AVAILABLE, RUNTIME_SKIP_REASON = runtime_available()


class EvidenceReuseBenchmarkCatalogTests(unittest.TestCase):
    def test_semantic_oracle_and_manifest_form_five_hundred_case_matrix(self) -> None:
        self.assertEqual(len(MUTATIONS), 100)
        self.assertEqual(len(MANIFEST_VARIANTS), 5)
        self.assertEqual(len(MUTATIONS) * len(MANIFEST_VARIANTS), 500)
        self.assertEqual(len(mutation_ids()), len(set(mutation_ids())))
        self.assertEqual(sum(mutation.oracle_reuse_safe for mutation in MUTATIONS), 40)
        self.assertEqual(
            sum(not mutation.oracle_reuse_safe for mutation in MUTATIONS), 60
        )
        self.assertEqual(
            sum(mutation.expected_rerun_pass for mutation in MUTATIONS), 60
        )
        self.assertEqual(
            sum(not mutation.expected_rerun_pass for mutation in MUTATIONS), 40
        )
        self.assertEqual(
            Counter(mutation.profile for mutation in MUTATIONS),
            {
                "python-service": 20,
                "python-package": 20,
                "node-commonjs": 10,
                "node-esm": 10,
                "c-native": 20,
                "java-jdk": 20,
            },
        )
        self.assertEqual(
            Counter(mutation.semantic_class for mutation in MUTATIONS),
            {
                "irrelevant": 40,
                "relevant_nonbreaking": 20,
                "relevant_breaking": 30,
                "environment_drift": 10,
            },
        )

    def test_oracle_and_manifest_definitions_do_not_import_each_other(self) -> None:
        benchmark_root = (
            Path(__file__).resolve().parents[1] / "benchmarks" / "evidence_reuse"
        )
        scenario_source = (benchmark_root / "scenarios.py").read_text(encoding="utf-8")
        manifest_source = (benchmark_root / "manifests.py").read_text(encoding="utf-8")
        observation_source = (benchmark_root / "runtime_observations.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("from .manifests import", scenario_source)
        self.assertNotIn("from .scenarios import", manifest_source)
        self.assertNotIn("from .manifests import", observation_source)
        self.assertNotIn("from .scenarios import", observation_source)
        self.assertFalse(
            any(hasattr(mutation, "manifest_variant") for mutation in MUTATIONS)
        )

    def test_controlled_runtime_observations_are_complete_for_every_fixture(
        self,
    ) -> None:
        for profile in PROFILES:
            with self.subTest(profile=profile.name):
                observation = capture_baseline_observation(
                    profile.name,
                    profile.fixture_template,
                    baseline_passed=True,
                )
                self.assertEqual(observation["status"], "complete")
                self.assertTrue(observation["process_tree_complete"])
                self.assertFalse(observation["external_access"])


class EvidenceReuseBenchmarkCoreRuntimeTests(unittest.TestCase):
    def test_c_fixture_uses_windows_executable_suffix(self) -> None:
        fixture_root = Path("fixture")
        with mock.patch("benchmarks.evidence_reuse.runner.os.name", "nt"):
            checks = _checks(
                PROFILES_BY_NAME[C_NATIVE],
                fixture_root,
                RuntimeTools(python="python", gcc="gcc"),
            )

        self.assertEqual(checks[0]["argv"][-1], "build/test_app.exe")
        self.assertEqual(
            checks[1]["argv"],
            [str((fixture_root / "build" / "test_app.exe").resolve())],
        )

    def test_fixture_cleanup_handles_read_only_git_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixture"
            pack = root / ".git" / "objects" / "pack"
            pack.mkdir(parents=True)
            index = pack / "pack-test.idx"
            index.write_bytes(b"index")
            index.chmod(stat.S_IREAD)

            _remove_tree(root)

            self.assertFalse(root.exists())

    def test_fixture_cleanup_retries_transient_directory_race(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixture"
            root.mkdir()
            (root / "artifact").write_bytes(b"artifact")
            real_rmtree = shutil.rmtree
            attempts = 0

            def transient_rmtree(path: Path, *, onerror: object) -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise OSError(errno.ENOTEMPTY, "directory not empty", path)
                real_rmtree(path, onerror=onerror)

            with mock.patch.object(shutil, "rmtree", side_effect=transient_rmtree):
                _remove_tree(root)

            self.assertEqual(attempts, 2)
            self.assertFalse(root.exists())

    def test_manifest_stress_inputs_are_scored_against_the_same_oracle(self) -> None:
        selected_names = {
            "docs-readme-append",
            "app-behavior-break",
            "shared-behavior-break",
            "environment-production",
        }
        selected = tuple(
            mutation
            for mutation in MUTATIONS
            if mutation.profile == "python-service" and mutation.name in selected_names
        )

        report = run_benchmark(selected)
        payload = report.to_dict()

        self.assertEqual(report.total_cases, 20)
        self.assertEqual(payload["by_manifest"]["exact"]["decision_correct"], 4)
        self.assertEqual(payload["by_manifest"]["broad"]["decision_correct"], 4)
        self.assertEqual(payload["by_manifest"]["broad"]["unsafe_reuse"], 0)
        self.assertEqual(payload["by_manifest"]["broad"]["over_conservative_rerun"], 0)
        self.assertEqual(payload["by_manifest"]["incomplete"]["unsafe_reuse"], 0)
        self.assertEqual(payload["by_manifest"]["incomplete"]["decision_correct"], 4)
        self.assertEqual(payload["by_manifest"]["malformed"]["decision_correct"], 4)
        self.assertEqual(payload["by_manifest"]["malformed"]["unsafe_reuse"], 0)
        self.assertEqual(payload["by_manifest"]["uncommitted"]["decision_correct"], 4)
        self.assertEqual(payload["by_manifest"]["uncommitted"]["unsafe_reuse"], 0)
        self.assertEqual(report.correct_reuse, 5)
        self.assertEqual(report.correct_invalidation, 15)
        self.assertEqual(report.over_conservative_rerun, 0)
        self.assertEqual(payload["must_rerun_protection_percent"], 100.0)
        self.assertEqual(payload["safe_reuse_capture_percent"], 100.0)
        self.assertTrue(all(case.rerun_matches_oracle for case in report.cases))
        self.assertIn("Plain-language result", report.text())


@unittest.skipUnless(RUNTIMES_AVAILABLE, RUNTIME_SKIP_REASON)
class EvidenceReuseBenchmarkRuntimeTests(unittest.TestCase):
    def test_exact_manifest_baseline_matches_independent_oracle(self) -> None:
        exact = tuple(
            variant for variant in MANIFEST_VARIANTS if variant.name == "exact"
        )
        report = run_benchmark(manifest_variants=exact)

        self.assertEqual(report.total_cases, 100)
        self.assertEqual(report.correct_reuse, 40)
        self.assertEqual(report.correct_invalidation, 60)
        self.assertEqual(report.unsafe_reuse, 0)
        self.assertEqual(report.over_conservative_rerun, 0)
        self.assertEqual(report.shadow_rerun_pass, 60)
        self.assertEqual(report.shadow_rerun_fail, 40)
        self.assertTrue(all(case.baseline_passed for case in report.cases))
        self.assertTrue(all(case.actual_rerun.ran for case in report.cases))
        self.assertTrue(all(case.rerun_matches_oracle for case in report.cases))

        payload = report.to_dict()
        self.assertEqual(payload["must_rerun_protection_percent"], 100.0)
        self.assertEqual(
            payload["decision_engine"],
            "hooks.click_verification.dependency_receipt_matches",
        )
        self.assertEqual(payload["exact_manifest_baseline"]["decision_correct"], 100)
        self.assertEqual(payload["exact_manifest_baseline"]["unsafe_reuse"], 0)
        self.assertEqual(
            {
                name: values["total_cases"]
                for name, values in payload["by_profile"].items()
            },
            {
                "c-native": 20,
                "java-jdk": 20,
                "node-commonjs": 10,
                "node-esm": 10,
                "python-package": 20,
                "python-service": 20,
            },
        )
        for case in payload["cases"]:
            self.assertIn("oracle", case)
            self.assertIn("decision", case)
            self.assertIn("actual_rerun", case)
            self.assertIn("reuse_safe", case["oracle"])
            self.assertIn("expected_rerun_pass", case["oracle"])
            self.assertIn("reuse", case["decision"])
            self.assertIn("exit_code", case["actual_rerun"])


if __name__ == "__main__":
    unittest.main()
