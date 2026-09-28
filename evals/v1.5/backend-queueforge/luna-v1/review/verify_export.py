"""Verify the Luna export without imposing a passing outcome or calling a model."""

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
    starts = list((ROOT / "evidence").glob("*/stage*/call.started.json"))
    assert len(starts) == len(summary["calls"]) <= 9
    assert len(summary["stages"]) == 9
    assert len(summary["cells"]) == 99
    assert summary["human_scores"] is None and summary["backend_model_echo"] is None
    for arm, total in summary["development_totals"].items():
        calls = [read(path) for path in sorted((ROOT / "evidence" / arm).glob("stage*/call.json"))]
        assert total["attempted_model_calls"] == len(calls)
        for call in calls:
            assert call["model"] == "gpt-6-luna" and call["effort"] == "medium"
            assert call["attempt"] == 1
            for value in (call.get("usage") or {}).values():
                assert value is None or isinstance(value, int) and value >= 0
        for key, actual in total["usage"].items():
            values = [(c.get("usage") or {}).get(key) for c in calls]
            expected = sum(values) if values and all(x is not None for x in values) else None
            assert actual == expected, (arm, key)
        for stage in (1, 2, 3):
            path = ROOT / "evidence" / arm / f"stage{stage}"
            state = read(path / "stage.json")
            scenarios = read(path / "acceptance.json")["scenarios"]
            observed = next(x for x in summary["stages"] if x["arm"] == arm and x["stage"] == stage)
            for status in ("pass", "fail", "error", "unassessable"):
                assert observed["scenario_counts"][status] == sum(x["status"] == status for x in scenarios)
            assert observed["own_tests_pass"] == state["own_tests_pass"]
            for relative, digest in state.get("source_files", {}).items():
                candidate = ROOT / "snapshots" / arm / f"stage{stage}" / relative
                if candidate.exists():
                    exported = manifest["files"][str(candidate.relative_to(ROOT))]
                    assert exported["source_sha256"] == digest
    for stage, expected in ((2, 18), (3, 81)):
        rows = read(ROOT / f"evidence/performance-stage{stage}/summary.json")
        assert len(rows) == expected
        assert {r["config"]["index"] for r in rows} == set(range(expected))
        for row in rows:
            if row.get("unavailable_reason"):
                continue
            measured = row["phases"]["measure"]
            seconds = row["config"]["measure_seconds"]
            assert measured["successful_rps"] == measured["window_successful_http"] / seconds
            assert measured["completed_jobs_per_second"] == measured["window_completed_jobs"] / seconds
    ops = read(ROOT / "review/memory-operations.json")
    assert ops["total"] == len(ops["operations"])
    assert sum(ops["counts"].values()) == ops["total"]
    print(f"Luna export: PASS ({len(manifest['files'])} files; {len(starts)} counted calls; 99 planned performance cells; outcomes and missingness preserved)")


if __name__ == "__main__":
    verify()
