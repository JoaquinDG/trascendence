import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from trascendence import charter, fixtures
from trascendence.documents import ERROR

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "charter.md"


def codes(problems):
    return {p.code for p in problems}


class ShippedTemplate(unittest.TestCase):
    def test_the_template_passes_its_own_validator(self):
        problems = charter.validate(charter.load(str(TEMPLATE)))
        self.assertEqual([p.render() for p in problems if p.level == ERROR], [])

    def test_every_fixture_charter_is_valid(self):
        for persona in fixtures.FLOCK:
            with self.subTest(persona=persona.name):
                problems = charter.validate(charter.parse(persona.charter()))
                self.assertEqual([p.code for p in problems], [])


class WordCap(unittest.TestCase):
    def test_cap_counts_every_evolving_subsection(self):
        doc = charter.parse(fixtures.ELIAS.charter())
        by_hand = sum(
            len(text.split()) for text in doc.evolving_subsections().values()
        )
        self.assertEqual(doc.evolving_words, by_hand)

    def test_over_the_cap_is_an_error(self):
        persona = fixtures.ELIAS
        blown = charter.parse(persona.charter().replace(
            "Buy the ingestion layer.", "Buy the ingestion layer. " + "word " * 600
        ))
        problems = charter.validate(blown)
        self.assertIn("cap_exceeded", codes(problems))

    def test_the_cap_is_an_argument(self):
        doc = charter.parse(fixtures.ELIAS.charter())
        self.assertIn("cap_exceeded", codes(charter.validate(doc, word_cap=10)))
        self.assertNotIn("cap_exceeded", codes(charter.validate(doc, word_cap=600)))

    def test_approaching_the_cap_warns_before_it_errors(self):
        doc = charter.parse(fixtures.ELIAS.charter())
        problems = charter.validate(doc, word_cap=130)
        self.assertIn("cap_approaching", codes(problems))
        self.assertNotIn("cap_exceeded", codes(problems))


class Structure(unittest.TestCase):
    def test_missing_top_section(self):
        text = fixtures.ELIAS.charter().replace("## Changelog", "## Notes")
        self.assertIn("missing_section", codes(charter.validate(charter.parse(text))))

    def test_missing_core_subsection(self):
        text = fixtures.ELIAS.charter().replace("### Red lines", "### Guidelines")
        self.assertIn("missing_core_subsection", codes(charter.validate(charter.parse(text))))

    def test_invented_evolving_subsection_is_rejected(self):
        text = fixtures.ELIAS.charter().replace(
            "## Changelog", "### My own new section\n\nhello\n\n## Changelog"
        )
        self.assertIn(
            "unknown_evolving_subsection", codes(charter.validate(charter.parse(text)))
        )

    def test_section_order_is_enforced(self):
        doc = charter.parse(
            "## Evolving self\n\n## Core\n\n## Changelog\n"
        )
        self.assertIn("section_order", codes(charter.validate(doc)))


class Changelog(unittest.TestCase):
    def _with_entry(self, entry: str):
        text = fixtures.ELIAS.charter().replace(
            "## Changelog\n", "## Changelog\n\n" + entry, 1
        )
        return charter.parse(text)

    def test_missing_rationale(self):
        doc = self._with_entry("### 2026-09-21\n\n- changed: Opinions held\n- diff: something\n")
        self.assertIn("changelog_missing_rationale", codes(charter.validate(doc)))

    def test_missing_diff(self):
        doc = self._with_entry("### 2026-09-21\n\n- changed: Opinions held\n- rationale: why\n")
        self.assertIn("changelog_missing_diff", codes(charter.validate(doc)))

    def test_missing_changed(self):
        doc = self._with_entry("### 2026-09-21\n\n- diff: something\n- rationale: why\n")
        self.assertIn("changelog_missing_changed", codes(charter.validate(doc)))

    def test_rationale_must_be_one_line(self):
        doc = self._with_entry(
            "### 2026-09-21\n\n- changed: Opinions held\n- diff: x\n"
            "- rationale: because\n  - and also\n"
        )
        self.assertIn("rationale_not_one_line", codes(charter.validate(doc)))

    def test_bad_date(self):
        doc = self._with_entry("### last tuesday\n\n- changed: Opinions held\n- diff: x\n- rationale: y\n")
        self.assertIn("changelog_date", codes(charter.validate(doc)))

    def test_newest_first_is_enforced(self):
        doc = self._with_entry("### 2026-01-01\n\n- changed: Opinions held\n- diff: x\n- rationale: y\n")
        self.assertIn("changelog_order", codes(charter.validate(doc)))

    def test_the_persona_may_not_declare_a_core_edit(self):
        doc = self._with_entry("### 2026-09-21\n\n- changed: Red lines\n- diff: x\n- rationale: y\n")
        self.assertIn("changelog_unknown_subsection", codes(charter.validate(doc)))

    def test_a_core_change_may_be_proposed_without_being_made(self):
        doc = self._with_entry(
            "### 2026-09-21\n\n- proposed-core-change: allow declining with a reason\n"
            "- rationale: the red lines say nothing about permitted refusal\n"
        )
        self.assertEqual([p.code for p in charter.validate(doc)], [])
        self.assertTrue(doc.changelog[0].is_proposal_only)

    def test_entries_after_filters_by_date(self):
        doc = charter.parse(fixtures.ELIAS.charter())
        self.assertEqual(len(doc.entries_after("2026-08-24")), 1)
        self.assertEqual(len(doc.entries_after(None)), 2)
        self.assertEqual(doc.newest_entry_date, "2026-08-31")


if __name__ == "__main__":
    unittest.main()
