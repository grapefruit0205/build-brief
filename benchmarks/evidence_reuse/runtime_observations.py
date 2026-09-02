"""Controlled baseline dependency observations for benchmark fixtures.

These inputs model the output of a complete runtime observer. They are kept
separate from both the semantic oracle and dependency-manifest variants so the
decision rule cannot select observations from expected case labels.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hooks import click_dependency_cache


OBSERVATION_SOURCE = "controlled-fixture-runtime-v1"


_OBSERVATIONS: dict[str, dict[str, Any]] = {
    "python-service": {
        "paths": (
            "app.py",
            "config.py",
            "fixture_data.json",
            "shared.py",
            "tests/",
            "tests/test_app.py",
        ),
        "child_processes": 0,
    },
    "python-package": {
        "paths": (
            "samplepkg/__init__.py",
            "samplepkg/core.py",
            "samplepkg/data.json",
            "samplepkg/settings.py",
            "samplepkg/shared.py",
            "tests/",
            "tests/test_core.py",
        ),
        "child_processes": 0,
    },
    "node-commonjs": {
        "paths": (
            "lib/app.cjs",
            "lib/config.cjs",
            "lib/data.json",
            "lib/shared.cjs",
            "package.json",
            "tests/app.test.cjs",
        ),
        "child_processes": 1,
    },
    "node-esm": {
        "paths": (
            "package.json",
            "src/app.mjs",
            "src/config.mjs",
            "src/data.json",
            "src/shared.mjs",
            "tests/app.test.mjs",
        ),
        "child_processes": 1,
    },
    "c-native": {
        "paths": (
            "include/app.h",
            "include/config.h",
            "include/shared.h",
            "src/app.c",
            "src/data.txt",
            "src/shared.c",
            "tests/test_app.c",
        ),
        "child_processes": 4,
    },
    "java-jdk": {
        "paths": (
            "src/App.java",
            "src/Config.java",
            "src/Shared.java",
            "src/data.txt",
            "tests/AppTest.java",
            "tools/run-tests.sh",
        ),
        "child_processes": 3,
    },
}


def capture_baseline_observation(
    profile_name: str,
    root: Path,
    *,
    baseline_passed: bool,
) -> dict[str, Any]:
    """Return the fixture observer receipt produced by one baseline run."""
    specification = _OBSERVATIONS.get(profile_name)
    if not baseline_passed or specification is None:
        return click_dependency_cache.unavailable_dependency_observation(failed=True)
    paths = tuple(specification["paths"])
    if any(not (root / path.rstrip("/")).exists() for path in paths):
        return click_dependency_cache.unavailable_dependency_observation(failed=True)
    return click_dependency_cache.dependency_observation(
        paths,
        child_processes=int(specification["child_processes"]),
        process_tree_complete=True,
    )


assert len(_OBSERVATIONS) == 6
