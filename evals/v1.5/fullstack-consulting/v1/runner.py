"""Fresh subject processes with timestamped passive observation; no deadlines.

This runner never sends coaching, follows up, changes model or kills an active
model because of time, tokens, tool count, output length or observed quality.
"""

from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "evals/v1.5/practical"))
SPEC = importlib.util.spec_from_file_location(
    "matrix_package_installer", ROOT / "evals/v1.5/practical/runner.py"
)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
AUTH = Path.home() / ".codex/auth.json"
LOCK = threading.Lock()
BLOCKED = {}
PUBLIC_TYPES = {
    "agent_message",
    "command_execution",
    "file_change",
    "mcp_tool_call",
    "web_search",
    "todo_list",
}
USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)
EXCLUDED = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".npm",
    ".cache",
    "target",
    "vendor",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write("\n")


def inventory(root):
    found = {}
    for parent, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(
            d for d in dirs if d not in EXCLUDED and not (Path(parent) / d).is_symlink()
        )
        for name in sorted(names):
            p = Path(parent) / name
            if p.is_file() and not p.is_symlink() and not name.endswith((".pyc", ".DS_Store")):
                found[str(p.relative_to(root))] = dict(
                    sha256=sha(p), bytes=p.stat().st_size, executable=bool(p.stat().st_mode & 0o111)
                )
    return found


