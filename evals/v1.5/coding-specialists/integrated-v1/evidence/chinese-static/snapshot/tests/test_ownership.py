import unittest

from tagindex import TagIndex


class TagIndexOwnership(unittest.TestCase):
    def test_put_copies_nested_input(self):
        index = TagIndex()
        metadata = {
            "tags": ["alpha", "beta", "alpha"],
            "details": {"aliases": ["first", "second"]},
        }

        index.put("doc", metadata)
        metadata["tags"].append("later")
        metadata["details"]["aliases"][0] = "changed"
        metadata["details"]["added"] = True

        self.assertEqual(
            index.summary(),
            {
                "doc": {
                    "tags": ["alpha", "beta", "alpha"],
                    "details": {"aliases": ["first", "second"]},
                }
            },
        )

    def test_summary_mutations_do_not_change_index(self):
        index = TagIndex()
        index.put("doc", {"tags": ["alpha", "alpha"], "details": {"ok": True}})

        result = index.summary()
        result["doc"]["tags"].reverse()
        result["doc"]["details"]["ok"] = False
        result["other"] = {"tags": ["beta"]}

        self.assertEqual(
            index.summary(),
            {"doc": {"tags": ["alpha", "alpha"], "details": {"ok": True}}},
        )

    def test_existing_summary_is_stable_after_index_changes(self):
        index = TagIndex()
        index.put("doc", {"tags": ["alpha", "beta", "alpha"]})

        result = index.summary()
        index.put("doc", {"tags": ["replacement"]})
        index.put("new", {"tags": ["new"]})

        self.assertEqual(
            index.summary(),
            {"doc": {"tags": ["replacement"]}, "new": {"tags": ["new"]}},
        )
        self.assertEqual(result, {"doc": {"tags": ["alpha", "beta", "alpha"]}})


if __name__ == "__main__":
    unittest.main()
