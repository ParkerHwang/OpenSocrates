"""Integrator-owned execution; the verified reviewer can only read and return JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from validate_review import validate

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
ROOT = HERE.parents[4]
sys.path.insert(0, str(BASE))
from harness_v4 import native_counts, profile, summarize  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def freeze() -> dict:
    path = HERE / "manifest.json"
    relative = str(path.relative_to(ROOT))
    assert (
        subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT) == path.read_bytes()
    )
    manifest = read(path)
    for name, expected in manifest["file_hashes"].items():
        assert sha(ROOT / name) == expected, name
    for packet in manifest["packets"]:
        assert sha(ROOT / packet["original_path"]) == packet["original_sha256"]
    definition = ROOT / manifest["agent"]["original_definition_path"]
    assert sha(definition) == manifest["agent"]["definition_sha256"]
    assert not definition.is_symlink() and definition.stat().st_uid == os.getuid()
    assert not definition.stat().st_mode & 0o022
    assert sha(Path(manifest["client"]["path"])) == manifest["client"]["sha256"]
    assert (
        sha(ROOT / manifest["original_first_pass_lock"]["path"])
        == manifest["original_first_pass_lock"]["sha256"]
    )
    config = tomllib.loads((HERE / "runtime-profile.toml").read_text())
    assert (config["model"], config["model_reasoning_effort"], config["sandbox_mode"]) == (
        "gpt-6-astra",
        "xhigh",
        "read-only",
    )
    return manifest


def materialize(
    manifest: dict, assignment: dict, phase: str, workspace: Path
) -> tuple[dict, dict, dict | None]:
    packets, evidence = {}, {}
    for name in ("AGENTS.md", "CONTRIBUTING.md"):
        shutil.copyfile(ROOT / name, workspace / name)
    rubric = workspace / manifest["rubric"]["path"]
    rubric.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / manifest["rubric"]["path"], rubric)
    shutil.copyfile(HERE / "reviewer-definition.toml", workspace / "reviewer-definition.toml")
    shutil.copyfile(HERE / "response.schema.json", workspace / "response.schema.json")
    by_id = {row["packet_id"]: row for row in manifest["packets"]}
    for identifier in assignment["packet_ids"]:
        info = by_id[identifier]
        target = workspace / info["delivered_relative_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / info["first_pass_path"], target)
        packets[identifier] = {"content": read(target), "sha256": sha(target)}
        if phase == "evidence":
            target = workspace / "evals/v1.5/expanded/judge-evidence-v2" / f"{identifier}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / info["evidence_path"], target)
            evidence[identifier] = {"content": read(target), "sha256": sha(target)}
    locked = None
    if phase == "evidence":
        source = ROOT / assignment["first_pass_projection_path"]
        assert sha(source) == assignment["first_pass_projection_sha256"]
        shutil.copyfile(source, workspace / "locked-first-pass.json")
        locked = read(source)
    for path in workspace.rglob("*"):
        if path.is_file():
            path.chmod(0o400)
    return packets, evidence, locked


def prompt(manifest: dict, assignment: dict, phase: str) -> str:
    entries = {row["packet_id"]: row for row in manifest["packets"]}
    selected = [
        {
            "packet_id": identifier,
            "path": entries[identifier]["delivered_relative_path"],
            "sha256": entries[identifier]["first_pass_sha256"],
            "locale": entries[identifier]["locale"],
        }
        for identifier in assignment["packet_ids"]
    ]
    instructions = f"""TASK: Complete assignment {assignment["assignment_id"]}, phase {phase}, as the verified opensocrates_bilingual_reviewer.
This is a new isolated review context. Read AGENTS.md, CONTRIBUTING.md and {manifest["rubric"]["path"]} (SHA-256 {manifest["rubric"]["sha256"]}). Your exact verified agent definition is also available as reviewer-definition.toml. Only review the following {len(selected)} assigned packets:
{json.dumps(selected, ensure_ascii=False, indent=2)}

These are frozen first-pass views of prepared synthetic packets. packet_sha256 in your response must identify the supplied view bytes above; the integrator separately preserves original packet hashes and projection provenance. No treatment identity, outcome summary, map, hidden checker, implementation conversation or other assignment is available or permitted. Read each assigned packet completely using bounded read-only operations. You may parse JSON or hash files; never execute/import candidate artifact code, tests, plugins, or harnesses. Never modify files, access credentials, use network/apps, or spawn agents.

