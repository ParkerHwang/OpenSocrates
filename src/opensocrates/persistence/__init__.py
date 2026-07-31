"""Secure local persistence implementations for OpenSocrates v1."""

from .atomic import (
    AtomicWriteError,
    append_fsync,
    atomic_replace_bytes,
    atomic_write_document,
    atomic_write_json,
    canonical_json_bytes,
    decode_json_bytes,
)
from .jsonl_store import (
    AppendReceipt,
    JsonlRecordStore,
    RecordCorruptionError,
    RecordSequenceError,
    RecordStoreError,
    RecordUnavailableError,
)
from .metrics_store import (
    InMemoryMetricsStore,
    MetricAppendReceipt,
    MetricsStore,
    MetricsStoreError,
)
from .paths import DataRoot, DataRootConfig, DataRootLayout, ensure_data_root, resolve_data_root
from .permissions import PermissionManager, PermissionReport, PermissionSecurityError
from .quarantine import QuarantineReason, QuarantineReceipt
from .settings_store import (
    InMemorySettingsStore,
    SettingsReadStatus,
    SettingsStore,
    SettingsStoreError,
    default_settings,
)
from .task_store import InMemoryTaskStore, TaskSnapshot, TaskStore, TaskStoreError
from .turn_store import InMemoryTurnStore, TurnStateConflict, TurnStateStore, TurnStoreError

__all__ = [
    "AtomicWriteError",
    "AppendReceipt",
    "DataRoot",
    "DataRootConfig",
    "DataRootLayout",
    "InMemoryTaskStore",
    "InMemoryMetricsStore",
    "InMemoryTurnStore",
    "JsonlRecordStore",
    "MetricAppendReceipt",
    "MetricsStore",
    "MetricsStoreError",
    "PermissionManager",
    "PermissionReport",
    "PermissionSecurityError",
    "QuarantineReason",
    "QuarantineReceipt",
    "RecordCorruptionError",
    "RecordSequenceError",
    "RecordStoreError",
    "RecordUnavailableError",
    "SettingsReadStatus",
    "SettingsStore",
    "SettingsStoreError",
    "TaskSnapshot",
    "TaskStore",
    "TaskStoreError",
    "TurnStateConflict",
    "TurnStateStore",
    "TurnStoreError",
    "append_fsync",
    "atomic_replace_bytes",
    "atomic_write_document",
    "atomic_write_json",
    "canonical_json_bytes",
    "decode_json_bytes",
    "ensure_data_root",
    "default_settings",
    "resolve_data_root",
    "InMemorySettingsStore",
]
