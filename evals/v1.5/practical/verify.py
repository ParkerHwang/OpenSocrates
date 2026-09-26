"""Offline integrity and accounting; does not rerun an outcome or require auth."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    manifest = read(HERE / "manifest.v1.json")
    for name, expected in manifest["files"].items():
        assert sha(ROOT / name) == expected, name
    lock = read(HERE / "outcome-lock.v1.json")
    for name, expected in lock["files"].items():
        assert sha(HERE / name) == expected, name
    starts = list((HERE / "results").glob("*/call-*.started.json"))
    assert len(starts) == 20 <= manifest["limits"]["initial_model_invocations"]
    for path in starts:
        initial = read(path)
        receipt = read(path.with_name(path.name.replace(".started", "")))
        assert (initial["model"], initial["effort"]) == (manifest["model"], manifest["effort"])
        assert initial["client_sha256"] == manifest["client"]["sha256"]
        assert receipt["process_success"]
        assert receipt["billed_cost"] is None and receipt["server_echoed_model"] is None
        for value in receipt["usage"].values():
            assert value is None or (type(value) is int and value >= 0)
    summary = read(HERE / "summary.v1.json")
    assert len(summary["rows"]) == 12
    for row in summary["rows"]:
        folder = HERE / "results" / (row["scenario"] + "--" + row["arm"])
        result = read(folder / "result.json")
        assert result["auth_copies_removed"] and result["artifact_and_state_checks_pass"]
        calls = [read(folder / name) for name in result["calls"]]
        assert row["model_invocations"] == len(calls)
        assert row["tool_actions"] == sum(
            call["tool_actions_started_or_completed"] for call in calls
        )
        for key, value in row["usage"].items():
            values = [call["usage"].get(key) for call in calls]
            assert value == (sum(values) if all(x is not None for x in values) else None)
    assert read(HERE / "host-before.json") == read(HERE / "host-after.json")["snapshot"]
    print(
        "Practical comparison integrity: PASS (20 calls; 12 episodes; immutable outcomes; nulls preserved)"
    )


if __name__ == "__main__":
    verify()
