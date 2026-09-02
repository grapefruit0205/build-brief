"""Semantic mutations for the evidence-reuse safety benchmark.

This module deliberately knows nothing about Click dependency manifests.  Its
oracle is based only on whether the fixture verification semantically depends
on the changed input.  Manifest variants are defined independently in
``manifests.py`` and crossed with these mutations by the runner.
"""

from __future__ import annotations

from dataclasses import dataclass


PYTHON_SERVICE = "python-service"
PYTHON_PACKAGE = "python-package"
NODE_CJS = "node-commonjs"
NODE_ESM = "node-esm"
C_NATIVE = "c-native"
JAVA_JDK = "java-jdk"


@dataclass(frozen=True)
class SemanticMutation:
    profile: str
    name: str
    semantic_class: str
    component: str
    oracle_reuse_safe: bool
    expected_rerun_pass: bool
    oracle_reason: str
    path: str = ""
    operation: str = "append"
    value: str = ""
    old: str = ""
    new: str = ""
    environment: tuple[tuple[str, str], ...] = ()

    @property
    def mutation_id(self) -> str:
        return f"{self.profile}/{self.name}"


def _file(
    profile: str,
    name: str,
    semantic_class: str,
    component: str,
    *,
    reuse_safe: bool,
    rerun_pass: bool,
    reason: str,
    path: str,
    operation: str = "append",
    value: str = "",
    old: str = "",
    new: str = "",
) -> SemanticMutation:
    return SemanticMutation(
        profile=profile,
        name=name,
        semantic_class=semantic_class,
        component=component,
        oracle_reuse_safe=reuse_safe,
        expected_rerun_pass=rerun_pass,
        oracle_reason=reason,
        path=path,
        operation=operation,
        value=value,
        old=old,
        new=new,
    )


def _environment(profile: str, value: str) -> SemanticMutation:
    return SemanticMutation(
        profile=profile,
        name=f"environment-{value}",
        semantic_class="environment_drift",
        component="environment",
        oracle_reuse_safe=False,
        expected_rerun_pass=False,
        oracle_reason="the verification process reads CLICK_BENCH_MODE",
        operation="environment",
        environment=(("CLICK_BENCH_MODE", value),),
    )


def _safe_mutations(profile: str) -> tuple[SemanticMutation, ...]:
    reason = "the verification command never reads this repository input"
    return (
        _file(
            profile,
            "docs-readme-append",
            "irrelevant",
            "documentation",
            reuse_safe=True,
            rerun_pass=True,
            reason=reason,
            path="docs/README.md",
            value="\nBenchmark documentation note.\n",
        ),
        _file(
            profile,
            "docs-guide-reword",
            "irrelevant",
            "documentation",
            reuse_safe=True,
            rerun_pass=True,
            reason=reason,
            path="docs/guide.md",
            operation="replace",
            old="The guide",
            new="This guide",
        ),
        _file(
            profile,
            "changelog-append",
            "irrelevant",
            "documentation",
            reuse_safe=True,
            rerun_pass=True,
            reason=reason,
            path="CHANGELOG.md",
            value="\n- Benchmark-only history note.\n",
        ),
        _file(
            profile,
            "example-reword",
            "irrelevant",
            "example",
            reuse_safe=True,
            rerun_pass=True,
            reason=reason,
            path="examples/unused.txt",
            operation="replace",
            old="not imported",
            new="still not imported",
        ),
        _file(
            profile,
            "tool-notes-append",
            "irrelevant",
            "tooling_note",
            reuse_safe=True,
            rerun_pass=True,
            reason=reason,
            path="tools/notes.txt",
            value="\nupdated tooling notes\n",
        ),
        _file(
            profile,
            "asset-delete",
            "irrelevant",
            "asset",
            reuse_safe=True,
            rerun_pass=True,
            reason=reason,
            path="assets/banner.txt",
            operation="delete",
        ),
        _file(
            profile,
            "env-example-reword",
            "irrelevant",
            "environment_example",
            reuse_safe=True,
            rerun_pass=True,
            reason=reason,
            path=".env.example",
            operation="replace",
            old="development",
            new="preview",
        ),
        _file(
            profile,
            "generated-report-append",
            "irrelevant",
            "generated_sample",
            reuse_safe=True,
            rerun_pass=True,
            reason=reason,
            path="generated/report.txt",
            value="\nregenerated fixture report\n",
        ),
    )


