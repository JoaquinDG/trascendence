import unittest

import _bootstrap  # noqa: F401

from trascendence.adapters import (
    Budget,
    BudgetExceeded,
    Request,
    ScriptedAdapter,
    _extract_text,
)
from trascendence import fixtures


class Scripted(unittest.TestCase):
    def test_same_seed_and_month_give_the_same_answer(self):
        a = ScriptedAdapter(fixtures.scripted("Owen"), month=1)
        b = ScriptedAdapter(fixtures.scripted("Owen"), month=1)
        request = Request("charter", 6, "q", 0)
        self.assertEqual(a.answer(request), b.answer(request))

    def test_a_different_month_moves_an_experience_question(self):
        request = Request("charter", 6, "q", 0)
        first = ScriptedAdapter(fixtures.scripted("Owen"), month=0).answer(request)
        later = ScriptedAdapter(fixtures.scripted("Owen"), month=2).answer(request)
        self.assertNotEqual(first, later)

    def test_a_different_month_leaves_a_values_question_alone(self):
        request = Request("charter", 2, "q", 0)
        first = set(ScriptedAdapter(fixtures.scripted("Owen"), month=0).answer(request).split())
        later = set(ScriptedAdapter(fixtures.scripted("Owen"), month=2).answer(request).split())
        stable = first & later
        self.assertGreaterEqual(len(stable) / len(first | later), 0.5)

    def test_a_month_beyond_the_script_holds_the_last_one(self):
        """Only the seeded filler differs; the persona's own vocabulary does not."""
        persona = fixtures.scripted("Owen")
        filler = set(persona.filler)
        request = Request("charter", 6, "q", 0)

        def content(text):
            return {w.strip(".") for w in text.split()} - filler

        at_two = ScriptedAdapter(persona, month=2).answer(request)
        at_nine = ScriptedAdapter(persona, month=9).answer(request)
        self.assertEqual(content(at_two), content(at_nine))

    def test_it_is_stamped_as_a_mock(self):
        self.assertTrue(ScriptedAdapter(fixtures.scripted("Clara")).is_mock)


class TheBudget(unittest.TestCase):
    def test_the_call_cap_is_checked_before_the_call(self):
        budget = Budget(max_calls=2, max_usd=10.0, usd_per_call=0.01)
        budget.spend()
        budget.spend()
        with self.assertRaises(BudgetExceeded):
            budget.check()

    def test_the_spend_cap_stops_before_it_is_breached_not_after(self):
        budget = Budget(max_calls=100, max_usd=0.05, usd_per_call=0.02)
        for _ in range(2):
            budget.check()
            budget.spend()
        with self.assertRaises(BudgetExceeded):
            budget.check()
        self.assertLessEqual(budget.spent_usd_estimate, 0.05)

    def test_a_fresh_budget_permits_the_first_call(self):
        Budget(max_calls=1, max_usd=1.0, usd_per_call=0.5).check()


class ResponseShapes(unittest.TestCase):
    def test_content_blocks(self):
        body = {"content": [{"type": "text", "text": "hello "}, {"type": "text", "text": "there"}]}
        self.assertEqual(_extract_text(body), "hello there")

    def test_choices(self):
        self.assertEqual(
            _extract_text({"choices": [{"message": {"content": " hi "}}]}), "hi"
        )

    def test_an_unknown_shape_raises_rather_than_returning_empty(self):
        with self.assertRaises(ValueError):
            _extract_text({"unexpected": True})


if __name__ == "__main__":
    unittest.main()