def sanitize(text, base, manifest):
    text = text.replace(str(base), "<CELL>").replace(str(ROOT), "<REPO>")
    text = text.replace(manifest["tools"]["runtime_root"], "<SHARED_RUNTIME>").replace(
        manifest["tools"]["browser_root"], "<BROWSER_RUNTIME>"
    )
    text = re.sub(r"/Users/[^/\s]+/", "<USER>/", text)
    # No real credentials are needed in public evidence. Demo app tokens are not
    # account credentials, but JWT-shaped values are still redacted consistently.
    text = re.sub(r"(?<![A-Za-z0-9_])sk-(?:proj-)?[A-Za-z0-9_-]{20,}", "<REDACTED_TOKEN>", text)
    text = re.sub(r"eyJ[A-Za-z0-9_-]{25,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "<REDACTED_JWT>", text)
    return text


def clean(value, base, manifest):
    return json.loads(sanitize(json.dumps(value, ensure_ascii=False), base, manifest))


def verify(manifest):
    for file, digest in manifest["frozen_files"].items():
        assert sha(HERE / file) == digest, file
    for file, digest in manifest["helper_files"].items():
        assert sha(ROOT / file) == digest, file
    for key in ("launcher", "actual_executable"):
        assert sha(manifest["client"][key]) == manifest["client"][key + "_sha256"], key
    for arm in manifest["arms"].values():
        if arm.get("archive_path"):
            assert sha(arm["archive_path"]) == arm["archive_sha256"]
    account = (read(AUTH).get("tokens") or {}).get("account_id")
    assert (hashlib.sha256(account.encode()).hexdigest() if account else None) == manifest[
        "account_id_sha256"
    ]
    assert all(v is None for v in manifest["subject_budgets"].values())


def make_profile(base, manifest):
    home = base / "profile/home"
    temporary = base / "profile/tmp"
    codex = home / ".codex"
    codex.mkdir(parents=True, mode=0o700)
    temporary.mkdir(parents=True, mode=0o700)
    auth = codex / "auth.json"
    shutil.copyfile(AUTH, auth)
    auth.chmod(0o600)
    config = (
        (HERE / "profile.toml")
        .read_text()
        .format(home=home, temporary=temporary, **manifest["tools"])
    )
    (codex / "config.toml").write_text(config)
    tools = manifest["tools"]
    path = os.pathsep.join(
        [
            str(Path(tools["python"]).parent),
            str(Path(tools["node"]).parent),
            "/usr/local/go/bin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
        ]
    )
    env = dict(
        HOME=str(home),
        CODEX_HOME=str(codex),
        TMPDIR=str(temporary),
        PATH=path,
        LANG="en_US.UTF-8",
        LC_ALL="en_US.UTF-8",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        PYTHONUTF8="1",
        NODE_PATH=tools["node_modules"],
        PLAYWRIGHT_BROWSERS_PATH=tools["browser_root"],
        EVAL_CHROMIUM=tools["browser_executable"],
        npm_config_cache=str(home / ".npm"),
        PIP_CACHE_DIR=str(home / ".cache/pip"),
        GOPATH=str(home / "go"),
        GOCACHE=str(home / ".cache/go-build"),
        OPENSOCRATES_DEVELOPMENT_MANIFEST="1",
        OPENSOCRATES_DATA_DIR=str(base / "profile/product-data"),
    )
    return codex, env, config


def command(args, env, cwd=None):
    p = subprocess.run(args, env=env, cwd=cwd, capture_output=True, text=True)
    return p


def browser_tool(base, manifest, env, workspace, output):
    runtime = manifest["tools"]["runtime_root"]
    browser = manifest["tools"]["browser_root"]
    policy = f'''(version 1)
(allow default)
(deny file-read-data (require-all (require-any (subpath "/Users") (subpath "/private/tmp") (subpath "/private/var/folders")) (require-not (require-any (subpath "{base}") (subpath "{runtime}") (subpath "{browser}")))))
(deny file-read-data file-write* (subpath "{base}/profile/home/.codex"))
(deny file-write* (require-not (subpath "{base}")))
'''
    (base / "browser-policy.sb").write_text(policy)
    shutil.copyfile(HERE / "browser_server.cjs", base / "browser-server.cjs")
    sibling = base.parent / "browser-sibling-canary.txt"
    with LOCK:
        if not sibling.exists():
            sibling.write_text("Synthetic sibling browser canary")
    probes = {
        "global_memory": str(Path.home() / ".codex/memories/MEMORY.md"),
        "development_repository": str(ROOT / "README.md"),
        "sibling": str(sibling),
        "auth_copy": env["CODEX_HOME"] + "/auth.json",
    }
    proc = subprocess.Popen(
        [
            "/usr/bin/sandbox-exec",
            "-f",
            str(base / "browser-policy.sb"),
            manifest["tools"]["node"],
            str(base / "browser-server.cjs"),
        ],
        cwd=workspace,
        env={**env, "EVAL_BROWSER_READ_PROBES": json.dumps(probes)},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("Browser tool startup failed: " + proc.stderr.read())
    ready = json.loads(line)
    assert not any(ready["read_checks"].values())
    env["EVAL_BROWSER_WS"] = ready["endpoint"]
    env["EVAL_BROWSER_PID"] = str(proc.pid)
    save(
        output / "browser-isolation.json",
        {
            "read_checks": ready["read_checks"],
            "policy_sha256": sha(base / "browser-policy.sb"),
            "browser_executable_sha256": sha(manifest["tools"]["browser_executable"]),
            "protocol": "Playwright WebSocket",
            "profile": "fresh per cell; no reused context",
            "model_calls": 0,
        },
    )
    return proc


def close_browser(proc, output, base, manifest):
    if proc is None:
        return
    proc.stdin.close()
    proc.wait()
    save(
        output / "browser-tool-exit.json",
        {
            "exit_code": proc.returncode,
            "stderr": clean(proc.stderr.read(), base, manifest),
            "closed_after_subject": True,
        },
    )


def preflight(manifest, base, workspace, codex, env, output):
    probe = base / "outside-canary.txt"
    probe.write_text("Synthetic inaccessible sibling fixture.\n")
    python = manifest["tools"]["python"]
    launcher = manifest["client"]["launcher"]
    script = """import os,json,pathlib,urllib.request
paths=json.loads(os.environ['EVAL_READ_PROBES'])
out={}
for label,path in paths.items():
 try:
  with open(path,'rb') as f:f.read(1)
  out[label]=True
 except (OSError,PermissionError):out[label]=False
pathlib.Path('sandbox-canary.txt').write_text('owned write succeeds')
out['workspace_write']=True
print(json.dumps(out))
"""
    probes = {
        "global_memory": str(Path.home() / ".codex/memories/MEMORY.md"),
        "development_repository": str(ROOT / "README.md"),
        "sibling": str(probe),
        "auth_copy": str(codex / "auth.json"),
    }
    p = command(
        [launcher, "sandbox", "-P", "evaluation", "-C", str(workspace), python, "-c", script],
        {**env, "EVAL_READ_PROBES": json.dumps(probes)},
    )
    observed = json.loads(p.stdout) if p.returncode == 0 else None
    save(
        output / "sandbox-preflight.json",
        dict(exit_code=p.returncode, observed=observed, stderr=clean(p.stderr, base, manifest)),
    )
    assert observed == dict.fromkeys(probes, False) | {"workspace_write": True}, (
        "read isolation probe failed"
    )
    (workspace / "sandbox-canary.txt").unlink()
    p = command(
        [
            launcher,
            "--no-daemon",
            "-C",
            str(workspace),
            "-m",
            "gpt-6-luna",
            "debug",
            "prompt-input",
            "Synthetic preflight only; no model call.",
        ],
        env,
    )
    markers = [
        "MEMORY_SUMMARY BEGINS",
        "rollout_summaries/",
        "memories/MEMORY.md",
        str(ROOT),
        "opensocrates_bilingual_reviewer",
    ]
    receipt = {
        "exit_code": p.returncode,
        "context_sha256": hashlib.sha256(p.stdout.encode()).hexdigest(),
        "context_bytes": len(p.stdout),
        "forbidden_marker_matches": [x for x in markers if x in p.stdout],
        "model_call": False,
        "opensocrates_discovery_present": "opensocrates:opensocrates" in p.stdout
        or "skills/opensocrates/SKILL.md" in p.stdout,
    }
    save(output / "context-preflight.json", clean(receipt, base, manifest))
    assert p.returncode == 0 and not receipt["forbidden_marker_matches"], (
        "context isolation probe failed"
    )
    flags = command([launcher, "features", "list"], env)
    selected = {
        line.split()[0]: line.split()[-1]
        for line in flags.stdout.splitlines()
        if line.split()
        and line.split()[0]
        in (
            "fast_mode",
            "memories",
            "external_agent_memory_import",
            "apps",
            "remote_plugin",
            "multi_agent",
            "multi_agent_v2",
            "hooks",
        )
    }
    save(
        output / "feature-preflight.json",
        dict(exit_code=flags.returncode, flags=selected, requested_service_tier="default"),
    )
    assert flags.returncode == 0 and selected and all(v == "false" for v in selected.values()), (
        "feature isolation failed"
    )
    save(output / "native-memory-before.json", installer.native_counts(codex))


def resource_sample(pid):
    p = subprocess.run(
        ["/bin/ps", "-axo", "pid=,ppid=,pcpu=,rss=,comm="], capture_output=True, text=True
    )
    rows = []
    for line in p.stdout.splitlines():
        fields = line.split(None, 4)
        if len(fields) == 5:
            try:
                rows.append(
                    (
                        int(fields[0]),
                        int(fields[1]),
                        float(fields[2]),
                        int(fields[3]),
                        Path(fields[4]).name,
                    )
                )
            except ValueError:
                pass
    descendants = {pid}
    while True:
        expanded = descendants | {r[0] for r in rows if r[1] in descendants}
        if expanded == descendants:
            break
        descendants = expanded
    chosen = [r for r in rows if r[0] in descendants]
    return dict(
        process_count=len(chosen),
        rss_kib=sum(r[3] for r in chosen),
        cpu_percent=sum(r[2] for r in chosen),
        process_names=dict(Counter(r[4] for r in chosen)),
        host_load=list(os.getloadavg()),
    )


def serve_sources(output):
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            with LOCK:
                with (output / "source-requests.jsonl").open("a") as f:
                    f.write(json.dumps({"utc": now(), "method": "GET", "path": self.path}) + "\n")
            super().do_GET()

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(HERE / "source-room"))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/"


def observe(args, prompt, env, workspace, base, output, manifest, started):
    events = []
    counts = Counter()
    stderr_parts = []
    event_lock = threading.Lock()
    proc = subprocess.Popen(
        args,
        cwd=workspace,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    begin = time.monotonic()
    save(
        output / "process.json",
        {
            "pid": proc.pid,
            "started_utc": now(),
            "command": clean(args, base, manifest),
            "model_deadline": None,
        },
    )

    def stdout_reader():
        with (output / "observation.jsonl").open("x", encoding="utf-8") as stream:
            for line in proc.stdout:
                timestamp = now()
                elapsed = round(time.monotonic() - begin, 6)
                try:
                    event = json.loads(line)
                except ValueError:
                    counts["malformed_json_lines"] += 1
                    continue
                kind = event.get("type", "unknown")
                counts[kind] += 1
                item = event.get("item") or {}
                retained = None
                if (
                    kind.startswith("item.")
                    and item.get("type") in PUBLIC_TYPES
                    and kind in ("item.started", "item.completed")
                ):
                    retained = event
                elif kind in (
                    "turn.started",
                    "turn.completed",
                    "turn.failed",
                    "error",
                    "thread.started",
                ):
                    retained = event
                if retained is not None:
                    retained = clean(retained, base, manifest)
                    with event_lock:
                        events.append(retained)
                    stream.write(
                        json.dumps(
                            {"utc": timestamp, "elapsed_seconds": elapsed, "event": retained},
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    stream.flush()
                # Private reasoning content and raw response streams are discarded.

    def stderr_reader():
        for line in proc.stderr:
            stderr_parts.append(line)

    ended = {}
    finished = threading.Event()

    def waiter():
        proc.wait()
        ended.update(wall=time.monotonic() - begin, utc=now())
        finished.set()

    out_thread = threading.Thread(target=stdout_reader)
    err_thread = threading.Thread(target=stderr_reader)
    out_thread.start()
    err_thread.start()
    proc.stdin.write(prompt)
    proc.stdin.close()
    wait_thread = threading.Thread(target=waiter)
    wait_thread.start()
    with (output / "resources.jsonl").open("x") as samples:
        while proc.poll() is None:
            sample = {
                "utc": now(),
                "elapsed_seconds": round(time.monotonic() - begin, 3),
                **resource_sample(proc.pid),
            }
            if env.get("EVAL_BROWSER_PID"):
                sample["browser_tool"] = resource_sample(int(env["EVAL_BROWSER_PID"]))
            samples.write(json.dumps(sample) + "\n")
            samples.flush()
            with event_lock:
                tool_count = sum(
                    e.get("type") == "item.completed"
                    and (e.get("item") or {}).get("type")
                    in PUBLIC_TYPES - {"agent_message", "todo_list"}
                    for e in events
                )
            temp = output / "progress.tmp"
            temp.write_text(
                json.dumps({**sample, "tools_completed": tool_count, "observation_only": True})
                + "\n"
            )
            temp.replace(output / "progress.json")
            # Sampling interval, NEVER a termination condition.
            finished.wait(15)
    wait_thread.join()
    out_thread.join()
    err_thread.join()
    wall = ended["wall"]
    summary, final = installer.summarize(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events)
    )
    summary.update(
        started,
        ended_utc=ended["utc"],
        exit_code=proc.returncode,
        wall_seconds=round(wall, 3),
        process_success=proc.returncode == 0 and summary["turn_completed"],
        public_messages=[
            e["item"]["text"]
            for e in events
            if e.get("type") == "item.completed"
            and (e.get("item") or {}).get("type") == "agent_message"
        ],
        final=final,
        error_events=[e for e in events if e.get("type") in ("error", "turn.failed")],
        event_counts=dict(counts),
        stderr=clean("".join(stderr_parts), base, manifest),
        native_memory=installer.native_counts(Path(env["CODEX_HOME"])),
        account_side_isolation="unproven",
        backend_model_echo=None,
        backend_service_tier_echo=None,
        billed_cost=None,
        human_review=None,
        model_wall_clock_limit=None,
        token_budget=None,
        tool_call_budget=None,
        output_length_budget=None,
    )
    return summary


def one(manifest, cell, storage):
    output = HERE / "results" / cell["id"]
    output.mkdir(parents=True, exist_ok=True)
    if (output / "call.json").exists() or (output / "skipped.json").exists():
        return
    assert not (output / "call.started.json").exists(), (
        "incomplete prior call; inspect, never auto-rerun"
    )
    with LOCK:
        blocker = BLOCKED.get(cell["tuple"]) or BLOCKED.get("account")
    if blocker:
        save(
            output / "skipped.json",
            {
                "cell": cell,
                "call_attempted": False,
                "reason": blocker,
                "usage": dict.fromkeys(USAGE_FIELDS),
            },
        )
        return
    base = storage / cell["id"]
    server = None
    browser_proc = None
    codex = base / "profile/home/.codex"
    begin = time.monotonic()
    try:
        verify(manifest)
        base.mkdir(mode=0o700)
        workspace = base / "workspace"
        workspace.mkdir()
        codex, env, config = make_profile(base, manifest)
        shutil.copyfile(HERE / "tasks" / f"{cell['task']}.md", workspace / "TASK.md")
        arm = manifest["arms"][cell["arm"]]
        package = None
        if cell["arm"] != "vanilla":
            package = installer.install(
                {"client": {"path": manifest["client"]["launcher"]}}, arm, base, env, output
            )
        browser_proc = browser_tool(base, manifest, env, workspace, output)
        url = None
        if cell["task"] == "consulting":
            server, url = serve_sources(output)
        tooling = f"""# Available environment\n\nPython: {manifest["tools"]["python"]}\nNode: {manifest["tools"]["node"]}\nShared Node packages: {manifest["tools"]["node_modules"]}\nGo: /usr/local/go/bin/go\nSystem shell, curl, git and local toolchains are available. Choose your own programming language/stack. Public network/dependency downloads are enabled. Install dependencies only within this disposable workspace/profile.\nBundled Python has pandas, openpyxl, python-docx, python-pptx, reportlab and PDF/image tools. Bundled Node has Playwright; NODE_PATH and PLAYWRIGHT_BROWSERS_PATH are set. Use headless Chromium for local browser verification.\n"""
        tooling += "\nA fresh isolated Chromium tool is already running for this cell. Connect using Playwright: const {chromium}=require('playwright'); const browser=await chromium.connect(process.env.EVAL_BROWSER_WS); const context=await browser.newContext(); const page=await context.newPage(); Close your context and browser connection when done. Do not call chromium.launch() inside the Codex shell: macOS shell IPC blocks browser startup. This WebSocket tool has its own filesystem isolation and no existing browsing profile.\n"
        if url:
            tooling += f"\nSource room: {url}\nCollect from its index and preserve source provenance. Public research is also available.\n"
        (workspace / "TOOLING.md").write_text(tooling)
        preflight(manifest, base, workspace, codex, env, output)
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
                "Frozen task input",
            ],
        ):
            p = command(args, env, workspace)
            assert p.returncode == 0, p.stderr
        entry = (
            ""
            if package is None
            else f"Use the installed OpenSocrates controller at {package / 'skills/opensocrates/SKILL.md'} as its instructions direct. No particular reasoning method is required by the evaluator.\n"
        )
        prompt = (
            manifest["common_prompt"] + "\n" + entry + "\n" + (workspace / "TASK.md").read_text()
        )
        save(
            output / "inputs.json",
            {
                "task_source_sha256": sha(HERE / "tasks" / f"{cell['task']}.md"),
                "workspace_files": inventory(workspace),
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "config_sha256": hashlib.sha256(config.encode()).hexdigest(),
                "config": clean(config, base, manifest),
                "package_sha256": arm.get("archive_sha256"),
                "source_room": bool(url),
                "setup_wall_seconds": round(time.monotonic() - begin, 3),
            },
        )
        started = {
            **cell,
            "attempt": 1,
            "call_attempted": True,
            "started_utc": now(),
            "manifest_sha256": sha(HERE / "manifest.json"),
            "service_tier_requested": "default",
            "fast_mode_enabled": False,
        }
        save(output / "call.started.json", started)
        args = [
            manifest["client"]["launcher"],
            "--no-daemon",
            "--ask-for-approval",
            "never",
            "exec",
            "--skip-git-repo-check",
            "--ignore-rules",
            "--ephemeral",
            "--json",
            "-C",
            str(workspace),
            "-m",
            cell["model"],
            "-c",
            f'model_reasoning_effort="{cell["effort"]}"',
            "-c",
            'service_tier="default"',
        ]
        for feature in manifest["disabled_features"]:
            args += ["--disable", feature]
        args += ["-"]
        print(json.dumps({"event": "start", "cell": cell["id"], "utc": now()}), flush=True)
        result = observe(args, prompt, env, workspace, base, output, manifest, started)
        result["protected_inputs_unchanged"] = sha(workspace / "TASK.md") == sha(
            HERE / "tasks" / f"{cell['task']}.md"
        )
        result["package_members_unchanged"] = (
            all(sha(package / p) == h for p, h in arm["members"].items()) if package else None
        )
        result["product_memory_enrolled"] = False
        result["product_data_tree_created"] = (base / "profile/product-data").exists()
        save(output / "call.json", result)
        files = inventory(workspace)
        save(
            output / "snapshot.json",
            {
                "locked_utc": now(),
                "locked_before_independent_checks": True,
                "files": files,
                "excluded_dependency_directories": sorted(EXCLUDED),
            },
        )
        snapshot = base / "locked-artifacts"
        snapshot.mkdir()
        for name, meta in files.items():
            dest = snapshot / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(workspace / name, dest)
            assert sha(dest) == meta["sha256"]
        error_text = (result["stderr"] + json.dumps(result["error_events"])).lower()
        if not result["turn_completed"]:
            with LOCK:
                if any(
                    x in error_text
                    for x in (
                        "usage limit",
                        "rate_limit",
                        "insufficient_quota",
                        "authentication",
                        "unauthorized",
                    )
                ):
                    BLOCKED["account"] = cell["id"] + ": account access/usage failure"
                elif any(
                    x in error_text
                    for x in ("not supported", "model_not_found", "capacity", "not available")
                ):
                    BLOCKED[cell["tuple"]] = cell["id"] + ": tuple access failure"
        print(
            json.dumps(
                {
                    "event": "done",
                    "cell": cell["id"],
                    "success": result["process_success"],
                    "wall_seconds": result["wall_seconds"],
                    "usage": result["usage"],
                }
            ),
            flush=True,
        )
    except Exception as error:
        save(
            output / "harness-failure.json",
            {
                "utc": now(),
                "type": type(error).__name__,
                "detail": clean(str(error), base, manifest),
                "call_attempted": (output / "call.started.json").exists(),
                "usage": dict.fromkeys(USAGE_FIELDS),
            },
        )
        print(
            json.dumps({"event": "harness_failure", "cell": cell["id"], "error": str(error)}),
            flush=True,
        )
    finally:
        close_browser(browser_proc, output, base, manifest)
        if server:
            server.shutdown()
            server.server_close()
        (codex / "auth.json").unlink(missing_ok=True)
        save(
            output / "cleanup.json",
            {
                "utc": now(),
                "auth_copy_removed": not (codex / "auth.json").exists(),
                "active_installation_changed": False,
            },
        )


def execute(manifest, storage):
    storage.mkdir(mode=0o700, parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(one, manifest, c, storage) for c in manifest["cells"]]
        for future in futures:
            future.result()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["execute", "verify"])
    p.add_argument("--storage", type=Path, required=True)
    a = p.parse_args()
    manifest = read(HERE / "manifest.json")
    verify(manifest)
    if a.action == "execute":
        execute(manifest, a.storage)
    else:
        print("frozen inputs verified")