Assess each packet independently. Include every packet even when its evidence is missing; use null/unassessable with a reason. Judge clarification over ALL available public messages; where earlier public messages are absent, do not conclude that no earlier question was asked. Separate observed behavior, rubric defects and missing evidence. Preserve human_scores=null. You are one provisional model assessor, never a human or an independent set of judges.

Return valid JSON only, matching response.schema.json. Use assignment_id={assignment["assignment_id"]}, phase={phase}. Six axis keys are task_outcome, evidence_factual_accuracy, initiative_continuity, communication, coding_maintainability, efficiency_discipline. For each use score 0-4 when supported; otherwise null with status not_applicable or unassessable. Give concise public grounds and citations, not hidden reasoning. Every gate/finding needs evidence. Evidence syntax is packet:/JSON/Pointer (the packet: prefix is optional) or, after disclosure only, deterministic:/JSON/Pointer. For code/text you may append #L<number>, e.g. packet:/stages/0/artifacts/invoice.py#L2. For JSON stored as artifact text you may continue into its decoded JSON fields. Cite an existing parent/coverage field when information is absent; do not invent pointers. Host/backend model echoes and usage are null because they are not available to you; the integrator captures actual client usage separately.

READ EFFICIENTLY WITHOUT OMITTING EVIDENCE: Your exact role is already loaded as developer instructions, and the full output schema is supplied natively. The locked response shows the response structure. Do not repeatedly dump the role, schema or already-read packet text. Read the required repository constraints, rubric, locked judgments, packet views and matching evidence completely once in bounded chunks. Keep all required ratings, gates, citations and missingness; this is an execution instruction, never a request to infer less reasoning from shorter text. Use parsing/hashing only; do not execute any candidate artifact.
"""
    if phase == "first_pass":
        return (
            instructions
            + """
FIRST-PASS LOCK: Deterministic evidence is physically withheld. Do not search for it. Set deterministic_evidence_status to {"status":"withheld","sha256":null,"limitations":["First pass precedes deterministic evidence"]}, disagreements=[], post_evidence_scores=null, and post_evidence_critical_gates=[]. Make the six first_pass_scores, critical_gates and findings complete now. Efficiency based on unavailable action/timing evidence must remain unassessable; short output is not efficiency. Return this bounded assignment and stop.
"""
        )
    evidence = [
        {
            "packet_id": identifier,
            "path": f"evals/v1.5/expanded/judge-evidence-v2/{identifier}.json",
            "sha256": entries[identifier]["evidence_sha256"],
        }
        for identifier in assignment["packet_ids"]
    ]
    return (
        instructions
        + f"""
