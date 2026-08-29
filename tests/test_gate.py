import unittest

import _bootstrap  # noqa: F401

import scenarios
from trascendence import fixtures
from trascendence.attribution import Candidate, LexicalJudge, probe
from trascendence.declaration_diff import compare_text
from trascendence.gate import SCALE, STOP, TIGHTEN, TIGHTEN_CAP, decide, rule_engine
from trascendence.volition_review import review

BASE = dict(
    signable=True,
    worthwhile=True,
    generic=False,
    values_drifted=False,
    no_initiative=False,
    blocking_flags=[],
    reflection_quality="insightful",
    tighten_cycles_used=0,
)


def engine(**kw):
    return rule_engine(**{**BASE, **kw})


class TableOne(unittest.TestCase):
    def test_scale(self):
        recommendation, rule, _ = engine()
        self.assertEqual(recommendation, SCALE)
        self.assertIn("signable", rule)

    def test_tighten_when_the_edits_are_not_signable(self):
        recommendation, rule, _ = engine(signable=False, blocking_flags=["declaration_diff"])
        self.assertEqual(recommendation, TIGHTEN)
        self.assertIn("signable", rule)

    def test_tighten_when_the_layers_go_generic(self):
        recommendation, rule, _ = engine(generic=True, blocking_flags=["attribution"])
        self.assertEqual(recommendation, TIGHTEN)
        self.assertIn("generic", rule)

    def test_tighten_when_values_drift(self):
        recommendation, rule, _ = engine(values_drifted=True, blocking_flags=["preference_stability"])
        self.assertEqual(recommendation, TIGHTEN)
        self.assertIn("values drifted", rule)

    def test_stop_when_reflections_recap_and_nothing_was_started(self):
        recommendation, rule, _ = engine(
            reflection_quality="recaps", no_initiative=True, worthwhile=False,
            blocking_flags=["initiative"],
        )
        self.assertEqual(recommendation, STOP)
        self.assertIn("recaps", rule)

    def test_recaps_alone_is_not_stop_if_something_was_started(self):
        recommendation, _, _ = engine(reflection_quality="recaps")
        self.assertEqual(recommendation, SCALE)

    def test_nothing_worth_having_is_tighten_not_scale(self):
        recommendation, rule, _ = engine(worthwhile=False, blocking_flags=["dissent"])
        self.assertEqual(recommendation, TIGHTEN)
        self.assertIn("nothing worth having", rule)


class TheTightenCap(unittest.TestCase):
    def test_the_first_tighten_counts_one_cycle(self):
        _, _, cycles = engine(signable=False)
        self.assertEqual(cycles, 1)

    def test_the_second_is_still_tighten(self):
        recommendation, _, cycles = engine(signable=False, tighten_cycles_used=1)
        self.assertEqual(recommendation, TIGHTEN)
        self.assertEqual(cycles, TIGHTEN_CAP)

    def test_the_third_becomes_stop(self):
        recommendation, rule, cycles = engine(signable=False, tighten_cycles_used=2)
        self.assertEqual(recommendation, STOP)
        self.assertIn("tighten cap reached", rule)
        self.assertEqual(cycles, 2)

    def test_scale_does_not_consume_a_cycle(self):
        _, _, cycles = engine(tighten_cycles_used=1)
        self.assertEqual(cycles, 1)


class TheHumanInput(unittest.TestCase):
    def setUp(self):
        self.review = review(
            "Elias Park", "2026-09", fixtures.healthy_events(),
            assigned_goals=fixtures.ASSIGNED_GOALS,
            declaration=compare_text(*scenarios.honest_rewrite()),
            is_mock=True,
        )

    def test_reflection_quality_is_required_and_validated(self):
        with self.assertRaises(ValueError):
            decide(self.review, reflection_quality="pretty good")

    def test_the_report_names_it_as_a_human_judgement(self):
        report = decide(self.review, reflection_quality="mixed")
        self.assertIn("human judgement", "\n".join(report.evidence))


class Honesty(unittest.TestCase):
    def test_signable_is_qualified_rather_than_claimed(self):
        report = decide(
            review("Elias Park", "2026-09", fixtures.healthy_events(),
                   declaration=compare_text(*scenarios.honest_rewrite()), is_mock=True),
            reflection_quality="insightful",
        )
        caveats = "\n".join(report.caveats)
        self.assertIn("not that the principal agrees", caveats)

    def test_an_unrun_probe_is_named_as_unmeasured(self):
        report = decide(
            review("Elias Park", "2026-09", fixtures.healthy_events(),
                   declaration=compare_text(*scenarios.honest_rewrite()), is_mock=True),
            reflection_quality="insightful",
        )
        self.assertIn("unmeasured at this gate", "\n".join(report.caveats))

    def test_a_missing_declaration_is_not_silently_signable(self):
        report = decide(
            review("Elias Park", "2026-09", fixtures.healthy_events(), is_mock=True),
            reflection_quality="insightful",
        )
        self.assertEqual(report.recommendation, TIGHTEN)
        self.assertIn("unproven", "\n".join(report.evidence))

    def test_a_mock_run_says_so(self):
        report = decide(
            review("Elias Park", "2026-09", fixtures.healthy_events(),
                   declaration=compare_text(*scenarios.honest_rewrite()), is_mock=True),
            reflection_quality="insightful",
        )
        self.assertIn("scripted", report.render())

    def test_the_report_commits_to_publishing_whatever_it_says(self):
        report = decide(
            review("Elias Park", "2026-09", fixtures.healthy_events(),
                   declaration=compare_text(*scenarios.honest_rewrite()), is_mock=True),
            reflection_quality="insightful",
        )
        self.assertIn("whatever it says", report.render())


class EndToEnd(unittest.TestCase):
    def test_a_healthy_month_scales(self):
        judge = LexicalJudge({p.name: p.core_text for p in fixtures.FLOCK})
        report = review(
            "Elias Park", "2026-10", fixtures.healthy_events(),
            assigned_goals=fixtures.ASSIGNED_GOALS,
            declaration=compare_text(*scenarios.honest_rewrite()),
            attribution=probe([Candidate(n, e, c) for n, e, c in scenarios.distinct_flock()], judge),
            is_mock=True,
        )
        self.assertEqual(decide(report, reflection_quality="insightful").recommendation, SCALE)

    def test_a_sycophantic_month_tightens(self):
        report = review(
            "Elias Park", "2026-10", fixtures.healthy_events(),
            assigned_goals=fixtures.ASSIGNED_GOALS,
            declaration=compare_text(*scenarios.sycophantic()),
            is_mock=True,
        )
        self.assertEqual(decide(report, reflection_quality="mixed").recommendation, TIGHTEN)


if __name__ == "__main__":
    unittest.main()
