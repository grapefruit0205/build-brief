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

    def test_readmes_document_automatic_budget_and_its_limit(self) -> None:
        readmes = _readmes()
        for readme in readmes.values():
            self.assertIn("click-gate verify", readme)
            self.assertIn("evidence_id", readme)
            self.assertIn("10", readme)
        self.assertIn("Automatic verification budget", readmes["README.md"])
        self.assertIn("자동 검증 예산", readmes["README.ko.md"])
        self.assertIn("自动验证预算", readmes["README.zh-CN.md"])

        profiles = _reference("verification-profiles.md")
        for marker in ("Automatic ceiling", "Python `-c`", "minimum class", "custom program", "wrapper"):
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

        hook = (ROOT / "hooks" / "click_gate.py").read_text(encoding="utf-8")
        self.assertIn("staged_turn_id", hook)
        self.assertIn("approved_turn_id", hook)
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
        self.assertIn("observable tool path", readmes["README.md"])
        self.assertIn("관찰 가능한 tool path", readmes["README.ko.md"])
        self.assertIn("可观察的 tool path", readmes["README.zh-CN.md"])
        anti_loop = _reference("anti-loop-policy.md")
        for marker in ("48,000", "update_plan", "hidden reasoning", "Inventory once, then narrow"):
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

    def test_release_documents_identify_v0245_and_preserve_release_history(self) -> None:
        for readme in _readmes().values():
            self.assertIn("v0.24.5", readme)
            self.assertIn("codex plugin marketplace upgrade click", readme)
            self.assertIn("codex plugin add click@click", readme)
        notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        for marker in (
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
        self.assertIn("version: 18", golden)

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


if __name__ == "__main__":
    unittest.main()
