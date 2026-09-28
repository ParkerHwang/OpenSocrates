#!/usr/bin/env python3
"""Pin reviewed Git, SQLite and orchestration scanner boundaries against mutations."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from opensocrates.orchestration.adapter import CodexAdapter, _hashed_process
from opensocrates.orchestration.paths import BoundaryError
from security_scan import _call_findings, _reviewed_ast_bytes


def findings(source: str, path: str) -> dict[str, int]:
    return _call_findings(ast.parse(source), path)


def check_canonical_ast() -> None:
    # One common syntax fixture pins the same representation under supported
    # Python 3.12 and newer diagnostic interpreters, without ast.dump defaults.
    tree = ast.parse('def sample():\n    return emit(b"public", value=None, shell=False)\n')
    canonical = _reviewed_ast_bytes(tree)
    fingerprint = hashlib.sha256(canonical).hexdigest()
    assert fingerprint == "a0756e88eed082b540ade80490f721cca88e364eef7bb8d01e1a3735ff4ac920"
    ast.increment_lineno(tree, 20)
    assert _reviewed_ast_bytes(tree) == canonical
    projected = json.loads(canonical)
    function = projected["fields"]["body"][0]
    assert function["fields"]["decorator_list"] == []
    assert function["fields"]["type_params"] == []
    call = function["fields"]["body"][0]["fields"]["value"]
    assert call["fields"]["args"][0]["fields"]["value"] == {"bytes": "7075626c6963"}
    assert call["fields"]["keywords"][0]["fields"]["value"]["fields"]["value"] is None
    assert call["fields"]["keywords"][1]["fields"]["value"]["fields"]["value"] is False
    for left, right in (
        ("emit(0)", "emit(False)"),
        ("emit(b'x')", "emit('x')"),
        ("emit(None)", "emit([])"),
        ("emit(shell=False)", "emit()"),
    ):
        assert _reviewed_ast_bytes(ast.parse(left)) != _reviewed_ast_bytes(ast.parse(right))
    print("canonical reviewed AST: PASS (location-free, complete typed syntax fields)")


def check_orchestration_exception() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "src/opensocrates/orchestration/adapter.py"
    ).read_text()
    boundary = "orchestration/adapter.py"
    assert findings(source, boundary)["shell_execution"] == 0
    assert findings(source, "application/other.py")["shell_execution"] == 5
    mutations = [
        ("shell=False", "shell=True"),
        ("shell=False", "shell=caller_setting"),
        ("shell=False", "**caller_kwargs"),
        ("shell=False,", ""),
        ("[str(self.client), *args]", '"raw command; touch forbidden"'),
        ("self._argv(assignment, cwd, output),", '["/bin/sh", "-c", assignment["objective"]],'),
        ('[str(client), "sandbox", "-P", ":read-only", "-C", str(cwd), "--", *argv]', "argv"),
        ('":read-only"', '":workspace-write"'),
        ('"read-only",', '"danger-full-access",'),
        ('"--ephemeral",', '"--worktree",'),
        ('"--ignore-user-config",', '"--dangerously-bypass-approvals-and-sandbox",'),
        ('"project_doc_max_bytes=0"', '"project_doc_max_bytes=32768"'),
        ('approval_policy="never"', 'approval_policy="on-request"'),
        ('"allow_login_shell=false"', '"allow_login_shell=true"'),
        ('"memories",', '"unrelated_feature",'),
        ('"multi_agent",', '"unrelated_feature",'),
        ("env=_role_environment()", "env=os.environ.copy()"),
        ('"CODEX_HOME": str(scratch)', '"CODEX_HOME": os.environ["CODEX_HOME"]'),
        ('"RUST_LOG": "off"', '"RUST_LOG": "debug"'),
        (
            '_hashed_process(self.client, check["argv"], cwd, env)',
            '_hashed_process(self.client, check["raw_command"], cwd, env)',
        ),
        ("self._probe_sandbox()", "None"),
        ('raise BoundaryError("unapproved_capability_probe")', "pass"),
        ("import subprocess", "import subprocess as sp"),
        ("import subprocess", "from subprocess import Popen"),
    ]
    for before, after in mutations:
        assert before in source, before
        changed = source.replace(before, after, 1)
        assert findings(changed, boundary)["shell_execution"] > 0, before
    additions = [
        '\nsubprocess.run(["/bin/sh", "-c", "touch forbidden"], shell=False)\n',
        '\ndef unapproved():\n    subprocess.Popen(["/bin/echo", "side effect"], shell=False)\n',
        "\ndef unapproved():\n    return _hashed_process(client, unapproved_argv, cwd, env)\n",
        '\nspawn = subprocess.Popen\nspawn(["/bin/sh", "-c", "touch forbidden"])\n',
        '\nsetattr(subprocess, "run", untrusted_runner)\n',
        "\nsubprocess = replacement\n",
        '\nos.system("touch forbidden")\n',
        "\nDISABLED_FEATURES = ()\n",
    ]
    for addition in additions:
        assert findings(source + addition, boundary)["shell_execution"] > 0, addition
    assert findings(source + "\neval(payload)\n", boundary)["dynamic_execution"] > 0
    assert findings(source + "\npickle.loads(payload)\n", boundary)["unsafe_deserialization"] > 0
    assert findings(source + "\nsocket.connect(address)\n", boundary)["network_calls"] > 0
    # Harmless formatting/comment changes do not require new policy identities.
    assert findings("# audit note\n" + source, boundary)["shell_execution"] == 0
    print(
        f"orchestration subprocess security boundary: PASS ({len(mutations) + len(additions)} rejecting mutations)"
    )


def check_adapter_guards() -> None:
    with patch("opensocrates.orchestration.adapter.subprocess.run") as run:
        try:
            CodexAdapter("/fixture/codex")._inspect(["exec", "unapproved prompt"])
        except BoundaryError:
            pass
        else:
            raise AssertionError("unapproved capability probe was allowed")
        run.assert_not_called()

    class Process:
        stdout = io.BytesIO(b"bounded stdout")
        stderr = io.BytesIO(b"")
        returncode = 0

        def wait(self):
            return 0

        def poll(self):
            return 0

    with patch(
        "opensocrates.orchestration.adapter.subprocess.Popen", return_value=Process()
    ) as popen:
        result = _hashed_process(
            Path("/fixture/codex"),
            ["/bin/echo", "literal; no shell expansion"],
            Path("/fixture/candidate"),
            {"HOME": "/fixture/empty"},
        )
    assert result["exit_code"] == 0
    argv = popen.call_args.args[0]
    assert argv == [
        "/fixture/codex",
        "sandbox",
        "-P",
        ":read-only",
        "-C",
        "/fixture/candidate",
        "--",
        "/bin/echo",
        "literal; no shell expansion",
    ]
    assert popen.call_args.kwargs["shell"] is False
    assert popen.call_args.kwargs["stdin"] == subprocess.DEVNULL
    assert "stdout" not in result and "stderr" not in result
    print("orchestration process adapter guards: PASS (mocked processes; no model calls)")


def main() -> None:
    git = 'import subprocess\ndef run_git():\n    subprocess.run([binary, "-C", "/fixture", "status"], check=False)\n'
    assert findings(git, "project_memory/git.py")["shell_execution"] == 0
    assert findings(git, "application/other.py")["shell_execution"] == 1
    unsafe = (
        'import subprocess\ndef run_git():\n    subprocess.run([binary, "status"], shell=True)\n'
    )
    assert findings(unsafe, "project_memory/git.py")["shell_execution"] == 1
    sqlite = "import sqlite3\nsqlite3.connect('file:fixture?mode=ro')\n"
    assert findings(sqlite, "project_memory/store.py")["network_calls"] == 0
    socket = "import socket\nsocket.connect(('example.com', 443))\n"
    assert findings(socket, "project_memory/store.py")["network_calls"] == 1
    print("memory security-scan exceptions: PASS")
    check_canonical_ast()
    check_orchestration_exception()
    check_adapter_guards()


if __name__ == "__main__":
    main()
