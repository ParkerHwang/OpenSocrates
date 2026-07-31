"""Content-free local metrics persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from opensocrates.constants import MAX_RECORD_EVENT_BYTES
from opensocrates.domain.models import LocalMetric
from opensocrates.domain.validation import canonical_json, model_from_json, validate_model

from ..verification.secret_filter import reject_forbidden_keys, reject_secrets
from .atomic import AtomicWriteError, append_fsync, read_bytes
from .locks import FileLock, LockPolicy, LockTimeoutError
from .paths import DataRoot, DataRootLayout, secure_join
from .permissions import PermissionManager


class MetricsStoreError(OSError):
    """Raised when content-free metric storage is unavailable or corrupt."""


def _metric_bytes(metric: LocalMetric) -> bytes:
    if not isinstance(metric, LocalMetric):
        raise TypeError("metrics store accepts LocalMetric only")
    validate_model(metric)
    value = metric.to_dict()
    reject_forbidden_keys(value)
    reject_secrets(value)
    encoded = canonical_json(value).encode("utf-8")
    if len(encoded) > MAX_RECORD_EVENT_BYTES:
        raise MetricsStoreError("metric event exceeds the line limit")
    return encoded


@dataclass(frozen=True, slots=True)
class MetricAppendReceipt:
    path: Path
    metric: LocalMetric


class MetricsStore:
    """Append-only metrics log partitioned by UTC month."""

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

    def _path(self, month: str) -> Path:
        if len(month) != 7 or month[4] != "-" or not month.replace("-", "").isdigit():
            raise MetricsStoreError("metric partition must be YYYY-MM")
        return secure_join(self.layout.metrics_dir, f"local-events-{month}.jsonl")

    def append(self, metric: LocalMetric, *, month: str | None = None) -> MetricAppendReceipt:
        encoded = _metric_bytes(metric)
        partition = month or metric.occurred_at_day[:7]
        path = self._path(partition)
        metrics_report = self.permissions.root_report(self.layout.metrics_dir)
        root_report = self.permissions.root_report(self.layout.root)
        if not root_report.write_allowed or not metrics_report.write_allowed:
            raise MetricsStoreError("metric writes disabled by permissions")
        lock_path = secure_join(self.layout.metrics_dir, f"local-events-{partition}.lock")
        try:
            with FileLock(lock_path, policy=self.lock_policy):
                append_fsync(path, encoded, max_bytes=MAX_RECORD_EVENT_BYTES)
        except (AtomicWriteError, LockTimeoutError) as error:
            raise MetricsStoreError("metric append failed") from error
        return MetricAppendReceipt(path=path, metric=metric)

    def read(self, *, month: str) -> tuple[LocalMetric, ...]:
        path = self._path(month)
        try:
            data = read_bytes(path, max_bytes=100 * 1024 * 1024)
        except FileNotFoundError:
            return ()
        except AtomicWriteError as error:
            raise MetricsStoreError("metric log could not be read") from error
        metrics: list[LocalMetric] = []
        for line in data.splitlines(keepends=True):
            if not line.endswith(b"\n"):
                raise MetricsStoreError("metric log has a torn tail")
            try:
                metric = model_from_json(LocalMetric, line)
                validate_model(metric)
            except (TypeError, ValueError) as error:
                raise MetricsStoreError("metric log contains invalid JSON") from error
            if _metric_bytes(metric) != line:
                raise MetricsStoreError("metric log line is not canonical")
            metrics.append(metric)
        return tuple(metrics)


class InMemoryMetricsStore:
    """Thread-safe content-free metrics repository."""

    def __init__(self) -> None:
        self._metrics: list[LocalMetric] = []
        self._lock = RLock()

    def append(self, metric: LocalMetric) -> LocalMetric:
        _metric_bytes(metric)
        with self._lock:
            self._metrics.append(metric)
        return metric

    def read(self) -> tuple[LocalMetric, ...]:
        with self._lock:
            return tuple(self._metrics)


__all__ = ["MetricsStoreError", "MetricAppendReceipt", "MetricsStore", "InMemoryMetricsStore"]
