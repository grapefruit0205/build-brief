from __future__ import annotations

from click_gate_test_support import (
    CLICK_GATE,
    CLICK_MUTATION,
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


class ClickGateExecutionTests(ClickGateTestCase):
    def test_structured_mutation_requires_approval_and_rejects_shell_wrapper(self) -> None:
        self.set_default("guarded")
        denied = self.mutate_gate([sys.executable, "-c", "print('no')"])
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.approve_contract()
        shell = self.mutate_gate(["bash", "-c", "touch hidden.txt"])
        self.assertEqual(shell["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_structured_mutation_rejects_process_control_executable(self) -> None:
        self.approve_contract()
        process_control = self.mutate_gate(["pkill", "-f", "codex"])
        self.assertEqual(
            process_control["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "process-control executable",
            process_control["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_executable_policy_normalizes_windows_aliases(self) -> None:
        cases = {
            "bash.exe": "shell interpreter",
            "SH.EXE.": "shell interpreter",
            "pwsh.exe ": "shell interpreter",
            r"C:\Windows\System32\taskkill.exe.": "process-control executable",
            "pkill.exe": "process-control executable",
        }
        for executable, expected in cases.items():
            with self.subTest(executable=executable):
                argv, error = CLICK_GATE._validate_argv(
                    [executable, "ignored"], "Mutation"
                )
                self.assertIsNone(argv)
                self.assertIn(expected, error)

    @unittest.skipIf(os.name == "nt", "POSIX session IDs are not available on Windows")
    def test_structured_mutation_runs_in_a_new_posix_session(self) -> None:
        self.approve_contract()
        payload = self.mutate_gate(
            [
                sys.executable,
                "-c",
                (
                    "import os; "
                    "print(os.getpid(), os.getsid(0), os.getsid(os.getppid()))"
                ),
            ]
        )
        result = self.run_rewritten(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        child_pid, child_session, parent_session = map(int, result.stdout.split())
        self.assertEqual(child_pid, child_session)
        self.assertNotEqual(child_session, parent_session)

    def test_abandoned_structured_mutation_expires_instead_of_blocking_forever(self) -> None:
        self.approve_contract()
        pending = self.mutate_gate([sys.executable, "-c", "print('first')"])
        self.assertEqual(
            pending["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["mutation"]["started_at"] = 0
        state_path.write_text(json.dumps(state), encoding="utf-8")

        recovered = self.mutate_gate(
            [sys.executable, "-c", "print('second')"], "turn-2"
        )
        self.assertEqual(
            recovered["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        result = self.run_rewritten(recovered)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("second", result.stdout)

    def test_claimed_mutation_never_auto_expires_while_result_is_unknown(self) -> None:
        mutation = {
            "status": "running",
            "runner_claimed_at": 1,
            "started_at": int(time.time()) - 10_000,
        }
        with mock.patch.object(CLICK_GATE.time, "time", return_value=20_000):
            self.assertTrue(CLICK_MUTATION.is_running(mutation))

    def test_mutation_runner_claims_authorization_before_execution(self) -> None:
        self.approve_contract()
        payload = self.mutate_gate([sys.executable, "-c", "print('claimed')"])
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        tokens = split_runner_command(command)
        self.assertEqual(tokens[2], "--state-root")
        self.assertEqual(tokens[4], "run-mutation")
        arguments = tokens[5:]

        tampered = [arguments[0], arguments[1], "wrong-token", arguments[3]]
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ, {"PLUGIN_DATA": str(self.plugin_data)}
            ),
            mock.patch.object(CLICK_GATE, "_execute_argv_commands") as execute,
        ):
            self.assertEqual(CLICK_GATE._run_mutation(tampered), 2)
        execute.assert_not_called()

    def test_mutation_runner_blocks_replay_before_a_second_execution(self) -> None:
        self.approve_contract()
        payload = self.mutate_gate([sys.executable, "-c", "print('once')"])
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        arguments = split_runner_command(command)[5:]

        with (
            mock.patch.dict(
                CLICK_GATE.os.environ, {"PLUGIN_DATA": str(self.plugin_data)}
            ),
            mock.patch.object(
                CLICK_GATE, "_execute_argv_commands", return_value=0
            ) as execute,
        ):
            self.assertEqual(CLICK_GATE._run_mutation(arguments), 0)
            self.assertEqual(CLICK_GATE._run_mutation(arguments), 2)
        self.assertEqual(execute.call_count, 1)

    def test_rewritten_mutation_uses_bound_root_not_ambient_plugin_data(self) -> None:
        self.plugin_data = Path(self.temporary.name) / "plugin%PATH%!CLICK!&data"
        self.approve_contract()
        payload = self.mutate_gate(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; Path('bound-root.txt').write_text('ok')",
            ]
        )
        environment = os.environ.copy()
        environment["PLUGIN_DATA"] = str(Path(self.temporary.name) / "wrong-root")
        environment["CLICK_CONFIG_HOME"] = environment["PLUGIN_DATA"]
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        result = subprocess.run(
            command,
            shell=True,
            cwd=self.workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.workspace / "bound-root.txt").read_text(encoding="utf-8"),
            "ok",
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["mutation"]["status"], "passed")

    def test_mutation_runner_rejects_invalid_state_before_execution(self) -> None:
        self.approve_contract()
        payload = self.mutate_gate([sys.executable, "-c", "print('blocked')"])
        command = payload["hookSpecificOutput"]["updatedInput"]["command"]
        arguments = split_runner_command(command)[5:]
        state_path = Path(arguments[0])
        original = json.loads(state_path.read_text(encoding="utf-8"))

        variants: list[tuple[str, dict]] = []
        staged = json.loads(json.dumps(original))
        staged["status"] = "staged"
        variants.append(("top-level status", staged))
        finished = json.loads(json.dumps(original))
        finished["mutation"]["status"] = "passed"
        variants.append(("mutation status", finished))
        digest = json.loads(json.dumps(original))
        digest["mutation"]["request_digest"] = "0" * 64
        variants.append(("stored digest", digest))
        claimed = json.loads(json.dumps(original))
        claimed["mutation"]["runner_claimed_at"] = 1
        variants.append(("replay claim", claimed))
        malformed = json.loads(json.dumps(original))
        malformed["mutation"]["runner_claimed_at"] = True
        variants.append(("malformed claim", malformed))
        expired = json.loads(json.dumps(original))
        expired["mutation"]["started_at"] = int(time.time()) - 10_000
        variants.append(("expired reservation", expired))
        future = json.loads(json.dumps(original))
        future["mutation"]["started_at"] = int(time.time()) + 60
        variants.append(("future reservation", future))

        with mock.patch.dict(
            CLICK_GATE.os.environ, {"PLUGIN_DATA": str(self.plugin_data)}
        ):
            for label, state in variants:
                with self.subTest(label=label):
                    state_path.write_text(json.dumps(state), encoding="utf-8")
                    with mock.patch.object(
                        CLICK_GATE, "_execute_argv_commands"
                    ) as execute:
                        self.assertEqual(CLICK_GATE._run_mutation(arguments), 2)
                    execute.assert_not_called()

    def test_mutation_runner_rejects_unmanaged_state_before_execution(self) -> None:
        self.approve_contract()
        payload = self.mutate_gate([sys.executable, "-c", "print('blocked')"])
        arguments = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )[5:]
        managed = Path(arguments[0])
        unmanaged = Path(self.temporary.name) / "copied-contract.json"
        unmanaged.write_text(managed.read_text(encoding="utf-8"), encoding="utf-8")
        arguments[0] = str(unmanaged)
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ, {"PLUGIN_DATA": str(self.plugin_data)}
            ),
            mock.patch.object(CLICK_GATE, "_execute_argv_commands") as execute,
        ):
            self.assertEqual(CLICK_GATE._run_mutation(arguments), 2)
        execute.assert_not_called()

    def test_mutation_result_requires_a_claim(self) -> None:
        self.approve_contract()
        payload = self.mutate_gate([sys.executable, "-c", "print('claimless')"])
        arguments = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )[5:]
        with mock.patch.dict(
            CLICK_GATE.os.environ, {"PLUGIN_DATA": str(self.plugin_data)}
        ):
            self.assertFalse(
                CLICK_MUTATION.record_result(
                    Path(arguments[0]), arguments[1], arguments[2], 0
                )
            )

    def test_active_direct_bash_requires_a_structured_capability(self) -> None:
        self.approve_contract()
        denied = self.pre_tool("Bash", "python3 update_schema.py", "turn-2")
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "click-gate mutate",
            denied["hookSpecificOutput"]["permissionDecisionReason"],
        )

    def test_state_lock_retries_windows_permission_contention(self) -> None:
        with mock.patch.dict(
            CLICK_GATE.os.environ,
            {"PLUGIN_DATA": str(self.plugin_data)},
        ):
            lock_root = self.plugin_data / "gate-state"
            lock_root.mkdir(parents=True)
            lock_path = lock_root / ".state.lock"
            lock_path.write_text("competing-process", encoding="utf-8")
            real_open = CLICK_GATE.os.open
            attempts = 0

            def open_with_windows_contention(
                path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                flags: int,
                mode: int = 0o777,
            ) -> int:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise PermissionError(13, "Permission denied", str(path))
                return real_open(path, flags, mode)

            def release_competing_lock(_: float) -> None:
                lock_path.unlink()

            with (
                mock.patch.object(
                    CLICK_GATE.os,
                    "open",
                    side_effect=open_with_windows_contention,
                ),
                mock.patch.object(
                    CLICK_GATE.time,
                    "sleep",
                    side_effect=release_competing_lock,
                ),
            ):
                with CLICK_GATE._state_lock():
                    self.assertTrue(lock_path.exists())

            self.assertEqual(attempts, 2)
            self.assertFalse(lock_path.exists())

    def test_parallel_observation_results_do_not_leave_running_state(self) -> None:
        self.approve_contract()
        for name in ("a.txt", "b.txt"):
            (self.workspace / name).write_text(name, encoding="utf-8")
        payloads = [
            self.pre_tool("Bash", self.read_file_command(name), "turn-2")
            for name in ("a.txt", "b.txt")
        ]
        environment = os.environ.copy()
        environment["PLUGIN_DATA"] = str(self.plugin_data)
        environment["CLICK_CONFIG_HOME"] = str(self.plugin_data)
        invocations = [self.rewritten_invocation(payload) for payload in payloads]
        processes = [
            subprocess.Popen(
                invocation,
                shell=use_shell,
                cwd=self.workspace,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for invocation, use_shell in invocations
        ]
        try:
            for process in processes:
                _, stderr = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, stderr)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        states = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ]
        self.assertEqual(len(states), 1)
        entries = states[0]["observations"]["entries"]
        self.assertEqual(len(entries), 2)
        self.assertEqual({entry["status"] for entry in entries.values()}, {"success"})

    def test_observation_runner_claims_before_read_and_clears_claim(self) -> None:
        self.approve_contract()
        (self.workspace / "claim.txt").write_text("claim", encoding="utf-8")
        payload = self.pre_tool(
            "Bash", self.read_file_command("claim.txt"), "turn-2"
        )
        arguments = self.observation_runner_arguments(payload)
        state_path = Path(arguments[0])

        def execute_after_claim(*_: object, **__: object) -> int:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            entry = next(iter(state["observations"]["entries"].values()))
            self.assertGreater(entry["runner_claimed_at"], 0)
            return 0

        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {
                    "PLUGIN_DATA": str(self.plugin_data),
                    "CLICK_CONFIG_HOME": str(self.plugin_data),
                },
            ),
            mock.patch.object(
                CLICK_GATE,
                "_execute_inspection_commands",
                side_effect=execute_after_claim,
            ),
        ):
            self.assertEqual(CLICK_GATE._run_observation(arguments), 0)

        state = json.loads(state_path.read_text(encoding="utf-8"))
        entry = next(iter(state["observations"]["entries"].values()))
        self.assertEqual(entry["status"], "success")
        self.assertEqual(entry["runner_claimed_at"], 0)
        self.assertEqual(entry["runner_token_digest"], "")

        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {
                    "PLUGIN_DATA": str(self.plugin_data),
                    "CLICK_CONFIG_HOME": str(self.plugin_data),
                },
            ),
            mock.patch.object(CLICK_GATE, "_execute_inspection_commands") as execute,
        ):
            self.assertEqual(CLICK_GATE._run_observation(arguments), 2)
        execute.assert_not_called()

    def test_expired_unclaimed_observation_executes_no_read(self) -> None:
        self.approve_contract()
        (self.workspace / "expired.txt").write_text("expired", encoding="utf-8")
        payload = self.pre_tool(
            "Bash", self.read_file_command("expired.txt"), "turn-2"
        )
        arguments = self.observation_runner_arguments(payload)
        state_path = Path(arguments[0])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        entry = next(iter(state["observations"]["entries"].values()))
        entry["started_at"] = (
            int(time.time())
            - CLICK_GATE.OBSERVATION_RESERVATION_TTL_SECONDS
            - 1
        )
        state_path.write_text(json.dumps(state), encoding="utf-8")

        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {
                    "PLUGIN_DATA": str(self.plugin_data),
                    "CLICK_CONFIG_HOME": str(self.plugin_data),
                },
            ),
            mock.patch.object(CLICK_GATE, "_execute_inspection_commands") as execute,
        ):
            self.assertEqual(CLICK_GATE._run_observation(arguments), 2)
        execute.assert_not_called()

    def test_claimed_observation_does_not_expire_for_interlocks(self) -> None:
        self.approve_contract()
        (self.workspace / "claimed.txt").write_text("claimed", encoding="utf-8")
        payload = self.pre_tool(
            "Bash", self.read_file_command("claimed.txt"), "turn-2"
        )
        arguments = self.observation_runner_arguments(payload)
        state_path = Path(arguments[0])
        request_digest, runner_token, encoded = arguments[1:]
        raw, error = CLICK_GATE._decode_encoded_request(encoded, "observation")
        self.assertEqual(error, "")
        with mock.patch.dict(
            CLICK_GATE.os.environ,
            {
                "PLUGIN_DATA": str(self.plugin_data),
                "CLICK_CONFIG_HOME": str(self.plugin_data),
            },
        ):
            with CLICK_GATE._state_lock():
                request, claim_error = CLICK_GATE._claim_observation_run(
                    state_path, raw, request_digest, runner_token
                )
        self.assertIsNotNone(request)
        self.assertEqual(claim_error, "")

        state = json.loads(state_path.read_text(encoding="utf-8"))
        entry = next(iter(state["observations"]["entries"].values()))
        old_timestamp = (
            int(time.time())
            - CLICK_GATE.OBSERVATION_RESERVATION_TTL_SECONDS
            - 1
        )
        entry["started_at"] = old_timestamp
        entry["runner_claimed_at"] = old_timestamp
        state_path.write_text(json.dumps(state), encoding="utf-8")

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

    def test_expired_unclaimed_observation_releases_mutation_interlock(self) -> None:
        self.approve_contract()
        (self.workspace / "reserved.txt").write_text("reserved", encoding="utf-8")
        payload = self.pre_tool(
            "Bash", self.read_file_command("reserved.txt"), "turn-2"
        )
        arguments = self.observation_runner_arguments(payload)
        state_path = Path(arguments[0])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        entry = next(iter(state["observations"]["entries"].values()))
        entry["started_at"] = (
            int(time.time())
            - CLICK_GATE.OBSERVATION_RESERVATION_TTL_SECONDS
            - 1
        )
        state_path.write_text(json.dumps(state), encoding="utf-8")

        self.assertIsNone(
            self.pre_tool(
                "apply_patch", "*** Begin Patch\n*** End Patch", "turn-2"
            )
        )

    def test_observation_startup_failure_clears_claim_for_retry(self) -> None:
        self.approve_contract()
        (self.workspace / "startup.txt").write_text("startup", encoding="utf-8")
        command = self.read_file_command("startup.txt")
        payload = self.pre_tool("Bash", command, "turn-2")
        arguments = self.observation_runner_arguments(payload)
        state_path = Path(arguments[0])

        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {
                    "PLUGIN_DATA": str(self.plugin_data),
                    "CLICK_CONFIG_HOME": str(self.plugin_data),
                },
            ),
            mock.patch.object(
                CLICK_GATE,
                "_execute_inspection_commands",
                side_effect=OSError("startup failed"),
            ),
        ):
            self.assertEqual(CLICK_GATE._run_observation(arguments), 127)

        state = json.loads(state_path.read_text(encoding="utf-8"))
        entry = next(iter(state["observations"]["entries"].values()))
        self.assertEqual(entry["status"], "failed")
        self.assertEqual(entry["last_exit_code"], 127)
        self.assertEqual(entry["runner_claimed_at"], 0)
        self.assertEqual(entry["runner_token_digest"], "")
        retry = self.pre_tool("Bash", command, "turn-2")
        self.assertEqual(retry["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_observation_runner_rejects_unmanaged_state_before_execution(self) -> None:
        unmanaged = Path(self.temporary.name) / "session-contract-copied.json"
        unmanaged.write_text("{}", encoding="utf-8")
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
                clear=True,
            ),
            mock.patch.object(CLICK_GATE, "_run_inspection_request") as execute,
        ):
            result = CLICK_GATE._run_observation(
                [str(unmanaged), "digest", "token", "encoded"]
            )
        self.assertEqual(result, 2)
        execute.assert_not_called()
