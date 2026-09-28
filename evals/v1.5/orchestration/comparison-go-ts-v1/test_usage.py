from __future__ import annotations

import unittest

from usage import aggregate


class UsageControls(unittest.TestCase):
    def test_missing_usage_is_not_zero(self):
        result = aggregate([
            {"usage": {"input_tokens": 20, "cached_input_tokens": 5,
                       "cache_write_input_tokens": 0, "output_tokens": 8,
                       "reasoning_output_tokens": 3}},
            {"usage": {"input_tokens": None, "cached_input_tokens": None,
                       "cache_write_input_tokens": None, "output_tokens": None,
                       "reasoning_output_tokens": None}},
        ])
        self.assertIsNone(result["reported_usage"]["input_tokens"])
        self.assertEqual(result["missing_call_count"]["input_tokens"], 1)
        self.assertIsNone(result["combined_input_plus_output_tokens"])

    def test_cache_and_reasoning_are_subsets(self):
        result = aggregate([{"usage": {
            "input_tokens": 20, "cached_input_tokens": 5,
            "cache_write_input_tokens": 2, "output_tokens": 8,
            "reasoning_output_tokens": 3,
        }}])
        self.assertEqual(result["derived_uncached_input_tokens"], 15)
        self.assertEqual(result["combined_input_plus_output_tokens"], 28)


if __name__ == "__main__":
    unittest.main()
