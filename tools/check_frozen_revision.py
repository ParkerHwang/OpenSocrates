#!/usr/bin/env python3
"""Exercise revised commands and canonical bytes through a disposable native package."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from check_frozen_memory import request, run, uid
from check_task_verification import exercise as check_task_verification


def check_decision_recovery(command, root, package, launcher, environment, base):
    template = json.loads(
        (root / "plugin-src/shared/decision/request.json").read_text(encoding="utf-8")
    )
    for locale in ("en", "ko"):
        prepared_decision = command("decision", {"operation": "prepare", "locale": locale})
        assert prepared_decision["status"] == "prepared"
        assert prepared_decision["selector_model_calls"] == 0
        draft_decision = prepared_decision["request"]
        assert command("decision", draft_decision)["diagnostic"]["field_path"] == "$.participation"
        draft_decision.update(participation="judgment", routing=template["routing"])
        selected = command("decision", draft_decision)
        assert selected["selected"] == ["critical-thinking"]
        assert selected["methods"][0]["instructions"] == (
            package
            / f"skills/opensocrates/references/decision/methods/{locale}/critical-thinking.md"
        ).read_text(encoding="utf-8")
        invalid = json.loads(json.dumps(draft_decision))
        invalid["context"] = "b" * 32
        invalid["routing"]["features"][0]["basis"] = "governing_rule"
        acknowledged = dict(
            operation="acknowledge",
            context=draft_decision["context"],
            epoch=0,
            digests=[selected["methods"][0]["sha256"]],
        )
        streamed = subprocess.run(
            [*launcher, "decision", "codex", "--stream"],
            input="".join(
                json.dumps(value) + "\n"
                for value in (draft_decision, acknowledged, invalid, draft_decision)
            ).encode(),
            capture_output=True,
            env=environment,
            cwd=base,
            timeout=30,
        )
        assert streamed.returncode == 0
        responses = [json.loads(line) for line in streamed.stdout.splitlines()]
        assert len(responses) == 4
        assert responses[2]["diagnostic"]["field_path"] == "$.routing.features[0].basis"
        assert responses[3]["selection_reused"]
        assert responses[3]["methods"][0]["instructions"] is None


def check(binary: Path, package: Path) -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="opensocrates-revision-") as temporary:
        base = Path(temporary)
        data = base / "data"
        source = base / "event"
        if os.name == "nt":
            from opensocrates.persistence.permissions import create_owner_only_directory

            assert create_owner_only_directory(source)
        else:
            source.mkdir()
        (source / "brief.md").write_text("Capacity: 64.\n", encoding="utf-8")
        environment = {
            **os.environ,
            "OPENSOCRATES_MEMORY_FIXTURE": "1",
            "OPENSOCRATES_DEVELOPMENT_MANIFEST": "1",
            "OPENSOCRATES_DATA_DIR": str(data),
        }
        launcher = (
            ["node", str(package / "bin/launch.mjs")]
            if os.name == "nt"
            else [str(package / "bin/launch.sh")]
        )

        def command(mode, value):
            result = subprocess.run(
                [*launcher, mode, "codex"],
                input=json.dumps(value).encode(),
                capture_output=True,
                env=environment,
                cwd=base,
                timeout=30,
            )
            assert result.returncode == 0, (mode, result.returncode)
            return json.loads(result.stdout)

        documented = json.loads(
            (root / "plugin-src/shared/documentation/request.json").read_text(encoding="utf-8")
        )
        for locale in ("en", "ko"):
            result = command("documentation", {**documented, "locale": locale})
            assert result["next_action"] == "read_reference"
            assert result["application"] == "unverified"
            assert result["instructions"] == (
                root / f"plugin-src/shared/documentation/prompt.{locale}.md"
            ).read_text(encoding="utf-8")
        obligations = json.loads(
            (root / "plugin-src/shared/assistance/obligations.json").read_text(encoding="utf-8")
        )
        result = command("assistance", obligations)
        assert result["obligation_summary"]["ready_ids"] == ["draft"]
        assert result["obligation_summary"]["required_input_ids"] == ["budget"]
        task_verification = check_task_verification(command, root)
        check_decision_recovery(command, root, package, launcher, environment, base)
        assert not data.exists(), "stateless commands initialized memory"
        payload = {
            "root": str(source),
            "apply": False,
            "mode": "read_write",
            "capture_policy": "milestones",
            "excluded_paths": [],
        }
        preview = run(binary, environment, request("init", payload))
        payload.update(
            apply=True,
            disclosure_digest=preview["result"]["disclosure_digest"],
            authorization_basis="fixture:revision",
            authorization_attribution="operator_declared",
            idempotency_key=uid(),
        )
        enrolled = run(binary, environment, request("init", payload))["result"]
        project, workspace, task = enrolled["project_id"], enrolled["workspace_id"], uid()
        prepared_request = json.loads(
            (package / "skills/opensocrates/references/assistance/memory-prepare.json").read_text(
                encoding="utf-8"
            )
        )
        prepared_request.update(
            request_id=uid(), project_id=project, workspace_id=workspace, task_id=task
        )
        before = {p.relative_to(data): p.read_bytes() for p in data.rglob("*") if p.is_file()}
        prepared = command("memory", prepared_request)
        assert prepared["status"] == "ok", prepared
        assert {
            p.relative_to(data): p.read_bytes() for p in data.rglob("*") if p.is_file()
        } == before
        draft = prepared["result"]["request"]
        draft["payload"].update(
            objective="Update the public event plan.",
            constraints=["Do not book."],
            completion_conditions=["Capacity matches current source."],
            next_action="Recheck the current brief.",
        )
        saved = command("memory", draft)
        assert saved["status"] == "ok", saved
        recalled_request = request(
            "recall",
            {"need": "continue", "budget_bytes": 16384, "scope_paths": ["brief.md"]},
            project,
            workspace,
            task,
        )
        recalled_request["schema"] = "opensocrates.project-memory.request/1.1.0"
        recalled = command("memory", recalled_request)
        assert recalled["status"] == "ok", recalled
        assert recalled["result"]["checkpoint"]["checkpoint_version"] == 1
        assert recalled["result"]["constraints"][0]["lifecycle"] == "proposed"
        assert recalled["result"]["searched_scope"] == ["brief.md"]
        deleted = command(
            "memory",
            request(
                "delete",
                {
                    "intent": "delete_record",
                    "record_id": saved["result"]["record_id"],
                    "expected_record_version": 1,
                    "idempotency_key": uid(),
                },
                project,
                workspace,
                task,
            ),
        )
        assert deleted["status"] == "ok"
        assert command("memory", recalled_request)["result"]["checkpoint"] is None
        assert (
            command(
                "memory",
                request(
                    "delete",
                    {
                        "intent": "delete_project",
                        "expected_policy_version": 1,
                        "idempotency_key": uid(),
                    },
                    project,
                ),
            )["status"]
            == "ok"
        )
        assert not (data / "projects" / project).exists()

    internal = binary.parent / "_internal"
    checked = 0
    for canonical in (root / "schemas/v1").glob("*.json"):
        expected = canonical.read_bytes()
        assert (package / "schemas/v1" / canonical.name).read_bytes() == expected
        assert (internal / "schemas/v1" / canonical.name).read_bytes() == expected
        checked += 2
    for folder in ("documentation", "assistance", "coding", "decision"):
        for canonical in (root / "plugin-src/shared" / folder).iterdir():
            if not canonical.is_file():
                continue
            expected = canonical.read_bytes()
            if (
                os.name == "nt"
                and folder in {"documentation", "decision"}
                and canonical.name.startswith("guide.")
            ):
                expected = expected.replace(b"bin/launch.sh", b"node bin/launch.mjs")
            assert (
                package / "skills/opensocrates/references" / folder / canonical.name
            ).read_bytes() == expected
            checked += 1
            if folder == "documentation":
                assert (
                    internal / "plugin-src/shared/documentation" / canonical.name
                ).read_bytes() == canonical.read_bytes()
                checked += 1
    return {
        "status": "pass",
        "checked_members": checked,
        "languages": ["en", "ko"],
        "stateless_no_memory": True,
        "prepared_read_only": True,
        "scoped_recall_and_delete": True,
        "decision_prepare_and_recovery": True,
        "rejected_request_preserves_availability": True,
        "task_verification": task_verification,
        "model_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    binary_source = parser.add_mutually_exclusive_group(required=True)
    binary_source.add_argument("--binary", type=Path)
    binary_source.add_argument("--runtime-report", type=Path)
    parser.add_argument("--package", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary
    if args.runtime_report:
        report = json.loads(args.runtime_report.read_text(encoding="utf-8"))
        binary = Path(__file__).resolve().parents[1] / report["artifact"]
    print(json.dumps(check(binary.resolve(), args.package.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
