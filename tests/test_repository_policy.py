from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
README_NAMES = ("README.md", "README.ko.md", "README.zh-CN.md")


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
        self.assertEqual(manifest["version"], "0.19.0")
        self.assertEqual(manifest["license"], "MIT")
        self.assertIn("always on", manifest["description"].lower())
        self.assertIn("manual", manifest["description"].lower())
        self.assertIn("plain-language", manifest["description"].lower())
        self.assertIn("execution contract", manifest["description"].lower())
        self.assertIn("compact", manifest["description"].lower())
        self.assertIn("one shot", manifest["interface"]["longDescription"].lower())
        self.assertIn("verification", manifest["interface"]["longDescription"].lower())
        self.assertIn(
            "cheapest sufficient primary evidence",
            manifest["interface"]["longDescription"].lower(),
        )
        self.assertIn("automatically", manifest["interface"]["longDescription"].lower())
        self.assertIn("replanning", manifest["interface"]["longDescription"].lower())
        self.assertIn(
            "isolated child process groups",
            manifest["interface"]["longDescription"].lower(),
        )
        self.assertIn(
            "process-control executables",
            manifest["interface"]["longDescription"].lower(),
        )
        self.assertIn("anti-loop", manifest["keywords"])
        self.assertIn("@Click", manifest["description"])
        self.assertIn("structured", manifest["description"].lower())

    def test_readmes_use_plugin_mention_as_the_default_invocation(self) -> None:
        for readme_name in README_NAMES:
            with self.subTest(readme=readme_name):
                readme = (ROOT / readme_name).read_text(encoding="utf-8")
                self.assertIn("@Click", readme)
                self.assertNotRegex(readme, r"(?m)^\$click\s")
                self.assertNotIn("<br/>$click", readme)

    def test_readmes_document_automatic_budget_and_its_limit(self) -> None:
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        korean = (ROOT / "README.ko.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        for readme in (english, korean, chinese):
            self.assertIn("click-gate verify", readme)
            self.assertIn("10", readme)
        self.assertIn("Automatic ceiling", english)
        self.assertIn("custom wrapper", english)
        self.assertIn("자동 상한", korean)
        self.assertIn("사용자 정의 래퍼", korean)
        self.assertIn("自动上限", chinese)
        self.assertIn("自定义 wrapper", chinese)
        self.assertIn("minimum class", english.lower())
        self.assertIn("최소 class", korean)
        self.assertIn("最低 class", chinese)
        self.assertIn("Python `-c`", english)
        self.assertIn("Python `-c`", korean)
        self.assertIn("Python `-c`", chinese)

    def test_evidence_economy_uses_one_primary_source_per_condition(self) -> None:
        click_skill = (ROOT / "skills" / "click" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        fix_skill = (ROOT / "skills" / "fix" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        verification = (
            ROOT
            / "skills"
            / "click"
            / "references"
            / "verification-profiles.md"
        ).read_text(encoding="utf-8")
        anti_loop = (
            ROOT / "skills" / "click" / "references" / "anti-loop-policy.md"
        ).read_text(encoding="utf-8")
        directive = (
            ROOT / "skills" / "click" / "references" / "directive-format.md"
        ).read_text(encoding="utf-8")
        grader = (ROOT / "evals" / "SEMANTIC_GRADER.md").read_text(
            encoding="utf-8"
        )

        for document in (
            click_skill,
            fix_skill,
            verification,
            anti_loop,
            directive,
            grader,
        ):
            with self.subTest(document=document[:40]):
                lowered = document.lower()
                self.assertIn("one cheapest sufficient primary evidence source", lowered)
                self.assertIn("one source may cover several conditions", lowered)

        english = (ROOT / "README.md").read_text(encoding="utf-8")
        korean = (ROOT / "README.ko.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn("cheapest sufficient primary evidence source", english)
        self.assertIn("가장 싼 주 증거", korean)
        self.assertIn("成本最低的主要证据来源", chinese)

    def test_readmes_document_distinct_turn_approval_and_git_mutation_guard(self) -> None:
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        korean = (ROOT / "README.ko.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        for readme in (english, korean, chinese):
            self.assertIn("UserPromptSubmit", readme)
            self.assertIn("staged_turn_id", readme)
            self.assertIn("non-ignored untracked", readme)
        self.assertIn("later user turn", english)
        self.assertIn("다음 사용자 turn", korean)
        self.assertIn("后续用户 turn", chinese)

    def test_readmes_document_observable_anti_loop_guards_and_limits(self) -> None:
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        korean = (ROOT / "README.ko.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        for readme in (english, korean, chinese):
            self.assertIn("48,000", readme)
            self.assertIn("update_plan", readme)
            self.assertIn("rg --files", readme)
        self.assertIn("Implementation without loops", english)
        self.assertIn("hidden reasoning", english)
        self.assertIn("실행 루프 없이 구현", korean)
        self.assertIn("숨은 추론", korean)
        self.assertIn("无循环实现", chinese)
        self.assertIn("隐藏推理", chinese)

    def test_readmes_document_structured_capabilities_and_shell_boundary(self) -> None:
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        korean = (ROOT / "README.ko.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        protocol = (
            ROOT
            / "skills"
            / "click"
            / "references"
            / "capability-protocol.md"
        ).read_text(encoding="utf-8")
        for document in (english, korean, chinese, protocol):
            self.assertIn("click-gate inspect", document)
            self.assertIn("click-gate mutate", document)
            self.assertIn("click-gate service", document)
            self.assertIn('"version":1', document)
            self.assertIn("shell=False", document)
            self.assertIn("process group", document)
            self.assertIn("process-control", document)
            self.assertIn("pkill", document)
        self.assertIn('"checks"', english)
        self.assertIn('"checks"', korean)
        self.assertIn('"checks"', chinese)
        self.assertIn("hosted tools", protocol)

    def test_marketplace_exposes_click_from_the_click_catalog(self) -> None:
        marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(marketplace["name"], "click")
        self.assertEqual(marketplace["plugins"][0]["name"], "click")
        self.assertEqual(
            marketplace["plugins"][0]["source"]["ref"], "v0.19.0"
        )

    def test_ci_enforces_distribution_compilation_and_diff_validation(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("python scripts/validate_distribution.py", workflow)
        self.assertIn("python -m compileall", workflow)
        self.assertIn("git diff --check", workflow)
        self.assertIn("push:\n    branches: [main]", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertTrue((ROOT / "scripts" / "validate_distribution.py").is_file())

    def test_release_documents_identify_v019_without_an_unreleased_heading(self) -> None:
        for readme_name in README_NAMES:
            with self.subTest(readme=readme_name):
                readme = (ROOT / readme_name).read_text(encoding="utf-8")
                self.assertIn("v0.19.0", readme)
        notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        self.assertIn("## v0.19.0", notes)
        self.assertNotIn("## Unreleased", notes)

    def test_click_supports_always_on_while_fix_remains_explicit(self) -> None:
        for skill_name in ("click", "fix"):
            with self.subTest(skill=skill_name):
                skill_root = ROOT / "skills" / skill_name
                skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
                metadata = (skill_root / "agents" / "openai.yaml").read_text(
                    encoding="utf-8"
                )
                self.assertIn(f"name: {skill_name}", skill_text)
                self.assertIn(f"${skill_name}", metadata)
                self.assertNotIn("[TODO:", skill_text)
                self.assertIn("click-gate verify", skill_text)
        click_metadata = (
            ROOT / "skills" / "click" / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        fix_metadata = (
            ROOT / "skills" / "fix" / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("allow_implicit_invocation: true", click_metadata)
        self.assertIn("allow_implicit_invocation: false", fix_metadata)

    def test_persistent_modes_and_read_only_review_are_documented(self) -> None:
        modes = (
            ROOT / "skills" / "click" / "references" / "modes.md"
        ).read_text(encoding="utf-8")
        hook_config = json.loads(
            (ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        for phrase in (
            "click-gate default on",
            "click-gate default manual",
            "click-gate review",
            "click-gate bypass",
        ):
            self.assertIn(phrase, modes)
        self.assertIn("UserPromptSubmit", hook_config["hooks"])

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
        self.assertEqual(suite["schema_version"], 6)
        self.assertEqual(suite["release_under_test"], "0.19.0")
        self.assertEqual(suite["model"], "gpt-5.6-sol")
        self.assertEqual(suite["reasoning_effort"], "max")
        self.assertGreaterEqual(suite["runs_per_condition"], 5)
        self.assertIsInstance(suite["random_seed"], int)
        self.assertEqual(
            suite["conditions"],
            ["no-plugin", "explicit-skill-only", "explicit-skill-and-hook"],
        )
        self.assertGreaterEqual(len(suite["cases"]), 6)
        for case in suite["cases"]:
            with self.subTest(case=case["id"]):
                self.assertRegex(case["commit"], r"^[0-9a-f]{40}$")
                self.assertTrue(case["required_invariants"])
                if case["expected_activation"]:
                    self.assertTrue(case["baseline_prompt"])
        approval_case = next(
            case for case in suite["cases"] if case["expected_activation"]
        )
        self.assertTrue(approval_case["approval_followup"])
        runner = (ROOT / "evals" / "run_ab.py").read_text(encoding="utf-8")
        self.assertIn("--execute-paid-runs", runner)
        self.assertIn("paired_deltas_against_no_plugin", runner)
        self.assertIn("--ignore-user-config", runner)
        self.assertIn("_prepare_isolated_runtime", runner)
        self.assertIn("click_commit_sha", runner)
        self.assertIn("_is_broad_exploration_command", runner)
        self.assertIn("browser_tool_call_count", runner)
        self.assertIn("browser_tool_seconds", runner)
        self.assertIn("timed_browser_call_count", runner)

    def test_golden_cases_cover_always_on_manual_and_review_routing(self) -> None:
        catalog = (
            ROOT / "evals" / "golden-prompts.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("version: 17", catalog)
        for case_id in (
            "unset-first-mutation-choice",
            "always-on-trivial-edit",
            "always-on-code-review",
            "always-on-explanation",
        ):
            self.assertIn(f"id: {case_id}", catalog)
        self.assertIn("default_mode: manual", catalog)
        self.assertIn("default_mode: on", catalog)
        self.assertIn("id: structured-capability-active-build", catalog)
        self.assertIn("id: structured-capability-review", catalog)
        self.assertIn("id: completed-contract-rollover", catalog)
        self.assertIn("id: verification-minimum-class", catalog)
        self.assertIn("id: verification-workspace-mutation", catalog)
        self.assertIn("id: distinct-turn-contract-approval", catalog)
        self.assertIn("id: active-lifecycle-plan-block", catalog)
        self.assertIn("id: cheapest-evidence-browser-game", catalog)


if __name__ == "__main__":
    unittest.main()
