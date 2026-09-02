from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from hooks import click_change_policy


class ClickChangePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "workspace"
        self.root.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True)
        (self.root / "src").mkdir()
        (self.root / "src" / "unit.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "guide.md").write_text("before\n", encoding="utf-8")
        (self.root / "README.md").write_text("before\n", encoding="utf-8")
        self.argv = ["python3", "-m", "pytest", "tests/unit"]
        self.checks = [
            {
                "evidence_id": "E1",
                "argv": self.argv,
                "class": "targeted",
            }
        ]
        self.write_policy(["README.md", "docs/**"])
        self.commit("baseline")

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

    def write_policy(
        self,
        patterns: list[str],
        *,
        argv: list[str] | None = None,
        extra_entries: list[dict[str, object]] | None = None,
    ) -> None:
        target = self.root / click_change_policy.CONFIG_RELATIVE_PATH
        target.parent.mkdir(exist_ok=True)
        entries: list[dict[str, object]] = [
            {
                "checks": [argv or self.argv],
                "reuse_if_only_changed": patterns,
            }
        ]
        entries.extend(extra_entries or [])
        target.write_text(
            json.dumps({"version": 1, "entries": entries}, indent=2) + "\n",
            encoding="utf-8",
        )

    def commit(self, message: str) -> None:
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

    def baseline(self) -> dict[str, object]:
        receipts = click_change_policy.receipts_for_groups(
            self.root,
            {"source": self.checks},
            git_capture=self.git_capture,
        )
        self.assertIn("source", receipts)
        return receipts["source"]

    def decide(self, baseline: dict[str, object]) -> dict[str, object]:
        return click_change_policy.decide(
            self.root,
            self.checks,
            baseline,
            git_capture=self.git_capture,
        )

    def test_module_has_no_upward_runtime_dependency(self) -> None:
        source = Path(click_change_policy.__file__).read_text(encoding="utf-8")
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

    def test_declared_readme_change_is_reusable(self) -> None:
        baseline = self.baseline()
        (self.root / "README.md").write_text("after\n", encoding="utf-8")

        decision = self.decide(baseline)

        self.assertEqual(decision["status"], "reuse")
        self.assertEqual(decision["reason"], "all-paths-declared-safe")
        self.assertEqual(decision["changed_paths"], ["README.md"])
        self.assertRegex(str(decision["decision_digest"]), r"^[0-9a-f]{64}$")

    def test_nested_docs_add_delete_and_rename_are_reusable(self) -> None:
        baseline = self.baseline()
        (self.root / "docs" / "guide.md").unlink()
        (self.root / "docs" / "new.md").write_text("new\n", encoding="utf-8")

        decision = self.decide(baseline)

        self.assertEqual(decision["status"], "reuse")
        self.assertEqual(
            decision["changed_paths"], ["docs/guide.md", "docs/new.md"]
        )

    def test_code_change_forces_rerun(self) -> None:
        baseline = self.baseline()
        (self.root / "src" / "unit.py").write_text("VALUE = 2\n", encoding="utf-8")

        decision = self.decide(baseline)

        self.assertEqual(decision["status"], "rerun")
        self.assertEqual(decision["reason"], "path-not-declared-safe")
        self.assertEqual(decision["changed_paths"], ["src/unit.py"])

    def test_safe_and_unsafe_changes_together_force_rerun(self) -> None:
        baseline = self.baseline()
        (self.root / "README.md").write_text("after\n", encoding="utf-8")
        (self.root / "src" / "unit.py").write_text("VALUE = 2\n", encoding="utf-8")

        decision = self.decide(baseline)

        self.assertEqual(decision["status"], "rerun")
        self.assertEqual(decision["changed_paths"], ["README.md", "src/unit.py"])

    def test_committed_changes_are_compared_across_heads(self) -> None:
        baseline = self.baseline()
        (self.root / "docs" / "guide.md").write_text("committed\n", encoding="utf-8")
        self.commit("docs")

        decision = self.decide(baseline)

        self.assertEqual(decision["status"], "reuse")
        self.assertEqual(decision["changed_paths"], ["docs/guide.md"])

    def test_baseline_dirty_file_uses_its_effective_content(self) -> None:
        (self.root / "README.md").write_text("verified dirty baseline\n", encoding="utf-8")
        baseline = self.baseline()
        (self.root / "README.md").write_text("later\n", encoding="utf-8")

        decision = self.decide(baseline)

        self.assertEqual(decision["status"], "reuse")
        self.assertEqual(decision["changed_paths"], ["README.md"])

    def test_reverted_content_has_no_net_change(self) -> None:
        baseline = self.baseline()
        original = (self.root / "README.md").read_text(encoding="utf-8")
        (self.root / "README.md").write_text("temporary\n", encoding="utf-8")
        (self.root / "README.md").write_text(original, encoding="utf-8")

        decision = self.decide(baseline)

        self.assertEqual(decision["status"], "reuse")
        self.assertEqual(decision["reason"], "no-net-change")
        self.assertEqual(decision["changed_paths"], [])

    def test_uncommitted_policy_change_is_not_authority(self) -> None:
        baseline = self.baseline()
        self.write_policy(["README.md", "docs/**", "src/**"])
        (self.root / "src" / "unit.py").write_text("VALUE = 2\n", encoding="utf-8")

        decision = self.decide(baseline)

        self.assertEqual(decision["status"], "unknown")
        self.assertEqual(decision["reason"], "preflight-unavailable")

    def test_committed_policy_change_forces_one_rerun(self) -> None:
        baseline = self.baseline()
        self.write_policy(["README.md", "docs/**", "notes/**"])
        self.commit("policy")

        decision = self.decide(baseline)

        self.assertEqual(decision["status"], "rerun")
        self.assertEqual(decision["reason"], "policy-changed")

    def test_policy_cannot_mark_click_authority_files_safe(self) -> None:
        self.write_policy(["**"])
        self.commit("overbroad policy")

        receipts = click_change_policy.receipts_for_groups(
            self.root,
            {"source": self.checks},
            git_capture=self.git_capture,
        )

        self.assertEqual(receipts, {})

    def test_wrong_check_group_has_no_policy_receipt(self) -> None:
        receipts = click_change_policy.receipts_for_groups(
            self.root,
            {
                "source": [
                    {
                        "evidence_id": "E1",
                        "argv": ["python3", "-m", "pytest", "tests/other"],
                        "class": "targeted",
                    }
                ]
            },
            git_capture=self.git_capture,
        )

        self.assertEqual(receipts, {})

    def test_tampered_baseline_fails_closed(self) -> None:
        baseline = self.baseline()
        baseline["baseline"]["head"] = "0" * 40

        decision = self.decide(baseline)

        self.assertEqual(decision["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
