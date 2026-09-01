from __future__ import annotations

from click_gate_test_support import (
    CLICK_BROWSER,
    CLICK_EVIDENCE,
    CLICK_GATE,
    CLICK_PROCESS,
    HOOK_CONFIG,
    Path,
    ClickGateTestCase,
    json,
    mark_git_boundary,
    mock,
    os,
    shlex,
    split_runner_command,
    subprocess,
    sys,
    tempfile,
    time,
    unittest,
)


class ClickGateBrowserTests(ClickGateTestCase):
    def test_browser_evidence_requires_an_assigned_primary_source(self) -> None:
        self.approve_contract()
        denied = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            {"code": "await page.title()", "timeout_ms": 5000},
        )
        self.assertEqual(
            denied["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "kind `browser`",
            denied["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_browser_response_classifier_requires_meaningful_success(self) -> None:
        for response in (
            {},
            {"content": []},
            {"content": [{"type": "text", "text": ""}]},
            {"output": None},
            {"result": ""},
            {"status": "cancelled", "content": ["diagnostic"]},
        ):
            with self.subTest(response=response):
                self.assertTrue(CLICK_BROWSER.response_failed(response))
        for response in (
            {"status": "success"},
            {"status": "completed"},
            {"content": [{"type": "text", "text": "ready"}]},
            {"result": False},
        ):
            with self.subTest(response=response):
                self.assertFalse(CLICK_BROWSER.response_failed(response))

    def test_lost_browser_post_event_expires_and_allows_receipt_bound_retry(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {"id": "E-browser", "kind": "browser", "description": "one session"}
        ]
        contract["verification"]["done_when"] = [
            {"condition": "the page works", "primary_evidence": "E-browser"}
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="lost-browser-post",
            )
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["external_evidence"]["browser_running"]["lost-browser-post"] = (
            time.time() - CLICK_GATE.BROWSER_RUNNING_TTL_SECONDS - 1
        )
        state_path.write_text(json.dumps(state), encoding="utf-8")

        long_retry_input = {"code": "await page.title()", "timeout_ms": 60000}
        long_retry = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            long_retry_input,
            tool_use_id="long-browser-retry",
        )
        self.assert_browser_advisory(long_retry, "timeout above 30 seconds")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertIn(
            "long-browser-retry", state["external_evidence"]["browser_running"]
        )
        running_entry = state["external_evidence"]["browser_running"][
            "long-browser-retry"
        ]
        self.assertGreater(
            running_entry["expires_at"] - running_entry["started_at"], 60
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                long_retry_input,
                tool_use_id="long-browser-retry",
                tool_response={"status": "error", "isError": True},
            )
        )

        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="browser-retry",
            )
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["external_evidence"]["browser_calls"], 3)
        self.assertIn(
            "browser-retry", state["external_evidence"]["browser_running"]
        )

    def test_browser_primary_source_uses_structured_kind_not_localized_text(self) -> None:
        conditions = (
            "layout works",
            "레이아웃이 동작한다",
            "布局正常",
            "レイアウトが動作する",
        )
        for condition in conditions:
            with self.subTest(condition=condition):
                contract = self.contract()
                contract["verification"]["evidence"] = [
                    {
                        "id": "E-browser",
                        "kind": "browser",
                        "description": "one representative session",
                    }
                ]
                contract["verification"]["done_when"] = [
                    {
                        "condition": condition,
                        "primary_evidence": "E-browser",
                    }
                ]
                self.assertTrue(CLICK_EVIDENCE.browser_required(contract))

        non_browser = self.contract()
        non_browser["verification"]["evidence"][0]["description"] = (
            "a local test whose name happens to contain browser"
        )
        self.assertFalse(CLICK_EVIDENCE.browser_required(non_browser))

    def test_browser_receipt_binding_and_serial_interlock_remain_hard(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {"id": "E-browser", "kind": "browser", "description": "one session"}
        ]
        contract["verification"]["done_when"] = [
            {"condition": "the page works", "primary_evidence": "E-browser"}
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        input_value = {"code": "await page.title()", "timeout_ms": 5000}
        missing_identity = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            input_value,
            tool_use_id="",
        )
        self.assertEqual(
            missing_identity["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "stable tool_use_id",
            missing_identity["hookSpecificOutput"]["permissionDecisionReason"],
        )

        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                input_value,
                tool_use_id="browser-serial-1",
            )
        )
        parallel = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            {"code": "await page.url()", "timeout_ms": 5000},
            tool_use_id="browser-serial-2",
        )
        self.assertEqual(parallel["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "already running",
            parallel["hookSpecificOutput"]["permissionDecisionReason"],
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                input_value,
                tool_use_id="browser-serial-1",
                tool_response={"status": "success"},
            )
        )

    def test_browser_attempt_history_compacts_instead_of_blocking(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {"id": "E-browser", "kind": "browser", "description": "one session"}
        ]
        contract["verification"]["done_when"] = [
            {"condition": "the page works", "primary_evidence": "E-browser"}
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        attempts = {
            f"old-attempt-{index}": {
                "status": "failed",
                "attempts": 1,
                "unchanged_retries": 0,
                "successful_attempts": 0,
                "failed_attempts": 1,
            }
            for index in range(CLICK_GATE.MAX_BROWSER_UNIQUE_INPUTS)
        }
        state["external_evidence"]["browser_attempts"] = attempts
        state_path.write_text(json.dumps(state), encoding="utf-8")

        input_value = {"code": "await page.title()", "timeout_ms": 5000}
        advised = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            input_value,
            tool_use_id="browser-after-compaction",
        )
        self.assert_browser_advisory(advised, "attempt guidance was compacted")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        retained = state["external_evidence"]["browser_attempts"]
        self.assertEqual(len(retained), CLICK_GATE.MAX_BROWSER_UNIQUE_INPUTS)
        self.assertNotIn("old-attempt-0", retained)
        self.assertIn(CLICK_BROWSER.attempt_digest(input_value), retained)
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                input_value,
                tool_use_id="browser-after-compaction",
                tool_response={"status": "success"},
            )
        )

    def test_browser_workflow_tuning_is_advisory_without_a_call_cap(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {
                "id": "E-browser",
                "kind": "browser",
                "description": "one representative input and layout session",
            }
        ]
        contract["verification"]["done_when"] = [
            {
                "condition": "input and responsive layout work",
                "primary_evidence": "E-browser",
            }
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        timed_input = {
            "code": "await page.waitForTimeout(55000)",
            "timeout_ms": 60000,
        }
        timed = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            timed_input,
            tool_use_id="browser-timed",
        )
        self.assert_browser_advisory(timed, "timeout above 30 seconds")
        self.assertIn(
            "explicit wait above five seconds",
            timed["hookSpecificOutput"]["additionalContext"],
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                timed_input,
                tool_use_id="browser-timed",
                tool_response={"status": "error", "isError": True},
            )
        )

        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="browser-1",
            )
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="browser-1",
                tool_response={"status": "success"},
            )
        )

        self.base_event["model"] = "another-frontier-model"
        duplicate_input = {
            "code": "  await page.title()\r\n",
            "timeout_ms": 12000,
            "_meta": {"trace": "different bookkeeping"},
        }
        duplicate = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            duplicate_input,
            tool_use_id="browser-duplicate",
        )
        self.assert_browser_advisory(
            duplicate, "normalized Browser interaction already succeeded"
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                duplicate_input,
                tool_use_id="browser-duplicate",
                tool_response={"status": "success"},
            )
        )

        for index in range(2, 7):
            tool_id = f"browser-{index}"
            code = f"await page.locator('main').count(); // {index}"
            self.assertIsNone(
                self.tool_hook(
                    "pre-tool",
                    "mcp__node_repl__js",
                    {"code": code, "timeout_ms": 5000},
                    tool_use_id=tool_id,
                )
            )
            self.assertIsNone(
                self.tool_hook(
                    "post-tool",
                    "mcp__node_repl__js",
                    {"code": code, "timeout_ms": 5000},
                    tool_use_id=tool_id,
                    tool_response={"status": "success"},
                )
            )

    def test_browser_failure_retry_is_per_input_and_observed_is_monotonic(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {
                "id": "E-browser",
                "kind": "browser",
                "description": "one representative browser session",
            }
        ]
        contract["verification"]["done_when"] = [
            {
                "condition": "the representative session works",
                "primary_evidence": "E-browser",
            }
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        successful_input = {"code": "await page.title()", "timeout_ms": 5000}
        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                successful_input,
                tool_use_id="browser-success",
            )
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                successful_input,
                tool_use_id="browser-success",
                tool_response={"status": "success"},
            )
        )

        failing_input = {"code": "await missing.locator()", "timeout_ms": 5000}
        for attempt in range(2):
            tool_id = f"browser-failure-{attempt}"
            self.assertIsNone(
                self.tool_hook(
                    "pre-tool",
                    "mcp__node_repl__js",
                    failing_input,
                    tool_use_id=tool_id,
                )
            )
            self.assertIsNone(
                self.tool_hook(
                    "post-tool",
                    "mcp__node_repl__js",
                    failing_input,
                    tool_use_id=tool_id,
                    tool_response={"status": "error", "isError": True},
                )
            )

        advised = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            failing_input,
            tool_use_id="browser-failure-advised",
        )
        self.assert_browser_advisory(
            advised, "failed or produced incomplete evidence twice"
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                failing_input,
                tool_use_id="browser-failure-advised",
                tool_response={"status": "error", "isError": True},
            )
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        source = state["evidence_state"]["sources"][
            CLICK_EVIDENCE.evidence_key("E-browser")
        ]
        self.assertEqual(state["external_evidence"]["browser_status"], "observed")
        self.assertEqual(source["status"], "observed")

    def test_browser_primary_source_is_required_for_contract_completion(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {
                "id": "E-browser",
                "kind": "browser",
                "description": "one representative visual integration session",
            }
        ]
        contract["verification"]["done_when"] = [
            {
                "condition": "visual integration works",
                "primary_evidence": "E-browser",
            }
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            state["external_evidence"]["browser_source_key"],
            CLICK_EVIDENCE.evidence_key("E-browser"),
        )
        self.assertFalse(CLICK_GATE._contract_is_completed(state))
        premature = self.complete_evidence("E-browser")
        self.assertEqual(
            premature["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "successful current-revision Browser call",
            premature["hookSpecificOutput"]["permissionDecisionReason"],
        )

        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="completion-browser",
            )
        )
        self.tool_hook(
            "post-tool",
            "mcp__node_repl__js",
            {"code": "await page.title()", "timeout_ms": 5000},
            tool_use_id="completion-browser",
            tool_response={"status": "success"},
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(CLICK_GATE._contract_is_completed(state))
        completed = self.complete_evidence("E-browser")
        self.assertEqual(
            completed["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(CLICK_GATE._contract_is_completed(state))
        repeated = self.tool_hook(
            "pre-tool",
            "mcp__node_repl__js",
            {"code": "await page.title()", "timeout_ms": 5000},
            tool_use_id="completion-browser-2",
        )
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "contract is complete",
            repeated["hookSpecificOutput"]["permissionDecisionReason"],
        )
        self.prompt_submit("open an unrelated browser reference", "turn-3")
        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                turn_id="turn-3",
                tool_use_id="unrelated-browser",
            )
        )

    def test_empty_browser_tool_response_is_not_completion_evidence(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {"id": "E-browser", "kind": "browser", "description": "one session"}
        ]
        contract["verification"]["done_when"] = [
            {"condition": "the page works", "primary_evidence": "E-browser"}
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="empty-browser-response",
            )
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="empty-browser-response",
                tool_response={},
            )
        )
        denied = self.complete_evidence("E-browser")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "successful current-revision Browser call",
            denied["hookSpecificOutput"]["permissionDecisionReason"],
        )
        self.assertIsNone(
            self.tool_hook(
                "pre-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="cancelled-browser-response",
            )
        )
        self.assertIsNone(
            self.tool_hook(
                "post-tool",
                "mcp__node_repl__js",
                {"code": "await page.title()", "timeout_ms": 5000},
                tool_use_id="cancelled-browser-response",
                tool_response={"status": "cancelled", "content": ["diagnostic"]},
            )
        )
        denied = self.complete_evidence("E-browser")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
