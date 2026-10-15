"""Loopback-only, authenticated browser interface for the office evaluation lab."""

from __future__ import annotations

import hmac
import json
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .engine import Lab
from .model import LabError

_ASSETS = Path(__file__).with_name("assets")
_MAX_REQUEST = 262144
_ACTIONS = frozenset(
    {
        "snapshot",
        "create",
        "prepare",
        "preflight",
        "start",
        "monitor",
        "preview",
        "finish",
        "retry",
        "packet",
        "judge",
        "reveal",
        "freeze",
        "export",
    }
)
_STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/review": ("index.html", "text/html; charset=utf-8"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/assets/style.css": ("style.css", "text/css; charset=utf-8"),
}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, lab: Lab, port: int) -> None:
        self.lab = lab
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), _Handler)
        self.expected_host = f"127.0.0.1:{self.server_address[1]}"
        self.origin = f"http://{self.expected_host}"

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Never write request data, local paths or exception text to a log."""


class _Handler(BaseHTTPRequestHandler):
    server: _Server
    server_version = "OfficeLab"
    sys_version = ""

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, format: str, *args: Any) -> None:
        """Request logging is deliberately disabled."""

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'none'; object-src 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: dict[str, Any]) -> None:
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _error(self, status: int, code: str) -> None:
        self.close_connection = True
        self._json(status, {"error": code})

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        """Replace the standard raw request-bearing error document."""
        self._error(code, "http_request_rejected")

    def _same_site(self) -> bool:
        hosts = self.headers.get_all("Host", [])
        origins = self.headers.get_all("Origin", [])
        fetch_site = self.headers.get("Sec-Fetch-Site", "")
        return (
            hosts == [self.server.expected_host]
            and (not origins or origins == [self.server.origin])
            and fetch_site in {"", "none", "same-origin"}
        )

    def do_GET(self) -> None:
        if not self._same_site():
            self._error(403, "origin_rejected")
            return
        route = self.path.split("?", 1)[0]
        asset = _STATIC.get(route)
        if asset is None:
            self._error(404, "route_unknown")
            return
        try:
            body = (_ASSETS / asset[0]).read_bytes()
        except OSError:
            self._error(503, "ui_unavailable")
            return
        self._send(200, body, asset[1])

    def _authorized(self) -> bool:
        auth = self.headers.get_all("Authorization", [])
        expected = f"Bearer {self.server.token}"
        return len(auth) == 1 and auth[0].isascii() and hmac.compare_digest(auth[0], expected)

    def _read_request(self) -> dict[str, Any]:
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
            raise ValueError
        length = int(lengths[0])
        if not 0 < length <= _MAX_REQUEST:
            raise ValueError
        if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Encoding"):
            raise ValueError
        if self.headers.get_all("Content-Type", []) != ["application/json"]:
            raise ValueError
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError
        parsed: Any = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        if not isinstance(parsed, dict) or set(parsed) != {"action", "data"}:
            raise ValueError
        if parsed["action"] not in _ACTIONS or not isinstance(parsed["data"], dict):
            raise ValueError
        return parsed

    def do_POST(self) -> None:
        if not self._same_site() or not self._authorized():
            self._error(403, "request_rejected")
            return
        if self.path != "/api":
            self._error(404, "route_unknown")
            return
        try:
            request = self._read_request()
        except (ValueError, TypeError, UnicodeError, OSError, RecursionError):
            self._error(400, "invalid_request")
            return
        self._dispatch(request)

    def _dispatch(self, request: dict[str, Any]) -> None:
        try:
            if request["action"] == "snapshot":
                if request["data"]:
                    raise ValueError
                result = self.server.lab.snapshot()
            else:
                result = self.server.lab.action(request["action"], request["data"])
        except LabError as error:
            self._json(400, {"error": error.code})
        except (ValueError, TypeError):
            self._json(400, {"error": "invalid_request"})
        except Exception:
            self._json(500, {"error": "operation_unavailable"})
        else:
            self._json(200, {"result": result})


def serve(
    root: Path,
    pack: Path,
    payloads: Path | None = None,
    *,
    open_browser: bool = True,
    port: int = 0,
) -> None:
    """Serve only this lab; the URL fragment never enters HTTP request logs."""
    lab = Lab(root, pack, payloads)
    with _Server(lab, port) as server:
        url = f"{server.origin}/#token={server.token}"
        print("Office evaluation lab is running locally. Close with Ctrl+C.")
        if open_browser:
            try:
                opened = webbrowser.open(url)
            except Exception:
                opened = False
            if not opened:
                print("Open this private local URL in your browser:")
                print(url)
        else:
            print(url)
        try:
            server.serve_forever(poll_interval=0.3)
        except KeyboardInterrupt:
            pass
