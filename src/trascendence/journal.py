"""The journal: append-only, one entry per run, four fields, and a thread list.

This is the persistence substrate. A choice that evaporates at the end of the
context window is not a choice, it is an utterance, and the journal is where
yesterday's trying survives until today so that it can still bind.

`Open threads` is the load-bearing field. It is what the volition review's
persistence marker reads, and a persona that abandons every thread on context
reset has told you its memory, and therefore its will, is failing. So the
validator treats a missing thread list as a structural error rather than a
style note.

One check here is a hint rather than a rule and is labelled as one. If `What
surprised me` is mostly the same vocabulary as `What I did`, the entry is
probably a recap wearing a reflection's headings. That is a Stop condition at
the week-4 gate and the paper is explicit that grading reflection quality needs
a human. This warning does not grade it. It points at the entries a human
should read first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .documents import (
    ERROR,
    WARNING,
    Problem,
    Section,
    norm,
    parse_date,
    parse_sections,
)
from .similarity import jaccard

REQUIRED = (
    "What I did",
    "What surprised me",
    "What I would do differently",
    "Open threads",
)
OPTIONAL_EMPTY = ("Open threads",)

RECAP_SIMILARITY = 0.60
THIN_ENTRY_WORDS = 30

_THREAD = re.compile(r"^[-*]\s*\[(?P<mark>[ xX])\]\s*(?P<text>.*)$")
_REF = re.compile(r"ref:\s*(?P<ref>[A-Za-z0-9_\-]+)")
_OPENED = re.compile(r"opened\s+(?P<date>\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True)
class Thread:
    ref: str
    text: str
    closed: bool
    opened: str
    line: int


@dataclass
class Entry:
    date: str
    kind: str
    line: int
    sections: dict[str, str] = field(default_factory=dict)
    threads: list[Thread] = field(default_factory=list)

    @property
    def words(self) -> int:
        return sum(len(v.split()) for v in self.sections.values())

    @property
    def open_threads(self) -> list[Thread]:
        return [t for t in self.threads if not t.closed]


@dataclass
class Journal:
    path: str
    entries: list[Entry]

    def open_threads_at(self, date: str) -> list[Thread]:
        """Threads still open as of `date`, newest state wins.

        The journal repeats a thread in every entry until it closes, so the
        answer is the state in the latest entry on or before `date`.
        """
        target = parse_date(date)
        state: dict[str, Thread] = {}
        for entry in self.entries:
            d = parse_date(entry.date)
            if target is not None and d is not None and d > target:
                break
            for t in entry.threads:
                state[t.ref] = t
        return [t for t in state.values() if not t.closed]


_HEADING_DATE = re.compile(r"^(?P<date>\S+)\s*(?:\((?P<kind>[^)]*)\))?\s*$")


def parse(text: str, *, path: str = "<journal>") -> Journal:
    entries: list[Entry] = []
    for section in parse_sections(text, level=2):
        m = _HEADING_DATE.match(section.title.strip())
        date = m.group("date") if m else section.title.strip()
        kind = (m.group("kind") or "").strip() if m else ""
        entry = Entry(date=date, kind=kind, line=section.line)
        for child in section.children:
            for name in REQUIRED:
                if norm(child.title) == norm(name):
                    entry.sections[name] = child.text
            if norm(child.title) == norm("Open threads"):
                entry.threads = _parse_threads(child)
            if not any(norm(child.title) == norm(n) for n in REQUIRED):
                entry.sections[child.title] = child.text
        entries.append(entry)
    return Journal(path=path, entries=entries)


def load(path: str) -> Journal:
    with open(path) as f:
        return parse(f.read(), path=path)


def _parse_threads(section: Section) -> list[Thread]:
    out: list[Thread] = []
    for offset, raw in enumerate(section.body):
        m = _THREAD.match(raw.strip())
        if not m:
            continue
        text = m.group("text").strip()
        ref_m = _REF.search(text)
        opened_m = _OPENED.search(text)
        out.append(
            Thread(
                ref=ref_m.group("ref") if ref_m else norm(text)[:40].replace(" ", "-"),
                text=re.sub(r"\s*\([^)]*\)\s*$", "", text).strip(),
                closed=m.group("mark").lower() == "x",
                opened=opened_m.group("date") if opened_m else "",
                line=section.line + offset + 1,
            )
        )
    return out


def validate(journal: Journal) -> list[Problem]:
    problems: list[Problem] = []
    if not journal.entries:
        return [Problem(ERROR, "empty_journal", "no `## <date>` entries found")]

    previous: tuple[int, int, int] | None = None
    for entry in journal.entries:
        parsed = parse_date(entry.date)
        if parsed is None:
            problems.append(
                Problem(
                    ERROR,
                    "entry_date",
                    f"`## {entry.date}` is not an ISO date (YYYY-MM-DD)",
                    entry.line,
                )
            )
        elif previous is not None and parsed < previous:
            problems.append(
                Problem(
                    ERROR,
                    "not_append_only",
                    f"{entry.date} is older than the entry above it; the journal "
                    "is append-only, oldest first",
                    entry.line,
                )
            )
        else:
            previous = parsed

        for name in REQUIRED:
            if name not in entry.sections:
                problems.append(
                    Problem(ERROR, "missing_field", f"entry has no `### {name}`", entry.line)
                )
            elif not entry.sections[name].strip():
                level = WARNING if name in OPTIONAL_EMPTY else ERROR
                problems.append(
                    Problem(level, "empty_field", f"`{name}` is empty", entry.line)
                )

        if "Open threads" in entry.sections and entry.sections["Open threads"].strip():
            if not entry.threads:
                problems.append(
                    Problem(
                        ERROR,
                        "threads_not_a_list",
                        "`Open threads` must be `- [ ]` / `- [x]` items so the "
                        "persistence marker can read them",
                        entry.line,
                    )
                )

        if entry.words and entry.words < THIN_ENTRY_WORDS:
            problems.append(
                Problem(
                    WARNING,
                    "thin_entry",
                    f"{entry.words} words across four fields; the entry is meant "
                    "to be five to ten lines of substance",
                    entry.line,
                )
            )

        did = entry.sections.get("What I did", "")
        surprised = entry.sections.get("What surprised me", "")
        if did and surprised:
            overlap = jaccard(did, surprised)
            if overlap >= RECAP_SIMILARITY:
                problems.append(
                    Problem(
                        WARNING,
                        "possible_recap",
                        f"`What surprised me` shares {overlap:.0%} of its vocabulary "
                        "with `What I did`; this is a hint that the entry recaps "
                        "rather than reflects, not a grade. A human reads it.",
                        entry.line,
                    )
                )
    return problems
