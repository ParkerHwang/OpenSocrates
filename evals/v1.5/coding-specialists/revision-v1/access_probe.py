"""One frozen exact-tuple access probe; no generation wall-clock cutoff."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CLIENT = Path("/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex")
ACTUAL = Path("/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex")
HELPER = ROOT / "evals/v1.5/expanded/harness_v4.py"
SPEC = importlib.util.spec_from_file_location("specialist_probe_helpers", HELPER)
helpers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helpers)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / "access-manifest.json").read_text())
    assert sha(CLIENT) == manifest["launcher_sha256"]
    assert sha(ACTUAL) == manifest["executable_sha256"]
    assert sha(__file__) == manifest["runner_sha256"]
    assert sha(HELPER) == manifest["helper_sha256"]
    output = HERE / "access-result.json"
    assert not output.exists(), "Every new attempt needs a new frozen boundary."
    base = Path(manifest["disposable_root"])
    base.mkdir(mode=0o700)
    work = base / "workspace"
    work.mkdir()
    codex, env = helpers.profile(base / "profile")
    (codex / "config.toml").write_text(manifest["profile_config"])
    args = [str(CLIENT), "--no-daemon", "--ask-for-approval", "never", "exec",
            "--sandbox", "read-only", "--skip-git-repo-check", "--ignore-rules",
            "--ephemeral", "--json", "-C", str(work)]
    for feature in manifest["disabled_features"]:
        args += ["--disable", feature]
    args += ["-m", manifest["model"], "-c", f'model_reasoning_effort="{manifest["effort"]}"', "-"]
    started = time.time()
    helpers.save_new(HERE / "access-started.json", {"started_unix": started, "attempt": 1})
    try:
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, cwd=work, env=env)
        raw, err = proc.communicate(manifest["prompt"])
        result, final = helpers.summarize(raw)
        result.update(exit_code=proc.returncode, wall_seconds=round(time.time()-started, 3),
                      model=manifest["model"], effort=manifest["effort"],
                      final=final, successful_probe=proc.returncode == 0 and final.strip() == "SPECIALIST_ACCESS_OK",
                      stderr_sha256=hashlib.sha256(err.encode()).hexdigest(),
                      model_wall_clock_limit=None, account_side_isolation="unproven")
        helpers.save_new(output, result)
        print(json.dumps({k: result[k] for k in ("successful_probe", "exit_code", "model", "effort", "wall_seconds", "usage")}), flush=True)
    finally:
        (codex / "auth.json").unlink(missing_ok=True)
        helpers.save_new(HERE / "access-cleanup.json", {"disposable_auth_copy_removed": not (codex / "auth.json").exists()})


if __name__ == "__main__":
    main()
