"""Bounded installed-package comparison; all state is disposable and synthetic."""

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
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from checks import accepted_intent, evaluate, question_observation

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "expanded"))
from harness_v4 import native_counts, profile, summarize  # noqa: E402
from runner_v2 import files, public_text  # noqa: E402

COUNTER_LOCK = threading.Lock()
STOP = threading.Event()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def command(args, env, cwd=None, payload=None):
    start = time.monotonic()
    proc = subprocess.run(
        args,
        input=json.dumps(payload) if payload is not None else None,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    try:
        value = json.loads(proc.stdout)
    except ValueError:
        value = None
    receipt = {
        "exit_code": proc.returncode,
        "wall_seconds": round(time.monotonic() - start, 3),
        "stdout_sha256": hashlib.sha256(proc.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(proc.stderr.encode()).hexdigest(),
    }
    return receipt, value


def install(manifest, arm, base, env, output):
    archive = Path(arm["archive_path"])
    assert sha(archive) == arm["archive_sha256"]
    marketplace = base / "marketplace"
    package = marketplace / "plugin"
    package.mkdir(parents=True)
    with zipfile.ZipFile(archive) as source:
        assert source.testzip() is None
        for member in source.infolist():
            path = Path(member.filename)
            assert not path.is_absolute() and ".." not in path.parts
            if member.is_dir():
                (package / path).mkdir(parents=True, exist_ok=True)
            else:
                target = package / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read(member))
                target.chmod(0o755 if (member.external_attr >> 16) & 0o111 else 0o644)
    metadata = read(package / ".codex-plugin/plugin.json")
    assert metadata["version"] == arm["package_version"]
    save(
        marketplace / ".agents/plugins/marketplace.json",
        {
            "name": "os-practical",
            "plugins": [
                {
                    "name": "opensocrates",
                    "source": {"source": "local", "path": "./plugin"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Productivity",
                }
            ],
        },
    )
    receipts = []
    for action, args in (
        ("marketplace", ["plugin", "marketplace", "add", str(marketplace), "--json"]),
        ("install", ["plugin", "add", "opensocrates@os-practical", "--json"]),
        ("inventory", ["plugin", "list", "--json"]),
    ):
        receipt, value = command([manifest["client"]["path"], *args], env)
        save(output / f"setup-{action}.json", {**receipt, "operation": action})
        receipts.append(receipt)
        if receipt["exit_code"]:
            raise RuntimeError("disposable plugin setup failed: " + action)
    identities = [
        {k: x.get(k) for k in ("pluginId", "version", "enabled", "installed")}
        for x in value.get("installed", [])
        if x.get("name") == "opensocrates"
    ]
    assert len(identities) == 1 and identities[0]["version"] == arm["package_version"]
    assert identities[0]["enabled"] and identities[0]["installed"]
    codex = Path(env["CODEX_HOME"])
    installed = list(codex.glob("plugins/cache/**/skills/opensocrates/SKILL.md"))
    assert len(installed) == 1
    root = installed[0].parents[2]
    for name, digest in arm["members"].items():
        assert sha(root / name) == digest, name
    assert os.access(root / "bin/launch.sh", os.X_OK)
    assert os.access(
        root / "runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime", os.X_OK
    )
    save(
        output / "installation.json",
        {
            "inventory": identities,
            "member_hashes": arm["members"],
            "bytes_match": True,
            "executable_modes": True,
            "operations": receipts,
        },
    )
    return root


def memory_call(package, workspace, env, operation, payload, project=None, binding=None):
    request = {
        "schema": "opensocrates.project-memory.request/1.0.0",
        "request_id": str(uuid4()),
        "operation": operation,
        "project_id": project,
        "workspace_id": binding,
        "task_id": None,
        "payload": payload,
    }
    receipt, response = command(
        ["bash", str(package / "bin/launch.sh"), "memory", "codex"], env, workspace, request
    )
    if not isinstance(response, dict):
        raise ValueError("missing native memory response")
    return {
        "operation": operation,
        "request_id": request["request_id"],
        **receipt,
        "status": response.get("status"),
    }, response


def seed_memory(package, workspace, env, scenario, output):
    operations = []
    payload = {
        "root": str(workspace),
        "apply": False,
        "mode": "read_write",
        "capture_policy": "milestones",
        "excluded_paths": [],
    }
    receipt, response = memory_call(package, workspace, env, "init", payload)
    operations.append(receipt)
    assert response["status"] == "ok"
    payload.update(
        {
            "apply": True,
            "disclosure_digest": response["result"]["disclosure_digest"],
            "authorization_basis": "fixture:practical-authorized-enrollment",
            "authorization_attribution": "operator_declared",
            "idempotency_key": str(uuid4()),
        }
    )
    receipt, response = memory_call(package, workspace, env, "init", payload)
    operations.append(receipt)
    assert response["status"] == "ok"
    project, binding = response["result"]["project_id"], response["result"]["workspace_id"]
    records = []
    for accepted, summaries in (
        (True, scenario.get("accepted_records", [])),
        (False, scenario.get("proposed_records", [])),
    ):
        for summary in summaries:
            payload = {
                "idempotency_key": str(uuid4()),
                "expected_record_version": 0,
                "kind": "decision",
                "scope": {"level": "project"},
                "summary": summary,
                "origin": {
                    "producer_kind": "agent",
                    "source_reference": None,
                    "attestation": "agent_reported",
                },
                "support": "agent_reported",
                "source_refs": [],
                "revalidation": {
                    "dependency_paths": [],
                    "negative_claim": False,
                    "on_change": "not_applicable",
                },
            }
            receipt, response = memory_call(
                package, workspace, env, "record", payload, project, binding
            )
            operations.append(receipt)
            assert response["status"] == "ok"
            record = response["result"]["record"]
            if accepted:
                payload = {
                    "record_id": record["record_id"],
                    "expected_record_version": record["version"],
                    "idempotency_key": str(uuid4()),
                    "acceptance_basis": "fixture:practical-user-intent",
                    "acceptance_attribution": "operator_declared",
                }
                receipt, response = memory_call(
                    package, workspace, env, "accept", payload, project, binding
                )
                operations.append(receipt)
                assert response["status"] == "ok"
                record = response["result"]["record"]
            records.append(record)
    save(
        output / "memory-before.json",
        {
            "records": records,
            "operations": operations,
            "authority": "Synthetic public facts explicitly authorized by the frozen task",
        },
    )
    return {"project_id": project, "workspace_id": binding, "records": records}


def note_seed(scenario):
    value = {
        "accepted": [
            {"id": f"accepted-{i}", "summary": s}
            for i, s in enumerate(scenario.get("accepted_records", []))
        ],
        "proposed": [
            {"id": f"proposed-{i}", "summary": s}
            for i, s in enumerate(scenario.get("proposed_records", []))
        ],
    }
    return (
        "# Maintained project notes\n\nAccepted items are authorized intent; proposed items are not.\n\n```json\n"
        + json.dumps(value, indent=2)
        + "\n```\n"
    )


def capture(raw, base):
    summary, final = summarize(raw)
    messages, actions, errors = [], [], []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") in {"error", "turn.failed"}:
            errors.append(public_text(json.dumps(event), base))
        if event.get("type") != "item.completed":
            continue
        item = event.get("item") or {}
        if item.get("type") == "agent_message":
            messages.append(public_text(item.get("text", ""), base))
        if item.get("type") == "command_execution":
            actions.append(
                {
                    "command": public_text(item.get("command", ""), base),
                    "exit_code": item.get("exit_code"),
                    "status": item.get("status"),
                }
            )
    summary.update(
        {
            "public_messages": messages,
            "commands": actions,
            "error_events": errors,
            "trace_boundary": "Synthetic public messages and command templates only; no reasoning or raw event stream retained",
        }
    )
    return summary, public_text(final, base)


def invoke(manifest, scenario, stage, workspace, base, env, prompt, output):
    with COUNTER_LOCK:
        started = list((HERE / "results").glob("*/call-*.started.json"))
        if len(started) >= manifest["limits"]["initial_model_invocations"] or STOP.is_set():
            raise RuntimeError("comparison budget exhausted or transport lane stopped")
        receipt_path = output / f"call-{stage + 1}.json"
        save(
            receipt_path.with_suffix(".started.json"),
            {
                "started_unix": time.time(),
                "model": manifest["model"],
                "effort": manifest["effort"],
                "client_sha256": manifest["client"]["sha256"],
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "attempt": 1,
                "stage": stage,
            },
        )
    resume = bool(stage and not scenario.get("fresh_followup"))
    args = [manifest["client"]["path"], "--no-daemon", "--ask-for-approval", "never", "exec"]
    if resume:
        args += [
            "resume",
            "--last",
            "--skip-git-repo-check",
            "-c",
            'sandbox_mode="workspace-write"',
        ]
    else:
        args += [
            "--sandbox",
            "workspace-write",
            "--skip-git-repo-check",
            "--ignore-rules",
            "-C",
            str(workspace),
            "--add-dir",
            str(base / "data"),
        ]
        if scenario.get("fresh_followup") or len(scenario["prompts"]) == 1:
            args += ["--ephemeral"]
    args += [
        "--json",
        "--disable",
        "multi_agent",
        "--disable",
        "memories",
        "--disable",
        "external_agent_memory_import",
        "-c",
        "memories.use_memories=false",
        "-c",
        "memories.generate_memories=false",
        "-c",
        'shell_environment_policy.inherit="all"',
        "-m",
        manifest["model"],
        "-c",
        'model_reasoning_effort="' + manifest["effort"] + '"',
    ]
    args += ["--dangerously-bypass-hook-trust"] if scenario["hooks"] else ["--disable", "hooks"]
    args += ["-"]
    start = time.monotonic()
    proc = None
    stdout = stderr = ""
    error = None
    timeout = False
    try:
        proc = subprocess.Popen(
            args,
            cwd=workspace,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(
                prompt, timeout=manifest["limits"]["per_invocation_seconds"]
            )
        except subprocess.TimeoutExpired:
            timeout = True
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate(timeout=10)
    except OSError as exc:
        error = type(exc).__name__
    summary, final = capture(stdout, base)
    result = {
        **summary,
        "exit_code": proc.returncode if proc else None,
        "wall_seconds": round(time.monotonic() - start, 3),
        "timed_out": timeout,
        "invocation_error": error,
        "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
        "model": manifest["model"],
        "effort": manifest["effort"],
        "client_version": manifest["client"]["version"],
    }
    result["process_success"] = (
        result["exit_code"] == 0
        and result["turn_completed"]
        and not result["errors"]
        and not timeout
        and error is None
    )
    save(receipt_path, result)
    if not result["process_success"]:
        STOP.set()
    return result, final


def post_memory(package, workspace, env, seed, output, stage):
    values = {}
    receipts = []
    for op, payload in (
        ("inspect", {}),
        ("export", {"format": "json"}),
        (
            "recall",
            {"need": "accepted workshop constraints source correction", "budget_bytes": 8192},
        ),
    ):
        receipt, response = memory_call(
            package, workspace, env, op, payload, seed["project_id"], seed["workspace_id"]
        )
        receipts.append(receipt)
        values[op] = response
    exported = values["export"]
    body = exported.get("result") or {}
    records = body.get("content", [])
    result = {
        "operations": receipts,
        "records": records,
        "export_complete": exported.get("status") == "ok" and body.get("next_cursor") is None,
        "recall": values["recall"],
        "inspect": values["inspect"],
    }
    save(output / f"memory-after-{stage + 1}.json", result)
    return result


def episode(manifest, scenario, arm, setup_only=False, preflight_id="preflight"):  # noqa: C901
    output = (
        HERE / (preflight_id if setup_only else "results") / (scenario["id"] + "--" + arm["id"])
    )
    if not setup_only and output.exists():
        if (output / "result.json").exists():
            return read(output / "result.json")
        raise RuntimeError("Unfinished attempted episode requires explicit reconciliation")
    output.mkdir(parents=True, exist_ok=False)
    result = {
        "scenario": scenario["id"],
        "locale": scenario["locale"],
        "arm": arm["id"],
        "package_version": arm["package_version"],
        "package_sha256": arm["archive_sha256"],
        "calls": [],
        "stages": [],
        "checks": [],
        "setup_only": setup_only,
    }
    with tempfile.TemporaryDirectory(prefix="os-v15-practical-", dir="/private/tmp") as temporary:
        base = Path(temporary)
        workspace = base / "workspace"
        data = base / "data"
        support = base / "support"
        for folder in (workspace, data, support):
            folder.mkdir(mode=0o700)
        codex, env = profile(base / "profile")
        env.update(
            {
                "OPENSOCRATES_MEMORY_FIXTURE": "1",
                "OPENSOCRATES_DEVELOPMENT_MANIFEST": "1",
                "OPENSOCRATES_DATA_DIR": str(data),
            }
        )
        (codex / "config.toml").write_text(
            'cli_auth_credentials_store = "file"\nweb_search = "disabled"\n[features]\nmulti_agent = false\nmemories = false\nexternal_agent_memory_import = false\n[memories]\nuse_memories = false\ngenerate_memories = false\n'
        )
        try:
            files(workspace, scenario["files"])
            if scenario["git"]:
                for args in (
                    ["git", "init", "-q"],
                    ["git", "add", "."],
                    [
                        "git",
                        "-c",
                        "user.name=Fixture",
                        "-c",
                        "user.email=fixture@example.invalid",
                        "commit",
                        "-qm",
                        "Initial practical fixture",
                    ],
                ):
                    subprocess.run(args, cwd=workspace, env=env, capture_output=True, check=True)
            package = install(manifest, arm, base, env, output)
            seed = None
            tool = None
            if scenario["continuity"] and arm["memory"]:
                seed = seed_memory(package, workspace, env, scenario, output)
                tool = support / "memory_tool.py"
                shutil.copyfile(HERE / "memory_tool.py", tool)
                tool.chmod(0o400)
                save(
                    tool.with_suffix(".json"),
                    {
                        "launcher": str(package / "bin/launch.sh"),
                        "workspace": str(workspace),
                        "project_id": seed["project_id"],
                        "workspace_id": seed["workspace_id"],
                        "audit_log": str(data / "evaluation-memory-operations.jsonl"),
                    },
                )
            elif scenario["continuity"]:
                (workspace / "PROJECT_NOTES.md").write_text(note_seed(scenario))
                save(
                    output / "note-before.json",
                    {
                        "text": (workspace / "PROJECT_NOTES.md").read_text(),
                        "maintenance": "Harness-seeded public facts, same accepted/proposed content as candidate",
                    },
                )
            if setup_only:
                if seed:
                    result["postcheck"] = post_memory(package, workspace, env, seed, output, 0)
                    probe = {
                        "schema": "opensocrates.project-memory.request/1.0.0",
                        "request_id": str(uuid4()),
                        "operation": "inspect",
                        "project_id": seed["project_id"],
                        "workspace_id": seed["workspace_id"],
                        "task_id": None,
                        "payload": {},
                    }
                    probe_receipt, probe_response = command(
                        [sys.executable, str(tool)], env, workspace, probe
                    )
                    audit = [
                        json.loads(line)
                        for line in (data / "evaluation-memory-operations.jsonl")
                        .read_text()
                        .splitlines()
                    ]
                    assert (
                        probe_response["status"] == "ok"
                        and audit[-1]["request_id"]
                        == probe["request_id"]
                        == audit[-1]["response_request_id"]
                    )
                    result["adapter_operation_verified"] = True
                    save(
                        output / "adapter-probe.json",
                        {"process": probe_receipt, "operation_receipts": audit},
                    )
                result["setup_success"] = True
                return result
            for stage, request in enumerate(scenario["prompts"]):
                if STOP.is_set():
                    break
                if stage:
                    files(workspace, scenario.get("transition"))
                if stage and scenario.get("fresh_followup"):
                    (codex / "auth.json").unlink(missing_ok=True)
                    codex, env = profile(base / f"fresh-profile-{stage}")
                    env.update(
                        {
                            "OPENSOCRATES_MEMORY_FIXTURE": "1",
                            "OPENSOCRATES_DEVELOPMENT_MANIFEST": "1",
                            "OPENSOCRATES_DATA_DIR": str(data),
                        }
                    )
                    (codex / "config.toml").write_text(
                        'cli_auth_credentials_store = "file"\nweb_search = "disabled"\n'
                    )
                    package = install(
                        manifest,
                        arm,
                        base / f"fresh-install-{stage}",
                        env,
                        output / f"fresh-install-{stage}",
                    )
                    if tool:
                        configuration = read(tool.with_suffix(".json"))
                        configuration["launcher"] = str(package / "bin/launch.sh")
                        tool.with_suffix(".json").write_text(json.dumps(configuration))
                    # Exact package bytes are freshly installed; no prior session/native memory.
                prompt = (
                    manifest["common_prompt"]
                    + f"\nInstalled controller: {package}/skills/opensocrates/SKILL.md\n"
                )
                if scenario["continuity"]:
                    if seed:
                        prompt += f"An explicitly enrolled disposable project contains the prior public decisions. project_id={seed['project_id']}; workspace_id={seed['workspace_id']}. Use the installed guidance and native memory schema. For operation evidence, send the unchanged JSON request on stdin to `python3 {tool}`; this transparent evaluation adapter forwards to the installed launcher without altering requests and records only operation/ID/status metadata outside product memory. Do not bypass or modify the adapter, its config or audit log. No further enrollment or project deletion is authorized.\n"
                    else:
                        prompt += "The released version has no structured project-memory API. The usable maintained-note control is PROJECT_NOTES.md. Read it for accepted/proposed state, maintain it as authorized, and preserve unrelated content. Do not invent a nonexistent memory API.\n"
                prompt += "\n" + request
                source = {
                    str(f.relative_to(workspace)): f.read_text()
                    for f in workspace.rglob("*")
                    if f.is_file() and ".git" not in f.parts and f.suffix in (".py", ".json", ".md")
                }
                save(output / f"source-before-{stage + 1}.json", source)
                receipt, final = invoke(
                    manifest, scenario, stage, workspace, base, env, prompt, output
                )
                result["calls"].append(f"call-{stage + 1}.json")
                artifacts = {
                    name: public_text((workspace / name).read_text(), base)
                    if (workspace / name).exists()
                    else None
                    for name in scenario["artifacts"]
                }
                stage_value = {
                    "artifacts": artifacts,
                    "public_messages": receipt["public_messages"],
                    "public_final": final,
                    "question_candidates": question_observation(receipt["public_messages"]),
                }
                save(output / f"stage-{stage + 1}.json", stage_value)
                result["stages"].append(f"stage-{stage + 1}.json")
                try:
                    checks = evaluate(scenario, workspace, stage, receipt["public_messages"])
                except (OSError, ValueError, SyntaxError, TypeError, KeyError) as error:
                    checks = {
                        "artifact_check_completed": False,
                        "artifact_error": type(error).__name__,
                    }
                if seed:
                    state = post_memory(package, workspace, env, seed, output, stage)
                    log = data / "evaluation-memory-operations.jsonl"
                    operations = (
                        [json.loads(line) for line in log.read_text().splitlines()]
                        if log.exists()
                        else []
                    )
                    save(output / f"memory-operations-{stage + 1}.json", operations)
                    checks["audit_adapter_unchanged"] = sha(tool) == sha(HERE / "memory_tool.py")
                    checks["native_operation_ids_correlate"] = any(
                        x["status"] == "ok" for x in operations
                    ) and all(
                        x["request_id"] == x["response_request_id"]
                        for x in operations
                        if x["status"] == "ok"
                    )
                    if scenario["id"] == "continuity" and stage:
                        records = state["records"]
                        by_id = {r["record_id"]: r for r in records}
                        original, unrelated, proposal = seed["records"]
                        checks.update(
                            {
                                "complete_export": state["export_complete"],
                                "retained_intent_accepted": accepted_intent(records),
                                "exact_withdrawn_record_absent": original["record_id"] not in by_id,
                                "withdrawn_fact_absent": all(
                                    not re.search(
                                        r"\b60\b",
                                        r.get("summary", "") + " " + str(r.get("rationale", "")),
                                    )
                                    for r in records
                                ),
                                "unrelated_record_preserved": by_id.get(unrelated["record_id"])
                                == unrelated,
                                "proposal_not_promoted": by_id.get(proposal["record_id"], {}).get(
                                    "lifecycle"
                                )
                                == "proposed",
                                "observed_exact_delete": any(
                                    x["operation"] == "delete"
                                    and x["target_record_id"] == original["record_id"]
                                    and x["status"] == "ok"
                                    for x in operations
                                ),
                                "observed_acceptance": any(
                                    x["operation"] == "accept" and x["status"] == "ok"
                                    for x in operations
                                ),
                            }
                        )
                elif scenario["continuity"] and scenario["id"] == "continuity" and stage:
                    note = (workspace / "PROJECT_NOTES.md").read_text()
                    checks.update(
                        {
                            "withdrawn_fact_absent": not re.search(r"\b60\b", note),
                            "retained_intent": all(
                                x in note.lower() for x in ("52", "step-free", "quiet")
                            ),
                            "unrelated_note_preserved": "blue" in note.lower(),
                            "proposed_stays_marked": "proposed" in note.lower()
                            and "unapproved" in note.lower(),
                        }
                    )
                result["checks"].append(checks)
                if not receipt["process_success"]:
                    break
            result["all_calls_complete"] = len(result["calls"]) == len(scenario["prompts"]) and all(
                read(output / name)["process_success"] for name in result["calls"]
            )
            result["artifact_and_state_checks_pass"] = result["all_calls_complete"] and all(
                all(value is True for value in checks.values()) for checks in result["checks"]
            )
            result["dialogue_review"] = (
                "pending integrator review of all retained public messages; no independent human score"
            )
            result["native_memory_tables"] = native_counts(codex)
        except Exception as exc:
            result["runner_error"] = type(exc).__name__
            result["runner_error_detail"] = public_text(str(exc), base)[:1000]
            STOP.set()
        finally:
            for auth in base.glob("**/auth.json"):
                auth.unlink()
            result["auth_copies_removed"] = not list(base.glob("**/auth.json"))
            save(output / "result.json", result)
    return result


def verify(manifest):
    for name, digest in manifest["files"].items():
        assert sha(ROOT / name) == digest, name
    assert sha(manifest["client"]["path"]) == manifest["client"]["sha256"]
    for arm in manifest["arms"]:
        assert sha(arm["archive_path"]) == arm["archive_sha256"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--preflight-id", default="preflight")
    parser.add_argument("--scenario")
    args = parser.parse_args()
    manifest = read(HERE / "manifest.v1.json")
    verify(manifest)
    if not args.preflight:
        relative = str((HERE / "manifest.v1.json").relative_to(ROOT))
        assert (
            subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT)
            == (HERE / "manifest.v1.json").read_bytes()
        )
    tasks = {x["id"]: x for x in read(HERE / "fixtures.v1.json")["scenarios"]}
    if args.preflight:
        for arm in manifest["arms"]:
            result = episode(manifest, tasks["continuity"], arm, True, args.preflight_id)
            print(
                json.dumps(
                    {k: v for k, v in result.items() if k not in ("postcheck",)}, ensure_ascii=False
                ),
                flush=True,
            )
        return
    for scenario_id in manifest["scenario_order"]:
        if args.scenario and scenario_id != args.scenario:
            continue
        if STOP.is_set():
            break
        task = tasks[scenario_id]
        with ThreadPoolExecutor(max_workers=2) as pool:
            for result in pool.map(
                lambda arm, task=task: episode(manifest, task, arm), manifest["arms"]
            ):
                print(
                    json.dumps(
                        {
                            k: result.get(k)
                            for k in (
                                "scenario",
                                "arm",
                                "artifact_and_state_checks_pass",
                                "runner_error",
                                "runner_error_detail",
                            )
                        }
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    main()
