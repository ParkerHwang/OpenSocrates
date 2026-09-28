"""The legacy importer is used by an existing operations CLI."""
from copy import deepcopy
from threading import RLock


class PolicyError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def legacy_limit(value, default):
    if value is None or value == "":
        return default
    number = int(value)
    if number < 0:
        raise ValueError("negative legacy limit")
    return None if number == 0 else number


class Store:
    def __init__(self, default_limit=100):
        self.default_limit = default_limit
        self.rows = {}
        self.audit = []
        self._lock = RLock()

    def seed(self, namespace, configured=40, label="existing"):
        with self._lock:
            self.rows[namespace] = {
                "revision": 1,
                "configured_max_jobs": configured,
                "label": label,
            }

    def read(self, namespace):
        with self._lock:
            if namespace not in self.rows:
                raise PolicyError("not_found")
            row = deepcopy(self.rows[namespace])
            value = row["configured_max_jobs"]
            return {
                "namespace": namespace,
                "revision": row["revision"],
                "configured_max_jobs": value,
                "effective_max_jobs": self.default_limit if value is None else value,
                "label": row["label"],
            }

    def audit_entries(self):
        with self._lock:
            return deepcopy(self.audit)


def import_legacy(store, namespace, source):
    """Legacy zero is unlimited, while absent values select a numeric default."""
    value = legacy_limit(source.get("limit"), store.default_limit)
    store.seed(namespace, value, source.get("name", ""))
    return {"namespace": namespace, "legacy_limit": value}


def apply_policy(store, namespace, payload):
    """Apply a strict, revision-checked edit without changing legacy import rules."""
    if not isinstance(payload, dict):
        raise PolicyError("invalid")

    allowed = {"expected_revision", "max_jobs", "label"}
    if set(payload) - allowed or "expected_revision" not in payload:
        raise PolicyError("invalid")

    expected_revision = payload["expected_revision"]
    if (not isinstance(expected_revision, int) or isinstance(expected_revision, bool)
            or expected_revision <= 0):
        raise PolicyError("invalid")

    if "max_jobs" in payload:
        max_jobs = payload["max_jobs"]
        if max_jobs is not None and (
                not isinstance(max_jobs, int) or isinstance(max_jobs, bool)
                or not 0 <= max_jobs <= 1000):
            raise PolicyError("invalid")
    else:
        max_jobs = None

    if "label" in payload:
        label = payload["label"]
        if label is None:
            label = ""
        elif not isinstance(label, str) or len(label) > 40:
            raise PolicyError("invalid")
    else:
        label = None

    with store._lock:
        if namespace not in store.rows:
            raise PolicyError("not_found")

        current = store.rows[namespace]
        if expected_revision != current["revision"]:
            raise PolicyError("conflict")

        configured = current["configured_max_jobs"] if "max_jobs" not in payload else max_jobs
        new_label = current["label"] if "label" not in payload else label
        if (configured == current["configured_max_jobs"]
                and new_label == current["label"]):
            return store.read(namespace)

        old_revision = current["revision"]
        new_revision = old_revision + 1
        store.rows[namespace] = {
            "revision": new_revision,
            "configured_max_jobs": configured,
            "label": new_label,
        }
        store.audit.append({
            "namespace": namespace,
            "old_revision": old_revision,
            "new_revision": new_revision,
        })
        return store.read(namespace)
