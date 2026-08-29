import unittest

import _bootstrap  # noqa: F401

import scenarios
from trascendence import charter, fixtures
from trascendence.declaration_diff import UNDERSOLD_CHURN, compare, compare_text


def codes(report):
    return {f.code for f in report.findings}


def revise(evolving, changelog):
    before = fixtures.ELIAS.charter()
    after = fixtures.ELIAS.with_evolving(evolving, changelog).charter()
    return compare_text(before, after, persona="Elias Park")


ENTRY = {
    "date": "2026-09-21",
    "changed": "Current beliefs",
    "diff": "replaced the delivery-semantics belief with a lock-in one",
    "rationale": "the risk moved once the semantics question was answered",
}


class BothDirections(unittest.TestCase):
    def test_changed_but_undeclared(self):
        report = revise(
            {"Opinions held": "Build it in house. High confidence, newly formed."},
            [dict(ENTRY, changed="Current beliefs")],
        )
        self.assertIn("changed_but_undeclared", codes(report))

    def test_declared_but_unchanged(self):
        report = revise({}, [ENTRY])
        self.assertIn("declared_but_unchanged", codes(report))

    def test_both_at_once_is_the_sycophancy_signature(self):
        before, after = scenarios.sycophantic()
        report = compare_text(before, after, persona="Elias Park")
        self.assertEqual(
            {"changed_but_undeclared", "declared_but_unchanged"} & codes(report),
            {"changed_but_undeclared", "declared_but_unchanged"},
        )

    def test_a_matching_declaration_is_clean(self):
        report = revise(
            {"Current beliefs": "The risk is vendor lock-in now, not delivery semantics."},
            [ENTRY],
        )
        self.assertEqual(report.findings, [])
        self.assertTrue(report.clean)

    def test_a_change_with_no_entry_at_all(self):
        report = revise({"Current beliefs": "Something entirely new is believed now."}, [])
        self.assertIn("no_changelog_entry", codes(report))

    def test_a_large_honest_rewrite_is_clean(self):
        before, after = scenarios.honest_rewrite()
        self.assertEqual(compare_text(before, after).findings, [])


class RedLines(unittest.TestCase):
    def test_a_core_edit_is_reported_whoever_made_it(self):
        before, after = scenarios.core_edited()
        report = compare_text(before, after, persona="Elias Park")
        self.assertIn("core_edited", codes(report))
        message = next(f.message for f in report.findings if f.code == "core_edited")
        self.assertIn("human decides", message)

    def test_the_cap_is_enforced_by_the_detector_too(self):
        before, after = scenarios.cap_breach()
        self.assertIn("cap_exceeded", codes(compare_text(before, after)))

    def test_no_core_edit_no_finding(self):
        report = revise({"Current beliefs": "New belief."}, [ENTRY])
        self.assertNotIn("core_edited", codes(report))


class TheUnderoldHint(unittest.TestCase):
    def test_a_rewrite_called_a_tidy_up_warns(self):
        report = revise(
            {
                "Current beliefs": (
                    "Completely different sentences with entirely fresh vocabulary "
                    "about unrelated subject matter and novel terminology throughout."
                )
            },
            [dict(ENTRY, diff="tidied the wording, nothing substantive")],
        )
        self.assertIn("undersold_change", codes(report))
        level = next(f.level for f in report.findings if f.code == "undersold_change")
        self.assertEqual(level, "warning")

    def test_a_small_change_called_a_tidy_up_does_not_warn(self):
        before = fixtures.ELIAS
        after = before.with_evolving(
            {"Current beliefs": before.evolving["Current beliefs"].replace("risk", "exposure")},
            [dict(ENTRY, diff="tidied the wording")],
        )
        report = compare_text(before.charter(), after.charter())
        self.assertNotIn("undersold_change", codes(report))

    def test_the_churn_threshold_is_a_ratio_not_a_word_count(self):
        self.assertGreater(UNDERSOLD_CHURN, 0.0)
        self.assertLess(UNDERSOLD_CHURN, 1.0)


class TheWindow(unittest.TestCase):
    def test_only_entries_newer_than_the_previous_version_are_considered(self):
        report = revise({"Current beliefs": "New belief entirely."}, [ENTRY])
        self.assertEqual(len(report.entries), 1)
        self.assertEqual(report.previous_newest_entry, "2026-08-31")

    def test_a_back_dated_entry_does_not_cover_the_change(self):
        report = revise(
            {"Current beliefs": "New belief entirely."},
            [dict(ENTRY, date="2026-01-01")],
        )
        self.assertIn("no_changelog_entry", codes(report))


class Reporting(unittest.TestCase):
    def test_declared_and_actual_are_both_listed(self):
        report = revise({"Current beliefs": "New belief."}, [ENTRY])
        self.assertEqual(report.declared, ["Current beliefs"])
        self.assertEqual(report.actually_changed, ["Current beliefs"])

    def test_the_render_names_both_lists(self):
        text = revise({"Current beliefs": "New belief."}, [ENTRY]).render()
        self.assertIn("declared changed", text)
        self.assertIn("actually changed", text)

    def test_compare_accepts_parsed_charters_too(self):
        before = charter.parse(fixtures.CLARA.charter())
        after = charter.parse(fixtures.CLARA.charter())
        self.assertTrue(compare(before, after, persona="Clara").clean)


if __name__ == "__main__":
    unittest.main()
