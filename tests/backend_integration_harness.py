from __future__ import annotations

import argparse
import io
import json
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

TEST_MODULES = [
    "tests.test_backend_auth_integration",
    "tests.test_backend_lobby_integration",
    "tests.test_backend_telemetry_integration",
    "tests.test_backend_race_submit_integration",
    "tests.test_backend_external_delivery_integration",
    "tests.test_backend_contracts_integration",
    "tests.test_backend_ws_and_concurrency_integration",
]


def run_integration_suite() -> dict:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.loadTestsFromName(module) for module in TEST_MODULES)
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    result = runner.run(suite)
    return {
        "all_passed": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failures": [{"test": case.id(), "details": details} for case, details in result.failures],
        "errors": [{"test": case.id(), "details": details} for case, details in result.errors],
        "skipped": [{"test": case.id(), "reason": reason} for case, reason in result.skipped],
        "modules": TEST_MODULES,
        "output": stream.getvalue(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real-Postgres backend integration coverage.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    args = parser.parse_args()

    summary = run_integration_suite()
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(summary["output"], end="")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
