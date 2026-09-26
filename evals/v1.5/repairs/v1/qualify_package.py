"""Zero-model disposable native execution of the packaged checkpoint examples."""

import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def qualify_locale(package, base, locale):
    workspace, data, home = (base / f"{locale}-{x}" for x in ("workspace", "data", "home"))
    for path in (workspace, data, home):
        path.mkdir(mode=0o700)
    env = {key: os.environ[key] for key in ("PATH", "LANG") if key in os.environ}
    env.update(
        HOME=str(home),
        OPENSOCRATES_DATA_DIR=str(data),
        OPENSOCRATES_MEMORY_FIXTURE="1",
        OPENSOCRATES_DEVELOPMENT_MANIFEST="1",
    )
    project = binding = None
    task = str(uuid4())
    operations = []

    def call(operation, payload):
        request = {
            "schema": "opensocrates.project-memory.request/1.0.0",
            "request_id": str(uuid4()),
            "project_id": project,
            "workspace_id": binding,
            "task_id": task,
            "operation": operation,
            "payload": payload,
        }
        proc = subprocess.run(
            [str(package / "bin/launch.sh"), "memory", "codex"],
            cwd=workspace,
            env=env,
            input=json.dumps(request),
            text=True,
            capture_output=True,
            timeout=30,
        )
        response = json.loads(proc.stdout)
        operations.append(
            {"operation": operation, "status": response["status"], "exit_code": proc.returncode}
        )
        assert proc.returncode == (
            2
            if response["status"] == "invalid_request"
            else 3
            if response["status"] == "unavailable"
            else 0
        )
        return response

    enrollment = {
        "root": str(workspace),
        "apply": False,
        "mode": "read_write",
        "capture_policy": "milestones",
        "excluded_paths": [],
    }
    preview = call("init", enrollment)
    applied = call(
        "init",
        {
            **enrollment,
            "apply": True,
            "disclosure_digest": preview["result"]["disclosure_digest"],
            "authorization_basis": "fixture:checkpoint-repair",
            "authorization_attribution": "operator_declared",
            "idempotency_key": str(uuid4()),
        },
    )
    assert applied["status"] == "ok", applied
    project, binding = applied["result"]["project_id"], applied["result"]["workspace_id"]
    guide = (
        package / f"skills/opensocrates/references/assistance/checkpoint.{locale}.md"
    ).read_text()
    payload = json.loads(re.findall(r"```json\n(.*?)\n```", guide, re.S)[0])["payload"]
    payload["idempotency_key"] = str(uuid4())
    created = call("checkpoint", payload)
    assert created["status"] == "ok", created
    record_id = created["result"]["record_id"]
    inspected = call("inspect", {"record_id": record_id})["result"]
    assert inspected["payload"]["completed_actions"] == payload["completed_actions"]
    for support in ("runtime_observed", "tool_reported"):
        invalid = copy.deepcopy(payload)
        invalid["idempotency_key"] = str(uuid4())
        invalid["completed_actions"][0]["support"] = support
        before = [p.read_bytes() for p in data.rglob("*.sqlite3")]
        assert call("checkpoint", invalid)["status"] == "invalid_request"
        assert [p.read_bytes() for p in data.rglob("*.sqlite3")] == before
    payload.update(
        expected_checkpoint_version=inspected["payload"]["checkpoint_version"],
        idempotency_key=str(uuid4()),
        next_action="Verify current source facts.",
    )
    updated = call("checkpoint", payload)
    assert updated["status"] == "ok" and updated["result"]["checkpoint_version"] == 2
    assert call("checkpoint", payload)["result"] == updated["result"]
    recalled = call("recall", {"need": "continue task", "budget_bytes": 8192})
    assert recalled["result"]["checkpoint_reference"] == record_id
    assert call("inspect", {"record_id": record_id})["result"]["payload"]["checkpoint_version"] == 2
    return {"locale": locale, "status": "pass", "operations": operations}


def main():
    archive = ROOT / "dist/opensocrates-1.5.0-codex-plugin.zip"
    results, members = [], {}
    with tempfile.TemporaryDirectory(prefix="os-checkpoint-native-", dir="/private/tmp") as tmp:
        base = Path(tmp)
        package = base / "package"
        package.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            assert bundle.testzip() is None
            for entry in bundle.infolist():
                rel = Path(entry.filename)
                assert not rel.is_absolute() and ".." not in rel.parts
                if entry.is_dir():
                    continue
                dest = package / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(bundle.read(entry))
                dest.chmod(0o755 if (entry.external_attr >> 16) & 0o111 else 0o644)
            for source in sorted((ROOT / "schemas/v1").glob("*.json")):
                for prefix in (
                    "schemas/v1/",
                    "runtime/darwin-arm64/opensocrates-runtime/_internal/schemas/v1/",
                ):
                    name = prefix + source.name
                    assert bundle.read(name) == source.read_bytes(), name
                    members[name] = digest(bundle.read(name))
            for source in sorted((ROOT / "plugin-src/shared").glob("**/*.md")):
                if source.parent.name not in {"assistance", "coding"}:
                    continue
                name = "skills/opensocrates/references/" + str(
                    source.relative_to(ROOT / "plugin-src/shared")
                )
                assert bundle.read(name) == source.read_bytes(), name
                members[name] = digest(bundle.read(name))
        results = [qualify_locale(package, base, locale) for locale in ("en", "ko")]
    receipt = {
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "archive_sha256": digest(archive.read_bytes()),
        "packaged_bytes": members,
        "model_calls": 0,
        "results": results,
        "active_installation_changed": False,
    }
    with (HERE / "native-package.json").open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {"native_examples": "2/2 pass", "packaged_members": len(members), "model_calls": 0}
        )
    )


if __name__ == "__main__":
    main()
