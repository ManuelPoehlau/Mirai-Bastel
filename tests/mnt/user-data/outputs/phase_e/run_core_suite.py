"""Führt die komplette Core-Testsuite aus (Hardening Phase A/B + Architekturverträge).

Ausführen: python -m tests.run_core_suite
"""

from __future__ import annotations

import sys
import unittest


def main() -> int:
    print("=== Core-Testsuite (src/core) ===\n")

    # Phase A/B: unittest-Module
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for module_name in (
        "tests.test_mesh_invariants",
        "tests.test_topology_mutations",
        "tests.test_identity_continuity",
        "tests.test_topology_history",
        "tests.test_scene_serialization",
    ):
        suite.addTests(loader.loadTestsFromName(module_name))

    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    unittest_result = runner.run(suite)

    # Architekturverträge (bestehendes Skript)
    print("\n=== Architekturverträge (test_core.run_all) ===")
    arch_ok = True
    try:
        from tests.test_core import run_all

        run_all()
    except AssertionError as exc:
        arch_ok = False
        print(f"\n[FAIL] Architekturvertrag verletzt: {exc}")
    except Exception as exc:
        arch_ok = False
        print(f"\n[FAIL] Unerwarteter Fehler: {exc}")

    print("\n=== Zusammenfassung ===")
    print(f"  unittest (Phase A/B): {unittest_result.testsRun} Tests, "
          f"Failures={len(unittest_result.failures)}, Errors={len(unittest_result.errors)}")
    print(f"  Architekturverträge:  {'PASS' if arch_ok else 'FAIL'}")

    if unittest_result.wasSuccessful() and arch_ok:
        print("\nGesamt: PASS")
        return 0
    print("\nGesamt: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
