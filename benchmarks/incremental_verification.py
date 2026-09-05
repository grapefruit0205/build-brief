#!/usr/bin/env python3
"""Opt-in paired benchmark using real Click hooks, committed policies and runners.

Only the temporary fixture is modified. No receipt, plan decision, dependency
observation or passing ledger is manufactured by this driver.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from hooks import (  # noqa: E402
    click_dashboard_projection,
    click_incremental,
    click_reuse_diagnostics,
)

GATE = ROOT / "hooks" / "click_gate.py"
SCENARIOS = (
    "first-run",
    "unchanged",
    "docs",
    "partial-reuse",
    "code",
    "environment",
    "first-failure",
)
COMPARISONS = ("same-shards", "parent-suite")
DEFAULT_ITERATIONS = 3
DEFAULT_WORKLOAD_ROUNDS = 40_000
MAX_ITERATIONS = 10
MAX_WORKLOAD_ROUNDS = 1_000_000


def comparison_delta(baseline_ms: float, incremental_ms: float) -> dict[str, float | None]:
    delta = baseline_ms - incremental_ms
    return {"delta_ms": delta, "delta_percent": 100 * delta / baseline_ms if baseline_ms > 0 else None}


def distribution(values: list[float]) -> dict[str, float | None]:
    return {"median": statistics.median(values) if values else None,
            "min": min(values) if values else None, "max": max(values) if values else None}


def _split(command: str) -> list[str]:
    if os.name != "nt":
        return shlex.split(command)
    import ctypes
    shell = ctypes.windll.shell32
    shell.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    count = ctypes.c_int()
    args = shell.CommandLineToArgvW(command, ctypes.byref(count))
    if not args:
        raise RuntimeError("runner-command-invalid")
    try:
        return [args[index] for index in range(count.value)]
    finally:
        kernel = ctypes.windll.kernel32
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(ctypes.cast(args, ctypes.c_void_p))


def _fixture_runner_argv(command: str) -> list[str]:
    argv = _split(command)
    if len(argv) == 5 and argv[:2] == ["py", "-3"] and argv[3] == "--encoded-runner":
        # Windows py -3 can select a different Python from the benchmark driver.
        # Keep driver, preflight, and runner on one interpreter; preserve the
        # exact encoded capability for the real runner to authenticate.
        return [sys.executable, *argv[2:]]
    return argv


class Fixture:
    """One independent checkout and lifecycle; no shared receipt across roots."""

    def __init__(
        self,
        directory: Path,
        rounds: int,
        mode: str = "evidence",
        *,
        partial_policy: bool = False,
    ):
        self.root = directory / "repository"
        self.data = directory / "runtime"
        self.root.mkdir(parents=True)
        (self.root / "tests").mkdir()
        (self.root / ".click").mkdir()
        self.environment = {key: value for key, value in os.environ.items()
                            if key not in {"PLUGIN_DATA", "CLICK_CONFIG_HOME", "PLUGIN_ROOT"}
                            and not key.startswith("GIT_")}
        self.environment.update(PLUGIN_DATA=str(self.data), CLICK_CONFIG_HOME=str(self.data),
                                PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_GLOBAL=os.devnull,
                                GIT_CONFIG_NOSYSTEM="1")
        self.event = {"session_id": "efficiency-fixture", "turn_id": "measurement",
                      "cwd": str(self.root), "permission_mode": "default"}
        self.sequence = 0
        self.parent = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q", "-f"]
        self.children = [[sys.executable, "-m", "unittest", f"tests.test_{name}", "-q", "-f"]
                         for name in ("alpha", "beta")]
        self._write(".gitignore", "__pycache__/\n*.pyc\n")
        self._write("README.md", "Benchmark fixture\n")
        self._write("docs-beta.md", "Beta-owned documentation\n")
        self._write("implementation.py", f"ROUNDS = {rounds}\nVALUE = 1\n")
        self._write("tests/__init__.py", "")
        for name in ("alpha", "beta"):
            self._write(f"tests/test_{name}.py",
                        "import hashlib\nimport unittest\nfrom implementation import ROUNDS, VALUE\n"
                        "class Check(unittest.TestCase):\n"
                        "    def test_work(self):\n"
                        "        hashlib.pbkdf2_hmac('sha256', b'click', b'fixture', ROUNDS)\n"
                        "        self.assertEqual(VALUE, 1)\n")
        shards = {"version": 1, "entries": [{
            "checks": [self.parent], "inventory": ["tests/test*.py"],
            "shards": [{"id": name, "checks": [argv], "covers": [f"tests/test_{name}.py"]}
                       for name, argv in zip(("alpha", "beta"), self.children)]}]}
        policy = {
            "version": 1,
            "entries": [
                {
                    "checks": [argv],
                    "reuse_if_only_changed": [
                        "README.md"
                        if not partial_policy or name == "alpha"
                        else "docs-beta.md"
                    ],
                }
                for name, argv in zip(("alpha", "beta"), self.children)
            ],
        }
        self._write(".click/evidence-shards.json", json.dumps(shards))
        self._write(".click/evidence-reuse.json", json.dumps(policy))
        for args in (["git", "init", "-q"], ["git", "add", "."],
                     ["git", "-c", "user.name=Click Benchmark", "-c",
                      "user.email=benchmark@example.invalid", "-c", "commit.gpgsign=false",
                      "commit", "-q", "-m", "Committed benchmark policy and inventory"]):
            if self._run(args).returncode:
                raise RuntimeError("fixture-git-preparation-failed")
        self._hook("prompt-submit", {"hook_event_name": "UserPromptSubmit",
                                    "prompt": "Measure the committed verification fixture in Evidence mode."})
        if mode == "guarded":
            # An isolated integration-test user stages and approves this fixture
            # through the public lifecycle. This is not approval in the user's repo.
            self._hook("prompt-submit", {"hook_event_name": "UserPromptSubmit", "prompt": "@Click\nMeasure only this temporary fixture."})
            self._control("arm")
            contract = {
                "outcome": "measure real verification in the temporary fixture",
                "boundary": {"in_scope": ["temporary fixture checks and fixed changes"], "out_of_scope": ["user repositories"]},
                "must_hold": ["never manufacture passing receipts or skip decisions"],
                "build": {"approach": ["exercise existing hooks and runners"], "semantics": ["preserve verification authority"], "order": ["baseline before change"]},
                "verification": {"scale": "focused", "evidence": [
                    {"id": "E-suite", "kind": "argv", "description": "real fixture checks"},
                    {"id": "E-measure", "kind": "manual", "description": "finish paired measurement after changes"}],
                    "done_when": [{"condition": "fixture checks pass", "primary_evidence": "E-suite"},
                                  {"condition": "paired measurement ends", "primary_evidence": "E-measure"}]},
                "plain_language": "임시 저장소의 실제 검증과 고정된 변경만 측정합니다. 기존 재사용 권한을 유지하며 사용자 저장소를 바꾸거나 영수증을 위조하지 않습니다. 비교 측정이 끝날 때까지 계약을 유지합니다."
            }
            staged = self._control("stage " + shlex.quote(json.dumps(contract)))
            match = re.search(r"ctr_[0-9a-f]{32}", json.dumps(staged))
            if match is None:
                raise RuntimeError("fixture-contract-not-staged")
            self.event["turn_id"] = "measurement-approved"
            self._hook("prompt-submit", {"hook_event_name": "UserPromptSubmit", "prompt": "Approve the staged temporary integration-test contract."})
            self._control("arm")
            approved = self._control("pass " + match.group())
            if approved.get("permissionDecision") == "deny":
                raise RuntimeError("fixture-contract-not-approved")

    def _control(self, command: str) -> dict[str, Any]:
        self.sequence += 1
        return self._hook("pre-tool", {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                          "tool_use_id": f"control-{self.sequence}",
                          "tool_input": {"command": "click-gate " + command}}).get("hookSpecificOutput", {})

    def _write(self, path: str, text: str) -> None:
        (self.root / path).write_text(text, encoding="utf-8")

    def _run(self, argv: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.run(argv, cwd=self.root, env=self.environment, capture_output=True,
                              text=True, check=False, **kwargs)

    def _hook(self, action: str, event: dict[str, Any]) -> dict[str, Any]:
        result = self._run([sys.executable, str(GATE), action], input=json.dumps({**self.event, **event}))
        if result.returncode:
            raise RuntimeError("fixture-hook-failed")
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def state(self) -> dict[str, Any]:
        paths = list((self.data / "gate-state").glob("session-contract-*.json"))
        paths = [path for path in paths if not path.name.endswith(".efficiency.json")]
        if len(paths) != 1:
            raise RuntimeError("fixture-state-unavailable")
        return json.loads(paths[0].read_text(encoding="utf-8"))

    def change(self, scenario: str) -> None:
        if scenario in {"first-run", "unchanged"}:
            return
        if scenario == "environment":
            self.environment["CLICK_BENCHMARK_VARIANT"] = "changed"
            return
        if scenario == "partial-reuse" and self.state().get("runtime_mode") == "evidence":
            # Exercise the real completed-Evidence -> next-Evidence lifecycle.
            # No receipt, source status, or plan decision is manufactured here.
            self.event["turn_id"] = f"measurement-successor-{self.sequence + 1}"
            self._hook(
                "prompt-submit",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "prompt": "Measure a follow-up Evidence task after the baseline.",
                },
            )
        self.sequence += 1
        event = {"tool_name": "apply_patch", "tool_use_id": f"change-{self.sequence}",
                 "tool_input": {"patch": "*** benchmark fixture mutation ***"}}
        admission = self._hook("pre-tool", {**event, "hook_event_name": "PreToolUse"})
        if admission.get("hookSpecificOutput", {}).get("permissionDecision") == "deny":
            raise RuntimeError("fixture-mutation-rejected")
        if scenario in {"docs", "partial-reuse"}:
            self._write("README.md", "Documentation changed by the fixture.\n")
        elif scenario == "code":
            with (self.root / "implementation.py").open("a", encoding="utf-8") as handle:
                handle.write("# Code change outside the safe documentation policy.\n")
        elif scenario == "first-failure":
            self._write("tests/test_alpha.py",
                        "import unittest\nclass Check(unittest.TestCase):\n"
                        "    def test_work(self):\n        self.fail('fixture failure')\n")
        self._hook("post-tool", {**event, "hook_event_name": "PostToolUse",
                                "tool_response": {"success": True, "exit_code": 0}})

    def verify(self) -> dict[str, Any]:
        self.sequence += 1
        batch = {"version": 2, "workdir": str(self.root),
                 "checks": [{"evidence_id": "E-suite", "argv": self.parent, "class": "broad"}]}
        event = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                 "tool_use_id": f"verify-{self.sequence}",
                 "tool_input": {"command": "click-gate verify " + shlex.quote(json.dumps(batch))}}
        started = time.perf_counter_ns()
        response = self._hook("pre-tool", event).get("hookSpecificOutput", {})
        if response.get("permissionDecision") == "deny":
            code = 2
        else:
            command = response.get("updatedInput", {}).get("command")
            if not isinstance(command, str):
                raise RuntimeError("fixture-runner-not-issued")
            argv = _fixture_runner_argv(command)
            if argv and argv[0] == "echo":
                code = 0  # Actual preflight has applied reuse; no runner to dispatch.
            else:
                if "--encoded-runner" not in argv and "run-verification" not in argv:
                    raise RuntimeError("fixture-unexpected-runner")
                code = self._run(argv).returncode
        wall_ms = (time.perf_counter_ns() - started) / 1_000_000
        state = self.state()
        measured = click_incremental.current_batch(state.get("verification"))
        if measured is None:
            raise RuntimeError("fixture-measurement-unavailable")
        summary = click_incremental.batch_summary(measured)
        return {"wall_ms": wall_ms, "exit_code": code, "status": measured["status"],
                "executed_source_count": summary["executed_source_count"],
                "reused_source_count": summary["authoritative_reuse_count"],
                "not_run_source_count": summary["not_run_source_count"],
                "estimated_avoided_ms": summary["estimated_avoided_ms"],
                "estimated_source_count": summary["estimated_source_count"],
                "request_measurement_scope": "driver-preflight-through-runner-return",
                "batch": measured, "snapshot": click_dashboard_projection.dashboard_projection(state)}

    def full(self, comparison: str) -> dict[str, Any]:
        commands = self.children if comparison == "same-shards" else [self.parent]
        started = time.perf_counter_ns()
        code, executed = 0, 0
        for argv in commands:
            code = self._run(argv).returncode
            executed += 1
            if code:
                break
        return {"wall_ms": (time.perf_counter_ns() - started) / 1_000_000, "exit_code": code,
                "status": "passed" if code == 0 else "failed",
                "executed_source_count": executed, "reused_source_count": 0,
                "not_run_source_count": len(commands) - executed, "grouping": comparison,
                "request_measurement_scope": "driver-command-dispatch-through-return"}


def run_benchmark(*, iterations: int = DEFAULT_ITERATIONS, warmups: int = 1,
                  workload_rounds: int = DEFAULT_WORKLOAD_ROUNDS,
                  mode: str = "evidence",
                  scenarios: tuple[str, ...] = SCENARIOS) -> dict[str, Any]:
    if not 1 <= iterations <= MAX_ITERATIONS or not 0 <= warmups <= MAX_ITERATIONS:
        raise ValueError("invalid-repetition-count")
    if mode not in {"evidence", "guarded"} or not 1 <= workload_rounds <= MAX_WORKLOAD_ROUNDS or not scenarios or set(scenarios) - set(SCENARIOS):
        raise ValueError("invalid-fixture-configuration")
    samples = []
    latest_snapshot = None
    for scenario in scenarios:
        for comparison in COMPARISONS:
            for index in range(warmups + iterations):
                with tempfile.TemporaryDirectory(prefix="click-efficiency-") as directory:
                    arms = {name: Fixture(
                                Path(directory) / name,
                                workload_rounds,
                                mode,
                                partial_policy=scenario == "partial-reuse",
                            )
                            for name in ("baseline", "incremental")}
                    for arm in arms.values():
                        if scenario != "first-run":
                            if arm.verify()["status"] != "passed":
                                raise RuntimeError("fixture-baseline-failed")
                        arm.change(scenario)
                    order = ["baseline", "incremental"] if index % 2 == 0 else ["incremental", "baseline"]
                    results = {}
                    for name in order:
                        results[name] = arms[name].verify() if name == "incremental" else arms[name].full(comparison)
                    latest_snapshot = results["incremental"].pop("snapshot")
                    successful = all(item["status"] == "passed" for item in results.values())
                    samples.append({"scenario": scenario, "comparison": comparison,
                                    "iteration": index, "warmup": index < warmups, "order": order,
                                    "eligible": successful and index >= warmups,
                                    "excluded_reason": "warmup" if index < warmups else "" if successful else "verification-not-passed",
                                    **results, **comparison_delta(results["baseline"]["wall_ms"], results["incremental"]["wall_ms"])})
    summaries = []
    for scenario in scenarios:
        for comparison in COMPARISONS:
            selected = [sample for sample in samples if sample["scenario"] == scenario and
                        sample["comparison"] == comparison and sample["eligible"]]
            summaries.append({"scenario": scenario, "comparison": comparison, "samples": len(selected),
                              "baseline_wall_ms": distribution([item["baseline"]["wall_ms"] for item in selected]),
                              "incremental_wall_ms": distribution([item["incremental"]["wall_ms"] for item in selected]),
                              "delta_ms": distribution([item["delta_ms"] for item in selected]),
                              "delta_percent": distribution([item["delta_percent"] for item in selected if item["delta_percent"] is not None])})
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False)
    version = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    source_hash = hashlib.sha256()
    for path in sorted([*GATE.parent.glob("*.py"), Path(__file__).resolve()]):
        source_hash.update(path.relative_to(ROOT).as_posix().encode() + b"\0")
        source_hash.update(hashlib.sha256(path.read_bytes()).digest())
    reuse_diagnostics = click_reuse_diagnostics.aggregate(
        sample["incremental"]["batch"] for sample in samples
    )
    return {"version": 2, "kind": "click-paired-verification-benchmark",
            "engine": {"version": version, "commit": commit.stdout.strip() if commit.returncode == 0 else None,
                       "source_digest": source_hash.hexdigest(),
                       "working_tree_modified": bool(dirty.stdout.strip())},
            "environment": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
            "conditions": {"iterations": iterations, "warmups": warmups, "workload_rounds": workload_rounds,
                           "scope": ["alpha", "beta"], "scope_equivalence": "same-two-unittest-files",
                           "cache": "fresh-checkout-per-arm-and-pair; baseline-warmed-except-first-run; OS-cache-not-flushed; bytecode-disabled",
                           "order": "alternating-pair-order", "observer": "off", "runtime_mode": mode,
                           "authority": "real-hooks-and-one-use-runner",
                           "parent_group_count": 1, "shard_group_count": 2},
            "samples": samples, "summaries": summaries, "dashboard_snapshot": latest_snapshot,
            "reuse_diagnostics": reuse_diagnostics,
            "observer_overhead_ms": 0, "shadow_contradiction_count": 0,
            "limitations": ["temporary-fixture-not-general-product-performance", "no-authoritative-native-dependency-observation",
                            "different-checkout-roots-have-independent-receipts", "OS-cache-and-scheduler-uncontrolled"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--workload-rounds", type=int, default=DEFAULT_WORKLOAD_ROUNDS)
    parser.add_argument("--scenario", action="append", choices=SCENARIOS)
    parser.add_argument("--mode", choices=("evidence", "guarded"), default="evidence")
    parser.add_argument("--output", type=Path, help="Write a new local JSON file (never overwrite).")
    args = parser.parse_args(argv)
    try:
        result = run_benchmark(iterations=args.iterations, warmups=args.warmups,
                               workload_rounds=args.workload_rounds, scenarios=tuple(args.scenario or SCENARIOS), mode=args.mode)
        # JSON escapes preserve Unicode values on legacy Windows stdout,
        # while explicitly UTF-8 output files remain human-readable.
        encoded = json.dumps(result, ensure_ascii=args.output is None,
                             sort_keys=True, allow_nan=False)
        if args.output:
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
            print(json.dumps({"output": str(args.output), "samples": len(result["samples"]), "summaries": result["summaries"]}))
        else:
            print(encoded)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"benchmark failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
