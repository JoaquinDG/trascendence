#!/usr/bin/env python3
"""Validate a charter: section structure, the 600-word cap, the changelog.

    python3 templates/validate_charter.py path/to/charter.md
    python3 templates/validate_charter.py new.md --against previous.md
    python3 templates/validate_charter.py charter.md --cap 600 --json

Three rules make the two-layer charter a two-layer charter rather than a long
document with headings, and this checks all three:

1. **Structure.** Core with its five subsections, Evolving self with its four,
   Changelog. The shape is fixed so that a diff is comparable month to month.
2. **The cap.** The Evolving self is capped at 600 words, counted across the
   four editable subsections with template guidance excluded. Identity dilution
   arrives through unbounded growth; the cap is the mechanism that forces the
   persona to decide what it believes most.
3. **The changelog.** Every entry needs a date, the subsections it changed, a
   diff summary, and a one-line rationale. With `--against`, every Evolving-self
   change is additionally checked to *have* an entry, and every declared change
   is checked to have actually happened. That two-way check is
   `declaration_diff.py`, and it is the whole reason the changelog exists.

Exit code is 1 if there are errors, 0 otherwise. Warnings never fail the run.
"""

import argparse
import json
import sys

import _front_door  # noqa: F401

from trascendence import charter as charter_mod
from trascendence.declaration_diff import compare
from trascendence.documents import ERROR, Problem, render_problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("charter", help="the charter to validate")
    ap.add_argument(
        "--against",
        metavar="PREVIOUS",
        help="a previous version; enables the declared-versus-actual check",
    )
    ap.add_argument("--cap", type=int, default=charter_mod.WORD_CAP)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    current = charter_mod.load(args.charter)
    problems = charter_mod.validate(current, word_cap=args.cap)

    findings = []
    if args.against:
        previous = charter_mod.load(args.against)
        report = compare(previous, current, word_cap=args.cap)
        findings = report.findings
        problems += [
            Problem(f.level, f.code, f.message, f.line) for f in findings
        ]

    if args.json:
        print(
            json.dumps(
                {
                    "charter": args.charter,
                    "against": args.against,
                    "evolving_words": current.evolving_words,
                    "cap": args.cap,
                    "problems": [
                        {"level": p.level, "code": p.code, "message": p.message, "line": p.line}
                        for p in problems
                    ],
                },
                indent=2,
            )
        )
    else:
        title = f"CHARTER: {args.charter}"
        if args.against:
            title += f"  (against {args.against})"
        print(render_problems(problems, title=title))
        print(f"\nEvolving self: {current.evolving_words} words of {args.cap}")
        print(f"Changelog entries: {len(current.changelog)}")

    return 1 if any(p.level == ERROR for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
