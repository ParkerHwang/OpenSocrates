"""Non-model installed RC acceptance in disposable Git and directory projects."""

import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

from runner import (
    HERE,
    ROOT,
    accepted_intent,
    files,
    install,
    memory_call,
    post_memory,
    profile,
    read,
    save,
    seed_memory,
    sha,
)


def main():
    manifest = read(HERE / "manifest.v1.json")
    archive = ROOT / "dist/opensocrates-1.5.0-codex-plugin.zip"
    with zipfile.ZipFile(archive) as zipped:
        names = [name for name in zipped.namelist() if not name.endswith("/")]
        selected = [
            name
            for name in names
            if name.startswith("schemas/v1/")
            or name.startswith("skills/opensocrates/references/assistance/")
            or name
            in {
                "bin/launch.sh",
                "skills/opensocrates/SKILL.md",
                "runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime",
            }
        ]
        import hashlib

        members = {name: hashlib.sha256(zipped.read(name)).hexdigest() for name in selected}
        assert json.loads(zipped.read(".codex-plugin/plugin.json"))["version"] == "1.5.0"
        for language in ("en", "ko"):
            assert (
                zipped.read(f"skills/opensocrates/references/assistance/guide.{language}.md")
                == (ROOT / f"plugin-src/shared/assistance/guide.{language}.md").read_bytes()
            )
        for name in names:
            if name.startswith("schemas/v1/"):
                assert zipped.read(name) == (ROOT / name).read_bytes()
                assert zipped.read(name) == zipped.read(
                    "runtime/darwin-arm64/opensocrates-runtime/_internal/" + name
                )
    arm = {
        "id": "rc-1.5.0",
        "archive_path": str(archive),
        "archive_sha256": sha(archive),
        "package_version": "1.5.0",
        "memory": True,
        "members": members,
    }
    task = next(
        row for row in read(HERE / "fixtures.v1.json")["scenarios"] if row["id"] == "continuity"
    )
    root_output = HERE / "rc-acceptance"
    root_output.mkdir(exist_ok=False)
    results = []
    for kind in ("directory", "git"):
        output = root_output / kind
        result = {"kind": kind, "model_calls": 0, "checks": {}}
        with tempfile.TemporaryDirectory(prefix="os-v15-rc-", dir="/private/tmp") as temporary:
            base = Path(temporary)
            workspace, data = base / "workspace", base / "data"
            workspace.mkdir(mode=0o700)
            data.mkdir(mode=0o700)
            codex, env = profile(base / "profile")
            env.update(
                {
                    "OPENSOCRATES_MEMORY_FIXTURE": "1",
                    "OPENSOCRATES_DEVELOPMENT_MANIFEST": "1",
                    "OPENSOCRATES_DATA_DIR": str(data),
                }
            )
            try:
                files(workspace, task["files"])
                if kind == "git":
                    for args in (
                        ["git", "init", "-q"],
                        ["git", "add", "."],
                        [
                            "git",
                            "-c",
                            "user.name=Fixture",
                            "-c",
                            "user.email=fixture@example.invalid",
                            "commit",
                            "-qm",
                            "RC fixture",
                        ],
                    ):
                        subprocess.run(
                            args, cwd=workspace, env=env, capture_output=True, check=True
                        )
                package = install(manifest, arm, base, env, output)
                before_files = {name: sha(workspace / name) for name in task["files"]}
                seed = seed_memory(package, workspace, env, task, output)
                operations = []

                def call(
                    op,
                    payload,
                    package=package,
                    workspace=workspace,
                    env=env,
                    seed=seed,
                    operations=operations,
                ):
                    receipt, response = memory_call(
                        package,
                        workspace,
                        env,
                        op,
                        payload,
                        seed["project_id"],
                        seed["workspace_id"],
                    )
                    operations.append(receipt)
                    assert response["status"] == "ok", (op, response)
                    return response["result"]

                record = call(
                    "record",
                    {
                        "idempotency_key": str(uuid4()),
                        "expected_record_version": 0,
                        "kind": "decision",
                        "scope": {"level": "project"},
                        "summary": "Saturday workshop: 52 attendees require step-free entry and a quiet room; choose the least costly qualifying venue within $1,400. No booking exists.",
                        "origin": {
                            "producer_kind": "agent",
                            "source_reference": None,
                            "attestation": "agent_reported",
                        },
                        "support": "agent_reported",
                        "source_refs": [],
                        "revalidation": {
                            "dependency_paths": [],
                            "negative_claim": False,
                            "on_change": "not_applicable",
                        },
                    },
                )["record"]
                call(
                    "accept",
                    {
                        "record_id": record["record_id"],
                        "expected_record_version": record["version"],
                        "idempotency_key": str(uuid4()),
                        "acceptance_basis": "fixture:rc-scoped-intent",
                        "acceptance_attribution": "operator_declared",
                    },
                )
                old, unrelated, proposed = seed["records"]
                call(
                    "delete",
                    {
                        "intent": "delete_record",
                        "record_id": old["record_id"],
                        "expected_record_version": old["version"],
                        "idempotency_key": str(uuid4()),
                    },
                )
                state = post_memory(package, workspace, env, seed, output, 0)
                records = state["records"]
                by_id = {item["record_id"]: item for item in records}
                result["checks"] = {
                    "installed_bytes": True,
                    "all_41_schemas_and_bilingual_guides_match": True,
                    "complete_export": state["export_complete"],
                    "accepted_intent_preserved": accepted_intent(records),
                    "exact_old_record_deleted": old["record_id"] not in by_id,
                    "unrelated_accepted_record_unchanged": by_id.get(unrelated["record_id"])
                    == unrelated,
                    "proposal_not_promoted": by_id.get(proposed["record_id"], {}).get("lifecycle")
                    == "proposed",
                    "withdrawn_summary_absent": all(
                        "60" not in item["summary"] for item in records
                    ),
                }
                call(
                    "delete",
                    {
                        "intent": "delete_project",
                        "expected_policy_version": 1,
                        "idempotency_key": str(uuid4()),
                    },
                )
                result["checks"]["source_files_unchanged_after_project_delete"] = before_files == {
                    name: sha(workspace / name) for name in task["files"]
                }
                result["checks"]["project_store_deleted"] = not (
                    data / "projects" / seed["project_id"]
                ).exists()
                result["operations"] = operations
                assert all(result["checks"].values()), result["checks"]
            finally:
                (codex / "auth.json").unlink(missing_ok=True)
                result["auth_copy_removed"] = not (codex / "auth.json").exists()
                save(output / "result.json", result)
            results.append(result)
    save(
        root_output / "summary.json",
        {
            "schema": "opensocrates.rc-installed-acceptance/1.0.0",
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "product_version": "1.5.0",
            "archive_sha256": arm["archive_sha256"],
            "client": manifest["client"],
            "model_calls": 0,
            "results": results,
            "scope": "Disposable macOS Git/directory installed-native acceptance; no active installation, real project or destructive account-home test.",
        },
    )
    print(
        "Installed RC acceptance: PASS (Git + directory, all schema/guide bytes, scoped and project deletion; zero model calls)"
    )


if __name__ == "__main__":
    main()
