#!/usr/bin/env python3
"""Check frozen pilot/result identity and declared missingness without model calls."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    assert isinstance(value, dict), path
    return value


def _check_model_lanes() -> int:
    checked = 0
    for freeze_name, prefix in (
        ("pilot-execution-freeze.json", "eval-"),
        ("native-plugin-execution-freeze.v1.json", "native-eval-"),
    ):
        freeze = _read(ROOT / freeze_name)
        assert freeze["status"] in {"frozen_before_outcomes", "frozen_before_native_outcomes"}
        frozen_hash = _sha(ROOT / freeze_name)
        for lane, count in (("02", 6), ("03", 6), ("05", 8)):
            result = _read(RESULTS / f"{prefix}{lane}-pilot.json")
            assert result["freeze_sha256"] == frozen_hash
            assert result["held_out"] is False
            assert result["validated_profile"] is False
            cells = result["cells"]
            assert len(cells) == count
            groups: dict[tuple[str, str], set[str]] = defaultdict(set)
            seen: set[tuple[str, str, str]] = set()
            for cell in cells:
                key = (cell["task"], cell["language"], cell["arm"])
                assert key not in seen, key
                seen.add(key)
                groups[(cell["task"], cell["language"])].add(
                    json.dumps(cell["source_hashes_before"], sort_keys=True)
                )
                assert cell["calls"]
                for call in cell["calls"]:
                    assert call["usage"]["input_tokens"] is not None
                    assert call["usage"]["output_tokens"] is not None
                    assert call["exit_code"] == 0
                    model = call.get("requested_model", call.get("model"))
                    if lane == "02" and cell["arm"].startswith("luna"):
                        assert model == "gpt-6-luna"
                    if lane == "05":
                        assert model == "gpt-6-sol"
                if prefix == "native-eval-":
                    assert cell["auth_is_symlink"] is False
                    assert cell["auth_copy_owner_only"] is True
                    if cell["plugin_installed"]:
                        assert cell["candidate_zip_sha256"] == freeze["candidate_zip"]["sha256"]
                    else:
                        assert cell["candidate_zip_sha256"] is None
            assert all(len(hashes) == 1 for hashes in groups.values())
            checked += len(cells)
    for name in (
        "eval-05-pilot-attempt1-harness-failure.json",
        "eval-05-pilot-attempt2-readonly-followup.json",
    ):
        attempt = _read(RESULTS / name)
        assert attempt["held_out"] is False and len(attempt["cells"]) == 8
    return checked


def _check_memory_lanes() -> int:
    directory = ROOT / "memory-results"
    freeze = ROOT / "memory-pilot-freeze.json"
    eval04 = _read(directory / "eval04-pilot-2026-09-24.json")
    assert eval04["freeze_sha256"] == "sha256:" + _sha(freeze)
    assert eval04["cell_count"] == 9
    assert len(eval04["cells"]) == 9
    assert all(item["usage"] is not None for item in eval04["cells"])
    eval01 = _read(directory / "eval01-pilot-2026-09-24.json")
    assert len(eval01["receipts"]) == 10
    assert eval01["naturalistic_session_count"] == 8
    assert eval01["paired_replay_session_count"] == 2
    assert eval01["attempts"][0]["exit_code"] == 1
    assert all(item["usage"] is not None for item in eval01["receipts"])
    repair = _read(directory / "eval01-guide-repair-2026-09-24.json")
    assert repair["freeze_sha256"] == "sha256:" + _sha(ROOT / "eval01-guide-repair-freeze.json")
    assert len(repair["receipts"]) == 2
    assert repair["exposure_gate"] is True
    assert repair["quality_gate"] is True
    assert repair["receipts"][1]["successful_memory_calls"] == 1
    return 9 + 10 + 2


def main() -> None:
    model_cells = _check_model_lanes()
    memory_cells = _check_memory_lanes()
    for path in (*RESULTS.glob("*.json"), *(ROOT / "memory-results").glob("*.json")):
        data = path.read_text()
        assert not re.search(r"sk-[A-Za-z0-9_-]{10,}", data), path
        assert '"transcript"' not in data and '"raw_prompt"' not in data, path
    print(f"v1.5-pilot-integrity: PASS {model_cells} model cells, {memory_cells} memory cells")


if __name__ == "__main__":
    main()
