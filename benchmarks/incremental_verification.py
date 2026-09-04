#!/usr/bin/env python3
"""Small repeatable benchmark for Click's canonical execution-plan path.

The fixture runs four independent real child-process checks to establish a
recent duration baseline.  Its incremental pass executes the single affected
source selected by ``click_incremental.keys_to_execute`` and treats the other
three durations only as estimates of work that authoritative reuse would
avoid.  It is a fixture, not a product-performance claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hooks import click_incremental  # noqa: E402


BENCHMARK_VERSION = 1
SOURCE_KEYS = tuple(str(index) * 64 for index in range(1, 5))
CHECK_DIGESTS = tuple(str(index) * 64 for index in range(5, 9))
DEFAULT_ITERATIONS = 3
DEFAULT_WORKLOAD_ROUNDS = 40_000
MAX_ITERATIONS = 10
MAX_WORKLOAD_ROUNDS = 1_000_000


def _workload(index: int, rounds: int) -> None:
    if index not in range(len(SOURCE_KEYS)):
        raise ValueError("workload index is out of range")
    if not 1 <= rounds <= MAX_WORKLOAD_ROUNDS:
        raise ValueError("workload rounds are out of range")
    hashlib.pbkdf2_hmac(
        "sha256",
        f"click-source-{index}".encode("ascii"),
        b"incremental-verification-benchmark",
        rounds,
    )


def _run_source(index: int, rounds: int) -> int:
    started = time.perf_counter_ns()
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            "--workload",
            str(index),
            "--workload-rounds",
            str(rounds),
        ],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    duration_ms = max(1, round((time.perf_counter_ns() - started) / 1_000_000))
    if result.returncode != 0:
        raise RuntimeError(f"benchmark source {index} exited {result.returncode}")
    return duration_ms


def _plan(recent_durations_ms: list[int]) -> dict[str, Any]:
    choices = (
        ("run", "observed-input-changed", "runner", 0),
        (
            "reuse-exact",
            "same-revision-receipt-current",
            "exact-receipt",
            recent_durations_ms[1],
        ),
        (
            "reuse-dependency",
            "observed-dependencies-unchanged",
            "runtime-dependency-observation",
            recent_durations_ms[2],
        ),
        (
            "reuse-safe-change",
            "safe-change-policy-covered",
            "repository-safe-change-policy",
            recent_durations_ms[3],
        ),
    )
    decisions = [
        click_incremental.decision(
            source_key=SOURCE_KEYS[index],
            decision=selected,
            reason_code=reason,
            current_revision=2,
            previous_revision=1,
            check_digest=CHECK_DIGESTS[index],
            authority_source=authority,
            estimated_avoided_ms=avoided,
        )
        for index, (selected, reason, authority, avoided) in enumerate(choices)
    ]
    return click_incremental.build_plan(
        decisions, current_revision=2, planned_at=1
    )


def run_benchmark(
    *,
    iterations: int = DEFAULT_ITERATIONS,
    workload_rounds: int = DEFAULT_WORKLOAD_ROUNDS,
) -> dict[str, Any]:
    if not 1 <= iterations <= MAX_ITERATIONS:
        raise ValueError("iterations are out of range")
    if not 1 <= workload_rounds <= MAX_WORKLOAD_ROUNDS:
        raise ValueError("workload rounds are out of range")

    full_durations: list[int] = []
    incremental_durations: list[int] = []
    plan: dict[str, Any] | None = None
    for _ in range(iterations):
        started = time.perf_counter_ns()
        recent = [
            _run_source(index, workload_rounds)
            for index in range(len(SOURCE_KEYS))
        ]
        full_durations.append(
            max(1, round((time.perf_counter_ns() - started) / 1_000_000))
        )

        plan = _plan(recent)
        selected = click_incremental.keys_to_execute(plan)
        started = time.perf_counter_ns()
        for index, source_key in enumerate(SOURCE_KEYS):
            if source_key in selected:
                _run_source(index, workload_rounds)
        incremental_durations.append(
            max(1, round((time.perf_counter_ns() - started) / 1_000_000))
        )

    assert plan is not None
    result = {
        "version": BENCHMARK_VERSION,
        "fixture": "four-independent-child-process-checks",
        "iterations": iterations,
        "full_verification_duration_ms": round(statistics.median(full_durations)),
        "incremental_verification_duration_ms": round(
            statistics.median(incremental_durations)
        ),
        "total_source_count": plan["total_source_count"],
        "executed_source_count": plan["executed_source_count"],
        "reused_source_count": plan["authoritative_reuse_count"],
        "estimated_avoided_duration_ms": plan["estimated_avoided_ms"],
        "observer_overhead_ms": 0,
        "shadow_contradiction_count": 0,
        "duration_measurement": "wall-clock-measured",
        "estimated_avoided_duration_basis": (
            "most-recent-successful-full-run"
        ),
        "observer_mode": "off",
    }
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument(
        "--workload-rounds", type=int, default=DEFAULT_WORKLOAD_ROUNDS
    )
    parser.add_argument("--workload", type=int, default=None, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.workload is not None:
            _workload(arguments.workload, arguments.workload_rounds)
            return 0
        result = run_benchmark(
            iterations=arguments.iterations,
            workload_rounds=arguments.workload_rounds,
        )
    except (RuntimeError, ValueError) as error:
        print(f"benchmark failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
