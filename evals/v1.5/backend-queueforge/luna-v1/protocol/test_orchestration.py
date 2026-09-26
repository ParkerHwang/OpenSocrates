"""Non-model controls for the bounded Luna dispatch and global access stop."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("luna_run", Path(__file__).with_name("run.py"))
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


class DispatchControls(unittest.TestCase):
    def exercise(self, blocked):
        with tempfile.TemporaryDirectory(prefix="luna-orchestration-control-") as temporary:
            root = Path(temporary)
            seen = []
            ids = ["vanilla", "v1.4.0", "v1.5.0-rc"]
            manifest = {"arms": [{"id": x} for x in ids], "development_order": {str(s): ids[s-1:] + ids[:s-1] for s in (1, 2, 3)}}

            def setup(_manifest, arm, base):
                code = base / "codex"
                code.mkdir()
                (code / "auth.json").write_text("synthetic test canary")
                workspace = root / arm["id"]
                workspace.mkdir()
                return {"arm": arm, "codex": code, "workspace": workspace, "stages": {}}

            def invoke(_manifest, state, stage):
                if state.get("access_blocked"):
                    return
                seen.append((state["arm"]["id"], stage))
                if blocked:
                    state["access_blocked"] = True

            def qualify(state, stage):
                folder = root / "evidence" / state["arm"]["id"] / f"stage{stage}"
                for name, data in [("acceptance.json", {"passed": True, "scenarios": []}), ("own-tests.json", {"exit_code": 0}), ("build.json", {})]:
                    run.save(folder / name, data)

            with patch.object(run, "ROOT", root), patch.object(run, "setup_arm", setup), patch.object(run, "invoke", invoke), patch.object(run, "qualify_stage", qualify), patch.object(run, "measure", return_value=[]):
                run.execute(manifest)
            self.assertTrue(all(json.loads((root / "evidence" / arm / "cleanup.json").read_text())["auth_copy_removed"] for arm in ids))
            return seen

    def test_first_access_failure_stops_all_later_outcome_calls(self):
        self.assertEqual(self.exercise(True), [("vanilla", 1)])

    def test_success_keeps_exact_nine_calls_and_fresh_stage_order(self):
        seen = self.exercise(False)
        self.assertEqual(seen[0], ("vanilla", 1))
        self.assertEqual(len(seen), 9)
        self.assertEqual(set(seen), {(arm, stage) for arm in ("vanilla", "v1.4.0", "v1.5.0-rc") for stage in (1, 2, 3)})
        self.assertEqual([s for _, s in seen], [1]*3 + [2]*3 + [3]*3)


if __name__ == "__main__":
    unittest.main()
