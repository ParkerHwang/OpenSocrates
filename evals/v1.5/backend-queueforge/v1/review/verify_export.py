"""Verify public export, counts and accounting without a model or a server."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def verify():
    manifest = read(ROOT / "export-manifest.json")
    for relative, item in manifest["files"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == item["export_sha256"], relative
    summary = read(ROOT / "review/summary.json")
    assert len(summary["calls"]) == len(summary["stages"]) == 9
    assert len(summary["cells"]) == 99
    assert summary["human_scores"] is None and summary["backend_model_echo"] is None
    for arm, total in summary["development_totals"].items():
        calls = [read(ROOT / "evidence" / arm / f"stage{s}/call.json") for s in (1, 2, 3)]
        assert total["attempted_model_calls"] == 3
        for call in calls:
            assert call["model"] == "gpt-6-sol" and call["effort"] == "medium"
            assert call["process_success"] and call["attempt"] == 1
            assert len(call["usage_reports"]) == 1
        for key, actual in total["usage"].items():
            values = [c["usage"].get(key) for c in calls]
            expected = sum(values) if all(x is not None for x in values) else None
            assert actual == expected, (arm, key)
        assert total["tool_actions"] == sum(c["tool_actions_started_or_completed"] for c in calls)
        assert total["failed_tool_actions"] == sum(c["failed_tool_actions"] for c in calls)
        for stage in (1, 2, 3):
            path = ROOT / "evidence" / arm / f"stage{stage}"
            state = read(path / "stage.json")
            scenarios = read(path / "acceptance.json")["scenarios"]
            assert len(scenarios) == (8 if stage == 1 else 19)
            assert sum(x["status"] == "pass" for x in scenarios) == (8 if stage == 1 else 18 if stage == 2 else 19)
            assert state["own_tests_pass"] is (not (arm == "v1.5.0-rc" and stage in (2, 3)))
            for relative, digest in state["source_files"].items():
                candidate = ROOT / "snapshots" / arm / f"stage{stage}" / relative
                if candidate.exists():
                    source = manifest["files"][str(candidate.relative_to(ROOT))]
                    assert source["source_sha256"] == digest
    ops = read(ROOT / "review/memory-operations.json")
    assert len(ops["operations"]) == 13 and ops["counts"] == {"recall": 3, "checkpoint": 4, "inspect": 6}
    assert ops["all_ok"]
    for stage, expected in ((2, 18), (3, 81)):
        rows = read(ROOT / f"evidence/performance-v2/stage{stage}/summary.json")
        assert len(rows) == expected
        assert {r["config"]["index"] for r in rows} == set(range(expected))
        for row in rows:
            if row.get("unavailable_reason"):
                continue
            m = row["phases"]["measure"]
            seconds = row["config"]["measure_seconds"]
            assert m["successful_rps"] == m["window_successful_http"] / seconds
            assert m["completed_jobs_per_second"] == m["window_completed_jobs"] / seconds
            assert m["successful_http"] == m["window_successful_http"] + m["drain_successful_http"]
    failed = read(ROOT / "review/failure-ledger.json")
    assert failed["count"] == len(failed["all_nonzero_commands"]) == 24
    assert failed["invalid_original_performance_cells"] == 6
    print(f"QueueForge export: PASS ({len(manifest['files'])} files; 9 calls; 99 corrected load cells; original failures retained)")


if __name__ == "__main__":
    verify()
