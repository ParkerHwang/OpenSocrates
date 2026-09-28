import json
import math
from collections.abc import Mapping


def _is_json_compatible(value, seen):
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        if id(value) in seen:
            return False
        seen.add(id(value))
        try:
            return all(_is_json_compatible(item, seen) for item in value)
        finally:
            seen.remove(id(value))
    if isinstance(value, dict):
        if id(value) in seen:
            return False
        seen.add(id(value))
        try:
            return all(
                isinstance(key, str) and _is_json_compatible(item, seen)
                for key, item in value.items()
            )
        finally:
            seen.remove(id(value))
    return False


def _copy_json_value(value):
    try:
        compatible = _is_json_compatible(value, set())
        if compatible:
            return json.loads(json.dumps(value, allow_nan=False))
    except (RecursionError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("options must be JSON-compatible") from exc
    raise ValueError("options must be JSON-compatible")


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
        result = {
            "revision": value["revision"],
            "stages": _copy_json_value(value["stages"]),
        }
        result["total_workers"] = total_workers(result["stages"])
        return result


class Monitor:
    def __init__(self, registry, name):
        self.registry, self.name = registry, name

    def as_dict(self):
        return self.registry.describe(self.name)
