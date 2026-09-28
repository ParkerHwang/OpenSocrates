import json
from pathlib import Path
import tempfile
import unittest

from batchflow.cli import show_run
from batchflow.runs import RunStore, render_manifest
from batchflow.templates import Monitor, TemplateRegistry
from legacy.produce_v1 import produce


class DurableRunTests(unittest.TestCase):
    def test_registry_owns_nested_options_and_monitor_returns_owned_live_views(self):
        registry = TemplateRegistry()
        options = {"labels": ["ready", {"priority": 2}]}
        source = [{"name": "worker", "workers": 3, "options": options}]
        registry.put("alpha", source)

        options["labels"][1]["priority"] = 9
        source[0]["workers"] = 40
        description = registry.describe("alpha")
        self.assertEqual(description["stages"][0]["workers"], 3)
        self.assertEqual(description["stages"][0]["options"], {"labels": ["ready", {"priority": 2}]})
        description["stages"][0]["options"]["labels"].append("caller edit")
        description["stages"].append({"name": "extra", "workers": 1, "options": {}})
        self.assertEqual(registry.describe("alpha")["total_workers"], 3)

        monitor = Monitor(registry, "alpha")
        current = monitor.as_dict()
        current["stages"][0]["options"]["labels"].clear()
        self.assertEqual(monitor.as_dict()["stages"][0]["options"]["labels"][0], "ready")

        registry.put("alpha", [{"name": "worker", "workers": 5}])
        self.assertEqual(monitor.as_dict()["revision"], 2)
        self.assertEqual(monitor.as_dict()["total_workers"], 5)

    def test_create_load_and_other_store_instance_retain_independent_snapshot(self):
        registry = TemplateRegistry()
        registry.put(
            "alpha",
            [{"name": "worker", "workers": 2, "options": {"items": [{"tag": "old"}]}}],
        )
        with tempfile.TemporaryDirectory() as directory:
            first_store = RunStore(directory, registry)
            created = first_store.create("alpha")
            self.assertEqual(
                set(created),
                {
                    "run_id",
                    "template_name",
                    "source_revision",
                    "stages",
                    "factor",
                    "total_workers",
                },
            )
            self.assertEqual(created["source_revision"], 1)
            self.assertEqual(created["factor"], 1)
            self.assertEqual(created["total_workers"], 2)

            created["stages"][0]["options"]["items"][0]["tag"] = "returned edit"
            created["stages"].append({"name": "extra", "workers": 1, "options": {}})
            registry.put("alpha", [{"name": "new", "workers": 7}])

            second_store = RunStore(directory, registry)
            loaded = second_store.load(created["run_id"])
            self.assertEqual(loaded["source_revision"], 1)
            self.assertEqual(loaded["total_workers"], 2)
            self.assertEqual(loaded["stages"][0]["options"]["items"][0]["tag"], "old")
            loaded["stages"][0]["options"]["items"][0]["tag"] = "load edit"
            self.assertEqual(
                second_store.load(created["run_id"])["stages"][0]["options"]["items"][0]["tag"],
                "old",
            )
            self.assertEqual(Monitor(registry, "alpha").as_dict()["total_workers"], 7)

            other = second_store.create("alpha")
            self.assertNotEqual(other["run_id"], created["run_id"])
            self.assertTrue((Path(directory) / f"{created['run_id']}.json").is_file())
            self.assertTrue((Path(directory) / f"{other['run_id']}.json").is_file())
            self.assertEqual(
                second_store.export(created["run_id"]),
                render_manifest(second_store.load(created["run_id"])),
            )
            self.assertEqual(show_run(second_store, created["run_id"]), second_store.export(created["run_id"]))

    def test_factor_scales_an_owned_snapshot_and_keeps_options_isolated(self):
        registry = TemplateRegistry()
        registry.put(
            "alpha",
            [
                {
                    "name": "worker",
                    "workers": 2,
                    "options": {"labels": ["stable", {"priority": 2}]},
                }
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory, registry)
            created = store.create("alpha", factor=3)
            self.assertEqual(created["factor"], 3)
            self.assertEqual(created["stages"][0]["workers"], 6)
            self.assertEqual(created["total_workers"], 6)

            manifest_path = Path(directory) / f"{created['run_id']}.json"
            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["factor"], 3)
            self.assertEqual(persisted["stages"][0]["workers"], 6)
            self.assertEqual(persisted["total_workers"], 6)

            created["stages"][0]["options"]["labels"][1]["priority"] = 9
            loaded = store.load(created["run_id"])
            self.assertEqual(loaded["stages"][0]["options"]["labels"][1]["priority"], 2)
            self.assertEqual(loaded["total_workers"], 6)

            registry.put("alpha", [{"name": "worker", "workers": 4}])
            self.assertEqual(Monitor(registry, "alpha").as_dict()["total_workers"], 4)
            self.assertEqual(store.load(created["run_id"])["stages"][0]["workers"], 6)
            self.assertEqual(store.export(created["run_id"]), render_manifest(loaded))

    def test_factor_limits_and_overflow_rejection_are_atomic(self):
        registry = TemplateRegistry()
        registry.put("alpha", [{"name": "worker", "workers": 16}])
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory, registry)
            accepted = store.create("alpha", factor=4)
            self.assertEqual(accepted["stages"][0]["workers"], 64)
            self.assertEqual(accepted["total_workers"], 64)
            before = {
                path.name: path.read_bytes()
                for path in Path(directory).iterdir()
                if path.is_file()
            }

            for factor in (True, False, 0, 5, -1, 1.0, "2", None):
                with self.subTest(factor=factor):
                    with self.assertRaises(ValueError):
                        store.create("alpha", factor=factor)
            with self.assertRaises(TypeError):
                store.create("alpha", 2)

            registry.put("alpha", [{"name": "worker", "workers": 33}])
            with self.assertRaises(ValueError):
                store.create("alpha", factor=2)
            after = {
                path.name: path.read_bytes()
                for path in Path(directory).iterdir()
                if path.is_file()
            }
            self.assertEqual(after, before)
            self.assertEqual(
                sorted(path.name for path in Path(directory).iterdir()),
                [f"{accepted['run_id']}.json"],
            )

    def test_actual_legacy_producer_loads_without_rewriting_its_file(self):
        with tempfile.TemporaryDirectory() as directory:
            produce(directory)
            legacy_path = Path(directory) / "legacy-1.json"
            original_bytes = legacy_path.read_bytes()
            registry = TemplateRegistry()
            registry.put("alpha", [{"name": "today", "workers": 8}])
            store = RunStore(directory, registry)

            loaded = store.load("legacy-1")
            self.assertEqual(loaded["source_revision"], None)
            self.assertEqual(loaded["stages"], [{"name": "old-stage", "workers": 3, "options": {"labels": ["historic"]}}])
            self.assertEqual(loaded["total_workers"], 3)
            expected = json.loads(original_bytes.decode("utf-8"))
            expected["source_revision"] = None
            expected["factor"] = 1
            self.assertEqual(loaded, expected)
            self.assertEqual(legacy_path.read_bytes(), original_bytes)
            self.assertEqual(store.export("legacy-1"), "alpha:legacy-1 workers=3")

    def test_invalid_updates_do_not_change_registry_or_create_partial_runs(self):
        registry = TemplateRegistry()
        registry.put("alpha", [{"name": "stable", "workers": 4}])
        with self.assertRaises(ValueError):
            registry.put("alpha", [{"name": "invalid", "workers": True}])
        with self.assertRaises(ValueError):
            registry.put("alpha", [{"name": "invalid", "workers": 1, "options": {"bad": object()}}])

        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory, registry)
            before = store.create("alpha")
            before_bytes = (Path(directory) / f"{before['run_id']}.json").read_bytes()
            with self.assertRaises(KeyError):
                store.create("missing")
            self.assertEqual(registry.describe("alpha")["revision"], 1)
            self.assertEqual(store.load(before["run_id"])["total_workers"], 4)
            self.assertEqual((Path(directory) / f"{before['run_id']}.json").read_bytes(), before_bytes)
            self.assertEqual(list(Path(directory).glob("*.json")), [Path(directory) / f"{before['run_id']}.json"])

    def test_stage_options_must_be_json_compatible(self):
        registry = TemplateRegistry()
        for value in (float("nan"), {1: "non-string key"}, ("tuple",)):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    registry.put("bad", [{"name": "x", "workers": 1, "options": value}])


if __name__ == "__main__":
    unittest.main()
