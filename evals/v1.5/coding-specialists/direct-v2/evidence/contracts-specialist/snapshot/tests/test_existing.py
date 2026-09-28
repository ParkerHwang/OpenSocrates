import unittest
from quotadesk.cli import import_line, render_record
from quotadesk.policy import Store


class ExistingContracts(unittest.TestCase):
    def test_legacy_import(self):
        store = Store(default_limit=80)
        self.assertEqual(import_line(store, "a", "12"), "limit=12")
        self.assertEqual(import_line(store, "b", "0"), "unlimited")
        self.assertEqual(import_line(store, "c", None), "limit=80")

    def test_render_and_detached_reads(self):
        store = Store()
        store.seed("a", 20, "ops")
        row = store.read("a")
        self.assertEqual(render_record(row), "a@1: 20 (ops)")
        row["label"] = "edited externally"
        self.assertEqual(store.read("a")["label"], "ops")
