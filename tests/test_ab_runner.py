from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evals.run_ab import (
    _aggregate,
    _build_schedule,
    _condition_args,
    _condition_prompt,
    _is_root_inventory,
    _is_verification_command,
    _paired_deltas,
    _candidate_checks,
    _repository_snapshot,
    _runtime_trace,
    _thread_id_from_jsonl,
)


class ABRunnerTests(unittest.TestCase):
    def repository_fixture(self) -> tuple[Path, str]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repository = Path(temporary.name)
        subprocess.run(["git", "init", "--quiet"], cwd=repository, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Click Tests"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "click-tests@example.invalid"],
            cwd=repository,
            check=True,
        )
        (repository / "app.py").write_text("value = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "app.py"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "base"],
            cwd=repository,
            check=True,
        )
        base = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, text=True
        ).strip()
        return repository, base

    def test_schedule_is_repeated_complete_and_seeded(self) -> None:
        cases = [{"id": "a"}, {"id": "b"}]
        conditions = ["no-plugin", "explicit-skill-and-hook"]
        first = _build_schedule(cases, conditions, repetitions=3, seed=17)
        second = _build_schedule(cases, conditions, repetitions=3, seed=17)
        different = _build_schedule(cases, conditions, repetitions=3, seed=18)

        identity = lambda item: (
            item["case"]["id"],
            item["condition"],
            item["repetition"],
        )
        self.assertEqual([identity(item) for item in first], [identity(item) for item in second])
        self.assertNotEqual(
            [identity(item) for item in first], [identity(item) for item in different]
        )
        self.assertEqual(len(first), 12)
        self.assertEqual(len({identity(item) for item in first}), 12)

    def test_no_plugin_uses_a_prompt_without_the_skill_invocation(self) -> None:
        case = {
            "prompt": "$click Implement the change.",
            "baseline_prompt": "Implement the change.",
        }
        self.assertEqual(_condition_prompt(case, "no-plugin"), "Implement the change.")
        self.assertEqual(
            _condition_prompt(case, "explicit-skill-and-hook"),
            "$click Implement the change.",
        )

    def test_conditions_enable_only_the_pinned_plugin_in_isolated_home(self) -> None:
        installed = ["click@click-ab-isolated", "other@bundled"]
        baseline = _condition_args(
            "no-plugin", installed_plugin_ids=installed
        )
        self.assertIn("--disable", baseline)
        self.assertNotIn('plugins."click@click-ab-isolated".enabled=true', baseline)

        skill_only = _condition_args(
            "explicit-skill-only", installed_plugin_ids=installed
        )
        self.assertIn('plugins."click@click-ab-isolated".enabled=true', skill_only)
        self.assertIn('plugins."other@bundled".enabled=false', skill_only)
        self.assertNotIn("--dangerously-bypass-hook-trust", skill_only)

        with_hook = _condition_args(
            "explicit-skill-and-hook", installed_plugin_ids=installed
        )
        self.assertIn("--dangerously-bypass-hook-trust", with_hook)

    def test_inventory_metric_reuses_hook_argv_semantics(self) -> None:
        self.assertTrue(_is_root_inventory("rg --files"))
        self.assertTrue(_is_root_inventory("git ls-files"))
        self.assertFalse(_is_root_inventory("rg --files src"))
        self.assertFalse(_is_root_inventory("git worktree list"))
        self.assertFalse(_is_root_inventory("tree src"))

    def test_verification_metric_recognizes_the_hook_command_set(self) -> None:
        self.assertTrue(_is_verification_command("uv run pytest tests/test_one.py"))
        self.assertTrue(_is_verification_command("npm run lint"))
        self.assertTrue(_is_verification_command("click-gate verify '{}'"))
        self.assertFalse(_is_verification_command("python -c 'print(1)'"))

    def test_runtime_trace_counts_completed_observable_loops(self) -> None:
        events = [
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "rg --files",
                    "exit_code": 0,
                },
            },
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "rg --files",
                    "exit_code": 0,
                },
            },
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "python3 -m unittest discover -s tests",
                    "exit_code": 0,
                },
            },
            {
                "type": "item.completed",
                "item": {"type": "todo_list", "status": "completed"},
            },
        ]
        trace = _runtime_trace("\n".join(json.dumps(event) for event in events))
        self.assertEqual(trace["command_execution_count"], 3)
        self.assertEqual(trace["duplicate_successful_command_count"], 1)
        self.assertEqual(trace["root_inventory_count"], 2)
        self.assertEqual(trace["repeated_root_inventory_count"], 1)
        self.assertEqual(trace["verification_command_count"], 1)
        self.assertEqual(trace["plan_item_count"], 1)

    def test_thread_id_is_taken_from_the_candidate_jsonl(self) -> None:
        events = "\n".join(
            [
                json.dumps({"type": "turn.started"}),
                json.dumps(
                    {"type": "thread.started", "thread_id": "thread-candidate-7"}
                ),
            ]
        )
        self.assertEqual(_thread_id_from_jsonl(events), "thread-candidate-7")

    def test_repository_snapshot_captures_staged_and_untracked_changes(self) -> None:
        repository, base = self.repository_fixture()
        (repository / "app.py").write_text("value = 2\n", encoding="utf-8")
        subprocess.run(["git", "add", "app.py"], cwd=repository, check=True)
        (repository / "new_feature.py").write_text(
            "enabled = True\n", encoding="utf-8"
        )

        snapshot = _repository_snapshot(repository, base)

        self.assertTrue(snapshot["changed"])
        self.assertIn("value = 2", snapshot["diff"])
        self.assertIn("M  app.py", snapshot["status"])
        self.assertIn("?? new_feature.py", snapshot["status"])
        self.assertIn("enabled = True", snapshot["untracked_evidence"])

    def test_repository_snapshot_and_checks_reject_candidate_commits(self) -> None:
        repository, base = self.repository_fixture()
        (repository / "app.py").write_text("value = 3\n", encoding="utf-8")
        subprocess.run(["git", "add", "app.py"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "candidate commit"],
            cwd=repository,
            check=True,
        )

        snapshot = _repository_snapshot(repository, base)
        checks = _candidate_checks(
            {
                "id": "fixture",
                "checks": [
                    {
                        "name": "no-op",
                        "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                    }
                ],
            },
            repository,
            base,
            snapshot,
        )

        self.assertTrue(snapshot["head_changed"])
        self.assertIn("value = 3", snapshot["diff"])
        commit_check = next(
            check for check in checks if check["name"] == "candidate did not create a commit"
        )
        self.assertFalse(commit_check["passed"])

    def test_aggregate_reports_distribution_and_paired_baseline_delta(self) -> None:
        scores = [
            {
                "case_id": "case-a",
                "condition": "no-plugin",
                "repetition": 1,
                "status": "pass",
                "score": 80,
                "metrics": {"input_tokens": 100, "elapsed_seconds": 10},
            },
            {
                "case_id": "case-a",
                "condition": "explicit-skill-and-hook",
                "repetition": 1,
                "status": "pass",
                "score": 90,
                "metrics": {"input_tokens": 70, "elapsed_seconds": 8},
            },
        ]
        aggregate = _aggregate(scores)
        self.assertEqual(aggregate["no-plugin"]["input_tokens"]["median"], 100)
        deltas = _paired_deltas(scores)["explicit-skill-and-hook"]
        self.assertEqual(deltas["paired_runs"], 1)
        self.assertEqual(deltas["score_delta"]["median"], 10)
        self.assertEqual(deltas["input_tokens_delta"]["median"], -30)


if __name__ == "__main__":
    unittest.main()
