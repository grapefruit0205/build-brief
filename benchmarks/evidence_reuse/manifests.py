"""Dependency-manifest inputs crossed with the independent semantic oracle.

Nothing in this module imports or inspects scenario oracle labels.  The runner
applies every variant to every semantic mutation, which prevents the expected
answer from being baked into the manifest under test.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ManifestVariant:
    name: str
    description: str
    baseline_policy: str
    post_mutation: str = "none"


MANIFEST_VARIANTS = (
    ManifestVariant(
        "exact",
        "complete, narrowly scoped dependency mapping",
        "exact",
    ),
    ManifestVariant(
        "broad",
        "valid mapping that treats the whole repository as a dependency",
        "broad",
    ),
    ManifestVariant(
        "incomplete",
        "valid mapping that deliberately omits shared/configuration inputs",
        "incomplete",
    ),
    ManifestVariant(
        "uncommitted",
        "complete mapping changed after the baseline commit",
        "exact",
        post_mutation="append_whitespace",
    ),
    ManifestVariant(
        "malformed",
        "complete mapping replaced by malformed JSON after baseline",
        "exact",
        post_mutation="malformed_json",
    ),
)


def dependency_patterns(
    variant: ManifestVariant,
    *,
    exact: tuple[str, ...],
    incomplete: tuple[str, ...],
) -> tuple[str, ...]:
    if variant.baseline_policy == "exact":
        return exact
    if variant.baseline_policy == "broad":
        return ("**",)
    if variant.baseline_policy == "incomplete":
        return incomplete
    raise ValueError(f"unknown manifest policy: {variant.baseline_policy}")


assert len(MANIFEST_VARIANTS) == 5
assert len({variant.name for variant in MANIFEST_VARIANTS}) == 5
