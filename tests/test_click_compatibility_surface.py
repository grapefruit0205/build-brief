from __future__ import annotations

import ast
from pathlib import Path
import unittest

from click_gate_compatibility_baseline import (
    DOCUMENTED_LEGACY_FORWARDERS,
    HOST_ADAPTER_SURFACE,
    MAX_PRIVATE_FORWARDERS,
    PRIVATE_FORWARDERS,
)


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "hooks"


def _qualified_attribute(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
        return None
    return f"{node.value.id}.{node.attr}"


def _private_forwarders() -> dict[str, str]:
    tree = ast.parse((HOOKS / "click_gate.py").read_text(encoding="utf-8"))
    bindings: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if not target.id.startswith("_") or target.id.startswith("__"):
            continue
        value = _qualified_attribute(node.value)
        if value is not None:
            bindings[target.id] = value
    return bindings


def _click_gate_surface(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "click_gate"
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith(
            "click_gate"
        ):
            names.update(alias.name for alias in node.names)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "click_gate"
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            names.add(node.args[1].value)
    return frozenset(names)


class ClickCompatibilitySurfaceTests(unittest.TestCase):
    def test_private_forwarders_match_the_reviewed_baseline(self) -> None:
        actual = _private_forwarders()

        self.assertEqual(len(actual), MAX_PRIVATE_FORWARDERS)
        self.assertEqual(actual, PRIVATE_FORWARDERS)

    def test_documented_legacy_forwarders_keep_their_exact_owner(self) -> None:
        actual = _private_forwarders()

        for name, target in DOCUMENTED_LEGACY_FORWARDERS.items():
            with self.subTest(name=name):
                self.assertEqual(actual.get(name), target)

    def test_only_declared_host_adapters_depend_on_the_gate_facade(self) -> None:
        actual: dict[str, frozenset[str]] = {}
        for path in HOOKS.glob("*.py"):
            if path.name == "click_gate.py":
                continue
            attributes = _click_gate_surface(path)
            if attributes:
                actual[str(path.relative_to(ROOT))] = attributes

        self.assertEqual(actual, HOST_ADAPTER_SURFACE)

    def test_policy_explains_that_the_legacy_surface_must_shrink(self) -> None:
        policy = (ROOT / "COMPATIBILITY_SURFACE.md").read_text(encoding="utf-8")

        self.assertIn("144 private module-forwarding bindings", policy)
        self.assertIn("baseline must not grow", policy)
        self.assertIn("not a general public extension API", policy)
        self.assertIn("formal host API", policy)


if __name__ == "__main__":
    unittest.main()
