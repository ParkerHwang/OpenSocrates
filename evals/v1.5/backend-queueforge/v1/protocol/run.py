"""Prospectively frozen nine-call, three-condition backend experiment."""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT.parent / "OpenSocrates-v1.5.0-implementation"
PRACTICAL = PRODUCT / "evals/v1.5/practical"
sys.path.insert(0, str(PRACTICAL))
spec = importlib.util.spec_from_file_location(
    "comparison_helpers", PRACTICAL / "runner.py"
)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
spec = importlib.util.spec_from_file_location(
    "queue_benchmark", ROOT / "benchmark/runner.py"
)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def bounded_command(args, cwd, env, seconds):
    begin = time.monotonic()
    proc = None
    try:
        proc = subprocess.Popen(
            args,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        stdout, stderr = proc.communicate(timeout=seconds)
        return {
            "command": args,
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": False,
            "wall_seconds": time.monotonic() - begin,
        }
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate(timeout=10)
        return {
            "command": args,
            "exit_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
            "wall_seconds": time.monotonic() - begin,
        }
    except OSError as error:
        return {
            "command": args,
            "exit_code": None,
            "stdout": "",
            "stderr": str(error),
            "timed_out": False,
            "wall_seconds": time.monotonic() - begin,
        }
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def verify(manifest, digest):
    assert sha(manifest) == digest, "freeze changed"
    frozen = read(manifest)
    assert frozen["model"] == "gpt-6-sol" and frozen["effort"] == "medium"
    assert frozen["limits"]["model_calls"] == 9
    assert len(frozen["arms"]) == 3
    for relative, expected in frozen["files"].items():
        assert sha(ROOT / relative) == expected, relative
    for relative, expected in frozen["helper_files"].items():
        assert sha(PRODUCT / relative) == expected, relative
    assert sha(frozen["client"]["path"]) == frozen["client"]["sha256"]
    for arm in frozen["arms"]:
        if arm.get("archive_path"):
            assert sha(arm["archive_path"]) == arm["archive_sha256"]
    return frozen


def clone_cache(source, destination):
    # APFS copy-on-write keeps independent cache namespaces without shared writers.
    proc = subprocess.run(
        ["cp", "-cR", str(source), str(destination)], capture_output=True
    )
    if proc.returncode:
        if destination.exists():
            raise RuntimeError("partial cache clone; preserve for diagnosis")
        shutil.copytree(source, destination)


def setup_arm(manifest, arm, base):
    name = arm["id"]
    workspace = ROOT / "apps" / name
    shutil.copytree(ROOT / "seed", workspace)
    (workspace / "BRIEF.md").write_text((ROOT / "protocol/stage1.md").read_text())
    for args in (
        ["git", "init", "-q"],
        ["git", "add", "."],
        [
            "git",
            "-c",
            "user.name=QueueForge",
            "-c",
            "user.email=queueforge@example.invalid",
            "commit",
            "-qm",
            "Common pinned QueueForge starter",
        ],
    ):
        subprocess.run(args, cwd=workspace, check=True, capture_output=True)
    output = ROOT / "evidence" / name
    save(
        output / "starter.json",
        {
            "tree": subprocess.check_output(
                ["git", "rev-parse", "HEAD^{tree}"], cwd=workspace, text=True
            ).strip()
        },
    )
    clone_cache(ROOT / "toolchain/modcache", workspace / ".gomodcache")
    clone_cache(ROOT / "toolchain/gocache", workspace / ".gocache")
    (workspace / ".owned-temp").mkdir()
    data = base / "data"
    data.mkdir(mode=0o700)
    codex, env = helpers.profile(base / "profile")
    env.update(
        {
            "GOMODCACHE": str(workspace / ".gomodcache"),
            "GOCACHE": str(workspace / ".gocache"),
            "GOTOOLCHAIN": "local",
            "GOPROXY": "off",
            "GOMAXPROCS": "4",
            "TMPDIR": str(workspace / ".owned-temp"),
            "OPENSOCRATES_DATA_DIR": str(data),
            "OPENSOCRATES_MEMORY_FIXTURE": "1",
            "OPENSOCRATES_DEVELOPMENT_MANIFEST": "1",
        }
    )
    (codex / "config.toml").write_text(
        'cli_auth_credentials_store = "file"\nweb_search = "disabled"\n[features]\nremote_plugin = false\napps = false\nhooks = false\nmulti_agent = false\nmemories = false\nexternal_agent_memory_import = false\n[memories]\nuse_memories = false\ngenerate_memories = false\n[apps._default]\nenabled = false\n'
    )
    package, seed = None, None
    if arm.get("archive_path"):
        package = helpers.install(manifest, arm, base, env, output)
    else:
        receipt, inventory = helpers.command(
            [manifest["client"]["path"], "plugin", "list", "--json"], env
        )
        assert receipt["exit_code"] == 0 and isinstance(inventory, dict)
        assert not inventory.get("installed"), "vanilla has extra installed plugins"
        save(
            output / "vanilla-inventory.json",
            {
                "receipt": receipt,
                "installed": inventory.get("installed", []),
                "personal_instructions": "empty disposable home; --ignore-rules",
            },
        )
    if arm["memory"]:
        seed = helpers.seed_memory(
            package,
            workspace,
            env,
            {"accepted_records": manifest["accepted_intent"]},
            output,
        )
        config = {
            "launcher": str(package / "bin/launch.sh"),
            "workspace": str(workspace),
            "project_id": seed["project_id"],
            "workspace_id": seed["workspace_id"],
            "audit_log": str(data / "operations.jsonl"),
        }
        shutil.copyfile(PRACTICAL / "memory_tool.py", workspace / "memory_tool.py")
        (workspace / "memory_tool.json").write_text(json.dumps(config, indent=2) + "\n")
        (workspace / "MEMORY_USAGE.md").write_text(
            f"Read the installed checkpoint guide at {package / 'skills/opensocrates/references/assistance/checkpoint.en.md'}.\nUse stable task_id `{arm['task_id']}` for all sessions. Project/workspace identities are in memory_tool.json. Send complete unchanged native envelopes to python3 memory_tool.py; the adapter injects nothing and records operation receipts. Use relevant source-aware recall and inspect before relying on state, then capture bounded public milestones with caller-safe agent_reported actions. No raw prompts, code copies, tool dumps, credentials or hidden reasoning in memory. A rejected memory call does not erase source facts or block independent work.\n"
        )
    else:
        (workspace / "PROJECT_NOTES.md").write_text(
            helpers.note_seed(
                {
                    "accepted_records": manifest["accepted_intent"],
                    "proposed_records": [],
                }
            )
        )
    return {
        "arm": arm,
        "base": base,
        "workspace": workspace,
        "data": data,
        "codex": codex,
        "env": env,
        "package": package,
        "seed": seed,
        "stages": {},
    }


def native_projection(state, output):
    if not state["seed"]:
        return
    values = {}
    for op, payload in [
        ("inspect", {}),
        ("recall", {"need": "continue QueueForge task", "budget_bytes": 8192}),
    ]:
        request = {
            "schema": "opensocrates.project-memory.request/1.0.0",
            "request_id": str(uuid4()),
            "operation": op,
            "project_id": state["seed"]["project_id"],
            "workspace_id": state["seed"]["workspace_id"],
            "task_id": state["arm"]["task_id"],
            "payload": payload,
        }
        receipt, result = helpers.command(
            [str(state["package"] / "bin/launch.sh"), "memory", "codex"],
            state["env"],
            state["workspace"],
            request,
        )
        values[op] = {"receipt": receipt, "response": result}
    save(output / "memory-state.json", values)


def invoke(manifest, state, stage):
    arm, workspace, base = state["arm"], state["workspace"], state["base"]
    output = ROOT / "evidence" / arm["id"] / f"stage{stage}"
    output.mkdir(parents=True, exist_ok=False)
    if state.get("access_blocked"):
        save(
            output / "skipped.json",
            {"reason": "unchanged model/client access blocker; no repeated invocation"},
        )
        return output
    brief = (ROOT / f"protocol/stage{stage}.md").read_text()
    if stage > 1:
        (workspace / f"FOLLOW_UP_{stage - 1}.md").write_text(brief)
    if arm["memory"]:
        condition = "This synthetic project is explicitly enrolled under milestones. Read MEMORY_USAGE.md and use the installed native memory for relevant continuity/milestones. Preserve accepted intent separately from current source facts. All sessions use the same task UUID. Capture only bounded allowed public state; own actions use agent_reported, not native execution claims."
    else:
        condition = "Read and maintain PROJECT_NOTES.md as a competent bounded continuity record, carrying accepted intent, decisions, progress and next actions. Verify current source instead of treating notes as current implementation facts. Do not retain raw prompts, transcripts or code copies in notes."
    if state["package"]:
        condition += f"\nUse the installed OpenSocrates controller/guidance appropriately: {state['package'] / 'skills/opensocrates/SKILL.md'}. Mechanical work needs no canonical method."
    else:
        condition += "\nThis condition is plain Codex without extra plugins/personal instructions. Use its ordinary coding capabilities and do not install a plugin."
    prompt = manifest["common_prompt"] + "\n\n" + brief + "\n\n" + condition
    if stage == 3:
        prompt += (
            "\nRead FEEDBACK.json for your own frozen stage2 API/load observations."
        )
    (output / "prompt.md").write_text(
        prompt.replace(str(base), "<DISPOSABLE>").replace(str(workspace), "<WORKSPACE>")
    )
    args = [
        manifest["client"]["path"],
        "--no-daemon",
        "--ask-for-approval",
        "never",
        "exec",
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--ignore-rules",
        "-C",
        str(workspace),
        "--add-dir",
        str(state["data"]),
        "--ephemeral",
        "--json",
    ]
    for feature in [
        "multi_agent",
        "memories",
        "external_agent_memory_import",
        "hooks",
        "remote_plugin",
        "apps",
    ]:
        args += ["--disable", feature]
    args += [
        "-c",
        "memories.use_memories=false",
        "-c",
        "memories.generate_memories=false",
        "-c",
        'shell_environment_policy.inherit="all"',
        "-c",
        "sandbox_workspace_write.network_access=true",
        "-m",
        manifest["model"],
        "-c",
        f'model_reasoning_effort="{manifest["effort"]}"',
        "-",
    ]
    started = {
        "arm": arm["id"],
        "stage": stage,
        "attempt": 1,
        "model": manifest["model"],
        "effort": manifest["effort"],
        "client_sha256": manifest["client"]["sha256"],
        "package_sha256": arm.get("archive_sha256"),
        "started_unix": time.time(),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "fresh_context": True,
    }
    assert len(list((ROOT / "evidence").glob("*/stage*/call.started.json"))) < 9
    save(output / "call.started.json", started)
    audit = state["data"] / "operations.jsonl"
    before = len(audit.read_text().splitlines()) if audit.exists() else 0
    emit({"event": "model-start", "arm": arm["id"], "stage": stage})
    begin = time.monotonic()
    proc, stdout, stderr, start_error = None, "", "", None
    timeout = False
    try:
        proc = subprocess.Popen(
            args,
            cwd=workspace,
            env=state["env"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(
                prompt, timeout=manifest["limits"]["seconds_per_call"]
            )
        except subprocess.TimeoutExpired:
            timeout = True
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate(timeout=10)
    except OSError as error:
        start_error = str(error)
    receipt, final = helpers.capture(stdout, base)
    # Public synthetic evidence only; raw event streams and reasoning are discarded.
    receipt = json.loads(
        json.dumps(receipt)
        .replace(str(workspace), "<WORKSPACE>")
        .replace(str(ROOT), "<STUDY>")
    )
    receipt.update(started)
    receipt.update(
        exit_code=proc.returncode if proc else None,
        timed_out=timeout,
        invocation_error=start_error,
        wall_seconds=round(time.monotonic() - begin, 3),
        stderr_sha256=hashlib.sha256(stderr.encode()).hexdigest(),
    )
    receipt["process_success"] = (
        proc is not None
        and proc.returncode == 0
        and receipt["turn_completed"]
        and not timeout
        and not receipt["errors"]
    )
    error_text = json.dumps(receipt.get("error_events", [])).lower()
    state["access_blocked"] = (
        start_error is not None
        or (not receipt["turn_completed"] and not timeout)
        or (
            not receipt["turn_completed"]
            and any(
                x in error_text
                for x in [
                    "not supported",
                    "not available",
                    "usage limit",
                    "rate limit",
                    "quota",
                    "authentication",
                    "unauthorized",
                ]
            )
        )
    )
    save(output / "call.json", receipt)
    (output / "final.md").write_text(
        final.replace(str(workspace), "<WORKSPACE>") + "\n"
    )
    if audit.exists():
        save(
            output / "memory-operations.json",
            [json.loads(x) for x in audit.read_text().splitlines()[before:]],
        )
    native_projection(state, output)
    emit(
        {
            "event": "model-finish",
            "arm": arm["id"],
            "stage": stage,
            "success": receipt["process_success"],
            "seconds": receipt["wall_seconds"],
        }
    )
    return output


IGNORE = {
    ".git",
    ".gocache",
    ".gomodcache",
    ".owned-temp",
    "bin",
    "__pycache__",
    "memory_tool.py",
    "memory_tool.json",
    "MEMORY_USAGE.md",
}


def qualify_stage(state, stage):
    workspace = state["workspace"]
    output = ROOT / "evidence" / state["arm"]["id"] / f"stage{stage}"
    if (output / "skipped.json").exists():
        state["stages"][stage] = {
            "server_binary": None,
            "race_binary": None,
            "api_checks_pass": False,
            "own_tests_pass": False,
            "dependency_locks_unchanged": True,
        }
        save(output / "stage.json", state["stages"][stage])
        save(
            output / "acceptance.json",
            {
                "passed": False,
                "unavailable_reason": "development call skipped after access blocker",
                "scenarios": [],
                "requests": [],
            },
        )
        return
    target = ROOT / "snapshots" / state["arm"]["id"] / f"stage{stage}"
    shutil.copytree(
        workspace,
        target,
        ignore=lambda directory, names: [
            n
            for n in names
            if n in IGNORE or n.endswith((".sqlite", ".sqlite-wal", ".sqlite-shm"))
        ],
    )
    source_hashes = {
        str(p.relative_to(target)): sha(p) for p in target.rglob("*") if p.is_file()
    }
    subprocess.run(["git", "add", "."], cwd=workspace, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=QueueForge",
            "-c",
            "user.email=queueforge@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            f"Frozen generated stage{stage}",
        ],
        cwd=workspace,
        check=True,
        capture_output=True,
    )
    binaries = output / "bin"
    binaries.mkdir()
    builds = {}
    for kind, flags in [("server", []), ("race", ["-race"])]:
        command = [
            "go",
            "build",
            "-trimpath",
            *flags,
            "-o",
            str(binaries / kind),
            "./cmd/server",
        ]
        builds[kind] = bounded_command(command, workspace, state["env"], 240)
        builds[kind]["sha256"] = (
            sha(binaries / kind) if builds[kind]["exit_code"] == 0 else None
        )
    tests = bounded_command(
        ["go", "test", "-race", "-json", "./..."], workspace, state["env"], 240
    )
    save(output / "build.json", builds)
    save(output / "own-tests.json", tests)
    checker = output / "acceptance.json"
    if builds["race"]["exit_code"] == 0:
        args = [
            sys.executable,
            str(ROOT / "protocol/checker/acceptance.py"),
            "--binary",
            str(binaries / "race"),
            "--stage",
            str(stage),
            "--output",
            str(checker),
        ]
        legacy = state["stages"].get(1, {}).get("race_binary")
        if stage > 1 and legacy:
            args += ["--legacy-binary", legacy]
        checked = bounded_command(args, ROOT, os.environ.copy(), 190)
        save(output / "acceptance-process.json", checked)
        if not checker.exists():
            save(
                checker,
                {
                    "passed": False,
                    "unavailable_reason": "checker did not produce a report",
                    "scenarios": [],
                    "requests": [],
                },
            )
    else:
        save(
            checker,
            {
                "passed": False,
                "unavailable_reason": "race binary did not build",
                "scenarios": [],
                "requests": [],
            },
        )
    lock_problems = [
        p
        for p in ["go.mod", "go.sum"]
        if not (workspace / p).is_file() or sha(workspace / p) != sha(ROOT / "seed" / p)
    ]
    locks_ok = not lock_problems
    result = {
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=workspace, text=True
        ).strip(),
        "source_files": source_hashes,
        "server_binary": str(binaries / "server")
        if builds["server"]["exit_code"] == 0
        else None,
        "race_binary": str(binaries / "race")
        if builds["race"]["exit_code"] == 0
        else None,
        "dependency_locks_unchanged": locks_ok,
        "dependency_lock_problems": lock_problems,
        "own_tests_pass": tests["exit_code"] == 0,
        "api_checks_pass": checker.exists() and read(checker).get("passed") is True,
    }
    save(output / "stage.json", result)
    state["stages"][stage] = result
    emit(
        {
            "event": "checks-finish",
            "arm": state["arm"]["id"],
            "stage": stage,
            "checks_pass": result["api_checks_pass"],
            "locks_unchanged": locks_ok,
        }
    )


def compact_cell(directory):
    receipt = {}
    for name in ["generator.json", "result.json"]:
        path = directory / name
        if path.exists():
            raw = path.read_bytes()
            packed = gzip.compress(raw, mtime=0)
            destination = path.with_suffix(path.suffix + ".gz")
            destination.write_bytes(packed)
            receipt[name] = {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "gzip_sha256": sha(destination),
                "uncompressed_bytes": len(raw),
                "compressed_bytes": len(packed),
            }
            path.unlink()
    for suffix in ["", "-wal", "-shm"]:
        path = directory / ("cell.sqlite" + suffix)
        if path.exists():
            receipt[path.name] = {
                "sha256": sha(path),
                "bytes": path.stat().st_size,
                "removed_owned_stopped_fixture": True,
            }
            path.unlink()
    save(directory / "compression-and-cleanup.json", receipt)


def measure(manifest, states, stage):
    output = ROOT / "evidence" / f"performance-stage{stage}"
    output.mkdir(exist_ok=False)
    deadline = time.monotonic() + (900 if stage == 2 else 1800)
    seeds, rows = {}, []

    def shared_cap(_path):
        if bench.size_tree(ROOT / "evidence") > 2 * 1024**3:
            raise RuntimeError("shared two-GiB prepared database cap exceeded")

    bench.check_cap = shared_cap
    for name, state in states.items():
        binary = state["stages"][stage]["server_binary"]
        if not binary:
            save(
                output / name / "seed-unavailable.json",
                {"reason": "server binary unavailable"},
            )
            continue
        try:
            shared_cap(output)
            seeds[name] = bench.prepare_seed(binary, output / name / "seed", {})
        except Exception as error:
            save(output / name / "seed-unavailable.json", {"reason": str(error)})
    for cell in manifest["performance_cells"][str(stage)]:
        name = cell["arm"]
        if name not in seeds:
            rows.append({"config": cell, "unavailable_reason": "seed unavailable"})
            continue
        if (
            time.monotonic() + 60 >= deadline
            or bench.size_tree(ROOT / "evidence") > 2 * 1024**3
        ):
            rows.append(
                {"config": cell, "unavailable_reason": "frozen global time/data cap"}
            )
            continue
        directory = output / name / f"cell-{cell['index']:03d}"
        host_before = {"load_average": os.getloadavg(), "timestamp": time.time()}
        emit(
            {"event": "load-start", "stage": stage, "arm": name, "cell": cell["index"]}
        )
        try:
            result = bench.run_cell(
                states[name]["stages"][stage]["server_binary"],
                seeds[name],
                cell,
                directory,
                {},
            )
        except Exception as error:
            result = {"config": cell, "unavailable_reason": str(error)}
        summary = {
            key: value
            for key, value in result.items()
            if key not in {"samples", "resource_samples", "seed"}
        }
        summary["host_before"] = host_before
        summary["artifact_gate_pass"] = all(
            states[name]["stages"][stage][key]
            for key in [
                "dependency_locks_unchanged",
                "own_tests_pass",
                "api_checks_pass",
            ]
        )
        save(directory / "summary.json", summary)
        compact_cell(directory)
        rows.append(summary)
        if (
            result.get("unavailable_reason")
            or result.get("stopped_transport_failures")
            or result.get("drain_budget_exceeded")
        ):
            del seeds[
                name
            ]  # Stop this arm's remaining cells; no unchanged-blocker retries.
    save(output / "summary.json", rows)
    return rows


def execute(manifest):
    save(
        ROOT / "evidence/execution.started.json",
        {"started_unix": time.time(), "model_call_limit": 9},
    )
    with tempfile.TemporaryDirectory(
        prefix="os-queueforge-", dir="/private/tmp"
    ) as temporary:
        states = {}
        try:
            for arm in manifest["arms"]:
                base = Path(temporary) / arm["id"]
                base.mkdir(mode=0o700)
                states[arm["id"]] = setup_arm(manifest, arm, base)
            for stage in [1, 2, 3]:
                order = manifest["development_order"][str(stage)]
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    futures = {
                        pool.submit(invoke, manifest, states[name], stage): name
                        for name in order
                    }
                    for future in concurrent.futures.as_completed(futures):
                        future.result()
                # Builds and correctness checks finish before any timed API load.
                for name in order:
                    qualify_stage(states[name], stage)
                if stage >= 2:
                    rows = measure(manifest, states, stage)
                    if stage == 2:
                        for name, state in states.items():
                            if state.get("access_blocked"):
                                continue
                            report = read(
                                ROOT / "evidence" / name / "stage2/acceptance.json"
                            )
                            feedback = {
                                "stage": 2,
                                "own_checks_pass": report.get("passed"),
                                "scenarios": [
                                    {k: s.get(k) for k in ["name", "status", "error"]}
                                    for s in report.get("scenarios", [])
                                ],
                                "own_test_result": read(
                                    ROOT / "evidence" / name / "stage2/own-tests.json"
                                ),
                                "build": read(
                                    ROOT / "evidence" / name / "stage2/build.json"
                                ),
                                "performance": [
                                    x for x in rows if x["config"]["arm"] == name
                                ],
                                "interpretation": "Your artifact only. Failed/unassessable correctness means diagnostic performance. No sibling answer or repair is supplied.",
                            }
                            save(state["workspace"] / "FEEDBACK.json", feedback)
                            save(
                                ROOT / "evidence" / name / "stage3-feedback.json",
                                feedback,
                            )
            save(
                ROOT / "evidence/execution.completed.json",
                {
                    "model_calls": len(
                        list((ROOT / "evidence").glob("*/stage*/call.started.json"))
                    ),
                    "completed_unix": time.time(),
                },
            )
        finally:
            for name, state in states.items():
                (state["codex"] / "auth.json").unlink(missing_ok=True)
                save(
                    ROOT / "evidence" / name / "cleanup.json",
                    {"auth_copy_removed": not (state["codex"] / "auth.json").exists()},
                )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preflight", "execute"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    frozen = verify(args.manifest, args.sha256)
    if args.mode == "preflight":
        emit({"freeze": "pass", "model_calls": 0, "planned_calls": 9})
    else:
        execute(frozen)


if __name__ == "__main__":
    main()
