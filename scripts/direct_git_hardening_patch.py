from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_hook() -> None:
    path = ROOT / "hooks" / "click_gate.py"
    text = path.read_text(encoding="utf-8")
    old = '''        elif status == "review":
            rewritten, observation_error = _prepare_observation(
                event, inspection_request, broad_inventory, review=True
            )
            if observation_error:
                _deny(observation_error)
                return
            _allow_rewritten(rewritten)
        return
'''
    new = '''        elif status == "review":
            rewritten, observation_error = _prepare_observation(
                event, inspection_request, broad_inventory, review=True
            )
            if observation_error:
                _deny(observation_error)
                return
            _allow_rewritten(rewritten)
        elif any(
            Path(argv[0]).name.lower() in {"git", "git.exe"}
            for argv in inspection_request["commands"]
        ):
            _allow_rewritten(_inspection_once_runner_command(inspection_request))
        return
'''
    path.write_text(
        replace_once(text, old, new, "direct Git inspection routing"), encoding="utf-8"
    )


def patch_tests() -> None:
    path = ROOT / "tests" / "test_click_gate.py"
    text = path.read_text(encoding="utf-8")
    old = '''    def test_simple_read_only_inspection_is_not_tracked_outside_review(self) -> None:
        self.set_default("on")
        (self.workspace / "readme.txt").write_text("hello\\n", encoding="utf-8")
        command = self.read_file_command("readme.txt")
        self.assertIsNone(self.pre_tool("Bash", command))
        self.assertIsNone(self.pre_tool("Bash", command))
'''
    new = '''    def test_simple_read_only_inspection_is_not_tracked_outside_review(self) -> None:
        self.set_default("on")
        (self.workspace / "readme.txt").write_text("hello\\n", encoding="utf-8")
        command = self.read_file_command("readme.txt")
        self.assertIsNone(self.pre_tool("Bash", command))
        self.assertIsNone(self.pre_tool("Bash", command))

        initialized = subprocess.run(
            ["git", "init", "--quiet"],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        git_read = self.pre_tool("Bash", "git status --short")
        self.assertEqual(
            git_read["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertIn(
            "run-inspection-once",
            git_read["hookSpecificOutput"]["updatedInput"]["command"],
        )
        completed = self.run_rewritten(git_read)
        self.assertEqual(completed.returncode, 0, completed.stderr)
'''
    path.write_text(
        replace_once(text, old, new, "direct Git inspection regression"), encoding="utf-8"
    )


def main() -> None:
    patch_hook()
    patch_tests()


if __name__ == "__main__":
    main()
