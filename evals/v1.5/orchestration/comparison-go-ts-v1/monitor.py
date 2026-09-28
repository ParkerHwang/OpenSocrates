"""Read-only, privacy-safe progress snapshot for live comparison episodes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


CLIENT = Path("/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex")


def snapshot(results: Path, coordinator_pid: int | None = None,
             frozen_cell_ids: set[str] | None = None) -> dict:
    by_arm: dict[str, Counter] = defaultdict(Counter)
    reasons = Counter()
    role_started = role_terminal = 0
    startup_failures = []
    unknown_after_start = []
    seen_cell_names: set[str] = set()
    dispatch = results / "dispatch-index.json"
    if frozen_cell_ids is None and dispatch.is_file():
        frozen_cell_ids = {row["cell_id"] for row in json.loads(dispatch.read_text())["cell_results"]}
    for episode in sorted(results.iterdir()) if results.is_dir() else []:
        if not episode.is_dir():
            continue
        if frozen_cell_ids is not None and episode.name not in frozen_cell_ids:
            continue
        if frozen_cell_ids is None and not episode.name.startswith(("O-gpt-", "S-gpt-", "continuity-gpt-")):
            continue
        seen_cell_names.add(episode.name)
        arm = episode.name.rsplit("-", 1)[-1]
        counts = by_arm[arm]
        counts["claimed"] += 1
        counts["started"] += (episode / "started.json").is_file()
        counts["episode_terminal"] += (episode / "terminal.json").is_file()
        counts["summary"] += (episode / "summary.json").is_file()
        if (episode / "startup-failure.json").is_file():
            startup_failures.append(episode.name)
        if (episode / "terminal.json").is_file():
            terminal = json.loads((episode / "terminal.json").read_text())
            if terminal.get("status") == "unknown_after_start":
                unknown_after_start.append(episode.name)
        if (episode / "summary.json").is_file():
            summary = json.loads((episode / "summary.json").read_text())
            counts["status:" + str(summary.get("status"))] += 1
            if summary.get("status") == "integration_pending":
                publication = json.loads((episode / "response.json").read_text()).get("publication", {})
                counts["native_published_complete"] += (
                    publication.get("status") == "complete" and publication.get("location_verified") is True
                )
        response = episode / "response.json"
        if response.is_file():
            value = json.loads(response.read_text())
            if value.get("reason") and value.get("status") not in {"candidate_returned", "integration_pending"}:
                reasons[str(value["reason"])] += 1
            for unit in value.get("units", []):
                if unit.get("reason") and unit.get("status") not in {"ready", "qualified_candidate"}:
                    reasons[str(unit["reason"])] += 1
        journal = episode / "observation.jsonl"
        if journal.is_file():
            for line in journal.read_text().splitlines():
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if item.get("kind") == "role":
                    role_started += item.get("phase") == "start"
                    role_terminal += item.get("phase") == "terminal"
    try:
        coordinator_alive = coordinator_pid is not None and os.kill(coordinator_pid, 0) is None
    except OSError:
        coordinator_alive = False
    client_sha = hashlib.sha256(CLIENT.read_bytes()).hexdigest() if CLIENT.is_file() else None
    names = frozen_cell_ids or seen_cell_names
    if any(name.startswith("S-gpt-") for name in names):
        external_index = results / "external-qualification-S/index.json"
    elif any(name.startswith("continuity-gpt-") for name in names):
        external_index = results / "external-qualification-continuity/index.json"
    else:
        external_index = results / "external-qualification/index.json"
    external_passed = None
    if external_index.is_file():
        index = json.loads(external_index.read_text())
        external_passed = sum(item.get("status") == "deterministic_pass"
                              for item in index.get("variants", []))
    return {
        "schema": "opensocrates.go-ts.progress-snapshot/1",
        "by_arm": {arm: dict(counts) for arm, counts in sorted(by_arm.items())},
        "role_started": role_started, "role_terminal": role_terminal,
        "active_role_intervals": role_started - role_terminal,
        "startup_failures": startup_failures,
        "unknown_after_start": unknown_after_start,
        "structured_failure_reasons": dict(reasons),
        "coordinator_pid": coordinator_pid, "coordinator_alive": coordinator_alive,
        "dispatch_index_present": (results / "dispatch-index.json").is_file(),
        "external_index_present": external_index.is_file(),
        "externally_deterministic_passed_variants": external_passed,
        "actual_client_sha256": client_sha,
        "raw_prompt_transcript_reasoning_tool_output_retained": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--coordinator-pid", type=int)
    parser.add_argument("--freeze", type=Path,
                        help="optional exact frozen cell IDs; dispatch index is used when available")
    args = parser.parse_args()
    frozen_ids = set(json.loads(args.freeze.read_text())["cell_ids"]) if args.freeze else None
    print(json.dumps(snapshot(args.results, args.coordinator_pid, frozen_ids), sort_keys=True))


if __name__ == "__main__":
    main()
