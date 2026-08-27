from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]


class RepositoryPolicyTests(unittest.TestCase):
    def test_json_artifacts_are_valid(self) -> None:
        for path in ROOT.rglob("*.json"):
            with self.subTest(path=path.relative_to(ROOT)):
                json.loads(path.read_text(encoding="utf-8"))

    def test_manifest_declares_explicit_activation_release(self) -> None:
        manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "build-brief")
        self.assertEqual(manifest["version"], "0.6.0")
        self.assertEqual(manifest["license"], "MIT")
        self.assertIn("explicit", manifest["description"].lower())

    def test_runtime_hook_has_no_external_python_dependency(self) -> None:
        source = (ROOT / "hooks" / "build_brief_gate.py").read_text(encoding="utf-8")
        for forbidden in ("requests", "yaml", "pydantic", "openai"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(f"import {forbidden}", source)
                self.assertNotIn(f"from {forbidden}", source)

    def test_public_tree_contains_no_ballast_state(self) -> None:
        forbidden_parts = {
            "ballast",
            "checkpoint.md",
            "decisions.md",
            "handoff.md",
            "product-truth.md",
        }
        tracked_candidates = [
            path.relative_to(ROOT)
            for path in ROOT.rglob("*")
            if path.is_file() and ".git" not in path.parts
        ]
        for path in tracked_candidates:
            lowered = {part.lower() for part in path.parts}
            with self.subTest(path=path):
                self.assertTrue(lowered.isdisjoint(forbidden_parts))

    def test_ab_suite_is_bounded_and_reproducible(self) -> None:
        suite = json.loads((ROOT / "evals" / "ab-suite.json").read_text())
        self.assertEqual(
            suite["conditions"],
            ["no-plugin", "explicit-skill-only", "explicit-skill-and-hook"],
        )
        self.assertGreaterEqual(len(suite["cases"]), 2)
        for case in suite["cases"]:
            with self.subTest(case=case["id"]):
                self.assertRegex(case["commit"], r"^[0-9a-f]{40}$")
                self.assertTrue(case["required_invariants"])


if __name__ == "__main__":
    unittest.main()
