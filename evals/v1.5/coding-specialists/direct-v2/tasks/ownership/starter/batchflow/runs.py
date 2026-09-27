from .templates import normalize_stages, total_workers


def render_manifest(record):
    return f"{record['template_name']}:{record['run_id']} workers={record['total_workers']}"


class RunStore:
    def __init__(self, directory, registry):
        self.directory, self.registry = directory, registry

    def create(self, template_name):
        raise NotImplementedError("retained run manifests")

    def load(self, run_id):
        raise NotImplementedError("retained run manifests")

    def export(self, run_id):
        return render_manifest(self.load(run_id))
