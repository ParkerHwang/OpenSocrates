import unittest
from callbacks import apply_result


class CurrentCallback(unittest.TestCase):
    def test_current_generation_updates_same_object(self):
        state = {"generation": 3, "result": "old"}
        self.assertTrue(apply_result(state, 3, "new"))
        self.assertEqual(state, {"generation": 3, "result": "new"})
