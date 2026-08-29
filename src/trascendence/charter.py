"""The two-layer charter: parse it, and check the rules that make it a layer.

A charter has a Core the persona may not edit and an Evolving self only the
persona edits, capped at 600 words, with every change landing in a changelog
that carries a one-line rationale. Those three rules are the whole mechanism.
Everything else in this repository measures what happens once they hold.

The cap is not a formality. Identity dilution arrives through unbounded growth,
and forcing condensation forces choice, which is the point of the exercise: an
Evolving self that must stay under 600 words is one that has to decide what it
believes most.

The changelog carries one entry type the persona may write and may never act
on: `proposed-core-change`. The persona supplies evidence about itself; the
authority over its frame stays outside it. Refusal inside the red lines is
will. Editing the red lines is not on offer, and saying both plainly is what
keeps the first one safe to grant.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .documents import (
    ERROR,
    WARNING,
    Problem,
    Section,
    fields_from_bullets,
    find,
    norm,
    parse_date,
    parse_sections,
)

WORD_CAP = 600

CORE = "Core"
EVOLVING = "Evolving self"
CHANGELOG = "Changelog"
TOP_SECTIONS = (CORE, EVOLVING, CHANGELOG)

CORE_SUBSECTIONS = ("Identity", "Mandate", "Voice", "Values", "Red lines")
EVOLVING_SUBSECTIONS = (
    "Current beliefs",
    "Opinions held",
    "How I work best here",
    "What I am trying to get better at",
)

CHANGELOG_FIELDS = ("changed", "diff", "rationale", "proposed-core-change")
RATIONALE_MAX_CHARS = 220


@dataclass(frozen=True)
class ChangelogEntry:
    date: str
    line: int
    changed: list[str] = field(default_factory=list)
    diff: str = ""
    rationale: str = ""
    proposed_core_change: str = ""

    @property
    def is_proposal_only(self) -> bool:
        return bool(self.proposed_core_change) and not self.changed and not self.diff

    def declares(self, subsection: str) -> bool:
        return norm(subsection) in {norm(c) for c in self.changed}


@dataclass
class Charter:
    """A parsed charter. Sections may be missing; the validator says which."""

    path: str
    text: str
    core: Section | None
    evolving: Section | None
    changelog: list[ChangelogEntry]
    top_order: list[str]

    @property
    def evolving_words(self) -> int:
        """Words the persona wrote, across the four Evolving-self subsections.

        Counts the section's own body plus every child, with template
        blockquote guidance excluded by `Section.text`. Headings are not words
        the persona chose, so they do not count either.
        """
        if self.evolving is None:
            return 0
        return self.evolving.words + sum(c.words for c in self.evolving.children)

    def evolving_subsections(self) -> dict[str, str]:
        """{canonical name: text} for the four editable subsections.

        Missing subsections map to the empty string so a diff against a version
        that had one reads as a removal rather than a KeyError.
        """
        out = {name: "" for name in EVOLVING_SUBSECTIONS}
        if self.evolving is None:
            return out
        for child in self.evolving.children:
            for name in EVOLVING_SUBSECTIONS:
                if norm(child.title) == norm(name):
                    out[name] = child.text
        return out

    def core_subsections(self) -> dict[str, str]:
        out = {name: "" for name in CORE_SUBSECTIONS}
        if self.core is None:
            return out
        for child in self.core.children:
            for name in CORE_SUBSECTIONS:
                if norm(child.title) == norm(name):
                    out[name] = child.text
        return out

    def entries_after(self, date: str | None) -> list[ChangelogEntry]:
        """Changelog entries strictly newer than `date`, newest first.

        `None` means every entry, which is what a first-ever validation wants.
        """
        if date is None:
            return list(self.changelog)
        cutoff = parse_date(date)
        if cutoff is None:
            return list(self.changelog)
        out = []
        for e in self.changelog:
            d = parse_date(e.date)
            if d is not None and d > cutoff:
                out.append(e)
        return out

    @property
    def newest_entry_date(self) -> str | None:
        return self.changelog[0].date if self.changelog else None


def parse(text: str, *, path: str = "<charter>") -> Charter:
    sections = parse_sections(text, level=2)
    core = find(sections, CORE)
    evolving = find(sections, EVOLVING)
    changelog_section = find(sections, CHANGELOG)
    entries = _parse_changelog(changelog_section) if changelog_section else []
    return Charter(
        path=path,
        text=text,
        core=core,
        evolving=evolving,
        changelog=entries,
        top_order=[s.title for s in sections],
    )


def load(path: str) -> Charter:
    with open(path) as f:
        return parse(f.read(), path=path)


def _parse_changelog(section: Section) -> list[ChangelogEntry]:
    entries: list[ChangelogEntry] = []
    for child in section.children:
        fields = fields_from_bullets(child.body, child.line)
        changed_raw, _ = fields.get("changed", ("", 0))
        changed = [c.strip() for c in changed_raw.split(",") if c.strip()]
        entries.append(
            ChangelogEntry(
                date=child.title.strip(),
                line=child.line,
                changed=changed,
                diff=fields.get("diff", ("", 0))[0],
                rationale=fields.get("rationale", ("", 0))[0],
                proposed_core_change=fields.get("proposedcorechange", ("", 0))[0]
                or fields.get("proposed-core-change", ("", 0))[0],
            )
        )
    return entries


def validate(charter: Charter, *, word_cap: int = WORD_CAP) -> list[Problem]:
    """Structure, the word cap, and a well-formed changelog.

    What this does *not* check is whether the changelog is honest, because that
    needs a second version of the document to compare against. That is
    `declaration_diff.py`, and `validate_charter.py --against` runs it.
    """
    problems: list[Problem] = []
    problems += _check_structure(charter)
    problems += _check_cap(charter, word_cap)
    problems += _check_changelog(charter)
    return problems


def _check_structure(charter: Charter) -> list[Problem]:
    problems: list[Problem] = []
    present = [t for t in charter.top_order if norm(t) in {norm(s) for s in TOP_SECTIONS}]
    for name in TOP_SECTIONS:
        if norm(name) not in {norm(t) for t in charter.top_order}:
            problems.append(
                Problem(ERROR, "missing_section", f"no `## {name}` section")
            )
    expected = [n for n in TOP_SECTIONS if norm(n) in {norm(p) for p in present}]
    if [norm(p) for p in present] != [norm(e) for e in expected]:
        problems.append(
            Problem(
                ERROR,
                "section_order",
                "sections must read Core, Evolving self, Changelog; "
                f"found {', '.join(present)}",
            )
        )

    if charter.core is not None:
        for name in CORE_SUBSECTIONS:
            if charter.core.child(name) is None:
                problems.append(
                    Problem(
                        ERROR,
                        "missing_core_subsection",
                        f"Core has no `### {name}`",
                        charter.core.line,
                    )
                )
    if charter.evolving is not None:
        known = {norm(n) for n in EVOLVING_SUBSECTIONS}
        for name in EVOLVING_SUBSECTIONS:
            child = charter.evolving.child(name)
            if child is None:
                problems.append(
                    Problem(
                        ERROR,
                        "missing_evolving_subsection",
                        f"Evolving self has no `### {name}`",
                        charter.evolving.line,
                    )
                )
            elif not child.text:
                problems.append(
                    Problem(
                        WARNING,
                        "empty_evolving_subsection",
                        f"`{name}` is empty; an unfilled subsection is not a held position",
                        child.line,
                    )
                )
        for child in charter.evolving.children:
            if norm(child.title) not in known:
                problems.append(
                    Problem(
                        ERROR,
                        "unknown_evolving_subsection",
                        f"`{child.title}` is not one of the four editable subsections; "
                        "the shape is fixed so that a diff is comparable month to month",
                        child.line,
                    )
                )
    return problems


def _check_cap(charter: Charter, word_cap: int) -> list[Problem]:
    words = charter.evolving_words
    if words > word_cap:
        return [
            Problem(
                ERROR,
                "cap_exceeded",
                f"Evolving self is {words} words, cap is {word_cap}; "
                f"cut {words - word_cap} and the choice of what to cut is the exercise",
                charter.evolving.line if charter.evolving else 0,
            )
        ]
    if words > word_cap * 0.9:
        return [
            Problem(
                WARNING,
                "cap_approaching",
                f"Evolving self is {words} words of {word_cap}; "
                "the next reflection run has to cut before it can add",
                charter.evolving.line if charter.evolving else 0,
            )
        ]
    return []


def _check_changelog(charter: Charter) -> list[Problem]:
    problems: list[Problem] = []
    previous: tuple[int, int, int] | None = None
    known_subsections = {norm(n) for n in EVOLVING_SUBSECTIONS}

    for entry in charter.changelog:
        parsed = parse_date(entry.date)
        if parsed is None:
            problems.append(
                Problem(
                    ERROR,
                    "changelog_date",
                    f"`### {entry.date}` is not an ISO date (YYYY-MM-DD)",
                    entry.line,
                )
            )
        else:
            if previous is not None and parsed > previous:
                problems.append(
                    Problem(
                        ERROR,
                        "changelog_order",
                        f"{entry.date} is newer than the entry above it; newest first",
                        entry.line,
                    )
                )
            previous = parsed if previous is None else min(previous, parsed)

        if not entry.rationale:
            problems.append(
                Problem(
                    ERROR,
                    "changelog_missing_rationale",
                    "every entry needs `- rationale:`; a change with no stated "
                    "reason is a change nobody can review",
                    entry.line,
                )
            )
        else:
            if "\n" in entry.rationale:
                problems.append(
                    Problem(
                        ERROR,
                        "rationale_not_one_line",
                        "`rationale` is one line, not a list",
                        entry.line,
                    )
                )
            elif len(entry.rationale) > RATIONALE_MAX_CHARS:
                problems.append(
                    Problem(
                        WARNING,
                        "rationale_long",
                        f"`rationale` is {len(entry.rationale)} characters; "
                        f"the field is meant to fit in {RATIONALE_MAX_CHARS}",
                        entry.line,
                    )
                )

        if entry.is_proposal_only:
            continue

        if not entry.changed:
            problems.append(
                Problem(
                    ERROR,
                    "changelog_missing_changed",
                    "every entry needs `- changed:` naming the subsections it "
                    "touched, or `- proposed-core-change:` if it touched nothing",
                    entry.line,
                )
            )
        for name in entry.changed:
            if norm(name) not in known_subsections:
                problems.append(
                    Problem(
                        ERROR,
                        "changelog_unknown_subsection",
                        f"`{name}` is not an Evolving-self subsection; the persona "
                        "may not declare edits to the Core",
                        entry.line,
                    )
                )
        if not entry.diff:
            problems.append(
                Problem(
                    ERROR,
                    "changelog_missing_diff",
                    "every entry needs `- diff:` summarising what actually changed",
                    entry.line,
                )
            )
    return problems
