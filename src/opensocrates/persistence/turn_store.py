"""Content-free HMAC-addressed ephemeral cross-process turn state."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
from pathlib import Path
from threading import RLock

from opensocrates.constants import MAX_EPHEMERAL_TURN_STATE_BYTES
from opensocrates.domain.models import EphemeralTurnState
from opensocrates.domain.validation import canonical_json, model_from_json, validate_model
from opensocrates.errors import OpenSocratesError
from opensocrates.ids import validate_sha256, validate_timestamp, validate_turn_token

from ..verification.secret_filter import reject_forbidden_keys, reject_secrets
from .atomic import AtomicWriteError, atomic_replace_bytes, read_bytes
from .locks import FileLock, LockPolicy, LockTimeoutError
from .paths import DataRoot, DataRootLayout, secure_join
from .permissions import PermissionManager


class TurnStoreError(OSError):
    """Raised when ephemeral state cannot be safely loaded or updated."""


class TurnStateConflict(TurnStoreError):
    """Raised when compare-and-swap observes a different state."""


def token_tag_for(raw_token: str, installation_key: bytes) -> str:
    """Derive a domain-separated SHA-256 HMAC tag without retaining the token."""

    try:
        validate_turn_token(raw_token)
    except (OpenSocratesError, ValueError) as error:
        raise TurnStoreError("invalid turn token") from error
    if len(installation_key) != 32:
        raise TurnStoreError("installation key must be 256 bits")
    message = b"turn-token\0" + len(raw_token).to_bytes(4, "big") + raw_token.encode("ascii")
    return "sha256:" + hmac.new(installation_key, message, hashlib.sha256).hexdigest()


def _state_bytes(state: EphemeralTurnState) -> bytes:
    if not isinstance(state, EphemeralTurnState):
        raise TypeError("turn store accepts EphemeralTurnState only")
    try:
        validate_model(state)
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise TurnStoreError("ephemeral turn state is invalid") from error
    value = state.to_dict()
    reject_forbidden_keys(value)
    reject_secrets(value)
    encoded = canonical_json(value).encode("utf-8")
    if len(encoded) > MAX_EPHEMERAL_TURN_STATE_BYTES:
        raise TurnStoreError("ephemeral turn state exceeds 64 KiB")
    return encoded


def _parse_state(data: bytes) -> EphemeralTurnState:
    if len(data) > MAX_EPHEMERAL_TURN_STATE_BYTES:
        raise TurnStoreError("ephemeral turn state exceeds 64 KiB")
    try:
        decoded = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TurnStoreError("ephemeral turn state is not valid JSON") from error
    reject_forbidden_keys(decoded)
    reject_secrets(decoded)
    try:
        state = model_from_json(EphemeralTurnState, data)
        validate_model(state)
        return state  # type: ignore[no-any-return]  # Closed runtime boundary validates this value.
    except (OpenSocratesError, TypeError, ValueError, UnicodeError) as error:
        raise TurnStoreError("ephemeral turn state is invalid") from error


def _same_state(left: EphemeralTurnState, right: EphemeralTurnState) -> bool:
    return canonical_json(left) == canonical_json(right)


class _InstallationKey:
    def __init__(self, layout: DataRootLayout, permissions: PermissionManager) -> None:
        self.path = secure_join(layout.root, "installation.key")
        root_report = permissions.root_report(layout.root)
        if not root_report.write_allowed:
            raise TurnStoreError("installation key unavailable under current permissions")
        self.value = self._load_or_create()

    def _load_or_create(self) -> bytes:
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            info = None
        except OSError as error:
            raise TurnStoreError("installation key cannot be inspected") from error
        if info is not None:
            if stat.S_ISLNK(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
                raise TurnStoreError("installation key permissions are unsafe")
            try:
                value = read_bytes(self.path, max_bytes=32)
            except (AtomicWriteError, OSError) as error:
                raise TurnStoreError("installation key cannot be read") from error
            if len(value) != 32:
                raise TurnStoreError("installation key has invalid length")
            return value
        value = secrets.token_bytes(32)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(self.path, flags, 0o600)
            try:
                os.write(fd, value)
                os.fsync(fd)
            finally:
                os.close(fd)
        except FileExistsError:
            return self._load_or_create()
        except OSError as error:
            raise TurnStoreError("installation key cannot be created") from error
        return value


class TurnStateStore:
    """Owner-only atomic store addressed exclusively by HMAC token tags."""

    def __init__(
        self,
        data_root: DataRoot | DataRootLayout,
        *,
        installation_key: bytes | None = None,
        lock_policy: LockPolicy | None = None,
        permission_manager: PermissionManager | None = None,
    ) -> None:
        self.layout = data_root.layout if isinstance(data_root, DataRoot) else data_root
        self.permissions = permission_manager or PermissionManager()
        self.lock_policy = lock_policy or LockPolicy()
        self.installation_key = (
            installation_key or _InstallationKey(self.layout, self.permissions).value
        )

    def _path(self, token_tag: str) -> Path:
        try:
            validate_sha256(token_tag)
            return self.layout.turn_state(token_tag)
        except (OpenSocratesError, ValueError) as error:
            raise TurnStoreError("invalid turn token tag") from error

    def _lock_path(self, token_tag: str) -> Path:
        try:
            validate_sha256(token_tag)
            return self.layout.turn_lock(token_tag)
        except (OpenSocratesError, ValueError) as error:
            raise TurnStoreError("invalid turn token tag") from error

    def _write(self, state: EphemeralTurnState) -> None:
        path = self._path(state.token_tag)
        try:
            atomic_replace_bytes(path, _state_bytes(state))
        except AtomicWriteError as error:
            raise TurnStoreError("turn state atomic write failed") from error

    def issue(self, state: EphemeralTurnState) -> None:
        _state_bytes(state)
        self.layout.turns_dir.mkdir(mode=0o700, exist_ok=True)
        root_report = self.permissions.root_report(self.layout.root)
        turns_report = self.permissions.root_report(self.layout.turns_dir)
        if not root_report.write_allowed or not turns_report.write_allowed:
            raise TurnStoreError("turn state writes disabled by permissions")
        path = self._path(state.token_tag)
        try:
            with FileLock(self._lock_path(state.token_tag), policy=self.lock_policy):
                if path.exists():
                    raise TurnStateConflict("turn state already exists")
                self._write(state)
        except LockTimeoutError as error:
            raise TurnStoreError("turn state lock timeout") from error

    def load_by_raw_token(self, raw_token: str) -> EphemeralTurnState | None:
        try:
            tag = token_tag_for(raw_token, self.installation_key)
        except TurnStoreError:
            return None
        path = self._path(tag)
        try:
            data = read_bytes(path, max_bytes=MAX_EPHEMERAL_TURN_STATE_BYTES)
        except FileNotFoundError:
            return None
        except AtomicWriteError as error:
            raise TurnStoreError("turn state cannot be read") from error
        state = _parse_state(data)
        if state.token_tag != tag:
            raise TurnStoreError("turn state tag mismatch")
        return state

    def compare_and_swap(
        self, expected: EphemeralTurnState, replacement: EphemeralTurnState
    ) -> None:
        _state_bytes(expected)
        _state_bytes(replacement)
        if expected.token_tag != replacement.token_tag:
            raise TurnStateConflict("turn state tag cannot change")
        path = self._path(expected.token_tag)
        try:
            with FileLock(self._lock_path(expected.token_tag), policy=self.lock_policy):
                try:
                    current = _parse_state(
                        read_bytes(path, max_bytes=MAX_EPHEMERAL_TURN_STATE_BYTES)
                    )
                except FileNotFoundError as error:
                    raise TurnStateConflict("turn state is missing") from error
                if not _same_state(current, expected):
                    raise TurnStateConflict("turn state compare-and-swap mismatch")
                self._write(replacement)
        except LockTimeoutError as error:
            raise TurnStoreError("turn state lock timeout") from error

    def delete(self, state: EphemeralTurnState) -> None:
        _state_bytes(state)
        path = self._path(state.token_tag)
        try:
            with FileLock(self._lock_path(state.token_tag), policy=self.lock_policy):
                try:
                    info = path.lstat()
                except FileNotFoundError:
                    return
                if stat.S_ISLNK(info.st_mode):
                    raise TurnStoreError("turn state path may not be a symlink")
                path.unlink()
        except LockTimeoutError as error:
            raise TurnStoreError("turn state lock timeout") from error

    def sweep_expired(self, now: str) -> int:
        try:
            validate_timestamp(now)
        except (OpenSocratesError, ValueError) as error:
            raise TurnStoreError("invalid sweep timestamp") from error
        deleted = 0
        try:
            paths = tuple(self.layout.turns_dir.glob("*.json"))
        except OSError:
            return 0
        for path in paths:
            try:
                state = _parse_state(read_bytes(path, max_bytes=MAX_EPHEMERAL_TURN_STATE_BYTES))
            except (FileNotFoundError, TurnStoreError, AtomicWriteError):
                continue
            if state.expires_at <= now:
                self.delete(state)
                deleted += 1
        return deleted


class InMemoryTurnStore:
    """Content-free in-memory equivalent for focused process-boundary demos."""

    def __init__(self, installation_key: bytes | None = None) -> None:
        self.installation_key = installation_key or secrets.token_bytes(32)
        if len(self.installation_key) != 32:
            raise TurnStoreError("installation key must be 256 bits")
        self._states: dict[str, EphemeralTurnState] = {}
        self._lock = RLock()

    def issue(self, state: EphemeralTurnState) -> None:
        _state_bytes(state)
        with self._lock:
            if state.token_tag in self._states:
                raise TurnStateConflict("turn state already exists")
            self._states[state.token_tag] = state

    def load_by_raw_token(self, raw_token: str) -> EphemeralTurnState | None:
        try:
            tag = token_tag_for(raw_token, self.installation_key)
        except TurnStoreError:
            return None
        with self._lock:
            return self._states.get(tag)

    def compare_and_swap(
        self, expected: EphemeralTurnState, replacement: EphemeralTurnState
    ) -> None:
        _state_bytes(expected)
        _state_bytes(replacement)
        if expected.token_tag != replacement.token_tag:
            raise TurnStateConflict("turn state tag cannot change")
        with self._lock:
            current = self._states.get(expected.token_tag)
            if current is None or not _same_state(current, expected):
                raise TurnStateConflict("turn state compare-and-swap mismatch")
            self._states[expected.token_tag] = replacement

    def delete(self, state: EphemeralTurnState) -> None:
        _state_bytes(state)
        with self._lock:
            self._states.pop(state.token_tag, None)

    def sweep_expired(self, now: str) -> int:
        try:
            validate_timestamp(now)
        except (OpenSocratesError, ValueError) as error:
            raise TurnStoreError("invalid sweep timestamp") from error
        with self._lock:
            expired = tuple(tag for tag, state in self._states.items() if state.expires_at <= now)
            for tag in expired:
                del self._states[tag]
            return len(expired)


__all__ = [
    "TurnStoreError",
    "TurnStateConflict",
    "token_tag_for",
    "TurnStateStore",
    "InMemoryTurnStore",
]
