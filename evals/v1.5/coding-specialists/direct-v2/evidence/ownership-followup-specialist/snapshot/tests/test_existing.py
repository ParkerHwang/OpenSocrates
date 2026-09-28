import unittest
from batchflow.templates import TemplateRegistry, Monitor
from batchflow.runs import render_manifest


class ExistingConsumers(unittest.TestCase):
    def test_monitor_is_current_on_each_read(self):
        registry = TemplateRegistry()
        registry.put("alpha", [{"name": "first", "workers": 2}])
        monitor = Monitor(registry, "alpha")
        self.assertEqual(monitor.as_dict()["total_workers"], 2)
        registry.put("alpha", [{"name": "first", "workers": 4}])
        self.assertEqual(monitor.as_dict()["total_workers"], 4)

    def test_render_and_invalid_stage(self):
        self.assertEqual(render_manifest({"template_name": "alpha", "run_id": "r1", "total_workers": 3}), "alpha:r1 workers=3")
        registry = TemplateRegistry()
        with self.assertRaises(ValueError):
            registry.put("a", [{"name": "x", "workers": True}])
