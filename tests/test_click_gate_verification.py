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


class ClickGateVerificationTests(ClickGateTestCase):
    def test_evidence_mode_dynamically_registers_and_exports_host_authority(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        self.prompt_submit("검증 가능한 작은 변경", "turn-1")

        allowed = self.verify_gate(
            [self.verification_argv()],
            turn_id="turn-1",
            evidence_ids=["E_RUNTIME"],
        )
        self.assertEqual(
            allowed["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        completed = self.run_rewritten(allowed)
        self.assertEqual(completed.returncode, 0, completed.stderr)

        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "evidence")
        self.assertEqual(state["evidence_state"]["source_count"], 1)
        source = next(iter(state["evidence_state"]["sources"].values()))
        self.assertEqual(source["status"], "passed")
        self.assertEqual(source["dependency_patterns"], [])

        receipt = self.pre_tool(
            "Bash", "click-gate receipt export", "turn-1", submit_prompt=False
        )
        self.assertIsNotNone(receipt)
        exported = self.run_rewritten(receipt)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        envelope = json.loads(exported.stdout)
        self.assertIsNone(envelope["receipt"]["contract"])
        self.assertEqual(
            envelope["receipt"]["authority"]["execution_authority"], "host"
        )
        self.assertFalse(
            envelope["receipt"]["authority"]["approval_bound"]
        )

    def test_verification_batch_has_no_fixed_check_count_cap(self) -> None:
        checks = [
            {
                "argv": ["git", "diff", "--check"],
                "class": "targeted",
            }
            for _ in range(9)
        ]

        batch, _, error = CLICK_GATE._validate_verification_batch(
            json.dumps({"version": 2, "checks": checks}),
            "focused",
        )

        self.assertEqual(error, "")
        self.assertIsNotNone(batch)
        assert batch is not None
        self.assertEqual(len(batch["checks"]), 9)

    def test_verification_batch_has_no_arbitrary_character_cap(self) -> None:
        raw = json.dumps(
            {
                "version": 2,
                "checks": [
                    {
                        "argv": [
                            "git",
                            "diff",
                            "--check",
                            "--",
                            "x" * 6_500,
                        ],
                        "class": "targeted",
                    }
                ],
            }
        )
        self.assertGreater(len(raw), 6_000)

        batch, _, error = CLICK_GATE._validate_verification_batch(raw, "focused")

        self.assertEqual(error, "")
        self.assertIsNotNone(batch)

    def test_quick_profile_does_not_control_verification_authority(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        command = self.verification_argv()
        allowed = self.verify_gate([command, command])
        self.assertEqual(
            allowed["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertNotIn("additionalContext", allowed["hookSpecificOutput"])
        completed = self.run_rewritten(allowed)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_split_argv_batches_bind_exact_groups_without_a_profile_ceiling(self) -> None:
        (self.workspace / "empty_tests").mkdir()
        (self.workspace / "empty_tests" / "test_pass.py").write_text(
            "import unittest\n\n"
            "class PassingTest(unittest.TestCase):\n"
            "    def test_pass(self):\n"
            "        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E2", "kind": "argv", "description": "second broad check"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "second broad check passes", "primary_evidence": "E2"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        broad_argv = [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "empty_tests",
        ]

        first = self.verify_gate([broad_argv], evidence_ids=["E1"])
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        second = self.verify_gate([broad_argv], evidence_ids=["E2"])
        self.assertEqual(
            second["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertNotIn("additionalContext", second["hookSpecificOutput"])
        self.assertEqual(self.run_rewritten(second).returncode, 0)

        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        sources = state["evidence_state"]["sources"]
        for evidence_id in ("E1", "E2"):
            source = sources[CLICK_GATE._evidence_key(evidence_id)]
            self.assertEqual(source["status"], "passed")
            self.assertRegex(source["reserved_check_digest"], r"^[0-9a-f]{64}$")

    def test_legacy_class_normalization_is_deterministic_but_non_authoritative(self) -> None:
        for command in (
            "pytest tests",
            "python3 -m pytest tests",
            "vitest run",
            "cargo nextest run",
            "cargo test --all",
            "go test ./...",
            "go test ./internal/...",
        ):
            with self.subTest(command=command):
                batch, units, error = CLICK_GATE._validate_verification_batch(
                    json.dumps(
                        {
                            "version": 2,
                            "checks": [
                                {
                                    "argv": shlex.split(command),
                                    "class": "targeted",
                                }
                            ],
                        }
                    ),
                    "quick",
                )
                self.assertEqual(error, "")
                self.assertEqual(units, 3)
                self.assertEqual(batch["checks"][0]["class"], "broad")

        deep_batch, deep_units, error = CLICK_GATE._validate_verification_batch(
            json.dumps(
                {
                    "version": 2,
                    "checks": [
                        {
                            "argv": ["npx", "playwright", "test"],
                            "class": "broad",
                        }
                    ],
                }
            ),
            "quick",
        )
        self.assertEqual(error, "")
        self.assertEqual(deep_units, 5)
        self.assertEqual(deep_batch["checks"][0]["class"], "deep")

    def test_hook_raises_underdeclared_verification_to_its_minimum_class(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        for argv in (
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            ["pytest", "-k", "not definitely_missing", "tests"],
            ["pytest", "tests/test_01.py", "tests/test_02.py"],
            [
                "pytest",
                "tests/integration/test_cancel.py::test_duplicate_cancel",
            ],
        ):
            with self.subTest(argv=argv):
                batch, units, error = CLICK_GATE._validate_verification_batch(
                    json.dumps(
                        {
                            "version": 2,
                            "checks": [{"argv": argv, "class": "targeted"}],
                        }
                    ),
                    "quick",
                )
                self.assertEqual(error, "")
                self.assertEqual(units, 3)
                self.assertEqual(batch["checks"][0]["class"], "broad")

        allowed = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "discover",
                        "-s",
                        "tests",
                    ],
                    "class": "targeted",
                }
            ]
        )
        self.assertEqual(
            allowed["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertNotIn("additionalContext", allowed["hookSpecificOutput"])

    def test_deep_class_normalization_does_not_create_authority(self) -> None:
        self.approve_contract()
        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "coverage",
                        "run",
                        "-m",
                        "unittest",
                        "verification_fixture.VerificationFixture.test_pass",
                    ],
                    "class": "broad",
                }
            ]
        )
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertNotIn("additionalContext", payload["hookSpecificOutput"])

    def test_verification_classifier_uses_scope_before_kind_markers(self) -> None:
        cases = {
            ("pytest", "-k", "not definitely_missing", "tests"): "broad",
            ("pytest", "-m", "not slow", "tests"): "broad",
            ("pytest", "tests/test_01.py", "tests/test_02.py"): "broad",
            (
                "pytest",
                "tests/integration/test_cancel.py::test_duplicate_cancel",
            ): "broad",
            (
                "pytest",
                "tests/test_security_utils.py::test_parse_header",
            ): "broad",
            ("pytest", "tests/integration"): "deep",
            ("go", "test", "./pkg1", "./pkg2"): "broad",
            ("go", "test", "-run", ".*", "./pkg1"): "broad",
            ("ctest", "-R", ".*"): "broad",
            ("pre-commit", "run", "--files", "a.py", "b.py"): "broad",
            ("pre-commit", "run", "--files", "a.py"): "targeted",
        }
        for argv, expected in cases.items():
            with self.subTest(argv=argv):
                self.assertEqual(
                    CLICK_GATE._minimum_verification_class(list(argv)), expected
                )

    def test_verification_classifier_supports_common_build_and_check_forms(self) -> None:
        cases = {
            ("py", "-3", "-m", "unittest", "pkg.Test.test_one"): "targeted",
            ("uv", "run", "pytest", "tests/test_one.py"): "targeted",
            ("npm", "run", "lint"): "broad",
            ("npm", "run", "build"): "broad",
            ("ruff", "check", "."): "broad",
            ("ruff", "check", "src/one.py"): "targeted",
            ("mypy", "src"): "broad",
            ("mypy", "src/one.py"): "targeted",
            ("tsc", "--noEmit"): "broad",
            ("cargo", "check"): "broad",
            ("cargo", "clippy"): "broad",
            ("go", "vet", "./..."): "broad",
            ("node", "--check", "src/one.js"): "targeted",
            ("node", "--test", "tests/one.test.js"): "targeted",
            ("node", "--test"): "broad",
        }
        for argv, expected in cases.items():
            with self.subTest(argv=argv):
                self.assertEqual(
                    CLICK_GATE._minimum_verification_class(list(argv)), expected
                )
        self.assertIsNone(
            CLICK_GATE._minimum_verification_class(
                ["node", "--eval", "process.exit(0)"]
            )
        )

    def test_inline_and_direct_python_programs_are_not_verification(self) -> None:
        self.approve_contract()
        for argv in (
            [sys.executable, "-c", "raise SystemExit(0)"],
            [sys.executable, "verify_project.py"],
        ):
            with self.subTest(argv=argv):
                payload = self.verify_checks(
                    [{"argv": argv, "class": "targeted"}]
                )
                output = payload["hookSpecificOutput"]
                self.assertEqual(output["permissionDecision"], "deny")
                self.assertIn("neither read-only nor a recognized check", output["permissionDecisionReason"])

    def test_unknown_verification_wrapper_is_normalized_but_must_resolve(self) -> None:
        self.approve_contract()
        batch, units, error = CLICK_GATE._validate_verification_batch(
            json.dumps(
                {
                    "version": 2,
                    "checks": [
                        {"argv": ["project-test"], "class": "targeted"}
                    ],
                }
            ),
            "focused",
        )
        self.assertEqual(error, "")
        self.assertEqual(units, 5)
        self.assertEqual(batch["checks"][0]["class"], "deep")

        payload = self.verify_checks(
            [{"argv": ["project-test"], "class": "targeted"}]
        )
        output = payload["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn(
            "could not resolve and fingerprint",
            output["permissionDecisionReason"],
        )

    def test_verification_batch_rejects_legacy_shell_strings(self) -> None:
        self.approve_contract()
        payload = self.legacy_verify_gate(
            ["pytest tests/unit && pytest tests/integration"]
        )
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "legacy shell-string",
            payload["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_successful_final_batch_is_not_repeated_until_code_changes(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        command = self.verification_argv()

        first = self.verify_gate([command])
        completed = self.run_rewritten(first)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        state_text = "\n".join(
            path.read_text()
            for path in (self.plugin_data / "gate-state").glob("*.json")
        )
        self.assertNotIn("raise SystemExit", state_text)
        repeated = self.verify_gate([command])
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "reused 1 current unchanged-tree",
            repeated["hookSpecificOutput"]["updatedInput"]["command"],
        )

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        stale_retry = self.verify_gate([command])
        self.assertEqual(
            stale_retry["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "run-verification",
            split_runner_command(
                stale_retry["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )

    def test_approved_dependency_receipt_reuses_across_an_unrelated_revision(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        (self.workspace / "notes.md").write_text("before\n", encoding="utf-8")
        self.initialize_git(".gitignore", "verification_fixture.py", "notes.md")
        contract = self.contract()
        contract["verification"]["evidence"][0]["dependencies"] = [
            "verification_fixture.py"
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        command = self.verification_argv()

        first = self.verify_gate([command])
        completed = self.run_rewritten(first)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        (self.workspace / "notes.md").write_text("after\n", encoding="utf-8")
        self.tool_hook(
            "post-tool",
            "apply_patch",
            {"patch": "notes"},
            tool_use_id="tool-1",
        )

        reused = self.verify_gate([command])

        self.assertEqual(reused["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertIn(
            "dependency-safe cross-revision",
            reused["hookSpecificOutput"]["updatedInput"]["command"],
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        source = state["evidence_state"]["sources"][CLICK_GATE._evidence_key("E1")]
        self.assertEqual(state["verification"]["mutation_revision"], 1)
        self.assertEqual(source["status"], "passed")
        self.assertEqual(source["verified_revision"], 1)
        self.assertEqual(source["attempts"], 1)
        self.assertEqual(source["dependency_reuse_count"], 1)
        self.assertEqual(source["last_dependency_reused_from_revision"], 0)
        self.assertEqual(
            source["verified_dependency_paths"], ["verification_fixture.py"]
        )

    def _prepare_approved_dependency_receipt(self) -> list[str]:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        (self.workspace / "notes.md").write_text("before\n", encoding="utf-8")
        self.initialize_git(".gitignore", "verification_fixture.py", "notes.md")
        contract = self.contract()
        contract["verification"]["evidence"][0]["dependencies"] = [
            "verification_fixture.py"
        ]
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        command = self.verification_argv()
        first = self.verify_gate([command])
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        return command

    def test_dependency_change_reruns_cross_revision_check(self) -> None:
        command = self._prepare_approved_dependency_receipt()
        with (self.workspace / "verification_fixture.py").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write("\n# dependency changed\n")
        self.tool_hook(
            "post-tool",
            "apply_patch",
            {"patch": "dependency"},
            tool_use_id="tool-1",
        )

        repeated = self.verify_gate([command])

        self.assertIn(
            "run-verification",
            split_runner_command(
                repeated["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )

    def test_environment_change_reruns_cross_revision_check(self) -> None:
        command = self._prepare_approved_dependency_receipt()
        (self.workspace / "notes.md").write_text("after\n", encoding="utf-8")
        self.tool_hook(
            "post-tool",
            "apply_patch",
            {"patch": "notes"},
            tool_use_id="tool-1",
        )

        with mock.patch.dict(
            os.environ, {"CLICK_DEPENDENCY_TEST_ENV": "changed"}
        ):
            repeated = self.verify_gate([command])

        self.assertIn(
            "run-verification",
            split_runner_command(
                repeated["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )

    def test_change_after_approved_mutation_receipt_disables_dependency_reuse(
        self,
    ) -> None:
        command = self._prepare_approved_dependency_receipt()
        (self.workspace / "notes.md").write_text("approved change\n", encoding="utf-8")
        self.tool_hook(
            "post-tool",
            "apply_patch",
            {"patch": "notes"},
            tool_use_id="tool-1",
        )
        (self.workspace / "notes.md").write_text(
            "changed after PostToolUse\n", encoding="utf-8"
        )

        repeated = self.verify_gate([command])

        self.assertIn(
            "run-verification",
            split_runner_command(
                repeated["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )

    def test_unrelated_committed_manifest_entry_does_not_invalidate_receipt(
        self,
    ) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        (self.workspace / "notes.md").write_text("notes\n", encoding="utf-8")
        (self.workspace / "other.md").write_text("other\n", encoding="utf-8")
        manifest_path = self.workspace / ".click" / "evidence-dependencies.json"
        manifest_path.parent.mkdir()
        command = self.verification_argv()

        def write_manifest(unrelated_path: str) -> None:
            manifest_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": [
                            {
                                "checks": [command],
                                "paths": ["verification_fixture.py"],
                            },
                            {
                                "checks": [["python3", "-m", "pytest", "docs"]],
                                "paths": [unrelated_path],
                            },
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        write_manifest("notes.md")
        self.initialize_git(
            ".gitignore",
            "verification_fixture.py",
            "notes.md",
            "other.md",
            ".click/evidence-dependencies.json",
        )
        self.approve_contract()
        first = self.verify_gate([command])
        self.assertEqual(self.run_rewritten(first).returncode, 0)
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        write_manifest("other.md")
        subprocess.run(
            ["git", "add", ".click/evidence-dependencies.json"],
            cwd=self.workspace,
            check=True,
        )
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
                "unrelated dependency mapping",
            ],
            cwd=self.workspace,
            check=True,
        )
        self.tool_hook(
            "post-tool",
            "apply_patch",
            {"patch": "manifest"},
            tool_use_id="tool-1",
        )

        reused = self.verify_gate([command])

        self.assertIn(
            "dependency-safe cross-revision",
            reused["hookSpecificOutput"]["updatedInput"]["command"],
        )

    def test_legacy_class_change_does_not_invalidate_exact_argv_receipt(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        self.approve_contract()
        argv = self.verification_argv()

        first = self.verify_checks([{"argv": argv, "class": "targeted"}])
        completed = self.run_rewritten(first)
        self.assertEqual(completed.returncode, 0, completed.stderr)

        repeated = self.verify_checks([{"argv": argv, "class": "deep"}])
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "reused 1 current unchanged-tree",
            repeated["hookSpecificOutput"]["updatedInput"]["command"],
        )

    def test_runner_only_environment_noise_does_not_invalidate_receipt(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        self.approve_contract()
        command = self.verification_argv()
        first = self.verify_gate([command])
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        prepared = json.loads(state_path.read_text(encoding="utf-8"))
        source_key = CLICK_GATE._evidence_key("E1")
        prepared_digest = prepared["verification"][
            "running_environment_digests"
        ][source_key]

        completed = self.run_rewritten(
            first,
            {"CLICK_RUNNER_ONLY_NOISE": "launcher-added"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        recorded = json.loads(state_path.read_text(encoding="utf-8"))
        source = recorded["evidence_state"]["sources"][source_key]
        self.assertEqual(source["verified_environment_digest"], prepared_digest)

        repeated = self.verify_gate([command])
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "reused 1 current unchanged-tree",
            repeated["hookSpecificOutput"]["updatedInput"]["command"],
        )

    def test_prepared_environment_value_change_is_rebound_before_execution(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        self.approve_contract()
        with mock.patch.dict(
            os.environ, {"CLICK_TEST_ENVIRONMENT": "prepared-value"}
        ):
            first = self.verify_gate([self.verification_argv()])
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        prepared = json.loads(state_path.read_text(encoding="utf-8"))
        source_key = CLICK_GATE._evidence_key("E1")
        prepared_digest = prepared["verification"][
            "running_environment_digests"
        ][source_key]

        rewritten = first["hookSpecificOutput"]["updatedInput"]["command"]
        environment = os.environ.copy()
        environment["PLUGIN_DATA"] = str(self.plugin_data)
        environment["CLICK_CONFIG_HOME"] = str(self.plugin_data)
        environment["CLICK_TEST_ENVIRONMENT"] = "changed-before-runner"
        completed = subprocess.run(
            rewritten,
            shell=True,
            cwd=self.workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(
            "rebound to the current canonical environment", completed.stdout
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        source = state["evidence_state"]["sources"][source_key]
        self.assertEqual(state["verification"]["runner_claimed_at"], 0)
        self.assertEqual(source["status"], "passed")
        self.assertNotEqual(source["verified_environment_digest"], prepared_digest)
        serialized = state_path.read_text(encoding="utf-8")
        self.assertNotIn("CLICK_TEST_ENVIRONMENT", serialized)
        self.assertNotIn("prepared-value", serialized)

    def test_current_receipt_reruns_when_the_git_tree_changes_out_of_band(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        self.approve_contract()
        command = self.verification_argv()
        first = self.verify_gate([command])
        self.assertEqual(self.run_rewritten(first).returncode, 0)

        with (self.workspace / "verification_fixture.py").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write("\n# changed outside the matched mutation tools\n")

        repeated = self.verify_gate([command])
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "run-verification",
            split_runner_command(
                repeated["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["verification"]["mutation_revision"], 1)

    def test_current_receipt_reruns_when_the_execution_environment_changes(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        self.approve_contract()
        command = self.verification_argv()
        first = self.verify_gate([command])
        self.assertEqual(self.run_rewritten(first).returncode, 0)

        with mock.patch.dict(os.environ, {"CLICK_TEST_ENVIRONMENT": "changed"}):
            repeated = self.verify_gate([command])
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "run-verification",
            split_runner_command(
                repeated["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )

    def test_verification_environment_ignores_shell_bookkeeping(self) -> None:
        stable = {
            "PATH": os.environ.get("PATH", os.defpath),
            "CLICK_TEST_ENVIRONMENT": "stable",
        }
        with mock.patch.object(CLICK_GATE.os, "environ", stable):
            expected = CLICK_GATE._verification_environment(cwd=self.workspace)
        noisy = {
            **stable,
            "_": "launcher",
            "__CF_USER_TEXT_ENCODING": "0x1F5:0x0:0x0",
            "CMDCMDLINE": "cmd.exe /c runner",
            "COMMAND_MODE": "unix2003",
            "LC_CTYPE": "UTF-8",
            "PLUGIN_ROOT": "/host/plugin/cache/click",
            "PROMPT": "$P$G",
            "SHLVL": "2",
            "=C:": "C:\\runner",
        }
        with mock.patch.object(CLICK_GATE.os, "environ", noisy):
            actual = CLICK_GATE._verification_environment(cwd=self.workspace)

        self.assertEqual(actual, expected)
        self.assertEqual(actual["CLICK_TEST_ENVIRONMENT"], "stable")

    def test_windows_environment_binding_is_case_insensitive(self) -> None:
        reservation_nonce = "runner-nonce"
        executables = [
            {
                "name": "python.exe",
                "path": "C:\\Python\\python.exe",
                "size": 1,
                "mtime_ns": 1,
                "content_digest": "1" * 64,
            }
        ]
        with mock.patch.object(CLICK_GATE.os, "name", "nt"):
            binding = CLICK_GATE._verification_environment_binding(
                {"Path": "C:\\Python", "Click_Test": "stable"}, reservation_nonce
            )
            projected, drifted, error = (
                CLICK_GATE._verification_environment_from_binding(
                    binding,
                    reservation_nonce,
                    {
                        "PATH": "C:\\Python",
                        "CLICK_TEST": "stable",
                        "RUNNER_ONLY": "ignored",
                    },
                )
            )
            first_digest = CLICK_GATE._verification_environment_digest_from_records(
                executables,
                cwd=self.workspace,
                environment={"Path": "C:\\Python", "Click_Test": "stable"},
            )
            second_digest = CLICK_GATE._verification_environment_digest_from_records(
                executables,
                cwd=self.workspace,
                environment={"PATH": "C:\\Python", "CLICK_TEST": "stable"},
            )

        self.assertEqual(error, "")
        self.assertFalse(drifted)
        self.assertEqual(
            projected, {"PATH": "C:\\Python", "CLICK_TEST": "stable"}
        )
        self.assertEqual(first_digest, second_digest)

    def test_verification_environment_binding_recovers_missing_prepared_key(
        self,
    ) -> None:
        runner_token = "set-at-runtime"
        binding = CLICK_GATE._verification_environment_binding(
            {"PATH": "/usr/bin", "HOOK_ONLY": "prepared"}, runner_token
        )

        projected, drifted, error = (
            CLICK_GATE._verification_environment_from_binding(
                binding,
                runner_token,
                {"PATH": "/usr/bin", "RUNNER_ONLY": "ignored"},
            )
        )

        self.assertEqual(error, "")
        self.assertTrue(drifted)
        self.assertEqual(projected, {"PATH": "/usr/bin"})

    def test_receipt_fingerprint_resolves_relative_path_from_runner_cwd(self) -> None:
        tools = self.workspace / "tools"
        tools.mkdir()
        executable_name = "receipt-check.exe" if os.name == "nt" else "receipt-check"
        executable = tools / executable_name
        executable.write_bytes(b"receipt-check executable\n")
        executable.chmod(0o755)
        environment = os.environ.copy()
        environment["PATH"] = "tools"

        digest = CLICK_GATE._verification_environment_digest(
            [{"argv": [executable_name], "class": "targeted"}],
            cwd=self.workspace,
            environment=environment,
        )

        self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_relative_verifier_selection_uses_explicit_workspace(self) -> None:
        executable = self.workspace / "gradlew"
        executable.write_bytes(b"verification launcher\n")
        executable.chmod(0o755)
        relative = ".\\gradlew" if os.name == "nt" else "./gradlew"
        with mock.patch.object(CLICK_GATE.shutil, "which", return_value=relative):
            records = CLICK_GATE._verification_executable_records(
                [{"argv": [relative], "class": "targeted"}],
                cwd=self.workspace,
                environment={"PATH": os.environ.get("PATH", os.defpath)},
            )

        self.assertIsNotNone(records)
        assert records is not None
        self.assertEqual(records[0]["_execution_path"], str(executable.absolute()))

    @unittest.skipIf(os.name == "nt", "symlink launcher semantics are POSIX-specific")
    def test_verification_pins_selected_symlink_launcher_not_its_target(self) -> None:
        tools = self.workspace / "tools"
        tools.mkdir()
        launcher = tools / "python3"
        launcher.symlink_to(Path(sys.executable).resolve())
        self.approve_contract()
        argv = [
            launcher.name,
            "-m",
            "unittest",
            "verification_fixture.VerificationFixture.test_pass",
        ]
        with mock.patch.dict(os.environ, {"PATH": str(tools)}):
            payload = self.verify_gate([argv])
        tokens = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )
        raw, error = CLICK_GATE._decode_encoded_request(tokens[8], "verification")
        self.assertEqual(error, "")
        environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "CLICK_CONFIG_HOME": str(self.plugin_data),
            "PATH": str(tools),
        }
        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(CLICK_GATE.Path, "cwd", return_value=self.workspace),
        ):
            batch, claim_error = CLICK_GATE._claim_verification_run(
                Path(tokens[5]), raw, tokens[6], tokens[7]
            )
        self.assertEqual(claim_error, "")
        self.assertIsNotNone(batch)
        assert batch is not None
        self.assertTrue(
            os.path.samefile(batch["checks"][0]["argv"][0], launcher)
        )
        self.assertNotEqual(
            batch["checks"][0]["argv"][0], str(Path(sys.executable).resolve())
        )

    def test_rewritten_verification_runner_is_claimed_before_execution(self) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        tokens = split_runner_command(command)
        self.assertEqual(tokens[2], "--state-root")
        self.assertEqual(
            Path(tokens[3]).resolve(),
            (self.plugin_data / "gate-state").resolve(),
        )
        self.assertEqual(tokens[4], "run-verification")

        environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "CLICK_CONFIG_HOME": str(self.plugin_data),
        }
        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(CLICK_GATE.Path, "cwd", return_value=self.workspace),
            mock.patch.object(CLICK_GATE, "_git_workspace_snapshot", return_value=None),
            mock.patch.object(CLICK_GATE, "_git_metadata_present", return_value=False),
            mock.patch.object(
                CLICK_GATE, "_execute_argv_commands", return_value=0
            ) as execute,
        ):
            self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 0)
            self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 2)
        self.assertEqual(execute.call_count, 1)

    def test_verification_runner_rejects_executable_change_before_execution(self) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        tokens = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )
        environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "CLICK_CONFIG_HOME": str(self.plugin_data),
        }
        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(CLICK_GATE.Path, "cwd", return_value=self.workspace),
            mock.patch.object(CLICK_GATE, "_file_content_digest", return_value="0" * 64),
            mock.patch.object(
                CLICK_GATE, "_execute_argv_commands", return_value=0
            ) as execute,
        ):
            self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 2)
        execute.assert_not_called()

        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["verification"]["status"], "ready")
        self.assertEqual(state["verification"]["runner_claimed_at"], 0)
        self.assertEqual(state["verification"]["runner_token_digest"], "")
        source = state["evidence_state"]["sources"][CLICK_GATE._evidence_key("E1")]
        self.assertEqual(source["status"], "ready")

    def test_verification_environment_mismatch_rebinds_before_execution(
        self,
    ) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        tokens = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )
        state_path = Path(tokens[5])
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {
                    "PLUGIN_DATA": str(self.plugin_data),
                    "CLICK_CONFIG_HOME": str(self.plugin_data),
                    "HOME": str(self.workspace / "changed-home"),
                },
            ),
            mock.patch.object(
                CLICK_GATE, "_execute_argv_commands", return_value=0
            ) as execute,
            mock.patch.object(CLICK_GATE.Path, "cwd", return_value=self.workspace),
            mock.patch.object(CLICK_GATE, "_git_workspace_snapshot", return_value=None),
            mock.patch.object(CLICK_GATE, "_git_metadata_present", return_value=False),
        ):
            self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 0)
        execute.assert_called_once()

        state = json.loads(state_path.read_text(encoding="utf-8"))
        verification = state["verification"]
        self.assertEqual(verification["status"], "passed")
        self.assertEqual(verification["runner_token_digest"], "")
        self.assertEqual(verification["runner_claimed_at"], 0)
        self.assertEqual(verification["running_evidence_keys"], [])
        source = state["evidence_state"]["sources"][CLICK_GATE._evidence_key("E1")]
        self.assertEqual(source["status"], "passed")
        self.assertEqual(source["unchanged_failure_retries"], 0)

    def test_verification_runner_rejects_tampered_environment_binding(self) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["verification"]["running_environment_binding"].pop()
        state_path.write_text(json.dumps(state), encoding="utf-8")

        completed = self.run_rewritten(payload)

        self.assertEqual(completed.returncode, 2)
        self.assertIn("environment binding was malformed", completed.stderr)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        verification = state["verification"]
        self.assertEqual(verification["status"], "ready")
        self.assertEqual(verification["runner_claimed_at"], 0)
        self.assertEqual(verification["runner_token_digest"], "")
        source = state["evidence_state"]["sources"][CLICK_GATE._evidence_key("E1")]
        self.assertEqual(source["status"], "ready")

    def test_tampered_verification_token_does_not_release_reservation(self) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        tokens = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )
        state_path = Path(tokens[5])
        tokens[7] = "tampered-runner-token"
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {
                    "PLUGIN_DATA": str(self.plugin_data),
                    "CLICK_CONFIG_HOME": str(self.plugin_data),
                },
            ),
            mock.patch.object(
                CLICK_GATE, "_execute_argv_commands", return_value=0
            ) as execute,
        ):
            self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 2)
        execute.assert_not_called()

        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["verification"]["status"], "running")
        self.assertEqual(state["verification"]["runner_claimed_at"], 0)
        self.assertNotEqual(state["verification"]["runner_token_digest"], "")

    def test_claimed_verification_replay_does_not_release_active_runner(self) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        tokens = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )
        state_path = Path(tokens[5])
        raw, error = CLICK_GATE._decode_encoded_request(tokens[8], "verification")
        self.assertEqual(error, "")
        environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "CLICK_CONFIG_HOME": str(self.plugin_data),
        }
        with (
            mock.patch.dict(CLICK_GATE.os.environ, environment),
            mock.patch.object(CLICK_GATE.Path, "cwd", return_value=self.workspace),
        ):
            with CLICK_GATE._state_lock():
                batch, claim_error = CLICK_GATE._claim_verification_run(
                    state_path, raw, tokens[6], tokens[7]
                )
            self.assertEqual(claim_error, "")
            self.assertIsNotNone(batch)
            self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 2)

        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["verification"]["status"], "running")
        self.assertGreater(state["verification"]["runner_claimed_at"], 0)

    def test_verification_result_rejects_lost_context_bindings(self) -> None:
        for field in (
            "running_environment_digests",
            "running_environment_binding_digest",
            "running_executable_digests",
        ):
            with self.subTest(field=field):
                self.plugin_data = Path(self.temporary.name) / f"plugin-{field}"
                self.submitted_turns.clear()
                self.approve_contract()
                payload = self.verify_gate([self.verification_argv()])
                tokens = split_runner_command(
                    payload["hookSpecificOutput"]["updatedInput"]["command"]
                )
                raw, error = CLICK_GATE._decode_encoded_request(
                    tokens[8], "verification"
                )
                self.assertEqual(error, "")
                environment = {
                    "PLUGIN_DATA": str(self.plugin_data),
                    "CLICK_CONFIG_HOME": str(self.plugin_data),
                }
                with (
                    mock.patch.dict(CLICK_GATE.os.environ, environment),
                    mock.patch.object(
                        CLICK_GATE.Path, "cwd", return_value=self.workspace
                    ),
                ):
                    batch, claim_error = CLICK_GATE._claim_verification_run(
                        Path(tokens[5]), raw, tokens[6], tokens[7]
                    )
                self.assertEqual(claim_error, "")
                self.assertIsNotNone(batch)
                assert batch is not None
                batch.pop("_click_verification_environment")

                state_path = Path(tokens[5])
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state["verification"][field] = {}
                state_path.write_text(json.dumps(state), encoding="utf-8")
                with (
                    mock.patch.dict(CLICK_GATE.os.environ, environment),
                    mock.patch.object(
                        CLICK_GATE.Path, "cwd", return_value=self.workspace
                    ),
                ):
                    recorded = CLICK_GATE._record_verification_result(
                        state_path,
                        batch,
                        tokens[6],
                        tokens[7],
                        0,
                        1,
                        workspace_root=str(self.workspace),
                        workspace_digest="1" * 64,
                    )
                self.assertFalse(recorded)

    def test_verification_runner_rejects_tampered_source_reservation(self) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        tokens = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )
        state_path = Path(tokens[5])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        source = state["evidence_state"]["sources"][CLICK_GATE._evidence_key("E1")]
        source["reserved_check_digest"] = "0" * 64
        state_path.write_text(json.dumps(state), encoding="utf-8")

        environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "CLICK_CONFIG_HOME": str(self.plugin_data),
        }
        with (
            mock.patch.dict(CLICK_GATE.os.environ, environment),
            mock.patch.object(CLICK_GATE.Path, "cwd", return_value=self.workspace),
            mock.patch.object(CLICK_GATE, "_execute_argv_commands") as execute,
        ):
            self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 2)
        execute.assert_not_called()

    def test_source_reservation_survives_mutation_and_prevents_check_swapping(self) -> None:
        self.approve_contract()
        first = self.verify_gate([self.verification_argv(1)])
        self.assertEqual(self.run_rewritten(first).returncode, 1)
        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )

        changed = self.verify_gate([self.verification_argv()])
        self.assertEqual(
            changed["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "reserved to a different exact check set",
            changed["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_rewritten_verification_uses_bound_root_not_ambient_plugin_data(self) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        environment = os.environ.copy()
        environment.pop("PLUGIN_DATA", None)
        environment.pop("CLICK_CONFIG_HOME", None)
        first = subprocess.run(
            command,
            shell=True,
            cwd=self.workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        replay = subprocess.run(
            command,
            shell=True,
            cwd=self.workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(replay.returncode, 2)
        self.assertIn("no longer authorized", replay.stderr)

    def test_verification_runner_rejects_stale_or_future_reservation_before_execution(self) -> None:
        for label, started_at in (
            (
                "expired",
                int(time.time()) - CLICK_GATE.VERIFY_RUNNING_TTL_SECONDS - 1,
            ),
            ("future", int(time.time()) + 60),
        ):
            with self.subTest(label=label):
                self.plugin_data = Path(self.temporary.name) / f"plugin-{label}"
                self.submitted_turns.clear()
                self.approve_contract()
                payload = self.verify_gate([self.verification_argv()])
                tokens = split_runner_command(
                    payload["hookSpecificOutput"]["updatedInput"]["command"]
                )
                state_path = Path(tokens[5])
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state["verification"]["started_at"] = started_at
                state_path.write_text(json.dumps(state), encoding="utf-8")
                with (
                    mock.patch.dict(
                        CLICK_GATE.os.environ,
                        {"PLUGIN_DATA": str(self.plugin_data)},
                    ),
                    mock.patch.object(
                        CLICK_GATE, "_execute_argv_commands"
                    ) as execute,
                ):
                    self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 2)
                execute.assert_not_called()

    def test_verification_fails_closed_when_git_snapshot_cannot_be_established(self) -> None:
        self.approve_contract()
        payload = self.verify_gate([self.verification_argv()])
        tokens = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )
        environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "CLICK_CONFIG_HOME": str(self.plugin_data),
        }
        with (
            mock.patch.dict(CLICK_GATE.os.environ, environment),
            mock.patch.object(CLICK_GATE.Path, "cwd", return_value=self.workspace),
            mock.patch.object(CLICK_GATE, "_git_workspace_snapshot", return_value=None),
            mock.patch.object(CLICK_GATE, "_git_metadata_present", return_value=True),
            mock.patch.object(CLICK_GATE, "_execute_argv_commands") as execute,
        ):
            self.assertEqual(CLICK_GATE._run_verification(tokens[5:]), 2)
        execute.assert_not_called()

    def test_claimed_verification_never_auto_expires_while_result_is_unknown(self) -> None:
        self.approve_contract()
        first = self.verify_gate([self.verification_argv()])
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["verification"]["runner_claimed_at"] = 1
        state["verification"]["started_at"] = 1
        state_path.write_text(json.dumps(state), encoding="utf-8")

        repeated = self.verify_gate([self.verification_argv()])
        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "already running",
            repeated["hookSpecificOutput"]["permissionDecisionReason"],
        )
        current = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(current["verification"]["status"], "running")
        self.assertEqual(current["verification"]["runner_claimed_at"], 1)

    def test_stateful_runner_prefix_rejects_non_gate_state_root(self) -> None:
        self.approve_contract()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        arguments, error = CLICK_GATE._runner_arguments(
            [
                "--state-root",
                str(self.plugin_data.resolve()),
                "run-verification",
                str(state_path),
            ]
        )
        self.assertEqual(arguments, [])
        self.assertIn("invalid", error)

    def test_stateful_runner_requires_one_canonical_bound_state_root(self) -> None:
        self.approve_contract()
        state_root = (self.plugin_data / "gate-state").resolve()
        state_path = next(state_root.glob("session-contract-*.json")).resolve()

        for action in CLICK_GATE.STATEFUL_RUNNER_ACTIONS:
            with self.subTest(action=action):
                with mock.patch.dict(
                    CLICK_GATE.os.environ,
                    {"PLUGIN_DATA": str(Path(self.temporary.name) / "wrong-root")},
                ):
                    arguments, error = CLICK_GATE._runner_arguments(
                        ["--state-root", str(state_root), action, str(state_path)]
                    )
                    self.assertEqual(error, "")
                    self.assertEqual(arguments[:2], [action, str(state_path)])
                    self.assertEqual(
                        CLICK_GATE.os.environ["PLUGIN_DATA"],
                        str(state_root.parent),
                    )

        bare, error = CLICK_GATE._runner_arguments(
            ["run-mutation", str(state_path)]
        )
        self.assertEqual(bare, [])
        self.assertIn("requires", error)

        relative, error = CLICK_GATE._runner_arguments(
            ["--state-root", "gate-state", "run-mutation", str(state_path)]
        )
        self.assertEqual(relative, [])
        self.assertIn("invalid", error)

        missing_root = Path(self.temporary.name) / "missing" / "gate-state"
        missing, error = CLICK_GATE._runner_arguments(
            [
                "--state-root",
                str(missing_root),
                "run-mutation",
                str(state_path),
            ]
        )
        self.assertEqual(missing, [])
        self.assertIn("could not be resolved", error)

        other_root = Path(self.temporary.name) / "other" / "gate-state"
        other_root.mkdir(parents=True)
        mismatched, error = CLICK_GATE._runner_arguments(
            [
                "--state-root",
                str(other_root.resolve()),
                "run-mutation",
                str(state_path),
            ]
        )
        self.assertEqual(mismatched, [])
        self.assertIn("does not match", error)

        alias = Path(self.temporary.name) / "gate-state-alias"
        try:
            alias.symlink_to(state_root, target_is_directory=True)
        except OSError:
            alias = None
        if alias is not None:
            symlinked, error = CLICK_GATE._runner_arguments(
                ["--state-root", str(alias), "run-mutation", str(state_path)]
            )
            self.assertEqual(symlinked, [])
            self.assertIn("invalid", error)

        state_alias = Path(self.temporary.name) / "session-contract-alias.json"
        try:
            state_alias.symlink_to(state_path)
        except OSError:
            state_alias = None
        if state_alias is not None:
            aliased_state, error = CLICK_GATE._runner_arguments(
                [
                    "--state-root",
                    str(state_root),
                    "run-mutation",
                    str(state_alias),
                ]
            )
            self.assertEqual(aliased_state, [])
            self.assertIn("does not match", error)

    def test_verification_that_changes_repository_content_cannot_pass(self) -> None:
        (self.workspace / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.workspace / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.workspace / "mutating_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class MutatingTest(unittest.TestCase):\n"
            "    def test_mutates_source(self):\n"
            "        Path('app.py').write_text('VALUE = 2\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "app.py", "mutating_test.py")

        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "mutating_test.MutatingTest.test_mutates_source",
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("changed protected repository content", result.stderr)

        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        verification = state["verification"]
        self.assertEqual(verification["status"], "failed")
        self.assertTrue(verification["workspace_changed"])
        self.assertEqual(verification["mutation_revision"], 1)
        self.assertNotEqual(
            verification["verified_revision"], verification["mutation_revision"]
        )

        retry = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "mutating_test.MutatingTest.test_mutates_source",
                    ],
                    "class": "targeted",
                }
            ]
        )
        self.assertEqual(retry["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("code mutation", retry["hookSpecificOutput"]["permissionDecisionReason"])

    def test_workspace_changing_failure_does_not_mark_unrun_evidence_executed(self) -> None:
        (self.workspace / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.workspace / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.workspace / "mutating_failure_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class MutatingFailureTest(unittest.TestCase):\n"
            "    def test_mutates_then_fails(self):\n"
            "        Path('app.py').write_text('VALUE = 2\\n', encoding='utf-8')\n"
            "        self.fail('expected failure after mutation')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "app.py", "mutating_failure_test.py")

        contract = self.contract()
        contract["verification"]["evidence"].append(
            {"id": "E2", "kind": "argv", "description": "unrun compatibility check"}
        )
        contract["verification"]["done_when"].append(
            {"condition": "compatibility remains", "primary_evidence": "E2"}
        )
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        payload = self.verify_gate(
            [
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "mutating_failure_test.MutatingFailureTest.test_mutates_then_fails",
                ],
                self.verification_argv(),
            ],
            evidence_ids=["E1", "E2"],
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 1, result.stderr)
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        sources = state["evidence_state"]["sources"]
        executed = sources[CLICK_GATE._evidence_key("E1")]
        unrun = sources[CLICK_GATE._evidence_key("E2")]
        self.assertEqual((executed["status"], executed["attempts"]), ("failed", 1))
        self.assertEqual((unrun["status"], unrun["attempts"]), ("ready", 0))
        self.assertEqual(unrun["unchanged_failure_retries"], 0)

    def test_verification_protects_preexisting_untracked_content(self) -> None:
        (self.workspace / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.workspace / "local-settings.txt").write_text("safe\n", encoding="utf-8")
        (self.workspace / "untracked_mutating_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class UntrackedMutatingTest(unittest.TestCase):\n"
            "    def test_mutates_existing_file(self):\n"
            "        Path('local-settings.txt').write_text('changed\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "untracked_mutating_test.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        (
                            "untracked_mutating_test.UntrackedMutatingTest."
                            "test_mutates_existing_file"
                        ),
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("changed protected repository content", result.stderr)

    def test_verification_detects_content_committed_during_the_batch(self) -> None:
        (self.workspace / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.workspace / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.workspace / "committing_test.py").write_text(
            "import subprocess\n"
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class CommittingTest(unittest.TestCase):\n"
            "    def test_commits_source_change(self):\n"
            "        Path('app.py').write_text('VALUE = 2\\n', encoding='utf-8')\n"
            "        subprocess.run(['git', 'add', 'app.py'], check=True)\n"
            "        subprocess.run([\n"
            "            'git', '-c', 'user.name=Click Tests', '-c',\n"
            "            'user.email=click-tests@example.invalid', 'commit', '--quiet',\n"
            "            '-m', 'verification mutation'\n"
            "        ], check=True)\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "app.py", "committing_test.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "committing_test.CommittingTest.test_commits_source_change",
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("changed protected repository content", result.stderr)
        clean_diff = subprocess.run(
            ["git", "diff", "--quiet"], cwd=self.workspace, check=False
        )
        self.assertEqual(clean_diff.returncode, 0)

    def test_new_untracked_verification_artifact_fails_stale(self) -> None:
        (self.workspace / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.workspace / "artifact_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class ArtifactTest(unittest.TestCase):\n"
            "    def test_writes_disposable_report(self):\n"
            "        Path('new-report.tmp').write_text('result\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "artifact_test.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "artifact_test.ArtifactTest.test_writes_disposable_report",
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("new non-ignored untracked path", result.stderr)
        self.assertTrue((self.workspace / "new-report.tmp").exists())
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["verification"]["status"], "failed")
        self.assertTrue(state["verification"]["workspace_changed"])
        self.assertEqual(state["verification"]["mutation_revision"], 1)

    def test_new_source_path_created_during_verification_fails_stale(self) -> None:
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("src/new_feature.py"))
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("config/policy.json"))
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("migration/001.sql"))
        self.assertTrue(
            CLICK_GATE._new_untracked_is_suspicious("packages/api/lib/new_rule.py")
        )
        self.assertFalse(CLICK_GATE._new_untracked_is_suspicious("new-report.tmp"))
        self.assertFalse(
            CLICK_GATE._new_untracked_is_suspicious("reports/app/output.txt")
        )
        (self.workspace / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.workspace / "source_creating_test.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n\n"
            "class SourceCreatingTest(unittest.TestCase):\n"
            "    def test_creates_source(self):\n"
            "        Path('src').mkdir(exist_ok=True)\n"
            "        Path('src/new_feature.py').write_text('VALUE = 1\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.initialize_git(".gitignore", "source_creating_test.py")
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")

        payload = self.verify_checks(
            [
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "unittest",
                        "source_creating_test.SourceCreatingTest.test_creates_source",
                    ],
                    "class": "targeted",
                }
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("new non-ignored untracked path", result.stderr)
        self.assertIn("classification is informational", result.stderr)

    def test_running_batch_blocks_parallel_mutation_and_verification(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        self.verify_gate([self.verification_argv()])

        for tool_name, command in (
            ("apply_patch", "*** Begin Patch\n*** End Patch"),
            ("Bash", "pytest tests/test_inventory.py"),
        ):
            with self.subTest(tool_name=tool_name):
                payload = self.pre_tool(tool_name, command, "turn-2")
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    "verification batch is running",
                    payload["hookSpecificOutput"]["permissionDecisionReason"],
                )

    def test_unclaimed_expired_verification_does_not_consume_source_attempt(self) -> None:
        self.approve_contract()
        self.verify_gate([self.verification_argv()])
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["verification"]["started_at"] = (
            int(time.time()) - CLICK_GATE.VERIFY_RUNNING_TTL_SECONDS - 1
        )
        self.assertEqual(state["verification"]["runner_claimed_at"], 0)
        original_source = state["evidence_state"]["sources"][
            CLICK_GATE._evidence_key("E1")
        ]
        reserved_digest = original_source["reserved_check_digest"]
        reserved_units = original_source["reserved_units"]
        original_binding = state["verification"]["running_environment_binding"]
        original_token_digest = state["verification"]["runner_token_digest"]
        state_path.write_text(json.dumps(state), encoding="utf-8")

        retry = self.verify_gate([self.verification_argv()])
        self.assertEqual(retry["hookSpecificOutput"]["permissionDecision"], "allow")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        source = state["evidence_state"]["sources"][CLICK_GATE._evidence_key("E1")]
        self.assertEqual(source["status"], "running")
        self.assertEqual(source["attempts"], 0)
        self.assertEqual(source["unchanged_failure_retries"], 0)
        self.assertEqual(source["reserved_check_digest"], reserved_digest)
        self.assertEqual(source["reserved_units"], reserved_units)
        verification = state["verification"]
        source_key = CLICK_GATE._evidence_key("E1")
        for field in (
            "running_environment_digests",
            "running_executable_digests",
        ):
            self.assertEqual(set(verification[field]), {source_key})
            self.assertRegex(verification[field][source_key], r"^[0-9a-f]{64}$")
        self.assertNotEqual(
            verification["running_environment_binding"], original_binding
        )
        self.assertNotEqual(verification["runner_token_digest"], original_token_digest)

    def test_failed_batch_advises_after_unchanged_retry(self) -> None:
        contract = self.contract()
        contract["verification"]["scale"] = "quick"
        self.arm_gate("turn-1")
        self.stage_gate(contract, "turn-1")
        self.arm_gate("turn-2")
        self.pass_gate(turn_id="turn-2")
        command = self.verification_argv(exit_code=1)

        first = self.verify_gate([command])
        self.assertEqual(self.run_rewritten(first).returncode, 1)
        transient_retry = self.verify_gate([command])
        self.assertEqual(self.run_rewritten(transient_retry).returncode, 1)
        blocked = self.verify_gate([command])
        self.assert_verification_advisory(
            blocked, "already failed twice"
        )
        self.assertEqual(self.run_rewritten(blocked).returncode, 1)

        self.assertIsNone(
            self.pre_tool("apply_patch", "*** Begin Patch\n*** End Patch", "turn-2")
        )
        after_fix = self.verify_gate([command])
        self.assertEqual(after_fix["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_broad_checks_must_use_the_receipt_bound_runner_after_approval(self) -> None:
        self.approve_contract()
        for command in (
            "python3 -m unittest discover -s tests",
            "pytest tests",
            "python3 -m pytest tests",
            "vitest run",
            "pytest tests/unit && pytest tests/integration",
            "pytest tests/unit > verification.txt",
            "npm test -- --runInBand",
        ):
            with self.subTest(command=command):
                payload = self.pre_tool("Bash", command, "turn-2")
                self.assertEqual(
                    payload["hookSpecificOutput"]["permissionDecision"], "deny"
                )
                self.assertIn(
                    "click-gate verify",
                    payload["hookSpecificOutput"]["permissionDecisionReason"],
                )
        targeted = self.pre_tool("Bash", "pytest tests/test_inventory.py", "turn-2")
        self.assertEqual(
            targeted["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_uninvoked_verification_remains_fail_open(self) -> None:
        self.set_default("manual")
        self.assertIsNone(
            self.pre_tool("Bash", "python3 -m unittest discover -s tests")
        )

    def test_verification_root_main_py_fails_stale(self) -> None:
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("main.py"))
        self.assert_verification_new_path_behavior("main.py", suspicious=True)

    def test_verification_root_package_json_fails_stale(self) -> None:
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("package.json"))
        self.assert_verification_new_path_behavior("package.json", suspicious=True)

    def test_verification_root_dockerfile_fails_stale(self) -> None:
        self.assertTrue(CLICK_GATE._new_untracked_is_suspicious("Dockerfile"))
        self.assert_verification_new_path_behavior("Dockerfile", suspicious=True)

    def test_verification_generic_report_fails_stale(self) -> None:
        self.assertFalse(CLICK_GATE._new_untracked_is_suspicious("generic-report.txt"))
        self.assert_verification_new_path_behavior("generic-report.txt")

    def test_verification_ignored_artifact_does_not_change_snapshot(self) -> None:
        self.assert_verification_new_path_behavior(
            "ignored-artifact.tmp", ignored=True
        )

    def test_success_receipt_binds_the_current_host_coverage_identity(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        self.approve_contract()

        first = self.verify_gate([self.verification_argv()])
        completed = self.run_rewritten(first)
        self.assertEqual(completed.returncode, 0, completed.stderr)

        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        source = state["evidence_state"]["sources"][
            CLICK_GATE._evidence_key("E1")
        ]
        self.assertEqual(
            source["verified_host_coverage"],
            CLICK_GATE.click_host_coverage.receipt("codex"),
        )
        self.assertEqual(state["verification"]["running_host_coverage"], {})

    def test_current_receipt_is_not_reused_across_host_coverage_identities(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        self.approve_contract()
        command = self.verification_argv()
        first = self.verify_gate([command])
        self.assertEqual(self.run_rewritten(first).returncode, 0)

        self.base_event["platform"] = "antigravity"
        repeated = self.verify_gate([command])

        self.assertEqual(
            repeated["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "run-verification",
            split_runner_command(
                repeated["hookSpecificOutput"]["updatedInput"]["command"]
            ),
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            state["verification"]["running_host_coverage"],
            CLICK_GATE.click_host_coverage.receipt("antigravity"),
        )
        self.assertRegex(
            state["verification"]["running_host_coverage_digest"],
            r"^[0-9a-f]{64}$",
        )

    def test_runner_rejects_tampered_host_coverage_binding_before_execution(self) -> None:
        (self.workspace / ".gitignore").write_text(
            "__pycache__/\n", encoding="utf-8"
        )
        self.initialize_git(".gitignore", "verification_fixture.py")
        self.approve_contract()
        prepared = self.verify_gate([self.verification_argv()])
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["verification"]["running_host_coverage"] = (
            CLICK_GATE.click_host_coverage.receipt("antigravity")
        )
        state_path.write_text(json.dumps(state), encoding="utf-8")

        blocked = self.run_rewritten(prepared)

        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("host coverage binding", blocked.stderr)
        released = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(released["verification"]["status"], "ready")
        self.assertEqual(released["verification"]["running_host_coverage"], {})
        self.assertEqual(
            released["verification"]["running_host_coverage_digest"], ""
        )
