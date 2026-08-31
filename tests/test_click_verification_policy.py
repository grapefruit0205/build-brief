from __future__ import annotations

import ast
from pathlib import Path
import unittest

from hooks import (
    click_contract,
    click_gate,
    click_verification_meter,
    click_verification_policy,
)


class ClickVerificationPolicyTests(unittest.TestCase):
    def imported_modules(self, module: object) -> set[str]:
        source = Path(module.__file__).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                parent = node.module or ""
                imported.add(parent)
                imported.update(
                    f"{parent}.{alias.name}".strip(".") for alias in node.names
                )
        return imported

    def test_policy_and_meter_are_independent_leaf_boundaries(self) -> None:
        forbidden = {
            "click_contract",
            "click_evidence",
            "click_gate",
            "click_process",
            "click_state",
            "platform_protocol",
        }
        for module in (click_verification_policy, click_verification_meter):
            imported = self.imported_modules(module)
            with self.subTest(module=module.__name__):
                self.assertTrue(
                    all(
                        not any(part in forbidden for part in name.split("."))
                        for name in imported
                    ),
                    imported,
                )

        self.assertNotIn(
            "click_verification_meter",
            self.imported_modules(click_verification_policy),
        )
        self.assertNotIn(
            "click_verification_policy",
            self.imported_modules(click_verification_meter),
        )

    def test_profiles_are_qualitative_and_legacy_units_are_compatibility_only(self) -> None:
        self.assertEqual(
            click_verification_policy.VERIFICATION_SCALES,
            ("quick", "focused", "full"),
        )
        for profile in click_verification_policy.VERIFICATION_SCALES:
            with self.subTest(profile=profile):
                self.assertTrue(click_verification_policy.is_profile(profile))
        for invalid in (None, "", "automatic", "focused+1", 4):
            with self.subTest(invalid=invalid):
                self.assertFalse(click_verification_policy.is_profile(invalid))

        # Direct callers and persisted state keep working, but these values do
        # not drive authority or runtime advice.
        self.assertEqual(
            click_verification_policy.VERIFICATION_UNIT_LIMITS,
            {"quick": 1, "focused": 4, "full": 10},
        )
        self.assertEqual(click_verification_policy.approved_unit_limit("quick"), 1)

    def test_legacy_meter_normalizes_classes_for_compatibility(self) -> None:
        self.assertEqual(
            click_verification_meter.effective_class("targeted", "broad"),
            "broad",
        )
        self.assertEqual(
            click_verification_meter.effective_class("deep", "targeted"),
            "deep",
        )
        self.assertEqual(
            click_verification_meter.total_units(["targeted", "broad", "deep"]),
            9,
        )
        self.assertIsNone(
            click_verification_meter.effective_class("unknown", "targeted")
        )
        self.assertIsNone(click_verification_meter.total_units(["targeted", "unknown"]))

    def test_existing_contract_and_gate_symbols_remain_compatible(self) -> None:
        self.assertIs(
            click_contract.VERIFICATION_SCALES,
            click_verification_policy.VERIFICATION_SCALES,
        )
        self.assertIs(
            click_contract.VERIFICATION_UNIT_LIMITS,
            click_verification_policy.VERIFICATION_UNIT_LIMITS,
        )
        self.assertIs(
            click_contract.VERIFICATION_CLASSES,
            click_verification_meter.VERIFICATION_CLASSES,
        )
        self.assertIs(
            click_gate.VERIFICATION_SCALES,
            click_verification_policy.VERIFICATION_SCALES,
        )
        self.assertIs(
            click_gate.VERIFICATION_UNIT_LIMITS,
            click_verification_policy.VERIFICATION_UNIT_LIMITS,
        )
        self.assertIs(
            click_gate.VERIFICATION_CLASSES,
            click_verification_meter.VERIFICATION_CLASSES,
        )


if __name__ == "__main__":
    unittest.main()
