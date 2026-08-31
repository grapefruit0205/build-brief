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


class ClickGateContractTests(ClickGateTestCase):
    def test_invalid_contract_is_denied(self) -> None:
        command = (
            "click-gate stage "
            "'{\"outcome\":\"API 동작을 수정합니다.\","
            "\"plain_language\":\"기존 API 동작을 유지합니다.\","
            "\"boundary\":{\"in_scope\":[\"api\"],\"out_of_scope\":[]}}'"
        )
        payload = self.pre_tool("Bash", command)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("must_hold", output["permissionDecisionReason"])

    def test_contract_requires_structured_evidence_references(self) -> None:
        cases: list[tuple[str, dict, str]] = []

        missing_evidence = self.contract()
        del missing_evidence["verification"]["evidence"]
        cases.append(("missing evidence", missing_evidence, "evidence"))

        inline_string = self.contract()
        inline_string["verification"]["done_when"] = [
            "behavior works — primary evidence: one browser session"
        ]
        cases.append(("inline string", inline_string, "inline evidence strings"))

        duplicate_id = self.contract()
        duplicate_id["verification"]["evidence"].append(
            {
                "id": "E1",
                "kind": "manual",
                "description": "manual observation",
            }
        )
        cases.append(("duplicate id", duplicate_id, "must be unique"))

        unknown_reference = self.contract()
        unknown_reference["verification"]["done_when"][0][
            "primary_evidence"
        ] = "E-missing"
        cases.append(("unknown reference", unknown_reference, "unknown evidence id"))

        unsupported_kind = self.contract()
        unsupported_kind["verification"]["evidence"][0]["kind"] = "vector-match"
        cases.append(("unsupported kind", unsupported_kind, "kind must be one of"))

        unused_source = self.contract()
        unused_source["verification"]["evidence"].append(
            {
                "id": "E2",
                "kind": "hosted",
                "description": "hosted deployment status",
            }
        )
        cases.append(("unused source", unused_source, "are unused"))

        for label, contract, expected in cases:
            with self.subTest(label=label):
                value, error = CLICK_GATE._validate_contract(json.dumps(contract))
                self.assertIsNone(value)
                self.assertIn(expected, error)

    def test_one_structured_evidence_source_can_cover_multiple_conditions(self) -> None:
        contract = self.contract()
        contract["verification"]["done_when"].append(
            {
                "condition": "the existing inventory write remains compatible",
                "primary_evidence": "E1",
            }
        )
        value, error = CLICK_GATE._validate_contract(json.dumps(contract))
        self.assertEqual(error, "")
        self.assertEqual(value, contract)

    def test_contract_profile_does_not_limit_argv_reservations(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        contract["verification"]["evidence"].append(
            {"id": "E2", "kind": "argv", "description": "second local check"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "compatibility remains", "primary_evidence": "E2"}
        )
        value, error = CLICK_GATE._validate_contract(json.dumps(contract))
        self.assertEqual(error, "")
        self.assertEqual(value, contract)

        full = self.contract()
        full["verification"]["scale"] = "full"
        for index in range(2, 10):
            evidence_id = f"E{index}"
            full["verification"]["evidence"].append(
                {"id": evidence_id, "kind": "argv", "description": f"check {index}"}
            )
            full["verification"]["done_when"].append(
                {"condition": f"condition {index}", "primary_evidence": evidence_id}
            )
        value, error = CLICK_GATE._validate_contract(json.dumps(full))
        self.assertEqual(error, "")
        self.assertEqual(value, full)

        for index in range(10, 12):
            evidence_id = f"E{index}"
            full["verification"]["evidence"].append(
                {"id": evidence_id, "kind": "argv", "description": f"check {index}"}
            )
            full["verification"]["done_when"].append(
                {"condition": f"condition {index}", "primary_evidence": evidence_id}
            )
        value, error = CLICK_GATE._validate_contract(json.dumps(full))
        self.assertEqual(error, "")
        self.assertEqual(value, full)

    def test_verification_check_requires_a_declared_argv_evidence_id(self) -> None:
        self.approve_contract()
        check = {"argv": self.verification_argv(), "class": "targeted"}

        missing = self.verify_checks([check], bind_default=False)
        self.assertEqual(
            missing["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "evidence_id",
            missing["hookSpecificOutput"]["permissionDecisionReason"],
        )

        old_batch = {
            "version": 1,
            "checks": [{"evidence_id": "E1", **check}],
        }
        old_request = self.pre_tool(
            "Bash",
            f"click-gate verify {shlex.quote(json.dumps(old_batch))}",
            "turn-2",
        )
        self.assertEqual(
            old_request["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "version` must be 2",
            old_request["hookSpecificOutput"]["permissionDecisionReason"],
        )

        unknown = self.verify_checks(
            [{"evidence_id": "E9", **check}], bind_default=False
        )
        self.assertEqual(
            unknown["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "unknown evidence id",
            unknown["hookSpecificOutput"]["permissionDecisionReason"],
        )

        browser_contract = self.contract()
        browser_contract["verification"]["evidence"] = [
            {"id": "E-browser", "kind": "browser", "description": "one session"}
        ]
        browser_contract["verification"]["done_when"] = [
            {"condition": "the page works", "primary_evidence": "E-browser"}
        ]
        sources = CLICK_GATE._fresh_evidence_state(browser_contract)["sources"]
        raw = json.dumps(
            {
                "version": 2,
                "checks": [
                    {
                        "evidence_id": "E-browser",
                        "argv": self.verification_argv(),
                        "class": "targeted",
                    }
                ],
            }
        )
        value, _, error = CLICK_GATE._validate_verification_batch(
            raw, "focused", sources
        )
        self.assertIsNone(value)
        self.assertIn("not `argv`", error)

    def test_verification_batches_may_cover_unresolved_sources_incrementally(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E2", "kind": "argv", "description": "compatibility check"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "compatibility remains", "primary_evidence": "E2"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        first = self.verify_gate([self.verification_argv()])
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        sources = state["evidence_state"]["sources"]
        self.assertEqual(
            sources[CLICK_GATE._evidence_key("E1")]["status"], "passed"
        )
        self.assertEqual(
            sources[CLICK_GATE._evidence_key("E2")]["status"], "ready"
        )
        self.assertEqual(state["verification"]["status"], "ready")
        self.assertFalse(CLICK_GATE._contract_is_completed(state))

        reused = self.verify_gate([self.verification_argv()])
        self.assertEqual(
            reused["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "reused 1 current unchanged-tree",
            reused["hookSpecificOutput"]["updatedInput"]["command"],
        )

        non_adjacent = self.verify_gate(
            [
                self.verification_argv(),
                self.verification_argv(),
                self.verification_argv(),
            ],
            evidence_ids=["E1", "E2", "E1"],
        )
        self.assertEqual(
            non_adjacent["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "must be adjacent",
            non_adjacent["hookSpecificOutput"]["permissionDecisionReason"],
        )

        batch = self.verify_gate([self.verification_argv()], evidence_ids=["E2"])
        self.assertEqual(self.run_rewritten(batch).returncode, 0)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        revision = state["verification"]["mutation_revision"]
        sources = state["evidence_state"]["sources"]
        for evidence_id in ("E1", "E2"):
            source = sources[CLICK_GATE._evidence_key(evidence_id)]
            self.assertEqual(source["status"], "passed")
            self.assertEqual(source["verified_revision"], revision)
        self.assertTrue(CLICK_GATE._contract_is_completed(state))

    def test_partial_argv_batch_records_each_evidence_source(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E2", "kind": "argv", "description": "failing regression"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "regression passes", "primary_evidence": "E2"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        batch = self.verify_gate(
            [self.verification_argv(), self.verification_argv(1)],
            evidence_ids=["E1", "E2"],
        )
        self.assertEqual(self.run_rewritten(batch).returncode, 1)
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        sources = state["evidence_state"]["sources"]
        self.assertEqual(
            sources[CLICK_GATE._evidence_key("E1")]["status"], "passed"
        )
        self.assertEqual(
            sources[CLICK_GATE._evidence_key("E2")]["status"], "failed"
        )
        self.assertFalse(CLICK_GATE._contract_is_completed(state))

        retry = self.verify_gate(
            [self.verification_argv(1)], evidence_ids=["E2"]
        )
        self.assertEqual(self.run_rewritten(retry).returncode, 1)
        blocked = self.verify_gate(
            [self.verification_argv(1)], evidence_ids=["E2"]
        )
        self.assert_verification_advisory(
            blocked, "already failed twice"
        )
        self.assertEqual(self.run_rewritten(blocked).returncode, 1)

    def test_partial_batch_retries_only_unresolved_source_to_completion(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n.transient-marker\n", encoding="utf-8"
        )
        (self.workspace / "transient_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class TransientTest(unittest.TestCase):\n"
            "    def test_passes_on_retry(self):\n"
            "        marker = Path('.transient-marker')\n"
            "        if not marker.exists():\n"
            "            marker.write_text('retry\\n', encoding='utf-8')\n"
            "            self.fail('transient failure')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "transient_test.py")
        transient_argv = [
            sys.executable,
            "-m",
            "unittest",
            "transient_test.TransientTest.test_passes_on_retry",
        ]
        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E2", "kind": "argv", "description": "transient regression"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "transient regression passes", "primary_evidence": "E2"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        first = self.verify_gate(
            [self.verification_argv(), transient_argv],
            evidence_ids=["E1", "E2"],
        )
        self.assertEqual(self.run_rewritten(first).returncode, 1)
        retry = self.verify_gate([transient_argv], evidence_ids=["E2"])
        self.assertEqual(self.run_rewritten(retry).returncode, 0)

        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        revision = state["verification"]["mutation_revision"]
        for evidence_id in ("E1", "E2"):
            source = state["evidence_state"]["sources"][
                CLICK_GATE._evidence_key(evidence_id)
            ]
            self.assertEqual(source["status"], "passed")
            self.assertEqual(source["verified_revision"], revision)
        self.assertTrue(CLICK_GATE._contract_is_completed(state))

    def test_non_argv_evidence_can_complete_without_a_local_batch(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {"id": "E-hosted", "kind": "hosted", "description": "host status"},
            {"id": "E-manual", "kind": "manual", "description": "manual check"},
            {"id": "E-existing", "kind": "existing", "description": "current proof"},
        ]
        contract["verification"]["done_when"] = [
            {"condition": "host is ready", "primary_evidence": "E-hosted"},
            {"condition": "operator checked it", "primary_evidence": "E-manual"},
            {"condition": "current proof remains valid", "primary_evidence": "E-existing"},
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        for evidence_id in ("E-hosted", "E-manual"):
            completed = self.complete_evidence(evidence_id)
            self.assertEqual(
                completed["hookSpecificOutput"]["permissionDecision"], "allow"
            )
            state_path = next(
                (self.plugin_data / "gate-state").glob("session-contract-*.json")
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertFalse(CLICK_GATE._contract_is_completed(state))

        completed = self.complete_evidence("E-existing")
        self.assertEqual(completed["hookSpecificOutput"]["permissionDecision"], "allow")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(CLICK_GATE._contract_is_completed(state))

    def test_argv_evidence_cannot_be_completed_by_attestation(self) -> None:
        self.approve_contract()
        denied = self.complete_evidence("E1")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("click-gate verify", denied["hookSpecificOutput"]["permissionDecisionReason"])

    def test_mixed_evidence_requires_every_source_and_mutation_stales_all(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E-manual", "kind": "manual", "description": "operator check"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "operator view is correct", "primary_evidence": "E-manual"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        verification = self.verify_gate([self.verification_argv()])
        self.assertEqual(self.run_rewritten(verification).returncode, 0)
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(CLICK_GATE._contract_is_completed(state))

        self.complete_evidence("E-manual")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(CLICK_GATE._contract_is_completed(state))

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(CLICK_GATE._contract_is_completed(state))
        for source in state["evidence_state"]["sources"].values():
            self.assertIn(source["status"], {"stale", "ready"})

    def test_contract_allows_only_one_browser_evidence_source(self) -> None:
        contract = self.contract()
        contract["verification"]["evidence"] = [
            {
                "id": "E-browser-1",
                "kind": "browser",
                "description": "first browser session",
            },
            {
                "id": "E-browser-2",
                "kind": "browser",
                "description": "second browser session",
            },
        ]
        contract["verification"]["done_when"] = [
            {"condition": "first view works", "primary_evidence": "E-browser-1"},
            {"condition": "second view works", "primary_evidence": "E-browser-2"},
        ]
        value, error = CLICK_GATE._validate_contract(json.dumps(contract))
        self.assertIsNone(value)
        self.assertIn("at most one Browser evidence source", error)

    def test_optional_build_constraints_are_omitted_or_non_empty(self) -> None:
        compact = self.contract()
        compact["build"] = {"approach": compact["build"]["approach"]}
        self.arm_gate()
        payload = self.stage_gate(compact)
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "allow")

        for field in ("semantics", "order"):
            with self.subTest(field=field):
                invalid = self.contract()
                invalid["build"] = {**invalid["build"], field: []}
                payload = self.pre_tool(
                    "Bash",
                    f"click-gate stage {shlex.quote(json.dumps(invalid))}",
                )
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    field,
                    payload["hookSpecificOutput"]["permissionDecisionReason"],
                )

    def test_plain_language_explanation_is_required(self) -> None:
        contract = self.contract()
        del contract["plain_language"]
        command = f"click-gate stage {shlex.quote(json.dumps(contract))}"
        payload = self.pre_tool("Bash", command)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("plain_language", output["permissionDecisionReason"])

    def test_all_compact_contract_areas_are_required(self) -> None:
        base_contract = self.contract()
        for field in (
            "outcome",
            "boundary",
            "must_hold",
            "build",
            "verification",
            "plain_language",
        ):
            with self.subTest(field=field):
                contract = dict(base_contract)
                del contract[field]
                command = f"click-gate stage {shlex.quote(json.dumps(contract))}"
                payload = self.pre_tool("Bash", command)
                output = payload["hookSpecificOutput"]
                self.assertEqual(output["permissionDecision"], "deny")
                self.assertIn(field, output["permissionDecisionReason"])

    def test_boundary_requires_scope_but_allows_no_explicit_exclusion(self) -> None:
        compact = self.contract()
        compact["boundary"]["out_of_scope"] = []
        self.arm_gate()
        payload = self.stage_gate(compact)
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "allow")

        for field in ("in_scope", "out_of_scope"):
            with self.subTest(field=field):
                invalid = self.contract()
                del invalid["boundary"][field]
                payload = self.pre_tool(
                    "Bash",
                    f"click-gate stage {shlex.quote(json.dumps(invalid))}",
                )
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    field,
                    payload["hookSpecificOutput"]["permissionDecisionReason"],
                )

    def test_verification_is_required_and_bounded(self) -> None:
        missing = self.contract()
        del missing["verification"]
        payload = self.pre_tool(
            "Bash",
            f"click-gate stage {shlex.quote(json.dumps(missing))}",
            "turn-missing",
        )
        self.assertIn(
            "verification", payload["hookSpecificOutput"]["permissionDecisionReason"]
        )

        for index, scale in enumerate(("quick", "focused", "full"), start=1):
            with self.subTest(scale=scale):
                contract = self.contract()
                contract["verification"]["scale"] = scale
                turn_id = f"turn-scale-{index}"
                self.arm_gate(turn_id)
                payload = self.stage_gate(contract, turn_id)
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "allow"
                )

        invalid = self.contract()
        invalid["verification"]["scale"] = "every-step"
        payload = self.pre_tool(
            "Bash",
            f"click-gate stage {shlex.quote(json.dumps(invalid))}",
            "turn-invalid-scale",
        )
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "quick, focused, full",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )

        gated = self.contract()
        gated["verification"]["intermediate_gate"] = (
            "confirm immediately before applying the irreversible migration"
        )
        self.arm_gate("turn-gated")
        payload = self.stage_gate(gated, "turn-gated")
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "allow")

        invalid_gate = self.contract()
        invalid_gate["verification"]["intermediate_gate"] = ""
        payload = self.pre_tool(
            "Bash",
            f"click-gate stage {shlex.quote(json.dumps(invalid_gate))}",
            "turn-invalid-gate",
        )
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "intermediate_gate",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_unknown_contract_field_is_rejected(self) -> None:
        contract = {**self.contract(), "surprise_scope": ["rewrite unrelated API"]}
        command = f"click-gate stage {shlex.quote(json.dumps(contract))}"
        payload = self.pre_tool("Bash", command)
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("surprise_scope", output["permissionDecisionReason"])

    def test_contract_prose_length_does_not_control_staging_authority(self) -> None:
        contract = self.contract()
        contract["outcome"] = "x" * 4_000
        self.arm_gate("turn-large-contract")
        payload = self.stage_gate(contract, "turn-large-contract")
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "allow")
        self.assertNotIn("4,000", output.get("permissionDecisionReason", ""))

    def test_legacy_verbose_contract_fields_are_rejected(self) -> None:
        for field in (
            "invariants",
            "system_semantics",
            "implementation",
            "phases",
            "steps",
            "tasks",
            "plan",
            "execution_order",
            "minimality",
            "proof",
        ):
            with self.subTest(field=field):
                contract = {**self.contract(), field: ["legacy duplicate"]}
                command = f"click-gate stage {shlex.quote(json.dumps(contract))}"
                payload = self.pre_tool("Bash", command)
                output = payload["hookSpecificOutput"]
                self.assertEqual(output["permissionDecision"], "deny")
                self.assertIn(field, output["permissionDecisionReason"])
