from __future__ import annotations

import json
import unittest

from tests.backend_contract_harness import run_smoke_checks


class BackendContractSmokeTests(unittest.TestCase):
    def test_smoke_harness_passes_all_contract_checks(self):
        summary = run_smoke_checks()
        failed = [check for check in summary["checks"] if not check["ok"]]
        self.assertTrue(
            summary["all_passed"],
            msg=f"Contract smoke harness found failures:\n{json.dumps(failed, ensure_ascii=False, indent=2)}",
        )


if __name__ == "__main__":
    unittest.main()
