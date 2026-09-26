"""Evaluation-only transparent native-memory audit adapter; never product memory."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    configuration = json.loads(Path(__file__).with_suffix(".json").read_text())
    raw = sys.stdin.buffer.read(262145)
    request = json.loads(raw)
    if len(raw) > 262144 or request.get("project_id") != configuration["project_id"]:
        raise ValueError("outside declared evaluation project")
    if request.get("workspace_id") != configuration["workspace_id"]:
        raise ValueError("outside declared evaluation workspace")
    if request.get("operation") == "init" or (
        request.get("operation") == "delete"
        and request.get("payload", {}).get("intent") != "delete_record"
    ):
        raise ValueError("only exact record mutations authorized in this adapter")
    result = subprocess.run(
        ["bash", configuration["launcher"], "memory", "codex"],
        input=raw,
        capture_output=True,
        cwd=configuration["workspace"],
        timeout=60,
        check=False,
    )
    response = json.loads(result.stdout)
    payload = request.get("payload") or {}
    body = response.get("result") or {}
    record = body.get("record") if isinstance(body, dict) else None
    receipt = {
        "operation": request.get("operation"),
        "request_id": request.get("request_id"),
        "response_request_id": response.get("request_id"),
        "project_id": request.get("project_id"),
        "workspace_id": request.get("workspace_id"),
        "target_record_id": payload.get("record_id"),
        "expected_record_version": payload.get("expected_record_version"),
        "acceptance_basis": payload.get("acceptance_basis"),
        "summary_sha256": hashlib.sha256(payload["summary"].encode()).hexdigest()
        if isinstance(payload.get("summary"), str)
        else None,
        "status": response.get("status"),
        "exit_code": result.returncode,
        "record": {key: record.get(key) for key in ("record_id", "version", "lifecycle")}
        if isinstance(record, dict)
        else None,
        "response_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "limitations": response.get("limitations"),
    }
    descriptor = os.open(
        configuration["audit_log"], os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600
    )
    try:
        encoded = (json.dumps(receipt, ensure_ascii=False) + "\n").encode()
        assert os.write(descriptor, encoded) == len(encoded)
    finally:
        os.close(descriptor)
    sys.stdout.buffer.write(result.stdout)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
