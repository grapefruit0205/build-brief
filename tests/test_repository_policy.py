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

    def test_manifest_declares_click_one_shot_release(self) -> None:
        manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "click")
        self.assertEqual(manifest["version"], "0.11.0")
        self.assertEqual(manifest["license"], "MIT")
        self.assertIn("explicit", manifest["description"].lower())
        self.assertIn("plain-language", manifest["description"].lower())
        self.assertIn("execution contract", manifest["description"].lower())
        self.assertIn("compact", manifest["description"].lower())
        self.assertIn("one shot", manifest["interface"]["longDescription"].lower())
        self.assertIn("verification", manifest["interface"]["longDescription"].lower())
        self.assertIn("automatically", manifest["interface"]["longDescription"].lower())
        self.assertIn("@Click", manifest["description"])

    def test_readmes_use_plugin_mention_as_the_default_invocation(self) -> None:
        for readme_name in ("README.md", "README.ko.md"):
            with self.subTest(readme=readme_name):
                readme = (ROOT / readme_name).read_text(encoding="utf-8")
                self.assertIn("@Click", readme)
                self.assertNotRegex(readme, r"(?m)^\$click\s")
                self.assertNotIn("<br/>$click", readme)

    def test_readmes_document_automatic_budget_and_its_limit(self) -> None:
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        korean = (ROOT / "README.ko.md").read_text(encoding="utf-8")
        for readme in (english, korean):
            self.assertIn("click-gate verify", readme)
            self.assertIn("10", readme)
        self.assertIn("Automatic ceiling", english)
        self.assertIn("custom wrapper", english)
        self.assertIn("자동 상한", korean)
        self.assertIn("사용자 정의 래퍼", korean)

    def test_marketplace_exposes_click_from_the_click_catalog(self) -> None:
        marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(marketplace["name"], "click")
        self.assertEqual(marketplace["plugins"][0]["name"], "click")

    def test_click_and_fix_are_explicit_only_skills(self) -> None:
        for skill_name in ("click", "fix"):
            with self.subTest(skill=skill_name):
                skill_root = ROOT / "skills" / skill_name
                skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
                metadata = (skill_root / "agents" / "openai.yaml").read_text(
                    encoding="utf-8"
                )
                self.assertIn(f"name: {skill_name}", skill_text)
                self.assertIn(f"${skill_name}", metadata)
                self.assertIn("allow_implicit_invocation: false", metadata)
                self.assertNotIn("[TODO:", skill_text)
                self.assertIn("click-gate verify", skill_text)

    def test_runtime_hook_has_no_external_python_dependency(self) -> None:
        source = (ROOT / "hooks" / "click_gate.py").read_text(encoding="utf-8")
        for forbidden in ("requests", "yaml", "pydantic", "openai"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(f"import {forbidden}", source)
                self.assertNotIn(f"from {forbidden}", source)

    def test_compact_contract_replaces_the_verbose_execution_fields(self) -> None:
        hook = (ROOT / "hooks" / "click_gate.py").read_text(encoding="utf-8")
        directive = (
            ROOT / "skills" / "click" / "references" / "directive-format.md"
        ).read_text(encoding="utf-8")
        for required in (
            "outcome",
            "boundary",
            "must_hold",
            "build",
            "verification",
            "plain_language",
        ):
            with self.subTest(required=required):
                self.assertIn(required, hook)
                self.assertIn(required, directive)
        for removed in (
            '"invariants"',
            '"system_semantics"',
            '"implementation"',
            '"phases"',
            '"steps"',
            '"tasks"',
            '"plan"',
            '"execution_order"',
            '"minimality"',
            '"proof"',
        ):
            with self.subTest(removed=removed):
                self.assertNotIn(removed, hook)

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
        suite = json.loads(
            (ROOT / "evals" / "ab-suite.json").read_text(encoding="utf-8")
        )
        self.assertEqual(suite["schema_version"], 3)
        self.assertEqual(
            suite["conditions"],
            ["no-plugin", "explicit-skill-only", "explicit-skill-and-hook"],
        )
        self.assertGreaterEqual(len(suite["cases"]), 2)
        for case in suite["cases"]:
            with self.subTest(case=case["id"]):
                self.assertRegex(case["commit"], r"^[0-9a-f]{40}$")
                self.assertTrue(case["required_invariants"])
        approval_case = next(
            case for case in suite["cases"] if case["expected_activation"]
        )
        self.assertTrue(approval_case["approval_followup"])


if __name__ == "__main__":
    unittest.main()
