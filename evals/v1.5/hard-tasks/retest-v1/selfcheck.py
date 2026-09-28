"""Zero-model controls for new capture and supplemental measurement boundaries."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import office_display
import runner
from openpyxl import Workbook


def main():
    raw = "\n".join(
        json.dumps(event)
        for event in (
            {
                "type": "item.completed",
                "item": {
                    "id": "p",
                    "type": "agent_message",
                    "text": "A question before the final message.",
                },
            },
            {
                "type": "item.started",
                "item": {"id": "unfinished", "type": "command_execution", "command": "pending"},
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "a",
                    "type": "command_execution",
                    "command": "launch.sh decision codex",
                    "exit_code": 0,
                    "status": "completed",
                    "aggregated_output": '{"status":"unavailable","reason":"invalid_decision_request","diagnostic":{"field_path":"$.decision","code":"ascii_alphanumeric_1_to_64"}}\n{"status":"prepared","applied":"unverified"}',
                },
            },
            {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}},
        )
    )
    captured = runner.capture(raw, Path("/private/tmp/selfcheck"))
    assert len(captured["public_messages"]) == 1
    assert captured["tool_actions_started_or_completed"] == 2
    assert captured["incomplete_tool_actions"] == 1
    assert captured["usage"]["cached_input_tokens"] is None
    assert captured["usage"]["cache_write_input_tokens"] is None
    assert captured["usage"]["reasoning_output_tokens"] is None
    assert [p["status"] for p in captured["native_output_projections"]] == [
        "unavailable",
        "prepared",
    ]
    assert captured["native_output_projections"][0]["diagnostic"]["field_path"] == "$.decision"
    for format_code in ("₩#,##0", '"KRW "#,##0', "[$$-409]#,##0", '#,##0"원"'):
        assert office_display.currency_format(format_code)
    for format_code in ("General", "0", '#,##0"명"', "[$-409]0"):
        assert not office_display.currency_format(format_code)

    with tempfile.TemporaryDirectory(prefix="opensocrates-office-display-") as temporary:
        root = Path(temporary)
        workbook = Workbook()
        schedule = workbook.active
        schedule.title = "일정"
        schedule.append(["attendees", "capacity"])
        schedule.append([16, 20])
        budget = workbook.create_sheet("예산")
        budget.append(["key", "value"])
        for field, count in (
            ("assigned_count", 66),
            ("mandatory_count", 60),
            ("optional_count", 6),
        ):
            budget.append([field, count])
        workbook.save(root / "operations.xlsx")
        assert office_display.check(root)["counts_not_currency"] is True
        budget["B2"].number_format = '"₩"#,##0'
        workbook.save(root / "operations.xlsx")
        bad = office_display.check(root)
        assert bad["counts_not_currency"] is False
        assert [(x["sheet"], x["cell"]) for x in bad["violations"]] == [("예산", "B2")]
        budget.delete_rows(4)
        workbook.save(root / "operations.xlsx")
        assert office_display.check(root)["status"] == "unassessable"
        (root / "operations.xlsx").write_bytes(b"corrupt fixture")
        assert office_display.check(root)["counts_not_currency"] is None
    print(
        "PASS: public messages, unfinished attempts, native diagnostics, null usage; count/currency/locale/missing/corrupt workbook controls. Zero model calls."
    )


if __name__ == "__main__":
    main()
