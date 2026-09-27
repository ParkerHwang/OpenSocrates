import math
from collections.abc import Mapping


def _copy_json_value(value, active=None):
    """Validate and copy a value made only from JSON types."""
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("stage options must contain finite JSON numbers")
        return value

    if isinstance(value, (dict, list)):
        if active is None:
            active = set()
        identity = id(value)
        if identity in active:
            raise ValueError("stage options must not contain cycles")
        active.add(identity)
        try:
            if isinstance(value, dict):
                copied = {}
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise ValueError("stage option object keys must be strings")
                    copied[str(key)] = _copy_json_value(item, active)
                return copied
            return [_copy_json_value(item, active) for item in value]
        finally:
            active.remove(identity)

    raise ValueError("stage options must contain only JSON-compatible values")


def normalize_stages(stages):
    if not isinstance(stages, list) or not stages:
        raise ValueError("stages must be a nonempty list")
    out, names = [], set()
    for stage in stages:
        if not isinstance(stage, Mapping):
            raise ValueError("each stage must be a mapping")
        name, workers = stage.get("name"), stage.get("workers")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("unique nonempty stage name required")
        if type(workers) is not int or not 1 <= workers <= 64:
            raise ValueError("workers out of range")
        names.add(name)
        options = _copy_json_value(stage.get("options", {}))
        out.append({"name": name, "workers": workers, "options": options})
    return out


def total_workers(stages):
    return sum(stage["workers"] for stage in stages)


class TemplateRegistry:
    def __init__(self):
        self._templates = {}

    def put(self, name, stages):
        normalized = normalize_stages(stages)
        prior = self._templates.get(name, {"revision": 0})
        self._templates[name] = {"revision": prior["revision"] + 1, "stages": normalized}

    def describe(self, name):
        value = self._templates[name]
        stages = normalize_stages(value["stages"])
        return {
            "revision": value["revision"],
            "stages": stages,
            "total_workers": total_workers(stages),
        }


class Monitor:
    def __init__(self, registry, name):
        self.registry, self.name = registry, name

    def as_dict(self):
        return self.registry.describe(self.name)
