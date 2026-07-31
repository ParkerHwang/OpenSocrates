"""Atomic typed UserSettings persistence and an in-memory equivalent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Callable

from opensocrates.domain.enums import InterventionClass
from opensocrates.domain.models import InterventionPreference, UserSettings
from opensocrates.domain.validation import model_from_json, validate_model
from opensocrates.errors import OpenSocratesError

from .atomic import AtomicWriteError, atomic_replace_bytes, read_bytes
from .locks import FileLock, LockPolicy, LockTimeoutError
from .paths import DataRoot, DataRootLayout, secure_join
from .permissions import PermissionManager


class SettingsStoreError(OSError):
    """Raised when settings cannot be safely persisted."""


@dataclass(frozen=True, slots=True)
class SettingsReadStatus:
    used_default: bool
    error_code: str | None = None


def default_settings() -> UserSettings:
    """Return fresh-install settings with recording disabled until disclosure."""

    preferences = {member.value: InterventionPreference() for member in InterventionClass}
    return UserSettings(intervention_preferences=preferences)


class SettingsStore:
    """Owner-only atomic settings file with revision monotonicity."""

    def __init__(
        self,
        data_root: DataRoot | DataRootLayout,
        *,
        lock_policy: LockPolicy | None = None,
        permission_manager: PermissionManager | None = None,
    ) -> None:
        self.layout = data_root.layout if isinstance(data_root, DataRoot) else data_root
        self.lock_policy = lock_policy or LockPolicy()
        self.permissions = permission_manager or PermissionManager()
        self._last_status = SettingsReadStatus(False)

    @property
    def last_status(self) -> SettingsReadStatus:
        return self._last_status

    def _lock_path(self) -> Path:
        return secure_join(self.layout.root, "settings.lock")

    def _decode(self, data: bytes) -> UserSettings:
        if not data:
            raise SettingsStoreError("settings file is empty")
        try:
            value = model_from_json(UserSettings, data)
            validate_model(value)
            return value  # type: ignore[no-any-return]  # Closed runtime boundary validates this value.
        except (OpenSocratesError, TypeError, ValueError, OSError) as error:
            raise SettingsStoreError("settings file is invalid") from error

    def load(self) -> UserSettings:
        """Load validated settings or use an in-memory safe default."""

        try:
            data = read_bytes(self.layout.settings_file, max_bytes=128 * 1024)
        except FileNotFoundError:
            self._last_status = SettingsReadStatus(True, "missing")
            return default_settings()
        except AtomicWriteError:
            self._last_status = SettingsReadStatus(True, "unreadable")
            return default_settings()
        try:
            value = self._decode(data)
        except SettingsStoreError:
            self._last_status = SettingsReadStatus(True, "invalid")
            return default_settings()
        self._last_status = SettingsReadStatus(False)
        return value

    def save(self, settings: UserSettings) -> None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        if not isinstance(settings, UserSettings):
            raise TypeError("settings repository accepts UserSettings only")
        try:
            validate_model(settings)
        except (OpenSocratesError, TypeError, ValueError) as error:
            raise SettingsStoreError("settings value is invalid") from error
        root_report = self.permissions.root_report(self.layout.root)
        if not root_report.write_allowed:
            raise SettingsStoreError("settings writes disabled by data-root permissions")
        existing = self.load()
        if self.layout.settings_file.exists():
            file_report = self.permissions.file_report(self.layout.settings_file)
            if not file_report.write_allowed:
                raise SettingsStoreError("settings file permissions disable writes")
            if settings.revision <= existing.revision:
                raise SettingsStoreError("settings revision must increase")
        elif settings.revision < 1:
            raise SettingsStoreError("settings revision must be positive")
        try:
            encoded = settings.to_json().encode("utf-8")
            with FileLock(self._lock_path(), policy=self.lock_policy):
                # Re-read under the lock to close the revision race.
                current = self.load()
                if self.layout.settings_file.exists() and settings.revision <= current.revision:
                    raise SettingsStoreError("settings revision must increase")
                atomic_replace_bytes(self.layout.settings_file, encoded)
        except LockTimeoutError as error:
            raise SettingsStoreError("settings lock timeout") from error
        except AtomicWriteError as error:
            raise SettingsStoreError("settings atomic write failed") from error

    def mutate(self, transform: Callable[[UserSettings], UserSettings]) -> UserSettings:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        """Commit one revision from a lock-held, current settings snapshot.

        The transform runs only after the settings lock is acquired and the
        current file has been re-read.  A failed transform, no-op revision, or
        invalid returned model reaches no atomic-write call, so the prior file
        remains byte-for-byte unchanged.
        """

        if not callable(transform):
            raise TypeError("settings transform must be callable")
        root_report = self.permissions.root_report(self.layout.root)
        if not root_report.write_allowed:
            raise SettingsStoreError("settings writes disabled by data-root permissions")
        try:
            with FileLock(self._lock_path(), policy=self.lock_policy):
                locked_root_report = self.permissions.root_report(self.layout.root)
                if not locked_root_report.write_allowed:
                    raise SettingsStoreError("settings writes disabled by data-root permissions")
                current = self.load()
                if self.layout.settings_file.exists():
                    file_report = self.permissions.file_report(self.layout.settings_file)
                    if not file_report.write_allowed:
                        raise SettingsStoreError("settings file permissions disable writes")
                candidate = transform(current)
                if not isinstance(candidate, UserSettings):
                    raise SettingsStoreError("settings transform must return UserSettings")
                if candidate == current:
                    return current
                if candidate.revision != current.revision + 1:
                    raise SettingsStoreError("settings mutation must advance revision by one")
                try:
                    validate_model(candidate)
                    encoded = candidate.to_json().encode("utf-8")
                except (OpenSocratesError, TypeError, ValueError, OSError) as error:
                    raise SettingsStoreError(
                        "settings mutation returned an invalid value"
                    ) from error
                atomic_replace_bytes(self.layout.settings_file, encoded)
                return candidate
        except LockTimeoutError as error:
            raise SettingsStoreError("settings lock timeout") from error
        except AtomicWriteError as error:
            raise SettingsStoreError("settings atomic write failed") from error


class InMemorySettingsStore:
    """Thread-safe typed settings repository for focused demos."""

    def __init__(self, initial: UserSettings | None = None) -> None:
        self._settings = initial or default_settings()
        validate_model(self._settings)
        self._lock = RLock()

    def load(self) -> UserSettings:
        with self._lock:
            return self._settings

    def save(self, settings: UserSettings) -> None:
        if not isinstance(settings, UserSettings):
            raise TypeError("settings repository accepts UserSettings only")
        validate_model(settings)
        with self._lock:
            if settings.revision <= self._settings.revision:
                raise SettingsStoreError("settings revision must increase")
            self._settings = settings

    def mutate(self, transform: Callable[[UserSettings], UserSettings]) -> UserSettings:
        """Apply one lock-held, exactly-one-revision settings mutation."""

        if not callable(transform):
            raise TypeError("settings transform must be callable")
        with self._lock:
            current = self._settings
            candidate = transform(current)
            if not isinstance(candidate, UserSettings):
                raise SettingsStoreError("settings transform must return UserSettings")
            if candidate == current:
                return current
            if candidate.revision != current.revision + 1:
                raise SettingsStoreError("settings mutation must advance revision by one")
            try:
                validate_model(candidate)
            except (OpenSocratesError, TypeError, ValueError) as error:
                raise SettingsStoreError("settings mutation returned an invalid value") from error
            self._settings = candidate
            return candidate


__all__ = [
    "SettingsReadStatus",
    "SettingsStoreError",
    "default_settings",
    "SettingsStore",
    "InMemorySettingsStore",
]
