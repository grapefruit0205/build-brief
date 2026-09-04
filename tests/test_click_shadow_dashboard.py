from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request

from click_gate_test_support import (
    CLICK_GATE,
    CLICK_LIFECYCLE,
    CLICK_SHADOW_DASHBOARD,
    CLICK_STATE,
    ClickGateTestCase,
    mock,
    os,
    split_runner_command,
    unittest,
)


class ClickShadowDashboardTests(ClickGateTestCase):
    def test_control_parser_accepts_only_explicit_dashboard_actions(self) -> None:
        for action in ("start", "stop", "status"):
            self.assertEqual(
                CLICK_LIFECYCLE.control_request(f"click-gate dashboard {action}"),
                ("dashboard", action, ""),
            )
        parsed = CLICK_LIFECYCLE.control_request("click-gate dashboard erase")
        self.assertEqual(parsed[0], "")
        self.assertIn("dashboard start|stop|status", parsed[2])

    def test_prepare_start_persists_only_token_digests(self) -> None:
        self.approve_contract()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        before = json.loads(state_path.read_text(encoding="utf-8"))
        payload = self.pre_tool(
            "Bash", "click-gate dashboard start", "turn-2", submit_prompt=False
        )
        self.assertIsNotNone(payload)
        assert payload is not None
        tokens = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )
        action_index = tokens.index("run-dashboard-start")
        instance_id, runner_token, access_token = tokens[action_index + 2 :]
        self.assertEqual(Path(tokens[action_index + 1]), state_path)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        dashboard = state[CLICK_SHADOW_DASHBOARD.DASHBOARD_FIELD]

        self.assertEqual(dashboard["instance_id"], instance_id)
        self.assertEqual(
            dashboard["runner_token_digest"],
            hashlib.sha256(runner_token.encode()).hexdigest(),
        )
        self.assertEqual(
            dashboard["access_token_digest"],
            hashlib.sha256(access_token.encode()).hexdigest(),
        )
        encoded = state_path.read_text(encoding="utf-8")
        self.assertNotIn(runner_token, encoded)
        self.assertNotIn(access_token, encoded)
        self.assertEqual(
            state["verification"]["mutation_revision"],
            before["verification"]["mutation_revision"],
        )
        self.assertEqual(state["evidence_state"], before["evidence_state"])

    def test_session_end_requests_dashboard_cleanup_without_changing_evidence(self) -> None:
        self.approve_contract()
        self.pre_tool(
            "Bash", "click-gate dashboard start", "turn-2", submit_prompt=False
        )
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        before = json.loads(state_path.read_text(encoding="utf-8"))
        event = {
            **self.base_event,
            "turn_id": "turn-2",
            "hook_event_name": "SessionEnd",
        }

        result, _ = self.run_hook("session-end", event)

        self.assertEqual(result.returncode, 0, result.stderr)
        after = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(after["shadow_dashboard"]["status"], "stopping")
        self.assertTrue(after["shadow_dashboard"]["stop_requested"])
        self.assertEqual(
            after["verification"]["mutation_revision"],
            before["verification"]["mutation_revision"],
        )
        self.assertEqual(after["evidence_state"], before["evidence_state"])

    def test_start_runner_is_one_use_and_reports_fragment_token(self) -> None:
        self.approve_contract()
        payload = self.pre_tool(
            "Bash", "click-gate dashboard start", "turn-2", submit_prompt=False
        )
        assert payload is not None
        tokens = split_runner_command(
            payload["hookSpecificOutput"]["updatedInput"]["command"]
        )
        action_index = tokens.index("run-dashboard-start")
        arguments = tokens[action_index + 1 :]
        state_path = Path(arguments[0])
        instance_id = arguments[1]

        def mark_running(*_args: object, **_kwargs: object) -> mock.Mock:
            with CLICK_STATE.state_lock():
                self.assertTrue(
                    CLICK_SHADOW_DASHBOARD._write_dashboard_fields(
                        state_path,
                        instance_id,
                        status="running",
                        port=43219,
                        pid=123,
                    )
                )
            return mock.Mock()

        with (
            mock.patch.dict(
                os.environ,
                {
                    "PLUGIN_DATA": str(self.plugin_data),
                    "CLICK_CONFIG_HOME": str(self.plugin_data),
                },
            ),
            mock.patch.object(
                CLICK_SHADOW_DASHBOARD.click_process,
                "spawn_argv",
                side_effect=mark_running,
            ),
            mock.patch.object(CLICK_SHADOW_DASHBOARD.sys, "stdout") as stdout,
        ):
            self.assertEqual(
                CLICK_SHADOW_DASHBOARD.run_start(
                    arguments,
                    runner_script=CLICK_GATE.Path(CLICK_GATE.__file__).resolve(),
                    spawn=CLICK_SHADOW_DASHBOARD.click_process.spawn_argv,
                ),
                0,
            )
            self.assertEqual(
                CLICK_SHADOW_DASHBOARD.run_start(
                    arguments,
                    runner_script=CLICK_GATE.Path(CLICK_GATE.__file__).resolve(),
                    spawn=CLICK_SHADOW_DASHBOARD.click_process.spawn_argv,
                ),
                2,
            )
        rendered = "".join(call.args[0] for call in stdout.write.call_args_list)
        self.assertIn("http://127.0.0.1:43219/#token=", rendered)

    def test_server_is_loopback_read_only_authenticated_and_content_free(self) -> None:
        self.approve_contract()
        state_path = next(
            (self.plugin_data / "gate-state").glob("session-contract-*.json")
        ).resolve()
        instance_id = "dashboard-instance-12345"
        access_token = hashlib.sha256(instance_id.encode()).hexdigest()
        with CLICK_STATE.state_lock():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state[CLICK_SHADOW_DASHBOARD.DASHBOARD_FIELD] = {
                "version": 1,
                "status": "starting",
                "instance_id": instance_id,
                "runner_token_digest": "",
                "runner_claimed_at": 1,
                "access_token_digest": hashlib.sha256(
                    access_token.encode()
                ).hexdigest(),
                "port": 0,
                "pid": 0,
                "started_at": int(time.time()),
                "stop_requested": False,
                "last_error": "",
            }
            CLICK_STATE.write_json(state_path, state)

        results: list[int] = []
        environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "CLICK_CONFIG_HOME": str(self.plugin_data),
        }

        def serve() -> None:
            with mock.patch.dict(os.environ, environment):
                results.append(
                    CLICK_SHADOW_DASHBOARD.run_server(
                        [str(state_path), instance_id, access_token]
                    )
                )

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        port = 0
        for _ in range(500):
            with CLICK_STATE.state_lock():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                dashboard = state[CLICK_SHADOW_DASHBOARD.DASHBOARD_FIELD]
            if dashboard["status"] == "running":
                port = int(dashboard["port"])
                break
            time.sleep(0.02)
        self.assertGreater(port, 0)
        base = f"http://127.0.0.1:{port}"

        with urllib.request.urlopen(base + "/", timeout=2) as response:
            html = response.read().decode()
            self.assertEqual(response.status, 200)
            self.assertIn("Evidence you can see", html)
            self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

        with self.assertRaises(urllib.error.HTTPError) as unauthorized:
            urllib.request.urlopen(base + "/api/v1/snapshot", timeout=2)
        self.assertEqual(unauthorized.exception.code, 401)

        request = urllib.request.Request(
            base + "/api/v1/snapshot",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            body = response.read().decode()
            payload = json.loads(body)
            self.assertEqual(response.status, 200)
            self.assertEqual(payload["summary"]["actual_saved_ms"], 0)
            self.assertNotIn(str(self.workspace), body)
            self.assertNotIn("contract_id", body)

        wrong_host = urllib.request.Request(
            base + "/", headers={"Host": "attacker.invalid"}
        )
        with self.assertRaises(urllib.error.HTTPError) as misdirected:
            urllib.request.urlopen(wrong_host, timeout=2)
        self.assertEqual(misdirected.exception.code, 421)

        post = urllib.request.Request(base + "/api/v1/snapshot", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as method:
            urllib.request.urlopen(post, timeout=2)
        self.assertEqual(method.exception.code, 405)

        with CLICK_STATE.state_lock():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state[CLICK_SHADOW_DASHBOARD.DASHBOARD_FIELD]["status"] = "stopping"
            state[CLICK_SHADOW_DASHBOARD.DASHBOARD_FIELD]["stop_requested"] = True
            CLICK_STATE.write_json(state_path, state)
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results, [0])


if __name__ == "__main__":
    unittest.main()
