"""Hash-gated, model-free correction of the frozen QueueForge load schedule."""

import argparse
import datetime
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
ORIGINAL_SHA = "2c490204c344a31cb88169430024114cf7ae6e9ab7e5d62f4e992a2700b54e73"
ARMS = ["vanilla", "v1.4.0", "v1.5.0-rc"]
spec = importlib.util.spec_from_file_location("meter_v2", HERE / "runner.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def verify_original():
    assert sha(ROOT / "protocol/manifest.json") == ORIGINAL_SHA
    original = read(ROOT / "protocol/manifest.json")
    for relative, expected in original["files"].items():
        assert sha(ROOT / relative) == expected, relative
    assert len(list((ROOT / "evidence").glob("*/stage*/call.started.json"))) == 9
    return original


def freeze():
    original = verify_original()
    target = HERE / "manifest.json"
    assert not target.exists(), "measurement manifest is immutable"
    files = {}
    for path in HERE.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and path.name != "manifest.json":
            files[str(path.relative_to(ROOT))] = sha(path)
    artifacts = []
    for stage in (2, 3):
        for arm in ARMS:
            folder = ROOT / "evidence" / arm / f"stage{stage}"
            state = read(folder / "stage.json")
            build = read(folder / "build.json")
            binary = Path(state["server_binary"])
            assert sha(binary) == build["server"]["sha256"]
            for relative, expected in state["source_files"].items():
                assert sha(ROOT / "snapshots" / arm / f"stage{stage}" / relative) == expected
            seed_file = ROOT / "evidence" / f"performance-stage{stage}" / arm / "seed/seed.json"
            seed = read(seed_file)
            for path in [folder / "stage.json", folder / "build.json", folder / "acceptance.json", folder / "own-tests.json", binary, seed_file, *[Path(seed[k]) for k in ("db", "refs", "lifecycle_refs")]]:
                files[str(path.relative_to(ROOT))] = sha(path)
            artifacts.append({"arm": arm, "stage": stage, "source_commit": state["source_commit"], "binary": str(binary.relative_to(ROOT)), "seed": str(seed_file.relative_to(ROOT)), "source_files": state["source_files"], "artifact_gate_pass": all(state[k] for k in ("dependency_locks_unchanged", "own_tests_pass", "api_checks_pass"))})
    manifest = {"schema": "queueforge.measurement-repair/2", "frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "original_manifest_sha256": ORIGINAL_SHA, "original_freeze_commit": "5f8b3a50d48cd15bd3302250e53e3d44f61242e5", "model_calls_before_freeze": 9, "additional_model_calls": 0, "reason": "Closed-loop drain timer started before measurement; original six executed cells are invalid meter observations.", "stage3_feedback_limit": "All final development calls received original invalid or unavailable preliminary load results. Corrected measurement is post-development only.", "artifacts": artifacts, "performance_cells": original["performance_cells"], "limits": {"stage2_seconds": 900, "stage3_seconds": 1800, "total_database_bytes": 2 * 1024**3, "server_gomaxprocs": 4, "generator_gomaxprocs": 2, "warmup_seconds": 3, "drain_seconds": 3, "request_timeout_seconds": 2, "max_inflight": 256}, "failure_handling": "Retain every attempted/skipped cell. Stop the arm after unavailable result, repeated transport failures or exceeded drain budget; no retries. No model calls or candidate edits.", "retention": "Lossless gzip level 1 plus SHA256; owned stopped cell database files removed after metrics/conservation/digests. Original evidence untouched.", "files": files}
    save(target, manifest)
    print(json.dumps({"manifest": str(target), "sha256": sha(target)}), flush=True)


def verify(digest):
    verify_original()
    assert sha(HERE / "manifest.json") == digest
    manifest = read(HERE / "manifest.json")
    for relative, expected in manifest["files"].items():
        assert sha(ROOT / relative) == expected, relative
    for artifact in manifest["artifacts"]:
        for relative, expected in artifact["source_files"].items():
            assert sha(ROOT / "snapshots" / artifact["arm"] / f"stage{artifact['stage']}" / relative) == expected
    return manifest


def compact(directory):
    receipt = {}
    for name in ("generator.json", "result.json"):
        path = directory / name
        if path.exists():
            raw = path.read_bytes()
            packed = gzip.compress(raw, compresslevel=1, mtime=0)
            dest = path.with_suffix(path.suffix + ".gz")
            dest.write_bytes(packed)
            receipt[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "gzip_sha256": sha(dest), "uncompressed_bytes": len(raw), "compressed_bytes": len(packed), "gzip_level": 1}
            path.unlink()
    for suffix in ("", "-wal", "-shm"):
        path = directory / ("cell.sqlite" + suffix)
        if path.exists():
            receipt[path.name] = {"sha256": sha(path), "bytes": path.stat().st_size, "removed_owned_stopped_fixture": True}
            path.unlink()
    save(directory / "compression-and-cleanup.json", receipt)


def execute(digest):
    manifest = verify(digest)
    output = ROOT / "evidence/performance-v2"
    output.mkdir(exist_ok=False)
    save(output / "started.json", {"manifest_sha256": digest, "time": time.time(), "additional_model_calls": 0})

    def shared_cap(_path):
        if bench.size_tree(ROOT / "evidence") > manifest["limits"]["total_database_bytes"]:
            raise RuntimeError("shared 2GiB prepared database cap exceeded")

    bench.check_cap = shared_cap
    for stage in (2, 3):
        rows, stopped = [], {}
        deadline = time.monotonic() + manifest["limits"][f"stage{stage}_seconds"]
        artifacts = {x["arm"]: x for x in manifest["artifacts"] if x["stage"] == stage}
        stage_dir = output / f"stage{stage}"
        for cell in manifest["performance_cells"][str(stage)]:
            arm = cell["arm"]
            reason = stopped.get(arm)
            if time.monotonic() + 60 >= deadline:
                reason = "frozen global wall-time cap"
            if bench.size_tree(ROOT / "evidence") > manifest["limits"]["total_database_bytes"]:
                reason = "frozen global database cap"
            if reason:
                rows.append({"config": cell, "unavailable_reason": reason, "attempted": False})
                save(stage_dir / "summary.json", rows)
                continue
            directory = stage_dir / arm / f"cell-{cell['index']:03d}"
            artifact = artifacts[arm]
            print(json.dumps({"event": "load-start", "stage": stage, "arm": arm, "cell": cell["index"]}), flush=True)
            host = {"load_average": os.getloadavg(), "timestamp": time.time()}
            try:
                result = bench.run_cell(ROOT / artifact["binary"], read(ROOT / artifact["seed"]), cell, directory, {})
            except Exception as error:
                result = {"config": cell, "unavailable_reason": f"{type(error).__name__}: {error}"}
            summary = {k: v for k, v in result.items() if k not in ("samples", "resource_samples", "seed")}
            summary.update(host_before=host, artifact_gate_pass=artifact["artifact_gate_pass"], attempted=True, measurement_version=2)
            save(directory / "summary.json", summary)
            compact(directory)
            rows.append(summary)
            save(stage_dir / "summary.json", rows)
            measured = (result.get("phases") or {}).get("measure", {})
            print(json.dumps({"event": "load-finish", "stage": stage, "arm": arm, "cell": cell["index"], "rps": measured.get("successful_rps"), "jobs_per_second": measured.get("completed_jobs_per_second"), "errors": measured.get("errors"), "unavailable": result.get("unavailable_reason"), "drain_exceeded": result.get("drain_budget_exceeded")}), flush=True)
            if result.get("unavailable_reason") or result.get("stopped_transport_failures") or result.get("drain_budget_exceeded"):
                stopped[arm] = f"Stopped after cell {cell['index']}: " + (result.get("unavailable_reason") or "repeated transport failure or drain budget exceeded")
    verify(digest)
    save(output / "completed.json", {"manifest_sha256": digest, "time": time.time(), "bound_files_unchanged": True, "model_calls": 9, "additional_model_calls": 0})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["freeze", "verify", "execute"])
    parser.add_argument("--sha256")
    args = parser.parse_args()
    if args.mode == "freeze":
        freeze()
    elif args.mode == "verify":
        verify(args.sha256)
        print("All original inputs, corrected tools, binaries, source snapshots and seeds match.")
    else:
        execute(args.sha256)
