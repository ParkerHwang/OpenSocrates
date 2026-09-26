"""Separately frozen guide-3 diagnostics with public messages and store postchecks."""

from __future__ import annotations

import json
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import harness_v3 as harness
from runner_v2 import (
    build_marketplace,
    files,
    install_or_check,
    installed_root,
    member_check,
    memory_seed,
    public_text,
    retain_stage,
    setup_command,
)

HERE = Path(__file__).resolve().parent
ORIGINAL_SUMMARIZE = harness.summarize


def trace_public(raw: str) -> tuple[dict, str]:
    summary, final = ORIGINAL_SUMMARIZE(raw)
    public_messages, commands = [], []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict) or event.get("type") != "item.completed":
            continue
        item = event.get("item") or {}
        if item.get("type") == "agent_message":
            public_messages.append(public_text(item.get("text", ""), Path("/path-never-used")))
        if item.get("type") == "command_execution":
            command = item.get("command", "")
            commands.append(
                {
                    "command_template": public_text(command, Path("/path-never-used")),
                    "exit_code": item.get("exit_code"),
                    "status": item.get("status"),
                }
            )
    summary["public_messages"] = public_messages
    summary["synthetic_command_templates"] = commands
    summary["trace_boundary"] = (
        "Only public agent messages and redacted synthetic shell commands; no reasoning items or raw event stream"
    )
    return summary, final


def post_memory(package: Path, workspace: Path, env: dict, seed: dict, output: Path) -> dict:
    result = {}
    for operation, payload in (
        ("inspect", {}),
        ("export", {"format": "json"}),
        ("recall", {"need": "workshop guests step-free quiet room", "budget_bytes": 8192}),
    ):
        request = {
            "schema": "opensocrates.project-memory.request/1.0.0",
            "request_id": str(uuid4()),
            "operation": operation,
            "project_id": seed["project_id"],
            "workspace_id": seed["workspace_id"],
            "task_id": None,
            "payload": payload,
        }
        receipt, value = setup_command(
            ["bash", str(package / "bin/launch.sh"), "memory", "codex"],
            env,
            output / f"post-{operation}.json",
            payload=request,
            cwd=workspace,
        )
        result[operation] = {"status": value.get("status"), "exit_code": receipt["exit_code"]}
        body = value.get("result") or {}
        if operation == "export":
            records = body.get("content") if isinstance(body.get("content"), list) else []
            result["exported_public_records"] = [
                {
                    key: record.get(key)
                    for key in ("record_id", "summary", "rationale", "lifecycle", "scope")
                }
                for record in records
            ]
            texts = [
                str(record.get("summary", "")) + " " + str(record.get("rationale", ""))
                for record in records
            ]
            retained = [
                text
                for record, text in zip(records, texts, strict=True)
                if record.get("lifecycle") == "accepted"
            ]
            result["export_complete"] = (
                value.get("status") == "ok" and body.get("next_cursor") is None
            )
            result["withdrawn_capacity_absent"] = bool(records) and not any(
                re.search(r"\b60\b", text) for text in texts
            )
            result["retained_intent_present"] = any(
                "52" in text
                and any(term in text.lower() for term in ("step-free", "계단", "무장애", "휠체어"))
                and any(term in text.lower() for term in ("quiet", "조용", "정숙", "휴식실"))
                for text in retained
            )
            result["record_count"] = len(records)
    return result


