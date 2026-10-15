#!/usr/bin/env python3
"""Exercise the local office-lab HTTP trust boundary without actor calls."""

from __future__ import annotations

import argparse
import contextlib
import http.client
import io
import json
import re
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

_CHECKS = 0
_SECRET = "PRIVATE-REQUEST-MUST-NOT-BE-LOGGED"


def _require(condition: bool, message: str) -> None:
    global _CHECKS
    if not condition:
        raise AssertionError(message)
    _CHECKS += 1


class _LabFixture:
    """Transport fixture: engine behavior is covered separately, no real study."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def snapshot(self) -> dict[str, Any]:
        return {"initialized": False, "runs": []}

    def action(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        from opensocrates.evaluation.model import LabError

        self.calls.append((name, data))
        if name == "monitor":
            raise RuntimeError(_SECRET)
        if name == "prepare":
            raise LabError("run_unknown")
        return {"accepted": name}


@contextlib.contextmanager
def _running() -> Iterator[tuple[Any, _LabFixture]]:
    from opensocrates.evaluation.server import _Server

    fixture = _LabFixture()
    with _Server(fixture, 0) as server:  # type: ignore[arg-type]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server, fixture
        finally:
            server.shutdown()
            thread.join(timeout=5)
            _require(not thread.is_alive(), "HTTP fixture did not stop")


def _request(
    server: Any,
    method: str,
    path: str,
    *,
    body: bytes = b"",
    headers: list[tuple[str, str]] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    try:
        connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for name, value in headers if headers is not None else [("Host", server.expected_host)]:
            connection.putheader(name, value)
        connection.putheader("Connection", "close")
        connection.endheaders(body)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def _api(
    server: Any,
    value: Any,
    *,
    extra: list[tuple[str, str]] | None = None,
    auth: bool = True,
    content_type: str = "application/json",
    path: str = "/api",
) -> tuple[int, dict[str, str], bytes]:
    body = json.dumps(value, ensure_ascii=False).encode("utf-8")
    headers = [
        ("Host", server.expected_host),
        ("Origin", server.origin),
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
    ]
    if auth:
        headers.append(("Authorization", "Bearer " + server.token))
    headers.extend(extra or [])
    return _request(server, "POST", path, body=body, headers=headers)


def _check_static(server: Any, root: Path) -> None:
    status, headers, body = _request(server, "GET", "/")
    _require(status == 200 and b"<html" in body.lower(), "local UI unavailable")
    _require(server.token.encode() not in body, "launch token embedded in static HTML")
    _require(headers.get("Cache-Control") == "no-store", "UI caching is enabled")
    _require(headers.get("X-Content-Type-Options") == "nosniff", "MIME sniffing is enabled")
    csp = headers.get("Content-Security-Policy", "")
    _require("default-src 'none'" in csp and "unsafe-inline" not in csp, "unsafe CSP")
    for route in (
        "/state.json",
        "/.office-lab",
        "/actors/private/out/final.md",
        "/exports/study.json",
        "/assets/../server.py",
        "/assets/%2e%2e/server.py",
        "/%2e%2e/AGENTS.md",
        "/../../etc/passwd",
        "/src/opensocrates/evaluation/server.py",
        "/api",
    ):
        status, _, data = _request(server, "GET", route)
        _require(status == 404, "non-allowlisted static path exposed")
        _require(route.encode() not in data, "error reflects a requested filesystem path")
    app = (root / "src/opensocrates/evaluation/assets/app.js").read_text(encoding="utf-8")
    _require("textContent" in app, "final-answer text rendering not present")
    _require(
        re.search(r"\b(innerHTML|outerHTML|insertAdjacentHTML|eval)\b|document\.write", app)
        is None,
        "UI contains executable HTML insertion for imported answers",
    )
    _require(
        re.search(r"<script[^>]+src=[\"']https?://", body.decode(), re.I) is None,
        "UI loads a remote script",
    )


def _check_site_boundary(server: Any) -> None:
    for additions in (
        [("Host", "evil.invalid")],
        [("Host", "127.0.0.1")],
        [("Host", "localhost:" + str(server.server_address[1]))],
        [("Host", server.expected_host), ("Origin", "https://evil.invalid")],
        [("Host", server.expected_host), ("Origin", "null")],
        [("Host", server.expected_host), ("Origin", server.origin), ("Origin", server.origin)],
        [("Host", server.expected_host), ("Host", server.expected_host)],
        [("Host", server.expected_host), ("Sec-Fetch-Site", "cross-site")],
    ):
        status, _, _ = _request(server, "GET", "/", headers=additions)
        _require(status == 403, "hostile or ambiguous site header accepted")
    request = {"action": "start", "data": {"run_id": "opaque-test-run"}}
    _require(_api(server, request, auth=False)[0] == 403, "unauthenticated action accepted")
    _require(
        _api(server, request, extra=[("Authorization", "Bearer invalid")])[0] == 403,
        "duplicate/invalid authorization accepted",
    )
    _require(
        _api(server, request, extra=[("Origin", "https://evil.invalid")])[0] == 403,
        "cross-origin authenticated action accepted",
    )


def _check_actions(server: Any, fixture: _LabFixture) -> None:
    request = {"action": "start", "data": {"run_id": "opaque-test-run"}}
    status, _, body = _api(server, request)
    _require(
        status == 200 and json.loads(body)["result"]["accepted"] == "start",
        "valid start not delegated",
    )
    _require(fixture.calls[-1] == ("start", request["data"]), "action payload altered")
    status, _, body = _api(server, {"action": "snapshot", "data": {}})
    _require(status == 200 and not json.loads(body)["result"]["initialized"], "snapshot failed")
    calls = len(fixture.calls)
    for malformed in (
        [],
        {"action": "shell", "data": {}},
        {"action": "__class__", "data": {}},
        {"action": "start", "data": [], "private": _SECRET},
        {"action": "start", "data": {}, "private": _SECRET},
        {"action": "snapshot", "data": {"path": _SECRET}},
    ):
        status, _, body = _api(server, malformed)
        _require(
            status == 400 and _SECRET.encode() not in body, "malformed action accepted/reflected"
        )
    _require(len(fixture.calls) == calls, "invalid request reached engine")
    _require(_api(server, request, content_type="text/plain")[0] == 400, "non-JSON action accepted")
    _require(
        _api(server, request, path="/api/../state.json")[0] == 404,
        "alternate action route accepted",
    )
    status, _, body = _api(server, {"action": "prepare", "data": {}})
    _require(
        status == 400 and json.loads(body) == {"error": "run_unknown"},
        "public engine error changed",
    )
    status, _, body = _api(server, {"action": "monitor", "data": {}})
    _require(
        status == 500 and json.loads(body) == {"error": "operation_unavailable"},
        "raw exception exposed",
    )


def _check_body_limits(server: Any) -> None:
    base = [("Host", server.expected_host), ("Authorization", "Bearer " + server.token)]
    for fields, body in (
        ([("Content-Type", "application/json"), ("Content-Length", "262145")], b""),
        ([("Content-Type", "application/json"), ("Content-Length", "-1")], b""),
        ([("Content-Type", "application/json"), ("Content-Length", "0")], b""),
        ([("Content-Type", "application/json")], b""),
        (
            [
                ("Content-Type", "application/json"),
                ("Content-Length", "2"),
                ("Content-Length", "2"),
            ],
            b"{}",
        ),
        (
            [
                ("Content-Type", "application/json"),
                ("Content-Length", "2"),
                ("Transfer-Encoding", "chunked"),
            ],
            b"{}",
        ),
        (
            [
                ("Content-Type", "application/json"),
                ("Content-Length", "2"),
                ("Content-Encoding", "gzip"),
            ],
            b"{}",
        ),
        ([("Content-Type", "application/json"), ("Content-Length", "1")], b"\xff"),
        ([("Content-Type", "application/json"), ("Content-Length", "1")], b"{"),
    ):
        status, _, response = _request(server, "POST", "/api", body=body, headers=base + fields)
        _require(
            status == 400 and response == b'{"error": "invalid_request"}',
            "invalid body framing accepted",
        )


def check(root: Path) -> int:
    global _CHECKS
    _CHECKS = 0
    sys.path.insert(0, str(root / "src"))
    logs = io.StringIO()
    with (
        contextlib.redirect_stdout(logs),
        contextlib.redirect_stderr(logs),
        _running() as (server, fixture),
    ):
        _require(server.server_address[0] == "127.0.0.1", "server listens beyond loopback")
        _check_static(server, root)
        _check_site_boundary(server)
        _check_actions(server, fixture)
        _check_body_limits(server)
    _require(not logs.getvalue(), "server writes request/exception logs")
    print(f"Office lab HTTP: {_CHECKS} checks passed (synthetic transport; no host/model calls).")
    return _CHECKS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    check(args.root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
