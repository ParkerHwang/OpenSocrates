"""Prepare non-executable draft metadata; root reviews and freezes it afterward."""

import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT.parent / "OpenSocrates-v1.5.0-implementation"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    client = Path("$BUNDLED_CODEX")
    archives = [
        (
            "v1.4.0",
            PRODUCT / "dist/qualification-artifacts/released-v1.4.0-74efeab5797d.zip",
            "1.4.0",
            False,
        ),
        (
            "v1.5.0-rc",
            PRODUCT / "dist/qualification-artifacts/repair-guide6-1aae2efefc76.zip",
            "1.5.0",
            True,
        ),
    ]
    arms = [
        {
            "id": "vanilla",
            "archive_path": None,
            "archive_sha256": None,
            "package_version": None,
            "memory": False,
            "task_id": "c4a7a000-0000-4000-8000-000000000001",
        }
    ]
    for index, (name, archive, version, memory) in enumerate(archives, 2):
        with zipfile.ZipFile(archive) as bundle:
            members = {
                path: hashlib.sha256(bundle.read(path)).hexdigest()
                for path in bundle.namelist()
                if path
                in [
                    "bin/launch.sh",
                    "skills/opensocrates/SKILL.md",
                    "runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime",
                    "schemas/v1/project-memory-request.schema.json",
                ]
                or path.startswith("skills/opensocrates/references/assistance/")
                or path.startswith("skills/opensocrates/references/coding/")
            }
        arms.append(
            {
                "id": name,
                "archive_path": str(archive),
                "archive_sha256": sha(archive),
                "package_version": version,
                "memory": memory,
                "task_id": f"c4a7a000-0000-4000-8000-{index:012d}",
                "members": members,
            }
        )
    manifest = {
        "schema": "opensocrates.queueforge-comparison/1",
        "status": "preflight-draft-no-outcome-calls",
        "client": {
            "path": str(client),
            "version": "codex-cli 0.158.0-alpha.2",
            "sha256": sha(client),
        },
        "model": "gpt-6-sol",
        "effort": "medium",
        "service": "default",
        "arms": arms,
        "limits": {
            "model_calls": 9,
            "seconds_per_call": 1200,
            "parallel_builders": 2,
            "automatic_model_retries": 0,
            "final_performance_seconds": 1800,
            "preliminary_performance_seconds": 900,
            "prepared_database_bytes": 2 * 1024**3,
        },
        "accepted_intent": [
            "Preserve acknowledged jobs and lease fencing across restarts.",
            "Keep tenant namespaces isolated; synthetic tenant headers are not production authentication.",
            "SQLite WAL and synchronous=FULL remain required; do not trade durability for throughput.",
            "Current source and task contracts govern facts; bounded continuity summaries do not grant authority.",
        ],
        "common_prompt": (ROOT / "protocol/COMMON_PROMPT.md").read_text(),
        "development_order": {
            "1": ["vanilla", "v1.4.0", "v1.5.0-rc"],
            "2": ["v1.4.0", "v1.5.0-rc", "vanilla"],
            "3": ["v1.5.0-rc", "vanilla", "v1.4.0"],
        },
        "performance_cells": {},
    }
    ids = [arm["id"] for arm in arms]
    for stage, reps in [(2, 1), (3, 3)]:
        rows = []
        for rep in range(reps):
            cases = [
                {"workload": workload, "concurrency": concurrency, "rate": 0}
                for workload in ["read", "lifecycle"]
                for concurrency in [1, 16, 64]
            ]
            if stage == 3:
                cases += [
                    {"workload": "read", "concurrency": 1, "rate": rate}
                    for rate in [100, 500, 1000]
                ]
            for number, case in enumerate(cases):
                offset = (rep + number) % 3
                for arm in ids[offset:] + ids[:offset]:
                    rows.append(
                        {
                            **case,
                            "stage": stage,
                            "arm": arm,
                            "repetition": rep,
                            "index": len(rows),
                            "warmup_seconds": 3,
                            "measure_seconds": 8 if stage == 2 else 10,
                        }
                    )
        manifest["performance_cells"][str(stage)] = rows
    manifest["measurement"] = {
        "percentile": "lower order statistic at floor((n-1)*p), complete retained cohort samples",
        "throughput": "matching start-cohort responses completed in measurement window; cohort/drain counts separate",
        "qualification": "artifact_gate_pass is pre-load only; require separate source durability review and valid conservation/body/duplicate metrics; disclose generator saturation and drops",
        "comparison_unit": "one generated implementation per condition; load repetitions are not independent model replicates",
    }
    path = ROOT / "protocol/manifest.draft.json"
    with path.open("x") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    print(
        "Draft prepared: three conditions, nine calls, eighteen preliminary and eighty-one final cells"
    )


if __name__ == "__main__":
    main()
