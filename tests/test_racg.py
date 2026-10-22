import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import racg


class Stub:
    def __init__(self, *calls):
        self.calls = iter(calls)
        self.observed = []

    def __call__(self, upper):
        expected_upper, value = next(self.calls)
        assert expected_upper == upper, (expected_upper, upper)
        assert 0 <= value < upper
        self.observed.append(upper)
        return value


class RACGTests(unittest.TestCase):
    def test_catalog_exactly_100(self):
        topics = racg.catalog()
        self.assertEqual(len(topics), 100)
        self.assertEqual(topics[86], "Convex hulls")

    def test_new_topic_rolls_O_X_Y_P(self):
        rng = Stub((100, 90), (100000, 75785), (100, 55), (100, 90))
        result = racg.draw(None, rng)
        self.assertEqual(result["rolls"], {"O": 91, "X": 75785, "Y": 56, "P": 91})
        self.assertEqual(result["topic_id"], 86)
        self.assertEqual(result["difficulty"], 3)  # fresh roll Y=56 starts Level 3
        self.assertFalse(result["story"])
        self.assertEqual(rng.observed, [100, 100000, 100, 100])

    def test_continue_no_X_and_retain_label(self):
        previous = {"topic_id": 86, "topic_label": "Missing Elements", "difficulty": 5}
        rng = Stub((100, 14), (13, 0), (100, 69))
        result = racg.draw(previous, rng)
        self.assertTrue(result["continuation"])
        self.assertIsNone(result["rolls"]["X"])
        self.assertEqual(result["topic_label"], "Missing Elements")
        self.assertTrue(result["historical_catalog_mismatch"])
        self.assertEqual(result["difficulty"], 5)
        self.assertTrue(result["story"])
        self.assertEqual(rng.observed, [100, 13, 100])

    def test_continuation_can_increase_difficulty(self):
        rng = Stub((100, 0), (70, 65), (100, 70))
        result = racg.draw({"topic_id": 3, "difficulty": 2}, rng)
        self.assertEqual(result["difficulty"], 6)
        self.assertEqual(result["presentation"], "direct")

    def test_first_roll_low_O_is_still_new_topic(self):
        rng = Stub((100, 0), (100000, 0), (100, 0), (100, 0))
        result = racg.draw(None, rng)
        self.assertFalse(result["continuation"])
        self.assertEqual(result["topic_id"], 1)
        self.assertEqual(result["difficulty"], 1)
        self.assertTrue(result["story"])

    def test_exact_weighted_distribution(self):
        self.assertEqual(racg.DIFFICULTY_WEIGHTS, (30, 25, 20, 12, 8, 5))
        counts = [sum(racg.difficulty_from_roll(y) == level for y in range(1, 101))
                  for level in range(1, 7)]
        self.assertEqual(tuple(counts), racg.DIFFICULTY_WEIGHTS)
        self.assertEqual([racg.difficulty_from_roll(y) for y in
                          (1, 30, 31, 55, 56, 75, 76, 87, 88, 95, 96, 100)],
                         [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6])

    def test_continuation_reweights_only_eligible_levels(self):
        for prior in range(1, 7):
            size = racg.difficulty_roll_size(prior)
            counts = {level: 0 for level in range(1, 7)}
            for y in range(1, size + 1):
                level = racg.difficulty_from_roll(y, prior)
                self.assertGreaterEqual(level, prior)
                counts[level] += 1
            self.assertEqual([counts[level] for level in range(1, 7)],
                             [0] * (prior - 1) + list(racg.DIFFICULTY_WEIGHTS[prior-1:]))
        self.assertEqual(racg.difficulty_roll_size(4), 25)

    def test_invalid_weighted_rolls_rejected(self):
        for min_level, y in [(1, 0), (1, 101), (4, 26), (6, 6)]:
            with self.assertRaises(ValueError):
                racg.difficulty_from_roll(y, min_level)
        for min_level in (0, 7, True):
            with self.assertRaises(ValueError):
                racg.difficulty_roll_size(min_level)

    def test_invalid_prior_state_is_rejected(self):
        with self.assertRaises(ValueError):
            racg.draw({"topic_id": 101, "difficulty": 1})


if __name__ == "__main__":
    unittest.main()