def cell(freeze: dict, scheduled: dict) -> dict:  # noqa: C901
    task = freeze["tasks"][scheduled["task"]]
    output = HERE / "diagnostic-results-v3" / scheduled["id"]
    output.mkdir(parents=True, exist_ok=False)
    result = {"cell": scheduled, "held_out": False, "calls": [], "stages": [], "human_score": None}
    harness.save_new(output / "cell.started.json", result)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="os-v15-diag-v3-", dir="/private/tmp") as temporary:
        base = Path(temporary)
        workspace, data = base / "workspace", base / "data"
        workspace.mkdir(mode=0o700)
        data.mkdir(mode=0o700)
        codex = base / "profile/home/.codex"
        try:
            codex, env = harness.profile(base / "profile")
            marketplace = build_marketplace(freeze, base)
            result["installation"] = install_or_check(freeze, env, marketplace, True, output)
            assert result["installation"]["ok"]
            package = installed_root(codex)
            result["installed_bytes"] = member_check(package, freeze["package_members"])
            assert result["installed_bytes"]["all_match"]
            files(workspace, task["files"])
            files(workspace, task.get("replay_files"))
            seed = None
            if scheduled["kind"] == "memory":
                env.update(
                    {
                        "OPENSOCRATES_MEMORY_FIXTURE": "1",
                        "OPENSOCRATES_DEVELOPMENT_MANIFEST": "1",
                        "OPENSOCRATES_DATA_DIR": str(data),
                    }
                )
                seed = memory_seed(package, workspace, env, task["accepted_decision"], output)
                result["seed_summary_sha256"] = seed["summary_sha256"]
                files(workspace, task["source_transition"])
            for index, user_prompt in enumerate(task["prompts"]):
                prompt = (
                    freeze["common_prompt"][task["locale"]]
                    + "\n\n"
                    + freeze["skill_prompt"][task["locale"]]
                )
                if seed:
                    prompt += "\n\n" + freeze["recall_prompt"][task["locale"]].format(
                        project_id=seed["project_id"], workspace_id=seed["workspace_id"]
                    )
                prompt += "\n\n" + user_prompt
                receipt, final = harness.invoke(
                    client=freeze["client"]["path"],
                    workspace=workspace,
                    env=env,
                    model="gpt-6-sol",
                    prompt=prompt,
                    receipt=output / f"turn-{index + 1}.json",
                    timeout=300,
                    resume=bool(index),
                    ephemeral=scheduled["kind"] == "memory",
                    extra_dir=data,
                )
                result["calls"].append(f"turn-{index + 1}.json")
                harness.save_new(
                    output / f"artifact-{index + 1}.json",
                    retain_stage(task, workspace, final, base),
                )
                result["stages"].append(f"artifact-{index + 1}.json")
                if not receipt["process_success"]:
                    break
            result["process_complete"] = len(result["calls"]) == len(task["prompts"]) and all(
                json.loads((output / name).read_text())["process_success"]
                for name in result["calls"]
            )
            if seed:
                result["memory_postcheck"] = post_memory(package, workspace, env, seed, output)
                plan = json.loads((workspace / "plan.json").read_text())
                result["artifact_pass"] = (
                    plan.get("selected_venue") == "Harbor"
                    and plan.get("attendees") == 52
                    and plan.get("status") == "proposed_unbooked"
                )
                post = result["memory_postcheck"]
                result["memory_forgetting_verified"] = all(
                    post.get(key) is True
                    for key in (
                        "export_complete",
                        "withdrawn_capacity_absent",
                        "retained_intent_present",
                    )
                ) and all(
                    post[operation]["status"] == "ok"
                    for operation in ("inspect", "export", "recall")
                )
                result["diagnostic_pass"] = (
                    result["process_complete"]
                    and result["artifact_pass"]
                    and result["memory_forgetting_verified"]
                )
            else:
                from checks_v2 import evaluate

                result["original_strict_check"] = evaluate(task, workspace, final)
                messages = json.loads((output / result["calls"][-1]).read_text())["public_messages"]
                result["question_in_any_public_message_heuristic"] = any(
                    "?" in message and ("100" in message or "850" in message)
                    for message in messages
                )
                result["diagnostic_pass"] = (
                    result["process_complete"] and result["original_strict_check"]["all_pass"]
                )
                result["semantic_dialogue_score"] = None
        except Exception as error:
            result["error"] = type(error).__name__
            result["diagnostic_pass"] = False
            result["calls"] = sorted(
                path.name
                for path in output.glob("turn-*.json")
                if not path.name.endswith("started.json")
            )
        finally:
            result["native_tables"] = harness.native_counts(codex)
            (codex / "auth.json").unlink(missing_ok=True)
            result["auth_copy_removed"] = not (codex / "auth.json").exists()
            result["wall_including_setup"] = round(time.monotonic() - started, 3)
            harness.save_new(output / "result.json", result)
    return result


def main() -> None:
    freeze, commit = harness.verify_freeze(HERE / "diagnostic-freeze.v3.json")
    # Do not compete for account resources with the separately frozen v2 matrix.
    initial = json.loads((HERE / "execution-freeze.v2.json").read_text())
    if any(
        not (HERE / "results-v2" / entry["id"] / "result.json").exists()
        for entry in initial["cells"]
    ):
        raise SystemExit("The earlier pilot still has unfinished cells; diagnostic not started")
    harness.summarize = trace_public
    with ThreadPoolExecutor(max_workers=2) as pool:
        for result in pool.map(lambda row: cell(freeze, row), freeze["cells"]):
            print(result["cell"]["id"], result["diagnostic_pass"], flush=True)
    print("Diagnostic freeze", commit)


if __name__ == "__main__":
    main()
