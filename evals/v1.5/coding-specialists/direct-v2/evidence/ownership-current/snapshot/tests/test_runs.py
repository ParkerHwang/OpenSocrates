import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from batchflow.cli import show_run
from batchflow.runs import RunStore, render_manifest
from batchflow.templates import Monitor, TemplateRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RetainedRunTests(unittest.TestCase):
    def test_run_survives_new_store_and_existing_consumers_render_it(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = TemplateRegistry()
            registry.put(
                "alpha",
                [
                    {"name": "extract", "workers": 2, "options": {"labels": ["daily"]}},
                    {"name": "load", "workers": 4},
                ],
            )

            created = RunStore(directory, registry).create("alpha")
            self.assertEqual(
                set(created),
                {"run_id", "template_name", "source_revision", "stages", "total_workers"},
            )
            self.assertEqual(created["source_revision"], 1)
            self.assertEqual(created["total_workers"], 6)
            self.assertEqual(created["stages"][1]["options"], {})

            later_store = RunStore(directory, registry)
            loaded = later_store.load(created["run_id"])
            self.assertEqual(loaded, created)
            self.assertEqual(later_store.export(created["run_id"]), render_manifest(loaded))
            self.assertEqual(show_run(later_store, created["run_id"]), later_store.export(created["run_id"]))

    def test_template_and_returned_mutations_do_not_change_retained_state(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = TemplateRegistry()
            original_options = {"nested": {"labels": ["historic"], "weights": [1, 2]}}
            input_stages = [{"name": "work", "workers": 3, "options": original_options}]
            registry.put("alpha", input_stages)
            monitor = Monitor(registry, "alpha")

            original_options["nested"]["labels"].append("caller edit")
            input_stages[0]["workers"] = 64

            described = registry.describe("alpha")
            self.assertEqual(described["stages"][0]["workers"], 3)
            self.assertEqual(described["stages"][0]["options"]["nested"]["labels"], ["historic"])
            described["stages"][0]["options"]["nested"]["labels"].append("describe edit")
            monitored = monitor.as_dict()
            monitored["stages"][0]["options"]["nested"]["weights"].append(99)

            store = RunStore(directory, registry)
            created = store.create("alpha")
            self.assertEqual(created["stages"][0]["options"]["nested"]["labels"], ["historic"])
            created["stages"][0]["options"]["nested"]["labels"].append("create edit")
            created["stages"][0]["workers"] = 60

            loaded = store.load(created["run_id"])
            self.assertEqual(loaded["source_revision"], 1)
            self.assertEqual(loaded["total_workers"], 3)
            self.assertEqual(loaded["stages"][0]["workers"], 3)
            self.assertEqual(loaded["stages"][0]["options"]["nested"], {
                "labels": ["historic"], "weights": [1, 2]
            })
            loaded["stages"][0]["options"]["nested"]["labels"].clear()
            self.assertEqual(store.load(created["run_id"])["stages"][0]["options"]["nested"]["labels"], ["historic"])

            registry.put("alpha", [{"name": "work", "workers": 5, "options": {"version": [2]}}])
            live = monitor.as_dict()
            self.assertEqual((live["revision"], live["total_workers"]), (2, 5))
            self.assertEqual(live["stages"][0]["options"]["version"], [2])
            retained = store.load(created["run_id"])
            self.assertEqual(retained["source_revision"], 1)
            self.assertEqual(retained["total_workers"], 3)
            self.assertEqual(retained["stages"][0]["options"]["nested"]["labels"], ["historic"])

    def test_run_ids_do_not_overwrite_records_in_an_existing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = TemplateRegistry()
            registry.put("alpha", [{"name": "work", "workers": 1}])
            first_store = RunStore(directory, registry)
            first = first_store.create("alpha")
            second_store = RunStore(directory, registry)

            with patch(
                "batchflow.runs.uuid.uuid4",
                side_effect=[
                    SimpleNamespace(hex=first["run_id"]),
                    SimpleNamespace(hex="f" * 32),
                ],
            ):
                second = second_store.create("alpha")

            self.assertNotEqual(first["run_id"], second["run_id"])
            self.assertEqual(first_store.load(first["run_id"]), first)
            self.assertEqual(second_store.load(second["run_id"]), second)

    def test_bad_or_missing_template_creates_no_file_or_run_id(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = TemplateRegistry()
            registry.put("good", [{"name": "work", "workers": 2}])
            store = RunStore(directory, registry)
            prior = store.create("good")
            registry._templates["malformed"] = {
                "revision": 1,
                "stages": [{"name": "work", "workers": 2, "options": {"bad": float("nan")}}],
            }
            existing_files = sorted(path.name for path in Path(directory).glob("*.json"))

            with patch("batchflow.runs.uuid.uuid4", side_effect=AssertionError("ID generated too early")):
                with self.assertRaises(ValueError):
                    store.create("malformed")
                with self.assertRaises(KeyError):
                    store.create("missing")

            self.assertEqual(sorted(path.name for path in Path(directory).glob("*.json")), existing_files)
            self.assertEqual(list(Path(directory).glob(".batchflow-run-*.tmp")), [])
            self.assertEqual(store.load(prior["run_id"]), prior)

    def test_actual_v1_producer_loads_without_rewriting_its_file(self):
        with tempfile.TemporaryDirectory() as directory:
            producer = PROJECT_ROOT / "legacy" / "produce_v1.py"
            subprocess.run([sys.executable, str(producer), directory], check=True, capture_output=True)
            old_path = Path(directory) / "legacy-1.json"
            before = old_path.read_bytes()

            store = RunStore(directory, TemplateRegistry())
            loaded = store.load("legacy-1")

            self.assertEqual(loaded["source_revision"], None)
            self.assertEqual(loaded["stages"], [
                {"name": "old-stage", "workers": 3, "options": {"labels": ["historic"]}}
            ])
            self.assertEqual(loaded["total_workers"], 3)
            self.assertEqual(store.export("legacy-1"), "alpha:legacy-1 workers=3")
            self.assertEqual(old_path.read_bytes(), before)
            self.assertNotIn("source_revision", json.loads(old_path.read_text(encoding="utf-8")))

    def test_normalization_rejects_non_json_options_and_keeps_worker_limits(self):
        registry = TemplateRegistry()
        registry.put("limit", [{"name": "max", "workers": 64}])
        self.assertEqual(registry.describe("limit")["total_workers"], 64)

        for invalid in (
            {"name": "bad", "workers": 1, "options": {"payload": object()}},
            {"name": "bad", "workers": 1, "options": {"payload": float("nan")}},
            {"name": "bad", "workers": 1, "options": {1: "non-string key"}},
            {"name": "bad", "workers": True},
            {"name": "bad", "workers": 65},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    registry.put("bad", [invalid])

        with self.assertRaises(ValueError):
            registry.put("duplicate", [
                {"name": "same", "workers": 1},
                {"name": "same", "workers": 2},
            ])


if __name__ == "__main__":
    unittest.main()
