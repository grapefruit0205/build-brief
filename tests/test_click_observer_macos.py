from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from hooks import (
    click_dependency_cache,
    click_inspection,
    click_observer_macos,
    click_process,
)


EVIDENCE_KEY = "a" * 64
CHECK_DIGEST = "b" * 64
BACKEND_DIGEST = "c" * 64


class _FakeProcess:
    def __init__(
        self,
        *,
        pid: int,
        returncode: int,
        running: bool = False,
        stdout: bytes = b"",
        stderr: bytes = b"",
        interrupt: bool = False,
    ) -> None:
        self.pid = pid
        self.returncode = None if running else returncode
        self._final_returncode = returncode
        self._running = running
        self._interrupt = interrupt
        self.stdout = BytesIO(stdout)
        self.stderr = BytesIO(stderr)

    def wait(self, timeout: float | None = None) -> int:
        if self._interrupt and timeout is None:
            raise KeyboardInterrupt
        if self._running and timeout is not None:
            raise subprocess.TimeoutExpired("fake", timeout)
        self._running = False
        self.returncode = self._final_returncode
        return self._final_returncode

    def poll(self) -> int | None:
        return None if self._running else self.returncode

    def terminate_for_test(self) -> int:
        self._running = False
        self.returncode = self._final_returncode
        return self._final_returncode


class ClickObserverMacOSTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name).resolve()

    def trace_text(self, *lines: str) -> bytes:
        return ("\n".join(lines) + "\n").encode()

    def fake_fifo_location(self) -> tuple[Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name).resolve()
        return directory, directory / "launch.pipe"

    def test_parser_normalizes_inputs_and_never_retains_external_paths(self) -> None:
        root = self.workspace.as_posix()
        raw = self.trace_text(
            "12:00:00.000001 execve            /usr/bin/python3 0.000010 Python.20",
            f"12:00:00.000002 open F=3 (R_____) {root}/src/input.py "
            "0.000011 Python.20",
            f"12:00:00.000003 stat64 Err#2 {root}/missing.cfg "
            "0.000012 Python.20",
            f"12:00:00.000004 getdirentries64 {root}/pkg "
            "0.000013 Python.20",
            "12:00:00.000005 posix_spawn /usr/bin/git 0.000014 Python.20",
        )

        parsed = click_observer_macos.parse_fs_usage(
            raw, workspace=self.workspace
        )

        self.assertTrue(parsed.root_exec_observed)
        self.assertFalse(parsed.process_tree_complete)
        self.assertEqual(parsed.child_process_count, 1)
        self.assertEqual(parsed.external_input_count, 2)
        self.assertEqual(parsed.unresolved_event_count, 0)
        self.assertEqual(
            parsed.inputs,
            (
                {
                    "path": "missing.cfg",
                    "kind": "missing",
                    "operations": ["metadata"],
                },
                {
                    "path": "pkg/",
                    "kind": "directory",
                    "operations": ["enumerate"],
                },
                {
                    "path": "src/input.py",
                    "kind": "file",
                    "operations": ["read"],
                },
            ),
        )
        rendered = json.dumps(parsed.inputs)
        self.assertNotIn("/usr/bin", rendered)
        self.assertNotIn(root, rendered)

    def test_parser_marks_truncation_and_missing_exec_incomplete(self) -> None:
        parsed = click_observer_macos.parse_fs_usage(
            self.trace_text(
                f"12:00:00.000002 open F=3 (R_____) "
                f"{self.workspace.as_posix()}/input.txt 0.000011 Python.20"
            ),
            workspace=self.workspace,
            truncated=True,
        )
        self.assertFalse(parsed.root_exec_observed)
        self.assertFalse(parsed.process_tree_complete)
        self.assertEqual(parsed.unresolved_event_count, 2)

    def test_parser_handles_errno_write_only_and_pathless_events_safely(self) -> None:
        root = self.workspace.as_posix()
        parsed = click_observer_macos.parse_fs_usage(
            self.trace_text(
                "12:00:00.000001 execve /usr/bin/python3 "
                "0.000010 Python.20",
                f"12:00:00.000002 open [  2] {root}/missing.txt "
                "0.000011 Python.20",
                f"12:00:00.000003 open F=3 (_WCA__) {root}/output.txt "
                "0.000012 Python.20",
                "12:00:00.000004 read F=3 B=0x10 0.000013 Python.20",
            ),
            workspace=self.workspace,
        )

        self.assertEqual(
            parsed.inputs,
            (
                {
                    "path": "missing.txt",
                    "kind": "missing",
                    "operations": ["read"],
                },
            ),
        )
        self.assertEqual(parsed.unresolved_event_count, 1)
        self.assertFalse(parsed.process_tree_complete)

    def test_parser_bounds_aggregate_inputs(self) -> None:
        root = self.workspace.as_posix()
        with mock.patch.object(
            click_dependency_cache, "MAX_SHADOW_OBSERVER_INPUTS", 1
        ):
            parsed = click_observer_macos.parse_fs_usage(
                self.trace_text(
                    "12:00:00.000001 execve /usr/bin/python3 "
                    "0.000010 Python.20",
                    f"12:00:00.000002 open F=3 (R_____) {root}/a.txt "
                    "0.000011 Python.20",
                    f"12:00:00.000003 open F=4 (R_____) {root}/b.txt "
                    "0.000012 Python.20",
                ),
                workspace=self.workspace,
            )

        self.assertEqual(len(parsed.inputs), 1)
        self.assertEqual(parsed.unresolved_event_count, 1)
        self.assertFalse(parsed.process_tree_complete)

    def test_unprivileged_execution_uses_fallback_exactly_once(self) -> None:
        calls: list[int] = []
        result = click_observer_macos.run_command(
            ["check"],
            workspace=self.workspace,
            environment={},
            evidence_key=EVIDENCE_KEY,
            check_digest=CHECK_DIGEST,
            mutation_revision=1,
            execute_unobserved=lambda: calls.append(1) or 7,
            resolve_backend=lambda *_args, **_kwargs: self.fail(
                "an unprivileged run must not resolve fs_usage"
            ),
            privilege_probe=lambda: False,
            collector=lambda *_args, **_kwargs: self.fail(
                "an unprivileged run must not start collection"
            ),
            system_name="Darwin",
        )
        self.assertEqual(result.exit_code, 7)
        self.assertEqual(calls, [1])
        self.assertEqual(result.record["status"], "unavailable")
        self.assertIsNone(result.record["backend"])

    def test_failure_before_target_release_falls_back_once(self) -> None:
        calls: list[int] = []
        result = click_observer_macos.run_command(
            ["check"],
            workspace=self.workspace,
            environment={},
            evidence_key=EVIDENCE_KEY,
            check_digest=CHECK_DIGEST,
            mutation_revision=2,
            execute_unobserved=lambda: calls.append(1) or 9,
            resolve_backend=lambda *_args, **_kwargs: ("/usr/bin/fs_usage", ""),
            digest_file=lambda _path: BACKEND_DIGEST,
            native_backend_probe=lambda _executable: True,
            system_version=lambda: "15.0",
            privilege_probe=lambda: True,
            collector=lambda *_args, **_kwargs: click_observer_macos.CollectedExecution(
                127, b"permission denied", False, True, False, 0, 4
            ),
            system_name="Darwin",
        )
        self.assertEqual(result.exit_code, 9)
        self.assertEqual(calls, [1])
        self.assertEqual(result.record["status"], "failed")
        self.assertEqual(result.record["backend"]["name"], "fs_usage")

    def test_failure_after_target_release_never_reruns_target(self) -> None:
        fallback = mock.Mock(return_value=91)
        result = click_observer_macos.run_command(
            ["check"],
            workspace=self.workspace,
            environment={},
            evidence_key=EVIDENCE_KEY,
            check_digest=CHECK_DIGEST,
            mutation_revision=3,
            execute_unobserved=fallback,
            resolve_backend=lambda *_args, **_kwargs: ("/usr/bin/fs_usage", ""),
            digest_file=lambda _path: BACKEND_DIGEST,
            native_backend_probe=lambda _executable: True,
            system_version=lambda: "15.0",
            privilege_probe=lambda: True,
            collector=lambda *_args, **_kwargs: click_observer_macos.CollectedExecution(
                5, b"malformed trace\n", True, True, True, 12, 3
            ),
            system_name="Darwin",
        )
        self.assertEqual(result.exit_code, 5)
        fallback.assert_not_called()
        self.assertEqual(result.record["status"], "failed")
        self.assertFalse(result.record["process_tree_complete"])

    def test_complete_collection_preserves_exit_and_relative_inputs(self) -> None:
        fallback = mock.Mock(return_value=91)
        root = self.workspace.as_posix()
        raw = self.trace_text(
            "12:00:00.000001 execve /usr/bin/python3 0.000010 Python.20",
            f"12:00:00.000002 open F=3 (R_____) {root}/input.txt "
            "0.000011 Python.20",
        )
        result = click_observer_macos.run_command(
            ["check"],
            workspace=self.workspace,
            environment={},
            evidence_key=EVIDENCE_KEY,
            check_digest=CHECK_DIGEST,
            mutation_revision=4,
            execute_unobserved=fallback,
            resolve_backend=lambda *_args, **_kwargs: ("/usr/bin/fs_usage", ""),
            digest_file=lambda _path: BACKEND_DIGEST,
            native_backend_probe=lambda _executable: True,
            system_version=lambda: "15.0",
            privilege_probe=lambda: True,
            collector=lambda *_args, **_kwargs: click_observer_macos.CollectedExecution(
                6, raw, False, False, True, 15, 2
            ),
            system_name="Darwin",
        )
        self.assertEqual(result.exit_code, 6)
        fallback.assert_not_called()
        self.assertEqual(result.record["status"], "complete")
        self.assertEqual(
            result.record["inputs"],
            [{"path": "input.txt", "kind": "file", "operations": ["read"]}],
        )
        self.assertFalse(result.record["authoritative"])
        self.assertFalse(result.record["reuse_authorized"])

    def test_backend_identity_change_discards_trace_without_rerun(self) -> None:
        fallback = mock.Mock(return_value=91)
        digests = iter((BACKEND_DIGEST, "d" * 64))
        result = click_observer_macos.run_command(
            ["check"],
            workspace=self.workspace,
            environment={},
            evidence_key=EVIDENCE_KEY,
            check_digest=CHECK_DIGEST,
            mutation_revision=5,
            execute_unobserved=fallback,
            resolve_backend=lambda *_args, **_kwargs: ("/usr/bin/fs_usage", ""),
            digest_file=lambda _path: next(digests),
            native_backend_probe=lambda _executable: True,
            system_version=lambda: "15.0",
            privilege_probe=lambda: True,
            collector=lambda *_args, **_kwargs: click_observer_macos.CollectedExecution(
                0, b"", False, False, True, 8, 1
            ),
            system_name="Darwin",
        )
        self.assertEqual(result.exit_code, 0)
        fallback.assert_not_called()
        self.assertEqual(result.record["status"], "unavailable")
        self.assertIsNone(result.record["backend"])

    def test_non_native_fs_usage_path_is_never_executed(self) -> None:
        fallback = mock.Mock(return_value=3)
        collector = mock.Mock()
        result = click_observer_macos.run_command(
            ["check"],
            workspace=self.workspace,
            environment={},
            evidence_key=EVIDENCE_KEY,
            check_digest=CHECK_DIGEST,
            mutation_revision=6,
            execute_unobserved=fallback,
            resolve_backend=lambda *_args, **_kwargs: ("/opt/bin/fs_usage", ""),
            privilege_probe=lambda: True,
            collector=collector,
            system_name="Darwin",
        )
        self.assertEqual(result.exit_code, 3)
        fallback.assert_called_once_with()
        collector.assert_not_called()
        self.assertEqual(result.record["status"], "unavailable")

    def test_collector_uses_pid_filter_and_cleans_external_fifo(self) -> None:
        launches: list[list[str]] = []
        directory, fifo = self.fake_fifo_location()
        launcher = _FakeProcess(pid=4321, returncode=4)
        collector = _FakeProcess(
            pid=4322,
            returncode=0,
            running=True,
            stdout=b"trace-output",
        )

        def spawn(argv: list[str], **_kwargs: object) -> _FakeProcess:
            launches.append(list(argv))
            return launcher if len(launches) == 1 else collector

        terminated: list[int] = []

        def terminate(child: _FakeProcess) -> int:
            terminated.append(child.pid)
            return child.terminate_for_test()

        with (
            mock.patch.object(
                click_observer_macos,
                "_create_launch_fifo",
                return_value=(directory, fifo),
            ),
            mock.patch.object(
                click_observer_macos, "_release_target", return_value=True
            ),
        ):
            result = click_observer_macos.collect_command(
                ["tool", "--flag"],
                workspace=self.workspace,
                environment={"PATH": os.environ.get("PATH", os.defpath)},
                executable="/usr/bin/fs_usage",
                spawn_argv=spawn,
                terminate_group=terminate,
            )

        self.assertTrue(result.target_started)
        self.assertEqual(result.exit_code, 4)
        self.assertEqual(result.raw, b"trace-output")
        self.assertIn("--launch", launches[0])
        self.assertEqual(launches[0][-2:], ["tool", "--flag"])
        self.assertEqual(launches[1][-1], "4321")
        self.assertNotIn("sudo", launches[1])
        fifo = Path(launches[0][launches[0].index("--launch") + 1])
        self.assertFalse(fifo.exists())
        self.assertEqual(terminated, [4322])

    def test_collector_interrupt_stops_both_retained_groups(self) -> None:
        launches: list[list[str]] = []
        directory, fifo = self.fake_fifo_location()
        launcher = _FakeProcess(pid=5321, returncode=0, running=True, interrupt=True)
        collector = _FakeProcess(pid=5322, returncode=0, running=True)

        def spawn(argv: list[str], **_kwargs: object) -> _FakeProcess:
            launches.append(list(argv))
            return launcher if len(launches) == 1 else collector

        terminated: list[int] = []

        def terminate(child: _FakeProcess) -> int:
            terminated.append(child.pid)
            return child.terminate_for_test()

        with (
            mock.patch.object(
                click_observer_macos,
                "_create_launch_fifo",
                return_value=(directory, fifo),
            ),
            mock.patch.object(
                click_observer_macos, "_release_target", return_value=True
            ),
        ):
            result = click_observer_macos.collect_command(
                ["tool"],
                workspace=self.workspace,
                environment={},
                executable="/usr/bin/fs_usage",
                spawn_argv=spawn,
                terminate_group=terminate,
            )
        self.assertTrue(result.target_started)
        self.assertEqual(result.exit_code, 130)
        self.assertTrue(result.failed)
        self.assertEqual(terminated, [5321, 5322])

    def test_collector_early_exit_after_release_marks_trace_failed(self) -> None:
        launches: list[list[str]] = []
        directory, fifo = self.fake_fifo_location()
        collector = _FakeProcess(
            pid=6322,
            returncode=2,
            running=True,
            stdout=b"partial trace",
        )
        launcher = _FakeProcess(pid=6321, returncode=0)
        launcher_wait = launcher.wait

        def stop_collector_then_wait(timeout: float | None = None) -> int:
            if timeout is None:
                collector._running = False
                collector.returncode = 2
            return launcher_wait(timeout)

        launcher.wait = stop_collector_then_wait  # type: ignore[method-assign]

        def spawn(argv: list[str], **_kwargs: object) -> _FakeProcess:
            launches.append(list(argv))
            return launcher if len(launches) == 1 else collector

        with (
            mock.patch.object(
                click_observer_macos,
                "_create_launch_fifo",
                return_value=(directory, fifo),
            ),
            mock.patch.object(
                click_observer_macos, "_release_target", return_value=True
            ),
        ):
            result = click_observer_macos.collect_command(
                ["tool"],
                workspace=self.workspace,
                environment={},
                executable="/usr/bin/fs_usage",
                spawn_argv=spawn,
                terminate_group=lambda child: child.terminate_for_test(),
            )

        self.assertTrue(result.target_started)
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.failed)


