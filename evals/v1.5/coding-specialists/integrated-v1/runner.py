"""Disposable installed-package route observations, separate from content effect."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "evals/v1.5/practical"))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


direct = module("specialist_direct_io", HERE.parent / "direct-v2/runner.py")
practical = module("specialist_package_install", ROOT / "evals/v1.5/practical/runner.py")
save, sha, read = direct.save, direct.sha, direct.read
STOP = threading.Event()


def verify(manifest, archive, python):
    for relative, expected in manifest["frozen_files"].items():
        assert sha(HERE / relative) == expected, relative
    for relative, expected in manifest["helper_files"].items():
        assert sha(ROOT / relative) == expected, relative
    assert sha(archive) == manifest["package"]["archive_sha256"]
    assert sha(python) == manifest["python"]["executable_sha256"]
    for key in ("launcher", "actual_executable"):
        assert sha(manifest["client"][key]) == manifest["client"][key+"_sha256"]
    account = (read(direct.helpers.AUTH).get("tokens") or {}).get("account_id")
    assert (hashlib.sha256(account.encode()).hexdigest() if account else None) == manifest["account_id_sha256"]
    assert manifest["model_wall_clock_seconds"] is None


def one(manifest, cell, storage, archive, python):
    verify(manifest, archive, python)
    output = HERE / "results" / cell["id"]
    if (output / "call.json").exists():
        previous = read(output / "call.json")
        assert previous["manifest_sha256"] == sha(HERE / "manifest.json")
        return previous
    if STOP.is_set():
        save(output / "skipped.json", {"call_attempted": False, "usage": None, "reason": "unchanged_tuple_blocker"})
        return
    base = storage / cell["id"]
    codex = base / "profile/home/.codex"
    try:
        base.mkdir(mode=0o700)
        output.mkdir(parents=True)
        workspace = base / "workspace"
        starter = HERE / "cases" / cell["id"] / "starter"
        if starter.exists():
            shutil.copytree(starter, workspace)
        else:
            workspace.mkdir()
        shutil.copyfile(HERE / "cases" / cell["id"] / "TASK.md", workspace / "TASK.md")
        (workspace / "TOOLING.md").write_text(f"Python executable: {python}\nStandard library only. No remote services or network tools.\n")
        codex, env = direct.helpers.profile(base / "profile")
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PYTHONUTF8="1",
                   OPENSOCRATES_DEVELOPMENT_MANIFEST="1", OPENSOCRATES_DATA_DIR=str(base / "product-data"))
        env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
        (codex / "config.toml").write_text(manifest["profile_config"])
        package = practical.install({"client": {"path": manifest["client"]["launcher"]}},
                                    {**manifest["package"], "archive_path": str(archive)}, base, env, output)
        protected = {str(p.relative_to(workspace)): sha(p) for p in (workspace / "tests").glob('test_existing.py')}
        controller = package / "skills/opensocrates/SKILL.md"
        prompt = manifest["common_prompt"].format(controller=controller, python=python) + "\n\n" + (workspace / "TASK.md").read_text()
        save(output / "inputs.json", {"source_files": direct.inventory(workspace), "protected": protected,
                                      "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                                      "package_sha256": sha(archive), "delivery": "installed_package_explicit_controller_cue_hooks_off"})
        started = {**cell, "call_attempted": True, "attempt": 1, "started_unix": time.time(),
                   "manifest_sha256": sha(HERE / "manifest.json"), "model": manifest["model"], "effort": manifest["effort"]}
        save(output / "call.started.json", started)
        args = [manifest["client"]["launcher"], "--no-daemon", "--ask-for-approval", "never", "exec",
                "--sandbox", "workspace-write", "--skip-git-repo-check", "--ignore-rules", "--ephemeral", "--json", "-C", str(workspace)]
        for feature in manifest["disabled_features"]:
            args += ["--disable", feature]
        args += ["-c", 'shell_environment_policy.inherit="all"', "-c", "sandbox_workspace_write.network_access=false",
                 "-m", manifest["model"], "-c", f'model_reasoning_effort="{manifest["effort"]}"', "-"]
        print(json.dumps({"event": "start", "id": cell["id"]}), flush=True)
        proc = subprocess.Popen(args, cwd=workspace, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, start_new_session=True)
        begin, pending = time.monotonic(), prompt
        while True:
            try:
                raw, stderr = proc.communicate(pending, timeout=30)
                break
            except subprocess.TimeoutExpired as observed:
                pending = None
                partial = observed.output or b""
                if isinstance(partial, bytes):
                    partial = partial.decode("utf-8", "replace")
                info, _ = direct.helpers.summarize(partial)
                progress = {"id": cell["id"], "wall_seconds": round(time.monotonic()-begin,3),
                            "tools": info["tool_actions_started_or_completed"], "observation_only": True}
                temporary = output / ".progress.tmp"
                temporary.write_text(json.dumps(progress)+"\n")
                temporary.replace(output / "progress.json")
        result = direct.capture(raw, base)
        result.update(started, exit_code=proc.returncode, wall_seconds=round(time.monotonic()-begin,3),
                      process_success=proc.returncode == 0 and result["turn_completed"],
                      protected_inputs_unchanged=all((workspace/p).is_file() and sha(workspace/p)==h for p,h in protected.items()),
                      package_members_unchanged=all(sha(package/p)==h for p,h in manifest["package"]["members"].items()),
                      model_wall_clock_limit=None, native_memory=direct.helpers.native_counts(codex),
                      account_side_isolation="unproven", stderr_sha256=hashlib.sha256(stderr.encode()).hexdigest())
        save(output / "call.json", result)
        snapshot = output / "snapshot"
        snapshot.mkdir()
        for name in direct.inventory(workspace):
            destination = snapshot / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(workspace / name, destination)
        save(output / "snapshot.json", {"files":direct.inventory(snapshot), "locked_before_independent_checks":True})
        combined = stderr + json.dumps(result["error_events"])
        if not result["turn_completed"] and any(x in combined.lower() for x in ["capacity","usage limit","rate_limit","not supported","authentication","unauthorized"]):
            STOP.set()
        print(json.dumps({"event":"done","id":cell["id"],"success":result["process_success"],"wall_seconds":result["wall_seconds"],"usage":result["usage"]}),flush=True)
    except Exception as error:
        save(output / "harness-failure.json", {"type":type(error).__name__,"detail":str(error),"call_attempted":(output/'call.started.json').exists(),"usage":None})
        print(json.dumps({"event":"failure","id":cell["id"],"error":str(error)}),flush=True)
    finally:
        (codex / "auth.json").unlink(missing_ok=True)
        save(output / "cleanup.json", {"auth_copy_removed":not (codex/'auth.json').exists()})


def qualify(manifest, python):
    for cell in manifest["cells"]:
        output = HERE / "results" / cell["id"]
        snapshot = output / "snapshot"
        if not snapshot.exists() or (output/'qualification.json').exists():
            continue
        assert direct.inventory(snapshot) == read(output/'snapshot.json')["files"]
        record = {}
        for name in ["independent", "own_suite"] if (snapshot/'tests').exists() else ["independent"]:
            with tempfile.TemporaryDirectory(prefix="opensocrates-specialist-integrated-check-") as directory:
                work = Path(directory)/"workspace"
                shutil.copytree(snapshot,work)
                args = [str(python),str(HERE/'checker.py'),cell['id'],str(work)] if name=='independent' else [str(python),'-m','unittest','discover','-s','tests','-v']
                begin=time.monotonic()
                try:
                    p=subprocess.run(args,cwd=work,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'},capture_output=True,text=True,timeout=90)
                    record[name]={'exit_code':p.returncode,'stdout':direct.sanitize(p.stdout,work),'stderr':direct.sanitize(p.stderr,work),'wall_seconds':round(time.monotonic()-begin,3),'timed_out':False}
                    if name=='independent':
                        record[name]['result']=json.loads(p.stdout)
                except subprocess.TimeoutExpired:
                    record[name]={'exit_code':None,'stdout':None,'stderr':None,'timed_out':True,'wall_seconds':round(time.monotonic()-begin,3)}
        assert direct.inventory(snapshot) == read(output/'snapshot.json')["files"]
        save(output/'qualification.json',record)
        print(json.dumps({'event':'qualified','id':cell['id'],'result':record['independent'].get('result')}),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['execute','qualify'])
    parser.add_argument('--storage',type=Path,required=True)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--python',type=Path,required=True)
    args=parser.parse_args();manifest=read(HERE/'manifest.json')
    verify(manifest,args.archive,args.python)
    if args.action=='qualify':
        qualify(manifest,args.python)
    else:
        args.storage.mkdir(mode=0o700,parents=True,exist_ok=True)
        for round_id in sorted({c['round'] for c in manifest['cells']}):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(one,manifest,cell,args.storage,args.archive,args.python) for cell in manifest['cells'] if cell['round']==round_id]
                for future in futures:future.result()
