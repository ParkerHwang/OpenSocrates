import unittest

from callbacks import apply_result


class GenerationCallbackTests(unittest.TestCase):
    def test_current_generation_updates_the_input_dict_without_advancing(self):
        state = {"generation": 4, "result": "old"}

        result = apply_result(state, 4, "new")

        self.assertIs(result, True)
        self.assertEqual(state, {"generation": 4, "result": "new"})

    def test_older_generation_leaves_the_input_dict_unchanged(self):
        state = {"generation": 4, "result": "current"}
        before = state.copy()

        result = apply_result(state, 3, "stale")

        self.assertIs(result, False)
        self.assertEqual(state, before)

    def test_future_generation_leaves_the_input_dict_unchanged(self):
        state = {"generation": 4, "result": "current"}
        before = state.copy()

        result = apply_result(state, 5, "future")

        self.assertIs(result, False)
        self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
