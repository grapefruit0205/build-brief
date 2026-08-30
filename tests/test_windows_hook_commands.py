from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
HOOK_CONFIG = ROOT / "hooks" / "hooks.json"
WINDOWS_MODES = {
    "UserPromptSubmit": "prompt-submit",
    "PreToolUse": "pre-tool",
    "PostToolUse": "post-tool",
    "SessionEnd": "session-end",
}


def windows_commands() -> dict[str, str]:
    config = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
    return {
        event_name: config["hooks"][event_name][0]["hooks"][0][
            "commandWindows"
        ]
        for event_name in WINDOWS_MODES
    }


def synthetic_event(event_name: str, workspace: Path, suffix: str) -> dict[str, object]:
    event: dict[str, object] = {
        "session_id": f"windows-hook-{suffix}",
        "turn_id": f"windows-turn-{suffix}",
        "cwd": str(workspace),
        "model": "test-model",
        "permission_mode": "default",
        "hook_event_name": event_name,
    }
    if event_name == "UserPromptSubmit":
        event["prompt"] = "Explain the current Click mode."
    elif event_name == "PreToolUse":
        event.update(
            {
                "tool_name": "Bash",
                "tool_use_id": f"windows-tool-{suffix}",
                "tool_input": {"command": "click-gate default status"},
            }
        )
    elif event_name == "PostToolUse":
        event.update(
            {
                "tool_name": "mcp__node_repl__js",
                "tool_use_id": f"windows-tool-{suffix}",
                "tool_input": {"code": "return true;"},
                "tool_response": {"content": []},
            }
        )
    return event


class WindowsHookCommandTests(unittest.TestCase):
    def test_commands_use_codex_plugin_root_template(self) -> None:
        commands = windows_commands()
        self.assertEqual(set(commands), set(WINDOWS_MODES))
        for event_name, mode in WINDOWS_MODES.items():
            with self.subTest(event=event_name):
                self.assertEqual(
                    commands[event_name],
                    f'py -3 "${{PLUGIN_ROOT}}\\hooks\\click_gate.py" {mode}',
                )
                self.assertNotIn("%PLUGIN_ROOT%", commands[event_name])

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell integration test")
    def test_commands_execute_in_powershell_from_normal_and_spaced_roots(self) -> None:
        powershell = shutil.which("pwsh")
        self.assertIsNotNone(powershell, "pwsh is required on the Windows CI runner")
        command_prompt = shutil.which("cmd.exe")
        self.assertIsNotNone(command_prompt, "cmd.exe is required on Windows")
        commands = windows_commands()

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for root_name in ("click-normal", "Click Plugin Root With Spaces"):
                with self.subTest(plugin_root=root_name):
                    plugin_root = base / root_name
                    shutil.copytree(
                        ROOT / "hooks",
                        plugin_root / "hooks",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                    )
                    plugin_data = plugin_root / "plugin data"
                    workspace = plugin_root / "workspace"
                    workspace.mkdir()
                    environment = os.environ.copy()
                    environment.update(
                        {
                            "PLUGIN_ROOT": str(plugin_root),
                            "PLUGIN_DATA": str(plugin_data),
                            "CLICK_CONFIG_HOME": str(plugin_data),
                        }
                    )

                    for event_name, mode in WINDOWS_MODES.items():
                        with self.subTest(plugin_root=root_name, event=event_name):
                            rendered = commands[event_name].replace(
                                "${PLUGIN_ROOT}", str(plugin_root)
                            )
                            self.assertNotIn("PLUGIN_ROOT", rendered)
                            event = synthetic_event(
                                event_name,
                                workspace,
                                f"{root_name}-{mode}".replace(" ", "-"),
                            )
                            result = subprocess.run(
                                [
                                    powershell,
                                    "-NoProfile",
                                    "-NonInteractive",
                                    "-Command",
                                    rendered,
                                ],
                                input=json.dumps(event) + "\n",
                                capture_output=True,
                                text=True,
                                cwd=workspace,
                                env=environment,
                                check=False,
                            )
                            self.assertEqual(
                                result.returncode,
                                0,
                                f"{event_name} failed:\n{result.stderr}\n{result.stdout}",
                            )
                            if event_name == "PreToolUse":
                                payload = json.loads(result.stdout)
                                updated = payload["hookSpecificOutput"]["updatedInput"]
                                self.assertIn("Click default mode:", updated["command"])

                    probe = workspace / "runner probe.txt"
                    probe.write_text("portable Windows runner\n", encoding="utf-8")
                    request = {
                        "version": 1,
                        "commands": [["Get-Content", "-Raw", probe.name]],
                    }
                    inspect_event = synthetic_event(
                        "PreToolUse",
                        workspace,
                        f"{root_name}-inspect".replace(" ", "-"),
                    )
                    inspect_event["tool_input"] = {
                        "command": (
                            "click-gate inspect '"
                            + json.dumps(request, separators=(",", ":"))
                            + "'"
                        )
                    }
                    rendered_hook = commands["PreToolUse"].replace(
                        "${PLUGIN_ROOT}", str(plugin_root)
                    )
                    hook_result = subprocess.run(
                        [
                            powershell,
                            "-NoProfile",
                            "-NonInteractive",
                            "-Command",
                            rendered_hook,
                        ],
                        input=json.dumps(inspect_event) + "\n",
                        capture_output=True,
                        text=True,
                        cwd=workspace,
                        env=environment,
                        check=False,
                    )
                    self.assertEqual(
                        hook_result.returncode,
                        0,
                        f"inspect hook failed:\n{hook_result.stderr}\n{hook_result.stdout}",
                    )
                    payload = json.loads(hook_result.stdout)
                    runner = payload["hookSpecificOutput"]["updatedInput"]["command"]
                    self.assertTrue(runner.startswith("py -3 "), runner)

                    shells = {
                        "PowerShell": [
                            powershell,
                            "-NoProfile",
                            "-NonInteractive",
                            "-Command",
                            runner,
                        ],
                        "cmd.exe": [command_prompt, "/d", "/s", "/c", runner],
                    }
                    for shell_name, invocation in shells.items():
                        with self.subTest(plugin_root=root_name, shell=shell_name):
                            runner_result = subprocess.run(
                                invocation,
                                capture_output=True,
                                text=True,
                                cwd=workspace,
                                env=environment,
                                check=False,
                            )
                            self.assertEqual(
                                runner_result.returncode,
                                0,
                                f"{shell_name} runner failed:\n"
                                f"{runner_result.stderr}\n{runner_result.stdout}",
                            )
                            self.assertEqual(
                                runner_result.stdout, "portable Windows runner\n"
                            )


if __name__ == "__main__":
    unittest.main()
