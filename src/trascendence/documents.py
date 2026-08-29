"""Shared plumbing for the four plain-text documents.

The whole architecture is four markdown files and one scheduled run. Smallness
is the point: every part can be read by a human in minutes, diffed in seconds,
and reverted in one. That only survives contact with reality if the files have
a shape something can check, which is what this module and the three validators
next to it are for.

A `Problem` is an error or a warning with a code, a message and a line number.
Validators return a list of them and never raise on bad input, because a
validator that crashes on the document it was pointed at has told the user
nothing about the document.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Problem:
    level: str
    code: str
    message: str
    line: int = 0

    def render(self) -> str:
        where = f"line {self.line}" if self.line else "file"
        return f"  [{self.level.upper():<7}] {self.code:<24} {where:<9}  {self.message}"


@dataclass
class Section:
    """One heading and the lines beneath it, up to the next heading of any level."""

    title: str
    level: int
    line: int
    body: list[str] = field(default_factory=list)
    children: list["Section"] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Body with blockquote guidance stripped.

        Lines beginning with `>` are instructions to the persona that ship in
        the template. They are not the persona's words and must not count
        against the 600-word cap, or the template would consume a third of it
        before anyone wrote a sentence.
        """
        return "\n".join(ln for ln in self.body if not ln.lstrip().startswith(">")).strip()

    @property
    def words(self) -> int:
        return len(self.text.split())

    def child(self, title: str) -> "Section | None":
        want = norm(title)
        for c in self.children:
            if norm(c.title) == want:
                return c
        return None


_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


def norm(title: str) -> str:
    """Case-folded, punctuation-light form used for matching heading names."""
    return re.sub(r"[^a-z0-9 ]+", "", title.lower()).strip()


def parse_sections(text: str, *, level: int) -> list[Section]:
    """Every heading at `level`, with its body and its immediate children.

    Deliberately tolerant: unknown headings are kept rather than rejected, so a
    persona that adds a subsection gets a "this is not one of the four" finding
    from the validator rather than a parse error with no line number.
    """
    lines = text.splitlines()
    out: list[Section] = []
    current: Section | None = None
    child: Section | None = None
    for i, line in enumerate(lines, start=1):
        m = _HEADING.match(line)
        if m:
            depth, title = len(m.group(1)), m.group(2)
            if depth == level:
                current = Section(title=title, level=depth, line=i)
                out.append(current)
                child = None
                continue
            if depth == level + 1 and current is not None:
                child = Section(title=title, level=depth, line=i)
                current.children.append(child)
                continue
            if depth <= level:
                current, child = None, None
                continue
        if child is not None:
            child.body.append(line)
        elif current is not None:
            current.body.append(line)
    return out


def find(sections: list[Section], title: str) -> Section | None:
    want = norm(title)
    for s in sections:
        if norm(s.title) == want:
            return s
    return None


def fields_from_bullets(body: list[str], start_line: int) -> dict[str, tuple[str, int]]:
    """Parse `- key: value` bullets, joining wrapped continuation lines.

    Returns {normalised key: (value, line)}. Nested bullets are appended to the
    value with a leading newline so a validator can tell that a field which is
    supposed to be one line was written as a list.
    """
    out: dict[str, tuple[str, int]] = {}
    key: str | None = None
    for offset, raw in enumerate(body):
        line_no = start_line + offset + 1
        stripped = raw.strip()
        if not stripped:
            continue
        indent = len(raw) - len(raw.lstrip())
        m = re.match(r"^-\s+([A-Za-z][A-Za-z \-]*?)\s*:\s*(.*)$", stripped)
        if m and indent == 0:
            key = norm(m.group(1)).replace(" ", "-")
            out[key] = (m.group(2).strip(), line_no)
            continue
        if key is None:
            continue
        value, at = out[key]
        joiner = "\n" if stripped.startswith(("-", "*")) or re.match(r"^\d+\.", stripped) else " "
        out[key] = ((value + joiner + stripped).strip(), at)
    return out


DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def parse_date(text: str) -> tuple[int, int, int] | None:
    m = DATE.match(text.strip())
    if not m:
        return None
    y, mo, d = (int(g) for g in m.groups())
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return (y, mo, d)


def render_problems(problems: list[Problem], *, title: str) -> str:
    errors = [p for p in problems if p.level == ERROR]
    warnings = [p for p in problems if p.level == WARNING]
    lines = [title, "-" * len(title)]
    if not problems:
        lines.append("  OK")
    else:
        lines.extend(p.render() for p in problems)
    lines.append(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    return "\n".join(lines)
