"""Behavior checks for the experimental, non-verifying output scan."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugin-src/experimental-output-brief/skills/output-brief/scripts/evidence_scan.py"
SPEC = importlib.util.spec_from_file_location("experimental_evidence_scan", SCRIPT)
assert SPEC and SPEC.loader
scan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan)


class EvidenceScanChecks(unittest.TestCase):
    def test_changed_year_is_flagged_and_equivalent_format_is_not(self):
        source = "The deadline is 2026-03-01."
        changed = scan.analyze([source], "", "Deadline: 2027-03-01.")
        same = scan.analyze([source], "", "Deadline: March 1, 2026.")
        self.assertIn("novel_date", {f["kind"] for f in changed["findings"]})
        self.assertEqual(same["findings"], [])
        self.assertFalse(same["verified"])

    def test_new_full_date_keeps_year_in_the_review_cue(self):
        report = scan.analyze(["The date is undecided."], "", "The meeting is 2027-03-01.")
        self.assertTrue(
            any(
                f["kind"] == "novel_date" and "2027-03-01" in f["message"]
                for f in report["findings"]
            )
        )
        self.assertFalse(report["input_summary"]["prompt_used_as_source"])

    def test_iso_date_followed_by_korean_particle_is_one_date(self):
        report = scan.analyze(["날짜는 미정입니다."], "", "행사는 2027-03-01로 확정됐습니다.")
        self.assertTrue(
            any(
                f["kind"] == "novel_date" and "2027-03-01" in f["message"]
                for f in report["findings"]
            )
        )

    def test_unsupported_commitment_is_only_a_review_cue(self):
        report = scan.analyze(
            ["The venue is still under consideration."], "", "The venue is booked."
        )
        self.assertIn("commitment", {f["kind"] for f in report["findings"]})
        text = scan.render(report)
        self.assertIn("Review cues only", text)
        self.assertIn("RESULT: NOT VERIFIED", text)
        self.assertNotIn("[HIGH]", text)

    def test_negated_confirmation_is_not_reported_as_a_commitment(self):
        source = "The venue is not yet confirmed."
        report = scan.analyze([source], "", "The venue is not yet confirmed.")
        self.assertNotIn("commitment", {f["kind"] for f in report["findings"]})

    def test_korean_words_are_not_mistaken_for_negation(self):
        for draft in (
            "전체 일정이 확정되었습니다.",
            "미팅 일정이 확정되었습니다.",
            "문제없이 일정이 확정되었습니다.",
            "일정은 미정이나 인원은 24명으로 확정했습니다.",
        ):
            report = scan.analyze(["일정은 미정입니다."], "", draft)
            self.assertIn("commitment", {f["kind"] for f in report["findings"]}, draft)
        report = scan.analyze(["일정은 미정입니다."], "", "일정은 미확정입니다.")
        self.assertNotIn("commitment", {f["kind"] for f in report["findings"]})

    def test_authored_negation_examples(self):
        path = ROOT / "docs/experiments/v2-output-brief/cases/negation.json"
        examples = json.loads(path.read_text(encoding="utf-8"))
        for group in examples["sets"].values():
            for case in group:
                with self.subTest(text=case["text"]):
                    observed = any(
                        scan._present(pattern, case["text"]) for pattern, _ in scan.COMMIT
                    )
                    self.assertEqual(observed, case["expected_affirmed"])

    def test_conditional_confirmation_is_not_an_assertion(self):
        source = "예약은 아직 확정되지 않았습니다."
        draft = "예약이 확정되면 안내드리겠습니다."
        report = scan.analyze([source], "", draft)
        self.assertNotIn("commitment", {f["kind"] for f in report["findings"]})

    def test_full_draft_in_source_is_marked_as_potentially_circular(self):
        draft = "The venue is confirmed for 25 people on 2027-03-01."
        report = scan.analyze(["Source includes the draft: " + draft], "", draft)
        self.assertIn("draft_in_source", {f["kind"] for f in report["findings"]})
        self.assertFalse(report["verified"])

    def test_known_correct_arithmetic_can_be_flagged(self):
        report = scan.analyze(["There are 24 seats; 3 are reserved."], "", "21 seats remain.")
        self.assertIn("novel_number", {f["kind"] for f in report["findings"]})
        self.assertIn("calculated value", scan.render(report))

    def test_presence_is_not_support_for_an_attributed_fact(self):
        report = scan.analyze(
            ["Kickoff is 3 March. Deadline is 20 March."], "", "The deadline is 3 March."
        )
        self.assertFalse(report["verified"])
        self.assertIn("wrong person, item, or event", scan.render(report))

    def test_opt_in_context_shows_source_line_without_claiming_support(self):
        sources = ["The venue holds 24 people.", "The organizer hopes for 30 people."]
        draft = "The venue holds 30 people."
        report = scan.analyze(sources, "", draft)
        self.assertNotIn("source_contexts", report)
        contexts = scan.source_contexts(sources, draft)
        self.assertEqual(contexts["matches"][0]["source"], 2)
        self.assertEqual(contexts["matches"][0]["text"], sources[1])
        self.assertIn("not evidence", contexts["meaning"])
        self.assertFalse(report["verified"])

    def test_context_omits_very_long_line_without_truncating_its_meaning(self):
        contexts = scan.source_contexts(["A" * 1001 + " 30"], "The value is 30.")
        self.assertIsNone(contexts["matches"][0]["text"])

    def test_context_date_with_missing_year_is_labeled(self):
        contexts = scan.source_contexts(["Deadline: March 1, 2027."], "Deadline: March 1.")
        self.assertEqual(contexts["matches"][0]["match_type"], "year_missing")
        self.assertEqual(contexts["matches"][0]["text"], "Deadline: March 1, 2027.")
        other = scan.source_contexts(["Deadline: March 1, 2026."], "Deadline: March 1, 2027.")
        self.assertEqual(other["matches"], [])

    def test_context_escapes_terminal_and_bidirectional_controls(self):
        source = "Capacity 30\x1b]52;c;Zm9v\x07\u202eEND"
        contexts = scan.source_contexts([source], "Capacity 30")
        line = contexts["matches"][0]
        self.assertTrue(line["controls_escaped"])
        self.assertNotIn("\x1b", line["text"])
        self.assertNotIn("\u202e", line["text"])
        self.assertIn("\\u001b", line["text"])
        payload = {"sources": [source], "output": "Capacity 30"}
        for suffix in ([], ["--json"]):
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--stdin-json", "--show-context", *suffix],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertNotIn("\x1b", result.stdout)
            self.assertNotIn("\u202e", result.stdout)

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

    def test_cli_source_lines_are_only_included_when_requested(self):
        source = "The organizer hopes for 30 attendees."
        payload = {"sources": [source], "output": "The venue holds 30 people."}
        base = [sys.executable, str(SCRIPT), "--stdin-json", "--json"]
        ordinary = subprocess.run(
            base, input=json.dumps(payload), capture_output=True, text=True, check=False
        )
        detailed = subprocess.run(
            [*base, "--show-context"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual((ordinary.returncode, detailed.returncode), (0, 0))
        self.assertNotIn(source, ordinary.stdout)
        self.assertIn(source, detailed.stdout)

    def test_quoted_draft_in_prompt_is_not_treated_as_evidence(self):
        draft = "The event is confirmed for 25 people on 2027-03-01."
        report = scan.analyze(
            ["The capacity is 24; the date and booking are undecided."],
            f"Please check this draft: {draft}",
            draft,
        )
        kinds = {item["kind"] for item in report["findings"]}
        self.assertTrue({"novel_date", "novel_number", "commitment"} <= kinds)
        self.assertFalse(report["input_summary"]["prompt_used_as_source"])
        with self.assertRaises(ValueError):
            scan.analyze([], f"Please check: {draft}", draft)

    def test_missing_source_is_reported_as_not_run(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--stdin-json", "--json"],
            input=json.dumps({"sources": [], "prompt": "Check this draft", "output": "Draft"}),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)["ran"])


if __name__ == "__main__":
    unittest.main()
