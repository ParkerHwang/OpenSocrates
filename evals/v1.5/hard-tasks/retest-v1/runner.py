"""Frozen 12-cell pre/post revision comparison; no delegated preparation or review."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TASKS = HERE.parent / "v1"
ACTUAL_CLIENT = Path(
    "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
)
sys.path.insert(0, str(ROOT / "evals/v1.5/practical"))
spec = importlib.util.spec_from_file_location(
    "hard_helpers", ROOT / "evals/v1.5/practical/runner.py"
)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
CLIENT = Path("/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex")
PYTHON = Path(
    "/Users/parkerhwang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
)
GO = Path("/usr/local/go/bin/go")
LOCK = threading.Lock()
BLOCKED = set()
GLOBAL_STOP = threading.Event()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def sanitize(text, base):
    value = (
        text.replace(str(base), "<CELL>")
        .replace(str(PYTHON), "<BUNDLED_PYTHON>")
        .replace(str(ROOT), "<REPO>")
    )
    value = re.sub(r"/(?:private/)?(?:tmp|var/folders)/[^\s`\"\x27)]+", "<TEMP_PATH>", value)
    if re.search(
        r"(?<![A-Za-z0-9_])sk-(?:proj-)?[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{30,}\.", value
    ):
        raise ValueError("credential_like_output")
    return value


def capture(raw, base):  # noqa: C901 - explicit frozen event accounting, no semantic repair.
    summary, final = helpers.summarize(raw)
    public = []
    commands = []
    native = []
    errors = []
    decoder = json.JSONDecoder()
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") in ("error", "turn.failed"):
            errors.append(sanitize(json.dumps(event), base))
        if event.get("type") != "item.completed":
            continue
        item = event.get("item") or {}
        if item.get("type") == "agent_message":
            public.append(sanitize(item.get("text", ""), base))
        if item.get("type") == "command_execution":
            command = item.get("command", "")
            commands.append(
                {
                    "command": sanitize(command, base),
                    "exit_code": item.get("exit_code"),
                    "status": item.get("status"),
                }
            )
            if any(name in command for name in ("native_tool.py", "launch.sh")):
                output = item.get("aggregated_output", "") or ""
                for match in re.finditer(r"(?m)^\s*\{", output):
                    try:
                        value, _ = decoder.raw_decode(output[match.start() :].lstrip())
                    except ValueError:
                        continue
                    if (
                        isinstance(value, dict)
                        and value.get("status") is not None
                        and (
                            str(value.get("schema", "")).startswith("opensocrates.")
                            or value.get("status")
                            in (
                                "selected",
                                "catalog",
                                "invalid_request",
                                "prepared",
                                "unavailable",
                                "no_intervention",
                                "acknowledged",
                                "reset",
                            )
                        )
                    ):
                        native.append(
                            {
                                k: value.get(k)
                                for k in (
                                    "schema",
                                    "request_id",
                                    "status",
                                    "application",
                                    "applied",
                                    "selected",
                                    "reason",
                                    "diagnostic",
                                )
                            }
                        )
    summary.update(
        public_messages=public,
        commands=commands,
        native_output_projections=native,
        error_events=errors,
        final=sanitize(final, base),
    )
    return json.loads(sanitize(json.dumps(summary, ensure_ascii=False), base))


def bounded(args, cwd, env, seconds):
    start = time.monotonic()
    p = None
    out = err = b""
    timeout = False
    error = None
    try:
        p = subprocess.Popen(
            args,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            out, err = p.communicate(timeout=seconds)
        except subprocess.TimeoutExpired:
            timeout = True
            os.killpg(p.pid, signal.SIGKILL)
            out, err = p.communicate(timeout=10)
    except OSError as exc:
        error = type(exc).__name__
    finally:
        if p:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    return {
        "exit_code": p.returncode if p else None,
        "timeout": timeout,
        "error": error,
        "wall_seconds": round(time.monotonic() - start, 3),
        "stdout": out.decode("utf-8", "replace"),
        "stderr": err.decode("utf-8", "replace"),
    }


def clone(source, target):
    p = subprocess.run(["cp", "-cR", str(source), str(target)], capture_output=True)
    if p.returncode:
        if target.exists():
            raise RuntimeError("partial_cache_clone")
        shutil.copytree(source, target)


def verify(digest, packages):
    assert sha(HERE / "manifest.json") == digest
    m = read(HERE / "manifest.json")
    assert len(m["cells"]) == 12 and m["limits"]["model_calls"] == 12
    assert {(c["model"], c["effort"]) for c in m["cells"]} == {
        ("gpt-6-sol", "medium"),
        ("gpt-6-luna", "medium"),
        ("gpt-6-luna", "max"),
    }
    for path, d in m["files"].items():
        assert sha(ROOT / path) == d, path
    for binary, key in (
        (CLIENT, "client"),
        (ACTUAL_CLIENT, "actual_client"),
        (GO, "go"),
        (PYTHON, "python"),
    ):
        assert sha(binary) == m["runtime"][key]["sha256"], key
    for arm in m["arms"].values():
        if arm.get("archive_name"):
            assert sha(packages / arm["archive_name"]) == arm["archive_sha256"]
    return m


def setup(m, cell, storage, packages, toolchain):
    base = storage / cell["id"]
    base.mkdir()
    workspace = base / "workspace"
    output = HERE / "results" / cell["id"]
    output.mkdir(parents=True, exist_ok=False)
    if cell["task"] == "coding":
        shutil.copytree(TASKS / "coding/starter", workspace)
    else:
        workspace.mkdir()
        shutil.copytree(TASKS / "office/inputs", workspace / "inputs")
    shutil.copyfile(TASKS / cell["task"] / "TASK.md", workspace / "TASK.md")
    (base / "data").mkdir(mode=0o700)
    (base / "cache").mkdir()
    (workspace / "output").mkdir(exist_ok=True)
    codex, env = helpers.profile(base / "profile")
    env.update(
        OPENSOCRATES_MEMORY_FIXTURE="1",
        OPENSOCRATES_DEVELOPMENT_MANIFEST="1",
        OPENSOCRATES_DATA_DIR=str(base / "data"),
        PYTHONNOUSERSITE="1",
        PYTHONUTF8="1",
    )
    (codex / "config.toml").write_text(
        'cli_auth_credentials_store="file"\nweb_search="disabled"\n[features]\nremote_plugin=false\napps=false\nhooks=false\nmulti_agent=false\nmemories=false\nexternal_agent_memory_import=false\n[memories]\nuse_memories=false\ngenerate_memories=false\n[apps._default]\nenabled=false\n'
    )
    if cell["task"] == "coding":
        clone(toolchain / "modcache", base / "cache/modcache")
        clone(toolchain / "gocache", base / "cache/gocache")
        env.update(
            GOMODCACHE=str(base / "cache/modcache"),
            GOCACHE=str(base / "cache/gocache"),
            GOTOOLCHAIN="local",
            GOPROXY="off",
            GOSUMDB="off",
            GOMAXPROCS="4",
        )
        for args in (
            ["git", "init", "-q"],
            ["git", "add", "."],
            [
                "git",
                "-c",
                "user.name=Evaluation",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Common synthetic starter",
            ],
        ):
            subprocess.run(args, cwd=workspace, env=env, check=True, capture_output=True)
    (workspace / "TOOLING.md").write_text(
        f"Bundled Python: {PYTHON}\nPython3.12.14 with openpyxl3.1.5 is available.\nGo executable: {GO}\nOnly the pinned existing Go dependencies are available, no downloads.\nAll external facts needed for this task are in TASK.md and inputs/starter. Use localhost for backend tests.\n",
        encoding="utf-8",
    )
    (workspace / "PROJECT_NOTES.md").write_text(
        m["accepted_intent"][cell["task"]] + "\n", encoding="utf-8"
    )
    arm = m["arms"][cell["arm"]]
    package = None
    seed = None
    if arm.get("archive_name"):
        package = helpers.install(
            {"client": {"path": str(CLIENT)}},
            {**arm, "archive_path": str(packages / arm["archive_name"])},
            base,
            env,
            output,
        )
    else:
        receipt, inventory = helpers.command([str(CLIENT), "plugin", "list", "--json"], env)
        assert receipt["exit_code"] == 0 and not inventory.get("installed"), (
            "vanilla_plugin_inventory"
        )
        save(output / "installation.json", {"installed": [], "receipt": receipt})
    if cell["arm"] in ("guide8", "guide9"):
        seed = helpers.seed_memory(
            package,
            workspace,
            env,
            {"accepted_records": [m["accepted_intent"][cell["task"]]]},
            output,
        )
        shutil.copyfile(HERE / "native_tool.py", workspace / "native_tool.py")
        config = {
            "launcher": str(package / "bin/launch.sh"),
            "project_id": seed["project_id"],
            "workspace_id": seed["workspace_id"],
            "task_id": cell["task_id"],
            "audit_log": str(base / "data/native.jsonl"),
        }
        save(workspace / "native_tool.json", config)
        (workspace / "MEMORY_USAGE.md").write_text(
            f"This disposable task is enrolled for optional relevant continuity/milestones. Stable task ID: {cell['task_id']}. IDs and launcher are in native_tool.json. The same accepted intent is in PROJECT_NOTES.md. Use memory only when relevant; no extra calls are required merely to satisfy the evaluator. Use native_tool.py memory|assistance|documentation|decision with unchanged JSON on stdin for auditable forwarding. Read installed guides/examples at {package / 'skills/opensocrates/references/assistance'}. Keep derived ideas proposed and actions agent_reported. No enrollment, accept, delete, disable, global changes, raw prompts/transcripts/source copies or hidden reasoning in memory.\n",
            encoding="utf-8",
        )
    condition = "Read and maintain PROJECT_NOTES.md as a competent bounded work note. Recheck current source instead of treating predecessor notes as current facts."
    if package:
        condition += f" Use the installed OpenSocrates controller appropriately: {package / 'skills/opensocrates/SKILL.md'}."
    else:
        condition += " This is vanilla Codex with no extra plugins or personal instructions; do not install any."
    if seed:
        condition += (
            " Optional enrolled memory and its exact scope are described in MEMORY_USAGE.md."
        )
    prompt = (
        m["common_prompt"]
        + "\n\n"
        + (workspace / "TASK.md").read_text()
        + "\n\n"
        + condition
        + "\nRead TOOLING.md for the common tools. Write office deliverables in output/. Stop any server you start before your final response. Independent performance measurement runs after all model/build work; do not run a performance sweep inside this call."
    )
    save(
        output / "prompt.json",
        {"text": sanitize(prompt, base), "sha256": hashlib.sha256(prompt.encode()).hexdigest()},
    )
    protected = {
        str(p.relative_to(workspace)): sha(p)
        for p in workspace.rglob("*")
        if p.is_file()
        and (
            p.name == "TASK.md"
            or "inputs" in p.relative_to(workspace).parts
            or "legacy" in p.relative_to(workspace).parts
        )
    }
    return {
        "cell": cell,
        "base": base,
        "workspace": workspace,
        "output": output,
        "codex": codex,
        "env": env,
        "package": package,
        "seed": seed,
        "prompt": prompt,
        "protected": protected,
    }


def snapshot(state):
    workspace = state["workspace"]
    output = state["output"]
    target = output / "snapshot"
    target.mkdir()
    inventory = []
    for p in sorted(workspace.rglob("*")):
        rel = p.relative_to(workspace)
        if any(x in (".git", "__pycache__") for x in rel.parts) or not p.is_file():
            continue
        if p.is_symlink():
            inventory.append(
                {"path": str(rel), "retained": False, "reason": "symlink_not_followed"}
            )
            continue
        size = p.stat().st_size
        item = {"path": str(rel), "bytes": size, "sha256": sha(p), "retained": False}
        if (
            not p.is_symlink()
            and p.suffix
            in (
                ".go",
                ".mod",
                ".sum",
                ".md",
                ".txt",
                ".py",
                ".json",
                ".csv",
                ".xlsx",
                ".toml",
                ".yaml",
                ".yml",
            )
            and size <= 8 * 1024 * 1024
            and p.name not in ("native_tool.json",)
        ):
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if p.suffix == ".xlsx":
                shutil.copyfile(p, dest)
            else:
                try:
                    dest.write_text(
                        sanitize(p.read_text(encoding="utf-8"), state["base"]), encoding="utf-8"
                    )
                except (UnicodeError, ValueError):
                    item["reason"] = "text_retention_unavailable"
                    inventory.append(item)
                    continue
            item.update(retained=True, export_sha256=sha(dest))
        inventory.append(item)
    save(output / "artifact-inventory.json", inventory)
    save(
        output / "protected-inputs.json",
        {
            "unchanged": all(
                (workspace / k).is_file() and sha(workspace / k) == v
                for k, v in state["protected"].items()
            ),
            "sha256": state["protected"],
        },
    )


def one(m, cell, storage, packages, toolchain):  # noqa: C901 - keep every attempt and cleanup branch explicit.
    with LOCK:
        blocked = GLOBAL_STOP.is_set() or cell["tuple"] in BLOCKED
    if blocked:
        save(
            HERE / "results" / cell["id"] / "skipped.json",
            {"reason": "unchanged tuple/account access blocker", "call_attempted": False},
        )
        return
    state = None
    try:
        state = setup(m, cell, storage, packages, toolchain)
        base = state["base"]
        out = state["output"]
        save(base / "environment.json", state["env"])
        assert sha(CLIENT) == m["runtime"]["client"]["sha256"]
        assert sha(ACTUAL_CLIENT) == m["runtime"]["actual_client"]["sha256"]
        started = {
            **cell,
            "attempt": 1,
            "started_unix": time.time(),
            "client_sha256": sha(CLIENT),
            "actual_client_sha256": sha(ACTUAL_CLIENT),
            "package_sha256": m["arms"][cell["arm"]].get("archive_sha256"),
        }
        save(out / "call.started.json", started)
        args = [
            str(CLIENT),
            "--no-daemon",
            "--ask-for-approval",
            "never",
            "exec",
            "--sandbox",
            "workspace-write",
            "--skip-git-repo-check",
            "--ignore-rules",
            "-C",
            str(state["workspace"]),
            "--add-dir",
            str(base / "data"),
            "--add-dir",
            str(base / "cache"),
            "--ephemeral",
            "--json",
        ]
        for flag in (
            "multi_agent",
            "memories",
            "external_agent_memory_import",
            "hooks",
            "remote_plugin",
            "apps",
        ):
            args += ["--disable", flag]
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
            cell["model"],
            "-c",
            f'model_reasoning_effort="{cell["effort"]}"',
            "-",
        ]
        begin = time.monotonic()
        p = None
        raw = err = ""
        timeout = False
        error = None
        print(json.dumps({"event": "start", **cell}), flush=True)
        try:
            p = subprocess.Popen(
                args,
                cwd=state["workspace"],
                env=state["env"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            deadline = begin + m["limits"]["seconds_per_call"]
            pending_input = state["prompt"]
            while True:
                try:
                    raw, err = p.communicate(
                        pending_input, timeout=max(0.01, min(60, deadline - time.monotonic()))
                    )
                    break
                except subprocess.TimeoutExpired as event:
                    pending_input = None
                    partial = event.output or b""
                    if isinstance(partial, bytes):
                        partial = partial.decode("utf-8", "replace")
                    observed, _ = helpers.summarize(partial)
                    progress = {
                        key: observed.get(key)
                        for key in (
                            "event_count",
                            "tool_actions_started_or_completed",
                            "failed_tool_actions",
                            "incomplete_tool_actions",
                            "usage",
                            "turn_completed",
                        )
                    }
                    progress.update(
                        id=cell["id"],
                        provisional=True,
                        wall_seconds=round(time.monotonic() - begin, 3),
                    )
                    temporary = out / ".progress.tmp"
                    temporary.write_text(
                        json.dumps(progress, sort_keys=True) + "\n", encoding="utf-8"
                    )
                    temporary.replace(out / "progress.json")
                    if time.monotonic() >= deadline:
                        timeout = True
                        os.killpg(p.pid, signal.SIGKILL)
                        raw, err = p.communicate(timeout=10)
                        break
        except OSError as exc:
            error = type(exc).__name__
        finally:
            if p:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        try:
            result = capture(raw, base)
        except ValueError:
            minimal, _ = helpers.summarize(raw)
            result = {
                "usage": minimal.get("usage"),
                "turn_completed": minimal.get("turn_completed", False),
                "tool_actions": minimal.get("tool_actions", []),
                "public_messages": [],
                "commands": [],
                "error_events": [],
                "final": "",
                "retention_failure": "credential_like_public_text",
            }
        result.update(started)
        result.update(
            exit_code=p.returncode if p else None,
            timed_out=timeout,
            invocation_error=error,
            wall_seconds=round(time.monotonic() - begin, 3),
            stderr_sha256=hashlib.sha256(err.encode()).hexdigest(),
            billed_cost=None,
            backend_model_echo=None,
            stderr_mcp_startup_observed="mcp startup" in err.lower(),
        )
        result["process_success"] = (
            p is not None and p.returncode == 0 and result["turn_completed"] and not timeout
        )
        save(out / "call.json", result)
        error_text = (" ".join(result.get("error_events", [])) + " " + err).lower()
        if not result["turn_completed"] and not timeout:
            with LOCK:
                BLOCKED.add(cell["tuple"])
                if any(
                    word in error_text
                    for word in (
                        "usage limit",
                        "usage_limit",
                        "quota",
                        "authentication",
                        "unauthorized",
                    )
                ):
                    GLOBAL_STOP.set()
        audit = base / "data/native.jsonl"
        save(
            out / "native-operations.json",
            [json.loads(x) for x in audit.read_text().splitlines()] if audit.exists() else [],
        )
        if state["seed"]:
            _, response = helpers.memory_call(
                state["package"],
                state["workspace"],
                state["env"],
                "inspect",
                {},
                state["seed"]["project_id"],
                state["seed"]["workspace_id"],
            )
            save(out / "memory-after.json", response)
        save(out / "native-memory-state.json", helpers.native_counts(state["codex"]))
        snapshot(state)
        print(
            json.dumps(
                {
                    "event": "finish",
                    "id": cell["id"],
                    "process_success": result["process_success"],
                    "seconds": result["wall_seconds"],
                    "tool_actions": len(result.get("tool_actions", [])),
                }
            ),
            flush=True,
        )
    except Exception as error:
        out = HERE / "results" / cell["id"]
        out.mkdir(parents=True, exist_ok=True)
        save(
            out / "harness-failure.json",
            {
                "type": type(error).__name__,
                "message": sanitize(str(error), storage),
                "call_attempted": (out / "call.started.json").exists(),
            },
        )
        print(
            json.dumps(
                {"event": "harness-failure", "id": cell["id"], "type": type(error).__name__}
            ),
            flush=True,
        )
    finally:
        profile = state["codex"] if state else storage / cell["id"] / "profile/home/.codex"
        (profile / "auth.json").unlink(missing_ok=True)
        out = HERE / "results" / cell["id"]
        out.mkdir(parents=True, exist_ok=True)
        if not (out / "cleanup.json").exists():
            save(out / "cleanup.json", {"auth_copy_removed": not (profile / "auth.json").exists()})


def execute(m, storage, packages, toolchain):
    storage.mkdir(parents=True, exist_ok=False)
    save(
        HERE / "execution-started.json",
        {
            "manifest_sha256": sha(HERE / "manifest.json"),
            "started_unix": time.time(),
            "maximum_model_calls": 12,
        },
    )
    for round_id in range(6):
        cells = [c for c in m["cells"] if c["round"] == round_id]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(one, m, c, storage, packages, toolchain) for c in cells]
            for future in futures:
                future.result()


def qualify(m, storage):
    for cell in m["cells"]:
        out = HERE / "results" / cell["id"]
        workspace = storage / cell["id"] / "workspace"
        if not (out / "call.json").exists():
            continue
        env = read(storage / cell["id"] / "environment.json")
        if cell["task"] == "coding":
            binary = storage / cell["id"] / "server"
            for name, args in (
                ("own-tests", [str(GO), "test", "-race", "./..."]),
                ("build", [str(GO), "build", "-o", str(binary), "./cmd/server"]),
            ):
                result = bounded(args, workspace, env, 240)
                save(
                    out / (name + ".json"),
                    json.loads(sanitize(json.dumps(result), storage / cell["id"])),
                )
            if binary.exists() and read(out / "build.json")["exit_code"] == 0:
                raw_report = storage / cell["id"] / "acceptance.json"
                command = [
                    str(PYTHON),
                    str(TASKS / "coding/acceptance.py"),
                    str(binary),
                    "--output",
                    str(raw_report),
                    "--source",
                    str(workspace),
                ]
                result = bounded(command, workspace, env, 360)
                save(
                    out / "acceptance-command.json",
                    json.loads(sanitize(json.dumps(result), storage / cell["id"])),
                )
                if raw_report.exists():
                    save(
                        out / "acceptance.json",
                        json.loads(sanitize(raw_report.read_text(), storage / cell["id"])),
                    )
        else:
            command = [
                str(PYTHON),
                str(TASKS / "office/check.py"),
                str(workspace / "output"),
                "--report",
                str(out / "office-checks.json"),
            ]
            result = bounded(command, workspace, env, 120)
            save(
                out / "office-check-command.json",
                json.loads(sanitize(json.dumps(result), storage / cell["id"])),
            )
        print(json.dumps({"event": "qualified", "id": cell["id"]}), flush=True)


def measure(m, storage):
    for cell in m["cells"]:
        if cell["task"] != "coding":
            continue
        out = HERE / "results" / cell["id"]
        binary = storage / cell["id"] / "server"
        if not binary.is_file() or not (out / "acceptance.json").exists():
            continue
        raw = storage / cell["id"] / "performance.json"
        env = read(storage / cell["id"] / "environment.json")
        result = bounded(
            [
                str(PYTHON),
                str(TASKS / "coding/measure.py"),
                str(binary),
                "--output",
                str(raw),
                "--acceptance",
                str(out / "acceptance.json"),
                "--source",
                str(storage / cell["id"] / "workspace"),
            ],
            storage / cell["id"],
            env,
            300,
        )
        save(
            out / "performance-command.json",
            json.loads(sanitize(json.dumps(result), storage / cell["id"])),
        )
        if raw.exists():
            v = read(raw)
            own = read(out / "own-tests.json")
            v["own_tests_passed"] = own["exit_code"] == 0 and not own["timeout"]
            if not v["own_tests_passed"]:
                v["interpretation"] = "diagnostic_only"
            for item in v["cells"]:
                samples = item.pop("raw_attempts", [])
                item["retained_samples"] = len(samples)
            v["raw_evidence_sha256"] = sha(raw)
            save(
                out / "performance.json", json.loads(sanitize(json.dumps(v), storage / cell["id"]))
            )
        print(json.dumps({"event": "measured", "id": cell["id"]}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("preflight", "execute", "qualify", "measure"))
    p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--storage", type=Path, required=True)
    p.add_argument("--packages", type=Path, required=True)
    p.add_argument("--toolchain", type=Path, required=True)
    args = p.parse_args()
    m = verify(args.manifest_sha256, args.packages)
    if args.mode == "execute":
        execute(m, args.storage, args.packages, args.toolchain)
    elif args.mode == "qualify":
        qualify(m, args.storage)
    elif args.mode == "measure":
        measure(m, args.storage)
    else:
        print("PASS: frozen inputs, tuples, client and packages; zero model calls")
