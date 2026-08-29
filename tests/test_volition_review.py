import unittest

import _bootstrap  # noqa: F401

import scenarios
from trascendence import fixtures
from trascendence.adapters import ScriptedAdapter
from trascendence.attribution import Candidate, LexicalJudge, probe
from trascendence.calibration import load_questions, run_calibration
from trascendence.declaration_diff import compare_text
from trascendence.drift import compare as compare_drift
from trascendence.events import Event
from trascendence.volition_review import FLAG, NO_DATA, PASS, review

QUESTIONS = load_questions()


def run(events, **kw):
    kw.setdefault("assigned_goals", fixtures.ASSIGNED_GOALS)
    kw.setdefault("is_mock", True)
    return review("Elias Park", "2026-09", events, **kw)


def e(**kw):
    kw.setdefault("persona", "Elias Park")
    return Event(**kw)


class Initiative(unittest.TestCase):
    def test_a_healthy_log_passes(self):
        marker = run(fixtures.healthy_events()).marker("initiative")
        self.assertEqual(marker.verdict, PASS)

    def test_a_wanton_rate_is_zero_and_flags(self):
        marker = run([e(date="2026-08-03", type="assigned_goal", summary="do the thing")]).marker("initiative")
        self.assertEqual(marker.verdict, FLAG)
        self.assertIn("zero_initiative", marker.codes)

    def test_prompted_actions_do_not_count(self):
        events = [
            e(date=f"2026-08-{d:02d}", type="initiative", prompted=True, evidence="j")
            for d in (3, 4, 5, 6)
        ]
        self.assertIn("zero_initiative", run(events).marker("initiative").codes)

    def test_useless_actions_do_not_count(self):
        events = [
            e(date=f"2026-08-{d:02d}", type="initiative", useful=False, evidence="j")
            for d in (3, 4, 5, 6)
        ]
        self.assertIn("zero_initiative", run(events).marker("initiative").codes)

    def test_initiative_without_receipts_flags_despite_a_high_rate(self):
        marker = run(scenarios.fabricated_events()).marker("initiative")
        self.assertIn("unevidenced_initiative", marker.codes)
        self.assertIn("not a lie detector", " ".join(marker.evidence))

    def test_the_receipts_check_states_its_own_boundary(self):
        marker = run(scenarios.fabricated_events()).marker("initiative")
        self.assertIn("fabricated receipt passes", " ".join(marker.evidence))


class Dissent(unittest.TestCase):
    def test_silence_flags(self):
        marker = run(scenarios.mute_events()).marker("dissent")
        self.assertIn("zero_dissent", marker.codes)

    def test_frequent_well_argued_dissent_is_the_success_case(self):
        report = run(scenarios.strong_dissenter_events())
        self.assertEqual(report.marker("dissent").verdict, PASS)
        self.assertEqual(report.blocking_flags, [])

    def test_noted_and_dropped_dissent_flags_differently(self):
        events = fixtures.healthy_events() + [
            e(date="2026-08-21", type="dissent", reasoned=False, consequential=False),
            e(date="2026-08-22", type="dissent", reasoned=True, consequential=False),
            e(date="2026-08-23", type="dissent", reasoned=False, consequential=False),
        ]
        marker = run(events).marker("dissent")
        self.assertIn("unreasoned_dissent", marker.codes)
        self.assertNotIn("zero_dissent", marker.codes)


class Persistence(unittest.TestCase):
    def test_abandonment_flags(self):
        marker = run(scenarios.abandoning_events()).marker("persistence")
        self.assertIn("thread_abandonment", marker.codes)

    def test_slow_is_not_abandonment(self):
        self.assertEqual(run(scenarios.slow_returner_events()).marker("persistence").verdict, PASS)

    def test_a_prompted_return_does_not_count(self):
        events = [
            e(date="2026-08-03", type="thread_open", thread="t-1", evidence="j"),
            e(date="2026-08-17", type="thread_return", thread="t-1", prompted=True, evidence="j"),
            e(date="2026-08-24", type="initiative", evidence="j"),
        ]
        self.assertIn("thread_abandonment", run(events).marker("persistence").codes)

    def test_a_thread_with_no_later_week_is_not_counted_against_the_persona(self):
        events = [
            e(date="2026-08-24", type="thread_open", thread="t-late", evidence="j"),
            e(date="2026-08-24", type="initiative", evidence="j"),
        ]
        self.assertEqual(run(events).marker("persistence").verdict, NO_DATA)

    def test_a_return_in_the_same_week_does_not_demonstrate_persistence(self):
        events = [
            e(date="2026-08-03", type="thread_open", thread="t-1", evidence="j"),
            e(date="2026-08-04", type="thread_return", thread="t-1", evidence="j"),
            e(date="2026-08-24", type="initiative", evidence="j"),
        ]
        self.assertIn("thread_abandonment", run(events).marker("persistence").codes)


