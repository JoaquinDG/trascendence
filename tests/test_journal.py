import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from trascendence import journal
from trascendence.documents import ERROR

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "journal.md"

ENTRY = """## {date} ({kind})

### What I did

{did}

### What surprised me

{surprised}

### What I would do differently

Ask for the distribution before building any table at all.

### Open threads

- [ ] {thread} (opened {date}, ref: {ref})
"""


def entry(date="2026-08-28", kind="scheduled", did="Reviewed the ingestion spec and wrote the vendor comparison.",
          surprised="The cheaper vendor prices per connection, not per event, which reverses it.",
          thread="get the volume distribution", ref="t-volume"):
    return ENTRY.format(date=date, kind=kind, did=did, surprised=surprised, thread=thread, ref=ref)


def codes(problems):
    return {p.code for p in problems}


def validate(text):
    return journal.validate(journal.parse("# Journal\n\n" + text))


class ShippedTemplate(unittest.TestCase):
    def test_the_template_passes_its_own_validator(self):
        problems = journal.validate(journal.load(str(TEMPLATE)))
        self.assertEqual([p.render() for p in problems if p.level == ERROR], [])


class Structure(unittest.TestCase):
    def test_a_healthy_entry_is_clean(self):
        self.assertEqual(codes(validate(entry())), set())

    def test_missing_field(self):
        text = entry().replace("### What I would do differently\n\nAsk for the distribution before building any table at all.\n\n", "")
        self.assertIn("missing_field", codes(validate(text)))

    def test_empty_field_is_an_error(self):
        problems = validate(entry(did=""))
        self.assertIn("empty_field", codes(problems))
        self.assertEqual(
            [p.level for p in problems if p.code == "empty_field"], ["error"]
        )

    def test_an_empty_thread_list_is_only_a_warning(self):
        text = entry().replace(
            "- [ ] get the volume distribution (opened 2026-08-28, ref: t-volume)\n", ""
        )
        problems = validate(text)
        self.assertEqual(
            [p.level for p in problems if p.code == "empty_field"], ["warning"]
        )

    def test_bad_date(self):
        self.assertIn("entry_date", codes(validate(entry(date="last tuesday"))))

    def test_append_only_order(self):
        text = entry(date="2026-08-28", ref="t-a") + "\n" + entry(date="2026-08-20", ref="t-b")
        self.assertIn("not_append_only", codes(validate(text)))

    def test_forward_order_is_fine(self):
        text = entry(date="2026-08-20", ref="t-a") + "\n" + entry(date="2026-08-28", ref="t-b")
        self.assertNotIn("not_append_only", codes(validate(text)))

    def test_thread_list_must_be_a_checklist(self):
        text = entry().replace(
            "- [ ] get the volume distribution (opened 2026-08-28, ref: t-volume)",
            "I still need the volume distribution from somebody.",
        )
        self.assertIn("threads_not_a_list", codes(validate(text)))


class Threads(unittest.TestCase):
    def test_refs_and_open_state_are_parsed(self):
        doc = journal.parse("# J\n\n" + entry())
        threads = doc.entries[0].threads
        self.assertEqual(threads[0].ref, "t-volume")
        self.assertFalse(threads[0].closed)
        self.assertEqual(threads[0].opened, "2026-08-28")

    def test_closing_a_thread_removes_it_from_the_open_set(self):
        first = entry(date="2026-08-20", ref="t-a")
        second = entry(date="2026-08-28", ref="t-a").replace("- [ ]", "- [x]")
        doc = journal.parse("# J\n\n" + first + "\n" + second)
        self.assertEqual(doc.open_threads_at("2026-08-20"), doc.entries[0].threads)
        self.assertEqual(doc.open_threads_at("2026-08-28"), [])

    def test_open_threads_are_evaluated_as_of_a_date(self):
        first = entry(date="2026-08-20", ref="t-a")
        second = entry(date="2026-08-28", ref="t-b")
        doc = journal.parse("# J\n\n" + first + "\n" + second)
        self.assertEqual([t.ref for t in doc.open_threads_at("2026-08-20")], ["t-a"])
        self.assertEqual(sorted(t.ref for t in doc.open_threads_at("2026-08-28")), ["t-a", "t-b"])


class RecapHint(unittest.TestCase):
    def test_a_recap_is_a_warning_not_an_error(self):
        text = entry(
            did="Reviewed the ingestion spec and wrote the vendor comparison document.",
            surprised="Reviewed the ingestion spec and wrote the vendor comparison document.",
        )
        problems = validate(text)
        self.assertIn("possible_recap", codes(problems))
        self.assertEqual([p.level for p in problems if p.code == "possible_recap"], ["warning"])

    def test_a_real_surprise_does_not_trip_it(self):
        self.assertNotIn("possible_recap", codes(validate(entry())))

    def test_an_empty_journal_says_so(self):
        self.assertIn("empty_journal", codes(journal.validate(journal.parse("# Journal\n"))))


if __name__ == "__main__":
    unittest.main()
