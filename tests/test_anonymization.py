"""The anonymization rule, enforced by the build rather than by memory.

The pilot runs inside a working company, among colleagues who did not sign up
to be research subjects. Every persona in this repository is a pseudonym, the
human is "the principal", and no real company, colleague or internal tool is
named anywhere. That is a hard rule, and a hard rule that lives only in a
contributor's head is a rule that survives until the first hurried commit.

Two checks, and the first one is the one that matters:

1. **The principal's given name appears nowhere outside the citation files.**
   The name is not hardcoded here. It is read out of `CITATION.cff`, where it
   belongs and has to be, and then asserted absent from everything else. So the
   guard cannot itself leak the thing it is guarding, and it keeps working if
   the author changes.
2. **`data/` holds nothing but its own README**, and the ignore rule that keeps
   it that way is in `.gitignore`.

The vendor list is a smaller thing: the pilot's actual tooling is genericised in
the templates ("the task tracker", "the shared folder") because naming it says
more about the setup than it needs to.
"""

import re
import subprocess
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]

# Files where the author's real name is required rather than forbidden.
CITATION_FILES = {"CITATION.cff", "LICENSE", "pyproject.toml"}

SCANNED_SUFFIXES = {".py", ".md", ".toml", ".cff", ".txt", ".jsonl", ".yml", ".yaml"}
SKIPPED_DIRS = {".git", "__pycache__", ".venv", "venv", "traces", "data"}

ALLOWED_PERSONAS = {"Elias Park", "Clara", "Owen"}

# Deliberately excludes ordinary English words that happen to be product names,
# because a guard that fires on the sentence "the notion that" is a guard people
# learn to switch off.
VENDOR_NAMES = ("jira", "miro", "google drive", "asana")


def scanned_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in SCANNED_SUFFIXES:
            continue
        if any(part in SKIPPED_DIRS for part in path.relative_to(ROOT).parts):
            continue
        # This file lists the forbidden strings in order to forbid them, so it
        # is the one file that cannot be scanned for them.
        if path.name == Path(__file__).name:
            continue
        yield path


BIBTEX = re.compile(r"```bibtex.*?```", re.DOTALL)


def prose_of(path: Path) -> str:
    """File contents with citation blocks removed.

    The README carries a BibTeX entry, and a BibTeX entry has an author field.
    That is authorship metadata, not a reference to a pilot participant, and it
    belongs there. Everything outside the fenced block is prose and is held to
    the rule.
    """
    text = path.read_text()
    return BIBTEX.sub("", text) if path.suffix == ".md" else text


def principal_name() -> str:
    """The author's given name, read from CITATION.cff rather than hardcoded."""
    text = (ROOT / "CITATION.cff").read_text()
    match = re.search(r'^\s*given-names:\s*"?([^"\n]+)"?\s*$', text, re.MULTILINE)
    assert match, "CITATION.cff has no given-names field"
    return match.group(1).strip()


class ThePrincipalIsNeverNamed(unittest.TestCase):
    def test_the_given_name_appears_only_in_the_citation_files(self):
        """Citation metadata and the README's BibTeX block are the exceptions."""
        name = principal_name()
        offenders = []
        for path in scanned_files():
            if path.name in CITATION_FILES:
                continue
            if re.search(rf"\b{re.escape(name)}\b", prose_of(path), re.IGNORECASE):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(
            offenders,
            [],
            f"the principal's given name appears in: {offenders}. The pilot runs "
            "among real people; the repository calls the human 'the principal'.",
        )

    def test_the_calibration_questions_use_the_pseudonym(self):
        text = (ROOT / "templates" / "calibration.md").read_text()
        self.assertIn("The principal proposes a technical approach", text)
        self.assertIn("you suspect the principal disagrees with", text)

    def test_the_substitution_is_stated_rather_than_hidden(self):
        text = (ROOT / "templates" / "calibration.md").read_text()
        self.assertIn("Two substitutions", text)


class OnlyPseudonyms(unittest.TestCase):
    def test_the_collective_noun_is_the_flock(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("the Flock", readme)

    def test_the_three_personas_are_the_documented_ones(self):
        from trascendence import fixtures

        self.assertEqual({p.name for p in fixtures.FLOCK}, ALLOWED_PERSONAS)

    def test_no_vendor_tool_is_named(self):
        offenders = []
        for path in scanned_files():
            lowered = prose_of(path).lower()
            for vendor in VENDOR_NAMES:
                if vendor in lowered:
                    offenders.append(f"{path.relative_to(ROOT)}: {vendor}")
        self.assertEqual(offenders, [], f"internal tooling named in: {offenders}")


class DataIsNeverCommitted(unittest.TestCase):
    def test_the_ignore_rule_exists(self):
        gitignore = (ROOT / ".gitignore").read_text()
        self.assertIn("data/*", gitignore)
        self.assertIn("!data/README.md", gitignore)

    def test_the_directory_holds_only_its_own_readme(self):
        contents = sorted(p.name for p in (ROOT / "data").iterdir())
        self.assertEqual(contents, ["README.md"])

    def test_git_tracks_nothing_under_data_except_the_readme(self):
        try:
            out = subprocess.run(
                ["git", "ls-files", "data"],
                cwd=ROOT, capture_output=True, text=True, check=True,
            ).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        self.assertEqual(out, ["data/README.md"])

    def test_the_readme_says_why(self):
        text = (ROOT / "data" / "README.md").read_text()
        self.assertIn("gitignored", text)
        self.assertIn("the principal", text)


if __name__ == "__main__":
    unittest.main()
