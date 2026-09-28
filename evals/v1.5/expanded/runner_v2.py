"""Run committed expanded pilot cells; retain synthetic artifacts, never reasoning."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from uuid import uuid4

from harness_v3 import HERE, digest, invoke, native_counts, profile, save_new, verify_freeze

sys.path.insert(0, str(HERE.parent))
from native_plugin_runner import build_marketplace as legacy_marketplace  # noqa: E402


def build_marketplace(freeze: dict, base: Path) -> Path:
    marketplace = legacy_marketplace(freeze, base)
    # zipfile.extractall preserves bytes, not Unix executable modes. The runtime
    # must be executable before the CLI copies this local marketplace package.
    with zipfile.ZipFile(freeze["candidate_zip"]["path"]) as archive:
        for member in archive.infolist():
            if not member.is_dir():
                path = safe_path(marketplace / "plugin", member.filename)
                path.chmod(0o755 if (member.external_attr >> 16) & 0o111 else 0o644)
    return marketplace


def safe_path(workspace: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("Unsafe fixture path")
    current = workspace
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Linked fixture path")
    if not current.resolve().is_relative_to(workspace.resolve()):
        raise ValueError("Escaped fixture path")
    return current


def files(workspace: Path, contents: dict[str, str] | None) -> None:
    for name, content in (contents or {}).items():
        path = safe_path(workspace, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)


def setup_command(
    command: list[str],
    env: dict[str, str],
    receipt: Path,
    *,
    payload: dict | None = None,
    cwd: Path | None = None,
) -> tuple[dict, dict]:
    save_new(receipt.with_suffix(".started.json"), {"attempt_status": "started"})
    started = time.monotonic()
    result: dict[str, Any] = {"exit_code": None, "status": None, "error": None}
    value: dict[str, Any] = {}
    try:
        proc = subprocess.run(
            command,
            input=json.dumps(payload) if payload else None,
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd,
            timeout=90,
            check=False,
        )
        result["exit_code"] = proc.returncode
        result["stdout_sha256"] = digest(proc.stdout)
        value = json.loads(proc.stdout)
        result["status"] = value.get("status")
        result["limitations"] = value.get("limitations")
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        result["error"] = type(error).__name__
    result["wall_seconds"] = round(time.monotonic() - started, 3)
    save_new(receipt, result)
    return result, value


def install_or_check(
    freeze: dict, env: dict, marketplace: Path, plugin: bool, output: Path
) -> dict:
    receipts = []
    if plugin:
        for operation, arguments in (
            ("marketplace", ["plugin", "marketplace", "add", str(marketplace), "--json"]),
            ("install", ["plugin", "add", "opensocrates@os-eval", "--json"]),
        ):
            receipt, _ = setup_command(
                [freeze["client"]["path"], *arguments], env, output / f"setup-{operation}.json"
            )
            receipts.append(receipt)
            if receipt["exit_code"] != 0 or receipt["error"]:
                return {"ok": False, "operations": receipts}
    receipt, value = setup_command(
        [freeze["client"]["path"], "plugin", "list", "--json"], env, output / "setup-inventory.json"
    )
    matches = [
        {key: item.get(key) for key in ("pluginId", "version", "installed", "enabled")}
        for item in value.get("installed", [])
        if item.get("name") == "opensocrates"
    ]
    expected = (
        [
            {
                "pluginId": "opensocrates@os-eval",
                "version": "1.4.0",
                "installed": True,
                "enabled": True,
            }
        ]
        if plugin
        else []
    )
    return {
        "ok": receipt["exit_code"] == 0 and matches == expected,
        "operations": receipts,
        "inventory": matches,
    }


def installed_root(codex: Path) -> Path:
    matches = list(codex.glob("plugins/cache/**/skills/opensocrates/SKILL.md"))
    if len(matches) != 1:
        raise RuntimeError("Installed skill identity is ambiguous")
    return matches[0].parents[2]


def member_check(root: Path, expected: dict[str, str]) -> dict[str, Any]:
    actual = {name: digest((root / name).read_bytes()) for name in expected}
    executable = os.access(root / "bin/launch.sh", os.X_OK) and os.access(
        root / "runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime", os.X_OK
    )
    return {
        "all_match": actual == expected and executable,
        "hashes": actual,
        "launcher_and_runtime_executable": executable,
    }


def memory_seed(
    package: Path, workspace: Path, env: dict[str, str], summary: str, output: Path
) -> dict[str, Any]:
    """Seed only one attributed synthetic public decision before source transition."""
    receipts = []

    def call(
        operation: str, payload: dict, project: str | None = None, worktree: str | None = None
    ) -> dict:
        request = {
            "schema": "opensocrates.project-memory.request/1.0.0",
            "operation": operation,
            "request_id": str(uuid4()),
            "project_id": project,
            "workspace_id": worktree,
            "task_id": None,
            "payload": payload,
        }
        receipt, response = setup_command(
            ["bash", str(package / "bin/launch.sh"), "memory", "codex"],
            env,
            output / f"seed-{len(receipts) + 1}-{operation}.json",
            payload=request,
            cwd=workspace,
        )
        receipts.append({"operation": operation, **receipt})
        if receipt["exit_code"] != 0 or response.get("status") != "ok":
            raise RuntimeError(
                f"Seed {operation}: {response.get('status')} {response.get('limitations')}"
            )
        return response["result"]

    policy = {
        "root": str(workspace),
        "apply": False,
        "mode": "read_write",
        "capture_policy": "milestones",
        "excluded_paths": [],
    }
    preview = call("init", policy)
    policy.update(
        {
            "apply": True,
            "disclosure_digest": preview["disclosure_digest"],
            "authorization_basis": "fixture:expanded-v2-enrollment",
            "authorization_attribution": "operator_declared",
            "idempotency_key": str(uuid4()),
        }
    )
    enrolled = call("init", policy)
    project, worktree = enrolled["project_id"], enrolled["workspace_id"]
    created = call(
        "record",
        {
            "idempotency_key": str(uuid4()),
            "expected_record_version": 0,
            "kind": "decision",
            "scope": {"level": "project"},
            "summary": summary,
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
        project,
        worktree,
    )
    call(
        "accept",
        {
            "record_id": created["record"]["record_id"],
            "expected_record_version": 1,
            "idempotency_key": str(uuid4()),
            "acceptance_basis": "fixture:expanded-v2-frozen-intent",
            "acceptance_attribution": "operator_declared",
        },
        project,
        worktree,
    )
    return {
        "project_id": project,
        "workspace_id": worktree,
        "operations": receipts,
        "summary_sha256": digest(summary),
        "source_refs_attached": False,
    }


def public_text(text: str, base: Path) -> str:
    value = text.replace(str(base), "<disposable>")
    # Public synthetic artifacts may contain paths to their disposable files.
    value = re.sub(r"/(?:private/)?(?:tmp|var/folders)/[^\s`\"')]+", "<disposable-path>", value)
    if re.search(r"sk-[A-Za-z0-9_-]{10,}|eyJ[A-Za-z0-9_-]{30,}\.", value):
        raise ValueError("Credential-like output rejected from evaluation retention")
    return value


def retain_stage(task: dict, workspace: Path, final: str, base: Path) -> dict:
    artifacts = {}
    for name in task["artifact_paths"]:
        path = safe_path(workspace, name)
        if not path.exists():
            artifacts[name] = None
        elif path.is_symlink() or path.stat().st_size > 131072:
            raise ValueError("Unsafe or oversized evaluation artifact")
        else:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
                artifacts[name] = public_text(stream.read(131073), base)
    return {"artifacts": artifacts, "public_final": public_text(final, base)}


def task_prompt(
    freeze: dict, task: dict, cell: dict, seed: dict | None, followup: bool = False
) -> str:
    language = task["locale"]
    parts = [freeze["common_prompt"][language]]
    if cell["plugin"]:
        # EVAL03 varies only this separately frozen optional wrapper, not hook access.
        parts.append(freeze["skill_prompt"][language])
    if cell.get("wrapper"):
        parts.append(freeze["optional_wrapper"][language])
    if cell.get("memory"):
        assert seed is not None
        parts.append(
            freeze["recall_prompt"][language].format(
                project_id=seed["project_id"], workspace_id=seed["workspace_id"]
            )
        )
    elif cell.get("note"):
        parts.append(freeze["note_prompt"][language])
    continuation = task["lane"] in {"EVAL-01", "EVAL-04"}
    parts.append(task["followup_prompt"] if followup or continuation else task["prompt"])
    return "\n\n".join(parts)


def run_cell(freeze: dict, task: dict, cell: dict, marketplace: Path, output: Path) -> dict:  # noqa: C901
    from checks_v2 import evaluate

    cell_output = output / cell["id"]
    cell_output.mkdir(parents=True, exist_ok=False)
    result: dict[str, Any] = {
        "cell": cell,
        "task": task["id"],
        "lane": task["lane"],
        "locale": task["locale"],
        "held_out": False,
        "quality_judge": None,
        "calls": [],
        "stages": [],
    }
    save_new(cell_output / "cell.started.json", result)
    wall = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="os-v15-expanded-v2-", dir="/private/tmp") as temporary:
        base = Path(temporary)
        workspace, data = base / "workspace", base / "data"
        workspace.mkdir(mode=0o700)
        data.mkdir(mode=0o700)
        codex = base / "profile/home/.codex"
        try:
            codex, env = profile(base / "profile")
            files(workspace, task["files"])
            files(workspace, task.get("replay_files"))
            if task["kind"] == "coding" or task["lane"] == "EVAL-01":
                for command in (
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
                        "frozen source",
                    ],
                ):
                    subprocess.run(command, cwd=workspace, env=env, check=True, capture_output=True)
            result["initial_source_hashes"] = {
                name: digest((workspace / name).read_bytes())
                for name in dict.fromkeys([*task["files"], *(task.get("replay_files") or {})])
            }
            result["installation"] = install_or_check(
                freeze, env, marketplace, cell["plugin"], cell_output
            )
            save_new(cell_output / "installation.json", result["installation"])
            if not result["installation"]["ok"]:
                raise RuntimeError("Disposable installation failed")
            package = installed_root(codex) if cell["plugin"] else None
            if package:
                result["installed_bytes"] = member_check(package, freeze["package_members"])
                if not result["installed_bytes"]["all_match"]:
                    raise RuntimeError("Installed package byte drift")
            seed = None
            if cell.get("memory"):
                env.update(
                    {
                        "OPENSOCRATES_MEMORY_FIXTURE": "1",
                        "OPENSOCRATES_DEVELOPMENT_MANIFEST": "1",
                        "OPENSOCRATES_DATA_DIR": str(data),
                    }
                )
                seed = memory_seed(package, workspace, env, task["accepted_decision"], cell_output)
                result["memory_seed"] = {
                    key: value
                    for key, value in seed.items()
                    if key not in {"project_id", "workspace_id"}
                }
                save_new(cell_output / "memory-seed.json", result["memory_seed"])
            if cell.get("note"):
                start = time.monotonic()
                (workspace / "PROJECT_NOTES.md").write_text(
                    task["maintained_note"], encoding="utf-8"
                )
                result["note_setup"] = {
                    "wall_seconds": round(time.monotonic() - start, 6),
                    "bytes": len(task["maintained_note"].encode()),
                    "maintenance": "Operator-seeded frozen note; human authoring burden unmeasured",
                }
            continuity = task["lane"] in {"EVAL-01", "EVAL-04"}
            if continuity:
                files(workspace, task["source_transition"])
            result["source_hashes_before_call"] = {
                name: digest((workspace / name).read_bytes())
                for name in dict.fromkeys(
                    [
                        *task["files"],
                        *(task.get("replay_files") or {}),
                        *((task["source_transition"] or {}) if continuity else {}),
                    ]
                )
            }
            dialogue = task["lane"] == "EVAL-05"
            turns = 2 if dialogue and task.get("followup_prompt") else 1
            for turn in range(turns):
                if turn:
                    files(workspace, task["source_transition"])
                receipt, final = invoke(
                    client=freeze["client"]["path"],
                    workspace=workspace,
                    env=env,
                    model=cell["model"],
                    prompt=task_prompt(freeze, task, cell, seed, followup=bool(turn)),
                    receipt=cell_output / f"turn-{turn + 1}.json",
                    timeout=freeze["limits"]["per_turn_seconds"],
                    resume=bool(turn),
                    ephemeral=not dialogue,
                    hooks=cell.get("hooks", False),
                    extra_dir=data,
                )
                result["calls"].append(f"turn-{turn + 1}.json")
                stage = retain_stage(task, workspace, final, base)
                save_new(cell_output / f"artifact-{turn + 1}.json", stage)
                result["stages"].append(f"artifact-{turn + 1}.json")
                # A failed initial call remains recorded; no repair or substitute is injected.
                if not receipt["process_success"]:
                    break
            if task["lane"] == "H02":
                value = json.loads((workspace / "plan.json").read_text())
                checks = {
                    "accepted_activity": value.get("welcome_activity") == "silent_paper_reflection",
                    "current_attendance": value.get("attendees") == 18,
                    "current_capacity": value.get("capacity") == 24,
                }
                result["grade"] = {
                    "checks": checks,
                    "all_pass": all(checks.values()),
                    "critical_failures": [key for key, ok in checks.items() if not ok],
                }
            else:
                result["grade"] = evaluate(task, workspace, final)
            result["all_calls_completed"] = len(result["calls"]) == turns and all(
                json.loads((cell_output / name).read_text())["process_success"]
                for name in result["calls"]
            )
            result["deterministic_success"] = (
                result["all_calls_completed"] and result["grade"]["all_pass"]
            )
        except Exception as error:
            result["runner_error"] = type(error).__name__
            result["runner_error_detail"] = public_text(str(error), base)[:500]
            result["deterministic_success"] = False
            # Reconcile persisted receipts even if capture or grading failed afterward.
            result["calls"] = sorted(
                path.name
                for path in cell_output.glob("turn-*.json")
                if not path.name.endswith("started.json")
            )
        finally:
            result["native_tables"] = native_counts(codex)
            (codex / "auth.json").unlink(missing_ok=True)
            result["auth_copy_removed"] = not (codex / "auth.json").exists()
            result["wall_including_setup_seconds"] = round(time.monotonic() - wall, 3)
            result["account_side_memory_isolation"] = (
                "unverified; memory-effect comparisons confounded"
            )
            save_new(cell_output / "result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell", help="One scheduled cell; otherwise run each unstarted cell")
    args = parser.parse_args()
    freeze, commit = verify_freeze(HERE / "execution-freeze.v2.json")
    tasks = {
        task["id"]: task for task in json.loads((HERE / "fixtures.v2.json").read_text())["tasks"]
    }
    host_task = json.loads((HERE / "host-fixture.v2.json").read_text())
    tasks[host_task["id"]] = host_task
    output = HERE / "results-v2"
    output.mkdir(exist_ok=True)
    schedule = [cell for cell in freeze["cells"] if not args.cell or cell["id"] == args.cell]
    if args.cell and not schedule:
        raise SystemExit("Unknown frozen cell")
    schedule = [cell for cell in schedule if not (output / cell["id"]).exists()]
    with tempfile.TemporaryDirectory(prefix="os-v15-expanded-market-") as temporary:
        marketplace = build_marketplace(freeze, Path(temporary))
        with ThreadPoolExecutor(max_workers=freeze["limits"]["max_parallel_cells"]) as pool:
            futures = {
                pool.submit(run_cell, freeze, tasks[cell["task"]], cell, marketplace, output): cell
                for cell in schedule
            }
            for future in as_completed(futures):
                result = future.result()
                print(
                    f"{result['cell']['id']}: success={result['deterministic_success']} error={result.get('runner_error')}",
                    flush=True,
                )
    print(f"Freeze commit: {commit}; results: {output}")


if __name__ == "__main__":
    main()
