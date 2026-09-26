"""Verify historical preservation and new repair evidence without model calls."""

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical_verifiers(commit):
    # Existing historical verifiers intentionally bind their original product
    # sources. Execute those unchanged scripts against the committed historical
    # tree, not against the deliberately repaired current product schema/guides.
    with tempfile.TemporaryDirectory(prefix="os-repair-history-") as temporary:
        target = Path(temporary)
        proc = subprocess.Popen(["git", "archive", commit], cwd=ROOT, stdout=subprocess.PIPE)
        with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
            archive.extractall(target, filter="data")
        assert proc.wait() == 0
        for script in (
            "evals/v1.5/practical/verify.py",
            "evals/v1.5/verify_pilot_results.py",
            "evals/v1.5/expanded/reviews/astra-xhigh-v4/verify_review.py",
        ):
            subprocess.run([sys.executable, script], cwd=target, check=True)


def verify_usability():
    for name, digest in read(HERE / "usability/manifest.json")["hashes"].items():
        assert sha(ROOT / name) == digest, name
    lock = HERE / "usability/outcomes.lock.json"
    if lock.exists():
        for name, digest in read(lock)["files"].items():
            assert sha(HERE / "usability" / name) == digest, name
        calls = list((HERE / "usability/results").glob("*/call-*.started.json"))
        assert len(calls) <= 4
        for start in calls:
            assert read(start)["model"] == "gpt-6-sol"
            assert read(start)["effort"] == "medium"
            receipt = read(start.with_name(start.name.replace(".started", "")))
            for value in receipt["usage"].values():
                assert value is None or (type(value) is int and value >= 0)
        for cleanup in (HERE / "usability/results").glob("*/cleanup.json"):
            assert read(cleanup)["auth_copy_removed"]
        verify_summary(calls)


def verify_summary(calls):
    summary = read(HERE / "usability/summary.json")
    rubric = read(HERE / "usability/rubric.json")
    assert len(calls) == summary["model_calls"] == summary["completed"] == 4
    assert summary["outcome_retries"] == summary["failed_model_calls"] == 0
    receipts, operations = [], Counter()
    for row in summary["rows"]:
        lane = HERE / "usability/results" / row["locale"]
        stage = row["stage"]
        call = read(lane / f"call-{stage}.json")
        receipts.append(call)
        assert call["turn_completed"] and call["exit_code"] == 0 and not call["timed_out"]
        checks = read(lane / f"checks-{stage}.json")
        assert all(
            checks[key] is True
            for key in rubric["automated_required"] + rubric[f"stage{stage}_required"]
        )
        assert row["artifact"] == read(lane / f"artifact-{stage}.json")
        ops = read(lane / f"operations-{stage}.json")
        assert all(op["status"] == "ok" and op["exit_code"] == 0 for op in ops)
        operations.update(op["operation"] for op in ops)
    assert dict(operations) == summary["memory_operations"]
    for key, total in summary["usage"].items():
        values = [call["usage"].get(key) for call in receipts]
        assert total == (sum(values) if all(x is not None for x in values) else None)


def verify(include_history=False):
    before = read(HERE / "before.json")
    # STATUS.md is an explicitly mutable current planning surface, not an old
    # outcome. Every historical protocol, result, packet and verifier is pinned.
    historical = {
        k: v for k, v in before["historical_files"].items() if k != "evals/v1.5/STATUS.md"
    }
    for name, digest in historical.items():
        assert sha(ROOT / name) == digest, name
    gear = read(HERE / "geardesk/manifest.json")
    for name, digest in gear["files"].items():
        assert sha(HERE / "geardesk" / name) == digest, name
    for arm in gear["integrator_results"]:
        for result in arm["results"]:
            assert result["exit_code"] == 0
            assert result["counts"]["fail"] == result["counts"]["error"] == 0
    native = read(HERE / "native-package.json")
    assert native["model_calls"] == 0 and len(native["results"]) == 2
    assert all(row["status"] == "pass" for row in native["results"])
    verify_usability()
    if include_history:
        historical_verifiers(before["source_commit"])
    print(
        f"Repair integrity: PASS ({len(historical)} historical files unchanged; {len(gear['files'])} portable GearDesk files; packaged native examples; current freeze)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical", action="store_true")
    verify(parser.parse_args().historical)
