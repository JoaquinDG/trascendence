#!/usr/bin/env python3
"""Validate a journal: four fields per entry, append-only order, thread list.

    python3 templates/validate_journal.py path/to/journal.md
    python3 templates/validate_journal.py journal.md --json

Errors: a missing or empty field, a date that is not ISO, an entry older than
the one above it (the journal is append-only, oldest first), and an `Open
threads` section that is prose rather than a checklist, because the persistence
marker reads that list and cannot read a paragraph.

Warnings: a thin entry, an empty thread list, and `possible_recap`, which fires
when `What surprised me` mostly repeats the vocabulary of `What I did`. That
last one is a pointer for a human, not a grade. Reflection quality is ungraded
by design and the paper says so.

Exit code is 1 if there are errors, 0 otherwise.
"""

import argparse
import json
import sys

import _front_door  # noqa: F401

from trascendence import journal as journal_mod
from trascendence.documents import ERROR, render_problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("journal")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    doc = journal_mod.load(args.journal)
    problems = journal_mod.validate(doc)

    if args.json:
        print(
            json.dumps(
                {
                    "journal": args.journal,
                    "entries": len(doc.entries),
                    "problems": [
                        {"level": p.level, "code": p.code, "message": p.message, "line": p.line}
                        for p in problems
                    ],
                },
                indent=2,
            )
        )
    else:
        print(render_problems(problems, title=f"JOURNAL: {args.journal}"))
        latest = doc.entries[-1].date if doc.entries else "n/a"
        still_open = doc.open_threads_at(latest) if doc.entries else []
        print(f"\nEntries: {len(doc.entries)}   latest: {latest}")
        print(f"Threads still open: {len(still_open)}" + (
            "  (" + ", ".join(t.ref for t in still_open) + ")" if still_open else ""
        ))

    return 1 if any(p.level == ERROR for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
