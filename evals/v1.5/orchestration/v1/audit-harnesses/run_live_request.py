"""Run one frozen synthetic request once through the packaged public CLI."""

import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    data = args.request.read_bytes()
    request = json.loads(data)
    assert request["operation"] == "run"
    assert request["model"] == {"name": "gpt-6-astra", "effort": "max"}
    assert request["repair_limit"] == 1
    launcher = (args.package / "bin/launch.sh").resolve()
    start = time.monotonic()
    write_new(args.output / "started.json", {
        "schema": "opensocrates.orchestration.live-invocation/1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "request_sha256": sha(data), "launcher_sha256": sha(launcher.read_bytes()),
        "configured_model": request["model"], "outer_retries": 0,
        "model_wall_clock_cutoff": None,
    })
    result = subprocess.run([str(launcher), "orchestrate", "codex"], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=args.package.resolve(), check=False)
    try:
        response = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        response = None
    write_new(args.output / "invocation.json", {
        "schema": "opensocrates.orchestration.live-invocation-result/1",
        "request_sha256": sha(data), "exit_code": result.returncode,
        "elapsed_seconds": time.monotonic() - start,
        "stdout_sha256": sha(result.stdout), "stderr_sha256": sha(result.stderr),
        "response_available": response is not None, "outer_retries": 0,
        "raw_event_or_prompt_retained": False,
    })
    if response is not None:
        write_new(args.output / "response.json", response)
    print(json.dumps({"exit_code": result.returncode,
                      "status": response.get("status") if isinstance(response, dict) else None,
                      "recorded_role_calls": len(response.get("calls", [])) if isinstance(response, dict) else None}))
    return 0 if result.returncode == 0 and response is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