@unittest.skipUnless(platform.system() == "Darwin", "native smoke is macOS-only")
class MacOSNativeSmokeTests(unittest.TestCase):
    @unittest.skipUnless(
        click_observer_macos.has_privilege(),
        "native fs_usage smoke requires an explicitly privileged test process",
    )
    def test_native_fs_usage_reads_input_without_workspace_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            input_path = workspace / "input.txt"
            input_path.write_text("observed\n", encoding="utf-8")
            executable, error = click_inspection.resolve_read_only_executable(
                "fs_usage", workspace=workspace
            )
            self.assertFalse(error)
            self.assertIsNotNone(executable)
            fallback_calls: list[int] = []

            def fallback() -> int:
                fallback_calls.append(1)
                return int(
                    click_process.run_argv(
                        [
                            sys.executable,
                            "-I",
                            "-S",
                            "-B",
                            "-c",
                            "from pathlib import Path; import time; "
                            "Path('input.txt').read_bytes(); time.sleep(1)",
                        ],
                        cwd=workspace,
                        env=dict(os.environ),
                    ).returncode
                )

            result = click_observer_macos.run_command(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-B",
                    "-c",
                    "from pathlib import Path; import time; "
                    "Path('input.txt').read_bytes(); time.sleep(1)",
                ],
                workspace=workspace,
                environment=dict(os.environ),
                evidence_key=EVIDENCE_KEY,
                check_digest=CHECK_DIGEST,
                mutation_revision=0,
                execute_unobserved=fallback,
                resolve_backend=click_inspection.resolve_read_only_executable,
                system_name="Darwin",
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(fallback_calls, [])
            self.assertIn(result.record["status"], {"complete", "partial"})
            self.assertTrue(
                any(item["path"] == "input.txt" for item in result.record["inputs"]),
                result.record,
            )
            self.assertTrue(
                click_dependency_cache.shadow_observer_record_is_valid(result.record)
            )
            self.assertEqual(
                sorted(path.name for path in workspace.iterdir()), ["input.txt"]
            )


if __name__ == "__main__":
    unittest.main()