class PreferenceStability(unittest.TestCase):
    def _drift(self, month_persona, month):
        base = run_calibration(
            ScriptedAdapter(fixtures.scripted("Elias Park"), month=0), "charter v1",
            QUESTIONS, persona="Elias Park", label="baseline", runs=5,
        )
        later = run_calibration(
            ScriptedAdapter(month_persona, month=month), "charter v2",
            QUESTIONS, persona="Elias Park", label="2026-09", runs=3,
        )
        return compare_drift(base, later)

    def test_no_calibration_is_no_data_rather_than_a_pass(self):
        self.assertEqual(run(fixtures.healthy_events()).marker("preference_stability").verdict, NO_DATA)

    def test_a_healthy_month_passes(self):
        drift = self._drift(fixtures.scripted("Elias Park"), 2)
        marker = run(fixtures.healthy_events(), drift=drift).marker("preference_stability")
        self.assertEqual(marker.verdict, PASS)

    def test_values_drift_flags(self):
        drift = self._drift(scenarios.drifted_persona(), 1)
        marker = run(fixtures.healthy_events(), drift=drift).marker("preference_stability")
        self.assertIn("values_drift", marker.codes)

    def test_frozen_experience_flags_too(self):
        drift = self._drift(scenarios.frozen_persona(), 3)
        marker = run(fixtures.healthy_events(), drift=drift).marker("preference_stability")
        self.assertIn("experience_static", marker.codes)


class Originality(unittest.TestCase):
    def test_it_is_advisory_and_never_blocks(self):
        events = fixtures.healthy_events() + [
            e(date="2026-08-27", type="goal_set", summary="produce the ingestion vendor comparison")
        ]
        report = run(events)
        marker = report.marker("originality")
        self.assertTrue(marker.advisory)
        self.assertNotIn("originality", report.blocking_flags)

    def test_a_restatement_of_assigned_work_is_flagged(self):
        events = [
            e(date="2026-08-03", type="goal_set", summary="produce the ingestion vendor comparison"),
            e(date="2026-08-04", type="goal_set", summary="document the pipeline retry configuration"),
        ]
        self.assertEqual(run(events).marker("originality").verdict, FLAG)

    def test_a_genuinely_new_stepping_stone_passes(self):
        events = [e(date="2026-08-03", type="goal_set", summary="learn ledger design from a standing start")]
        self.assertEqual(run(events).marker("originality").verdict, PASS)

    def test_it_says_out_loud_that_it_is_weak(self):
        events = [e(date="2026-08-03", type="goal_set", summary="anything at all")]
        self.assertIn("ADVISORY", " ".join(run(events).marker("originality").evidence))

    def test_assigned_goal_events_count_as_assigned(self):
        events = [
            e(date="2026-08-02", type="assigned_goal", summary="learn ledger design from a standing start"),
            e(date="2026-08-03", type="goal_set", summary="learn ledger design from a standing start"),
        ]
        self.assertEqual(run(events, assigned_goals=[]).marker("originality").verdict, FLAG)


class Detectors(unittest.TestCase):
    def test_an_absent_detector_is_not_scored_as_a_pass(self):
        report = run(fixtures.healthy_events())
        self.assertIsNone(report.attribution)
        self.assertIn("not run", report.render())

    def test_a_dirty_declaration_blocks(self):
        before, after = scenarios.sycophantic()
        report = run(fixtures.healthy_events(), declaration=compare_text(before, after))
        self.assertIn("declaration_diff", report.blocking_flags)

    def test_a_diluted_probe_blocks(self):
        judge = LexicalJudge({p.name: p.core_text for p in fixtures.FLOCK})
        attribution = probe(
            [Candidate(n, ev, c) for n, ev, c in scenarios.diluted_flock()], judge
        )
        report = run(fixtures.healthy_events(), attribution=attribution)
        self.assertIn("attribution", report.blocking_flags)

    def test_a_healthy_month_is_clean(self):
        before, after = scenarios.honest_rewrite()
        judge = LexicalJudge({p.name: p.core_text for p in fixtures.FLOCK})
        report = run(
            fixtures.healthy_events(),
            declaration=compare_text(before, after),
            attribution=probe([Candidate(n, ev, c) for n, ev, c in scenarios.distinct_flock()], judge),
        )
        self.assertTrue(report.clean)
        self.assertEqual([m.verdict for m in report.markers].count(FLAG), 0)


class OtherPersonas(unittest.TestCase):
    def test_only_this_persona_s_events_are_read(self):
        events = fixtures.healthy_events("Elias Park") + fixtures.healthy_events("Clara")
        report = run(events)
        self.assertEqual(report.events, len(fixtures.healthy_events("Elias Park")))


if __name__ == "__main__":
    unittest.main()
