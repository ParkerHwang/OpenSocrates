"""Keep the experiment separate from the existing 1.x marketplace contract."""

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MarketplaceChecks(unittest.TestCase):
    def test_existing_manager_keeps_its_single_entry(self):
        path = ROOT / ".agents/plugins/marketplace.json"
        marketplace = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(marketplace["plugins"]), 1)
        self.assertEqual(marketplace["plugins"][0]["name"], "opensocrates")

    def test_experimental_marketplace_resolves_to_its_own_plugin(self):
        root = ROOT / "plugin-src/experimental-output-brief"
        marketplace = json.loads((root / ".agents/plugins/marketplace.json").read_text())
        entry = marketplace["plugins"][0]
        plugin_root = (root / entry["source"]["path"]).resolve()
        self.assertEqual(plugin_root, root.resolve())
        manifest = json.loads((plugin_root / "plugin.json").read_text())
        self.assertEqual(entry["name"], manifest["name"])
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertTrue((plugin_root / "skills/output-brief/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
