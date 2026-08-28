#!/usr/bin/env python3
"""Run a bounded Click A/B pilot on pinned disposable repositories."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any

try:
    from .semantic_grader import AssessmentError, score_assessment
except ImportError:
    from semantic_grader import AssessmentError, score_assessment


ROOT = Path(__file__).parents[1]
DEFAULT_SUITE = Path(__file__).with_name("ab-suite.json")
JUDGE_SCHEMA = Path(__file__).with_name("semantic-judgment.schema.json")
JUDGE_GUIDE = Path(__file__).with_name("SEMANTIC_GRADER.md")
HOOK_TEST = ROOT / "tests" / "test_click_gate.py"
CONDITION_ARGS = {
    "no-plugin": ["--disable", "plugins", "--disable", "hooks"],
    "explicit-skill-only": [
        "--disable",
        "hooks",
        "-c",
        'plugins."ballast@ballast".enabled=false',
    ],
    "explicit-skill-and-hook": [
        "--enable",
        "hooks",
        "--dangerously-bypass-hook-trust",
        "-c",
        'plugins."ballast@ballast".enabled=false',
    ],
}


def _run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _usage_from_jsonl(text: str) -> dict[str, int]:
    usage: dict[str, int] = {}
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed" and isinstance(
            event.get("usage"), dict
        ):
            usage = {
                key: int(value)
                for key, value in event["usage"].items()
                if isinstance(value, (int, float))
            }
    return usage


def _thread_id_from_jsonl(text: str) -> str:
    for event in _jsonl_events(text):
        if event.get("type") != "thread.started":
            continue
        thread_id = event.get("thread_id")
        if isinstance(thread_id, str) and thread_id:
            return thread_id
    return ""


def _sum_usage(*items: dict[str, int]) -> dict[str, int]:
    keys = {key for item in items for key in item}
    return {key: sum(item.get(key, 0) for item in items) for key in keys}


def _jsonl_events(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _completed_items(text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for event in _jsonl_events(text):
        if event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if isinstance(item, dict):
            items.append(item)
    return items


def _item_command(item: dict[str, Any]) -> str:
    command = item.get("command")
    if isinstance(command, str):
        return " ".join(command.split())
    if isinstance(command, list) and all(isinstance(part, str) for part in command):
        return " ".join(str(part) for part in command)
    return ""


def _successful_command(item: dict[str, Any]) -> bool:
    exit_code = item.get("exit_code")
    status = str(item.get("status", "")).lower()
    return exit_code == 0 or (exit_code is None and status in {"completed", "success"})


def _is_root_inventory(command: str) -> bool:
    lowered = command.lower()
    markers = (
        "rg --files",
        "git ls-files",
        "find . ",
        "find .\n",
        "ls -r",
        "tree",
        "get-childitem -recurse -path .",
    )
    return any(marker in lowered for marker in markers)


def _is_verification_command(command: str) -> bool:
    lowered = command.lower()
    markers = (
        "click-gate verify",
        " pytest",
        "pytest ",
        "python -m unittest",
        "python3 -m unittest",
        "python -m pytest",
        "python3 -m pytest",
        "npm test",
        "pnpm test",
        "yarn test",
        "cargo test",
        "go test",
        "dotnet test",
    )
    return any(marker in f" {lowered}" for marker in markers)


def _runtime_trace(text: str) -> dict[str, Any]:
    items = _completed_items(text)
    commands = [_item_command(item) for item in items]
    commands = [command for command in commands if command]
    successful_commands = [
        _item_command(item)
        for item in items
        if _item_command(item) and _successful_command(item)
    ]
    command_frequencies: dict[str, int] = {}
    for command in successful_commands:
        command_frequencies[command] = command_frequencies.get(command, 0) + 1
    duplicate_successes = sum(
        max(0, count - 1) for count in command_frequencies.values()
    )
    inventories = [command for command in commands if _is_root_inventory(command)]
    item_types = [str(item.get("type", "")) for item in items]
    lowered = text.lower()
    excerpts = [
        line[-2_000:]
        for line in text.splitlines()
        if "click execution contract" in line.lower()
        or "click-gate" in line.lower()
        or "permissiondecision" in line.lower()
    ]
    return {
        "completed_tool_items": sum(
            item_type not in {"agent_message", "reasoning"}
            for item_type in item_types
        ),
        "command_execution_count": len(commands),
        "duplicate_successful_command_count": duplicate_successes,
        "root_inventory_count": len(inventories),
        "repeated_root_inventory_count": max(0, len(inventories) - 1),
        "verification_command_count": sum(
            _is_verification_command(command) for command in commands
        ),
        "plan_item_count": sum(
            item_type in {"plan", "todo_list", "update_plan"}
            for item_type in item_types
        )
        + sum("update_plan" in command.lower() for command in commands),
        "file_change_item_count": sum(
            item_type in {"file_change", "file_write"} for item_type in item_types
        ),
        "gate_block_count": lowered.count('"permissiondecision":"deny"')
        + lowered.count('"permissiondecision": "deny"'),
        "gate_arm_mentions": sum("click-gate arm" in command.lower() for command in commands),
        "gate_stage_mentions": sum(
            "click-gate stage" in command.lower() for command in commands
        ),
        "gate_pass_mentions": sum(
            "click-gate pass" in command.lower() for command in commands
        ),
        "gate_bypass_mentions": sum(
            "click-gate bypass" in command.lower() for command in commands
        ),
        "excerpts": excerpts[-12:],
    }


def _check(
    name: str,
    result: subprocess.CompletedProcess[str],
    evidence_limit: int = 4_000,
) -> dict[str, Any]:
    combined = (result.stdout + "\n" + result.stderr).strip()
    return {
        "name": name,
        "passed": result.returncode == 0,
        "required": True,
        "evidence": combined[-evidence_limit:] or f"exit code {result.returncode}",
    }


def _clone_case(case: dict[str, Any], destination: Path) -> None:
    clone = _run(
        ["git", "clone", "--quiet", str(case["repository"]), str(destination)],
        cwd=destination.parent,
        timeout=180,
    )
    if clone.returncode != 0:
        raise RuntimeError(f"git clone failed: {clone.stderr.strip()}")
    checkout = _run(
        ["git", "checkout", "--quiet", "--detach", str(case["commit"])],
        cwd=destination,
        timeout=60,
    )
    if checkout.returncode != 0:
        raise RuntimeError(f"git checkout failed: {checkout.stderr.strip()}")


def _candidate_checks(case: dict[str, Any], candidate: Path) -> list[dict[str, Any]]:
    checks = [
        _check(
            "git diff --check",
            _run(["git", "diff", "--check"], cwd=candidate, timeout=60),
        )
    ]
    raw_checks = case.get("checks")
    if raw_checks is None:
        raw_checks = [
            {
                "name": "candidate test suite",
                "argv": [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-v",
                ],
                "timeout_seconds": 180,
            }
        ]
    if not isinstance(raw_checks, list):
        raise RuntimeError(f"case {case['id']} checks must be an array")
    for index, raw_check in enumerate(raw_checks, start=1):
        if not isinstance(raw_check, dict):
            raise RuntimeError(f"case {case['id']} check {index} must be an object")
        argv = raw_check.get("argv")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(part, str) and part for part in argv
        ):
            raise RuntimeError(
                f"case {case['id']} check {index} argv must be a non-empty string array"
            )
        timeout_seconds = int(raw_check.get("timeout_seconds", 180))
        checks.append(
            _check(
                str(raw_check.get("name", f"case check {index}")),
                _run(argv, cwd=candidate, timeout=timeout_seconds),
            )
        )
    if case.get("external_hook_contract"):
        environment = os.environ.copy()
        environment["CLICK_GATE_UNDER_TEST"] = str(
            candidate / "hooks" / "click_gate.py"
        )
        environment["CLICK_HOOK_CONFIG_UNDER_TEST"] = str(
            candidate / "hooks" / "hooks.json"
        )
        checks.append(
            _check(
                "v0.15.0 hardened one-shot contract Hook",
                _run(
                    [sys.executable, str(HOOK_TEST)],
                    cwd=ROOT,
                    timeout=180,
                    environment=environment,
                ),
            )
        )
    return checks


def _judge_prompt(
    *,
    masked_id: str,
    case: dict[str, Any],
    request: str,
    expected_activation: bool,
    approval_followup: str | None,
    diff: str,
    pre_approval_diff: str,
    preview_message: str,
    final_message: str,
    checks: list[dict[str, Any]],
    runtime_trace: dict[str, Any],
) -> str:
    guide = JUDGE_GUIDE.read_text(encoding="utf-8")
    evidence = {
        "masked_candidate": masked_id,
        "request": request,
        "expected_activation": expected_activation,
        "opt_out_applicable": case["opt_out_applicable"],
        "required_invariants": case["required_invariants"],
        "approval_followup": approval_followup,
        "automated_checks": checks,
        "runtime_trace": runtime_trace,
        "pre_approval_diff": pre_approval_diff[-30_000:],
        "candidate_design_preview": preview_message[-12_000:],
        "candidate_diff": diff[-60_000:],
        "candidate_final_message": final_message[-12_000:],
    }
    return (
        f"{guide}\n\nEvaluate this single masked candidate. Do not use tools or seek other "
        "candidates. Return only the required JSON.\n\n"
        + json.dumps(evidence, ensure_ascii=False, indent=2)
    )


def _judge(
    *,
    run_dir: Path,
    prompt: str,
    model: str,
    reasoning_effort: str,
) -> tuple[dict[str, Any], subprocess.CompletedProcess[str], float]:
    judgment_path = run_dir / "judgment.json"
    started = time.monotonic()
    result = _run(
        [
            "codex",
            "exec",
            "--ignore-user-config",
            "--disable",
            "plugins",
            "--disable",
            "hooks",
            "--ignore-rules",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--model",
            model,
            "-c",
            f'model_reasoning_effort="{reasoning_effort}"',
            "--output-schema",
            str(JUDGE_SCHEMA),
            "--output-last-message",
            str(judgment_path),
            "--json",
            prompt,
        ],
        cwd=run_dir,
        timeout=900,
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0 or not judgment_path.exists():
        raise RuntimeError(
            "semantic judge failed: " + (result.stderr or result.stdout)[-2_000:]
        )
    return json.loads(judgment_path.read_text(encoding="utf-8")), result, elapsed


def _condition_prompt(case: dict[str, Any], condition: str) -> str:
    if condition == "no-plugin" and case.get("baseline_prompt"):
        return str(case["baseline_prompt"])
    return str(case["prompt"])


def _build_schedule(
    cases: list[dict[str, Any]],
    conditions: list[str],
    repetitions: int,
    seed: int,
) -> list[dict[str, Any]]:
    schedule = [
        {"case": case, "condition": condition, "repetition": repetition}
        for repetition in range(1, repetitions + 1)
        for case in cases
        for condition in conditions
    ]
    random.Random(seed).shuffle(schedule)
    return schedule


def _metric_summary(items: list[dict[str, Any]], name: str) -> dict[str, float]:
    values = [float(item.get("metrics", {}).get(name, 0)) for item in items]
    return {
        "mean": round(statistics.fmean(values), 3),
        "median": round(statistics.median(values), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "population_stdev": round(statistics.pstdev(values), 3),
    }


def _aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    by_condition: dict[str, list[dict[str, Any]]] = {}
    for score in scores:
        by_condition.setdefault(score["condition"], []).append(score)
    return {
        condition: {
            "runs": len(items),
            "pass_rate": round(
                sum(item["status"] == "pass" for item in items) / len(items), 3
            ),
            "mean_score": round(sum(item["score"] for item in items) / len(items), 1),
            "input_tokens": _metric_summary(items, "input_tokens"),
            "output_tokens": _metric_summary(items, "output_tokens"),
            "elapsed_seconds": _metric_summary(items, "elapsed_seconds"),
            "completed_tool_items": _metric_summary(items, "completed_tool_items"),
            "duplicate_successful_command_count": _metric_summary(
                items, "duplicate_successful_command_count"
            ),
            "repeated_root_inventory_count": _metric_summary(
                items, "repeated_root_inventory_count"
            ),
            "verification_command_count": _metric_summary(
                items, "verification_command_count"
            ),
            "plan_item_count": _metric_summary(items, "plan_item_count"),
        }
        for condition, items in by_condition.items()
    }


def _paired_deltas(scores: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed = {
        (item["case_id"], int(item["repetition"]), item["condition"]): item
        for item in scores
    }
    metrics = (
        "score",
        "input_tokens",
        "output_tokens",
        "elapsed_seconds",
        "completed_tool_items",
        "duplicate_successful_command_count",
        "repeated_root_inventory_count",
        "verification_command_count",
        "plan_item_count",
    )
    conditions = sorted(
        {item["condition"] for item in scores if item["condition"] != "no-plugin"}
    )
    result: dict[str, dict[str, Any]] = {}
    for condition in conditions:
        pairs = []
        for key, baseline in indexed.items():
            case_id, repetition, baseline_condition = key
            if baseline_condition != "no-plugin":
                continue
            candidate = indexed.get((case_id, repetition, condition))
            if candidate is not None:
                pairs.append((baseline, candidate))
        condition_result: dict[str, Any] = {"paired_runs": len(pairs)}
        for metric in metrics:
            deltas: list[float] = []
            for baseline, candidate in pairs:
                baseline_value = (
                    baseline.get("score", 0)
                    if metric == "score"
                    else baseline.get("metrics", {}).get(metric, 0)
                )
                candidate_value = (
                    candidate.get("score", 0)
                    if metric == "score"
                    else candidate.get("metrics", {}).get(metric, 0)
                )
                deltas.append(float(candidate_value) - float(baseline_value))
            if deltas:
                condition_result[f"{metric}_delta"] = {
                    "mean": round(statistics.fmean(deltas), 3),
                    "median": round(statistics.median(deltas), 3),
                }
        result[condition] = condition_result
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded Click A/B pilot")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--condition", action="append", dest="conditions")
    parser.add_argument(
        "--repetitions",
        type=int,
        help="override suite runs_per_condition (paid model runs; no default execution)",
    )
    parser.add_argument("--seed", type=int, help="override suite random_seed")
    parser.add_argument("--keep-worktrees", action="store_true")
    parser.add_argument(
        "--execute-paid-runs",
        action="store_true",
        help="required acknowledgement before starting candidate and judge model calls",
    )
    arguments = parser.parse_args()

    suite = json.loads(arguments.suite.read_text(encoding="utf-8"))
    selected_cases = [
        case
        for case in suite["cases"]
        if not arguments.case_ids or case["id"] in arguments.case_ids
    ]
    selected_conditions = [
        condition
        for condition in suite["conditions"]
        if not arguments.conditions or condition in arguments.conditions
    ]
    unknown_conditions = set(selected_conditions) - set(CONDITION_ARGS)
    if unknown_conditions:
        parser.error(f"unknown conditions: {sorted(unknown_conditions)}")
    if not selected_cases or not selected_conditions:
        parser.error("at least one case and condition must be selected")
    if not arguments.execute_paid_runs:
        parser.error(
            "A/B evaluation starts paid candidate and judge calls. Re-run with "
            "--execute-paid-runs after reviewing the selected suite and repetitions."
        )
    repetitions = (
        arguments.repetitions
        if arguments.repetitions is not None
        else int(suite.get("runs_per_condition", 1))
    )
    if repetitions < 1 or repetitions > 50:
        parser.error("repetitions must be between 1 and 50")
    seed = arguments.seed if arguments.seed is not None else int(suite.get("random_seed", 0))
    for case in selected_cases:
        if (
            bool(case.get("expected_activation"))
            and "no-plugin" in selected_conditions
            and not case.get("baseline_prompt")
        ):
            parser.error(
                f"activated case {case['id']} needs baseline_prompt for no-plugin masking"
            )

    results_root = arguments.results.resolve()
    work_root = results_root / "worktrees"
    work_root.mkdir(parents=True, exist_ok=True)
    scores: list[dict[str, Any]] = []
    run_index = 0
    schedule = _build_schedule(
        selected_cases, selected_conditions, repetitions, seed
    )

    for scheduled in schedule:
            case = scheduled["case"]
            condition = str(scheduled["condition"])
            repetition = int(scheduled["repetition"])
            run_index += 1
            masked_id = f"candidate-{run_index:03d}"
            run_dir = (
                results_root
                / "runs"
                / str(case["id"])
                / condition
                / f"repeat-{repetition:02d}"
            )
            candidate = work_root / f"{case['id']}-{condition}-r{repetition:02d}"
            run_dir.mkdir(parents=True, exist_ok=True)
            if candidate.exists():
                shutil.rmtree(candidate)
            _clone_case(case, candidate)

            approval_followup = case.get("approval_followup")
            needs_followup = bool(approval_followup) and condition != "no-plugin"
            preview_path = run_dir / (
                "preview-message.md" if needs_followup else "final-message.md"
            )
            command = [
                "codex",
                "exec",
            ]
            if not needs_followup:
                command.append("--ephemeral")
            command.extend([
                "--ignore-rules",
                "--sandbox",
                "workspace-write",
                "--model",
                str(suite["model"]),
                "-c",
                f'model_reasoning_effort="{suite["reasoning_effort"]}"',
                "-c",
                'approval_policy="never"',
                "--output-last-message",
                str(preview_path),
                "--json",
                *CONDITION_ARGS[condition],
                _condition_prompt(case, condition),
            ])
            started = time.monotonic()
            candidate_result = _run(command, cwd=candidate, timeout=1_800)
            preview_elapsed = time.monotonic() - started
            preview_message = (
                preview_path.read_text(encoding="utf-8")
                if preview_path.exists()
                else ""
            )
            pre_approval_diff_result = _run(
                ["git", "diff", "--no-ext-diff", "--binary"],
                cwd=candidate,
                timeout=60,
            )
            pre_approval_diff = pre_approval_diff_result.stdout
            _write(run_dir / "pre-approval.patch", pre_approval_diff)
            _write(run_dir / "preview-events.jsonl", candidate_result.stdout)
            _write(run_dir / "preview-stderr.txt", candidate_result.stderr)

            approval_result: subprocess.CompletedProcess[str] | None = None
            approval_elapsed = 0.0
            final_message = preview_message
            if needs_followup and candidate_result.returncode == 0:
                thread_id = _thread_id_from_jsonl(candidate_result.stdout)
                if not thread_id:
                    raise RuntimeError(
                        f"candidate preview {masked_id} returned no thread.started id"
                    )
                final_path = run_dir / "final-message.md"
                approval_command = [
                    "codex",
                    "exec",
                    "resume",
                    "--ignore-rules",
                    "--model",
                    str(suite["model"]),
                    "-c",
                    f'model_reasoning_effort="{suite["reasoning_effort"]}"',
                    "-c",
                    'approval_policy="never"',
                    "--output-last-message",
                    str(final_path),
                    "--json",
                    *CONDITION_ARGS[condition],
                    thread_id,
                    str(approval_followup),
                ]
                approval_started = time.monotonic()
                approval_result = _run(
                    approval_command,
                    cwd=candidate,
                    timeout=1_800,
                )
                approval_elapsed = time.monotonic() - approval_started
                _write(run_dir / "approval-events.jsonl", approval_result.stdout)
                _write(run_dir / "approval-stderr.txt", approval_result.stderr)
                if final_path.exists():
                    final_message = final_path.read_text(encoding="utf-8")

            candidate_elapsed = preview_elapsed + approval_elapsed
            combined_events = candidate_result.stdout
            combined_stderr = candidate_result.stderr
            if approval_result is not None:
                combined_events += "\n" + approval_result.stdout
                combined_stderr += "\n" + approval_result.stderr
            _write(run_dir / "events.jsonl", combined_events)
            _write(run_dir / "codex-stderr.txt", combined_stderr)

            diff_result = _run(
                ["git", "diff", "--no-ext-diff", "--binary"],
                cwd=candidate,
                timeout=60,
            )
            diff = diff_result.stdout
            _write(run_dir / "candidate.patch", diff)
            checks = _candidate_checks(case, candidate)
            if needs_followup:
                checks.append(
                    {
                        "name": "repository unchanged before execution contract approval",
                        "passed": not pre_approval_diff.strip(),
                        "required": True,
                        "evidence": pre_approval_diff[-4_000:]
                        or "no pre-approval repository diff",
                    }
                )
            runtime_trace = _runtime_trace(combined_events + "\n" + combined_stderr)
            if candidate_result.returncode != 0:
                checks.append(
                    {
                        "name": "Codex design-preview run",
                        "passed": False,
                        "required": True,
                        "evidence": (candidate_result.stderr or candidate_result.stdout)[-4_000:]
                        or f"exit code {candidate_result.returncode}",
                    }
                )
            if approval_result is not None and approval_result.returncode != 0:
                checks.append(
                    {
                        "name": "Codex approved implementation run",
                        "passed": False,
                        "required": True,
                        "evidence": (
                            approval_result.stderr or approval_result.stdout
                        )[-4_000:]
                        or f"exit code {approval_result.returncode}",
                    }
                )

            judgment, judge_result, judge_elapsed = _judge(
                run_dir=run_dir,
                prompt=_judge_prompt(
                    masked_id=masked_id,
                    case=case,
                    request=_condition_prompt(case, condition),
                    expected_activation=(
                        bool(case["expected_activation"])
                        and condition != "no-plugin"
                    ),
                    approval_followup=(
                        str(approval_followup) if needs_followup else None
                    ),
                    diff=diff,
                    pre_approval_diff=pre_approval_diff,
                    preview_message=preview_message,
                    final_message=final_message,
                    checks=checks,
                    runtime_trace=runtime_trace,
                ),
                model=str(suite["judge_model"]),
                reasoning_effort=str(suite["judge_reasoning_effort"]),
            )
            _write(run_dir / "judge-events.jsonl", judge_result.stdout)
            _write(run_dir / "judge-stderr.txt", judge_result.stderr)

            usage = _sum_usage(
                _usage_from_jsonl(candidate_result.stdout),
                _usage_from_jsonl(approval_result.stdout)
                if approval_result is not None
                else {},
            )
            judge_usage = _usage_from_jsonl(judge_result.stdout)
            assessment = {
                "schema_version": 2,
                "case_id": str(case["id"]),
                "condition": condition,
                "repetition": repetition,
                "masked_candidate": masked_id,
                "automated_checks": checks,
                "semantic_judgment": judgment,
                "metrics": {
                    **usage,
                    "elapsed_seconds": round(candidate_elapsed, 3),
                    "preview_elapsed_seconds": round(preview_elapsed, 3),
                    "approval_elapsed_seconds": round(approval_elapsed, 3),
                    "approval_turns": 1 if approval_result is not None else 0,
                    "judge_input_tokens": judge_usage.get("input_tokens", 0),
                    "judge_output_tokens": judge_usage.get("output_tokens", 0),
                    "judge_elapsed_seconds": round(judge_elapsed, 3),
                    "gate_block_count": runtime_trace["gate_block_count"],
                    "gate_arm_mentions": runtime_trace["gate_arm_mentions"],
                    "gate_stage_mentions": runtime_trace["gate_stage_mentions"],
                    "gate_pass_mentions": runtime_trace["gate_pass_mentions"],
                    "gate_bypass_mentions": runtime_trace["gate_bypass_mentions"],
                    "completed_tool_items": runtime_trace["completed_tool_items"],
                    "command_execution_count": runtime_trace[
                        "command_execution_count"
                    ],
                    "duplicate_successful_command_count": runtime_trace[
                        "duplicate_successful_command_count"
                    ],
                    "root_inventory_count": runtime_trace["root_inventory_count"],
                    "repeated_root_inventory_count": runtime_trace[
                        "repeated_root_inventory_count"
                    ],
                    "verification_command_count": runtime_trace[
                        "verification_command_count"
                    ],
                    "plan_item_count": runtime_trace["plan_item_count"],
                    "file_change_item_count": runtime_trace[
                        "file_change_item_count"
                    ],
                },
            }
            try:
                score = score_assessment(assessment)
            except AssessmentError as exc:
                raise RuntimeError(f"invalid judgment for {masked_id}: {exc}") from exc
            score["repetition"] = repetition
            score["masked_candidate"] = masked_id
            _write(
                run_dir / "assessment.json",
                json.dumps(assessment, ensure_ascii=False, indent=2) + "\n",
            )
            _write(
                run_dir / "score.json",
                json.dumps(score, ensure_ascii=False, indent=2) + "\n",
            )
            scores.append(score)
            print(
                f"{case['id']} / {condition} / repeat {repetition}: "
                f"{score['score']} ({score['status']})",
                flush=True,
            )
            if not arguments.keep_worktrees:
                shutil.rmtree(candidate)

    summary = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suite": str(arguments.suite.resolve()),
        "release_under_test": suite.get("release_under_test", "unknown"),
        "model": suite["model"],
        "reasoning_effort": suite["reasoning_effort"],
        "judge_model": suite["judge_model"],
        "judge_reasoning_effort": suite["judge_reasoning_effort"],
        "runs_per_condition": repetitions,
        "random_seed": seed,
        "sample_size": len(scores),
        "aggregate": _aggregate(scores),
        "paired_deltas_against_no_plugin": _paired_deltas(scores),
        "schedule": [
            {
                "case_id": str(item["case"]["id"]),
                "condition": str(item["condition"]),
                "repetition": int(item["repetition"]),
            }
            for item in schedule
        ],
        "scores": scores,
    }
    _write(
        results_root / "summary.json",
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
    )
    if not arguments.keep_worktrees and work_root.exists():
        work_root.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
