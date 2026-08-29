import unittest

import _bootstrap  # noqa: F401

from trascendence import similarity


class TheMetricSaysWhatItIs(unittest.TestCase):
    def test_measures_meaning_is_false_and_stays_false(self):
        """Pinned. Every surface that prints a similarity number reads this."""
        self.assertFalse(similarity.measures_meaning)

    def test_identical_text_scores_one(self):
        self.assertEqual(similarity.jaccard("the vendor prices per connection", "the vendor prices per connection"), 1.0)

    def test_disjoint_text_scores_zero(self):
        self.assertEqual(similarity.jaccard("alpha beta", "gamma delta"), 0.0)

    def test_two_empty_texts_are_the_same_text(self):
        self.assertEqual(similarity.jaccard("", ""), 1.0)

    def test_one_empty_text_is_not(self):
        self.assertEqual(similarity.jaccard("something", ""), 0.0)

    def test_the_documented_blind_spot_is_real(self):
        """Opposite conclusions, shared vocabulary, scored as similar.

        This is not a bug report, it is the limitation the module documents,
        pinned so nobody quietly starts treating the number as semantic.
        """
        a = "we should buy the ingestion layer rather than build it"
        b = "we should build the ingestion layer rather than buy it"
        self.assertGreater(similarity.jaccard(a, b), 0.9)

    def test_the_other_direction_too(self):
        a = "buy the ingestion layer"
        b = "purchase the data intake component"
        self.assertLess(similarity.jaccard(a, b), 0.2)


class Statistics(unittest.TestCase):
    def test_pairwise_covers_every_unordered_pair(self):
        self.assertEqual(len(similarity.pairwise(["a", "b", "c", "d"])), 6)

    def test_pairwise_of_one_text_is_empty(self):
        self.assertEqual(similarity.pairwise(["only one"]), [])

    def test_stdev_of_one_value_is_zero(self):
        self.assertEqual(similarity.stdev([0.5]), 0.0)

    def test_mean_of_nothing_is_zero(self):
        self.assertEqual(similarity.mean([]), 0.0)

    def test_stdev_matches_the_population_formula(self):
        self.assertAlmostEqual(similarity.stdev([1.0, 3.0]), 1.0)


class Normalisation(unittest.TestCase):
    def test_accents_and_case_fold(self):
        self.assertEqual(similarity.normalize("Café RESUMÉ"), "cafe resume")

    def test_stopwords_are_dropped(self):
        self.assertNotIn("the", similarity.tokens("the vendor"))
        self.assertIn("the", similarity.tokens("the vendor", drop_stopwords=False))

    def test_distinctive_finds_the_rare_words(self):
        mine = "cohorts payback window segmented"
        others = ["schema retries ingestion", "interviews acceptance criteria"]
        self.assertIn("cohorts", similarity.distinctive(mine, others, top=4))


if __name__ == "__main__":
    unittest.main()
