#!/usr/bin/env python3
"""External fixture check; state receipt comes from harness-owned memory API readback."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect(candidate: Path, locale: str, condition: str, state_receipt: Path | None, source_root: Path | None, *, allow_synthetic_state: bool = False) -> dict:
    checks = []

    def add(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"id": name, "passed": bool(passed), "detail": detail[:180]})

    current = json.loads((ROOT / "public/source-v2.json").read_text())
    setup = json.loads((ROOT / "private/harness_setup.json").read_text())
    output = json.loads((candidate / "continuation.json").read_text())
    handoff = (candidate / "handoff.md").read_text()
    current_source = source_root / "current-source.md" if source_root else None
    current_bytes_ok = bool(current_source and current_source.is_file() and hashlib.sha256(current_source.read_bytes()).digest() == hashlib.sha256((ROOT / "public/current-source.md").read_bytes()).digest())
    mirrored = bool(current_source and current_source.is_file() and f"Revision: {current['revision']}" in current_source.read_text() and f"P1 delay: {current['p1_delay_minutes']} minutes" in current_source.read_text())
    add("continuity_current_source_bytes", current_bytes_ok and mirrored, "tracked Markdown matches final source bytes and revision/P1 facts")
    joined = (json.dumps(output, ensure_ascii=False) + "\n" + handoff).lower()
    add("continuity_correction", output.get("source_revision") == current["revision"] and output.get("p1_delay_minutes") == current["p1_delay_minutes"] and str(current["p1_delay_minutes"]) in output.get("side_answer", "") and str(current["p1_delay_minutes"]) in handoff, "current source and side question")
    add("continuity_source_lineage", any(mark in joined for mark in ("source-v2", "service-policy@2", "revision 2", "2판")) and any(mark in joined for mark in ("stale", "superseded", "outdated", "old revision", "낡은", "이전 판", "대체", "옛 자료")), "current citation and old-source status")
    stack = output.get("backend") == "Go" and output.get("frontend") == "TypeScript"
    fake = any(term in str(output.get("notification_target", "")).lower() for term in ("fake outbox", "simulated outbox", "local outbox", "가짜 발송함", "모의 발송함", "실제 발송 없음"))
    viewer = any(term in str(output.get("viewer_permission", "")).lower() for term in ("read only", "read-only", "view only", "읽기 전용", "조회만", "쓰기 권한 없음"))
    focus = str(output.get("focus_rule", "")).lower()
    focus_valid = any(term in focus for term in ("focus", "포커스", "초점")) and any(term in focus for term in ("refresh", "reload", "rerender", "새로고침", "다시 그림", "갱신"))
    add("continuity_retained_intent", stack and fake and viewer and focus_valid, "settled stack, outbox, viewer and post-starter accepted focus")
    add("continuity_proposal_pending", output.get("proposal_accepted") is False and str(output.get("unassigned_handover_owner", "")).lower() in ("pending", "보류", "미정"), "proposal not promoted; unresolved owner pending")
    add("continuity_scoped_forget_output", "west-demo" not in joined, "deleted temporary record absent")
    add("continuity_language", (len(re.findall(r"[가-힣]", handoff)) >= 30) if locale == "ko" else (len(re.findall(r"[가-힣]", handoff)) == 0 and len(handoff.split()) >= 55), "language-matched handoff")
    if state_receipt:
        receipt = json.loads(state_receipt.read_text())
        required_retained = set(setup["postconditions"]["retained_record_ids"])
        deleted = setup["postconditions"]["deleted_record_absent"]
        persisted = set(receipt.get("persisted_record_ids", []))
        projected = set(receipt.get("projected_record_ids", []))
        stale_id = setup["postconditions"]["stale_record_id"]
        proposal_id = setup["postconditions"]["unaccepted_record_id"]
        before = hashlib.sha256((ROOT / "private/harness_initial_source.md").read_bytes()).hexdigest()
        after = hashlib.sha256((ROOT / "public/current-source.md").read_bytes()).hexdigest()
        verified = receipt.get("api_readback_verified") is True and receipt.get("correction_replayed") is True and receipt.get("scoped_forget_applied") is True and receipt.get("current_source_before_sha256") == before and receipt.get("current_source_after_sha256") == after and (allow_synthetic_state or receipt.get("control_only") is not True)
        persisted_ok = required_retained <= persisted and stale_id in persisted and proposal_id in persisted and deleted not in persisted
        if condition == "scoped_disposable_memory":
            projection_ok = receipt.get("projection_status") in ("available", "stale") and required_retained <= projected and deleted not in projected
            add("continuity_memory_state", verified and persisted_ok and projection_ok, "harness persisted readback and available/stale native memory projection")
        else:
            equivalent = set(receipt.get("maintained_note_equivalent_ids", []))
            note_ok = receipt.get("projection_status") == "disabled" and not projected and (required_retained | {stale_id, proposal_id}) <= equivalent
            add("continuity_memory_state", verified and persisted_ok and note_ok, "persisted readback; disabled empty projection; separate equivalent maintained note")
    else:
        add("continuity_memory_state", False, "harness memory readback receipt missing")
    if condition == "disabled_memory_with_equivalent_note":
        note_file = ROOT / f"private/maintained_note.{locale}.md"
        materialized = source_root / "maintained_note.md" if source_root else None
        add("continuity_note_equivalence", bool(materialized and materialized.is_file() and hashlib.sha256(materialized.read_bytes()).digest() == hashlib.sha256(note_file.read_bytes()).digest()), "exact maintained-note bytes")
    else:
        leaked_note = source_root / "maintained_note.md" if source_root else None
        add("continuity_note_absent", bool(source_root and not leaked_note.exists()), "memory arm has no maintained-note source")
    return {"passed": all(item["passed"] for item in checks), "checks": checks, "limitations": ["Narrative judgment and clarification timing require separately observable public messages or human semantic review."]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--locale", choices=("en", "ko"), required=True)
    parser.add_argument("--condition", choices=("scoped_disposable_memory", "disabled_memory_with_equivalent_note"), required=True)
    parser.add_argument("--state-receipt", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--control-selftest", action="store_true", help="allow synthetic harness receipt only for oracle controls")
    args = parser.parse_args()
    result = inspect(args.candidate, args.locale, args.condition, args.state_receipt, args.source_root, allow_synthetic_state=args.control_selftest)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
