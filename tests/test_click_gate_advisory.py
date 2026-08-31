from __future__ import annotations

from click_gate_test_support import (
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


class ClickGateAdvisoryTests(ClickGateTestCase):
    def test_review_mode_needs_no_contract_and_advises_repeated_successful_reads(self) -> None:
        self.set_default("on")
        review = self.start_review()
        self.assertEqual(
            review["hookSpecificOutput"]["updatedInput"]["command"],
            "echo Click read-only review guard armed",
        )
        (self.workspace / "review.py").write_text("value = 1\n", encoding="utf-8")
        command = self.read_file_command("review.py")
        first = self.pre_tool("Bash", command)
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertEqual(self.run_rewritten(first).returncode, 0)

        repeated = self.pre_tool("Bash", command)
        self.assert_observation_advisory(
            repeated, "identical read or search already succeeded"
        )
        self.assertEqual(self.run_rewritten(repeated).returncode, 0)

    def test_review_mode_advises_narrowing_after_root_inventory(self) -> None:
        self.set_default("on")
        self.start_review()
        (self.workspace / "review.py").write_text("value = 1\n", encoding="utf-8")
        initialized = subprocess.run(
            ["git", "init", "--quiet"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        first = self.pre_tool("Bash", "git ls-files")
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertEqual(self.run_rewritten(first).returncode, 0)

        second = self.pre_tool("Bash", "git ls-files --cached")
        self.assert_observation_advisory(second, "already completed")
        self.assertEqual(self.run_rewritten(second).returncode, 0)

        identical = self.pre_tool("Bash", "git ls-files")
        self.assert_observation_advisory(
            identical, "identical read or search already succeeded"
        )
        self.assertEqual(self.run_rewritten(identical).returncode, 0)

    def test_review_mode_keeps_mutations_blocked_but_advises_plan(self) -> None:
        self.set_default("on")
        self.start_review()

        plan = self.pre_tool("update_plan", "")
        self.assert_plan_advisory(plan, "read-only review")
        assert plan is not None
        self.assertIn(
            "does not authorize mutation",
            plan["hookSpecificOutput"]["additionalContext"],
        )

        mutation = self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch")
        self.assertEqual(
            mutation["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn("read-only", mutation["hookSpecificOutput"]["permissionDecisionReason"])

    def test_simple_read_only_inspection_is_not_tracked_outside_review(self) -> None:
        self.set_default("on")
        (self.workspace / "readme.txt").write_text("hello\n", encoding="utf-8")
        command = self.read_file_command("readme.txt")
        first = self.pre_tool("Bash", command)
        second = self.pre_tool("Bash", command)
        for payload in (first, second):
            self.assertEqual(
                payload["hookSpecificOutput"]["permissionDecision"], "allow"
            )
            self.assertIn(
                "run-inspection-once",
                split_runner_command(
                    payload["hookSpecificOutput"]["updatedInput"]["command"]
                ),
            )

    def test_always_on_bypass_is_limited_to_the_current_turn(self) -> None:
        self.set_default("on")
        self.bypass_gate()
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch")
        )
        blocked = self.pre_tool(
            "apply_patch", "*** Begin Patch\n*** End Patch", turn_id="turn-2"
        )
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_always_on_can_stage_and_pass_without_explicit_arm(self) -> None:
        self.set_default("on")
        staged = self.stage_gate(turn_id="turn-1")
        self.assertEqual(staged["hookSpecificOutput"]["permissionDecision"], "allow")
        passed = self.pass_gate(turn_id="turn-2")
        self.assertEqual(passed["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_identical_successful_read_is_advised_until_mutation(self) -> None:
        (self.workspace / "README.md").write_text("hello\n", encoding="utf-8")
        self.approve_contract()
        command = self.read_file_command("README.md")

        first = self.pre_tool("Bash", command, "turn-2")
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        completed = self.run_rewritten(first)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "hello")

        repeated = self.pre_tool("Bash", command, "turn-2")
        self.assert_observation_advisory(
            repeated, "identical read or search already succeeded"
        )
        first_runner = self.observation_runner_arguments(first)
        repeated_runner = self.observation_runner_arguments(repeated)
        self.assertEqual(first_runner[1], repeated_runner[1])
        self.assertNotEqual(first_runner[2], repeated_runner[2])
        self.assertEqual(self.run_rewritten(repeated).returncode, 0)

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        after_mutation = self.pre_tool("Bash", command, "turn-2")
        self.assertEqual(
            after_mutation["hookSpecificOutput"]["permissionDecision"], "allow"
        )

    def test_observation_digest_normalizes_shell_spacing(self) -> None:
        (self.workspace / "README.md").write_text("hello\n", encoding="utf-8")
        self.approve_contract()

        first = self.pre_tool(
            "Bash", "sed -n '1,99999p' README.md", "turn-2"
        )
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        repeated = self.pre_tool(
            "Bash", "sed   -n   '1,99999p'   README.md", "turn-2"
        )
        self.assert_observation_advisory(
            repeated, "identical read or search already succeeded"
        )
        self.assertEqual(self.run_rewritten(repeated).returncode, 0)

    def test_identical_cat_read_is_observed_and_advised(self) -> None:
        (self.workspace / "README.md").write_text("hello\n", encoding="utf-8")
        self.approve_contract()

        first = self.pre_tool("Bash", "cat README.md", "turn-2")
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        completed = self.run_rewritten(first)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "hello")

        repeated = self.pre_tool("Bash", "cat README.md", "turn-2")
        self.assert_observation_advisory(
            repeated, "identical read or search already succeeded"
        )
        self.assertEqual(self.run_rewritten(repeated).returncode, 0)

    def test_running_observation_blocks_mutation_and_final_verification(self) -> None:
        (self.workspace / "README.md").write_text("hello\n", encoding="utf-8")
        self.approve_contract()
        observation = self.pre_tool(
            "Bash", self.read_file_command("README.md"), "turn-2"
        )
        self.assertEqual(
            observation["hookSpecificOutput"]["permissionDecision"], "allow"
        )

        mutation = self.pre_tool(
            "apply_patch", "*** Begin Patch\n*** End Patch", "turn-2"
        )
        self.assertEqual(
            mutation["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "read or search is running",
            mutation["hookSpecificOutput"]["permissionDecisionReason"],
        )

        verification = self.verify_gate([self.verification_argv()])
        self.assertEqual(
            verification["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "read or search to finish",
            verification["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_failed_or_incomplete_read_advises_after_bounded_retry(self) -> None:
        self.approve_contract()
        missing = self.read_file_command("missing.txt", fail_hard=True)

        first_failure = self.pre_tool("Bash", missing, "turn-2")
        self.assertNotEqual(self.run_rewritten(first_failure).returncode, 0)
        retry_failure = self.pre_tool("Bash", missing, "turn-2")
        self.assertNotEqual(self.run_rewritten(retry_failure).returncode, 0)
        blocked_failure = self.pre_tool("Bash", missing, "turn-2")
        self.assert_observation_advisory(
            blocked_failure, "failed or produced incomplete output twice"
        )
        self.assertNotEqual(self.run_rewritten(blocked_failure).returncode, 0)

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        (self.workspace / "large.txt").write_text(
            "x" * 60_000, encoding="utf-8"
        )
        large = self.read_file_command("large.txt")
        first_large = self.pre_tool("Bash", large, "turn-2")
        completed = self.run_rewritten(first_large)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("exceeded 48,000 bytes", completed.stderr)
        retry_large = self.pre_tool("Bash", large, "turn-2")
        self.assertEqual(
            retry_large["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertEqual(self.run_rewritten(retry_large).returncode, 0)
        blocked_large = self.pre_tool("Bash", large, "turn-2")
        self.assert_observation_advisory(
            blocked_large, "failed or produced incomplete output twice"
        )
        self.assertEqual(self.run_rewritten(blocked_large).returncode, 0)

    def test_approved_boundary_advises_broad_rescans_and_resets_on_mutation(
        self,
    ) -> None:
        (self.workspace / "threshold.txt").write_text(
            "threshold\n", encoding="utf-8"
        )
        self.initialize_git("threshold.txt", "verification_fixture.py")
        self.approve_contract()
        first = self.pre_tool("Bash", "git ls-files", "turn-2")
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        parallel = self.pre_tool(
            "Bash", "git ls-files --cached", "turn-2"
        )
        self.assert_observation_advisory(parallel, "already running")
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        self.assertEqual(self.run_rewritten(parallel).returncode, 0)

        repeated = self.pre_tool("Bash", "git ls-files --stage", "turn-2")
        self.assert_observation_advisory(repeated, "already completed")
        self.assertEqual(self.run_rewritten(repeated).returncode, 0)

        for command in (
            "git ls-files -- src",
            "git ls-tree -r HEAD -- src",
        ):
            with self.subTest(command=command):
                payload = self.pre_tool("Bash", command, "turn-2")
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "allow"
                )
                self.run_rewritten(payload)

        targeted = self.pre_tool(
            "Bash", "Get-Content -Raw threshold.txt", "turn-2"
        )
        self.assertEqual(
            targeted["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertEqual(self.run_rewritten(targeted).returncode, 0)

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        after_mutation = self.pre_tool("Bash", "git ls-files", "turn-2")
        self.assertEqual(
            after_mutation["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertNotIn("additionalContext", after_mutation["hookSpecificOutput"])

    def test_approved_contract_advises_plan_but_still_blocks_replacement(self) -> None:
        self.approve_contract()
        for tool_name in ("update_plan", "functions.update_plan"):
            with self.subTest(tool_name=tool_name):
                payload = self.pre_tool(tool_name, "", "turn-2")
                self.assert_plan_advisory(payload, "approved contract")
                assert payload is not None
                self.assertIn(
                    "remains authoritative",
                    payload["hookSpecificOutput"]["additionalContext"],
                )

        replacement = self.contract()
        replacement["outcome"] = "replace the approved outcome without new authority"
        blocked = self.stage_gate(replacement, "turn-2")
        self.assertEqual(
            blocked["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "already executing one approved contract",
            blocked["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_armed_contract_workflow_advises_plan_tool_calls(self) -> None:
        self.arm_gate("turn-1")
        for tool_name in ("update_plan", "functions.update_plan"):
            with self.subTest(tool_name=tool_name):
                payload = self.pre_tool(tool_name, "", "turn-1")
                self.assert_plan_advisory(payload, "contract workflow")

    def test_staged_session_contract_advises_plan_in_a_later_turn(self) -> None:
        self.arm_gate("turn-1")
        self.stage_gate(turn_id="turn-1")
        payload = self.pre_tool("update_plan", "", "turn-2")
        self.assert_plan_advisory(payload, "approved contract")

    def test_approved_session_contract_advises_plan_in_a_later_turn(self) -> None:
        self.approve_contract()
        payload = self.pre_tool("update_plan", "", "turn-3")
        self.assert_plan_advisory(payload, "approved contract")

    def test_completed_contract_allows_plan_in_a_fresh_uninvoked_turn(self) -> None:
        self.approve_contract()
        verification = self.verify_gate([self.verification_argv()])
        result = self.run_rewritten(verification)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(self.pre_tool("update_plan", "", "turn-3"))

    def test_bypass_allows_plan_in_the_current_turn(self) -> None:
        self.arm_gate("turn-1")
        self.bypass_gate("turn-1")
        self.assertIsNone(self.pre_tool("update_plan", "", "turn-1"))
