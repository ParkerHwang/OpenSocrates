"""The legacy importer is used by an existing operations CLI."""
from copy import deepcopy


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

    def seed(self, namespace, configured=40, label="existing"):
        self.rows[namespace] = {"revision": 1, "configured_max_jobs": configured, "label": label}

    def read(self, namespace):
        if namespace not in self.rows:
            raise PolicyError("not_found")
        row = deepcopy(self.rows[namespace])
        value = row["configured_max_jobs"]
        return {"namespace": namespace, **row,
                "effective_max_jobs": self.default_limit if value is None else value}

    def audit_entries(self):
        return deepcopy(self.audit)


def import_legacy(store, namespace, source):
    """Legacy zero is unlimited, while absent values select a numeric default."""
    value = legacy_limit(source.get("limit"), store.default_limit)
    store.seed(namespace, value, source.get("name", ""))
    return {"namespace": namespace, "legacy_limit": value}


def apply_policy(store, namespace, payload):
    """Apply a strict, revision-checked edit to an existing namespace."""
    if not isinstance(payload, dict):
        raise PolicyError("invalid")

    allowed_keys = {"expected_revision", "max_jobs", "label"}
    if "expected_revision" not in payload or any(key not in allowed_keys for key in payload):
        raise PolicyError("invalid")

    expected_revision = payload["expected_revision"]
    if type(expected_revision) is not int or expected_revision <= 0:
        raise PolicyError("invalid")

    max_jobs = payload.get("max_jobs", _UNSET)
    if max_jobs is not _UNSET and max_jobs is not None:
        if type(max_jobs) is not int or not 0 <= max_jobs <= 1000:
            raise PolicyError("invalid")

    label = payload.get("label", _UNSET)
    if label is not _UNSET and label is not None:
        if not isinstance(label, str) or len(label) > 40:
            raise PolicyError("invalid")

    if namespace not in store.rows:
        raise PolicyError("not_found")

    current = store.rows[namespace]
    old_revision = current["revision"]
    if expected_revision != old_revision:
        raise PolicyError("conflict")

    next_configured = current["configured_max_jobs"]
    if max_jobs is not _UNSET:
        next_configured = max_jobs

    next_label = current["label"]
    if label is not _UNSET:
        next_label = "" if label is None else label

    if (next_configured == current["configured_max_jobs"]
            and next_label == current["label"]):
        return store.read(namespace)

    new_revision = old_revision + 1
    store.rows[namespace] = {
        "revision": new_revision,
        "configured_max_jobs": next_configured,
        "label": next_label,
    }
    store.audit.append({
        "namespace": namespace,
        "old_revision": old_revision,
        "new_revision": new_revision,
    })
    return store.read(namespace)


_UNSET = object()
