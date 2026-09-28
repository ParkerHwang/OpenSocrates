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
    raise NotImplementedError("new strict revisioned editor")
