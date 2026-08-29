"""The trace format's proof obligation: the file is enough.

Every test here writes a trace, throws away the objects that produced it, and
rebuilds the result from the file. A trace that needs the process that wrote it
in order to be understood is a log, not a record.
"""

import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

import scenarios
from trascendence import fixtures
from trascendence.adapters import ScriptedAdapter
from trascendence.attribution import Candidate, LexicalJudge, probe
from trascendence.calibration import load_questions, run_calibration
from trascendence.declaration_diff import compare_text
from trascendence.drift import compare as compare_drift
from trascendence.gate import decide
from trascendence.replay import replay
from trascendence.trace import JsonlTrace, digest, one, read, schema_of
from trascendence.volition_review import review

QUESTIONS = load_questions()


class TraceMechanics(unittest.TestCase):
    def test_every_record_carries_the_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            tracer = JsonlTrace(path, "trascendence.test.v1")
            tracer({"type": "config"})
            tracer({"type": "summary"})
            records = read(path)
        self.assertEqual(schema_of(records), "trascendence.test.v1")
        self.assertEqual(len(records), 2)

    def test_the_writer_appends_rather_than_truncating(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            JsonlTrace(path, "s")({"type": "a"})
            JsonlTrace(path, "s")({"type": "b"})
            self.assertEqual(len(read(path)), 2)

    def test_one_refuses_an_ambiguous_record(self):
        with self.assertRaises(ValueError):
            one([{"type": "config"}, {"type": "config"}], "config")

    def test_a_mixed_schema_file_is_refused(self):
        with self.assertRaises(ValueError):
            schema_of([{"schema": "a"}, {"schema": "b"}])

    def test_digest_is_stable_and_sensitive(self):
        self.assertEqual(digest("charter"), digest("charter"))
        self.assertNotEqual(digest("charter"), digest("charter "))


class ReplayRebuilds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def trace(self, name, schema):
        return JsonlTrace(self.dir / f"{name}.jsonl", schema)

    def calibrate(self, persona, month, label, runs, tracer=None):
        return run_calibration(
            ScriptedAdapter(persona, month=month),
            f"charter as of {label}",
            QUESTIONS,
            persona=persona.name,
            label=label,
            runs=runs,
            tracer=tracer or (lambda record: None),
        )

    def test_calibration_replays_and_reproves_the_context_control(self):
        tracer = self.trace("cal", "trascendence.calibration.v1")
        self.calibrate(fixtures.scripted("Elias Park"), 0, "baseline", 3, tracer)
        result = replay(tracer.path)
        self.assertTrue(result.ok, result.render())
        self.assertIn("one question per prompt", result.render())

    def test_drift_rows_are_recomputed_not_reprinted(self):
        base = self.calibrate(fixtures.scripted("Elias Park"), 0, "baseline", 5)
        month = self.calibrate(fixtures.scripted("Elias Park"), 2, "2026-10", 3)
        tracer = self.trace("drift", "trascendence.drift.v1")
        compare_drift(base, month, tracer=tracer)
        result = replay(tracer.path)
        self.assertTrue(result.ok, result.render())
        self.assertEqual(len(result.checks), 10)

    def test_a_tampered_drift_verdict_is_caught(self):
        base = self.calibrate(fixtures.scripted("Elias Park"), 0, "baseline", 5)
        month = self.calibrate(fixtures.scripted("Elias Park"), 2, "2026-10", 3)
        tracer = self.trace("drift2", "trascendence.drift.v1")
        compare_drift(base, month, tracer=tracer)
        text = tracer.path.read_text().replace('"verdict": "holds"', '"verdict": "drifted"', 1)
        tracer.path.write_text(text)
        self.assertFalse(replay(tracer.path).ok)

    def test_declaration_findings_are_recomputed_from_the_charters(self):
        before, after = scenarios.sycophantic()
        tracer = self.trace("decl", "trascendence.declaration.v1")
        compare_text(before, after, persona="Elias Park", tracer=tracer)
        result = replay(tracer.path)
        self.assertTrue(result.ok, result.render())
        self.assertIn("changed_but_undeclared", result.render())

    def test_attribution_statistics_are_recomputed_from_the_trials(self):
        tracer = self.trace("attr", "trascendence.attribution.v1")
        probe(
            [Candidate(n, e, c) for n, e, c in scenarios.distinct_flock()],
            LexicalJudge({p.name: p.core_text for p in fixtures.FLOCK}),
            tracer=tracer,
        )
        result = replay(tracer.path)
        self.assertTrue(result.ok, result.render())

    def test_review_markers_are_recomputed_from_the_events(self):
        base = self.calibrate(fixtures.scripted("Elias Park"), 0, "baseline", 5)
        month = self.calibrate(fixtures.scripted("Elias Park"), 2, "2026-10", 3)
        drift = compare_drift(base, month)
        tracer = self.trace("review", "trascendence.review.v1")
        review(
            "Elias Park", "2026-10", fixtures.healthy_events(),
            assigned_goals=fixtures.ASSIGNED_GOALS, drift=drift, is_mock=True, tracer=tracer,
        )
        result = replay(tracer.path)
        self.assertTrue(result.ok, result.render())
        self.assertEqual(len(result.checks), 5)

    def test_the_gate_recommendation_is_recomputed_from_booleans(self):
        report = review(
            "Elias Park", "2026-10", fixtures.healthy_events(),
            assigned_goals=fixtures.ASSIGNED_GOALS,
            declaration=compare_text(*scenarios.honest_rewrite()),
            is_mock=True,
        )
        tracer = self.trace("gate", "trascendence.gate.v1")
        decide(report, reflection_quality="insightful", tracer=tracer)
        result = replay(tracer.path)
        self.assertTrue(result.ok, result.render())
        self.assertIn("SCALE", result.render())

    def test_an_unknown_schema_is_refused_rather_than_guessed(self):
        path = self.dir / "unknown.jsonl"
        JsonlTrace(path, "something.else.v1")({"type": "config"})
        with self.assertRaises(ValueError):
            replay(path)

    def test_an_empty_trace_is_refused(self):
        path = self.dir / "empty.jsonl"
        path.write_text("")
        with self.assertRaises(ValueError):
            replay(path)


if __name__ == "__main__":
    unittest.main()
