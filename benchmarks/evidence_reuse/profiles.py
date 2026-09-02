"""Runtime fixture definitions for the evidence-reuse benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .scenarios import (
    C_NATIVE,
    JAVA_JDK,
    NODE_CJS,
    NODE_ESM,
    PYTHON_PACKAGE,
    PYTHON_SERVICE,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures"


@dataclass(frozen=True)
class FixtureProfile:
    name: str
    display_name: str
    language: str
    runtime_kind: str
    fixture_template: Path
    evidence_id: str
    exact_dependencies: tuple[str, ...]
    incomplete_dependencies: tuple[str, ...]


PROFILES = (
    FixtureProfile(
        PYTHON_SERVICE,
        "Python service",
        "Python",
        "python-service",
        FIXTURES / "python_fixture",
        "E-benchmark-python-service",
        ("app.py", "config.py", "fixture_data.json", "shared.py", "tests/"),
        ("app.py", "tests/"),
    ),
    FixtureProfile(
        PYTHON_PACKAGE,
        "Python package",
        "Python",
        "python-package",
        FIXTURES / "python_package_fixture",
        "E-benchmark-python-package",
        ("samplepkg/", "tests/"),
        ("samplepkg/__init__.py", "samplepkg/core.py", "tests/"),
    ),
    FixtureProfile(
        NODE_CJS,
        "Node.js CommonJS",
        "Node.js",
        "node-cjs",
        FIXTURES / "node_cjs_fixture",
        "E-benchmark-node-cjs",
        ("lib/", "tests/app.test.cjs"),
        ("lib/app.cjs", "tests/app.test.cjs"),
    ),
    FixtureProfile(
        NODE_ESM,
        "Node.js ESM",
        "Node.js",
        "node-esm",
        FIXTURES / "node_esm_fixture",
        "E-benchmark-node-esm",
        ("src/", "tests/app.test.mjs"),
        ("src/app.mjs", "tests/app.test.mjs"),
    ),
    FixtureProfile(
        C_NATIVE,
        "C (GCC)",
        "C",
        "c-gcc",
        FIXTURES / "c_fixture",
        "E-benchmark-c-gcc",
        ("include/", "src/", "tests/test_app.c"),
        ("include/app.h", "src/app.c", "tests/test_app.c"),
    ),
    FixtureProfile(
        JAVA_JDK,
        "Java (JDK 21)",
        "Java",
        "java-jdk",
        FIXTURES / "java_fixture",
        "E-benchmark-java-jdk",
        ("src/", "tests/AppTest.java", "tools/run-tests.sh"),
        ("src/App.java", "tests/AppTest.java", "tools/run-tests.sh"),
    ),
)

PROFILES_BY_NAME = {profile.name: profile for profile in PROFILES}


assert len(PROFILES) == 6
assert len(PROFILES_BY_NAME) == len(PROFILES)
