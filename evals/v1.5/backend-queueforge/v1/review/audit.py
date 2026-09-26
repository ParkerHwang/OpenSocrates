"""Independently recompute numeric summaries from retained samples after loads."""

import collections
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PRODUCT = ROOT.parent / "OpenSocrates-v1.5.0-implementation"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def main():
    assert (ROOT / "evidence/performance-v2/completed.json").exists()
    original = read(ROOT / "protocol/manifest.json")
    for rel, expected in original["files"].items():
        assert sha(ROOT / rel) == expected, rel
    for rel, expected in original["helper_files"].items():
        assert sha(PRODUCT / rel) == expected, rel
    assert sha(Path(original["client"]["path"])) == original["client"]["sha256"]
    for arm in original["arms"]:
        if arm.get("archive_path"):
            assert sha(Path(arm["archive_path"])) == arm["archive_sha256"]
    audits, total_samples = [], 0
    for stage in (2, 3):
        rows = read(ROOT / f"evidence/performance-v2/stage{stage}/summary.json")
        for row in rows:
            cfg = row["config"]
            folder = ROOT / f"evidence/performance-v2/stage{stage}" / cfg["arm"] / f"cell-{cfg['index']:03d}"
            if row.get("unavailable_reason"):
                audits.append({"config": cfg, "status": "unavailable", "reason": row["unavailable_reason"]})
                continue
            receipts = read(folder / "compression-and-cleanup.json")
            raw = gzip.decompress((folder / "generator.json.gz").read_bytes())
            assert hashlib.sha256(raw).hexdigest() == receipts["generator.json"]["sha256"]
            assert sha(folder / "generator.json.gz") == receipts["generator.json"]["gzip_sha256"]
            data = json.loads(raw)
            total_samples += len(data["samples"])
            phase_counts = {}
            for phase in ("warmup", "measure"):
                samples = [x for x in data["samples"] if x["phase"] == phase]
                m = row["phases"][phase]
                assert len(samples) == m["attempts"] == m["sample_count"]
                phase_counts[phase] = len(samples)
                lower = 0 if phase == "warmup" else cfg["warmup_seconds"] * 1000
                seconds = cfg["warmup_seconds"] if phase == "warmup" else cfg["measure_seconds"]
                upper = lower + seconds * 1000
                windows = [x for x in samples if lower <= x["finish_offset_ms"] < upper]
                successes = sum(x["success"] for x in windows)
                jobs = sum(x["success"] and x["op"] == "complete" for x in windows)
                assert successes / seconds == m["successful_rps"]
                assert jobs / seconds == m["completed_jobs_per_second"]
                assert m["errors"] == sum(bool(x.get("error")) for x in samples)
                assert m["duplicates"] == sum(x["duplicate"] for x in samples)
                assert m["idle_claims"] == sum(x["idle"] for x in samples)
                assert m["status_counts"] == dict(collections.Counter(str(x["status"]) for x in samples))
                for field, metric in (("send_ms", "send_latency_ms"), ("scheduled_ms", "scheduled_latency_ms"), ("lag_ms", "scheduler_lag_ms")):
                    ordered = sorted(x[field] for x in samples)
                    for label, quantile in (("p50", .5), ("p95", .95), ("p99", .99)):
                        expected = ordered[math.floor((len(ordered) - 1) * quantile)] if ordered else None
                        assert m[metric][label] == expected, (cfg, metric, label)
                if cfg["rate"]:
                    assert m["scheduled_count"] == cfg["rate"] * seconds
            audits.append({"config": cfg, "status": "pass", "sample_counts": phase_counts, "raw_sha256": receipts["generator.json"]["sha256"]})
    save(HERE / "measurement-audit.json", {"scope": "Independent Python recomputation from original retained numeric samples, after all loads", "cells": audits, "total_samples_including_warmup": total_samples, "checked": ["compressed and decompressed hashes", "attempts", "status counts", "window throughput", "completed jobs", "errors", "idle", "duplicates", "all p50/p95/p99 send/schedule/lag order statistics", "fixed arrival counts"], "conservation_evidence": "runner public API pre/post state receipts; separately reviewed", "model_calls": 0})
    app_states = []
    for arm in ("vanilla", "v1.4.0", "v1.5.0-rc"):
        for stage in (1, 2, 3):
            receipt = read(ROOT / "evidence" / arm / f"stage{stage}/stage.json")
            for relative, expected in receipt["source_files"].items():
                assert sha(ROOT / "snapshots" / arm / f"stage{stage}" / relative) == expected
                if stage == 3:
                    assert sha(ROOT / "apps" / arm / relative) == expected
            build = read(ROOT / "evidence" / arm / f"stage{stage}/build.json")
            for kind in ("server", "race"):
                assert sha(ROOT / "evidence" / arm / f"stage{stage}/bin" / kind) == build[kind]["sha256"]
            app_states.append({"arm": arm, "stage": stage, "source_commit": receipt["source_commit"], "source_and_binaries_unchanged": True})
    active = Path("$USER_HOME/.codex/plugins/cache/opensocrates/opensocrates/1.4.0/skills/opensocrates/SKILL.md")
    agent = PRODUCT / ".codex/agents/opensocrates_bilingual_reviewer.toml"
    config = Path("$USER_HOME/.codex/config.toml")
    assert sha(active) == "6be6a2615b9e90e88519cfbc1cadc385a2fba604b0c047f5cc3cadb7097e9600"
    assert sha(agent) == "324906ab9460043d75202b199167cf2f8590941014a0a06c2459294a2cfb48d5"
    save(HERE / "preservation.json", {"original_manifest_files_unchanged": len(original["files"]), "helper_files_unchanged": len(original["helper_files"]), "client_and_archives_unchanged": True, "generated_artifacts": app_states, "active_controller_sha256": sha(active), "user_agent_sha256": sha(agent), "global_config": {"observed_sha256": sha(config), "mtime_utc": datetime.fromtimestamp(config.stat().st_mtime, timezone.utc).isoformat(), "matches_late_measurement_read": sha(config) == "760363c60a6fdce38c406bdfe958418849e6aca0c3193e67dffd0efb5e4809d8", "limitation": "No experiment-start content digest was frozen. Current mtime precedes model execution; it differs from an earlier repair checkpoint, so equality to that older configuration is not claimed. No task step requested global settings writes; no restoration attempted."}, "disposable_auth_copies_removed": all(read(ROOT / "evidence" / a / "cleanup.json")["auth_copy_removed"] for a in ("vanilla", "v1.4.0", "v1.5.0-rc")), "model_calls": len(list((ROOT / "evidence").glob("*/stage*/call.started.json")))})
    print(json.dumps({"audited_cells": len(audits), "numeric_samples": total_samples, "original_inputs_unchanged": True, "nine_artifact_stages_unchanged": True}))


if __name__ == "__main__":
    main()
