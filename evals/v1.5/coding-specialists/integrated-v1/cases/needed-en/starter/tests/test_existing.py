import unittest
from logquery import positional_slice


class LegacySlice(unittest.TestCase):
    def test_negative_position(self):
        self.assertEqual(positional_slice([7, 11, 20], -2, None), [11, 20])
