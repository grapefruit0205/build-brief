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


class ClickGateServiceTests(ClickGateTestCase):
    def test_managed_service_start_runner_is_one_use_and_preclaimed(self) -> None:
        self.approve_contract()
        request = {
            "version": 1,
            "action": "start",
            "argv": [sys.executable, "-m", "http.server", "0"],
        }
        runner_token = self.id()
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(
                CLICK_GATE.secrets,
                "token_urlsafe",
                side_effect=["service-id", runner_token],
            ),
        ):
            _, error = CLICK_GATE._prepare_service(
                self.base_event, json.dumps(request)
            )
        self.assertEqual(error, "")
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        normalized, error = CLICK_GATE._validate_service_request(json.dumps(request))
        self.assertEqual(error, "")
        self.assertIsNotNone(normalized)
        assert normalized is not None
        arguments = [
            str(state_path),
            "service-id",
            runner_token,
            str(self.workspace.resolve()),
            CLICK_GATE._encoded_request(normalized),
        ]

        def launch_supervisor(*_args: object, **_kwargs: object) -> mock.Mock:
            with CLICK_GATE._state_lock():
                self.assertTrue(
                    CLICK_GATE._record_service_fields(
                        state_path,
                        "service-id",
                        expected_statuses=("launching",),
                        status="running",
                    )
                )
            return mock.Mock()

        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(
                CLICK_PROCESS,
                "spawn_argv",
                side_effect=launch_supervisor,
            ) as popen,
        ):
            tampered = [*arguments]
            tampered[2] = "wrong-token"
            self.assertEqual(CLICK_GATE._run_service_start(tampered), 2)
            self.assertEqual(CLICK_GATE._run_service_start(arguments), 0)
            self.assertEqual(CLICK_GATE._run_service_start(arguments), 2)
        self.assertEqual(popen.call_count, 1)

    def test_managed_service_rejects_stale_or_future_start_before_launch(self) -> None:
        for label, started_at in (
            (
                "expired",
                int(time.time()) - CLICK_GATE.SERVICE_START_TIMEOUT_SECONDS * 2 - 1,
            ),
            ("future", int(time.time()) + 60),
        ):
            with self.subTest(label=label):
                self.plugin_data = Path(self.temporary.name) / f"service-{label}"
                self.submitted_turns.clear()
                self.approve_contract()
                request = {
                    "version": 1,
                    "action": "start",
                    "argv": [sys.executable, "-m", "http.server", "0"],
                }
                runner_token = f"service-{label}-token"
                with (
                    mock.patch.dict(
                        CLICK_GATE.os.environ,
                        {"PLUGIN_DATA": str(self.plugin_data)},
                    ),
                    mock.patch.object(
                        CLICK_GATE.secrets,
                        "token_urlsafe",
                        side_effect=[f"service-{label}-id", runner_token],
                    ),
                ):
                    CLICK_GATE._prepare_service(self.base_event, json.dumps(request))
                state_path = next(
                    (self.plugin_data / "gate-state").glob("session-contract-*.json")
                ).resolve()
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state["service"]["started_at"] = started_at
                state_path.write_text(json.dumps(state), encoding="utf-8")
                normalized, error = CLICK_GATE._validate_service_request(
                    json.dumps(request)
                )
                self.assertEqual(error, "")
                assert normalized is not None
                arguments = [
                    str(state_path),
                    f"service-{label}-id",
                    runner_token,
                    str(self.workspace.resolve()),
                    CLICK_GATE._encoded_request(normalized),
                ]
                with (
                    mock.patch.dict(
                        CLICK_GATE.os.environ,
                        {"PLUGIN_DATA": str(self.plugin_data)},
                    ),
                    mock.patch.object(CLICK_PROCESS, "spawn_argv") as popen,
                ):
                    self.assertEqual(CLICK_GATE._run_service_start(arguments), 2)
                popen.assert_not_called()

    def test_managed_service_supervisor_launch_is_one_use(self) -> None:
        self.approve_contract()
        request = {
            "version": 1,
            "action": "start",
            "argv": [sys.executable, "-m", "http.server", "0"],
        }
        runner_token = self.id()
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(
                CLICK_GATE.secrets,
                "token_urlsafe",
                side_effect=["service-id", runner_token],
            ),
        ):
            CLICK_GATE._prepare_service(self.base_event, json.dumps(request))
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        normalized, error = CLICK_GATE._validate_service_request(json.dumps(request))
        self.assertEqual(error, "")
        assert normalized is not None
        cwd_raw = str(self.workspace.resolve())
        arguments = [
            str(state_path),
            "service-id",
            runner_token,
            cwd_raw,
            CLICK_GATE._encoded_request(normalized),
        ]
        child = mock.Mock()
        child.pid = 12345
        child.poll.return_value = 0
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            CLICK_GATE._state_lock(),
        ):
            self.assertEqual(
                CLICK_GATE._claim_service_runner(
                    state_path,
                    "service-id",
                    normalized,
                    cwd_raw,
                    runner_token,
                    supervisor=False,
                ),
                "",
            )
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(
                CLICK_PROCESS, "spawn_argv", return_value=child
            ) as popen,
            mock.patch.object(CLICK_GATE.time, "sleep"),
        ):
            self.assertEqual(CLICK_GATE._run_service_supervisor(arguments), 2)
            self.assertEqual(CLICK_GATE._run_service_supervisor(arguments), 2)
        self.assertEqual(popen.call_count, 1)

    def test_managed_service_rejects_stale_supervisor_before_launch(self) -> None:
        self.approve_contract()
        request = {
            "version": 1,
            "action": "start",
            "argv": [sys.executable, "-m", "http.server", "0"],
        }
        runner_token = self.id()
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(
                CLICK_GATE.secrets,
                "token_urlsafe",
                side_effect=["stale-supervisor-id", runner_token],
            ),
        ):
            CLICK_GATE._prepare_service(self.base_event, json.dumps(request))
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        normalized, error = CLICK_GATE._validate_service_request(json.dumps(request))
        self.assertEqual(error, "")
        assert normalized is not None
        cwd_raw = str(self.workspace.resolve())
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            CLICK_GATE._state_lock(),
        ):
            self.assertEqual(
                CLICK_GATE._claim_service_runner(
                    state_path,
                    "stale-supervisor-id",
                    normalized,
                    cwd_raw,
                    runner_token,
                    supervisor=False,
                ),
                "",
            )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["service"]["runner_claimed_at"] = (
            int(time.time()) - CLICK_GATE.SERVICE_START_TIMEOUT_SECONDS * 2 - 1
        )
        state_path.write_text(json.dumps(state), encoding="utf-8")
        arguments = [
            str(state_path),
            "stale-supervisor-id",
            runner_token,
            cwd_raw,
            CLICK_GATE._encoded_request(normalized),
        ]
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(CLICK_PROCESS, "spawn_argv") as popen,
        ):
            self.assertEqual(CLICK_GATE._run_service_supervisor(arguments), 2)
        popen.assert_not_called()

    def test_managed_service_cancellation_before_claim_prevents_launch(self) -> None:
        self.approve_contract()
        request = {
            "version": 1,
            "action": "start",
            "argv": [sys.executable, "-m", "http.server", "0"],
        }
        runner_token = self.id()
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(
                CLICK_GATE.secrets,
                "token_urlsafe",
                side_effect=["service-id", runner_token],
            ),
        ):
            CLICK_GATE._prepare_service(self.base_event, json.dumps(request))
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        normalized, error = CLICK_GATE._validate_service_request(json.dumps(request))
        self.assertEqual(error, "")
        assert normalized is not None
        arguments = [
            str(state_path),
            "service-id",
            runner_token,
            str(self.workspace.resolve()),
            CLICK_GATE._encoded_request(normalized),
        ]
        state_path.unlink()
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(CLICK_PROCESS, "spawn_argv") as popen,
        ):
            self.assertEqual(CLICK_GATE._run_service_start(arguments), 2)
        popen.assert_not_called()

    def test_long_running_local_server_uses_managed_service_lifecycle(self) -> None:
        self.approve_contract()
        argv = [sys.executable, "-m", "http.server", "0", "--bind", "127.0.0.1"]
        mutation = self.mutate_gate(argv)
        self.assertEqual(
            mutation["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn(
            "click-gate service",
            mutation["hookSpecificOutput"]["permissionDecisionReason"],
        )

        start_request = {"version": 1, "action": "start", "argv": argv}
        start = self.pre_tool(
            "Bash",
            f"click-gate service {shlex.quote(json.dumps(start_request))}",
            "turn-2",
        )
        self.assertEqual(start["hookSpecificOutput"]["permissionDecision"], "allow")
        start_result = self.run_rewritten(start)
        self.assertEqual(start_result.returncode, 0, start_result.stderr)

        stop_request = {"version": 1, "action": "stop"}
        stop = self.pre_tool(
            "Bash",
            f"click-gate service {shlex.quote(json.dumps(stop_request))}",
            "turn-2",
        )
        self.assertEqual(stop["hookSpecificOutput"]["permissionDecision"], "allow")
        stop_result = self.run_rewritten(stop)
        self.assertEqual(stop_result.returncode, 0, stop_result.stderr)
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["service"]["status"], "stopped")

        restart = self.pre_tool(
            "Bash",
            f"click-gate service {shlex.quote(json.dumps(start_request))}",
            "turn-2",
        )
        restart_result = self.run_rewritten(restart)
        self.assertEqual(restart_result.returncode, 0, restart_result.stderr)
        end_event = {
            **self.base_event,
            "hook_event_name": "SessionEnd",
        }
        end_result, end_payload = self.run_hook("session-end", end_event)
        self.assertEqual(end_result.returncode, 0, end_result.stderr)
        self.assertIsNone(end_payload)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state["service"]["status"] == "stopped":
                break
            time.sleep(0.05)
        self.assertEqual(state["service"]["status"], "stopped")

    def test_service_snapshot_retries_windows_sharing_collision(self) -> None:
        self.approve_contract()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["service"] = {
            **CLICK_GATE._fresh_service_state(),
            "status": "stopped",
            "service_id": "service-1",
        }
        state_path.write_text(json.dumps(state), encoding="utf-8")
        original_read_text = Path.read_text

        def transient_read(path: Path, *args: object, **kwargs: object) -> str:
            if path == state_path and transient_read.attempts == 0:
                transient_read.attempts += 1
                raise PermissionError("sharing violation")
            return original_read_text(path, *args, **kwargs)

        transient_read.attempts = 0
        with (
            mock.patch.dict(
                CLICK_GATE.os.environ,
                {"PLUGIN_DATA": str(self.plugin_data)},
            ),
            mock.patch.object(Path, "read_text", transient_read),
        ):
            snapshot = CLICK_GATE._service_snapshot(state_path, "service-1")
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot["status"], "stopped")

    def test_service_stop_does_not_treat_unreadable_state_as_stopped(self) -> None:
        with (
            mock.patch.object(
                CLICK_GATE,
                "_service_snapshot",
                side_effect=[None, {"status": "stopped"}],
            ) as snapshot,
            mock.patch.object(CLICK_GATE.time, "sleep"),
        ):
            result = CLICK_GATE._run_service_stop(
                [str(self.plugin_data / "state.json"), "service-1"]
            )
        self.assertEqual(result, 0)
        self.assertEqual(snapshot.call_count, 2)
