from __future__ import annotations

import ast
from pathlib import Path
import unittest

from hooks import click_capability, click_gate


class ClickCapabilityTests(unittest.TestCase):
    def test_capability_validation_is_a_runtime_leaf(self) -> None:
        source = Path(click_capability.__file__).read_text(encoding="utf-8")
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
        self.assertFalse(
            any(part.startswith("click_") for name in imported for part in name.split(".")),
            imported,
        )

    def test_gate_keeps_capability_compatibility_aliases(self) -> None:
        aliases = {
            "_decode_capability_request": click_capability.decode_request,
            "_validate_argv": click_capability.validate_argv,
            "_policy_executable_name": click_capability.policy_executable_name,
            "_shell_segments": click_capability.shell_segments,
            "_command_parts": click_capability.command_parts,
            "_positional_arguments": click_capability.positional_arguments,
            "_capability_digest": click_capability.digest,
            "_encoded_request": click_capability.encode_request,
            "_decode_encoded_request": click_capability.decode_encoded_request,
        }
        for name, expected in aliases.items():
            with self.subTest(name=name):
                self.assertIs(getattr(click_gate, name), expected)
        self.assertEqual(
            click_gate.CAPABILITY_PROTOCOL_VERSION,
            click_capability.PROTOCOL_VERSION,
        )
        self.assertEqual(click_gate.MAX_ARGV_ITEMS, click_capability.MAX_ARGV_ITEMS)

    def test_direct_argv_errors_and_normalization_are_exact(self) -> None:
        cases = (
            (None, "Inspection `argv` must be a non-empty string list."),
            ([""], "Every Inspection `argv` item must be a non-empty NUL-free string."),
            (
                ["CI=1", "pytest"],
                "Inspection cannot use a NAME=value environment prefix. Pass direct argv; "
                "a future protocol may add an explicit environment field.",
            ),
            (
                ["PowerShell.exe", "-Command", "Get-Content README.md"],
                "Inspection cannot invoke a shell interpreter. Pass the executable and "
                "each argument directly instead of using `-c` or `-Command`.",
            ),
            (
                [r"C:\Windows\System32\taskkill.exe", "/IM", "codex.exe"],
                "Inspection cannot invoke the process-control executable `taskkill`. Use "
                "a target-specific lifecycle command that cannot terminate Codex or "
                "unrelated processes.",
            ),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv):
                normalized, error = click_capability.validate_argv(argv, "Inspection")
                self.assertIsNone(normalized)
                self.assertEqual(error, expected)

        normalized, error = click_capability.validate_argv(
            ["python", "-m", "unittest"], "Verification"
        )
        self.assertEqual(error, "")
        self.assertEqual(normalized, ["python", "-m", "unittest"])


if __name__ == "__main__":
    unittest.main()