EVIDENCE PHASE: Every first-pass assignment was validated and locked before this phase. Read locked-first-pass.json, which contains only this assignment's own locked judgments, then the corresponding opaque evidence files below. No other prior ratings are supplied. Preserve packet_sha256, locale, blinding_status, non_blindable_cues, first_pass_scores, critical_gates, findings, assessment_status and human_scores EXACTLY as locked, even if later evidence changes your view. Set deterministic_evidence_status to reviewed with the evidence file SHA. Add separately labelled post_evidence_scores (all six axes, explicit nulls allowed), post_evidence_critical_gates and cited disagreements. Classify any divergence as behavior_defect, rubric_defect or missing_evidence; do not rewrite historical flags. A contradictory test flag does not erase a visible question in another public message, and absence of older messages does not prove a question was never asked. Do not run the checker or candidate code. Return JSON and stop.
{json.dumps(evidence, indent=2)}
"""
    )


def tool_audit(raw: str, workspace: Path) -> dict:
    commands, flags = [], []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        item = event.get("item") or {}
        if event.get("type") != "item.completed":
            continue
        if item.get("type") == "command_execution":
            command = item.get("command") or ""
            redacted = command.replace(str(workspace), "<review-workspace>")
            redacted = re.sub(r"/private/tmp/[^\s'\"]+", "<disposable-path>", redacted)
            commands.append({"command_template": redacted, "exit_code": item.get("exit_code")})
            if re.search(
                r"unblinding|RESULTS\.md|AUDIT\.md|STATUS\.md|HELD_OUT_READINESS|AUTHORSHIP|auth\.json|results-v[2345]|checks_v2|git\s+(?:log|show)|\b(?:curl|wget|pytest)\b|\b(?:exec|eval)\s*\(",
                command,
            ):
                flags.append("prohibited_read_or_execution_pattern")
        elif item.get("type") in {"file_change", "web_search", "mcp_tool_call"}:
            flags.append("unexpected_tool_type:" + item["type"])
    return {
        "commands": commands,
        "flags": flags,
        "limit": "Declared read-only sandbox and narrow physical input scope; command-pattern audit is not universal access attestation",
    }


def invoke(
    manifest: dict, workspace: Path, env: dict, text: str, destination: Path
) -> tuple[dict, str]:
    command = [
        manifest["client"]["path"],
        "--no-daemon",
        "--ask-for-approval",
        "never",
        "exec",
        "--json",
        "--ephemeral",
        "--profile",
        "opensocrates_bilingual_reviewer",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--ignore-rules",
        "--disable",
        "plugins",
        "--disable",
        "hooks",
        "--disable",
        "memories",
        "--disable",
        "multi_agent",
        "--disable",
        "external_agent_memory_import",
        "-m",
        "gpt-6-astra",
        "-c",
        'model_reasoning_effort="xhigh"',
        "--output-schema",
        str(workspace / "response.schema.json"),
        "-C",
        str(workspace),
        "-",
    ]
    metadata = {
        "model_requested": "gpt-6-astra",
        "effort_requested": "xhigh",
        "sandbox_requested": "read-only",
        "agent_definition_sha256": manifest["agent"]["definition_sha256"],
        "runtime_profile_sha256": manifest["agent"]["runtime_profile_sha256"],
        "client_sha256": manifest["client"]["sha256"],
        "prompt_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "started_unix": time.time(),
        "backend_model_echo": None,
        "billed_cost": None,
    }
    save(destination / "started.json", metadata)
    started = time.monotonic()
    process = None
    stdout = stderr = ""
    failure = None
    timed_out = False
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=workspace,
            start_new_session=True,
        )
        stdout, stderr = process.communicate(text, timeout=manifest["limits"]["per_call_seconds"])
    except subprocess.TimeoutExpired:
        timed_out = True
        assert process is not None
        os.killpg(process.pid, signal.SIGKILL)
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            failure = "post_kill_output_unavailable"
            for stream in (process.stdout, process.stderr, process.stdin):
                if stream:
                    stream.close()
    except OSError as error:
        failure = type(error).__name__
    error_events = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") in {"error", "turn.failed"}:
            error_events.append(event)
    summary, final = summarize(stdout)
    audit = tool_audit(stdout, workspace)
    result = {
        **metadata,
        "exit_code": process.returncode if process else None,
        "timed_out": timed_out,
        "invocation_error": failure,
        "wall_seconds": round(time.monotonic() - started, 3),
        "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest() if stderr else None,
        **summary,
        "access_audit": audit,
        "error_events": error_events,
    }
    result["process_success"] = (
        result["exit_code"] == 0
        and summary["turn_completed"]
        and not summary["errors"]
        and not timed_out
        and failure is None
    )
    # The receipt precedes parsing/scoring; malformed JSON cannot erase usage.
    save(destination / "receipt.json", result)
    with (destination / "returned.txt").open("x", encoding="utf-8") as stream:
        stream.write(final)
    return result, final


def run_assignment(manifest: dict, assignment: dict, phase: str) -> dict:  # noqa: C901
    identifier = assignment["assignment_id"]
    output = HERE / "assessments" / f"{identifier}-{phase}.json"
    if output.exists():
        return {"assignment_id": identifier, "status": "already_locked"}
    for attempt in range(1, manifest["limits"]["format_retry_limit"] + 2):
        destination = HERE / "attempts" / identifier / phase / f"attempt-{attempt:02d}"
        if destination.exists():
            raise RuntimeError(
                "Existing attempted call needs explicit reconciliation, not blind retry"
            )
        destination.mkdir(parents=True)
        with tempfile.TemporaryDirectory(
            prefix="os-astra-review-", dir="/private/tmp"
        ) as temporary:
            base = Path(temporary)
            workspace = base / "workspace"
            workspace.mkdir(mode=0o700)
            codex, env = profile(base / "profile")
            try:
                shutil.copyfile(
                    HERE / "runtime-profile.toml",
                    codex / "opensocrates_bilingual_reviewer.config.toml",
                )
                packets, evidence, locked = materialize(manifest, assignment, phase, workspace)
                hashes = {
                    str(path.relative_to(workspace)): sha(path)
                    for path in workspace.rglob("*")
                    if path.is_file()
                }
                receipt, returned = invoke(
                    manifest, workspace, env, prompt(manifest, assignment, phase), destination
                )
                errors, warnings = [], []
                value = None
                try:
                    if not receipt["process_success"]:
                        raise ValueError("client process/turn did not complete")
                    if len(returned.encode()) > manifest["limits"]["max_response_bytes"]:
                        raise ValueError("response exceeds frozen byte bound")
                    value = json.loads(returned)
                    warnings = validate(
                        value,
                        schema=read(HERE / "response.schema.json"),
                        assignment=assignment,
                        packets=packets,
                        rubric=manifest["rubric"],
                        phase=phase,
                        deterministic=evidence,
                        locked=locked,
                    )
                    if receipt["access_audit"]["flags"]:
                        raise ValueError("read-boundary audit flagged an attempted violation")
                    after = {
                        str(path.relative_to(workspace)): sha(path)
                        for path in workspace.rglob("*")
                        if path.is_file()
                    }
                    if hashes != after:
                        raise ValueError("review input files changed")
                except (ValueError, KeyError, TypeError) as error:
                    errors.append(str(error))
                save(
                    destination / "validation.json",
                    {"valid": not errors, "errors": errors, "warnings": warnings},
                )
                if value is not None:
                    save(destination / "parsed.json", value)
                save(
                    destination / "isolation.json",
                    {
                        "input_hashes_unchanged": hashes
                        == {
                            str(path.relative_to(workspace)): sha(path)
                            for path in workspace.rglob("*")
                            if path.is_file()
                        },
                        "native_memory_tables": native_counts(codex),
                        "profile_initial_state": "new local profile",
                        "account_side_isolation": "unverified",
                    },
                )
                if not errors:
                    save(output, value)
                    lock = {
                        "assignment_id": identifier,
                        "phase": phase,
                        "response_sha256": sha(output),
                        "accepted_attempt": attempt,
                        "packet_ids": assignment["packet_ids"],
                        "locked_at_unix": time.time(),
                        "warnings": warnings,
                    }
                    save(HERE / "locks" / f"{identifier}-{phase}.json", lock)
                    return {"assignment_id": identifier, "status": "locked", "attempt": attempt}
                if not receipt["process_success"] or receipt["access_audit"]["flags"]:
                    return {"assignment_id": identifier, "status": "failed", "errors": errors}
            finally:
                (codex / "auth.json").unlink(missing_ok=True)
                save(
                    destination / "cleanup.json",
                    {"auth_copy_removed": not (codex / "auth.json").exists()},
                )
    return {"assignment_id": identifier, "status": "failed_validation"}


def lock_phase(manifest: dict, phase: str) -> None:
    assessments = dict(manifest["retained_evidence_assessments"])
    for assignment in manifest["assignment_order"]:
        path = HERE / "assessments" / f"{assignment['assignment_id']}-{phase}.json"
        if not path.exists():
            raise RuntimeError("Cannot lock an incomplete phase")
        assessments[assignment["assignment_id"]] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha(path),
        }
    save(
        HERE / "locks/all-ratings.lock.json",
        {
            "phase": phase,
            "manifest_sha256": sha(HERE / "manifest.json"),
            "assessments": assessments,
            "locked_at_unix": time.time(),
            "packets": 60,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["evidence"])
    parser.add_argument("--assignment")
    args = parser.parse_args()
    manifest = freeze()
    assignments = [
        row
        for row in manifest["assignment_order"]
        if not args.assignment or row["assignment_id"] == args.assignment
    ]
    assert assignments
    results = []
    with ThreadPoolExecutor(max_workers=manifest["limits"]["max_parallel_calls"]) as executor:
        pending = iter(assignments)
        running = set()
        stop_dispatch = False
        while True:
            while not stop_dispatch and len(running) < manifest["limits"]["max_parallel_calls"]:
                assignment = next(pending, None)
                if assignment is None:
                    break
                running.add(executor.submit(run_assignment, manifest, assignment, args.phase))
            if not running:
                break
            completed, running = wait(running, return_when=FIRST_COMPLETED)
            for future in completed:
                result = future.result()
                results.append(result)
                print(json.dumps(result), flush=True)
                if result["status"] not in {"locked", "already_locked"}:
                    stop_dispatch = True
    if (
        not args.assignment
        and len(results) == len(assignments)
        and all(result["status"] in {"locked", "already_locked"} for result in results)
    ):
        lock_phase(manifest, args.phase)


if __name__ == "__main__":
    main()
