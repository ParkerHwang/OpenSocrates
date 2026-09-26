"""Freeze bounded blind assignments and derived views without changing old packets."""

from __future__ import annotations

import hashlib
import json
import math
import random
import shutil
import subprocess
import tomllib
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
ROOT = HERE.parents[4]
AGENT = ROOT / ".codex/agents/opensocrates_bilingual_reviewer.toml"
CLIENT = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
AXES = (
    "task_outcome",
    "evidence_factual_accuracy",
    "initiative_continuity",
    "communication",
    "coding_maintainability",
    "efficiency_discipline",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def schema() -> dict:
    def obj(properties: dict) -> dict:
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    string = {"type": "string"}
    strings = {"type": "array", "items": string}
    null = {"type": "null"}
    evidence = {"type": "array", "items": string}
    score = obj(
        {
            "score": {"type": ["integer", "null"], "minimum": 0, "maximum": 4},
            "status": {"enum": ["scored", "not_applicable", "unassessable"]},
            "reason": string,
            "evidence": evidence,
        }
    )
    scores = obj({axis: score for axis in AXES})
    gate = obj(
        {
            "gate_id": string,
            "status": {"enum": ["pass", "fail", "unassessable"]},
            "reason": string,
            "evidence": evidence,
        }
    )
    finding = obj(
        {
            "category": {
                "enum": ["behavior_defect", "rubric_defect", "missing_evidence", "strength"]
            },
            "severity": {"enum": ["critical", "major", "minor", "info"]},
            "finding": string,
            "evidence": evidence,
        }
    )
    disagreement = obj(
        {
            "subject": string,
            "category": {
                "enum": ["behavior_defect", "rubric_defect", "missing_evidence", "no_disagreement"]
            },
            "first_pass_observation": string,
            "deterministic_observation": string,
            "interpretation": string,
            "evidence": evidence,
        }
    )
    packet = obj(
        {
            "packet_id": string,
            "packet_sha256": string,
            "locale": {"enum": ["en", "ko"]},
            "blinding_status": {"enum": ["intact", "limited", "contaminated"]},
            "non_blindable_cues": strings,
            "first_pass_scores": scores,
            "critical_gates": {"type": "array", "items": gate},
            "findings": {"type": "array", "items": finding},
            "deterministic_evidence_status": obj(
                {
                    "status": {"enum": ["withheld", "reviewed", "unavailable"]},
                    "sha256": {"type": ["string", "null"]},
                    "limitations": strings,
                }
            ),
            "disagreements": {"type": "array", "items": disagreement},
            "post_evidence_scores": {"anyOf": [scores, null]},
            "post_evidence_critical_gates": {"type": "array", "items": gate},
            "human_scores": null,
            "assessment_status": {"enum": ["provisional_ai", "unassessable", "contaminated"]},
        }
    )
    return obj(
        {
            "schema": {"const": "opensocrates.provisional-ai-review/1.0.0"},
            "assignment_id": string,
            "phase": {"enum": ["first_pass", "evidence"]},
            "assessor": obj(
                {
                    "agent": {"const": "opensocrates_bilingual_reviewer"},
                    "kind": {"const": "model"},
                    "configured_model": {"const": "gpt-6-astra"},
                    "configured_effort": {"const": "xhigh"},
                    "host_reported_model": null,
                    "backend_model_echo": null,
                    "human_assessor": {"const": False},
                    "provisional": {"const": True},
                }
            ),
            "rubric": obj({"path": string, "sha256": string}),
            "packets": {"type": "array", "items": packet},
            "unreviewed_packets": strings,
            "usage": null,
            "limitations": strings,
        }
    )


def family(packet: dict) -> str:
    task = packet.get("task_id", "")
    if packet.get("task_kind") == "memory" or "eval04" in task:
        return "event_continuity"
    if packet.get("task_kind") == "dialogue" or "eval05-collaboration" in task:
        return "nondeveloper_collaboration"
    if "eval05-developer" in task:
        return "developer_collaboration"
    return task.removesuffix("-en").removesuffix("-ko")


def main() -> None:  # noqa: C901
    definition = tomllib.loads(AGENT.read_text())
    assert definition["name"] == "opensocrates_bilingual_reviewer"
    assert (
        definition["model"],
        definition["model_reasoning_effort"],
        definition["sandbox_mode"],
    ) == ("gpt-6-astra", "xhigh", "read-only")
    assert not AGENT.is_symlink() and not AGENT.stat().st_mode & 0o022
    shutil.copyfile(AGENT, HERE / "reviewer-definition.toml")
    shutil.copyfile(Path("/tmp/opensocrates-review-profile.toml"), HERE / "runtime-profile.toml")
    assert tomllib.loads((HERE / "runtime-profile.toml").read_text()) == {
        key: value for key, value in definition.items() if key not in {"name", "description"}
    }
    for number in (1, 2):
        source = Path(
            "/tmp/opensocrates-review-config-preflight" + ("2" if number == 2 else "") + ".json"
        )
        value = json.loads(source.read_text())
        if "stderr" in value:
            value["stderr"] = (
                "--strict-config is unsupported for debug; temporary helper aliases unavailable; no model call"
            )
        save(HERE / "preflight" / f"configuration-{number}.json", value)
    save(HERE / "response.schema.json", schema())
    records = []
    # Mechanical, private join only to form opaque evidence projections. No labels
    # enter assignments or reviewer inputs; analytic unblinding waits for locks.
    diagnostic_join = {
        row["packet_id"]: row["cell_id"]
        for row in json.loads((BASE / "diagnostic-unblinding.json").read_text())
    }
    for folder in ("blinded-v2", "blinded-diagnostics"):
        for original in sorted((BASE / folder).glob("*.json")):
            packet = json.loads(original.read_text())
            identifier = packet["packet_id"]
            view = json.loads(original.read_text())
            withheld = []
            if folder == "blinded-diagnostics":
                post = view.pop("persisted_memory_observation", None)
                withheld.append("/persisted_memory_observation")
                view["persisted_public_records"] = (post or {}).get("exported_public_records")
                cell_id = diagnostic_join[identifier]
                version = cell_id.split("-")[0]
                result = json.loads(
                    (BASE / f"diagnostic-results-{version}" / cell_id / "result.json").read_text()
                )
                evidence = {
                    "packet_id": identifier,
                    "deterministic_checks": result.get("original_strict_check"),
                    "artifact_pass": result.get("artifact_pass"),
                    "memory_forgetting_verified": result.get("memory_forgetting_verified"),
                    "persisted_memory_observation": result.get("memory_postcheck"),
                    "question_in_any_public_message_heuristic": result.get(
                        "question_in_any_public_message_heuristic"
                    ),
                    "strict_diagnostic_pass": result.get("diagnostic_pass"),
                    "measurement_limit": "Original flags remain frozen; missing messages and legacy final-only criteria may make a semantic conclusion unassessable or disagree.",
                }
            else:
                evidence = json.loads((BASE / "judge-evidence-v2" / original.name).read_text())
            view_path = HERE / "inputs/first" / original.name
            evidence_path = HERE / "inputs/evidence" / original.name
            save(view_path, view)
            save(evidence_path, evidence)
            records.append(
                {
                    "packet_id": identifier,
                    "locale": packet["locale"],
                    "family": family(packet),
                    "original_path": str(original.relative_to(ROOT)),
                    "original_sha256": sha(original),
                    "first_pass_path": str(view_path.relative_to(ROOT)),
                    "first_pass_sha256": sha(view_path),
                    "delivered_relative_path": f"evals/v1.5/expanded/{folder}/{original.name}",
                    "evidence_path": str(evidence_path.relative_to(ROOT)),
                    "evidence_sha256": sha(evidence_path),
                    "withheld_from_first_pass": withheld,
                    "projection_note": "Existing persisted public records are observational artifacts; computed booleans and checker flags withheld"
                    if withheld
                    else "Semantically unchanged packet; canonical JSON serialization only",
                }
            )
    assert len(records) == 60 and len({row["packet_id"] for row in records}) == 60
    randomizer = random.Random(2026092401)
    assignments = []
    for locale in ("en", "ko"):
        rows = [row for row in records if row["locale"] == locale]
        families = defaultdict(list)
        for row in rows:
            families[row["family"]].append(row)
        count = max(math.ceil(len(rows) / 4), max(map(len, families.values())))
        batches: list[list[dict]] = [[] for _ in range(count)]
        for _, entries in sorted(families.items(), key=lambda item: (-len(item[1]), item[0])):
            randomizer.shuffle(entries)
            candidates = list(range(count))
            randomizer.shuffle(candidates)
            candidates.sort(key=lambda index: len(batches[index]))
            for row, index in zip(entries, candidates, strict=False):
                batches[index].append(row)
        for batch in batches:
            assert 1 <= len(batch) <= 4 and len({row["family"] for row in batch}) == len(batch)
            randomizer.shuffle(batch)
            assignments.append(
                {"locale": locale, "packet_ids": [row["packet_id"] for row in batch]}
            )
    randomizer.shuffle(assignments)
    for index, assignment in enumerate(assignments, 1):
        assignment["assignment_id"] = f"A{index:02d}"
    assert sum(len(row["packet_ids"]) for row in assignments) == 60
    paths = [
        HERE / name
        for name in (
            "reviewer-definition.toml",
            "runtime-profile.toml",
            "response.schema.json",
            "prepare_review.py",
            "review.py",
            "validate_review.py",
        )
    ]
    paths += [
        ROOT / "AGENTS.md",
        ROOT / "CONTRIBUTING.md",
        BASE / "JUDGE_PROCEDURE.v2.md",
        BASE / "harness_v4.py",
    ]
    paths += list((HERE / "inputs").rglob("*.json"))
    manifest = {
        "schema": "opensocrates.provisional-ai-review-manifest/1.0.0",
        "status": "frozen_before_judging",
        "source_commit_before_freeze": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "agent": {
            "name": definition["name"],
            "original_definition_path": str(AGENT.relative_to(ROOT)),
            "definition_sha256": sha(AGENT),
            "model": "gpt-6-astra",
            "effort": "xhigh",
            "sandbox": "read-only",
            "substitution": "forbidden",
            "invocation": "Codex CLI named isolated configuration profile derived from exact user agent TOML; metadata name/description excluded from runtime settings, all behavioral fields preserved",
            "runtime_profile_sha256": sha(HERE / "runtime-profile.toml"),
            "developer_instructions_sha256": hashlib.sha256(
                definition["developer_instructions"].encode()
            ).hexdigest(),
        },
        "client": {
            "path": str(CLIENT),
            "version": subprocess.check_output([str(CLIENT), "--version"], text=True).strip(),
            "sha256": sha(CLIENT),
        },
        "rubric": {
            "path": str((BASE / "JUDGE_PROCEDURE.v2.md").relative_to(ROOT)),
            "sha256": sha(BASE / "JUDGE_PROCEDURE.v2.md"),
        },
        "packets": records,
        "assignment_order": assignments,
        "randomization_seed": 2026092401,
        "limits": {
            "max_packets_per_assignment": 4,
            "max_parallel_calls": 2,
            "per_call_seconds": 900,
            "max_response_bytes": 262144,
            "format_retry_limit": 1,
            "model_switches": 0,
            "output_guidance": "Concise JSON public grounds, roughly 3000 words at most per four-packet assignment; no omitted required axes or critical gates",
            "token_cap": None,
            "token_cap_reason": "No verified total-token cap on this CLI; enforce wall and response byte bounds",
        },
        "phase_order": "All 17 first-pass assignments complete and are validated/hashed/locked before any deterministic-evidence call. Evidence calls use a fresh context containing only that assignment's locked first pass, its packets and corresponding opaque checks. All evidence assessments lock before analytic unblinding.",
        "input_isolation": "New owner-only HOME/CODEX_HOME and workspace per call; no implementation conversation, history, summaries, other scores, map or hidden checker. Native memory use/generation/import, hooks, plugins, web and delegation disabled. Agent tools read-only. CLI ephemeral; only integrator persists JSON.",
        "preparer_join_boundary": "A deterministic preparer uses the diagnostic join key solely to project corresponding checks without labels. No treatment join or analysis is exposed until all ratings lock.",
        "failure_handling": "Persist started and terminal receipts plus returned public JSON before validation. One fresh same-tuple format/citation retry may follow failed validation; no semantic direction, prior ratings, effort change or artifact repair. Keep all failures and null usage. Transport/unavailability errors never substitute a model. Interrupted calls stay missing unless a separately recorded safe recovery is justified.",
        "usage_fields": [
            "input_tokens",
            "cached_input_tokens",
            "cache_write_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
            "wall_seconds",
            "tool_actions",
            "failed_tool_actions",
            "billed_cost",
        ],
        "identity_limit": "Client/configuration requested identity is verified; independent backend model echo remains null unless actually exposed.",
        "judgment_boundary": "Provisional Astra model assessments only. Human scores unavailable. No candidate repair, outcome rerun, stronger assistance inside Luna treatments, held-out relabelling, profile promotion or release approval.",
        "file_hashes": {str(path.relative_to(ROOT)): sha(path) for path in paths},
        "unblinding_hashes": {
            name: sha(BASE / name) for name in ("unblinding-v2.json", "diagnostic-unblinding.json")
        },
    }
    save(HERE / "manifest.json", manifest)
    print(
        f"Prepared {len(records)} packets in {len(assignments)} assignments; original packets/rubric unchanged"
    )


if __name__ == "__main__":
    main()
