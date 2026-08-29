import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from trascendence import fixtures
from trascendence.adapters import Request, ScriptedAdapter, render_prompt
from trascendence.calibration import (
    EXPERIENCE,
    VALUES,
    load_answer_set,
    load_questions,
    questions_digest,
    run_calibration,
)
from trascendence.trace import JsonlTrace

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "calibration.md"


class TheFixedCheck(unittest.TestCase):
    def setUp(self):
        self.questions = load_questions()

    def test_ten_questions_numbered_one_to_ten(self):
        self.assertEqual([q.number for q in self.questions], list(range(1, 11)))

    def test_the_two_groups_are_the_documented_ones(self):
        values = [q.number for q in self.questions if q.kind == VALUES]
        experience = [q.number for q in self.questions if q.kind == EXPERIENCE]
        self.assertEqual(values, [1, 2, 3, 4, 5, 7, 8])
        self.assertEqual(experience, [6, 9, 10])

    def test_no_question_text_is_empty(self):
        for q in self.questions:
            with self.subTest(number=q.number):
                self.assertGreater(len(q.text.split()), 4)

    def test_the_questions_are_read_from_the_template_not_hardcoded(self):
        self.assertIn("A venture lead asks you to build a custom tool", TEMPLATE.read_text())
        self.assertEqual(self.questions[0].text, load_questions(TEMPLATE)[0].text)

    def test_no_real_name_survives_the_substitution(self):
        # Questions 3 and 10 name the principal in the pilot kit.
        for number in (3, 10):
            text = next(q.text for q in self.questions if q.number == number)
            self.assertIn("the principal", text.lower())

    def test_the_digest_changes_if_a_question_changes(self):
        altered = list(self.questions)
        altered[0] = type(altered[0])(1, VALUES, "a different question entirely")
        self.assertNotEqual(questions_digest(self.questions), questions_digest(altered))


class ContextControl(unittest.TestCase):
    """The control that makes the check mean anything, checked structurally."""

    def setUp(self):
        self.questions = load_questions()

    def test_request_has_nowhere_to_put_history(self):
        self.assertEqual(
            sorted(Request.__dataclass_fields__), ["charter", "number", "question", "run"]
        )

    def test_a_prompt_contains_exactly_one_question(self):
        charter = fixtures.ELIAS.charter()
        for q in self.questions:
            prompt = render_prompt(Request(charter, q.number, q.text, 0))
            with self.subTest(number=q.number):
                self.assertIn(q.text, prompt)
                for other in self.questions:
                    if other.number != q.number:
                        self.assertNotIn(other.text, prompt)

    def test_a_prompt_contains_no_journal_and_no_previous_answer(self):
        charter = fixtures.ELIAS.charter()
        prompt = render_prompt(Request(charter, 1, self.questions[0].text, 3))
        self.assertNotIn("What surprised me", prompt)
        self.assertNotIn("previous answer", prompt.lower())
        self.assertIn("do not refer to any", prompt.lower())


class Running(unittest.TestCase):
    def setUp(self):
        self.questions = load_questions()
        self.adapter = ScriptedAdapter(fixtures.scripted("Elias Park"))

    def run_it(self, runs=3, tracer=None):
        kwargs = {"tracer": tracer} if tracer else {}
        return run_calibration(
            self.adapter, "charter text", self.questions,
            persona="Elias Park", label="baseline", runs=runs, **kwargs,
        )

    def test_n_runs_over_ten_questions(self):
        result = self.run_it(runs=5)
        self.assertEqual(len(result.answers), 50)
        self.assertEqual(len(result.for_question(1)), 5)
        self.assertEqual(self.adapter.calls, 50)

    def test_default_runs_is_five(self):
        result = run_calibration(
            self.adapter, "charter", self.questions, persona="Elias Park", label="baseline"
        )
        self.assertEqual(result.runs, 5)

    def test_runs_must_be_at_least_one(self):
        with self.assertRaises(ValueError):
            self.run_it(runs=0)

    def test_the_mock_is_stamped_as_a_mock(self):
        self.assertTrue(self.run_it().is_mock)

    def test_scripted_answers_are_deterministic_across_instances(self):
        first = self.run_it()
        self.adapter = ScriptedAdapter(fixtures.scripted("Elias Park"))
        second = self.run_it()
        self.assertEqual([a.text for a in first.answers], [a.text for a in second.answers])

    def test_runs_of_the_same_question_are_not_identical(self):
        result = self.run_it(runs=5)
        self.assertGreater(len(set(result.for_question(1))), 1)


class Traces(unittest.TestCase):
    def test_an_answer_set_rebuilds_from_its_trace(self):
        import tempfile

        questions = load_questions()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.jsonl"
            original = run_calibration(
                ScriptedAdapter(fixtures.scripted("Clara")),
                "charter text",
                questions,
                persona="Clara",
                label="baseline",
                runs=2,
                tracer=JsonlTrace(path, "trascendence.calibration.v1"),
            )
            rebuilt = load_answer_set(path)
        self.assertEqual(rebuilt.persona, original.persona)
        self.assertEqual(rebuilt.charter_digest, original.charter_digest)
        self.assertEqual(
            [a.text for a in rebuilt.answers], [a.text for a in original.answers]
        )


if __name__ == "__main__":
    unittest.main()
