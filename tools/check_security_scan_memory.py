#!/usr/bin/env python3
"""Pin the narrow local-Git/SQLite scanner exception against regressions."""

from __future__ import annotations

import ast

from security_scan import _call_findings


def findings(source: str, path: str) -> dict[str, int]:
    return _call_findings(ast.parse(source), path)


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


if __name__ == "__main__":
    main()
