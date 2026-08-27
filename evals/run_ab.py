#!/usr/bin/env python3
"""Run a bounded Build Brief A/B pilot on pinned disposable repositories."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

from semantic_grader import AssessmentError, score_assessment


ROOT = Path(__file__).parents[1]
DEFAULT_SUITE = Path(__file__).with_name("ab-suite.json")
JUDGE_SCHEMA = Path(__file__).with_name("semantic-judgment.schema.json")
JUDGE_GUIDE = Path(__file__).with_name("SEMANTIC_GRADER.md")
HOOK_TEST = ROOT / "tests" / "test_build_brief_gate.py"
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


def _runtime_trace(text: str) -> dict[str, Any]:
    markers = {
        "gate_block_count": "blocked this mutation",
        "gate_arm_mentions": "build-brief-gate arm",
        "gate_pass_mentions": "build-brief-gate pass",
        "gate_bypass_mentions": "build-brief-gate bypass",
    }
    lowered = text.lower()
    excerpts = [
        line[-2_000:]
        for line in text.splitlines()
        if "build brief" in line.lower() or "build-brief-gate" in line.lower()
    ]
    return {
        **{name: lowered.count(marker) for name, marker in markers.items()},
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
        ),
        _check(
            "candidate test suite",
            _run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                cwd=candidate,
                timeout=180,
            ),
        ),
    ]
    if case.get("external_hook_contract"):
        environment = os.environ.copy()
        environment["BUILD_BRIEF_GATE_UNDER_TEST"] = str(
            candidate / "hooks" / "build_brief_gate.py"
        )
        environment["BUILD_BRIEF_HOOK_CONFIG_UNDER_TEST"] = str(
            candidate / "hooks" / "hooks.json"
        )
        checks.append(
            _check(
                "v0.6.0 explicit-activation Hook contract",
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
    diff: str,
    final_message: str,
    checks: list[dict[str, Any]],
    runtime_trace: dict[str, Any],
) -> str:
    guide = JUDGE_GUIDE.read_text(encoding="utf-8")
    evidence = {
        "masked_candidate": masked_id,
        "request": case["prompt"],
        "expected_activation": case["expected_activation"],
        "opt_out_applicable": case["opt_out_applicable"],
        "required_invariants": case["required_invariants"],
        "automated_checks": checks,
        "runtime_trace": runtime_trace,
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
            "mean_input_tokens": round(
                sum(item.get("metrics", {}).get("input_tokens", 0) for item in items)
                / len(items),
                1,
            ),
            "mean_elapsed_seconds": round(
                sum(item.get("metrics", {}).get("elapsed_seconds", 0) for item in items)
                / len(items),
                2,
            ),
        }
        for condition, items in by_condition.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded Build Brief A/B pilot")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--condition", action="append", dest="conditions")
    parser.add_argument("--keep-worktrees", action="store_true")
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

    results_root = arguments.results.resolve()
    work_root = results_root / "worktrees"
    work_root.mkdir(parents=True, exist_ok=True)
    scores: list[dict[str, Any]] = []
    run_index = 0

    for case in selected_cases:
        for condition in selected_conditions:
            run_index += 1
            masked_id = f"candidate-{run_index:02d}"
            run_dir = results_root / "runs" / case["id"] / condition
            candidate = work_root / f"{case['id']}-{condition}"
            run_dir.mkdir(parents=True, exist_ok=True)
            if candidate.exists():
                shutil.rmtree(candidate)
            _clone_case(case, candidate)

            final_path = run_dir / "final-message.md"
            command = [
                "codex",
                "exec",
                "--ephemeral",
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
                str(final_path),
                "--json",
                *CONDITION_ARGS[condition],
                str(case["prompt"]),
            ]
            started = time.monotonic()
            candidate_result = _run(command, cwd=candidate, timeout=1_800)
            candidate_elapsed = time.monotonic() - started
            _write(run_dir / "events.jsonl", candidate_result.stdout)
            _write(run_dir / "codex-stderr.txt", candidate_result.stderr)
            final_message = (
                final_path.read_text(encoding="utf-8") if final_path.exists() else ""
            )

            diff_result = _run(
                ["git", "diff", "--no-ext-diff", "--binary"],
                cwd=candidate,
                timeout=60,
            )
            diff = diff_result.stdout
            _write(run_dir / "candidate.patch", diff)
            checks = _candidate_checks(case, candidate)
            runtime_trace = _runtime_trace(
                candidate_result.stdout + "\n" + candidate_result.stderr
            )
            if candidate_result.returncode != 0:
                checks.append(
                    {
                        "name": "Codex implementation run",
                        "passed": False,
                        "required": True,
                        "evidence": (candidate_result.stderr or candidate_result.stdout)[-4_000:]
                        or f"exit code {candidate_result.returncode}",
                    }
                )

            judgment, judge_result, judge_elapsed = _judge(
                run_dir=run_dir,
                prompt=_judge_prompt(
                    masked_id=masked_id,
                    case=case,
                    diff=diff,
                    final_message=final_message,
                    checks=checks,
                    runtime_trace=runtime_trace,
                ),
                model=str(suite["judge_model"]),
                reasoning_effort=str(suite["judge_reasoning_effort"]),
            )
            _write(run_dir / "judge-events.jsonl", judge_result.stdout)
            _write(run_dir / "judge-stderr.txt", judge_result.stderr)

            usage = _usage_from_jsonl(candidate_result.stdout)
            judge_usage = _usage_from_jsonl(judge_result.stdout)
            assessment = {
                "schema_version": 1,
                "case_id": str(case["id"]),
                "condition": condition,
                "automated_checks": checks,
                "semantic_judgment": judgment,
                "metrics": {
                    **usage,
                    "elapsed_seconds": round(candidate_elapsed, 3),
                    "judge_input_tokens": judge_usage.get("input_tokens", 0),
                    "judge_output_tokens": judge_usage.get("output_tokens", 0),
                    "judge_elapsed_seconds": round(judge_elapsed, 3),
                    "gate_block_count": runtime_trace["gate_block_count"],
                    "gate_arm_mentions": runtime_trace["gate_arm_mentions"],
                    "gate_pass_mentions": runtime_trace["gate_pass_mentions"],
                    "gate_bypass_mentions": runtime_trace["gate_bypass_mentions"],
                },
            }
            try:
                score = score_assessment(assessment)
            except AssessmentError as exc:
                raise RuntimeError(f"invalid judgment for {masked_id}: {exc}") from exc
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
                f"{case['id']} / {condition}: {score['score']} ({score['status']})",
                flush=True,
            )
            if not arguments.keep_worktrees:
                shutil.rmtree(candidate)

    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suite": str(arguments.suite.resolve()),
        "model": suite["model"],
        "reasoning_effort": suite["reasoning_effort"],
        "judge_model": suite["judge_model"],
        "judge_reasoning_effort": suite["judge_reasoning_effort"],
        "sample_size": len(scores),
        "aggregate": _aggregate(scores),
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
