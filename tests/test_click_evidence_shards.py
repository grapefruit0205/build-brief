from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from hooks import click_evidence, click_evidence_shards


class ClickEvidenceShardsTests(unittest.TestCase):
    def test_antigravity_distribution_contains_the_exact_shard_module(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(
            (root / "hooks" / "click_evidence_shards.py").read_bytes(),
            (
                root
                / "dist"
                / "antigravity"
                / "hooks"
                / "click_evidence_shards.py"
            ).read_bytes(),
        )

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "workspace"
        self.root.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True)
        tests = self.root / "tests"
        tests.mkdir()
        (tests / "test_alpha.py").write_text("# alpha\n", encoding="utf-8")
        (tests / "test_beta.py").write_text("# beta\n", encoding="utf-8")
        self.parent_argv = [
            "python3",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-q",
        ]
        self.write_manifest()
        self.commit()

    def git_capture(self, cwd: Path, arguments: list[str]) -> bytes | None:
        completed = subprocess.run(
            [
                "git",
                "--no-pager",
                "--no-optional-locks",
                "-c",
                "core.fsmonitor=false",
                *arguments,
            ],
            cwd=cwd,
            capture_output=True,
            check=False,
        )
        return completed.stdout if completed.returncode == 0 else None

    def commit(self) -> None:
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Click Tests",
                "-c",
                "user.email=click-tests@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "fixture",
            ],
            cwd=self.root,
            check=True,
        )

    def manifest(self) -> dict[str, object]:
        return {
            "version": 1,
            "entries": [
                {
                    "checks": [self.parent_argv],
                    "inventory": ["tests/test_*.py"],
                    "shards": [
                        {
                            "id": "alpha",
                            "checks": [
                                ["python3", "-m", "unittest", "tests.test_alpha", "-q"]
                            ],
                            "covers": ["tests/test_alpha.py"],
                        },
                        {
                            "id": "beta",
                            "checks": [
                                ["python3", "-m", "unittest", "tests.test_beta", "-q"]
                            ],
                            "covers": ["tests/test_beta.py"],
                        },
                    ],
                }
            ],
        }

    def named_manifest(self, *, label: str = "Full suite") -> dict[str, object]:
        return {
            "version": 2,
            "verifications": [
                {
                    "id": "full-suite",
                    "label": label,
                    "class": "broad",
                    "checks": [self.parent_argv],
                },
                {
                    "id": "alpha-unit",
                    "label": "Alpha unit",
                    "class": "targeted",
                    "checks": [
                        ["python3", "-m", "unittest", "tests.test_alpha", "-q"]
                    ],
                },
            ],
            "entries": [
                {
                    "verification_id": "full-suite",
                    "inventory": ["tests/test_*.py"],
                    "shards": self.manifest()["entries"][0]["shards"],
                }
            ],
        }

    def write_manifest(self, value: dict[str, object] | None = None) -> None:
        target = self.root / click_evidence_shards.CONFIG_RELATIVE_PATH
        target.parent.mkdir(exist_ok=True)
        target.write_text(
            json.dumps(value or self.manifest(), indent=2) + "\n",
            encoding="utf-8",
        )

    def parent_checks(self) -> list[dict[str, object]]:
        return [
            {"evidence_id": "E1", "argv": self.parent_argv, "class": "broad"}
        ]

    def named_definition(
        self,
        *,
        verification_id: str,
        label: str,
        argv: list[str],
    ) -> dict[str, object]:
        return {
            "id": verification_id,
            "label": label,
            "class": "targeted",
            "checks": [argv],
        }

    def resolve(self) -> dict[str, object]:
        return click_evidence_shards.resolve_plan(
            self.root,
            self.parent_checks(),
            parent_source_key=click_evidence.evidence_key("E1"),
            git_capture=self.git_capture,
        )

    def test_committed_exact_map_resolves_stable_complete_children(self) -> None:
        first = self.resolve()
        second = self.resolve()

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "sharded")
        children = first["children"]
        self.assertEqual([child["shard_id"] for child in children], ["alpha", "beta"])
        self.assertEqual(len({child["source_key"] for child in children}), 2)
        self.assertRegex(first["plan_digest"], r"^[0-9a-f]{64}$")

    def test_v2_names_resolve_exact_argv_and_reuse_the_shard_definition(self) -> None:
        self.write_manifest(self.named_manifest())
        self.commit()

        resolved, error = click_evidence_shards.resolve_named_verifications(
            self.root,
            ["alpha-unit", "full-suite"],
            git_capture=self.git_capture,
        )

        self.assertEqual(error, "")
        assert resolved is not None
        self.assertEqual(
            resolved["checks"][0],
            {
                "evidence_id": "alpha-unit",
                "argv": [
                    "python3",
                    "-m",
                    "unittest",
                    "tests.test_alpha",
                    "-q",
                ],
                "class": "targeted",
            },
        )
        self.assertEqual(
            [check["evidence_id"] for check in resolved["checks"]],
            ["alpha-unit", "full-suite"],
        )
        self.assertTrue(
            click_evidence_shards.selection_binding_is_valid(
                resolved["binding"]
            )
        )
        serialized_binding = json.dumps(resolved["binding"], sort_keys=True)
        self.assertNotIn("python3", serialized_binding)
        self.assertNotIn(str(self.root), serialized_binding)
        plan = click_evidence_shards.resolve_plan(
            self.root,
            [resolved["checks"][1]],
            parent_source_key=click_evidence.evidence_key("full-suite"),
            git_capture=self.git_capture,
            preloaded_entries=resolved["entries"],
        )
        self.assertEqual(plan["status"], "sharded")
        self.assertEqual(self.resolve()["status"], "sharded")

    def test_display_label_is_not_part_of_executable_definition_identity(self) -> None:
        self.write_manifest(self.named_manifest(label="First label"))
        self.commit()
        first, first_error = click_evidence_shards.resolve_named_verifications(
            self.root, ["full-suite"], git_capture=self.git_capture
        )
        self.assertEqual(first_error, "")
        assert first is not None

        self.write_manifest(self.named_manifest(label="Second label"))
        self.commit()
        second, second_error = click_evidence_shards.resolve_named_verifications(
            self.root, ["full-suite"], git_capture=self.git_capture
        )
        self.assertEqual(second_error, "")
        assert second is not None

        self.assertEqual(first["checks"], second["checks"])
        self.assertEqual(
            first["binding"]["selections"][0]["definition_digest"],
            second["binding"]["selections"][0]["definition_digest"],
        )
        self.assertNotEqual(
            first["binding"]["config_digest"],
            second["binding"]["config_digest"],
        )

    def test_named_resolution_rejects_unknown_duplicate_and_edited_catalog(self) -> None:
        self.write_manifest(self.named_manifest())
        self.commit()

        unknown, unknown_error = click_evidence_shards.resolve_named_verifications(
            self.root, ["missing"], git_capture=self.git_capture
        )
        duplicate, duplicate_error = (
            click_evidence_shards.resolve_named_verifications(
                self.root,
                ["alpha-unit", "alpha-unit"],
                git_capture=self.git_capture,
            )
        )
        target = self.root / click_evidence_shards.CONFIG_RELATIVE_PATH
        target.write_text(
            target.read_text(encoding="utf-8") + "\n", encoding="utf-8"
        )
        edited, edited_error = click_evidence_shards.resolve_named_verifications(
            self.root, ["alpha-unit"], git_capture=self.git_capture
        )

        self.assertIsNone(unknown)
        self.assertEqual(unknown_error, "unknown-verification-name:missing")
        self.assertIsNone(duplicate)
        self.assertEqual(
            duplicate_error, "verification-names-invalid-or-duplicate"
        )
        self.assertIsNone(edited)
        self.assertEqual(edited_error, "manifest-working-copy-mismatch")

    def test_duplicate_committed_names_are_ambiguous_and_rejected(self) -> None:
        value = self.named_manifest()
        value["verifications"].append(
            copy.deepcopy(value["verifications"][0])
        )
        self.write_manifest(value)
        self.commit()

        resolved, error = click_evidence_shards.resolve_named_verifications(
            self.root, ["full-suite"], git_capture=self.git_capture
        )

        self.assertIsNone(resolved)
        self.assertEqual(error, "verification-id-invalid-or-duplicate")

    def test_named_definitions_preserve_exact_argv_differences(self) -> None:
        variants = [
            self.named_definition(
                verification_id="python-name",
                label="Python name",
                argv=["python", "-m", "unittest", "tests.test_alpha", "-q"],
            ),
            self.named_definition(
                verification_id="python3-name",
                label="Python3 name",
                argv=["python3", "-m", "unittest", "tests.test_alpha", "-q"],
            ),
            self.named_definition(
                verification_id="verbose-name",
                label="Verbose name",
                argv=["python3", "-m", "unittest", "-v", "tests.test_alpha"],
            ),
        ]
        value = {
            "version": 2,
            "verifications": variants,
            "entries": [],
        }
        self.write_manifest(value)
        self.commit()

        resolved, error = click_evidence_shards.resolve_named_verifications(
            self.root,
            ["python-name", "python3-name", "verbose-name"],
            git_capture=self.git_capture,
        )

        self.assertEqual(error, "")
        assert resolved is not None
        self.assertEqual(
            [check["argv"] for check in resolved["checks"]],
            [definition["checks"][0] for definition in variants],
        )
        self.assertEqual(
            len(
                {
                    selection["definition_digest"]
                    for selection in resolved["binding"]["selections"]
                }
            ),
            3,
        )

    def test_named_binding_detects_definition_change_before_execution(self) -> None:
        self.write_manifest(self.named_manifest())
        self.commit()
        resolved, error = click_evidence_shards.resolve_named_verifications(
            self.root, ["alpha-unit"], git_capture=self.git_capture
        )
        self.assertEqual(error, "")
        assert resolved is not None
        self.assertEqual(
            click_evidence_shards.selection_binding_error(
                self.root, resolved["binding"], git_capture=self.git_capture
            ),
            "",
        )

        target = self.root / click_evidence_shards.CONFIG_RELATIVE_PATH
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "Alpha unit", "Changed label"
            ),
            encoding="utf-8",
        )

        self.assertIn(
            "changed after preparation",
            click_evidence_shards.selection_binding_error(
                self.root, resolved["binding"], git_capture=self.git_capture
            ),
        )

        self.commit()
        self.assertIn(
            "changed after preparation",
            click_evidence_shards.selection_binding_error(
                self.root, resolved["binding"], git_capture=self.git_capture
            ),
        )

    def test_edited_map_and_inventory_drift_fall_back_to_parent(self) -> None:
        target = self.root / click_evidence_shards.CONFIG_RELATIVE_PATH
        target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        edited = self.resolve()
        self.assertEqual(edited["status"], "fallback")
        self.assertEqual(edited["reason"], "manifest-working-copy-mismatch")

        subprocess.run(
            ["git", "restore", click_evidence_shards.CONFIG_RELATIVE_PATH],
            cwd=self.root,
            check=True,
        )
        (self.root / "tests" / "test_gamma.py").write_text("# gamma\n", encoding="utf-8")
        drifted = self.resolve()
        self.assertEqual(drifted["status"], "fallback")
        self.assertEqual(drifted["reason"], "inventory-not-covered-exactly-once")

    def test_default_unittest_discovery_cannot_be_narrower_than_inventory(
        self,
    ) -> None:
        # unittest discover defaults to test*.py, not test_*.py.  An untracked
        # file is executable by the parent runner and therefore must prevent
        # decomposition when the committed shard inventory omits it.
        (self.root / "tests" / "testfoo.py").write_text(
            "# discovered by the parent only\n", encoding="utf-8"
        )

        plan = self.resolve()

        self.assertEqual(plan["status"], "fallback")
        self.assertEqual(plan["reason"], "inventory-narrower-than-parent-discovery")

    def test_explicit_unittest_pattern_bounds_parent_discovery(self) -> None:
        (self.root / "tests" / "testfoo.py").write_text(
            "# outside the explicit parent pattern\n", encoding="utf-8"
        )
        self.parent_argv = [
            "python3",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
            "-q",
        ]
        self.write_manifest()
        self.commit()

        plan = self.resolve()

        self.assertEqual(plan["status"], "sharded")

    def test_ignored_parent_discovery_member_also_forces_fallback(self) -> None:
        (self.root / ".gitignore").write_text(
            "tests/testignored.py\n", encoding="utf-8"
        )
        self.commit()
        (self.root / "tests" / "testignored.py").write_text(
            "# ignored by Git but executable by unittest\n", encoding="utf-8"
        )

        plan = self.resolve()

        self.assertEqual(plan["status"], "fallback")
        self.assertEqual(plan["reason"], "inventory-narrower-than-parent-discovery")

    def test_overlap_or_unsupported_child_is_not_decomposition_authority(self) -> None:
        value = self.manifest()
        shards = value["entries"][0]["shards"]
        shards[0]["covers"] = ["tests/test_*.py"]
        self.write_manifest(value)
        self.commit()

        overlap = self.resolve()
        self.assertEqual(overlap["status"], "fallback")
        self.assertEqual(overlap["reason"], "inventory-not-covered-exactly-once")

    def test_activation_uses_regular_sources_and_tampering_fails_closed(self) -> None:
        plan = self.resolve()
        contract = {
            "verification": {
                "evidence": [
                    {
                        "id": "E1",
                        "kind": "argv",
                        "description": "suite",
                        "dependencies": ["src/"],
                    }
                ]
            }
        }
        state = {
            "state_schema_version": 2,
            "status": "approved",
            "evidence_state": click_evidence.fresh_state(contract),
        }
        parent_key = click_evidence.evidence_key("E1")

        sources, error = click_evidence.activate_shard_plan(state, parent_key, plan)

        self.assertEqual(error, "")
        assert sources is not None
        self.assertNotIn(parent_key, sources)
        self.assertEqual(len(sources), 2)
        self.assertTrue(
            all(click_evidence_shards.source_metadata_is_valid(source["shard"])
                for source in sources.values())
        )
        self.assertEqual(
            click_evidence.sources_from_state(
                state, expected_contract_schema_version=2
            ),
            sources,
        )

        tampered = copy.deepcopy(state)
        next(iter(tampered["evidence_state"]["sources"].values()))[
            "reserved_check_digest"
        ] = hashlib.sha256(b"wrong").hexdigest()
        self.assertEqual(
            click_evidence.sources_from_state(
                tampered, expected_contract_schema_version=2
            ),
            {},
        )

        restored, error = click_evidence.collapse_shard_plan(state, parent_key)
        self.assertEqual(error, "")
        assert restored is not None
        self.assertEqual(set(restored), {parent_key})
        self.assertEqual(restored[parent_key]["status"], "ready")

    def test_runner_revalidates_committed_plan_before_execution(self) -> None:
        plan = self.resolve()
        contract = {
            "verification": {
                "evidence": [{"id": "E1", "kind": "argv", "description": "suite"}]
            }
        }
        state = {
            "state_schema_version": 2,
            "status": "approved",
            "evidence_state": click_evidence.fresh_state(contract),
        }
        parent_key = click_evidence.evidence_key("E1")
        sources, error = click_evidence.activate_shard_plan(state, parent_key, plan)
        self.assertEqual(error, "")
        assert sources is not None
        grouped = {
            child["source_key"]: [
                {
                    "evidence_id": child["evidence_id"],
                    "argv": child["checks"][0],
                    "class": "broad",
                }
            ]
            for child in plan["children"]
        }
        self.assertEqual(
            click_evidence_shards.running_plan_error(
                self.root,
                state["evidence_state"],
                grouped,
                git_capture=self.git_capture,
            ),
            "",
        )

        target = self.root / click_evidence_shards.CONFIG_RELATIVE_PATH
        target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertIn(
            "authority changed",
            click_evidence_shards.running_plan_error(
                self.root,
                state["evidence_state"],
                grouped,
                git_capture=self.git_capture,
            ),
        )


if __name__ == "__main__":
    unittest.main()
