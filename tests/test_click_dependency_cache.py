from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from hooks import click_dependency_cache


class ClickDependencyCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "workspace"
        self.root.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True)
        (self.root / "src").mkdir()
        (self.root / "src" / "unit.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "a.md").write_text("a\n", encoding="utf-8")
        (self.root / "docs" / "b.md").write_text("b\n", encoding="utf-8")
        self.checks = {
            "source": [
                {
                    "evidence_id": "E1",
                    "argv": ["python3", "-m", "pytest", "tests/unit"],
                    "class": "targeted",
                }
            ]
        }

    def git_capture(self, cwd: Path, arguments: list[str]) -> bytes | None:
        completed = subprocess.run(
            [
                "git",
                "--no-pager",
                "--no-optional-locks",
                "-c",
                "core.fsmonitor=false",
                *arguments,
            ],
            cwd=cwd,
            capture_output=True,
            check=False,
        )
        return completed.stdout if completed.returncode == 0 else None

    def commit(self, message: str = "fixture") -> None:
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Click Tests",
                "-c",
                "user.email=click-tests@example.invalid",
                "commit",
                "--quiet",
                "-m",
                message,
            ],
            cwd=self.root,
            check=True,
        )

    def write_manifest(self, entries: list[dict[str, object]]) -> None:
        destination = self.root / ".click" / "evidence-dependencies.json"
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(
            json.dumps({"version": 1, "entries": entries}, indent=2) + "\n",
            encoding="utf-8",
        )

    def entry(
        self,
        paths: list[str],
        argv: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "checks": [argv or self.checks["source"][0]["argv"]],
            "paths": paths,
        }

    def receipts(
        self,
        declarations: dict[str, list[str]] | None = None,
        observations: dict[str, dict[str, object]] | None = None,
    ) -> dict[str, dict[str, object]]:
        return click_dependency_cache.receipts_for_groups(
            self.root,
            self.checks,
            declarations=declarations,
            observations=observations,
            git_capture=self.git_capture,
        )

    def test_module_has_no_upward_runtime_dependency(self) -> None:
        source = Path(click_dependency_cache.__file__).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        for forbidden in (
            "click_gate",
            "click_contract",
            "click_evidence",
            "click_state",
            "click_process",
            "platform_protocol",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(
                    any(forbidden in name.split(".") for name in imported),
                    imported,
                )

    def test_approved_contract_patterns_track_only_the_resolved_set(self) -> None:
        self.commit()
        first = self.receipts({"source": ["src/*.py"]})["source"]
        (self.root / "docs" / "a.md").write_text("unrelated\n", encoding="utf-8")
        unrelated = self.receipts({"source": ["src/*.py"]})["source"]
        self.assertEqual(first["entry_digest"], unrelated["entry_digest"])
        self.assertEqual(first["dependency_digest"], unrelated["dependency_digest"])
        self.assertEqual(first["resolved_paths"], ["src/unit.py"])

        (self.root / "src" / "unit.py").write_text("VALUE = 2\n", encoding="utf-8")
        changed = self.receipts({"source": ["src/*.py"]})["source"]
        self.assertNotEqual(first["dependency_digest"], changed["dependency_digest"])

    def test_double_star_is_cross_directory_and_star_is_one_segment(self) -> None:
        nested = self.root / "src" / "nested"
        nested.mkdir()
        (nested / "more.py").write_text("MORE = 1\n", encoding="utf-8")
        self.commit()

        shallow = self.receipts({"source": ["src/*.py"]})["source"]
        recursive = self.receipts({"source": ["src/**/*.py"]})["source"]
        self.assertEqual(shallow["resolved_paths"], ["src/unit.py"])
        self.assertEqual(
            recursive["resolved_paths"],
            ["src/nested/more.py", "src/unit.py"],
        )

    def test_unrelated_manifest_entry_change_keeps_relevant_entry_current(self) -> None:
        self.write_manifest(
            [
                self.entry(["src/"]),
                self.entry(["docs/a.md"], ["python3", "-m", "pytest", "docs"]),
            ]
        )
        self.commit("initial manifest")
        first = self.receipts()["source"]

        self.write_manifest(
            [
                self.entry(["src/"]),
                self.entry(["docs/b.md"], ["python3", "-m", "pytest", "docs"]),
            ]
        )
        self.commit("unrelated entry")
        second = self.receipts()["source"]

        self.assertNotEqual(first["manifest_digest"], second["manifest_digest"])
        self.assertEqual(first["entry_digest"], second["entry_digest"])
        self.assertEqual(first["dependency_digest"], second["dependency_digest"])

    def test_committed_manifest_remains_authority_until_a_new_commit(self) -> None:
        self.write_manifest([self.entry(["src/unit.py"])])
        self.commit()
        first = self.receipts()["source"]

        self.write_manifest([self.entry(["src/", "docs/a.md"])])
        uncommitted = self.receipts()["source"]
        self.assertEqual(first["entry_digest"], uncommitted["entry_digest"])
        self.assertEqual(first["dependency_digest"], uncommitted["dependency_digest"])

        manifest = self.root / ".click" / "evidence-dependencies.json"
        manifest.write_text("{not-json\n", encoding="utf-8")
        malformed = self.receipts()["source"]
        self.assertEqual(first["entry_digest"], malformed["entry_digest"])
        self.assertEqual(first["dependency_digest"], malformed["dependency_digest"])

        self.write_manifest([self.entry(["src/", "docs/a.md"])])
        self.commit("relevant entry")
        second = self.receipts()["source"]
        self.assertNotEqual(first["entry_digest"], second["entry_digest"])
        self.assertNotEqual(first["dependency_digest"], second["dependency_digest"])

    def test_complete_observation_refines_expanding_manifest_patterns(self) -> None:
        self.write_manifest([self.entry(["**", "docs/a.md"])])
        self.commit()
        observation = click_dependency_cache.dependency_observation(
            ["src/unit.py"]
        )

        first = self.receipts(observations={"source": observation})["source"]
        self.assertEqual(first["resolved_paths"], ["docs/a.md", "src/unit.py"])

        (self.root / "docs" / "b.md").write_text(
            "unrelated\n", encoding="utf-8"
        )
        unrelated = self.receipts(observations={"source": observation})["source"]
        self.assertEqual(first["dependency_digest"], unrelated["dependency_digest"])

        (self.root / "docs" / "a.md").write_text("required\n", encoding="utf-8")
        required = self.receipts(observations={"source": observation})["source"]
        self.assertNotEqual(first["dependency_digest"], required["dependency_digest"])

    def test_incomplete_observation_cannot_refine_expanding_patterns(self) -> None:
        self.write_manifest([self.entry(["**"])])
        self.commit()
        observation = click_dependency_cache.dependency_observation(
            ["src/unit.py"], status="failed", process_tree_complete=False
        )

        receipt = self.receipts(observations={"source": observation})["source"]

        self.assertIn("docs/b.md", receipt["resolved_paths"])
        self.assertFalse(
            click_dependency_cache.dependency_observation_is_complete(
                receipt["observation"]
            )
        )

    def test_worktree_manifest_change_invalidates_when_the_check_reads_it(self) -> None:
        self.write_manifest([self.entry(["**"])])
        self.commit()
        observation = click_dependency_cache.dependency_observation(
            [click_dependency_cache.CONFIG_RELATIVE_PATH, "src/unit.py"]
        )
        first = self.receipts(observations={"source": observation})["source"]

        manifest = self.root / ".click" / "evidence-dependencies.json"
        manifest.write_text("{not-json\n", encoding="utf-8")
        changed = self.receipts(observations={"source": observation})["source"]

        self.assertEqual(first["entry_digest"], changed["entry_digest"])
        self.assertNotEqual(first["dependency_digest"], changed["dependency_digest"])

    def test_committed_manifest_accepts_windows_checkout_line_endings(self) -> None:
        subprocess.run(
            ["git", "config", "core.autocrlf", "true"],
            cwd=self.root,
            check=True,
        )
        self.write_manifest([self.entry(["src/unit.py"])])
        manifest = self.root / ".click" / "evidence-dependencies.json"
        manifest.write_bytes(manifest.read_bytes().replace(b"\n", b"\r\n"))
        self.commit("windows checkout manifest")

        self.assertIn(b"\r\n", manifest.read_bytes())
        receipt = self.receipts()["source"]
        self.assertEqual(receipt["resolved_paths"], ["src/unit.py"])

        manifest.write_bytes(
            manifest.read_bytes().replace(b"src/unit.py", b"docs/a.md")
        )
        uncommitted = self.receipts()["source"]
        self.assertEqual(receipt["entry_digest"], uncommitted["entry_digest"])
        self.commit("windows checkout manifest update")
        committed_update = self.receipts()["source"]
        self.assertEqual(committed_update["resolved_paths"], ["docs/a.md"])
        self.assertNotEqual(receipt["entry_digest"], committed_update["entry_digest"])

    @unittest.skipIf(os.name == "nt", "Windows symlink creation needs host privileges")
    def test_internal_symlink_hashes_link_and_target_but_external_is_rejected(self) -> None:
        (self.root / "linked.py").symlink_to("src/unit.py")
        self.commit()
        first = self.receipts({"source": ["linked.py"]})["source"]
        self.assertEqual(first["resolved_paths"], ["linked.py", "src/unit.py"])

        (self.root / "src" / "unit.py").write_text("VALUE = 3\n", encoding="utf-8")
        changed = self.receipts({"source": ["linked.py"]})["source"]
        self.assertNotEqual(first["dependency_digest"], changed["dependency_digest"])

        (self.root / "linked.py").unlink()
        (self.root / "linked.py").symlink_to(Path(self.temporary.name) / "outside.py")
        (Path(self.temporary.name) / "outside.py").write_text("outside\n", encoding="utf-8")
        self.assertEqual(self.receipts({"source": ["linked.py"]}), {})

    def test_ambiguous_patterns_are_rejected(self) -> None:
        for pattern in (
            "../src/",
            "/src/",
            "src/**x.py",
            "src/file?.py",
            "src/[ab].py",
            "src\\unit.py",
        ):
            with self.subTest(pattern=pattern):
                normalized, error = click_dependency_cache.normalize_patterns(
                    [pattern]
                )
                self.assertIsNone(normalized)
                self.assertTrue(error)

    def test_observed_dependency_fills_a_silent_manifest_gap(self) -> None:
        (self.root / "src" / "shared.py").write_text(
            "SHARED = 1\n", encoding="utf-8"
        )
        self.write_manifest([self.entry(["src/unit.py"])])
        self.commit()
        observation = click_dependency_cache.dependency_observation(
            ["src/shared.py"]
        )

        first = self.receipts(observations={"source": observation})["source"]

        self.assertEqual(
            first["resolved_paths"], ["src/shared.py", "src/unit.py"]
        )
        self.assertTrue(
            click_dependency_cache.dependency_observation_is_complete(
                first["observation"]
            )
        )
        (self.root / "src" / "shared.py").write_text(
            "SHARED = 2\n", encoding="utf-8"
        )
        changed = self.receipts(observations={"source": observation})["source"]
        self.assertNotEqual(first["dependency_digest"], changed["dependency_digest"])

    def test_failed_or_unavailable_observation_is_explicitly_incomplete(self) -> None:
        self.write_manifest([self.entry(["src/unit.py"])])
        self.commit()

        unavailable = self.receipts()["source"]["observation"]
        failed = click_dependency_cache.dependency_observation(
            ["src/unit.py"], status="failed", process_tree_complete=False
        )

        self.assertEqual(unavailable["status"], "unavailable")
        self.assertFalse(
            click_dependency_cache.dependency_observation_is_complete(unavailable)
        )
        self.assertFalse(
            click_dependency_cache.dependency_observation_is_complete(failed)
        )

    def test_external_input_marks_a_successful_trace_incomplete(self) -> None:
        observation = click_dependency_cache.dependency_observation(
            ["src/unit.py"], external_access=True
        )

        self.assertTrue(
            click_dependency_cache.dependency_observation_is_valid(observation)
        )
        self.assertFalse(
            click_dependency_cache.dependency_observation_is_complete(observation)
        )

    def test_child_process_requires_complete_process_tree_coverage(self) -> None:
        partial = click_dependency_cache.dependency_observation(
            ["src/unit.py"],
            child_processes=1,
            process_tree_complete=False,
        )
        followed = click_dependency_cache.dependency_observation(
            ["src/unit.py"],
            child_processes=1,
            process_tree_complete=True,
        )

        self.assertFalse(
            click_dependency_cache.dependency_observation_is_complete(partial)
        )
        self.assertTrue(
            click_dependency_cache.dependency_observation_is_complete(followed)
        )

        combined = click_dependency_cache.combine_dependency_observations(
            [
                followed,
                click_dependency_cache.dependency_observation(["docs/a.md"]),
            ]
        )
        self.assertEqual(combined["paths"], ["docs/a.md", "src/unit.py"])
        self.assertEqual(combined["child_processes"], 1)
        self.assertTrue(
            click_dependency_cache.dependency_observation_is_complete(combined)
        )

    def test_observed_missing_lookup_invalidates_when_the_path_appears(self) -> None:
        self.write_manifest([self.entry(["src/unit.py"])])
        self.commit()
        observation = click_dependency_cache.dependency_observation(
            ["optional.py"]
        )
        first = self.receipts(observations={"source": observation})["source"]

        (self.root / "optional.py").write_text("OPTION = 1\n", encoding="utf-8")
        appeared = self.receipts(observations={"source": observation})["source"]

        self.assertIn("optional.py", first["resolved_paths"])
        self.assertNotEqual(first["dependency_digest"], appeared["dependency_digest"])

    def test_observed_directory_listing_invalidates_membership_change(self) -> None:
        self.write_manifest([self.entry(["src/unit.py"])])
        self.commit()
        observation = click_dependency_cache.dependency_observation(["src/"])
        first = self.receipts(observations={"source": observation})["source"]

        (self.root / "src" / "added.py").write_text(
            "ADDED = 1\n", encoding="utf-8"
        )
        changed = self.receipts(observations={"source": observation})["source"]

        self.assertNotEqual(first["dependency_digest"], changed["dependency_digest"])


if __name__ == "__main__":
    unittest.main()
