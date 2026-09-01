from __future__ import annotations

import json
import unittest

import repository_policy_core as core


ROOT = core.ROOT
README_NAMES = core.README_NAMES


def _readmes() -> dict[str, str]:
    return {name: (ROOT / name).read_text(encoding="utf-8") for name in README_NAMES}


def _reference(name: str) -> str:
    return (ROOT / "skills" / "click" / "references" / name).read_text(encoding="utf-8")


class RepositoryPolicyTests(core.RepositoryPolicyTests):
    """Preserve the full policy suite while keeping protocol internals out of the README hero."""

    def test_manifest_declares_click_one_shot_release(self) -> None:
        manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "click")
        self.assertEqual(manifest["version"], "0.34.0")
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
        self.assertIn(
            "plan tools and distinct-digest broad inventories remain available with non-blocking advisory guidance",
            manifest["interface"]["longDescription"].lower(),
        )
        self.assertIn(
            "cannot alter contract authority",
            manifest["interface"]["longDescription"].lower(),
        )
        self.assertIn(
            "fresh repeated observations and ordinary argv retries",
            manifest["interface"]["longDescription"].lower(),
        )
        self.assertIn(
            "consumed-token replay",
            manifest["interface"]["longDescription"].lower(),
        )
        self.assertIn(
            "verification-time repository mutation",
            manifest["interface"]["longDescription"].lower(),
        )
        self.assertIn(
            "known-surface hook coverage digest",
            manifest["interface"]["longDescription"].lower(),
        )
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
        self.assertIn("revision-bound evidence", manifest["description"].lower())
        self.assertEqual(
            manifest["interface"]["shortDescription"],
            "Bind AI execution to approved intent and return verifiable evidence.",
        )
        self.assertLessEqual(len(manifest["interface"]["defaultPrompt"]), 3)
        for prompt in manifest["interface"]["defaultPrompt"]:
            self.assertLessEqual(len(prompt), 128)

    def test_marketplace_exposes_click_from_the_click_catalog(self) -> None:
        marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(marketplace["name"], "click")
        self.assertEqual(marketplace["plugins"][0]["name"], "click")
        self.assertEqual(
            marketplace["plugins"][0]["source"]["ref"], "v0.34.0"
        )

    def test_readmes_lead_with_hook_enforced_state_machine_positioning(self) -> None:
        english, korean, chinese = _readmes().values()
        for marker in (
            "Prompt-only coding workflows are over",
            "Prompts can suggest behavior. Hooks can enforce the workflow",
            "persistent Hook state machine",
            "observable execution path",
        ):
            self.assertIn(marker, english)
        for marker in (
            "프롬프트만으로 코딩 워크플로우를 제어하던 시대는 끝났습니다",
            "Hook은 워크플로우를 강제할 수 있습니다",
            "Hook 상태 머신",
            "관찰 가능한 실행 경로",
        ):
            self.assertIn(marker, korean)
        for marker in (
            "只靠提示词控制编码工作流的时代已经结束",
            "Hook 可以强制执行工作流",
            "Hook 状态机",
            "可观察的执行路径",
        ):
            self.assertIn(marker, chinese)

    def test_readmes_document_qualitative_profiles_and_exact_receipts(self) -> None:
        readmes = _readmes()
        for readme in readmes.values():
            self.assertIn("click-gate verify", readme)
            self.assertIn("evidence_id", readme)
        self.assertIn("Advisory verification profiles", readmes["README.md"])
        self.assertIn("Advisory 검증 profile", readmes["README.ko.md"])
        self.assertIn("Advisory 验证 profile", readmes["README.zh-CN.md"])

        profiles = _reference("verification-profiles.md")
        for marker in ("qualitative profile", "Python `-c`", "compatibility", "custom program", "wrapper"):
            self.assertIn(marker.lower(), profiles.lower())

    def test_plain_language_stays_digest_bound_and_is_rendered_once(self) -> None:
        hook = (ROOT / "hooks" / "click_gate.py").read_text(encoding="utf-8")
        contract_runtime = (ROOT / "hooks" / "click_contract.py").read_text(encoding="utf-8")
        self.assertIn('STRING_FIELDS = ("outcome", "plain_language")', contract_runtime)
        self.assertIn("STRING_FIELDS = click_contract.STRING_FIELDS", hook)
        documents = (
            ROOT / "skills" / "click" / "SKILL.md",
            ROOT / "skills" / "fix" / "SKILL.md",
            ROOT / "skills" / "click" / "references" / "translation-guide.md",
            ROOT / "skills" / "click" / "references" / "directive-format.md",
            ROOT / "evals" / "SEMANTIC_GRADER.md",
            ROOT / "evals" / "golden-prompts.yaml",
        )
        for path in documents:
            text = path.read_text(encoding="utf-8")
            for marker in ("digest-bound", "plain_language", "once"):
                self.assertIn(marker, text)
        grader = (ROOT / "evals" / "SEMANTIC_GRADER.md").read_text(encoding="utf-8")
        self.assertIn("duplicate rendering as a missed invariant", grader)
        for readme in _readmes().values():
            self.assertIn("plain_language", readme)

    def test_readmes_document_distinct_turn_approval_and_git_mutation_guard(self) -> None:
        readmes = _readmes()
        for readme in readmes.values():
            self.assertIn("contract_id", readme)
            self.assertIn("evidence_id", readme)
        self.assertIn("Later user turn", readmes["README.md"])
        self.assertIn("다음 turn의 사용자 승인", readmes["README.ko.md"])
        self.assertIn("后续用户 turn 批准", readmes["README.zh-CN.md"])

        lifecycle = (ROOT / "hooks" / "click_lifecycle.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("staged_turn_id", lifecycle)
        self.assertIn("approved_turn_id", lifecycle)
        hook_config = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        self.assertIn("UserPromptSubmit", hook_config["hooks"])
        directive = _reference("directive-format.md")
        self.assertIn("CLICK_CONTRACT_ID=ctr_", directive)
        self.assertIn("later user turn", directive)
        self.assertIn("non-ignored untracked", _reference("capability-protocol.md"))

    def test_readmes_document_observable_anti_loop_guards_and_limits(self) -> None:
        readmes = _readmes()
        for readme in readmes.values():
            self.assertIn("update_plan", readme)
        self.assertIn("non-blocking guidance", readmes["README.md"])
        self.assertIn("비차단 안내", readmes["README.ko.md"])
        self.assertIn("非阻断提示", readmes["README.zh-CN.md"])
        self.assertIn("observable tool path", readmes["README.md"])
        self.assertIn("관찰 가능한 tool path", readmes["README.ko.md"])
        self.assertIn("可观察的 tool path", readmes["README.zh-CN.md"])
        self.assertIn("distinct-digest broad inventory remains available", readmes["README.md"])
        self.assertIn("서로 다른 digest의 broad inventory", readmes["README.ko.md"])
        self.assertIn("不同 digest 的 broad inventory", readmes["README.zh-CN.md"])
        self.assertIn("fresh identical structured read/search", readmes["README.md"])
        self.assertIn("동일 structured read/search의 새 요청", readmes["README.ko.md"])
        self.assertIn("相同 structured read/search 发起新请求", readmes["README.zh-CN.md"])
        anti_loop = _reference("anti-loop-policy.md")
        for marker in (
            "48,000",
            "update_plan",
            "hidden reasoning",
            "Prefer narrow follow-up after broad context",
            "fresh authorization",
            "Verification that changed protected repository content",
        ):
            self.assertIn(marker, anti_loop)

    def test_readmes_document_structured_capabilities_and_shell_boundary(self) -> None:
        for readme in _readmes().values():
            for marker in (
                "click-gate inspect",
                "click-gate mutate",
                "click-gate service",
                "click-gate verify",
                '"version":1',
                '"version":2',
            ):
                self.assertIn(marker, readme)
        protocol = _reference("capability-protocol.md")
        for marker in ("shell=False", "process group", "process-control", "pkill"):
            self.assertIn(marker, protocol)

    def test_release_documents_identify_current_and_preserve_release_history(self) -> None:
        for readme in _readmes().values():
            self.assertIn("v0.34.0", readme)
            self.assertIn("codex plugin marketplace upgrade click", readme)
            self.assertIn("codex plugin add click@click", readme)
        notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        for marker in (
            "## v0.34.0",
            "## v0.33.0",
            "## v0.32.0",
            "## v0.31.0",
            "## v0.30.0",
            "## v0.24.6",
            "## v0.24.5",
            "## v0.24.4",
            "## v0.24.3",
            "## v0.24.1",
            "## v0.24.0",
            "## v0.23.0",
            "## v0.22.0",
            "## v0.21.1",
            "## v0.21.0",
            "## v0.20.0",
        ):
            self.assertIn(marker, notes)
        self.assertNotIn("Unreleased v0.24", notes)
        golden = (ROOT / "evals" / "golden-prompts.yaml").read_text(encoding="utf-8")
        self.assertIn("version: 22", golden)

    def test_readmes_document_trusted_reads_and_pre_execution_claims(self) -> None:
        readmes = _readmes()
        self.assertIn("capability protocol", readmes["README.md"].lower())
        self.assertIn("capability protocol", readmes["README.ko.md"].lower())
        self.assertIn("能力协议", readmes["README.zh-CN.md"])
        for readme in readmes.values():
            self.assertIn("workflow guardrail", readme)

        protocol = _reference("capability-protocol.md")
        for marker in (
            "gate-state", "LD_*", "DYLD_*", "GCONV_PATH", "LOCPATH",
            "one-use", "snapshot", "Windows drive-prefixed forms",
            "nearest containing Git repository", "executes no mutation command",
            "initial protected snapshot", "concurrent same-user replacement",
        ):
            self.assertIn(marker, protocol)

    def test_completion_docs_match_per_source_and_service_state(self) -> None:
        modes = _reference("modes.md")
        profiles = _reference("verification-profiles.md")
        for marker in ("every declared evidence source", "no managed service remains active", "no argv source"):
            self.assertIn(marker, modes)
        self.assertIn("Typical argv evidence, when declared", profiles)
        self.assertIn("no argv source", profiles)
        for readme in _readmes().values():
            self.assertIn("current", readme)
            self.assertIn("managed service", readme)

    def test_readmes_explain_the_core_purpose_and_v021_update(self) -> None:
        readmes = _readmes()
        for readme in readmes.values():
            self.assertIn("codex plugin marketplace upgrade click", readme)
            self.assertIn("codex plugin add click@click", readme)
            self.assertIn("Hook", readme)
            self.assertIn("contract", readme.lower())
        self.assertIn("## Why Click?", readmes["README.md"])
        self.assertIn("## 왜 Click인가요?", readmes["README.ko.md"])
        self.assertIn("## 为什么需要 Click？", readmes["README.zh-CN.md"])

    def test_multiplatform_adapter_is_documented_without_false_parity(self) -> None:
        readmes = _readmes()
        for value, heading in (
            (readmes["README.md"], "Google Antigravity adapter"),
            (readmes["README.ko.md"], "Google Antigravity 어댑터"),
            (readmes["README.zh-CN.md"], "Google Antigravity 适配器"),
        ):
            self.assertIn(heading, value)
            self.assertIn("dist/antigravity", value)
            self.assertIn("Browser evidence", value)
        platform = (ROOT / "platforms" / "antigravity" / "README.md").read_text(encoding="utf-8")
        self.assertIn("model_stop", platform)
        self.assertIn("cannot rewrite tool arguments", platform)
        self.assertIn("not claimed", platform)
        self.assertIn("control inspect", platform)
        self.assertIn("non-blocking narrowing advisory", platform)

    def test_dependency_aware_receipts_are_opt_in_and_documented(self) -> None:
        readmes = _readmes()
        for readme in readmes.values():
            self.assertIn('"dependencies":', readme)
            self.assertIn(".click/evidence-dependencies.json", readme)
        directive = _reference("directive-format.md")
        protocol = _reference("capability-protocol.md")
        self.assertIn("Omit `dependencies` when uncertain", directive)
        for marker in (
            "dependency-aware cross-revision reuse",
            "relevant normalized entry",
            "PostToolUse",
            "Repository-internal relative symlinks",
        ):
            self.assertIn(marker, protocol)
        hook_config = json.loads(
            (ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        post_matchers = [
            entry.get("matcher", "")
            for entry in hook_config["hooks"]["PostToolUse"]
        ]
        self.assertTrue(any("apply_patch" in matcher for matcher in post_matchers))


if __name__ == "__main__":
    unittest.main()
