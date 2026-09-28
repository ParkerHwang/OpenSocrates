import unittest

from logquery import export_lines, query_window


class QueryWindowTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"seq": seq, "text": f"row {seq}"} for seq in (0, 2, 5, 9)
        ]

    def test_bounds_are_inclusive_sequence_numbers(self):
        self.assertEqual(
            query_window(self.records, start=2, stop=5),
            self.records[1:3],
        )
        self.assertEqual(query_window(self.records, start=0, stop=0), self.records[:1])
        self.assertEqual(query_window(self.records, start=5), self.records[2:])
        self.assertEqual(query_window(self.records, stop=2), self.records[:2])

    def test_limit_applies_after_sequence_filter(self):
        self.assertEqual(
            query_window(self.records, start=2, stop=9, limit=2),
            self.records[1:3],
        )
        self.assertEqual(query_window(self.records, limit=0), [])

    def test_unbounded_query_returns_new_list_without_mutating_input(self):
        original = list(self.records)
        result = query_window(self.records)

        self.assertEqual(result, original)
        self.assertIsNot(result, self.records)
        self.assertEqual(self.records, original)

    def test_rejects_invalid_arguments(self):
        for name in ("start", "stop", "limit"):
            for value in (-1, True, False, 1.5, "1"):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError):
                        query_window(self.records, **{name: value})

    def test_rejects_start_after_stop(self):
        with self.assertRaises(ValueError):
            query_window(self.records, start=6, stop=5)

    def test_export_lines_uses_sequence_window(self):
        self.assertEqual(
            export_lines(self.records, start=2, stop=9, limit=2),
            "row 2\nrow 5",
        )


if __name__ == "__main__":
    unittest.main()
