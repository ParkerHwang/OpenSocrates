"""Verify frozen identities and public evidence, without model calls or repairs."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MANIFESTS = {
    "direct-v1": "9965e6366b9c7cb6c4b2b303f7f3367271c48364bb9808db1b7cf88f59a6cd2f",
    "direct-v2": "bac6bf212ae255d9eb5d8ab5042218ddd761cf0ce968b48ddb4daa492315d288",
    "integrated-v1": "7bf680daf444710361a5f5bcb208078f988c2d5463bc41480e8084f9ec6e03be",
}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(root, expected):
    for relative, digest in expected.items():
        assert sha(root / relative) == digest, str(root / relative)


def verify_boundary(name, local):
    base = HERE / name
    manifest = read(base / "manifest.json")
    assert sha(base / "manifest.json") == MANIFESTS[name]
    hashes(base, manifest["frozen_files"])
    hashes(ROOT, manifest["helper_files"])
    if name == "direct-v1":
        assert not (base / "results").exists()
        assert (base / "ABANDONED.md").exists()
        return {"frozen_inputs": len(manifest["frozen_files"]), "model_calls": 0}
    export = read(base / "export-map.json")
    assert export["business_source_changed"] is False
    paths = {entry["path"] for entry in export["files"]}
    assert len(paths) == len(export["files"])
    actual = {p.relative_to(base / "evidence").as_posix() for p in (base / "evidence").rglob('*') if p.is_file()}
    assert paths == actual
    entries = {entry["path"]: entry for entry in export["files"]}
    for relative, item in entries.items():
        path = base / "evidence" / relative
        assert sha(path) == item["export_sha256"], relative
        if item["redaction"]:
            assert path.name == "TOOLING.md"
            assert b"<BUNDLED_PYTHON>" in path.read_bytes()
        else:
            assert item["original_sha256"] == item["export_sha256"]
        if local:
            assert sha(base / "results" / relative) == item["original_sha256"], relative
    summaries = {row["id"]: row for row in read(base / "summary.json")["rows"]}
    assert set(summaries) == {cell["id"] for cell in manifest["cells"]}
    total_tools = 0
    usage = {}
    for cell in manifest["cells"]:
        identifier = cell["id"]
        folder = base / "evidence" / identifier
        started, call = read(folder / "call.started.json"), read(folder / "call.json")
        assert started["manifest_sha256"] == sha(base / "manifest.json")
        assert call["manifest_sha256"] == started["manifest_sha256"]
        assert call["call_attempted"] and call["attempt"] == 1
        assert call["started_unix"] >= datetime.fromisoformat(manifest["frozen_at"]).timestamp()
        assert (call["model"], call["effort"]) == (manifest["model"], manifest["effort"])
        assert call["process_success"] and call["exit_code"] == 0 and call["turn_completed"]
        assert call["model_wall_clock_limit"] is None
        assert call["protected_inputs_unchanged"]
        assert read(folder / "cleanup.json")["auth_copy_removed"]
        total_tools += call["tool_actions_started_or_completed"]
        assert len(call["tool_actions"]) == call["tool_actions_started_or_completed"]
        for key, value in call["usage"].items():
            assert value is None or (type(value) is int and value >= 0)
            if value is not None:
                usage[key] = usage.get(key, 0) + value
        assert summaries[identifier]["usage"] == call["usage"]
        snapshot = read(folder / "snapshot.json")["files"]
        for path, digest in snapshot.items():
            assert entries[f"{identifier}/snapshot/{path}"]["original_sha256"] == digest
        inputs = read(folder / "inputs.json")
        for path, digest in inputs.get("protected_paths", inputs.get("protected", {})).items():
            assert snapshot[path] == digest
        if cell.get("from_cell"):
            parent = read(base / "evidence" / cell["from_cell"] / "snapshot.json")["files"]
            for path, digest in parent.items():
                if path not in {"TASK.md", "GUIDANCE.md", "TOOLING.md"}:
                    assert inputs["source_files"][path] == digest, (identifier, path)
        qualification = read(folder / "qualification.json")
        result = qualification["independent"]["result"]
        if name == "direct-v2":
            assert sum(x["passed"] for x in result["checks"]) == result["passed"]
            assert len(result["checks"]) == result["total"]
            assert (summaries[identifier]["passed"], summaries[identifier]["total"]) == (result["passed"], result["total"])
        else:
            assert result["artifact_pass"] == summaries[identifier]["artifact_pass"]
            assert call["package_members_unchanged"] and not call["product_data_tree_created"]
    summary = read(base / "summary.json")
    assert summary["reported_usage_sums"] == usage
    assert summary["model_calls"] == len(manifest["cells"])
    assert summary["complete_cli_turns"] == len(manifest["cells"])
    assert summary["billed_cost"] is None and summary["human_scores"] is None
    return {"frozen_inputs":len(manifest["frozen_files"]),"model_calls":len(manifest["cells"]),
            "exported_files":len(entries),"tools":total_tools,"usage":usage}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true", help="Also check preserved local originals, candidates and cleanup.")
    parser.add_argument("--candidate-root", type=Path, default=ROOT.parent / "work/opensocrates-coding-insert-prompts")
    args = parser.parse_args()
    baseline = read(HERE / "revision-v1/baseline.json")
    hashes(ROOT, baseline["canonical_files"])
    hashes(ROOT, baseline["historical_evaluation_files"])
    if args.local:
        assert sha(ROOT / ".codex/agents/opensocrates_bilingual_reviewer.toml") == baseline["agent_definition_sha256"]
    qualification = read(HERE / "revision-v1/validation.json")
    hashes(ROOT, qualification["runtime_input_hashes"])
    hashes(ROOT, qualification["qualification_input_hashes"])
    assert sha(HERE / "revision-v1/native-release.json") == qualification["native_report_sha256"]
    results = {name: verify_boundary(name, args.local) for name in MANIFESTS}
    access = read(HERE / "revision-v1/access-manifest.json")
    probe = read(HERE / "revision-v1/access-result.json")
    assert sha(HERE / "revision-v1/access_probe.py") == access["runner_sha256"]
    assert sha(ROOT / "evals/v1.5/expanded/harness_v4.py") == access["helper_sha256"]
    assert probe["successful_probe"] and probe["turn_completed"] and probe["exit_code"] == 0
    assert read(HERE / "revision-v1/access-started.json")["started_unix"] >= datetime.fromisoformat(access["frozen_at"]).timestamp()
    assert read(HERE / "revision-v1/access-cleanup.json")["disposable_auth_copy_removed"]
    diagnostic = HERE / "direct-v2/diagnostics"
    frozen = read(diagnostic / "ownership-boundary-v1.manifest.json")
    assert sha(diagnostic / "ownership-boundary-v1.py") == frozen["script_sha256"]
    for case, digest in frozen["snapshots"].items():
        assert sha(HERE / "direct-v2/evidence" / case / "snapshot.json") == digest
    if args.local:
        candidate = args.candidate_root
        hashes(candidate / "candidate-v0.1.0", baseline["old_candidate"])
        hashes(candidate / "candidate-v0.1.1", baseline["corrected_candidate"])
        for version, count in [("candidate-v0.1.0",24),("candidate-v0.1.1",24)]:
            assert len([p for p in (candidate / version).rglob('*') if p.is_file()]) == count
        for directory in ["/private/tmp/opensocrates-specialist-direct-v2-20260927", "/private/tmp/opensocrates-specialist-integrated-v1-20260927"]:
            assert not list(Path(directory).glob("*/profile/home/.codex/auth.json"))
        assert not (Path(access["disposable_root"]) / "profile/home/.codex/auth.json").exists()
    report = {"status":"pass","canonical_files_unchanged":len(baseline["canonical_files"]),
              "historical_eval_files_unchanged":len(baseline["historical_evaluation_files"]),
              "qualified_runtime_inputs":len(qualification["runtime_input_hashes"]),
              "access_calls":1,"outcome_calls":sum(x["model_calls"] for x in results.values()),
              "local_originals_checked":args.local,"boundaries":results}
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
