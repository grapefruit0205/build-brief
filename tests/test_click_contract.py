from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import unittest

from hooks import click_contract, click_gate


class ClickContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = {
            "outcome": "Extract one contract validator.",
            "plain_language": "계약 검증 동작을 그대로 유지합니다.",
            "boundary": {
                "in_scope": ["contract validation"],
                "out_of_scope": [],
            },
            "must_hold": ["existing behavior remains unchanged"],
            "build": {"approach": ["extract one leaf module"]},
            "verification": {
                "scale": "focused",
                "evidence": [
                    {
                        "id": "E1",
                        "kind": "argv",
                        "description": "targeted contract tests",
                    }
                ],
                "done_when": [
                    {
                        "condition": "contract behavior is unchanged",
                        "primary_evidence": "E1",
                    }
                ],
            },
        }

    def encoded(self, mutate: object | None = None) -> str:
        value = copy.deepcopy(self.contract)
        if callable(mutate):
            mutate(value)
        return json.dumps(value, ensure_ascii=False)

    def test_contract_module_has_no_upward_runtime_dependency(self) -> None:
        source = Path(click_contract.__file__).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported.add(module)
                imported.update(
                    f"{module}.{alias.name}".strip(".") for alias in node.names
                )

        for forbidden in (
            "click_gate",
            "click_state",
            "click_process",
            "platform_protocol",
            "antigravity_gate",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(
                    any(forbidden in name.split(".") for name in imported),
                    imported,
                )

    def test_gate_keeps_direct_contract_validator_compatibility_alias(self) -> None:
        self.assertIs(click_gate._validate_contract, click_contract.validate_contract)
        aliases = {
            "STRING_FIELDS": click_contract.STRING_FIELDS,
            "OBJECT_FIELDS": click_contract.OBJECT_FIELDS,
            "CONTRACT_FIELDS": click_contract.CONTRACT_FIELDS,
            "BOUNDARY_FIELDS": click_contract.BOUNDARY_FIELDS,
            "BUILD_FIELDS": click_contract.BUILD_FIELDS,
            "VERIFICATION_FIELDS": click_contract.VERIFICATION_FIELDS,
            "EVIDENCE_SOURCE_FIELDS": click_contract.EVIDENCE_SOURCE_FIELDS,
            "DONE_WHEN_FIELDS": click_contract.DONE_WHEN_FIELDS,
            "EVIDENCE_ID_PATTERN": click_contract.EVIDENCE_ID_PATTERN,
            "VERIFICATION_SCALES": click_contract.VERIFICATION_SCALES,
            "VERIFICATION_UNIT_LIMITS": click_contract.VERIFICATION_UNIT_LIMITS,
            "VERIFICATION_CLASSES": click_contract.VERIFICATION_CLASSES,
        }
        for name, expected in aliases.items():
            with self.subTest(name=name):
                self.assertIs(getattr(click_gate, name), expected)
    def test_valid_contract_is_returned_without_normalization(self) -> None:
        full = copy.deepcopy(self.contract)
        full["build"]["semantics"] = ["preserve errors"]
        full["build"]["order"] = ["extract before wiring"]
        full["verification"]["intermediate_gate"] = "before an irreversible step"

        value, error = click_contract.validate_contract(
            json.dumps(full, ensure_ascii=False)
        )

        self.assertEqual(error, "")
        self.assertEqual(value, full)

    def test_representative_rejections_keep_exact_messages_and_order(self) -> None:
        unknown_top = copy.deepcopy(self.contract)
        unknown_top["unsupported"] = True
        del unknown_top["outcome"]

        invalid_id = copy.deepcopy(self.contract)
        invalid_id["verification"]["evidence"][0]["id"] = "1-invalid"

        duplicate_id = copy.deepcopy(self.contract)
        duplicate_id["verification"]["evidence"].append(
            {
                "id": "E1",
                "kind": "manual",
                "description": "duplicate source",
            }
        )

        browser_sources = copy.deepcopy(self.contract)
        browser_sources["verification"]["evidence"] = [
            {"id": "E1", "kind": "browser", "description": "first"},
            {"id": "E2", "kind": "browser", "description": "second"},
        ]
        browser_sources["verification"]["done_when"] = [
            {"condition": "first", "primary_evidence": "E1"},
            {"condition": "second", "primary_evidence": "E2"},
        ]

        inline_done_when = copy.deepcopy(self.contract)
        inline_done_when["verification"]["done_when"] = ["behavior works"]

        unknown_reference = copy.deepcopy(self.contract)
        unknown_reference["verification"]["done_when"][0][
            "primary_evidence"
        ] = "E-missing"

        unused_source = copy.deepcopy(self.contract)
        unused_source["verification"]["evidence"].append(
            {"id": "E2", "kind": "hosted", "description": "hosted result"}
        )

        cases = (
            ("invalid json", "{", "Execution Contract must be valid JSON."),
            ("not object", "[]", "Execution Contract must be a JSON object."),
            (
                "unknown before required",
                json.dumps(unknown_top),
                "Execution Contract contains unsupported top-level field(s): `unsupported`.",
            ),
            (
                "missing outcome",
                self.encoded(lambda value: value.pop("outcome")),
                "Execution Contract field `outcome` must be a non-empty string.",
            ),
            (
                "invalid evidence id",
                json.dumps(invalid_id),
                "Verification evidence item 1 `id` must start with a letter and contain at most 32 letters, digits, underscores, or hyphens.",
            ),
            (
                "duplicate evidence id",
                json.dumps(duplicate_id),
                "Verification evidence id `E1` must be unique.",
            ),
            (
                "multiple browser sources",
                json.dumps(browser_sources),
                "Verification may assign at most one Browser evidence source; reuse its id across every condition covered by the representative session.",
            ),
            (
                "inline done_when",
                json.dumps(inline_done_when),
                "Verification done_when item 1 must be an object with `condition` and `primary_evidence`; inline evidence strings are no longer accepted.",
            ),
            (
                "unknown evidence reference",
                json.dumps(unknown_reference),
                "Verification done_when item 1 references unknown evidence id `E-missing`.",
            ),
            (
                "unused evidence source",
                json.dumps(unused_source),
                "Verification evidence source(s) `E2` are unused; remove them or reference each one from `done_when`.",
            ),
            (
                "empty intermediate gate",
                self.encoded(
                    lambda value: value["verification"].__setitem__(
                        "intermediate_gate", ""
                    )
                ),
                "Optional verification `intermediate_gate` must be omitted or non-empty.",
            ),
        )

        for label, raw, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(
                    click_contract.validate_contract(raw),
                    (None, expected),
                )

    def test_valid_contract_is_not_rejected_by_prose_length(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["plain_language"] = "계약의 의미를 충분히 설명합니다. " * 300

        value, error = click_contract.validate_contract(
            json.dumps(contract, ensure_ascii=False)
        )

        self.assertEqual(error, "")
        self.assertEqual(value, contract)

    def test_profile_recommendation_does_not_limit_argv_source_count(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["verification"]["scale"] = "quick"
        for index in range(2, 12):
            evidence_id = f"E{index}"
            contract["verification"]["evidence"].append(
                {
                    "id": evidence_id,
                    "kind": "argv",
                    "description": f"targeted check {index}",
                }
            )
            contract["verification"]["done_when"].append(
                {
                    "condition": f"condition {index} remains true",
                    "primary_evidence": evidence_id,
                }
            )

        value, error = click_contract.validate_contract(json.dumps(contract))

        self.assertEqual(error, "")
        self.assertEqual(value, contract)


if __name__ == "__main__":
    unittest.main()
