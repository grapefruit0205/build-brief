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
        self.assertEqual(manifest["version"], "0.21.1")
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
        self.assertIn("contract_id", manifest["interface"]["longDescription"])
        self.assertIn(
            "never the json again",
            manifest["interface"]["longDescription"].lower(),
        )
        self.assertIn("anti-loop", manifest["keywords"])
        self.assertIn("@Click", manifest["description"])
        self.assertIn("structured", manifest["description"].lower())
        self.assertIn("keeps codex inside that boundary", manifest["description"].lower())
        self.assertEqual(
            manifest["interface"]["shortDescription"],
            "Approve one clear boundary, then build and verify without replanning.",
        )
        self.assertLessEqual(len(manifest["interface"]["defaultPrompt"]), 3)
        for prompt in manifest["interface"]["defaultPrompt"]:
            self.assertLessEqual(len(prompt), 128)

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

    def test_evidence_economy_uses_structured_primary_source_references(self) -> None:
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

        for document in (verification, anti_loop, directive, grader):
            with self.subTest(document=document[:40]):
                self.assertIn("primary_evidence", document)
                self.assertIn("evidence", document)

        for skill in (click_skill, fix_skill):
            with self.subTest(skill=skill[:40]):
                self.assertIn("verification-profiles.md", skill)
                self.assertIn("directive-format.md", skill)
                self.assertIn("anti-loop-policy.md", skill)
                self.assertIn("capability-protocol.md", skill)
                self.assertIn("CLICK_CONTRACT_ID", skill)
                self.assertIn("contract_id", skill)
                self.assertNotIn("Python `-c`", skill)
                self.assertNotIn("three serial calls", skill)

        self.assertLessEqual(len(click_skill.split()), 900)
        self.assertLessEqual(len(fix_skill.split()), 350)

        english = (ROOT / "README.md").read_text(encoding="utf-8")
        korean = (ROOT / "README.ko.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        for readme in (english, korean, chinese):
            self.assertIn('"evidence": [', readme)
            self.assertIn('"primary_evidence":', readme)
            self.assertIn('"kind": "argv"', readme)
            self.assertIn('"evidence_id":', readme)
            self.assertIn('"version":2', readme)
            self.assertIn("click-gate evidence", readme)

        hook = (ROOT / "hooks" / "click_gate.py").read_text(encoding="utf-8")
        self.assertNotIn("BROWSER_SOURCE_MARKERS", hook)
        self.assertNotIn("BROWSER_SOURCE_TERMS", hook)
        self.assertIn('source.get("kind") == "browser"', hook)

    def test_plain_language_stays_digest_bound_and_is_rendered_once(self) -> None:
        hook = (ROOT / "hooks" / "click_gate.py").read_text(encoding="utf-8")
        documents = (
            (ROOT / "skills" / "click" / "SKILL.md").read_text(encoding="utf-8"),
            (ROOT / "skills" / "fix" / "SKILL.md").read_text(encoding="utf-8"),
            (
                ROOT
                / "skills"
                / "click"
                / "references"
                / "translation-guide.md"
            ).read_text(encoding="utf-8"),
            (
                ROOT
                / "skills"
                / "click"
                / "references"
                / "directive-format.md"
            ).read_text(encoding="utf-8"),
            (ROOT / "evals" / "SEMANTIC_GRADER.md").read_text(encoding="utf-8"),
            (ROOT / "evals" / "golden-prompts.yaml").read_text(encoding="utf-8"),
        )

        self.assertIn('STRING_FIELDS = ("outcome", "plain_language")', hook)
        for document in documents:
            with self.subTest(document=document[:40]):
                self.assertIn("digest-bound", document)
                self.assertIn("plain_language", document)
                self.assertIn("once", document)

        grader = documents[-2]
        self.assertIn("duplicate rendering as a missed invariant", grader)

        english = (ROOT / "README.md").read_text(encoding="utf-8")
        korean = (ROOT / "README.ko.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn("renders that exact value once", english)
        self.assertIn("같은 뜻을 별도의 두 번째 요약으로 다시 쓰지 않습니다", korean)
        self.assertIn("不会把同一说明输出两遍", chinese)

    def test_readmes_document_distinct_turn_approval_and_git_mutation_guard(self) -> None:
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        korean = (ROOT / "README.ko.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        for readme in (english, korean, chinese):
            self.assertIn("UserPromptSubmit", readme)
            self.assertIn("staged_turn_id", readme)
            self.assertIn("approved_turn_id", readme)
            self.assertIn("contract_id", readme)
            self.assertIn("CLICK_CONTRACT_ID=ctr_", readme)
            self.assertIn("non-ignored untracked", readme)
        self.assertIn("later user turn", english.lower())
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
            marketplace["plugins"][0]["source"]["ref"], "v0.21.1"
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

    def test_release_documents_identify_v0211_and_preserve_v021_history(self) -> None:
        for readme_name in README_NAMES:
            with self.subTest(readme=readme_name):
                readme = (ROOT / readme_name).read_text(encoding="utf-8")
                self.assertIn("v0.21.1", readme)
                self.assertIn("v0.21.0", readme)
                self.assertIn("version-18", readme)
        notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        self.assertIn("## v0.21.1", notes)
        self.assertIn("## v0.21.0", notes)
        self.assertIn("## v0.20.0", notes)
        self.assertNotIn("Unreleased v0.21", notes)
        self.assertIn(
            "## Evidence-bound completion in v0.21.0",
            (ROOT / "README.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "## v0.21.0의 증거별 완료 판정",
            (ROOT / "README.ko.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "## v0.21.0 的逐证据完成判定",
            (ROOT / "README.zh-CN.md").read_text(encoding="utf-8"),
        )

    def test_readmes_document_trusted_reads_and_pre_execution_claims(self) -> None:
        readmes = {
            name: (ROOT / name).read_text(encoding="utf-8")
            for name in README_NAMES
        }
        protocol = (
            ROOT / "skills" / "click" / "references" / "capability-protocol.md"
        ).read_text(encoding="utf-8")
        for name, readme in readmes.items():
            with self.subTest(readme=name):
                for marker in (
                    "gate-state",
                    "PLUGIN_DATA",
                    "LD_*",
                    "DYLD_*",
                    "GCONV_PATH",
                    "LOCPATH",
                    "one-use",
                    "snapshot",
                ):
                    self.assertIn(marker, readme)
        self.assertIn("Windows drive-prefixed forms", protocol)
        self.assertIn("nearest containing Git repository", protocol)
        self.assertIn("executes no mutation command", protocol)
        self.assertIn("initial protected snapshot", protocol)
        self.assertIn("concurrent same-user replacement", protocol)

    def test_completion_docs_match_per_source_and_service_state(self) -> None:
        modes = (
            ROOT / "skills" / "click" / "references" / "modes.md"
        ).read_text(encoding="utf-8")
        profiles = (
            ROOT
            / "skills"
            / "click"
            / "references"
            / "verification-profiles.md"
        ).read_text(encoding="utf-8")
        self.assertIn("every declared evidence source", modes)
        self.assertIn("no managed service remains active", modes)
        self.assertIn("no argv source", modes)
        self.assertIn("Typical argv evidence, when declared", profiles)
        self.assertIn("no argv source", profiles)

        localized_requirements = {
            "README.md": "no managed service remains active",
            "README.ko.md": "관리 서비스가 활성 상태가 아니",
            "README.zh-CN.md": "没有受管服务仍处于活动状态",
        }
        for name, phrase in localized_requirements.items():
            with self.subTest(readme=name):
                self.assertIn(
                    phrase, (ROOT / name).read_text(encoding="utf-8")
                )

    def test_readmes_explain_the_core_purpose_and_v021_update(self) -> None:
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        korean = (ROOT / "README.ko.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        for readme in (english, korean, chinese):
            self.assertIn("codex plugin marketplace upgrade click", readme)
            self.assertIn("codex plugin add click@click", readme)
        self.assertIn("## Core purpose", english)
        self.assertIn("## 핵심 목적", korean)
        self.assertIn("## 核心目的", chinese)

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
        click_metadata = (
            ROOT / "skills" / "click" / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        fix_metadata = (
            ROOT / "skills" / "fix" / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("allow_implicit_invocation: true", click_metadata)
        self.assertIn("allow_implicit_invocation: false", fix_metadata)

    def test_contract_id_is_the_canonical_approval_handoff(self) -> None:
        hook = (ROOT / "hooks" / "click_gate.py").read_text(encoding="utf-8")
        directive = (
            ROOT / "skills" / "click" / "references" / "directive-format.md"
        ).read_text(encoding="utf-8")
        grader = (ROOT / "evals" / "SEMANTIC_GRADER.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("CONTRACT_ID_PATTERN", hook)
        self.assertIn("secrets.token_hex(16)", hook)
        self.assertIn('"contract_id": contract_id', hook)
        self.assertIn("not the Execution ", hook)
        self.assertIn("Contract JSON", hook)
        self.assertNotIn("pass '<Execution Contract JSON>'", hook)

        for document in (directive, grader):
            with self.subTest(document=document[:40]):
                self.assertIn("contract_id", document)
                self.assertIn("later user turn", document)
                self.assertIn("JSON", document)
        self.assertIn("CLICK_CONTRACT_ID=ctr_", directive)
        self.assertIn("click-gate pass ctr_<32hex>", directive)
        self.assertIn("never resend", directive)

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

    def test_golden_cases_cover_always_on_manual_and_review_routing(self) -> None:
        catalog = (
            ROOT / "evals" / "golden-prompts.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("version: 18", catalog)
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
