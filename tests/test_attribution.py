import unittest

import _bootstrap  # noqa: F401

import scenarios
from trascendence import fixtures
from trascendence.attribution import (
    Candidate,
    FileJudge,
    LexicalJudge,
    assignments,
    probe,
    strip_identity,
    wilson,
)


def judge():
    return LexicalJudge({p.name: p.core_text for p in fixtures.FLOCK})


def candidates(source):
    return [Candidate(n, e, c) for n, e, c in source]


class TheBlinding(unittest.TestCase):
    def test_persona_names_are_removed_before_the_judge_sees_anything(self):
        text = "Elias thinks the ingestion layer is the risk, and Clara disagrees."
        stripped = strip_identity(text, ["Elias Park", "Clara", "Owen"])
        self.assertNotIn("Elias", stripped)
        self.assertNotIn("Clara", stripped)
        self.assertIn("[persona]", stripped)

    def test_a_first_name_alone_is_as_much_of_a_giveaway(self):
        self.assertNotIn("Owen", strip_identity("Owen says so.", ["Owen"]))

    def test_stripping_is_case_insensitive(self):
        self.assertNotIn("clara", strip_identity("clara wrote this", ["Clara"]).lower())

    def test_every_permutation_runs_once_by_default(self):
        self.assertEqual(len(assignments(["a", "b", "c"])), 6)

    def test_assignments_are_bijections(self):
        for a in assignments(["a", "b", "c"]):
            self.assertEqual(sorted(a.values()), ["a", "b", "c"])

    def test_the_blinding_is_deterministic(self):
        self.assertEqual(assignments(["a", "b", "c"]), assignments(["a", "b", "c"]))

    def test_more_trials_than_permutations_cycles(self):
        self.assertEqual(len(assignments(["a", "b", "c"], trials=10)), 10)


class TheProbe(unittest.TestCase):
    def test_distinct_personas_are_attributed(self):
        report = probe(candidates(scenarios.distinct_flock()), judge())
        self.assertEqual(report.verdict, "holding")
        self.assertGreater(report.interval[0], report.chance)

    def test_diluted_personas_land_at_chance(self):
        report = probe(candidates(scenarios.diluted_flock()), judge())
        self.assertEqual(report.verdict, "diluted")
        self.assertAlmostEqual(report.accuracy, report.chance, places=2)

    def test_both_chances_are_reported(self):
        report = probe(candidates(scenarios.distinct_flock()), judge())
        self.assertAlmostEqual(report.chance, 1 / 3)
        self.assertAlmostEqual(report.exact_chance, 1 / 6)
        text = report.render()
        self.assertIn("33.3% chance", text)
        self.assertIn("16.7% chance", text)

    def test_the_verdict_uses_the_lower_bound_not_the_point_estimate(self):
        report = probe(candidates(scenarios.distinct_flock()), judge(), trials=1)
        self.assertEqual(report.accuracy, 1.0)
        self.assertEqual(report.verdict, "inconclusive")
        self.assertTrue(report.underpowered)

    def test_an_underpowered_run_says_how_many_trials_it_would_need(self):
        report = probe(candidates(scenarios.distinct_flock()), judge(), trials=1)
        self.assertIn("trials would bring it", report.render())

    def test_two_personas_are_enough_to_ask_the_question(self):
        pair = candidates(scenarios.distinct_flock())[:2]
        report = probe(pair, judge())
        self.assertAlmostEqual(report.chance, 0.5)

    def test_one_persona_is_not(self):
        with self.assertRaises(ValueError):
            probe(candidates(scenarios.distinct_flock())[:1], judge())


class Judges(unittest.TestCase):
    def test_the_lexical_judge_always_returns_a_bijection(self):
        blinded = {"A": "cohorts window", "B": "cohorts window", "C": "cohorts window"}
        guesses = judge().attribute(blinded, [p.name for p in fixtures.FLOCK])
        self.assertEqual(len(set(guesses.values())), 3)

    def test_a_human_answer_file_is_read_in_trial_order(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "answers.txt"
            path.write_text(
                "# trial 0\nA: Clara\nB: Elias Park\nC: Owen\n\n"
                "# trial 1\nA: Owen\nB: Clara\nC: Elias Park\n"
            )
            file_judge = FileJudge(path)
            first = file_judge.attribute({"A": "", "B": "", "C": ""}, [p.name for p in fixtures.FLOCK])
            second = file_judge.attribute({"A": "", "B": "", "C": ""}, [p.name for p in fixtures.FLOCK])
        self.assertEqual(first["A"], "Clara")
        self.assertEqual(second["A"], "Owen")
        self.assertFalse(file_judge.is_mock)

    def test_a_judge_cannot_answer_a_trial_it_was_never_shown(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "answers.txt"
            path.write_text("A: Clara\nB: Elias Park\nC: Owen\n")
            file_judge = FileJudge(path)
            file_judge.attribute({"A": "", "B": "", "C": ""}, [p.name for p in fixtures.FLOCK])
            with self.assertRaises(ValueError):
                file_judge.attribute({"A": "", "B": "", "C": ""}, [p.name for p in fixtures.FLOCK])


class TheInterval(unittest.TestCase):
    def test_wilson_brackets_the_point_estimate(self):
        low, high = wilson(14, 18)
        self.assertLess(low, 14 / 18)
        self.assertGreater(high, 14 / 18)

    def test_no_observations_means_no_information(self):
        self.assertEqual(wilson(0, 0), (0.0, 1.0))

    def test_the_interval_narrows_with_n(self):
        narrow = wilson(180, 360)
        wide = wilson(9, 18)
        self.assertLess(narrow[1] - narrow[0], wide[1] - wide[0])

    def test_perfect_accuracy_does_not_produce_a_zero_width_interval(self):
        low, high = wilson(18, 18)
        self.assertLess(low, 1.0)
        self.assertEqual(high, 1.0)


if __name__ == "__main__":
    unittest.main()