def _python_service_mutations() -> tuple[SemanticMutation, ...]:
    profile = PYTHON_SERVICE
    dependent = "the unittest command imports or reads this input"
    return (
        *_safe_mutations(profile),
        _file(
            profile,
            "app-comment",
            "relevant_nonbreaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="app.py",
            value="\n# behavior-preserving note\n",
        ),
        _file(
            profile,
            "shared-comment",
            "relevant_nonbreaking",
            "shared_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="shared.py",
            value="\n# behavior-preserving note\n",
        ),
        _file(
            profile,
            "config-equivalent",
            "relevant_nonbreaking",
            "configuration",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="config.py",
            operation="replace",
            old="TAX_RATE = 0.15",
            new="TAX_RATE = 0.10 + 0.05",
        ),
        _file(
            profile,
            "test-comment",
            "relevant_nonbreaking",
            "test_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="tests/test_app.py",
            value="\n# behavior-preserving test note\n",
        ),
        _file(
            profile,
            "app-behavior-break",
            "relevant_breaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="app.py",
            operation="replace",
            old='return f"Hello, {normalize_name(name)}!"',
            new='return f"Hi, {normalize_name(name)}!"',
        ),
        _file(
            profile,
            "app-syntax-break",
            "relevant_breaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="app.py",
            value="\n\ndef broken(:\n    pass\n",
        ),
        _file(
            profile,
            "shared-behavior-break",
            "relevant_breaking",
            "shared_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="shared.py",
            operation="replace",
            old="return value.strip()",
            new="return value.strip().upper()",
        ),
        _file(
            profile,
            "config-value-break",
            "relevant_breaking",
            "configuration",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="config.py",
            operation="replace",
            old="TAX_RATE = 0.15",
            new="TAX_RATE = 0.25",
        ),
        _file(
            profile,
            "fixture-data-break",
            "relevant_breaking",
            "fixture_data",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="fixture_data.json",
            operation="replace",
            old='"label": "control"',
            new='"label": "changed"',
        ),
        _file(
            profile,
            "test-expectation-break",
            "relevant_breaking",
            "test_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="tests/test_app.py",
            operation="replace",
            old="self.assertEqual(total_with_tax(10), 11.5)",
            new="self.assertEqual(total_with_tax(10), 99)",
        ),
        _environment(profile, "production"),
        _environment(profile, "staging"),
    )


def _python_package_mutations() -> tuple[SemanticMutation, ...]:
    profile = PYTHON_PACKAGE
    dependent = "the package unittest command imports or reads this input"
    return (
        *_safe_mutations(profile),
        _file(
            profile,
            "core-comment",
            "relevant_nonbreaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="samplepkg/core.py",
            value="\n# behavior-preserving note\n",
        ),
        _file(
            profile,
            "shared-comment",
            "relevant_nonbreaking",
            "shared_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="samplepkg/shared.py",
            value="\n# behavior-preserving note\n",
        ),
        _file(
            profile,
            "settings-equivalent",
            "relevant_nonbreaking",
            "configuration",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="samplepkg/settings.py",
            operation="replace",
            old="MULTIPLIER = 2",
            new="MULTIPLIER = 1 + 1",
        ),
        _file(
            profile,
            "test-comment",
            "relevant_nonbreaking",
            "test_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="tests/test_core.py",
            value="\n# behavior-preserving test note\n",
        ),
        _file(
            profile,
            "core-behavior-break",
            "relevant_breaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="samplepkg/core.py",
            operation="replace",
            old="return value * MULTIPLIER",
            new="return value + MULTIPLIER",
        ),
        _file(
            profile,
            "core-syntax-break",
            "relevant_breaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="samplepkg/core.py",
            value="\n\ndef broken(:\n    pass\n",
        ),
        _file(
            profile,
            "shared-behavior-break",
            "relevant_breaking",
            "shared_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="samplepkg/shared.py",
            operation="replace",
            old="return value.strip()",
            new="return value.strip().upper()",
        ),
        _file(
            profile,
            "settings-value-break",
            "relevant_breaking",
            "configuration",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="samplepkg/settings.py",
            operation="replace",
            old="MULTIPLIER = 2",
            new="MULTIPLIER = 3",
        ),
        _file(
            profile,
            "package-data-break",
            "relevant_breaking",
            "fixture_data",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="samplepkg/data.json",
            operation="replace",
            old='"prefix": "Welcome"',
            new='"prefix": "Hello"',
        ),
        _file(
            profile,
            "test-expectation-break",
            "relevant_breaking",
            "test_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="tests/test_core.py",
            operation="replace",
            old="self.assertEqual(compute(4), 8)",
            new="self.assertEqual(compute(4), 9)",
        ),
        _environment(profile, "production"),
        _environment(profile, "staging"),
    )


