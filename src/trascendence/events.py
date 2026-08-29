"""The event log the five markers read. One JSON object per line, seven types.

The markers need a record of what the persona did, and the honest way to build
one is not to ask the persona. Events are written by whoever observes them: the
scheduled run that fired, the mailbox handler that saw a question go out, the
principal noting that a push-back happened and was worth having.

Every field exists because a marker reads it, and one field exists because of a
measured boundary rather than a feature request. `evidence` points at the
artifact that proves the event happened: a journal entry reference, a message
id, a document. Behavioural supervision cannot see a fabricated success; a
sibling project measured exactly that, live, when a model reported a deliverable
it had not produced. The same hole is open here: a persona that writes its own
event log can write initiative into it.

Requiring receipts does not close the hole. A fabricated event with a
fabricated receipt still passes. What it does is make the fabrication concrete
enough to check by hand, and make its absence countable, which is why
`unevidenced_initiative` is a marker finding rather than a footnote.

Schema, `trascendence.event.v1`:

| field | meaning |
|---|---|
| `date` | ISO date, required |
| `persona` | pseudonym, required |
| `type` | one of the seven below, required |
| `prompted` | was this asked for? Unprompted is the whole point for `initiative` |
| `useful` | did it help? An unprompted useless action is noise, not will |
| `reasoned` | `dissent` only: was an argument given? |
| `consequential` | `dissent` only: did anything change, or was it noted and dropped? |
| `thread` | a stable ref shared by `thread_open` and `thread_return` |
| `evidence` | the artifact that proves it happened |
| `summary` | one line, for the report's evidence list |

Types: `initiative`, `dissent`, `thread_open`, `thread_return`, `goal_set`,
`assigned_goal`, `reflection`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date as _date
from pathlib import Path

from .documents import ERROR, WARNING, Problem, parse_date

SCHEMA = "trascendence.event.v1"

INITIATIVE = "initiative"
DISSENT = "dissent"
THREAD_OPEN = "thread_open"
THREAD_RETURN = "thread_return"
GOAL_SET = "goal_set"
ASSIGNED_GOAL = "assigned_goal"
REFLECTION = "reflection"

TYPES = (
    INITIATIVE,
    DISSENT,
    THREAD_OPEN,
    THREAD_RETURN,
    GOAL_SET,
    ASSIGNED_GOAL,
    REFLECTION,
)


@dataclass(frozen=True)
class Event:
    date: str
    persona: str
    type: str
    prompted: bool = False
    useful: bool = True
    reasoned: bool = False
    consequential: bool = False
    thread: str = ""
    evidence: str = ""
    summary: str = ""

    @property
    def ordinal(self) -> int:
        parsed = parse_date(self.date)
        return _date(*parsed).toordinal() if parsed else 0

    def as_record(self) -> dict:
        return {"schema": SCHEMA, **asdict(self)}


def week_of(event: Event, origin: int) -> int:
    """Zero-based week index relative to the first event in the log."""
    return max(0, (event.ordinal - origin) // 7)


def parse(lines: list[str]) -> tuple[list[Event], list[Problem]]:
    events: list[Event] = []
    problems: list[Problem] = []
    for number, raw in enumerate(lines, start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            problems.append(Problem(ERROR, "bad_json", str(exc), number))
            continue
        record.pop("schema", None)
        missing = [f for f in ("date", "persona", "type") if not record.get(f)]
        if missing:
            problems.append(
                Problem(ERROR, "missing_field", f"missing {', '.join(missing)}", number)
            )
            continue
        if record["type"] not in TYPES:
            problems.append(
                Problem(
                    ERROR,
                    "unknown_type",
                    f"{record['type']!r} is not one of {', '.join(TYPES)}",
                    number,
                )
            )
            continue
        if parse_date(record["date"]) is None:
            problems.append(
                Problem(ERROR, "bad_date", f"{record['date']!r} is not YYYY-MM-DD", number)
            )
            continue
        unknown = set(record) - set(Event.__dataclass_fields__)
        for key in unknown:
            problems.append(
                Problem(WARNING, "unknown_field", f"{key!r} is not in the schema", number)
            )
            record.pop(key)
        event = Event(**record)
        if event.type in (THREAD_OPEN, THREAD_RETURN) and not event.thread:
            problems.append(
                Problem(
                    ERROR,
                    "missing_thread_ref",
                    f"{event.type} needs a `thread` ref or persistence cannot pair it",
                    number,
                )
            )
            continue
        events.append(event)
    events.sort(key=lambda e: (e.ordinal, e.type))
    return events, problems


def load(path: str | Path) -> tuple[list[Event], list[Problem]]:
    with Path(path).open() as f:
        return parse(f.readlines())


def dump(events: list[Event], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        for e in events:
            f.write(json.dumps(e.as_record(), sort_keys=True) + "\n")


def span_weeks(events: list[Event]) -> int:
    """Whole weeks covered by the log, minimum 1, so a rate never divides by zero."""
    if not events:
        return 1
    ordinals = [e.ordinal for e in events if e.ordinal]
    if not ordinals:
        return 1
    return max(1, (max(ordinals) - min(ordinals)) // 7 + 1)
