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

        current = self.registry.describe(template_name)
        scaled_stages = [
            {
                "name": stage["name"],
                "workers": stage["workers"] * factor,
                "options": stage["options"],
            }
            for stage in current["stages"]
        ]
        # Reuse the domain normalizer to enforce per-stage limits and to take
        # an owned copy of every nested options value for the retained record.
        stages = normalize_stages(scaled_stages)
        base = {
            "template_name": template_name,
            "source_revision": current["revision"],
            "stages": stages,
            "total_workers": total_workers(stages),
            "factor": factor,
        }

        # Check the complete record before generating an ID or touching disk.
        try:
            json.dumps({"run_id": "", **base}, allow_nan=False)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("template cannot be stored as a JSON run") from exc

        self.directory.mkdir(parents=True, exist_ok=True)
        return self._write_new(base)

    def _write_new(self, base):
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".batchflow-run-", suffix=".tmp", dir=self.directory
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                while True:
                    run_id = uuid.uuid4().hex
                    record = {"run_id": run_id, **base}
                    payload = json.dumps(record, allow_nan=False, separators=(",", ":"))
                    stream.seek(0)
                    stream.truncate()
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                    destination = self.directory / (run_id + ".json")
                    try:
                        # A hard link publishes the complete file and cannot
                        # replace a record created by another store instance.
                        os.link(temporary_name, destination)
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
            or run_id in {".", ".."}
            or "/" in run_id
            or "\\" in run_id
            or "\0" in run_id
        ):
            raise ValueError("invalid run ID")
        path = self.directory / (run_id + ".json")
        with path.open("r", encoding="utf-8") as stream:
            stored = json.load(stream)
        return {
            "run_id": stored["run_id"],
            "template_name": stored["template_name"],
            "source_revision": stored.get("source_revision"),
            "stages": stored["stages"],
            "total_workers": stored["total_workers"],
            "factor": stored.get("factor", 1),
        }

    def export(self, run_id):
        return render_manifest(self.load(run_id))
