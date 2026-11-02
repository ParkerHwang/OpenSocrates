"""Authenticated local byte transport with a separate, deny-by-default policy seam.

This module opens no TCP listener and uses no pickle serialization. Connection
details must be passed transiently through a trusted integration. Their possession
authenticates a member of that local channel, not a desktop conversation or a
user's task authority. Claimed sender/recipient references remain untrusted until
the configured authorizer binds them using evidence outside this transport.

Only the ephemeral Unix socket entry (or Windows named pipe) is created. No key,
message, response, address manifest or diagnostic log is written by this module.
Callers and injected callbacks must independently follow the retention policy.
Accept/connect and I/O already in progress are not forcibly cancellable;
``timeout`` bounds initial incoming-frame readiness, not completion of a frame
from a peer that stalls after writing only part of it. A hosting process must
account for that limitation rather than treating this as an untrusted public
endpoint. In particular, this module is not a denial-of-service isolation layer.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from multiprocessing.connection import Client, Connection, Listener
from pathlib import Path
from threading import Lock
from typing import Literal, cast

Family = Literal["AF_UNIX", "AF_PIPE"]
_REF = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_PIPE = re.compile(r"\\\\\.\\pipe\\opensocrates-[0-9a-f]{48}\Z")
_MAGIC = b"OS2-local-channel-v1:"
_FRAME_LIMIT = 64 * 1024


class AuthorizationDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    UNKNOWN = "unknown"


class ChannelStatus(StrEnum):
    HANDLED = "handled"
    DENIED = "denied"
    AUTHORITY_UNKNOWN = "authority_unknown"
    INVALID_REQUEST = "invalid_request"
    UNAVAILABLE = "unavailable"
    EFFECT_UNKNOWN = "effect_unknown"


class LocalChannelError(RuntimeError):
    """A fixed error code without paths, keys, bodies or callback exception text."""

    def __init__(self, code: Literal["invalid_configuration", "channel_unavailable"]) -> None:
        safe_code = code if code in ("invalid_configuration", "channel_unavailable") else "invalid_configuration"
        super().__init__(safe_code)


@dataclass(frozen=True, slots=True, repr=False)
class ConnectionDetails:
    """Transient capability; do not serialize it to logs, arguments or files."""

    address: str = field(repr=False)
    family: Family = field(repr=False)
    authkey: bytes = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class ChannelMessage:
    message_id: str
    task_ref: str
    sender_ref: str
    recipient_ref: str
    authority_ref: str
    body: bytes = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class AuthorizationRequest:
    """References are claims, not proof supplied by the HMAC handshake."""

    message_id: str
    task_ref: str
    sender_ref: str
    recipient_ref: str
    authority_ref: str


@dataclass(frozen=True, slots=True, repr=False)
class ChannelResult:
    status: ChannelStatus
    body: bytes = field(default=b"", repr=False)


Authorizer = Callable[[AuthorizationRequest], AuthorizationDecision]
Handler = Callable[[ChannelMessage], bytes]


def _deny(_request: AuthorizationRequest) -> AuthorizationDecision:
    return AuthorizationDecision.DENY


def _valid_ref(value: object) -> bool:
    return isinstance(value, str) and _REF.fullmatch(value) is not None


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("invalid_frame")
        result[key] = value
    return result


def _json_frame(value: dict[str, object], limit: int) -> bytes:
    frame = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(frame) > limit:
        raise ValueError("frame_too_large")
    return frame


def _read_frame(connection: Connection, timeout: float, limit: int) -> bytes:
    if not connection.poll(timeout):
        raise TimeoutError("frame_timeout")
    return connection.recv_bytes(maxlength=limit)


def _load_frame(frame: bytes) -> dict[str, object]:
    value: object = json.loads(frame.decode("utf-8"), object_pairs_hook=_pairs)
    if not isinstance(value, dict):
        raise ValueError("invalid_frame")
    return cast(dict[str, object], value)


def _body(value: object) -> bytes:
    if not isinstance(value, str):
        raise ValueError("invalid_frame")
    return base64.b64decode(value, validate=True)


def _message_frame(message: ChannelMessage, limit: int) -> bytes:
    refs = (
        message.message_id,
        message.task_ref,
        message.sender_ref,
        message.recipient_ref,
        message.authority_ref,
    )
    if (
        not all(_valid_ref(ref) for ref in refs)
        or type(message.body) is not bytes
        or len(message.body) > limit
    ):
        raise ValueError("invalid_frame")
    return _json_frame(
        {
            "version": 1,
            "message_id": message.message_id,
            "task_ref": message.task_ref,
            "sender_ref": message.sender_ref,
            "recipient_ref": message.recipient_ref,
            "authority_ref": message.authority_ref,
            "body": base64.b64encode(message.body).decode("ascii"),
        },
        limit,
    )


def _decode_message(frame: bytes) -> ChannelMessage:
    value = _load_frame(frame)
    names = ("message_id", "task_ref", "sender_ref", "recipient_ref", "authority_ref")
    if (
        set(value) != {"version", *names, "body"}
        or type(value["version"]) is not int
        or value["version"] != 1
        or not all(_valid_ref(value[name]) for name in names)
    ):
        raise ValueError("invalid_frame")
    return ChannelMessage(
        *(cast(str, value[name]) for name in names),
        body=_body(value["body"]),
    )


def _proof(key: bytes, side: bytes, nonce: bytes) -> bytes:
    return hmac.new(key, _MAGIC + side + nonce, hashlib.sha256).digest()


def _server_auth(connection: Connection, key: bytes, timeout: float) -> None:
    nonce = secrets.token_bytes(32)
    connection.send_bytes(_MAGIC + nonce)
    response = _read_frame(connection, timeout, 32)
    if not hmac.compare_digest(response, _proof(key, b"client", nonce)):
        raise ValueError("authentication_failed")
    connection.send_bytes(_proof(key, b"server", nonce))


def _client_auth(connection: Connection, key: bytes, timeout: float) -> None:
    challenge = _read_frame(connection, timeout, len(_MAGIC) + 32)
    if len(challenge) != len(_MAGIC) + 32 or not challenge.startswith(_MAGIC):
        raise ValueError("authentication_failed")
    nonce = challenge[len(_MAGIC) :]
    connection.send_bytes(_proof(key, b"client", nonce))
    response = _read_frame(connection, timeout, 32)
    if not hmac.compare_digest(response, _proof(key, b"server", nonce)):
        raise ValueError("authentication_failed")


class LocalChannel:
    """One-request-per-connection local server with no default delivery grant.

    ``serve_once`` accepts a connection synchronously. A hosting process must
    arrange its own worker/lifecycle; closing does not promise interruption of an
    accept, write or handler already running. HANDLED means the injected local
    handler returned, not host receipt, model reading or application.
    """

    def __init__(
        self,
        *,
        authorizer: Authorizer = _deny,
        timeout: float = 2.0,
        max_frame_bytes: int = _FRAME_LIMIT,
    ) -> None:
        if (
            not callable(authorizer)
            or isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 0 < timeout <= 60
            or type(max_frame_bytes) is not int
            or not 512 <= max_frame_bytes <= _FRAME_LIMIT
        ):
            raise LocalChannelError("invalid_configuration")
        self._authorizer = authorizer
        self._timeout = float(timeout)
        self._limit = max_frame_bytes
        self._key = secrets.token_bytes(32)
        self._directory: tempfile.TemporaryDirectory[str] | None = None
        self._closed = False
        self._serving = Lock()
        family: Family = "AF_PIPE" if os.name == "nt" else "AF_UNIX"
        try:
            if family == "AF_PIPE":
                address = "\\\\.\\pipe\\opensocrates-" + secrets.token_hex(24)
            else:
                self._directory = tempfile.TemporaryDirectory(prefix="os2-", dir="/tmp")
                root = Path(self._directory.name)
                if root.stat().st_mode & 0o077:
                    raise OSError("private_directory_unavailable")
                address = str(root / "channel.sock")
            self._listener = Listener(address, family=family, authkey=None)
            self._details = ConnectionDetails(address, family, self._key)
        except Exception:
            if self._directory is not None:
                try:
                    self._directory.cleanup()
                except OSError:
                    pass
            raise LocalChannelError("channel_unavailable") from None

    def __repr__(self) -> str:
        return "LocalChannel(closed=" + str(self._closed) + ")"

    def connection_details(self) -> ConnectionDetails:
        if self._closed:
            raise LocalChannelError("channel_unavailable")
        return self._details

    def serve_once(self, handler: Handler) -> ChannelStatus:
        """Accept/authenticate one local connection, then authorize its request."""
        if self._closed or not callable(handler):
            return ChannelStatus.UNAVAILABLE
        if not self._serving.acquire(blocking=False):
            return ChannelStatus.UNAVAILABLE
        connection: Connection | None = None
        effect_may_exist = False
        try:
            connection = self._listener.accept()
            _server_auth(connection, self._key, self._timeout)
            try:
                message = _decode_message(_read_frame(connection, self._timeout, self._limit))
            except (ValueError, UnicodeError, binascii.Error, RecursionError):
                return self._respond(connection, "", ChannelResult(ChannelStatus.INVALID_REQUEST))
            result = self._handle(message, handler)
            effect_may_exist = result.status in (
                ChannelStatus.HANDLED,
                ChannelStatus.EFFECT_UNKNOWN,
            )
            return self._respond(connection, message.message_id, result)
        except Exception:
            return ChannelStatus.EFFECT_UNKNOWN if effect_may_exist else ChannelStatus.UNAVAILABLE
        finally:
            if connection is not None:
                _close_connection(connection)
            self._serving.release()

    def _handle(self, message: ChannelMessage, handler: Handler) -> ChannelResult:
        request = AuthorizationRequest(
            message.message_id,
            message.task_ref,
            message.sender_ref,
            message.recipient_ref,
            message.authority_ref,
        )
        try:
            decision = self._authorizer(request)
        except Exception:
            return ChannelResult(ChannelStatus.AUTHORITY_UNKNOWN)
        if decision is AuthorizationDecision.DENY:
            return ChannelResult(ChannelStatus.DENIED)
        if decision is not AuthorizationDecision.ALLOW:
            return ChannelResult(ChannelStatus.AUTHORITY_UNKNOWN)
        try:
            response = handler(message)
            if type(response) is not bytes:
                return ChannelResult(ChannelStatus.EFFECT_UNKNOWN)
            result = ChannelResult(ChannelStatus.HANDLED, response)
            _response_frame(message.message_id, result, self._limit)
            return result
        except Exception:
            return ChannelResult(ChannelStatus.EFFECT_UNKNOWN)

    def _respond(
        self, connection: Connection, message_id: str, result: ChannelResult
    ) -> ChannelStatus:
        connection.send_bytes(_response_frame(message_id, result, self._limit))
        return result.status

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._listener.close()
        except OSError:
            pass
        finally:
            self._key = b""
            self._details = ConnectionDetails("", self._details.family, b"")
            if self._directory is not None:
                try:
                    self._directory.cleanup()
                except OSError:
                    pass

    def __enter__(self) -> LocalChannel:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _response_frame(message_id: str, result: ChannelResult, limit: int) -> bytes:
    if type(result.body) is not bytes or len(result.body) > limit:
        raise ValueError("frame_too_large")
    return _json_frame(
        {
            "version": 1,
            "message_id": message_id,
            "status": result.status.value,
            "body": base64.b64encode(result.body).decode("ascii"),
        },
        limit,
    )


def request(
    details: ConnectionDetails,
    message: ChannelMessage,
    *,
    timeout: float = 2.0,
    max_frame_bytes: int = _FRAME_LIMIT,
) -> ChannelResult:
    """Send once; an absent result after sending is an unknown external effect.

    Never retries automatically. The shared channel key does not establish the
    claimed sender, recipient, task authority or any real app-conversation ID.
    """
    if (
        not isinstance(details, ConnectionDetails)
        or not isinstance(message, ChannelMessage)
        or isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not 0 < timeout <= 60
        or type(max_frame_bytes) is not int
        or not 512 <= max_frame_bytes <= _FRAME_LIMIT
        or details.family not in ("AF_UNIX", "AF_PIPE")
        or not isinstance(details.address, str)
        or (details.family == "AF_PIPE" and _PIPE.fullmatch(details.address) is None)
        or type(details.authkey) is not bytes
        or len(details.authkey) != 32
    ):
        return ChannelResult(ChannelStatus.INVALID_REQUEST)
    try:
        frame = _message_frame(message, max_frame_bytes)
    except (ValueError, TypeError):
        return ChannelResult(ChannelStatus.INVALID_REQUEST)
    connection: Connection | None = None
    sent = False
    try:
        connection = Client(details.address, family=details.family, authkey=None)
        _client_auth(connection, details.authkey, float(timeout))
        sent = True
        connection.send_bytes(frame)
        response = _load_frame(_read_frame(connection, float(timeout), max_frame_bytes))
        if (
            set(response) != {"version", "message_id", "status", "body"}
            or type(response["version"]) is not int
            or response["version"] != 1
            or response["message_id"] != message.message_id
            or not isinstance(response["status"], str)
        ):
            raise ValueError("invalid_frame")
        return ChannelResult(ChannelStatus(response["status"]), _body(response["body"]))
    except Exception:
        status = ChannelStatus.EFFECT_UNKNOWN if sent else ChannelStatus.UNAVAILABLE
        return ChannelResult(status)
    finally:
        if connection is not None:
            _close_connection(connection)


def _close_connection(connection: Connection) -> None:
    try:
        connection.close()
    except OSError:
        pass


__all__ = [
    "AuthorizationDecision",
    "AuthorizationRequest",
    "ChannelMessage",
    "ChannelResult",
    "ChannelStatus",
    "ConnectionDetails",
    "LocalChannel",
    "LocalChannelError",
    "request",
]
