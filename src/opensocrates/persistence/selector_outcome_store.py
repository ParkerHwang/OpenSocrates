"""Owner-only aggregate persistence for content-free selector outcomes."""

from __future__ import annotations

from collections.abc import Mapping

from ..constants import SELECTOR_OUTCOME_LABELS
from .atomic import (
    AtomicWriteError,
    atomic_replace_bytes,
    canonical_json_bytes,
    decode_json_bytes,
    read_bytes,
)
from .locks import FileLock, LockPolicy, LockTimeoutError
from .paths import DataRoot, DataRootLayout, secure_join
from .permissions import PermissionManager

SELECTOR_OUTCOME_SCHEMA = "opensocrates.selector-outcome-aggregate/1.0.0"
MAX_SELECTOR_OUTCOME_FILE_BYTES = 4096
MAX_SELECTOR_OUTCOME_COUNT = 2**31 - 1
_LABELS = frozenset(SELECTOR_OUTCOME_LABELS)


class SelectorOutcomeStoreError(OSError):
    """Raised when a selector outcome aggregate is unsafe or unavailable."""

    def __init__(self, message: str, *, recoverable: bool = False) -> None:
        super().__init__(message)
        self.recoverable = recoverable


def _empty_counts() -> dict[str, int]:
    return {label: 0 for label in SELECTOR_OUTCOME_LABELS}


def _validated_counts(value: object, *, allow_zero: bool = True) -> dict[str, int]:
    if not isinstance(value, Mapping) or set(value) - _LABELS:
        raise SelectorOutcomeStoreError("selector outcome labels are invalid")
    counts = _empty_counts()
    for label, count in value.items():
        if (
            not isinstance(label, str)
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or count > MAX_SELECTOR_OUTCOME_COUNT
            or (not allow_zero and count == 0)
        ):
            raise SelectorOutcomeStoreError("selector outcome count is invalid")
        counts[label] = count
    return counts


class SelectorOutcomeStore:
    """Atomically accumulate only the fixed selector outcome vocabulary."""

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
        self.path = secure_join(self.layout.diagnostics_dir, "selector-outcomes.json")
        self.lock_path = secure_join(self.layout.diagnostics_dir, "selector-outcomes.lock")

    def read(self) -> dict[str, int]:
        """Read the aggregate or return a closed all-zero projection."""

        try:
            data = read_bytes(self.path, max_bytes=MAX_SELECTOR_OUTCOME_FILE_BYTES)
        except FileNotFoundError:
            return _empty_counts()
        except AtomicWriteError as error:
            raise SelectorOutcomeStoreError("selector outcome aggregate is unreadable") from error
        report = self.permissions.file_report(self.path)
        if not report.write_allowed:
            raise SelectorOutcomeStoreError("selector outcome aggregate is not owner-only")
        try:
            document = decode_json_bytes(data, max_bytes=MAX_SELECTOR_OUTCOME_FILE_BYTES)
        except (TypeError, ValueError) as error:
            raise SelectorOutcomeStoreError(
                "selector outcome aggregate is invalid", recoverable=True
            ) from error
        if not isinstance(document, Mapping) or document.get("schema") != SELECTOR_OUTCOME_SCHEMA:
            # A newer application may own an unknown schema.  Report it as
            # unavailable, but never let an older runtime overwrite it.
            raise SelectorOutcomeStoreError("selector outcome aggregate schema is invalid")
        raw_counts = document.get("counts")
        try:
            counts = _validated_counts(raw_counts)
        except SelectorOutcomeStoreError as error:
            raise SelectorOutcomeStoreError(
                "selector outcome aggregate counts are invalid", recoverable=True
            ) from error
        if (
            canonical_json_bytes(
                {"schema": SELECTOR_OUTCOME_SCHEMA, "counts": raw_counts},
                max_bytes=MAX_SELECTOR_OUTCOME_FILE_BYTES,
            )
            != data
        ):
            raise SelectorOutcomeStoreError(
                "selector outcome aggregate is not canonical", recoverable=True
            )
        return counts

    def increment(self, delta: Mapping[str, int]) -> dict[str, int]:
        """Add one bounded content-free delta and return the new aggregate."""

        selected = _validated_counts(delta)
        if not any(selected.values()):
            return self.read()
        root_report = self.permissions.root_report(self.layout.root)
        diagnostics_report = self.permissions.root_report(self.layout.diagnostics_dir)
        if not root_report.write_allowed or not diagnostics_report.write_allowed:
            raise SelectorOutcomeStoreError("selector outcome writes are disabled")
        try:
            with FileLock(self.lock_path, policy=self.lock_policy):
                try:
                    current = self.read()
                except SelectorOutcomeStoreError as error:
                    if not error.recoverable:
                        raise
                    current = _empty_counts()
                updated = {
                    label: min(MAX_SELECTOR_OUTCOME_COUNT, current[label] + selected[label])
                    for label in SELECTOR_OUTCOME_LABELS
                }
                encoded = canonical_json_bytes(
                    {"schema": SELECTOR_OUTCOME_SCHEMA, "counts": updated},
                    max_bytes=MAX_SELECTOR_OUTCOME_FILE_BYTES,
                )
                atomic_replace_bytes(self.path, encoded)
        except (AtomicWriteError, LockTimeoutError) as error:
            raise SelectorOutcomeStoreError("selector outcome aggregate update failed") from error
        return updated


__all__ = [
    "MAX_SELECTOR_OUTCOME_COUNT",
    "SELECTOR_OUTCOME_SCHEMA",
    "SelectorOutcomeStore",
    "SelectorOutcomeStoreError",
]
