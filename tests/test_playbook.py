import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from trascendence import playbook
from trascendence.documents import ERROR

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "playbook.md"

GOOD = """## Vendor comparison at real volume

- context: A build-versus-buy question decided by our own usage shape.
- steps:
  1. Get the usage distribution first.
  2. Identify which axis each vendor prices on.
- why it works here: our volumes are lumpy, which is where list-price intuition is worst.
- proven on: the ingestion build-versus-buy comparison.
- date: 2026-08-31
"""


def codes(text):
    return {p.code for p in playbook.validate(playbook.parse(text))}


class ShippedTemplate(unittest.TestCase):
    def test_the_template_passes_its_own_validator(self):
        problems = playbook.validate(playbook.load(str(TEMPLATE)))
        self.assertEqual([p.render() for p in problems if p.level == ERROR], [])


class Fields(unittest.TestCase):
    def test_a_complete_entry_is_clean(self):
        self.assertEqual(codes(GOOD), set())

    def test_every_field_is_required(self):
        for field, line in (
            ("context", "- context: A build-versus-buy question decided by our own usage shape.\n"),
            ("proven on", "- proven on: the ingestion build-versus-buy comparison.\n"),
            ("date", "- date: 2026-08-31\n"),
        ):
            with self.subTest(field=field):
                self.assertIn("missing_field", codes(GOOD.replace(line, "")))

    def test_steps_must_be_numbered(self):
        text = GOOD.replace("  1. Get the usage distribution first.\n  2. Identify which axis each vendor prices on.\n",
                            "  - get the distribution\n  - work out the axis\n")
        self.assertIn("steps_not_numbered", codes(text))

    def test_steps_are_parsed(self):
        library = playbook.parse(GOOD)
        self.assertEqual(len(library.playbooks[0].steps), 2)

    def test_bad_date(self):
        self.assertIn("bad_date", codes(GOOD.replace("2026-08-31", "last August")))

    def test_duplicate_titles_warn(self):
        self.assertIn("duplicate_title", codes(GOOD + "\n" + GOOD))

    def test_an_empty_library_is_a_phase_one_state_not_an_error(self):
        problems = playbook.validate(playbook.parse("# Playbooks\n"))
        self.assertEqual([p.level for p in problems], ["warning"])


if __name__ == "__main__":
    unittest.main()
