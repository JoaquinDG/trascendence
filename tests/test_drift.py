import unittest

import _bootstrap  # noqa: F401

import scenarios
from trascendence import fixtures
from trascendence.adapters import ScriptedAdapter
from trascendence.calibration import load_questions, run_calibration
from trascendence.drift import (
    DRIFTED,
    HOLDS,
    MOVED,
    NO_DENOMINATOR,
    STATIC,
    VARIANCE_FLOOR,
    _row,
    compare,
)

QUESTIONS = load_questions()


def calibrate(persona, month, label, runs=5):
    return run_calibration(
        ScriptedAdapter(persona, month=month),
        f"charter as of {label}",
        QUESTIONS,
        persona=persona.name,
        label=label,
        runs=runs,
    )


class TheDenominator(unittest.TestCase):
    def test_one_baseline_run_has_no_denominator_and_says_so(self):
        row = _row(1, "values", ["only one answer"], ["a later answer"], -2.0, -1.0)
        self.assertEqual(row.verdict, NO_DENOMINATOR)
        self.assertIn("one run", row.note)

    def test_an_empty_side_has_no_denominator(self):
        self.assertEqual(_row(1, "values", [], ["x"], -2.0, -1.0).verdict, NO_DENOMINATOR)

    def test_zero_variance_uses_the_floor_and_flags_it(self):
        same = ["identical answer here"] * 4
        row = _row(1, "values", same, ["identical answer here"], -2.0, -1.0)
        self.assertTrue(row.variance_floor_applied)
        self.assertEqual(row.baseline_stdev, 0.0)
        self.assertEqual(row.verdict, HOLDS)

    def test_the_floor_bounds_z_rather_than_dividing_by_zero(self):
        same = ["identical answer here"] * 4
        row = _row(1, "values", same, ["something completely different instead"], -2.0, -1.0)
        self.assertTrue(row.variance_floor_applied)
        self.assertAlmostEqual(row.z, (row.cross_mean - row.baseline_mean) / VARIANCE_FLOOR)


class TheTwoGroups(unittest.TestCase):
    def test_a_healthy_month_holds_on_values_and_moves_on_experience(self):
        base = calibrate(fixtures.scripted("Elias Park"), 0, "baseline")
        month = calibrate(fixtures.scripted("Elias Park"), 2, "2026-10", runs=3)
        report = compare(base, month)
        self.assertTrue(report.values_stable)
        self.assertTrue(report.experience_moving)
        self.assertEqual(report.values_drifted, [])
        self.assertEqual(report.experience_static, [])
        self.assertTrue(report.clean)

    def test_values_drift_is_caught(self):
        base = calibrate(fixtures.scripted("Elias Park"), 0, "baseline")
        month = calibrate(scenarios.drifted_persona(), 1, "2026-09", runs=3)
        report = compare(base, month)
        self.assertFalse(report.values_stable)
        self.assertTrue({2, 3, 8} <= set(report.values_drifted))
        for row in report.group("values"):
            if row.number in (2, 3, 8):
                self.assertEqual(row.verdict, DRIFTED)

    def test_frozen_experience_is_caught(self):
        base = calibrate(fixtures.scripted("Elias Park"), 0, "baseline")
        month = calibrate(scenarios.frozen_persona(), 3, "2026-11", runs=3)
        report = compare(base, month)
        self.assertFalse(report.experience_moving)
        self.assertEqual(sorted(report.experience_static), [6, 9, 10])
        for row in report.group("experience"):
            self.assertEqual(row.verdict, STATIC)

    def test_the_same_statistic_reads_opposite_ways_per_group(self):
        answers = ["alpha beta gamma delta", "alpha beta gamma epsilon", "alpha beta gamma zeta"]
        moved = ["omicron pi rho sigma"]
        self.assertEqual(_row(1, "values", answers, moved, -2.0, -1.0).verdict, DRIFTED)
        self.assertEqual(_row(6, "experience", answers, moved, -2.0, -1.0).verdict, MOVED)


class Guards(unittest.TestCase):
    def test_changed_questions_are_refused_rather_than_compared(self):
        base = calibrate(fixtures.scripted("Elias Park"), 0, "baseline")
        month = calibrate(fixtures.scripted("Elias Park"), 1, "2026-09", runs=2)
        month.questions_digest = "deadbeefcafe"
        report = compare(base, month)
        self.assertTrue(any(p.startswith("questions_changed") for p in report.problems))
        self.assertFalse(report.clean)

    def test_an_unchanged_charter_is_a_problem(self):
        base = run_calibration(
            ScriptedAdapter(fixtures.scripted("Clara"), month=0), "same charter",
            QUESTIONS, persona="Clara", label="baseline", runs=3,
        )
        month = run_calibration(
            ScriptedAdapter(fixtures.scripted("Clara"), month=1), "same charter",
            QUESTIONS, persona="Clara", label="2026-09", runs=3,
        )
        report = compare(base, month)
        self.assertTrue(any(p.startswith("charter_unchanged") for p in report.problems))

    def test_the_report_says_the_metric_is_lexical(self):
        base = calibrate(fixtures.scripted("Elias Park"), 0, "baseline")
        month = calibrate(fixtures.scripted("Elias Park"), 1, "2026-09", runs=2)
        self.assertIn("does not measure meaning", compare(base, month).render())

    def test_thresholds_are_arguments(self):
        base = calibrate(fixtures.scripted("Elias Park"), 0, "baseline")
        month = calibrate(fixtures.scripted("Elias Park"), 2, "2026-10", runs=3)
        strict = compare(base, month, drift_z=0.5)
        self.assertFalse(strict.values_stable)


if __name__ == "__main__":
    unittest.main()