def _node_cjs_mutations() -> tuple[SemanticMutation, ...]:
    profile = NODE_CJS
    dependent = "the Node.js test command imports this CommonJS input"
    return (
        *_safe_mutations(profile)[:4],
        _file(
            profile,
            "app-comment",
            "relevant_nonbreaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="lib/app.cjs",
            value="\n// behavior-preserving note\n",
        ),
        _file(
            profile,
            "shared-comment",
            "relevant_nonbreaking",
            "shared_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="lib/shared.cjs",
            value="\n// behavior-preserving note\n",
        ),
        _file(
            profile,
            "app-behavior-break",
            "relevant_breaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="lib/app.cjs",
            operation="replace",
            old="return value * FACTOR;",
            new="return value + FACTOR;",
        ),
        _file(
            profile,
            "config-value-break",
            "relevant_breaking",
            "configuration",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="lib/config.cjs",
            operation="replace",
            old="module.exports = { FACTOR: 3 };",
            new="module.exports = { FACTOR: 4 };",
        ),
        _file(
            profile,
            "test-expectation-break",
            "relevant_breaking",
            "test_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="tests/app.test.cjs",
            operation="replace",
            old="assert.equal(compute(4), 12);",
            new="assert.equal(compute(4), 13);",
        ),
        _environment(profile, "production"),
    )


def _node_esm_mutations() -> tuple[SemanticMutation, ...]:
    profile = NODE_ESM
    dependent = "the Node.js test command imports this ESM input"
    return (
        *_safe_mutations(profile)[4:],
        _file(
            profile,
            "config-equivalent",
            "relevant_nonbreaking",
            "configuration",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="src/config.mjs",
            operation="replace",
            old="export const OFFSET = 5;",
            new="export const OFFSET = 2 + 3;",
        ),
        _file(
            profile,
            "test-comment",
            "relevant_nonbreaking",
            "test_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="tests/app.test.mjs",
            value="\n// behavior-preserving test note\n",
        ),
        _file(
            profile,
            "app-behavior-break",
            "relevant_breaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="src/app.mjs",
            operation="replace",
            old="return value + OFFSET;",
            new="return value + OFFSET + 1;",
        ),
        _file(
            profile,
            "shared-behavior-break",
            "relevant_breaking",
            "shared_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="src/shared.mjs",
            operation="replace",
            old="return value.trim();",
            new="return value.trim().toUpperCase();",
        ),
        _file(
            profile,
            "test-expectation-break",
            "relevant_breaking",
            "test_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="tests/app.test.mjs",
            operation="replace",
            old='assert.equal(message("  Ada "), "Welcome, Ada!");',
            new='assert.equal(message("  Ada "), "Hello, Ada!");',
        ),
        _environment(profile, "staging"),
    )


def _c_mutations() -> tuple[SemanticMutation, ...]:
    profile = C_NATIVE
    dependent = "the GCC compile-and-test command reads this C input"
    return (
        *_safe_mutations(profile),
        _file(
            profile,
            "app-comment",
            "relevant_nonbreaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="src/app.c",
            value="\n// behavior-preserving note\n",
        ),
        _file(
            profile,
            "shared-comment",
            "relevant_nonbreaking",
            "shared_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="src/shared.c",
            value="\n// behavior-preserving note\n",
        ),
        _file(
            profile,
            "config-equivalent",
            "relevant_nonbreaking",
            "configuration",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="include/config.h",
            operation="replace",
            old="#define TAX_RATE 0.15",
            new="#define TAX_RATE (0.10 + 0.05)",
        ),
        _file(
            profile,
            "test-comment",
            "relevant_nonbreaking",
            "test_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="tests/test_app.c",
            value="\n// behavior-preserving test note\n",
        ),
        _file(
            profile,
            "app-behavior-break",
            "relevant_breaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="src/app.c",
            operation="replace",
            old='"Hello, %s!"',
            new='"Hi, %s!"',
        ),
        _file(
            profile,
            "app-syntax-break",
            "relevant_breaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="src/app.c",
            value="\nint broken( {\n",
        ),
        _file(
            profile,
            "shared-behavior-break",
            "relevant_breaking",
            "shared_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="src/shared.c",
            operation="replace",
            old="return buffer;",
            new='return "";',
        ),
        _file(
            profile,
            "config-value-break",
            "relevant_breaking",
            "configuration",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="include/config.h",
            operation="replace",
            old="#define TAX_RATE 0.15",
            new="#define TAX_RATE 0.25",
        ),
        _file(
            profile,
            "fixture-data-break",
            "relevant_breaking",
            "fixture_data",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="src/data.txt",
            operation="replace",
            old="control",
            new="changed",
        ),
        _file(
            profile,
            "test-expectation-break",
            "relevant_breaking",
            "test_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="tests/test_app.c",
            operation="replace",
            old="fabs(total_with_tax(10.0) - 11.5)",
            new="fabs(total_with_tax(10.0) - 99.0)",
        ),
        _environment(profile, "production"),
        _environment(profile, "staging"),
    )


