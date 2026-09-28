"""Pure deterministic controls for S lineage, structure and parent gate."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from qualify_s import assess_design, decision, sha, versions_for_cell


ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "fixtures/s_incidentops"
TASK = json.loads((S / "descriptor.json").read_text())["task"]


def add_version(episode: Path, unit: dict, number: int, qualified: bool,
                *, design_marker: str | None = None) -> dict:
    artifacts = []
    for name in unit["owned_paths"]:
        data = (S / "private/controls/good" / name).read_bytes()
        if name == "design.md" and design_marker:
            data += design_marker.encode()
        path = episode / "candidate/versions" / unit["unit_id"] / f"v{number}" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        artifacts.append({"path": name, "sha256": "sha256:" + sha(data)})
    return {"version": number, "qualified": qualified, "artifacts": artifacts}


class SLineageControls(unittest.TestCase):
    def test_only_actual_qualified_design_pairs_with_implementation(self):
        with tempfile.TemporaryDirectory() as raw:
            episode = Path(raw)
            design, implementation = TASK["units"]
            d1 = add_version(episode, design, 1, False, design_marker=" rejected design")
            d2 = add_version(episode, design, 2, True, design_marker=" accepted design")
            i1 = add_version(episode, implementation, 1, False)
            i2 = add_version(episode, implementation, 2, True)
            (episode / "response.json").write_text(json.dumps({"units": [
                {"unit_id": "S-design", "versions": [d1, d2]},
                {"unit_id": "S-implementation", "versions": [i1, i2]},
            ]}))
            result = versions_for_cell({"arm": "D"}, TASK, episode)
            self.assertEqual([item[0] for item in result], [
                "S-design-v1", "S-design-v2", "S-design-v2-S-implementation-v1",
                "S-design-v2-S-implementation-v2",
            ])
            self.assertEqual([item[1] for item in result], ["design", "design", "full", "full"])
            self.assertIn(b"accepted design", result[2][2]["design.md"])
            self.assertNotIn(b"rejected design", result[2][2]["design.md"])

    def test_no_implementation_pair_without_qualified_design(self):
        with tempfile.TemporaryDirectory() as raw:
            episode = Path(raw)
            design, implementation = TASK["units"]
            d1 = add_version(episode, design, 1, False)
            i1 = add_version(episode, implementation, 1, False)
            (episode / "response.json").write_text(json.dumps({"units": [
                {"unit_id": "S-design", "versions": [d1]},
                {"unit_id": "S-implementation", "versions": [i1]},
            ]}))
            with self.assertRaisesRegex(ValueError, "qualified_design"):
                versions_for_cell({"arm": "C"}, TASK, episode)

    def test_exact_version_hash_and_single_author(self):
        with tempfile.TemporaryDirectory() as raw:
            episode = Path(raw)
            candidate = episode / "candidate/artifacts"
            files = {}
            for name in TASK["required_artifacts"]:
                data = (S / "private/controls/good" / name).read_bytes()
                path = candidate / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                files[name] = "sha256:" + sha(data)
            (episode / "response.json").write_text(json.dumps({"candidate_hashes": files}))
            result = versions_for_cell({"arm": "A"}, TASK, episode)
            self.assertEqual([item[1] for item in result], ["design", "full"])
            self.assertEqual(set(result[1][2]), set(TASK["required_artifacts"]))
            (candidate / "design.md").write_text("changed")
            with self.assertRaisesRegex(ValueError, "candidate_changed"):
                versions_for_cell({"arm": "A"}, TASK, episode)

    def test_design_assessment_is_structural_and_parent_decision_explicit(self):
        good = {name: (S / "private/controls/good" / name).read_bytes()
                for name in ("design.json", "design.md")}
        self.assertTrue(assess_design(good)["passed"])
        defective = dict(good)
        value = json.loads(defective["design.json"])
        value["examples"] = []
        defective["design.json"] = json.dumps(value).encode()
        self.assertFalse(assess_design(defective)["passed"])
        with self.assertRaisesRegex(ValueError, "decision_missing"):
            decision({})
        value = {"status": "allow_unassessable_as_pending", "attribution": "parent_explicit", "reference": "parent:boundary-decision"}
        self.assertEqual(decision({"s_browser_transport_decision": value}), value)

    def test_actual_runner_classifies_browser_transport_unknown_separately(self):
        runner = os.environ.get("OPENSOCRATES_SECONDARY_RUNNER")
        if not runner:
            self.skipTest("set OPENSOCRATES_SECONDARY_RUNNER for runner integration control")
        sys.path.insert(0, str(Path(runner) / "evals/v1.5/orchestration/comparison-go-ts-v1"))
        from qualify_main import classification
        pending = {"passed": False, "checks": [
            {"id": "s_api_contract", "passed": True},
            {"id": "s_browser_network_ui", "passed": False, "status": "unassessable"},
        ]}
        judged = classification(pending, 1)
        self.assertEqual(judged["status"], "integration_pending_unassessable")
        self.assertIsNone(judged["subject_defect"])
        self.assertEqual(judged["pending_obligations"], ["s_browser_network_ui"])
        mixed = {"passed": False, "checks": [*pending["checks"],
            {"id": "s_tenant_isolation", "passed": False}]}
        judged = classification(mixed, 1)
        self.assertEqual(judged["status"], "mixed_failure_and_unassessable")
        self.assertTrue(judged["subject_defect"])
        self.assertEqual(judged["failed_obligations"], ["s_tenant_isolation"])


if __name__ == "__main__":
    unittest.main()
