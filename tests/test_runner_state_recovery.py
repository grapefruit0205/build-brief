from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zlib


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "hooks" / "click_gate.py"
STATE_SCRIPT = ROOT / "hooks" / "click_state.py"
STATE_SPEC = importlib.util.spec_from_file_location("click_state_recovery_test", STATE_SCRIPT)
assert STATE_SPEC is not None and STATE_SPEC.loader is not None
CLICK_STATE = importlib.util.module_from_spec(STATE_SPEC)
STATE_SPEC.loader.exec_module(CLICK_STATE)


class RunnerStateRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.plugin_data = Path(self.temporary.name) / "plugin-data"
        self.workspace = Path(self.temporary.name) / "workspace"
        self.workspace.mkdir()
        self.previous_plugin_data = os.environ.get("PLUGIN_DATA")
        self.previous_config_home = os.environ.get("CLICK_CONFIG_HOME")
        os.environ["PLUGIN_DATA"] = str(self.plugin_data)
        os.environ["CLICK_CONFIG_HOME"] = str(self.plugin_data)
        self.addCleanup(self._restore_environment)
        self.event = {
            "session_id": "recovery-session",
            "turn_id": "recovery-turn",
            "cwd": str(self.workspace),
        }

    def _restore_environment(self) -> None:
        if self.previous_plugin_data is None:
            os.environ.pop("PLUGIN_DATA", None)
        else:
            os.environ["PLUGIN_DATA"] = self.previous_plugin_data
        if self.previous_config_home is None:
            os.environ.pop("CLICK_CONFIG_HOME", None)
        else:
            os.environ["CLICK_CONFIG_HOME"] = self.previous_config_home

    def _prepared_mutation(self) -> tuple[Path, Path, dict[str, object], str, str, str]:
        request: dict[str, object] = {
            "version": 1,
            "argv": [sys.executable, "-c", "print('recovered mutation')"],
        }
        canonical = json.dumps(request, sort_keys=True, separators=(",", ":"))
        request_digest = hashlib.sha256(canonical.encode()).hexdigest()
        runner_token = secrets.token_urlsafe(32)
        now = int(time.time())
        state: dict[str, object] = {
            "state_schema_version": 2,
            "status": "approved",
            "contract_digest": hashlib.sha256(b"recovery-contract").hexdigest(),
            "contract_id": "ctr_" + hashlib.md5(b"recovery-contract").hexdigest(),
            "mutation": {
                "status": "running",
                "request_digest": request_digest,
                "runner_token_digest": hashlib.sha256(
                    runner_token.encode()
                ).hexdigest(),
                "runner_claimed_at": 0,
                "started_at": now,
                "last_exit_code": None,
            },
            "updated_at": now,
        }
        state_path = CLICK_STATE.contract_path(self.event)
        CLICK_STATE.write_json(state_path, state)
        bound_root = Path(str(state_path.parent.resolve(strict=True)))
        encoded_request = base64.urlsafe_b64encode(
            json.dumps(request, separators=(",", ":")).encode()
        ).decode()
        self.assertTrue(CLICK_STATE._recovery_snapshot_path(state_path).is_file())
        return (
            state_path,
            bound_root,
            request,
            request_digest,
            runner_token,
            encoded_request,
        )

    def _runner_argv(
        self,
        state_path: Path,
        bound_root: Path,
        request_digest: str,
        runner_token: str,
        encoded_request: str,
    ) -> list[str]:
        return [
            "--state-root",
            str(bound_root),
            "run-mutation",
            str(state_path),
            request_digest,
            runner_token,
            encoded_request,
        ]

    def _run(self, runner_argv: list[str], *, encoded_transport: bool = False) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PLUGIN_DATA"] = str(self.plugin_data)
        environment["CLICK_CONFIG_HOME"] = str(self.plugin_data)
        invocation = [sys.executable, str(SCRIPT), *runner_argv]
        if encoded_transport:
            raw = json.dumps(runner_argv, separators=(",", ":")).encode()
            encoded = base64.urlsafe_b64encode(zlib.compress(raw, level=9)).decode()
            invocation = [sys.executable, str(SCRIPT), "--encoded-runner", encoded]
        return subprocess.run(
            invocation,
            cwd=self.workspace,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_exact_token_recovers_deleted_state_root_before_strict_resolution(self) -> None:
        state_path, bound_root, _, digest, token, encoded_request = self._prepared_mutation()
        bound_state = Path(str(state_path.resolve(strict=True)))
        recovery = CLICK_STATE._recovery_snapshot_path(state_path)
        shutil.rmtree(bound_root)

        result = self._run(
            self._runner_argv(bound_state, bound_root, digest, token, encoded_request)
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("recovered mutation", result.stdout)
        restored = json.loads(bound_state.read_text(encoding="utf-8"))
        self.assertEqual(restored["status"], "approved")
        self.assertEqual(restored["mutation"]["status"], "passed")
        self.assertFalse(recovery.exists())

    def test_encoded_runner_recovers_deleted_state_file(self) -> None:
        state_path, bound_root, _, digest, token, encoded_request = self._prepared_mutation()
        bound_state = Path(str(state_path.resolve(strict=True)))
        Path(str(state_path)).unlink()

        result = self._run(
            self._runner_argv(bound_state, bound_root, digest, token, encoded_request),
            encoded_transport=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        restored = json.loads(bound_state.read_text(encoding="utf-8"))
        self.assertEqual(restored["mutation"]["status"], "passed")

    def test_wrong_token_cannot_restore_missing_state(self) -> None:
        state_path, bound_root, _, digest, _, encoded_request = self._prepared_mutation()
        bound_state = Path(str(state_path.resolve(strict=True)))
        Path(str(state_path)).unlink()

        result = self._run(
            self._runner_argv(
                bound_state,
                bound_root,
                digest,
                secrets.token_urlsafe(32),
                encoded_request,
            )
        )

        self.assertEqual(result.returncode, 2)
        self.assertFalse(bound_state.exists())
        self.assertIn("state path could not be resolved", result.stderr)

    def test_contract_cancel_unlink_revokes_recovery_snapshot(self) -> None:
        state_path, bound_root, _, digest, token, encoded_request = self._prepared_mutation()
        bound_state = Path(str(state_path.resolve(strict=True)))
        recovery = CLICK_STATE._recovery_snapshot_path(state_path)
        state_path.unlink()
        self.assertFalse(recovery.exists())

        result = self._run(
            self._runner_argv(bound_state, bound_root, digest, token, encoded_request)
        )

        self.assertEqual(result.returncode, 2)
        self.assertFalse(bound_state.exists())

    def test_consumed_runner_cannot_recover_after_replay(self) -> None:
        state_path, bound_root, _, digest, token, encoded_request = self._prepared_mutation()
        bound_state = Path(str(state_path.resolve(strict=True)))
        runner = self._runner_argv(bound_state, bound_root, digest, token, encoded_request)

        first = self._run(runner)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertFalse(CLICK_STATE._recovery_snapshot_path(state_path).exists())
        bound_state.unlink()

        replay = self._run(runner)
        self.assertEqual(replay.returncode, 2)
        self.assertFalse(bound_state.exists())


if __name__ == "__main__":
    unittest.main()