def _java_mutations() -> tuple[SemanticMutation, ...]:
    profile = JAVA_JDK
    dependent = "the JDK compile-and-test command reads this Java input"
    return (
        *_safe_mutations(profile),
        _file(
            profile,
            "app-comment",
            "relevant_nonbreaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="src/App.java",
            value="\n// behavior-preserving note\n",
        ),
        _file(
            profile,
            "shared-comment",
            "relevant_nonbreaking",
            "shared_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="src/Shared.java",
            value="\n// behavior-preserving note\n",
        ),
        _file(
            profile,
            "config-equivalent",
            "relevant_nonbreaking",
            "configuration",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="src/Config.java",
            operation="replace",
            old="static final int MULTIPLIER = 2;",
            new="static final int MULTIPLIER = 1 + 1;",
        ),
        _file(
            profile,
            "test-comment",
            "relevant_nonbreaking",
            "test_source",
            reuse_safe=False,
            rerun_pass=True,
            reason=dependent,
            path="tests/AppTest.java",
            value="\n// behavior-preserving test note\n",
        ),
        _file(
            profile,
            "app-behavior-break",
            "relevant_breaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="src/App.java",
            operation="replace",
            old="return value * Config.MULTIPLIER;",
            new="return value + Config.MULTIPLIER;",
        ),
        _file(
            profile,
            "app-syntax-break",
            "relevant_breaking",
            "direct_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="src/App.java",
            value="\npublic broken syntax\n",
        ),
        _file(
            profile,
            "shared-behavior-break",
            "relevant_breaking",
            "shared_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="src/Shared.java",
            operation="replace",
            old="return value.trim();",
            new="return value.trim().toUpperCase();",
        ),
        _file(
            profile,
            "config-value-break",
            "relevant_breaking",
            "configuration",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="src/Config.java",
            operation="replace",
            old="static final int MULTIPLIER = 2;",
            new="static final int MULTIPLIER = 3;",
        ),
        _file(
            profile,
            "fixture-data-break",
            "relevant_breaking",
            "fixture_data",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="src/data.txt",
            operation="replace",
            old="Welcome",
            new="Hello",
        ),
        _file(
            profile,
            "test-expectation-break",
            "relevant_breaking",
            "test_source",
            reuse_safe=False,
            rerun_pass=False,
            reason=dependent,
            path="tests/AppTest.java",
            operation="replace",
            old="assertEquals(8, App.compute(4));",
            new="assertEquals(9, App.compute(4));",
        ),
        _environment(profile, "production"),
        _environment(profile, "staging"),
    )


MUTATIONS_BY_PROFILE: dict[str, tuple[SemanticMutation, ...]] = {
    PYTHON_SERVICE: _python_service_mutations(),
    PYTHON_PACKAGE: _python_package_mutations(),
    NODE_CJS: _node_cjs_mutations(),
    NODE_ESM: _node_esm_mutations(),
    C_NATIVE: _c_mutations(),
    JAVA_JDK: _java_mutations(),
}

MUTATIONS = tuple(
    mutation
    for profile_mutations in MUTATIONS_BY_PROFILE.values()
    for mutation in profile_mutations
)


def mutation_ids() -> tuple[str, ...]:
    return tuple(mutation.mutation_id for mutation in MUTATIONS)


assert len(MUTATIONS) == 100
assert len(mutation_ids()) == len(set(mutation_ids()))
assert sum(mutation.oracle_reuse_safe for mutation in MUTATIONS) == 40
assert sum(not mutation.oracle_reuse_safe for mutation in MUTATIONS) == 60
