from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from boundary_gate import DECISION, evaluate


class BoundaryGateControls(unittest.TestCase):
    def test_exact_evidence_accepts_and_tampering_fails(self):
        self.assertTrue(evaluate()["accepted_component_evidence"])
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            decision = json.loads(DECISION.read_text())
            original = root / "result.json"
            shutil.copyfile(decision["original_probe_result_path"], original)
            shutil.copyfile(DECISION.parent / decision["reconciliation_path"],
                            root / decision["reconciliation_path"])
            decision["original_probe_result_path"] = str(original)
            local = root / "decision.json"
            local.write_text(json.dumps(decision))
            self.assertTrue(evaluate(local)["accepted_component_evidence"])
            original.write_bytes(original.read_bytes() + b" ")
            self.assertFalse(evaluate(local)["accepted_component_evidence"])
            original.write_bytes(Path(json.loads(DECISION.read_text())[
                "original_probe_result_path"]).read_bytes())
            (root / decision["reconciliation_path"]).unlink()
            self.assertFalse(evaluate(local)["accepted_component_evidence"])


if __name__ == "__main__":
    unittest.main()
