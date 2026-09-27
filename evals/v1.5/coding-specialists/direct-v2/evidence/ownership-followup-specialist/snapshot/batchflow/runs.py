import json
import os
import tempfile
import uuid
from pathlib import Path

from .templates import normalize_stages, total_workers


def render_manifest(record):
    return f"{record['template_name']}:{record['run_id']} workers={record['total_workers']}"


class RunStore:
    def __init__(self, directory, registry):
        self.directory, self.registry = Path(directory), registry

    def create(self, template_name, *, factor=1):
        if type(factor) is not int or not 1 <= factor <= 4:
            raise ValueError("factor must be an integer from 1 to 4")

        # describe() provides an owned, normalized snapshot from the registry.
        # Scale and normalize that snapshot before publishing anything, so an
        # over-limit request cannot consume an ID or leave a partial manifest.
        template = self.registry.describe(template_name)
        stages = normalize_stages(
            [
                {
                    "name": stage["name"],
                    "workers": stage["workers"] * factor,
                    "options": stage["options"],
                }
                for stage in template["stages"]
            ]
        )
        record = {
            "run_id": None,
            "template_name": template_name,
            "source_revision": template["revision"],
            "stages": stages,
            "factor": factor,
            "total_workers": total_workers(stages),
        }

        self.directory.mkdir(parents=True, exist_ok=True)
        while True:
            run_id = uuid.uuid4().hex
            record["run_id"] = run_id
            payload = json.dumps(
                record, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode("utf-8")

            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".batchflow-run-", dir=self.directory
            )
            try:
                with os.fdopen(descriptor, "wb") as output:
                    output.write(payload)
                    output.flush()
                    os.fsync(output.fileno())

                target = self.directory / f"{run_id}.json"
                try:
                    # Publishing a complete temporary file by hard link is
                    # atomic and refuses to overwrite any existing run ID.
                    os.link(temporary_name, target)
                except FileExistsError:
                    continue
                return record
            finally:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass

    def load(self, run_id):
        if (
            not isinstance(run_id, str)
            or not run_id
            or run_id in (".", "..")
            or "/" in run_id
            or "\\" in run_id
            or "\0" in run_id
        ):
            raise ValueError("run_id must be a single nonempty path component")

        path = self.directory / f"{run_id}.json"
        with path.open("r", encoding="utf-8") as source:
            record = json.load(source)
        if not isinstance(record, dict):
            raise ValueError("run manifest must contain a JSON object")

        # Old producer files did not store a source revision. Report that fact
        # to callers without changing the retained legacy file.
        if "source_revision" not in record:
            record["source_revision"] = None
        if "factor" not in record:
            record["factor"] = 1
        return record

    def export(self, run_id):
        return render_manifest(self.load(run_id))
