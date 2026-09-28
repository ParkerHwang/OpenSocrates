"""Bounded synthetic evaluation I/O; never persist raw model event streams."""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import sqlite3
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CLIENT = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
AUTH = Path.home() / ".codex" / "auth.json"
USAGE_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def save_new(path: Path, value: Any) -> None:
    """Exclusive creation prevents an accidental rerun from replacing evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def profile(base: Path) -> tuple[Path, dict[str, str]]:
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    home, temporary = base / "home", base / "tmp"
    home.mkdir(mode=0o700)
    temporary.mkdir(mode=0o700)
    codex = home / ".codex"
    codex.mkdir(mode=0o700)
    descriptor = os.open(codex / "auth.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as target:
        target.write(AUTH.read_bytes())
    # No inherited API credential, project configuration, or plugin environment.
    env = {
        key: os.environ[key]
        for key in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT")
        if key in os.environ
    }
    env.update({"HOME": str(home), "CODEX_HOME": str(codex), "TMPDIR": str(temporary)})
    return codex, env


def json_values(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    values = []
    for match in re.finditer(r"(?m)^\s*\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start() :].lstrip())
        except ValueError:
            continue
        if isinstance(value, dict):
            values.append(value)
    return values


def summarize(raw: str) -> tuple[dict[str, Any], str]:  # noqa: C901
    usage = {key: None for key in USAGE_KEYS}
    usage_reports = []
    events, malformed, messages, errors = [], 0, [], []
    started: dict[str, dict[str, Any]] = {}
    completed: dict[str, dict[str, Any]] = {}
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            malformed += 1
            continue
        if not isinstance(event, dict):
            malformed += 1
            continue
        events.append(event)
        kind = event.get("type")
        if kind == "turn.completed":
            reported = event.get("usage") or {}
            for key in dict.fromkeys([*USAGE_KEYS, *reported]):
                value = reported.get(key)
                usage[key] = (
                    value if isinstance(value, int) and not isinstance(value, bool) else None
                )
            usage_reports.append(dict(usage))
        if kind in {"turn.failed", "error"}:
            errors.append(kind)
        item = event.get("item") or {}
        if item.get("type") == "agent_message" and kind == "item.completed":
            messages.append(item.get("text", ""))
        if item.get("type") in {"command_execution", "file_change", "mcp_tool_call", "web_search"}:
            identifier = str(item.get("id", len(started)))
            if kind == "item.started":
                started[identifier] = item
            if kind == "item.completed":
                completed[identifier] = item
    receipts = []
    for identifier in dict.fromkeys([*started, *completed]):
        item = {**started.get(identifier, {}), **completed.get(identifier, {})}
        command = item.get("command", "")
        operations = re.findall(
            r"(?:launch\.(?:sh|mjs)[\"']?\s+|python\S*\s+-m\s+opensocrates\s+)(memory|assistance|decision)\b",
            command,
        )
        responses = []
        for value in json_values(item.get("aggregated_output") or ""):
            schema = value.get("schema", "")
            if isinstance(schema, str) and schema.startswith("opensocrates."):
                result = value.get("result") or {}
                responses.append(
                    {
                        "schema": schema,
                        "status": value.get("status"),
                        "delivery": result.get("delivery"),
                        "application": result.get("application"),
                        "used_bytes": result.get("used_bytes"),
                    }
                )
        receipts.append(
            {
                "type": item.get("type"),
                "completed": identifier in completed,
                "command_sha256": digest(command) if command else None,
                "exit_code": item.get("exit_code"),
                "status": item.get("status"),
                "direct_operations_lexical": operations,
                "structured_responses": responses,
                "source_scan_heuristic": bool(
                    re.search(r"\b(?:rg|grep|find|cat|sed|ls)\b", command)
                ),
            }
        )
    operation_counts = Counter(op for item in receipts for op in item["direct_operations_lexical"])
    statuses = Counter(
        response["status"]
        for item in receipts
        for response in item["structured_responses"]
        if isinstance(response["status"], str)
    )
    command_hashes = [item["command_sha256"] for item in receipts if item["command_sha256"]]
    return (
        {
            "event_count": len(events),
            "malformed_lines": malformed,
            "usage": usage,
            "usage_reports": usage_reports,
            "turn_completed": any(item.get("type") == "turn.completed" for item in events),
            "errors": errors,
            "tool_actions": receipts,
            "tool_actions_started_or_completed": len(receipts),
            "failed_tool_actions": sum(
                item["exit_code"] not in (0, None) or item["status"] == "failed"
                for item in receipts
            ),
            "incomplete_tool_actions": sum(not item["completed"] for item in receipts),
            "direct_operations_lexical": dict(operation_counts),
            "structured_status_counts": dict(statuses),
            "protocol_rejections": sum(
                statuses[name]
                for name in (
                    "invalid_request",
                    "unavailable",
                    "busy",
                    "conflict",
                    "budget_insufficient",
                )
            ),
            "repeated_command_hashes": sum(count - 1 for count in Counter(command_hashes).values()),
            "native_hook_events": sum("hook" in str(item.get("type", "")) for item in events),
            "final_message_sha256": digest(messages[-1]) if messages else None,
            "public_message_count": len(messages),
            "billed_cost": None,
            "server_echoed_model": None,
            "tool_classification_limit": "Lexical direct calls and structured responses; nested invocations may be missed. Repeated hash does not itself prove unnecessary work.",
        },
        messages[-1] if messages else "",
    )


def native_counts(codex: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"database_present": False, "stage1_outputs": None, "jobs": None}
    databases = list(codex.glob("memories*.sqlite"))
    if not databases:
        return result
    result["database_present"] = True
    try:
        with sqlite3.connect(f"file:{databases[0]}?mode=ro", uri=True) as connection:
            for table in ("stage1_outputs", "jobs"):
                result[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.Error as error:
        result["read_error"] = type(error).__name__
    return result


def invoke(  # noqa: C901  # Failure paths remain explicit in the immutable receipt harness.
    *,
    client: str,
    workspace: Path,
    env: dict[str, str],
    model: str,
    prompt: str,
    receipt: Path,
    timeout: int = 300,
    resume: bool = False,
    ephemeral: bool = True,
    hooks: bool = False,
    extra_dir: Path | None = None,
) -> tuple[dict[str, Any], str]:
    command = [client, "exec"]
    if resume:
        command += [
            "resume",
            "--last",
            "--skip-git-repo-check",
            "-c",
            'sandbox_mode="workspace-write"',
        ]
    else:
        command += ["--sandbox", "workspace-write", "--skip-git-repo-check", "-C", str(workspace)]
        if ephemeral:
            command.append("--ephemeral")
        if extra_dir:
            command += ["--add-dir", str(extra_dir)]
    command += [
        "--json",
        "--disable",
        "multi_agent",
        "--disable",
        "memories",
        "--disable",
        "external_agent_memory_import",
        "-c",
        "memories.use_memories=false",
        "-c",
        "memories.generate_memories=false",
        "-m",
        model,
        "-c",
        'model_reasoning_effort="medium"',
    ]
    command += ["--dangerously-bypass-hook-trust"] if hooks else ["--disable", "hooks"]
    command.append("-")
    before = {
        "requested_model": model,
        "requested_effort": "medium",
        "prompt_sha256": digest(prompt),
        "resume": resume,
        "ephemeral": ephemeral,
        "hooks": hooks,
        "native_memory_use": False,
        "native_memory_generate": False,
        "attempt_status": "started",
        "started_unix": time.time(),
    }
    save_new(receipt.with_suffix(".started.json"), before)
    started = time.monotonic()
    process = None
    stdout = stderr = ""
    invocation_error = None
    timed_out = False
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=workspace,
            env=env,
            start_new_session=True,
        )
        stdout, stderr = process.communicate(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        assert process is not None
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired as error:
                invocation_error = "post_kill_pipe_timeout"
                stdout = (
                    error.stdout.decode(errors="replace")
                    if isinstance(error.stdout, bytes)
                    else error.stdout or ""
                )
                stderr = (
                    error.stderr.decode(errors="replace")
                    if isinstance(error.stderr, bytes)
                    else error.stderr or ""
                )
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream:
                        stream.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    invocation_error = "post_kill_reap_timeout"
    except OSError as error:
        invocation_error = type(error).__name__
    try:
        summary, final = summarize(stdout)
    except (ValueError, TypeError, AttributeError) as error:
        summary, final = summarize("")
        invocation_error = "event_parser_" + type(error).__name__
    exit_code = process.returncode if process is not None else None
    result = {
        **before,
        "attempt_status": "completed",
        "exit_code": exit_code,
        "invocation_error": invocation_error,
        "timed_out": timed_out,
        "wall_seconds": round(time.monotonic() - started, 3),
        "stderr_sha256": digest(stderr) if stderr else None,
        **summary,
    }
    result["process_success"] = (
        exit_code == 0
        and invocation_error is None
        and not timed_out
        and summary["turn_completed"]
        and not summary["errors"]
    )
    save_new(receipt, result)  # Persist before grading; scorer exceptions cannot erase calls.
    return result, final


def verify_freeze(path: Path) -> tuple[dict[str, Any], str]:
    relative = str(path.relative_to(ROOT))
    committed = subprocess.run(
        ["git", "show", f"HEAD:{relative}"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    if committed != path.read_bytes():
        raise RuntimeError("Freeze is not committed or changed")
    freeze = json.loads(committed)
    for name, expected in freeze["file_hashes"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise RuntimeError(f"Frozen file drift: {name}")
    if digest(Path(freeze["client"]["path"]).read_bytes()) != freeze["client"]["sha256"]:
        raise RuntimeError("Client drift")
    freeze_commit = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", relative],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return freeze, freeze_commit


def selftest() -> None:
    events = [
        {
            "type": "item.completed",
            "item": {
                "id": "a",
                "type": "command_execution",
                "command": "cat /tmp/opensocrates/guide.md",
                "exit_code": 0,
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "b",
                "type": "command_execution",
                "command": "'/plugin/bin/launch.sh' memory codex",
                "exit_code": 0,
                "aggregated_output": '{"schema":"opensocrates.project-memory.response/1.0.0","status":"invalid_request"}',
            },
        },
        {
            "type": "item.started",
            "item": {"id": "c", "type": "command_execution", "command": "sleep 30"},
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 10, "cached_input_tokens": 5, "output_tokens": 2},
        },
    ]
    result, _ = summarize("\n".join(json.dumps(event) for event in events))
    assert result["direct_operations_lexical"] == {"memory": 1}
    assert result["incomplete_tool_actions"] == 1
    assert result["usage"]["reasoning_output_tokens"] is None
    memory = next(item for item in result["tool_actions"] if item["direct_operations_lexical"])
    assert memory["structured_responses"][0]["status"] == "invalid_request"
    assert result["protocol_rejections"] == 1
    merged, _ = summarize(
        "\n".join(
            json.dumps(value)
            for value in [
                {
                    "type": "item.started",
                    "item": {
                        "id": "x",
                        "type": "command_execution",
                        "command": "node /p/bin/launch.mjs memory codex",
                    },
                },
                {
                    "type": "item.completed",
                    "item": {"id": "x", "type": "command_execution", "exit_code": 0},
                },
            ]
        )
    )
    assert merged["direct_operations_lexical"] == {"memory": 1}
    print("harness-v3-selftest: PASS")


if __name__ == "__main__":
    selftest()
