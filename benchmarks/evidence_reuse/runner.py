"""Run the deterministic, LLM-free evidence-reuse safety benchmark."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable, Sequence

from hooks import (
    click_dependency_cache,
    click_evidence,
    click_host_coverage,
    click_verification,
)

from .manifests import MANIFEST_VARIANTS, ManifestVariant, dependency_patterns
from .profiles import PROFILES_BY_NAME, FixtureProfile
from .runtime_observations import (
    OBSERVATION_SOURCE,
    capture_baseline_observation,
)
from .scenarios import (
    C_NATIVE,
    JAVA_JDK,
    MUTATIONS,
    NODE_CJS,
    NODE_ESM,
    PYTHON_PACKAGE,
    PYTHON_SERVICE,
    SemanticMutation,
)


DECISION_ENGINE = "hooks.click_verification.dependency_receipt_matches"
CONTRACT_DIGEST = hashlib.sha256(b"evidence-reuse-semantic-benchmark-v1").hexdigest()
HOST_COVERAGE = click_host_coverage.receipt("codex")
JAVA_IMAGE_TAG = "eclipse-temurin:21-jdk-alpine"
JAVA_IMAGE = (
    "eclipse-temurin:21-jdk-alpine@"
    "sha256:6ea5548706b60ac0a602eaf48af74792cbab012d90e811ca8db6184b16b5c3d6"
)


@dataclass(frozen=True)
class RuntimeTools:
    python: str
    node: str = ""
    gcc: str = ""
    javac: str = ""
    java: str = ""
    docker: str = ""
    java_backend: str = ""
    versions: tuple[tuple[str, str], ...] = ()

    def version_dict(self) -> dict[str, str]:
        return dict(self.versions)


@dataclass(frozen=True)
class RerunResult:
    ran: bool
    passed: bool
    exit_code: int
    failed_check: int | None = None


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    profile: str
    profile_name: str
    language: str
    mutation_name: str
    semantic_class: str
    component: str
    manifest_variant: str
    manifest_description: str
    oracle_reuse_safe: bool
    oracle_expected_rerun_pass: bool
    oracle_reason: str
    decision_reuse: bool
    decision_source: str
    actual_rerun: RerunResult
    baseline_passed: bool
    observation_complete: bool
    observed_dependency_count: int

    @property
    def correct_reuse(self) -> bool:
        return self.oracle_reuse_safe and self.decision_reuse

    @property
    def correct_invalidation(self) -> bool:
        return not self.oracle_reuse_safe and not self.decision_reuse

    @property
    def unsafe_reuse(self) -> bool:
        return not self.oracle_reuse_safe and self.decision_reuse

    @property
    def over_conservative_rerun(self) -> bool:
        return self.oracle_reuse_safe and not self.decision_reuse

    @property
    def decision_correct(self) -> bool:
        return self.correct_reuse or self.correct_invalidation

    @property
    def rerun_matches_oracle(self) -> bool:
        return self.actual_rerun.passed == self.oracle_expected_rerun_pass


def _metrics(cases: Iterable[CaseResult]) -> dict[str, Any]:
    selected = tuple(cases)
    total = len(selected)
    correct_reuse = sum(case.correct_reuse for case in selected)
    correct_invalidation = sum(case.correct_invalidation for case in selected)
    correct = correct_reuse + correct_invalidation
    reuse_safe = sum(case.oracle_reuse_safe for case in selected)
    must_rerun = total - reuse_safe
    return {
        "total_cases": total,
        "decision_correct": correct,
        "decision_accuracy_percent": (
            round(100.0 * correct / total, 1) if total else 0.0
        ),
        "oracle_reuse_safe": reuse_safe,
        "oracle_must_rerun": must_rerun,
        "correct_reuse": correct_reuse,
        "correct_invalidation": correct_invalidation,
        "must_rerun_protection_percent": (
            round(100.0 * correct_invalidation / must_rerun, 1)
            if must_rerun
            else 100.0
        ),
        "safe_reuse_capture_percent": (
            round(100.0 * correct_reuse / reuse_safe, 1)
            if reuse_safe
            else 100.0
        ),
        "unsafe_reuse": sum(case.unsafe_reuse for case in selected),
        "over_conservative_rerun": sum(
            case.over_conservative_rerun for case in selected
        ),
        "shadow_rerun_pass": sum(case.actual_rerun.passed for case in selected),
        "shadow_rerun_fail": sum(not case.actual_rerun.passed for case in selected),
        "oracle_rerun_mismatch": sum(
            not case.rerun_matches_oracle for case in selected
        ),
        "complete_observations": sum(case.observation_complete for case in selected),
    }


@dataclass(frozen=True)
class BenchmarkReport:
    cases: tuple[CaseResult, ...]
    toolchains: tuple[tuple[str, str], ...]

    @property
    def summary(self) -> dict[str, Any]:
        return _metrics(self.cases)

    @property
    def total_cases(self) -> int:
        return len(self.cases)

    @property
    def correct_reuse(self) -> int:
        return int(self.summary["correct_reuse"])

    @property
    def correct_invalidation(self) -> int:
        return int(self.summary["correct_invalidation"])

    @property
    def unsafe_reuse(self) -> int:
        return int(self.summary["unsafe_reuse"])

    @property
    def over_conservative_rerun(self) -> int:
        return int(self.summary["over_conservative_rerun"])

    @property
    def shadow_rerun_pass(self) -> int:
        return int(self.summary["shadow_rerun_pass"])

    @property
    def shadow_rerun_fail(self) -> int:
        return int(self.summary["shadow_rerun_fail"])

    def _grouped(self, attribute: str) -> dict[str, dict[str, Any]]:
        names = sorted({str(getattr(case, attribute)) for case in self.cases})
        return {
            name: _metrics(
                case for case in self.cases if str(getattr(case, attribute)) == name
            )
            for name in names
        }

    def to_dict(self) -> dict[str, Any]:
        summary = self.summary
        return {
            **summary,
            "decision_engine": DECISION_ENGINE,
            "observation_source": OBSERVATION_SOURCE,
            "toolchains": dict(self.toolchains),
            "exact_manifest_baseline": _metrics(
                case for case in self.cases if case.manifest_variant == "exact"
            ),
            "by_manifest": self._grouped("manifest_variant"),
            "by_language": self._grouped("language"),
            "by_profile": self._grouped("profile"),
            "by_semantic_class": self._grouped("semantic_class"),
            "cases": [
                {
                    "case_id": case.case_id,
                    "profile": case.profile,
                    "profile_name": case.profile_name,
                    "language": case.language,
                    "mutation": case.mutation_name,
                    "manifest": {
                        "variant": case.manifest_variant,
                        "description": case.manifest_description,
                    },
                    "oracle": {
                        "reuse_safe": case.oracle_reuse_safe,
                        "expected_rerun_pass": case.oracle_expected_rerun_pass,
                        "semantic_class": case.semantic_class,
                        "component": case.component,
                        "reason": case.oracle_reason,
                    },
                    "decision": {
                        "reuse": case.decision_reuse,
                        "correct": case.decision_correct,
                        "source": case.decision_source,
                    },
                    "actual_rerun": asdict(case.actual_rerun),
                    "actual_rerun_matches_oracle": case.rerun_matches_oracle,
                    "baseline_passed": case.baseline_passed,
                    "baseline_observation": {
                        "complete": case.observation_complete,
                        "dependency_count": case.observed_dependency_count,
                        "source": OBSERVATION_SOURCE,
                    },
                }
                for case in self.cases
            ],
        }

    def text(self) -> str:
        overall = self.summary
        selected_manifest_variants = {case.manifest_variant for case in self.cases}
        languages = sorted({case.language for case in self.cases})
        profile_count = len({case.profile for case in self.cases})
        exact = _metrics(
            case for case in self.cases if case.manifest_variant == "exact"
        )
        incomplete = _metrics(
            case for case in self.cases if case.manifest_variant == "incomplete"
        )
        resilient_stress = _metrics(
            case
            for case in self.cases
            if case.manifest_variant in {"broad", "malformed", "uncommitted"}
        )
        manifest_rows = []
        for name, values in self._grouped("manifest_variant").items():
            manifest_rows.append(
                (
                    name,
                    str(values["total_cases"]),
                    f'{values["decision_correct"]}/{values["total_cases"]}',
                    str(values["unsafe_reuse"]),
                    str(values["over_conservative_rerun"]),
                )
            )
        profile_rows = []
        for name, values in self._grouped("profile").items():
            profile_rows.append(
                (
                    name,
                    str(values["total_cases"]),
                    f'{values["decision_accuracy_percent"]:.1f}%',
                    str(values["unsafe_reuse"]),
                    str(values["over_conservative_rerun"]),
                )
            )
        matrix_heading = (
            "Stress matrix: includes deliberately broad, incomplete, changed, and malformed working-tree manifests"
            if selected_manifest_variants
            == {variant.name for variant in MANIFEST_VARIANTS}
            else "Selected benchmark cases"
        )
        plain_result = ["Plain-language result"]
        if exact["total_cases"]:
            plain_result.append(
                f"  With a complete, narrow map: {exact['decision_correct']}/{exact['total_cases']} decisions were correct; {exact['unsafe_reuse']} were unsafe."
            )
        if incomplete["total_cases"]:
            if incomplete["unsafe_reuse"]:
                plain_result.append(
                    f"  With a silently incomplete map: {incomplete['unsafe_reuse']} relevant changes incorrectly reused old evidence."
                )
            else:
                plain_result.append(
                    "  With a silently incomplete map: complete baseline observations caught every omitted runtime dependency."
                )
        if resilient_stress["total_cases"]:
            plain_result.append(
                f"  Complete observations handled broad maps and non-authoritative working-tree manifest edits with {resilient_stress['unsafe_reuse']} unsafe reuses and {resilient_stress['over_conservative_rerun']} extra reruns."
            )
        clean_section = []
        if exact["total_cases"]:
            clean_section = [
                "Clean baseline: complete and narrow manifests",
                f"  Correct decisions: {exact['decision_correct']}/{exact['total_cases']} ({exact['decision_accuracy_percent']:.1f}%)",
                f"  Unsafe reuse: {exact['unsafe_reuse']}",
                f"  Unnecessary reruns: {exact['over_conservative_rerun']}",
                "",
            ]
        lines = [
            "Click evidence-reuse safety benchmark",
            "",
            f"Tested {overall['total_cases']} controlled cases across {profile_count} fixture repositories",
            f"and {len(languages)} languages/runtimes: {', '.join(languages)}.",
            "The semantic oracle was defined independently from Click's manifest rules.",
            f"Baseline dependencies came from {OBSERVATION_SOURCE}, independently of case labels.",
            "",
            *clean_section,
            matrix_heading,
            f"  Correct decisions: {overall['decision_correct']}/{overall['total_cases']} ({overall['decision_accuracy_percent']:.1f}%)",
            "",
            "Safety result",
            f"  Relevant changes correctly rerun: {overall['correct_invalidation']}/{overall['oracle_must_rerun']} ({overall['must_rerun_protection_percent']:.1f}%)",
            f"  Unsafe old-result reuse: {overall['unsafe_reuse']}",
            "",
            "Reuse efficiency",
            f"  Safe reuse opportunities taken: {overall['correct_reuse']}/{overall['oracle_reuse_safe']} ({overall['safe_reuse_capture_percent']:.1f}%)",
            f"  Safe but unnecessary reruns: {overall['over_conservative_rerun']}",
            "",
            "Decision counts",
            f"  Correct reuse: {overall['correct_reuse']}",
            f"  Correct invalidation: {overall['correct_invalidation']}",
            f"  Unsafe reuse: {overall['unsafe_reuse']}",
            f"  Unnecessary reruns: {overall['over_conservative_rerun']}",
            "",
            *plain_result,
            "",
            _table(
                ("manifest", "cases", "correct", "unsafe", "extra reruns"),
                manifest_rows,
            ),
            "",
            _table(
                ("runtime fixture", "cases", "accuracy", "unsafe", "extra reruns"),
                profile_rows,
            ),
            "",
            "Shadow rerun cross-check",
            f"  Passed: {overall['shadow_rerun_pass']}",
            f"  Failed: {overall['shadow_rerun_fail']}",
            f"  Unexpected outcomes: {overall['oracle_rerun_mismatch']}",
            f"  Complete baseline observations: {overall['complete_observations']}/{overall['total_cases']}",
            "",
            "How to read this",
            "  Unsafe reuse means Click trusted old evidence after a semantic dependency changed.",
            "  An unnecessary rerun is safe, but loses performance.",
            "  Incomplete manifests are deliberately missing real dependencies; their row measures",
            "  the authority-boundary risk, not just implementation conformance.",
            "  Only the committed manifest is policy authority; working-tree edits cannot narrow it.",
            "  Complete observations refine expanding manifest patterns to inputs actually consumed.",
            "  These are controlled synthetic cases, not 500 independent production projects.",
        ]
        return "\n".join(lines)


def _table(headers: tuple[str, ...], rows: Sequence[tuple[str, ...]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    rendered = [
        "  "
        + "  ".join(value.ljust(widths[index]) for index, value in enumerate(headers)),
        "  " + "  ".join("-" * width for width in widths),
    ]
    rendered.extend(
        "  " + "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    return "\n".join(rendered)


@dataclass(frozen=True)
class _Baseline:
    snapshot: Path
    tree_digest: str
    dependency_receipt: dict[str, Any]
    dependency_observation: dict[str, Any]
    environment_digest: str


def _capture_first_line(argv: list[str]) -> str:
    result = subprocess.run(
        argv, capture_output=True, text=True, check=False, timeout=30
    )
    output = (result.stdout + result.stderr).strip().splitlines()
    return output[0] if output else "unknown"


def _resolve_tools(
    profile_names: set[str], *, allow_java_pull: bool = False
) -> RuntimeTools:
    python = str(Path(sys.executable).resolve())
    node = shutil.which("node") or ""
    gcc = shutil.which("gcc") or ""
    javac = shutil.which("javac") or ""
    java = shutil.which("java") or ""
    docker = shutil.which("docker") or ""
    versions: dict[str, str] = {"python": _capture_first_line([python, "--version"])}

    if {NODE_CJS, NODE_ESM} & profile_names:
        if not node:
            raise RuntimeError(
                "Node.js is required for the selected benchmark profiles"
            )
        versions["node"] = _capture_first_line([node, "--version"])
    if C_NATIVE in profile_names:
        if not gcc:
            raise RuntimeError("GCC is required for the C benchmark profile")
        versions["gcc"] = _capture_first_line([gcc, "--version"])

    java_backend = ""
    if JAVA_JDK in profile_names:
        if javac and java:
            java_backend = "native-jdk"
            versions["java"] = _capture_first_line([java, "-version"])
        elif docker:
            inspect = subprocess.run(
                [docker, "image", "inspect", JAVA_IMAGE],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if inspect.returncode != 0 and allow_java_pull:
                pulled = subprocess.run(
                    [docker, "pull", JAVA_IMAGE],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=300,
                )
                if pulled.returncode != 0:
                    raise RuntimeError(
                        f"could not pull the pinned Java image: {pulled.stderr.strip()}"
                    )
                inspect = subprocess.run(
                    [docker, "image", "inspect", JAVA_IMAGE],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
            if inspect.returncode != 0:
                raise RuntimeError(
                    "Java requires javac/java or the pinned Docker image; run with "
                    "--pull-java-image to fetch it"
                )
            java_backend = "docker-temurin-21"
            versions["java"] = f"Temurin JDK 21 ({JAVA_IMAGE.split('@', 1)[1]})"
            versions["docker"] = _capture_first_line([docker, "--version"])
        else:
            raise RuntimeError("Java requires javac/java or Docker")
    return RuntimeTools(
        python=python,
        node=node,
        gcc=gcc,
        javac=javac,
        java=java,
        docker=docker,
        java_backend=java_backend,
        versions=tuple(sorted(versions.items())),
    )


def runtime_available() -> tuple[bool, str]:
    try:
        _resolve_tools(set(PROFILES_BY_NAME))
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        return False, str(error)
    return True, ""


def _checks(
    profile: FixtureProfile,
    root: Path,
    tools: RuntimeTools,
    *,
    java_container: str = "",
) -> list[dict[str, Any]]:
    def check(argv: list[str]) -> dict[str, Any]:
        return {"evidence_id": profile.evidence_id, "argv": argv, "class": "targeted"}

    if profile.runtime_kind in {"python-service", "python-package"}:
        return [
            check(
                [
                    tools.python,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-q",
                ]
            )
        ]
    if profile.runtime_kind == "node-cjs":
        return [check([tools.node, "--test", "tests/app.test.cjs"])]
    if profile.runtime_kind == "node-esm":
        return [check([tools.node, "--test", "tests/app.test.mjs"])]
    if profile.runtime_kind == "c-gcc":
        test_binary = "build/test_app.exe" if os.name == "nt" else "./build/test_app"
        return [
            check(
                [
                    tools.gcc,
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Iinclude",
                    "src/app.c",
                    "src/shared.c",
                    "tests/test_app.c",
                    "-lm",
                    "-o",
                    test_binary,
                ]
            ),
            check([test_binary]),
        ]
    if profile.runtime_kind == "java-jdk" and tools.java_backend == "native-jdk":
        return [
            check(
                [
                    tools.javac,
                    "-d",
                    "build",
                    "src/App.java",
                    "src/Shared.java",
                    "src/Config.java",
                    "tests/AppTest.java",
                ]
            ),
            check([tools.java, "-cp", "build", "AppTest"]),
        ]
    if profile.runtime_kind == "java-jdk" and tools.java_backend == "docker-temurin-21":
        if not java_container:
            raise RuntimeError("the Java benchmark container is not running")
        container_root = f"/benchmark/{profile.name}/current"
        return [
            check(
                [
                    tools.docker,
                    "exec",
                    "--env",
                    "CLICK_BENCH_MODE",
                    "--workdir",
                    container_root,
                    java_container,
                    "sh",
                    f"{container_root}/tools/run-tests.sh",
                ]
            ),
        ]
    raise RuntimeError(f"unsupported runtime profile: {profile.runtime_kind}")


def _run_git(root: Path, *arguments: str) -> None:
    result = subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")


def _start_java_container(workspace: Path, tools: RuntimeTools) -> str:
    name_suffix = hashlib.sha256(str(workspace).encode()).hexdigest()[:10]
    image_suffix = JAVA_IMAGE.rsplit(":", 1)[-1][:10]
    name = f"click-evidence-java-{image_suffix}-{os.getpid()}-{name_suffix}"
    mount = f"type=bind,src={workspace.resolve()},dst=/benchmark"
    result = subprocess.run(
        [
            tools.docker,
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--network",
            "none",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--mount",
            mount,
            JAVA_IMAGE,
            "tail",
            "-f",
            "/dev/null",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"could not start the Java benchmark container: {result.stderr.strip()}"
        )
    return name


def _stop_java_container(name: str, tools: RuntimeTools) -> None:
    if not name:
        return
    subprocess.run(
        [tools.docker, "stop", "--time", "1", name],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


def _git_capture(root: Path, arguments: list[str]) -> bytes | None:
    return click_verification.git_capture(root, arguments)


def _environment(
    root: Path, mutation: SemanticMutation | None = None
) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PWD"] = str(root.resolve())
    environment["CLICK_BENCH_MODE"] = "test"
    if mutation is not None:
        environment.update(dict(mutation.environment))
    return environment


def _run_checks(
    root: Path, checks: list[dict[str, Any]], environment: dict[str, str]
) -> tuple[RerunResult, str]:
    (root / "build").mkdir(exist_ok=True)
    for index, check in enumerate(checks):
        try:
            result = subprocess.run(
                check["argv"],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=45,
            )
        except subprocess.TimeoutExpired as error:
            output = "\n".join(filter(None, (error.stdout or "", error.stderr or "")))
            return RerunResult(True, False, 124, index), output[-4000:]
        if result.returncode != 0:
            output = (result.stdout + result.stderr)[-4000:]
            return RerunResult(True, False, result.returncode, index), output
    return RerunResult(True, True, 0, None), ""


def _write_manifest(
    root: Path, checks: list[dict[str, Any]], patterns: tuple[str, ...]
) -> None:
    manifest = {
        "version": 1,
        "entries": [
            {
                "checks": [list(check["argv"]) for check in checks],
                "paths": list(patterns),
            }
        ],
    }
    path = root / ".click" / "evidence-dependencies.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _copy_fixture(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "build"),
    )


def _remove_tree(path: Path) -> None:
    """Remove copied Git trees despite read-only files and short-lived races."""

    if not path.exists():
        return

    def make_writable_and_retry(function: Any, target: str, error: Any) -> None:
        exception = error[1]
        if isinstance(exception, FileNotFoundError):
            return
        if not isinstance(exception, PermissionError):
            raise exception
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        function(target)

    retryable = {errno.EACCES, errno.ENOTEMPTY, errno.EPERM}
    for attempt in range(6):
        try:
            shutil.rmtree(path, onerror=make_writable_and_retry)
            return
        except FileNotFoundError:
            return
        except OSError as error:
            if attempt == 5 or error.errno not in retryable:
                raise
            time.sleep(0.025 * (2**attempt))


def _create_baseline(
    profile: FixtureProfile,
    root: Path,
    snapshot: Path,
    checks: list[dict[str, Any]],
    variant: ManifestVariant,
) -> _Baseline:
    if root.exists():
        _remove_tree(root)
    if snapshot.exists():
        _remove_tree(snapshot)
    _copy_fixture(profile.fixture_template, root)
    patterns = dependency_patterns(
        variant,
        exact=profile.exact_dependencies,
        incomplete=profile.incomplete_dependencies,
    )
    _write_manifest(root, checks, patterns)
    _run_git(root, "init", "--quiet")
    _run_git(root, "config", "gc.auto", "0")
    _run_git(root, "add", "-A")
    _run_git(
        root,
        "-c",
        "user.name=Click Benchmark",
        "-c",
        "user.email=click-benchmark@example.invalid",
        "commit",
        "--quiet",
        "-m",
        f"baseline-{variant.baseline_policy}",
    )
    environment = _environment(root)
    baseline_run, output = _run_checks(root, checks, environment)
    if not baseline_run.passed:
        raise RuntimeError(
            f"baseline {profile.name}/{variant.baseline_policy} failed:\n{output}"
        )
    tree = click_verification.git_workspace_snapshot(root)
    if tree is None:
        raise RuntimeError(f"could not snapshot baseline fixture: {profile.name}")
    observation = capture_baseline_observation(
        profile.name,
        root,
        baseline_passed=baseline_run.passed,
    )
    receipts = click_dependency_cache.receipts_for_groups(
        root,
        {"source": checks},
        observations={"source": observation},
        git_capture=_git_capture,
    )
    receipt = receipts.get("source")
    if receipt is None:
        raise RuntimeError(
            f"baseline dependency receipt unavailable: {profile.name}/{variant.baseline_policy}"
        )
    environment_digest = click_verification.environment_digest(
        checks, cwd=root, environment=environment
    )
    if not environment_digest:
        raise RuntimeError(f"could not fingerprint runtime: {profile.name}")
    shutil.copytree(root, snapshot)
    return _Baseline(
        snapshot,
        str(tree["digest"]),
        receipt,
        observation,
        environment_digest,
    )


def _apply_mutation(root: Path, mutation: SemanticMutation) -> None:
    if mutation.operation == "environment":
        return
    path = root / mutation.path
    if mutation.operation == "append":
        path.write_text(
            path.read_text(encoding="utf-8") + mutation.value, encoding="utf-8"
        )
    elif mutation.operation == "replace":
        content = path.read_text(encoding="utf-8")
        if mutation.old not in content:
            raise RuntimeError(f"mutation text not found: {mutation.mutation_id}")
        path.write_text(
            content.replace(mutation.old, mutation.new, 1), encoding="utf-8"
        )
    elif mutation.operation == "write":
        path.write_text(mutation.value, encoding="utf-8")
    elif mutation.operation == "delete":
        path.unlink()
    else:
        raise RuntimeError(f"unknown mutation operation: {mutation.operation}")


def _apply_manifest_post_mutation(root: Path, variant: ManifestVariant) -> None:
    path = root / ".click" / "evidence-dependencies.json"
    if variant.post_mutation == "none":
        return
    if variant.post_mutation == "append_whitespace":
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        return
    if variant.post_mutation == "malformed_json":
        path.write_text("{not-json\n", encoding="utf-8")
        return
    raise RuntimeError(f"unknown manifest post-mutation: {variant.post_mutation}")


def _source(
    profile: FixtureProfile,
    root: Path,
    checks: list[dict[str, Any]],
    baseline: _Baseline,
) -> tuple[dict[str, Any], str]:
    state = click_evidence.fresh_state(
        {"verification": {"evidence": [{"id": profile.evidence_id, "kind": "argv"}]}}
    )
    source = state["sources"][click_evidence.evidence_key(profile.evidence_id)]
    group_digest = click_verification.group_digest(checks)
    source.update(
        {
            "status": "stale",
            "verified_revision": 0,
            "verified_contract_digest": CONTRACT_DIGEST,
            "verified_check_digest": group_digest,
            "verified_root": str(root.resolve()),
            "verified_tree_digest": baseline.tree_digest,
            "verified_environment_digest": baseline.environment_digest,
            "verified_executable_digest": hashlib.sha256(
                json.dumps([check["argv"] for check in checks]).encode()
            ).hexdigest(),
            "verified_host_coverage": HOST_COVERAGE,
            "verified_at": 1,
        }
    )
    click_verification.store_dependency_receipt(source, baseline.dependency_receipt)
    return source, group_digest


def _evaluate_case(
    profile: FixtureProfile,
    root: Path,
    checks: list[dict[str, Any]],
    baseline: _Baseline,
    mutation: SemanticMutation,
    variant: ManifestVariant,
) -> CaseResult:
    if root.exists():
        _remove_tree(root)
    shutil.copytree(baseline.snapshot, root)
    _apply_mutation(root, mutation)
    _apply_manifest_post_mutation(root, variant)
    environment = _environment(root, mutation)
    source, group_digest = _source(profile, root, checks, baseline)
    current_receipt = click_dependency_cache.receipts_for_groups(
        root,
        {"source": checks},
        observations={"source": baseline.dependency_observation},
        git_capture=_git_capture,
    ).get("source")
    environment_digest = click_verification.environment_digest(
        checks, cwd=root, environment=environment
    )
    decision_reuse = click_verification.dependency_receipt_matches(
        source,
        current_receipt,
        contract_digest=CONTRACT_DIGEST,
        revision=1,
        group_digest=group_digest,
        git_root=str(root.resolve()),
        environment_digest=environment_digest,
        host_coverage=HOST_COVERAGE,
    )
    actual_rerun, _output = _run_checks(root, checks, environment)
    return CaseResult(
        case_id=f"{mutation.mutation_id}/{variant.name}",
        profile=profile.name,
        profile_name=profile.display_name,
        language=profile.language,
        mutation_name=mutation.name,
        semantic_class=mutation.semantic_class,
        component=mutation.component,
        manifest_variant=variant.name,
        manifest_description=variant.description,
        oracle_reuse_safe=mutation.oracle_reuse_safe,
        oracle_expected_rerun_pass=mutation.expected_rerun_pass,
        oracle_reason=mutation.oracle_reason,
        decision_reuse=decision_reuse,
        decision_source=DECISION_ENGINE,
        actual_rerun=actual_rerun,
        baseline_passed=True,
        observation_complete=(
            click_dependency_cache.dependency_observation_is_complete(
                baseline.dependency_observation
            )
        ),
        observed_dependency_count=len(baseline.dependency_observation["paths"]),
    )


def run_benchmark(
    mutations: Sequence[SemanticMutation] = MUTATIONS,
    manifest_variants: Sequence[ManifestVariant] = MANIFEST_VARIANTS,
    *,
    allow_java_pull: bool = False,
) -> BenchmarkReport:
    selected_mutations = tuple(mutations)
    selected_variants = tuple(manifest_variants)
    if not selected_mutations or not selected_variants:
        raise ValueError(
            "benchmark requires at least one mutation and manifest variant"
        )
    profile_names = {mutation.profile for mutation in selected_mutations}
    unknown = profile_names - set(PROFILES_BY_NAME)
    if unknown:
        raise ValueError(f"unknown benchmark profiles: {sorted(unknown)}")
    tools = _resolve_tools(profile_names, allow_java_pull=allow_java_pull)
    results: list[CaseResult] = []
    with tempfile.TemporaryDirectory(prefix="click-evidence-reuse-") as temporary:
        workspace = Path(temporary)
        java_container = ""
        try:
            if JAVA_JDK in profile_names and tools.java_backend == "docker-temurin-21":
                java_container = _start_java_container(workspace, tools)
            for profile_name in PROFILES_BY_NAME:
                profile_mutations = tuple(
                    mutation
                    for mutation in selected_mutations
                    if mutation.profile == profile_name
                )
                if not profile_mutations:
                    continue
                profile = PROFILES_BY_NAME[profile_name]
                profile_workspace = workspace / profile.name
                profile_workspace.mkdir()
                current = profile_workspace / "current"
                checks = _checks(
                    profile,
                    current,
                    tools,
                    java_container=java_container,
                )
                baseline_by_policy: dict[str, _Baseline] = {}
                for variant in selected_variants:
                    if variant.baseline_policy in baseline_by_policy:
                        continue
                    snapshot = profile_workspace / f"baseline-{variant.baseline_policy}"
                    baseline_by_policy[variant.baseline_policy] = _create_baseline(
                        profile, current, snapshot, checks, variant
                    )
                for variant in selected_variants:
                    baseline = baseline_by_policy[variant.baseline_policy]
                    for mutation in profile_mutations:
                        results.append(
                            _evaluate_case(
                                profile,
                                current,
                                checks,
                                baseline,
                                mutation,
                                variant,
                            )
                        )
        finally:
            _stop_java_container(java_container, tools)
    return BenchmarkReport(tuple(results), tools.versions)


def _selected_mutations(profile_names: Sequence[str]) -> tuple[SemanticMutation, ...]:
    if not profile_names:
        return MUTATIONS
    selected = set(profile_names)
    return tuple(mutation for mutation in MUTATIONS if mutation.profile in selected)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="emit a machine-readable report"
    )
    parser.add_argument(
        "--profile",
        action="append",
        choices=tuple(PROFILES_BY_NAME),
        default=[],
        help="run only one fixture profile; may be repeated",
    )
    parser.add_argument(
        "--manifest",
        action="append",
        choices=tuple(variant.name for variant in MANIFEST_VARIANTS),
        default=[],
        help="run only one manifest variant; may be repeated",
    )
    parser.add_argument(
        "--pull-java-image",
        action="store_true",
        help=f"pull the pinned {JAVA_IMAGE_TAG} image when no local JDK is available",
    )
    parser.add_argument(
        "--fail-on-unsafe",
        action="store_true",
        help="return a non-zero exit status when any unsafe reuse is observed",
    )
    arguments = parser.parse_args(argv)
    variants = tuple(
        variant
        for variant in MANIFEST_VARIANTS
        if not arguments.manifest or variant.name in arguments.manifest
    )
    report = run_benchmark(
        _selected_mutations(arguments.profile),
        variants,
        allow_java_pull=arguments.pull_java_image,
    )
    if arguments.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.text())
    return 1 if arguments.fail_on_unsafe and report.unsafe_reuse else 0


if __name__ == "__main__":
    raise SystemExit(main())
