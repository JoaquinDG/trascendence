import json
import unittest

import _bootstrap  # noqa: F401

from trascendence import fixtures
from trascendence.events import Event, load, parse, span_weeks, week_of


def line(**kw):
    base = {"date": "2026-08-03", "persona": "Elias Park", "type": "initiative"}
    return json.dumps({**base, **kw})


def codes(problems):
    return {p.code for p in problems}


class Parsing(unittest.TestCase):
    def test_a_healthy_line_parses(self):
        events, problems = parse([line(evidence="j-1")])
        self.assertEqual(len(events), 1)
        self.assertEqual(problems, [])

    def test_bad_json_is_reported_with_a_line_number(self):
        events, problems = parse(["{not json"])
        self.assertIn("bad_json", codes(problems))
        self.assertEqual(problems[0].line, 1)

    def test_missing_required_fields(self):
        _, problems = parse([json.dumps({"date": "2026-08-03"})])
        self.assertIn("missing_field", codes(problems))

    def test_unknown_type_is_refused(self):
        _, problems = parse([line(type="vibes")])
        self.assertIn("unknown_type", codes(problems))

    def test_bad_date(self):
        _, problems = parse([line(date="last tuesday")])
        self.assertIn("bad_date", codes(problems))

    def test_a_thread_event_without_a_ref_cannot_be_paired(self):
        _, problems = parse([line(type="thread_open")])
        self.assertIn("missing_thread_ref", codes(problems))

    def test_unknown_fields_warn_and_are_dropped(self):
        events, problems = parse([line(mood="pleased")])
        self.assertIn("unknown_field", codes(problems))
        self.assertEqual(len(events), 1)

    def test_blank_lines_are_ignored(self):
        events, problems = parse(["", line(), "   "])
        self.assertEqual(len(events), 1)
        self.assertEqual(problems, [])

    def test_events_come_back_in_date_order(self):
        events, _ = parse([line(date="2026-08-20"), line(date="2026-08-03")])
        self.assertEqual([e.date for e in events], ["2026-08-03", "2026-08-20"])

    def test_a_round_trip_through_a_file(self):
        import tempfile
        from pathlib import Path

        from trascendence.events import dump

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            dump(fixtures.healthy_events(), path)
            events, problems = load(path)
        self.assertEqual(problems, [])
        self.assertEqual(len(events), len(fixtures.healthy_events()))


class Weeks(unittest.TestCase):
    def test_week_index_is_zero_based_from_the_origin(self):
        origin = Event(date="2026-08-03", persona="p", type="initiative").ordinal
        self.assertEqual(week_of(Event(date="2026-08-03", persona="p", type="initiative"), origin), 0)
        self.assertEqual(week_of(Event(date="2026-08-10", persona="p", type="initiative"), origin), 1)
        self.assertEqual(week_of(Event(date="2026-08-24", persona="p", type="initiative"), origin), 3)

    def test_span_of_an_empty_log_is_one_week_not_zero(self):
        self.assertEqual(span_weeks([]), 1)

    def test_the_healthy_fixture_spans_four_weeks(self):
        self.assertEqual(span_weeks(fixtures.healthy_events()), 4)


class Schema(unittest.TestCase):
    def test_records_carry_the_schema_version(self):
        record = Event(date="2026-08-03", persona="p", type="initiative").as_record()
        self.assertEqual(record["schema"], "trascendence.event.v1")

    def test_the_schema_field_is_not_treated_as_an_unknown_field(self):
        _, problems = parse([json.dumps(Event(date="2026-08-03", persona="p", type="initiative").as_record())])
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
