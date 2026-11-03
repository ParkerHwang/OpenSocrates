"""JSON report and the short human summary."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from bench.contract import REASON_CODES


def write_outputs(report: dict[str, Any], report_path: Path, summary_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_canonical(report), encoding="utf-8")
    summary_path.write_text(render_summary(report), encoding="utf-8")


def render_summary(report: dict[str, Any]) -> str:
    lines = [
        "# OpenSocrates v2 public bench",
        "",
        f"Mode: {report['mode']}",
        f"Live models invoked: {_yes(report['live_models_invoked'])}",
        f"Verified model calls: {report['model_evidence']['verified_model_calls']}",
        f"Unverified model-call rows: {report['model_evidence']['unverified_model_calls']}",
        f"Command processes started: {report['model_evidence']['command_processes_started']}",
        f"Command envelopes received: {report['model_evidence']['command_envelopes_received']}",
        "Codex selector invoked: no",
        "Effect sizes computed: no",
        "Comparison allowed: no",
        f"Envelope: {report['envelope']}",
        f"Skill audit: {report['skill_audit']['status']}",
        "",
        report["note"],
        "",
        report["model_evidence"]["rule"],
        "",
        "## Condition slots",
        "",
        "| Condition | Future | Skill bytes | Fixed English headers | SHA-256 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for item in report["conditions"]:
        digest = item["skill_sha256"] or "—"
        lines.append(
            "| {id} | {future} | {size} | {headers} | `{digest}` |".format(
                id=item["id"],
                future=_yes(item["future"]),
                size=item["skill_bytes"],
                headers=_yes(item["forces_fixed_english_headers"]),
                digest=digest,
            )
        )
    lines.extend(_pin_lines(report))
    lines.extend(
        [
            "",
            "## Case rows",
            "",
            "| Case | Condition | Status | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in report["results"]:
        lines.append(
            "| {case} | {condition} | {status} | {detail} |".format(
                case=row.get("case_id") or "—",
                condition=row.get("condition") or "—",
                status=row["status"],
                detail=_cell(row["reason"]),
            )
        )
    lines.extend(
        [
            "",
            "## Row counts",
            "",
            "These counts are rows in this run. They are not a pass rate.",
            "",
        ]
    )
    lines.extend(_count_lines(report["counts"]["results"]))
    lines.extend(
        [
            "",
            "## Classifier probes",
            "",
            "Probes exercise reason codes. They are not cases and are not model results.",
            "script-envelope is a local process with a forged attestation.",
            "harness-attestation-shape checks a helper and does not invoke a host.",
            "",
            "| Probe | Expected | Actual | Matched |",
            "| --- | --- | --- | --- |",
        ]
    )
    for probe in report["classifier_probes"]:
        lines.append(
            f"| {probe['id']} | {probe['expected_status']} | {probe['status']} | {_yes(probe['matched'])} |"
        )
    if report["skill_audit"]["errors"]:
        lines.extend(["", "## Skill audit errors", ""])
        lines.extend(f"- {error}" for error in report["skill_audit"]["errors"])
    lines.append("")
    return "\n".join(lines)


def _pin_lines(report: dict[str, Any]) -> list[str]:
    pin = None
    for item in report["conditions"]:
        if item["id"] == "output_brief":
            pin = item.get("pin")
    if not isinstance(pin, dict):
        return []
    tip = pin.get("tip_not_loaded") if isinstance(pin.get("tip_not_loaded"), dict) else {}
    return [
        "",
        "## output_brief pin",
        "",
        f"Loaded: {pin.get('loaded')}",
        f"Documented commit: `{pin.get('commit')}`",
        f"Documented blob: `{pin.get('git_blob')}`",
        f"Tip not loaded: `{tip.get('commit')}` blob `{tip.get('git_blob')}`",
        "",
        str(tip.get("coordination") or ""),
    ]


def count_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row["status"] for row in rows)
    return {code: int(counts.get(code, 0)) for code in REASON_CODES}


def exit_code(report: dict[str, Any]) -> int:
    if report["skill_audit"]["status"] != "pass":
        return 1
    if any(row["status"] in {"input_error", "scorer_error"} for row in report["results"]):
        return 1
    if any(not probe["matched"] for probe in report["classifier_probes"]):
        return 1
    return 0


def _count_lines(counts: dict[str, int]) -> list[str]:
    lines = ["| Status | Rows |", "| --- | ---: |"]
    lines.extend(f"| {code} | {counts[code]} |" for code in REASON_CODES)
    return lines


def _cell(value: str) -> str:
    compact = " ".join(value.split())
    compact = compact.replace("|", "/")
    if len(compact) <= 180:
        return compact
    return compact[:179] + "…"


def _yes(value: bool) -> str:
    return "yes" if value else "no"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
