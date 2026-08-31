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
        self, declarations: dict[str, list[str]] | None = None
    ) -> dict[str, dict[str, object]]:
        return click_dependency_cache.receipts_for_groups(
            self.root,
            self.checks,
            declarations=declarations,
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

    def test_relevant_or_uncommitted_manifest_change_fails_safe(self) -> None:
        self.write_manifest([self.entry(["src/unit.py"])])
        self.commit()
        first = self.receipts()["source"]

        self.write_manifest([self.entry(["src/", "docs/a.md"])])
        self.assertEqual(self.receipts(), {})
        self.commit("relevant entry")
        second = self.receipts()["source"]
        self.assertNotEqual(first["entry_digest"], second["entry_digest"])
        self.assertNotEqual(first["dependency_digest"], second["dependency_digest"])

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
        self.assertEqual(self.receipts(), {})

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


if __name__ == "__main__":
    unittest.main()
