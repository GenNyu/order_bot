import unittest

from duration import parse_duration


class ParseDurationTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_duration("45s"), 45)
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration("2h5s"), 7205)

    def test_days(self):
        self.assertEqual(parse_duration("1d"), 86400)
        self.assertEqual(parse_duration("1d2h"), 93600)
        self.assertEqual(parse_duration("2d3h4m5s"), 183845)

    def test_invalid(self):
        for bad in ["", "abc", "10x", "1h1h"]:
            with self.assertRaises(ValueError):
                parse_duration(bad)


if __name__ == "__main__":
    unittest.main()
