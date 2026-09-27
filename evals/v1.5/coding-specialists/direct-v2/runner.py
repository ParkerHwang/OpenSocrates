"""Frozen direct-delivery comparison. No model wall-clock termination path."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
HELPER_PATH = ROOT / "evals/v1.5/expanded/harness_v4.py"
SPEC = importlib.util.spec_from_file_location("specialist_io_helpers", HELPER_PATH)
helpers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helpers)
STOP = threading.Event()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def inventory(directory):
    return {str(p.relative_to(directory)): sha(p) for p in sorted(directory.rglob('*'))
            if p.is_file() and not p.is_symlink() and '.git' not in p.parts and '__pycache__' not in p.parts}


def check_freeze(manifest):
    for name, digest in manifest["frozen_files"].items():
        assert sha(HERE / name) == digest, name
    for name, digest in manifest["helper_files"].items():
        assert sha(ROOT / name) == digest, name
    for key in ("launcher", "actual_executable"):
        assert sha(manifest["client"][key]) == manifest["client"][key + "_sha256"], key
    account = (read(helpers.AUTH).get("tokens") or {}).get("account_id")
    observed_account = hashlib.sha256(account.encode()).hexdigest() if account else None
    assert observed_account == manifest["account_id_sha256"], "account identity changed"
    assert manifest["limits"]["model_wall_clock_seconds"] is None


def sanitize(text, base):
    text = text.replace(str(base), "<CELL>").replace(str(ROOT), "<REPO>")
    text = re.sub(r"/Users/[^/\s]+/", "<USER>/", text)
    if re.search(r"(?<![A-Za-z0-9_])sk-(?:proj-)?[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{30,}\.", text):
        raise ValueError("credential_like_output")
    return text


def capture(raw, base):
    result, final = helpers.summarize(raw)
    public, tools, errors = [], [], []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            public.append(item.get("text", ""))
        if event.get("type") == "item.completed" and item.get("type") in {"command_execution", "file_change", "mcp_tool_call", "web_search"}:
            tools.append(item)
        if event.get("type") in {"error", "turn.failed"}:
            errors.append(event)
    result.update(public_messages=public, public_tool_results=tools, error_events=errors, final=final)
    return json.loads(sanitize(json.dumps(result, ensure_ascii=False), base))


def prepare(manifest, cell, storage, python):
    base = storage / cell["id"]
    base.mkdir(mode=0o700)
    workspace = base / "workspace"
    output = HERE / "results" / cell["id"]
    output.mkdir(parents=True)
    if cell.get("from_cell"):
        prior = HERE / "results" / cell["from_cell"]
        previous = read(prior / "call.json")
        if not previous["process_success"]:
            raise RuntimeError("continuation_requires_completed_prior_call")
        shutil.copytree(prior / "snapshot", workspace)
        for name, digest in read(prior / "snapshot.json")["files"].items():
            assert sha(workspace / name) == digest
    else:
        shutil.copytree(HERE / "tasks" / cell["task"] / "starter", workspace)
    shutil.copyfile(HERE / "tasks" / cell["task"] / "TASK.md", workspace / "TASK.md")
    if cell.get("followup"):
        shutil.copyfile(HERE / "tasks" / cell["task"] / "FOLLOWUP.md", workspace / "FOLLOWUP.md")
    support = manifest["arms"][cell["arm"]][cell["task"]]
    bodies = [(HERE / name).read_text() for name in support]
    (workspace / "GUIDANCE.md").write_text("\n\n".join(bodies))
    (workspace / "TOOLING.md").write_text(f"Use the existing Python executable: {python}\nStandard library only. No network or external services are needed.\n")
    codex, env = helpers.profile(base / "profile")
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PYTHONUTF8="1")
    env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
    (codex / "config.toml").write_text(manifest["profile_config"])
    for args in (["git", "init", "-q"], ["git", "add", "."],
                 ["git", "-c", "user.name=Evaluation", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Frozen synthetic source"]):
        subprocess.run(args, cwd=workspace, env=env, check=True, capture_output=True)
    protected = {name: sha(workspace / name) for name in manifest["protected_paths"][cell["task"]]}
    task = (workspace / ("FOLLOWUP.md" if cell.get("followup") else "TASK.md")).read_text()
    prompt = manifest["common_prompt"] + "\n\n" + ("Continue your own retained implementation. Original requirements remain in TASK.md.\n" if cell.get("followup") else "")
    prompt += "Task:\n" + task + "\n\nComplete directly delivered guidance:\n" + "\n\n".join(bodies)
    prompt += f"\n\nUse Python at {python}. Protected paths: {', '.join(protected)}."
    save(output / "inputs.json", {"source_files": inventory(workspace), "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                                  "support": support, "protected_paths": protected, "delivery": "prompt_delivered",
                                  "installed_plugin_treatment": False, "model": manifest["model"], "effort": manifest["effort"]})
    return base, workspace, output, codex, env, prompt, protected


def one(manifest, cell, storage, python):
    check_freeze(manifest)
    output = HERE / "results" / cell["id"]
    if (output / "call.json").exists():
        previous = read(output / "call.json")
        assert previous["manifest_sha256"] == sha(HERE / "manifest.json")
        return previous
    if STOP.is_set():
        save(output / "skipped.json", {"reason": "unchanged_tuple_access_blocker", "call_attempted": False, "usage": None})
        return None
    state = None
    try:
        state = prepare(manifest, cell, storage, python)
        base, workspace, output, codex, env, prompt, protected = state
        args = [manifest["client"]["launcher"], "--no-daemon", "--ask-for-approval", "never", "exec",
                "--sandbox", "workspace-write", "--skip-git-repo-check", "--ignore-rules", "--ephemeral", "--json", "-C", str(workspace)]
        for feature in manifest["disabled_features"]:
            args += ["--disable", feature]
        args += ["-c", "memories.use_memories=false", "-c", "memories.generate_memories=false",
                 "-c", 'shell_environment_policy.inherit="all"', "-c", "sandbox_workspace_write.network_access=false",
                 "-m", manifest["model"], "-c", f'model_reasoning_effort="{manifest["effort"]}"', "-"]
        started = {**cell, "started_unix": time.time(), "attempt": 1, "call_attempted": True,
                   "manifest_sha256": sha(HERE / "manifest.json"), "model": manifest["model"], "effort": manifest["effort"],
                   "client_sha256": sha(manifest["client"]["actual_executable"])}
        save(output / "call.started.json", started)
        print(json.dumps({"event": "start", "id": cell["id"]}), flush=True)
        proc = subprocess.Popen(args, cwd=workspace, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, start_new_session=True)
        begin, pending = time.monotonic(), prompt
        while True:
            try:
                raw, stderr = proc.communicate(pending, timeout=30)
                break
            except subprocess.TimeoutExpired as observation:
                pending = None
                partial = observation.output or b""
                if isinstance(partial, bytes):
                    partial = partial.decode("utf-8", "replace")
                info, _ = helpers.summarize(partial)
                progress = {"id": cell["id"], "wall_seconds": round(time.monotonic()-begin, 3),
                            "tools": info["tool_actions_started_or_completed"], "usage": info["usage"], "observation_only": True}
                temporary = output / ".progress.tmp"
                temporary.write_text(json.dumps(progress)+"\n")
                temporary.replace(output / "progress.json")
        result = capture(raw, base)
        result.update(started, exit_code=proc.returncode, wall_seconds=round(time.monotonic()-begin, 3),
                      process_success=proc.returncode == 0 and result["turn_completed"], model_wall_clock_limit=None,
                      stderr_sha256=hashlib.sha256(stderr.encode()).hexdigest(),
                      protected_inputs_unchanged=all((workspace / name).is_file() and sha(workspace / name) == digest for name,digest in protected.items()),
                      native_memory=helpers.native_counts(codex), account_side_isolation="unproven")
        save(output / "call.json", result)
        snapshot = output / "snapshot"
        snapshot.mkdir()
        for name in inventory(workspace):
            source = workspace / name
            if source.is_symlink():
                continue
            destination = snapshot / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        save(output / "snapshot.json", {"files": inventory(snapshot), "locked_before_independent_checks": True})
        error_text = stderr + json.dumps(result["error_events"])
        if not result["turn_completed"] and any(word in error_text.lower() for word in ["capacity", "usage limit", "rate_limit", "unauthorized", "not supported", "authentication"]):
            STOP.set()
        print(json.dumps({"event":"done", "id":cell["id"], "success":result["process_success"], "wall_seconds":result["wall_seconds"], "usage":result["usage"]}), flush=True)
        return result
    except Exception as error:
        if not (output / "harness-failure.json").exists():
            save(output / "harness-failure.json", {"type": type(error).__name__, "detail": str(error),
                 "call_attempted": (output / "call.started.json").exists(), "usage": None})
        print(json.dumps({"event":"harness-failure", "id":cell["id"], "error":str(error)}), flush=True)
        return None
    finally:
        codex = state[3] if state else storage / cell["id"] / "profile/home/.codex"
        (codex / "auth.json").unlink(missing_ok=True)
        if not (output / "cleanup.json").exists():
            save(output / "cleanup.json", {"auth_copy_removed": not (codex / "auth.json").exists()})


def qualify(manifest, python):
    for cell in manifest["cells"]:
        output = HERE / "results" / cell["id"]
        source = output / "snapshot"
        if not source.exists() or (output / "qualification.json").exists():
            continue
        for name, digest in read(output / "snapshot.json")["files"].items():
            assert sha(source / name) == digest
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE":"1", "PYTHONNOUSERSITE":"1"}
        record = {}
        for name in ("independent", "own_suite"):
            with tempfile.TemporaryDirectory(prefix="opensocrates-specialist-check-") as directory:
                checked = Path(directory) / "workspace"
                shutil.copytree(source, checked)
                command = [str(python), str(HERE / "checker.py"), cell["task"], str(checked)] if name == "independent" else [str(python), "-m", "unittest", "discover", "-s", "tests", "-v"]
                if name == "independent" and cell.get("followup"):
                    command += ["--followup"]
                started = time.monotonic()
                proc = subprocess.Popen(command, cwd=checked, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
                timed_out = False
                try:
                    stdout, stderr = proc.communicate(timeout=manifest["limits"]["program_check_seconds"])
                except subprocess.TimeoutExpired:
                    timed_out = True
                    os.killpg(proc.pid, signal.SIGKILL)
                    stdout, stderr = proc.communicate()
                record[name] = {"exit_code":proc.returncode, "timed_out":timed_out, "wall_seconds":round(time.monotonic()-started,3),
                                "stdout":sanitize(stdout, checked), "stderr":sanitize(stderr, checked)}
                if name == "independent" and not timed_out:
                    try:
                        record[name]["result"] = json.loads(stdout)
                    except ValueError:
                        record[name]["result"] = None
        assert inventory(source) == read(output / "snapshot.json")["files"]
        save(output / "qualification.json", record)
        print(json.dumps({"event":"qualified", "id":cell["id"], "passed":record["independent"].get("result",{}), "own_suite_exit":record["own_suite"]["exit_code"]}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("execute", "qualify"))
    parser.add_argument("--storage", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()
    manifest = read(HERE / "manifest.json")
    check_freeze(manifest)
    assert sha(args.python) == manifest["python"]["executable_sha256"]
    if args.action == "qualify":
        qualify(manifest, args.python)
        return
    args.storage.mkdir(mode=0o700, parents=True, exist_ok=True)
    for phase in sorted({cell["round"] for cell in manifest["cells"]}):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(one, manifest, cell, args.storage, args.python) for cell in manifest["cells"] if cell["round"] == phase]
            for future in futures:
                future.result()


if __name__ == "__main__":
    main()
