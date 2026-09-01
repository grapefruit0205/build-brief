from __future__ import annotations

import ast
import io
import os
from pathlib import Path
import signal
import subprocess
import unittest
from unittest import mock

from hooks import click_gate, click_process


class ClickProcessTests(unittest.TestCase):
    def test_process_module_does_not_depend_on_gate_state_or_evidence(self) -> None:
        source = Path(click_process.__file__).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported.add(module)
                imported.update(
                    f"{module}.{alias.name}".strip(".") for alias in node.names
                )

        for forbidden in ("click_gate", "click_state", "evidence"):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(
                    any(forbidden in name.split(".") for name in imported),
                    imported,
                )

    def test_gate_does_not_reexport_process_primitives(self) -> None:
        for name in (
            "_copy_limited_output",
            "_isolated_subprocess_kwargs",
            "_terminate_managed_child",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(click_gate, name))

    def test_isolation_kwargs_are_platform_specific(self) -> None:
        with mock.patch.object(click_process.os, "name", "posix"):
            self.assertEqual(
                click_process.isolated_subprocess_kwargs(),
                {"start_new_session": True},
            )
        with (
            mock.patch.object(click_process.os, "name", "nt"),
            mock.patch.object(
                click_process.subprocess,
                "CREATE_NEW_PROCESS_GROUP",
                512,
                create=True,
            ),
        ):
            self.assertEqual(
                click_process.isolated_subprocess_kwargs(),
                {"creationflags": 512},
            )

    def test_run_argv_is_shell_free_and_uses_an_isolated_group(self) -> None:
        completed = mock.Mock(spec=subprocess.CompletedProcess)
        with (
            mock.patch.object(
                click_process,
                "isolated_subprocess_kwargs",
                return_value={"start_new_session": True},
            ),
            mock.patch.object(
                click_process.subprocess,
                "run",
                return_value=completed,
            ) as run,
        ):
            result = click_process.run_argv(
                ("tool", "--flag"),
                cwd=Path("workspace"),
                env={"SAFE": "1"},
                stdout=subprocess.PIPE,
            )

        self.assertIs(result, completed)
        run.assert_called_once_with(
            ["tool", "--flag"],
            cwd=Path("workspace"),
            env={"SAFE": "1"},
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=None,
            check=False,
            shell=False,
            start_new_session=True,
        )

    def test_spawn_argv_is_shell_free_and_uses_an_isolated_group(self) -> None:
        child = mock.Mock(spec=subprocess.Popen)
        with (
            mock.patch.object(
                click_process,
                "isolated_subprocess_kwargs",
                return_value={"creationflags": 512},
            ),
            mock.patch.object(
                click_process.subprocess,
                "Popen",
                return_value=child,
            ) as popen,
        ):
            result = click_process.spawn_argv(
                ("service", "start"),
                cwd="workspace",
                stderr=subprocess.DEVNULL,
                close_fds=False,
            )

        self.assertIs(result, child)
        popen.assert_called_once_with(
            ["service", "start"],
            cwd="workspace",
            env=None,
            stdin=None,
            stdout=None,
            stderr=subprocess.DEVNULL,
            close_fds=False,
            shell=False,
            creationflags=512,
        )

    @unittest.skipIf(os.name == "nt", "POSIX process groups are unavailable")
    def test_terminate_process_group_uses_posix_group_signals(self) -> None:
        child = mock.Mock()
        child.pid = 4242
        child.poll.return_value = None
        child.wait.return_value = 0
        with (
            mock.patch.object(click_process.os, "name", "posix"),
            mock.patch.object(click_process.os, "killpg", create=True) as killpg,
        ):
            result = click_process.terminate_process_group(
                child, grace_seconds=0.25
            )

        self.assertEqual(result, 0)
        killpg.assert_called_once_with(4242, signal.SIGTERM)
        child.wait.assert_called_once_with(timeout=0.25)

    @unittest.skipIf(os.name == "nt", "POSIX process groups are unavailable")
    def test_terminate_process_group_escalates_after_timeout(self) -> None:
        child = mock.Mock()
        child.pid = 4242
        child.poll.return_value = None
        child.wait.side_effect = [
            subprocess.TimeoutExpired("service", 0.25),
            -9,
        ]
        with (
            mock.patch.object(click_process.os, "name", "posix"),
            mock.patch.object(click_process.os, "killpg", create=True) as killpg,
        ):
            result = click_process.terminate_process_group(
                child, grace_seconds=0.25
            )

        self.assertEqual(result, -9)
        self.assertEqual(
            killpg.call_args_list,
            [
                mock.call(4242, signal.SIGTERM),
                mock.call(4242, signal.SIGKILL),
            ],
        )
        self.assertEqual(
            child.wait.call_args_list,
            [mock.call(timeout=0.25), mock.call(timeout=0.25)],
        )

    def test_terminate_process_group_uses_windows_control_break(self) -> None:
        child = mock.Mock()
        child.poll.return_value = None
        child.wait.return_value = 0
        with (
            mock.patch.object(click_process.os, "name", "nt"),
            mock.patch.object(
                click_process.signal,
                "CTRL_BREAK_EVENT",
                21,
                create=True,
            ),
        ):
            result = click_process.terminate_process_group(child)

        self.assertEqual(result, 0)
        child.send_signal.assert_called_once_with(21)
        child.terminate.assert_not_called()
        child.kill.assert_not_called()

    def test_windows_termination_falls_back_when_control_break_is_missing(self) -> None:
        child = mock.Mock()
        child.poll.return_value = None
        child.wait.return_value = 0
        with (
            mock.patch.object(click_process.os, "name", "nt"),
            mock.patch.object(
                click_process.signal,
                "CTRL_BREAK_EVENT",
                None,
                create=True,
            ),
        ):
            result = click_process.terminate_process_group(child)

        self.assertEqual(result, 0)
        child.send_signal.assert_not_called()
        child.terminate.assert_called_once_with()
        child.kill.assert_not_called()

    def test_windows_termination_escalates_to_kill_after_timeout(self) -> None:
        child = mock.Mock()
        child.poll.return_value = None
        child.wait.side_effect = [
            subprocess.TimeoutExpired("service", 0.25),
            1,
        ]
        with (
            mock.patch.object(click_process.os, "name", "nt"),
            mock.patch.object(
                click_process.signal,
                "CTRL_BREAK_EVENT",
                21,
                create=True,
            ),
        ):
            result = click_process.terminate_process_group(
                child, grace_seconds=0.25
            )

        self.assertEqual(result, 1)
        child.send_signal.assert_called_once_with(21)
        child.kill.assert_called_once_with()
        self.assertEqual(
            child.wait.call_args_list,
            [mock.call(timeout=0.25), mock.call(timeout=0.25)],
        )

    def test_copy_limited_output_stops_at_the_exact_byte_cap(self) -> None:
        source = io.BytesIO(b"0123456789")
        target = io.BytesIO()

        copied = click_process.copy_limited_output(
            source, target, 6, chunk_size=4
        )

        self.assertEqual(copied, 6)
        self.assertEqual(target.getvalue(), b"012345")
        self.assertEqual(source.read(), b"6789")


if __name__ == "__main__":
    unittest.main()
