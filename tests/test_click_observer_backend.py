from __future__ import annotations

import ast
from pathlib import Path
import unittest
from unittest import mock

from hooks import (
    click_dependency_cache,
    click_dependency_trace,
    click_observer_backend,
    click_observer_common,
    click_observer_linux,
)


EVIDENCE_KEY = "a" * 64
CHECK_DIGEST = "b" * 64


class ClickObserverBackendTests(unittest.TestCase):
    def test_selector_exposes_linux_and_honest_native_placeholders(self) -> None:
        linux = click_observer_backend.select_backend("Linux")
        self.assertEqual(linux.system, "Linux")
        self.assertEqual(linux.backend_name, "strace")
        self.assertEqual(linux.status, "available")
        self.assertEqual(linux.reason, "runtime-probe-required")

        for system in ("Darwin", "Windows"):
            with self.subTest(system=system):
                capability = click_observer_backend.select_backend(system)
                self.assertEqual(capability.system, system)
                self.assertIsNone(capability.backend_name)
                self.assertEqual(capability.status, "unavailable")
                self.assertEqual(
                    capability.reason, "native-backend-not-implemented"
                )

        unknown = click_observer_backend.select_backend("OtherOS")
        self.assertIsNone(unknown.backend_name)
        self.assertEqual(unknown.status, "unavailable")
        self.assertEqual(unknown.reason, "unsupported-operating-system")

    def test_capability_contract_rejects_contradictory_states(self) -> None:
        with self.assertRaises(ValueError):
            click_observer_backend.BackendCapability(
                system="Darwin",
                backend_name=None,
                status="available",
                reason="invalid",
            )
        with self.assertRaises(ValueError):
            click_observer_backend.BackendCapability(
                system="Windows",
                backend_name="invented",
                status="unavailable",
                reason="invalid",
            )
        with self.assertRaises(ValueError):
            click_observer_backend.BackendCapability(
                system="OtherOS",
                backend_name=None,
                status="unknown",
                reason="invalid",
            )

    def test_non_linux_facade_executes_target_once_without_backend_probe(self) -> None:
        calls: list[str] = []
        for system in ("Darwin", "Windows"):
            with self.subTest(system=system):
                result = click_dependency_trace.run_command(
                    ["check", "--flag"],
                    workspace=Path.cwd(),
                    environment={},
                    evidence_key=EVIDENCE_KEY,
                    check_digest=CHECK_DIGEST,
                    mutation_revision=2,
                    execute_unobserved=lambda: calls.append(system) or 7,
                    resolve_backend=lambda *_args, **_kwargs: self.fail(
                        "an unavailable backend must not be probed"
                    ),
                    system_name=system,
                )
                self.assertEqual(result.exit_code, 7)
                self.assertEqual(result.record["status"], "unavailable")
                self.assertIsNone(result.record["backend"])
                self.assertFalse(result.record["authoritative"])
                self.assertFalse(result.record["reuse_authorized"])
        self.assertEqual(calls, ["Darwin", "Windows"])

    def test_capability_detection_failure_executes_target_once(self) -> None:
        calls: list[int] = []
        with mock.patch.object(
            click_dependency_trace,
            "select_backend",
            side_effect=RuntimeError("probe failed"),
        ):
            result = click_dependency_trace.run_command(
                ["check"],
                workspace=Path.cwd(),
                environment={},
                evidence_key=EVIDENCE_KEY,
                check_digest=CHECK_DIGEST,
                mutation_revision=3,
                execute_unobserved=lambda: calls.append(1) or 4,
                resolve_backend=lambda *_args, **_kwargs: self.fail(
                    "failed capability detection must not probe a backend"
                ),
                system_name="Linux",
            )
        self.assertEqual(result.exit_code, 4)
        self.assertEqual(calls, [1])
        self.assertEqual(result.record["status"], "unavailable")

    def test_linux_facade_dispatches_through_backend_boundary(self) -> None:
        record = click_dependency_cache.shadow_observer_record(
            evidence_key=EVIDENCE_KEY,
            check_digest=CHECK_DIGEST,
            mutation_revision=4,
            backend_name="strace",
            backend_version="6.1",
            backend_digest="c" * 64,
        )
        expected = click_observer_common.ShadowExecution(0, record)
        fallback = mock.Mock(return_value=91)
        with mock.patch.object(
            click_observer_linux, "run_command", return_value=expected
        ) as run:
            result = click_dependency_trace.run_command(
                ["check"],
                workspace=Path.cwd(),
                environment={},
                evidence_key=EVIDENCE_KEY,
                check_digest=CHECK_DIGEST,
                mutation_revision=4,
                execute_unobserved=fallback,
                resolve_backend=lambda *_args, **_kwargs: ("/usr/bin/strace", ""),
                system_name="Linux",
            )
        self.assertIs(result, expected)
        self.assertEqual(run.call_count, 1)
        fallback.assert_not_called()

    def test_backend_layers_do_not_import_authority_domains(self) -> None:
        forbidden = {
            "click_contract",
            "click_evidence",
            "click_gate",
            "click_receipt",
            "click_state",
            "click_verification",
        }
        for module in (
            click_observer_backend,
            click_observer_common,
            click_observer_linux,
        ):
            with self.subTest(module=module.__name__):
                tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
                imported: set[str] = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.update(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom):
                        imported.add(node.module or "")
                self.assertTrue(forbidden.isdisjoint(imported), imported)


if __name__ == "__main__":
    unittest.main()
