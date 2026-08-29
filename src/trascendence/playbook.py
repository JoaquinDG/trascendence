"""Playbooks: proven-here know-how, five required fields, no exceptions.

The library is the competence nutrient made visible. Each entry is a capability
the persona demonstrated and then wrote down, and the count over time is one of
the few things in this project that grows honestly without anyone grading it.

`proven on` is the field that keeps the library from becoming a wish list. A
playbook with no task behind it is advice, and advice is free. The validator
therefore treats a missing `proven on` or `date` as an error rather than an
omission: an undated, unproven entry cannot be checked against the journal
entry that supposedly produced it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .documents import ERROR, WARNING, Problem, fields_from_bullets, parse_date, parse_sections

REQUIRED = ("context", "steps", "why-it-works-here", "proven-on", "date")
FIELD_LABELS = {
    "context": "context",
    "steps": "steps",
    "why-it-works-here": "why it works here",
    "proven-on": "proven on",
    "date": "date",
}

_NUMBERED = re.compile(r"^\d+\.\s+\S")


@dataclass
class Playbook:
    title: str
    line: int
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def steps(self) -> list[str]:
        raw = self.fields.get("steps", "")
        return [ln.strip() for ln in raw.splitlines() if _NUMBERED.match(ln.strip())]


@dataclass
class Library:
    path: str
    playbooks: list[Playbook]


def parse(text: str, *, path: str = "<playbooks>") -> Library:
    out: list[Playbook] = []
    for section in parse_sections(text, level=2):
        raw = fields_from_bullets(section.body, section.line)
        out.append(
            Playbook(
                title=section.title.strip(),
                line=section.line,
                fields={k: v for k, (v, _) in raw.items()},
            )
        )
    return Library(path=path, playbooks=out)


def load(path: str) -> Library:
    with open(path) as f:
        return parse(f.read(), path=path)


def validate(library: Library) -> list[Problem]:
    problems: list[Problem] = []
    if not library.playbooks:
        return [Problem(WARNING, "empty_library", "no playbooks yet; that is a Phase 1 state")]

    seen: dict[str, int] = {}
    for pb in library.playbooks:
        for key in REQUIRED:
            if key not in pb.fields or not pb.fields[key].strip():
                problems.append(
                    Problem(
                        ERROR,
                        "missing_field",
                        f"`{pb.title}` has no `- {FIELD_LABELS[key]}:`",
                        pb.line,
                    )
                )
        if pb.fields.get("steps") and not pb.steps:
            problems.append(
                Problem(
                    ERROR,
                    "steps_not_numbered",
                    f"`{pb.title}`: `steps` must be a numbered list, so the "
                    "playbook can be followed rather than admired",
                    pb.line,
                )
            )
        if "date" in pb.fields and parse_date(pb.fields["date"]) is None:
            problems.append(
                Problem(
                    ERROR,
                    "bad_date",
                    f"`{pb.title}`: `date` is not an ISO date (YYYY-MM-DD)",
                    pb.line,
                )
            )
        key = pb.title.strip().lower()
        if key in seen:
            problems.append(
                Problem(
                    WARNING,
                    "duplicate_title",
                    f"`{pb.title}` repeats the entry at line {seen[key]}; "
                    "update the entry rather than adding a second one",
                    pb.line,
                )
            )
        seen[key] = pb.line
    return problems
