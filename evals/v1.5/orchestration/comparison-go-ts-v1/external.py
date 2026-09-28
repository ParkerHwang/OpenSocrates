"""Serial, locked-copy Go/TypeScript qualification after subject generation.

The verifier is trusted deterministic evaluation code. Model roles never see
private oracle files, verifier results, or this post-generation workspace.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def inventory(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("symlink_in_disposable_copy")
        if path.is_file():
            result[str(path.relative_to(root))] = digest(path.read_bytes())
    return result


def stage(task: dict[str, Any], fixtures: Path, files: dict[str, bytes], run: Path) -> Path:
    public = fixtures / task["public_root"]
    target = run / "candidate-copy"
    if target.exists():
        raise FileExistsError(target)
    shutil.copytree(public / task["starter_root"], target, symlinks=False)
    data = public / "data"
    if data.is_dir():
        shutil.copytree(data, target / "data", symlinks=False)
    # The trusted verifier refuses any unmarked or in-place project directory.
    # This marker is operator-owned and never comes from a model artifact.
    (target / ".eval-copy").write_text("disposable qualification copy\n", encoding="utf-8")
    allowed = set(task["required_artifacts"])
    if not set(files) <= allowed:
        raise ValueError("undeclared_candidate_path")
    for name, content in files.items():
        path = target / name
        if not path.resolve().is_relative_to(target.resolve()):
            raise ValueError("candidate_path_escape")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return target


def candidate_policy(run: Path, deps: Path) -> str:
    # The private fixture/oracle root is intentionally absent. Only trusted
    # verifier Python runs outside this profile; every candidate-controlled
    # Go, TypeScript and browser child must enter it before executing code.
    roots = [run.resolve(), deps.resolve()]
    allowed = " ".join(f'(subpath "{str(path)}")' for path in roots)
    return f'''(version 1)
(allow default)
(deny file-read-data (require-all
  (require-any (subpath "/Users") (subpath "/private/tmp") (subpath "/private/var/folders"))
  (require-not (require-any {allowed}))))
(deny file-write* (require-not (require-any (subpath "{run.resolve()}") (literal "/dev/null"))))
(deny network-outbound (require-not (remote ip "localhost:*")))
'''


def qualify(task: dict[str, Any], fixtures: Path, deps: Path,
            files: dict[str, bytes], run: Path, *, scope: str = "full") -> dict[str, Any]:
    if scope not in {"full", "analysis"}:
        raise ValueError("unknown_external_scope")
    run.mkdir(mode=0o700, parents=True, exist_ok=False)
    candidate = stage(task, fixtures, files, run)
    before = inventory(candidate)
    boundary = run / "candidate-policy.sb"
    boundary.write_text(candidate_policy(run, deps), encoding="utf-8")
    temporary = run / "tmp"
    temporary.mkdir()
    home = run / "home"
    home.mkdir()
    spec = task["external_qualification"]
    entrypoint = fixtures / spec["entrypoint"]
    if not entrypoint.is_file():
        raise ValueError("external_verifier_missing")
    command = [
        str(entrypoint) if value == "{entrypoint}" else
        str(candidate) if value == "{marked_disposable_copy}" else
        str(boundary) if value == "{candidate_policy}" else
        str(deps) if value == "{deps_root}" else value
        for value in spec["command_template"]
    ]
    if "--candidate-policy" not in command:
        command += ["--candidate-policy", str(boundary)]
    if scope == "analysis":
        command += ["--scope", "analysis"]
    env = {
        "HOME": str(home), "TMPDIR": str(temporary),
        "PATH": "/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
        "GOMODCACHE": str(deps / "go-modcache"), "GOCACHE": str(run / "go-buildcache"),
        "GOPATH": str(run / "go-path"), "GOTMPDIR": str(temporary),
        "GOPROXY": "off", "GOSUMDB": "off", "CGO_ENABLED": "1",
        "NODE_PATH": str(deps / "npm/node_modules"),
        "PLAYWRIGHT_BROWSERS_PATH": str(deps / "browsers"),
        "OPENSOCRATES_EVAL_DEPS": str(deps),
        "OPENSOCRATES_CANDIDATE_POLICY": str(boundary),
    }
    started_utc = datetime.now(timezone.utc).isoformat()
    started = time.monotonic_ns()
    # A broad verifier sandbox would be inherited by candidate code and would
    # prevent its stricter nested Seatbelt from applying. The trusted verifier
    # is audited code; every candidate child must apply boundary itself.
    result = subprocess.run(
        command,
        cwd=candidate, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        start_new_session=True,
    )
    ended = time.monotonic_ns()
    try:
        structured = json.loads(result.stdout)
        if not isinstance(structured, dict):
            structured = None
    except (ValueError, UnicodeError):
        structured = None
    after = inventory(candidate)
    return {
        "schema": "opensocrates.go-ts.external-qualification/1",
        "scope": scope,
        "started_utc": started_utc, "elapsed_ns": ended - started,
        "argv_sha256": digest(json.dumps(command, separators=(",", ":")).encode()),
        "policy_sha256": digest(boundary.read_bytes()),
        "entrypoint_sha256": digest(entrypoint.read_bytes()),
        "before": before, "after": after,
        "exit_code": result.returncode,
        "stdout_sha256": digest(result.stdout), "stderr_sha256": digest(result.stderr),
        "structured": structured,
        "raw_output_retained": False,
    }
