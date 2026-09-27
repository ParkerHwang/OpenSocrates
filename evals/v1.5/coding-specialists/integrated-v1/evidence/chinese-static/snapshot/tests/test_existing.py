import unittest
from tagindex import TagIndex, render_count


class CurrentConsumer(unittest.TestCase):
    def test_count(self):
        index = TagIndex()
        index.put("a", {"tags": ["x"]})
        self.assertEqual(render_count(index), "documents=1")
