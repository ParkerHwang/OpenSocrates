"""Behavior checks for the experimental, non-verifying output scan."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugin-src/experimental-output-brief/skills/output-brief/scripts/evidence_scan.py"
SPEC = importlib.util.spec_from_file_location("experimental_evidence_scan", SCRIPT)
assert SPEC and SPEC.loader
scan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan)


class EvidenceScanChecks(unittest.TestCase):
    def test_changed_year_is_flagged_and_equivalent_format_is_not(self):
        source = "The deadline is 2026-03-01."
        changed = scan.analyze([], source, "Deadline: 2027-03-01.")
        same = scan.analyze([], source, "Deadline: March 1, 2026.")
        self.assertIn("novel_date", {f["kind"] for f in changed["findings"]})
        self.assertEqual(same["findings"], [])
        self.assertFalse(same["verified"])

    def test_unsupported_commitment_is_only_a_review_cue(self):
        report = scan.analyze([], "The venue is still under consideration.", "The venue is booked.")
        self.assertIn("commitment", {f["kind"] for f in report["findings"]})
        text = scan.render(report)
        self.assertIn("Review cues only", text)
        self.assertIn("RESULT: NOT VERIFIED", text)
        self.assertNotIn("[HIGH]", text)

    def test_negated_confirmation_is_not_reported_as_a_commitment(self):
        source = "The venue is not yet confirmed."
        report = scan.analyze([], source, "The venue is not yet confirmed.")
        self.assertNotIn("commitment", {f["kind"] for f in report["findings"]})

    def test_known_correct_arithmetic_can_be_flagged(self):
        report = scan.analyze([], "There are 24 seats; 3 are reserved.", "21 seats remain.")
        self.assertIn("novel_number", {f["kind"] for f in report["findings"]})
        self.assertIn("calculated value", scan.render(report))

    def test_presence_is_not_support_for_an_attributed_fact(self):
        report = scan.analyze(
            [], "Kickoff is 3 March. Deadline is 20 March.", "The deadline is 3 March."
        )
        self.assertFalse(report["verified"])
        self.assertIn("wrong person, item, or event", scan.render(report))

    def test_cli_requires_comparison_and_does_not_write_source_files(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "source.txt"
            draft = folder / "draft.txt"
            source.write_text("There are 24 seats.", encoding="utf-8")
            draft.write_text("There are 24 seats.", encoding="utf-8")
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            missing = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(draft)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(missing.returncode, 0)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    str(source),
                    "--output",
                    str(draft),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertFalse(json.loads(result.stdout)["verified"])
            self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir()})

    def test_chat_text_can_be_scanned_via_stdin_without_files(self):
        payload = {
            "sources": ["There are 24 seats."],
            "prompt": "",
            "output": "There are 25 seats.",
        }
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--stdin-json", "--json"],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                check=False,
                cwd=directory,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn(
                "novel_number", {f["kind"] for f in json.loads(result.stdout)["findings"]}
            )
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
