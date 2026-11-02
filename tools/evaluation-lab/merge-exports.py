#!/usr/bin/env python3
"""Read-only validation and deduplication of explicit office-lab JSON exports."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if not (ROOT / "src").is_dir():
    ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
MAX_EXPORT_BYTES = 32 * 1024 * 1024
MAX_INPUTS = 100
MAX_TOTAL_BYTES = 64 * 1024 * 1024


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate_json_key")
        output[key] = value
    return output


def _load(path: Path) -> dict[str, Any]:
    from opensocrates.evaluation.storage import read_bytes

    raw = read_bytes(path, MAX_EXPORT_BYTES)
    data: Any = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_object)
    from opensocrates.evaluation.report import validate_export

    return validate_export(data)


def merge(paths: list[Path]) -> dict[str, Any]:
    if not 1 <= len(paths) <= MAX_INPUTS:
        raise ValueError("input_count")
    studies: dict[str, dict[str, Any]] = {}
    identity: tuple[Any, ...] | None = None
    total = 0
    for path in paths:
        total += path.stat().st_size
        if total > MAX_TOTAL_BYTES:
            raise ValueError("total_export_size")
        data = _load(path)
        observed = (
            data["pack"]["id"],
            data["pack"]["version"],
            data["pack"]["sha256"],
            data["content_version"],
        )
        if identity is not None and observed != identity:
            raise ValueError("incompatible_identity")
        identity = observed
        study_id = data["study_id"]
        if study_id in studies and studies[study_id] != data:
            raise ValueError("conflicting_study_export")
        studies[study_id] = copy.deepcopy(data)
    reports: dict[str, list[dict[str, Any]]] = {}
    for study_id, data in studies.items():
        for cell in data["report"]["cells"]:
            reports.setdefault(cell["cell_id"], []).append(
                {"source_study_id": study_id, "report": cell}
            )
    return {
        "schema": "opensocrates.office-merged-export/1",
        "pack": next(iter(studies.values()))["pack"],
        "content_version": "1.5.3",
        "source_study_ids": sorted(studies),
        "studies": [studies[key] for key in sorted(studies)],
        "cells": [
            {"cell_id": key, "source_reports": value} for key, value in sorted(reports.items())
        ],
        "limitations": [
            "Separate OS/host/model cells and source denominators are retained; no pooled score.",
            "Read-only merge does not resume studies or establish clean-machine or effect evidence.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exports", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = merge(args.exports)
        raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
    except Exception:
        print(
            "Merge rejected: invalid/conflicting exports or output already exists. No source was modified."
        )
        return 1
    print("Read-only merged export written. Cells and original source study IDs remain separate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
