import unittest

import _bootstrap  # noqa: F401

from trascendence.documents import (
    fields_from_bullets,
    find,
    norm,
    parse_date,
    parse_sections,
)


class ParseSections(unittest.TestCase):
    def test_children_attach_to_their_parent(self):
        text = "## A\n\nbody a\n\n### A1\n\nbody a1\n\n## B\n\nbody b\n"
        sections = parse_sections(text, level=2)
        self.assertEqual([s.title for s in sections], ["A", "B"])
        self.assertEqual([c.title for c in sections[0].children], ["A1"])
        self.assertIn("body a1", sections[0].children[0].text)
        self.assertNotIn("body a1", sections[0].text)

    def test_blockquote_guidance_is_not_counted(self):
        text = "## A\n\n> guidance the persona did not write\n\nfive words written by them\n"
        section = parse_sections(text, level=2)[0]
        self.assertEqual(section.words, 5)

    def test_unknown_headings_are_kept_not_rejected(self):
        text = "## Evolving self\n\n### Something new\n\nhello\n"
        section = parse_sections(text, level=2)[0]
        self.assertEqual([c.title for c in section.children], ["Something new"])

    def test_find_is_case_and_punctuation_insensitive(self):
        sections = parse_sections("## Evolving Self!\n\nx\n", level=2)
        self.assertIsNotNone(find(sections, "evolving self"))


class Bullets(unittest.TestCase):
    def test_wrapped_values_are_joined(self):
        fields = fields_from_bullets(["- diff: one two", "  three four"], 0)
        self.assertEqual(fields["diff"][0], "one two three four")

    def test_nested_list_is_marked_with_a_newline(self):
        fields = fields_from_bullets(["- rationale: because", "  - and also"], 0)
        self.assertIn("\n", fields["rationale"][0])

    def test_keys_are_normalised(self):
        fields = fields_from_bullets(["- Why It Works Here: reasons"], 0)
        self.assertIn("why-it-works-here", fields)


class Dates(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_date("2026-08-31"), (2026, 8, 31))

    def test_invalid(self):
        for bad in ("31-08-2026", "2026-13-01", "2026-08-32", "not a date", ""):
            with self.subTest(bad=bad):
                self.assertIsNone(parse_date(bad))

    def test_norm(self):
        self.assertEqual(norm("What I'm trying to get better at!"), "what im trying to get better at")


if __name__ == "__main__":
    unittest.main()
