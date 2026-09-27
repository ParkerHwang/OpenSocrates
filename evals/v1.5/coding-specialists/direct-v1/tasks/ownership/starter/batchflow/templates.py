def normalize_stages(stages):
    if not isinstance(stages, list) or not stages:
        raise ValueError("stages must be a nonempty list")
    out, names = [], set()
    for stage in stages:
        name, workers = stage.get("name"), stage.get("workers")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("unique nonempty stage name required")
        if type(workers) is not int or not 1 <= workers <= 64:
            raise ValueError("workers out of range")
        names.add(name)
        out.append({"name": name, "workers": workers, "options": stage.get("options", {})})
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
        return {**value, "total_workers": total_workers(value["stages"])}


class Monitor:
    def __init__(self, registry, name):
        self.registry, self.name = registry, name

    def as_dict(self):
        return self.registry.describe(self.name)
