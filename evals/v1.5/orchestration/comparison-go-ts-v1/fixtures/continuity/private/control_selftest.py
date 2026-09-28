#!/usr/bin/env python3
"""Synthetic checker controls only; this does not call the actual memory API."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from verify_continuity import inspect

ROOT = Path(__file__).resolve().parents[1]
GOOD = ROOT / "private/controls/good"


def case(locale: str, condition: str, mutation: str | None) -> dict:
    with tempfile.TemporaryDirectory(prefix="opensocrates-cont-control-") as temporary:
        root = Path(temporary)
        candidate = root / "candidate"
        source = root / "source"
        shutil.copytree(GOOD / locale, candidate)
        source.mkdir()
        if condition == "disabled_memory_with_equivalent_note":
            shutil.copyfile(ROOT / f"private/maintained_note.{locale}.md", source / "maintained_note.md")
        shutil.copyfile(ROOT / "public/current-source.md", source / "current-source.md")
        state = root / "state.json"
        receipt = json.loads((GOOD / "synthetic_state_receipt.json").read_text())
        if condition == "disabled_memory_with_equivalent_note":
            receipt["projection_status"] = "disabled"
            receipt["projected_record_ids"] = []
        if mutation == "resurrected_memory":
            receipt["persisted_record_ids"].append("2a6ef571-6bcc-447e-94cd-64939f350106")
        elif mutation == "fake_note_projection":
            receipt["projected_record_ids"] = ["2a6ef571-6bcc-447e-94cd-64939f350101"]
        elif mutation == "missing_note_equivalence":
            receipt["maintained_note_equivalent_ids"] = []
        state.write_text(json.dumps(receipt))
        artifact = json.loads((candidate / "continuation.json").read_text())
        if mutation == "stale_source":
            artifact["source_revision"] = 1
            artifact["p1_delay_minutes"] = 45
        elif mutation == "lost_focus":
            artifact["focus_rule"] = ""
        elif mutation == "promoted_proposal":
            artifact["proposal_accepted"] = True
        elif mutation == "resurrected_output":
            (candidate / "handoff.md").write_text((candidate / "handoff.md").read_text() + "\nwest-demo\n")
        elif mutation == "wrong_note":
            (source / "maintained_note.md").write_text("A mismatched note")
        elif mutation == "leaked_note_into_memory":
            shutil.copyfile(ROOT / f"private/maintained_note.{locale}.md", source / "maintained_note.md")
        elif mutation == "allowed_paraphrase":
            artifact["notification_target"] = "simulated outbox" if locale == "en" else "모의 발송함"
            artifact["viewer_permission"] = "view only" if locale == "en" else "조회만"
            artifact["focus_rule"] = "keep focus after rerender" if locale == "en" else "새로고침 후 초점 유지"
        (candidate / "continuation.json").write_text(json.dumps(artifact, ensure_ascii=False))
        return inspect(candidate, locale, condition, state, source, allow_synthetic_state=True)


def main() -> int:
    expected = {"stale_source": "continuity_correction", "lost_focus": "continuity_retained_intent", "promoted_proposal": "continuity_proposal_pending", "resurrected_output": "continuity_scoped_forget_output", "resurrected_memory": "continuity_memory_state", "wrong_note": "continuity_note_equivalence", "fake_note_projection": "continuity_memory_state", "missing_note_equivalence": "continuity_memory_state", "leaked_note_into_memory": "continuity_note_absent"}
    results = []
    for locale in ("en", "ko"):
        for condition in ("scoped_disposable_memory", "disabled_memory_with_equivalent_note"):
            good = case(locale, condition, None)
            results.append({"locale": locale, "condition": condition, "control": "good", "passed": good["passed"]})
            paraphrase = case(locale, condition, "allowed_paraphrase")
            results.append({"locale": locale, "condition": condition, "control": "allowed_paraphrase", "passed": paraphrase["passed"]})
            for mutation, check_id in expected.items():
                if mutation in ("wrong_note", "fake_note_projection", "missing_note_equivalence") and condition != "disabled_memory_with_equivalent_note":
                    continue
                if mutation == "leaked_note_into_memory" and condition != "scoped_disposable_memory":
                    continue
                wrong = case(locale, condition, mutation)
                found = any(item["id"] == check_id and item["passed"] is False for item in wrong["checks"])
                results.append({"locale": locale, "condition": condition, "control": mutation, "rejected": not wrong["passed"] and found})
    okay = all(item.get("passed", item.get("rejected", False)) for item in results)
    print(json.dumps({"passed": okay, "controls": results}, sort_keys=True))
    return 0 if okay else 1


if __name__ == "__main__":
    raise SystemExit(main())
