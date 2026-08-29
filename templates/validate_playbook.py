#!/usr/bin/env python3
"""Validate a playbook library: five required fields, numbered steps, real dates.

    python3 templates/validate_playbook.py path/to/playbook.md
    python3 templates/validate_playbook.py playbook.md --json

Every entry needs `context`, `steps`, `why it works here`, `proven on` and
`date`. `steps` has to be a numbered list, so the playbook can be followed
rather than admired, and `proven on` has to name the task it worked on, so the
library stays a record of demonstrated capability rather than a wish list.

Exit code is 1 if there are errors, 0 otherwise.
"""

import argparse
import json
import sys

import _front_door  # noqa: F401

from trascendence import playbook as playbook_mod
from trascendence.documents import ERROR, render_problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("playbook")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    library = playbook_mod.load(args.playbook)
    problems = playbook_mod.validate(library)

    if args.json:
        print(
            json.dumps(
                {
                    "playbook": args.playbook,
                    "entries": len(library.playbooks),
                    "problems": [
                        {"level": p.level, "code": p.code, "message": p.message, "line": p.line}
                        for p in problems
                    ],
                },
                indent=2,
            )
        )
    else:
        print(render_problems(problems, title=f"PLAYBOOKS: {args.playbook}"))
        print(f"\nPlaybooks: {len(library.playbooks)}")
        for pb in library.playbooks:
            print(f"  {pb.fields.get('date', '?')}  {pb.title}  ({len(pb.steps)} steps)")

    return 1 if any(p.level == ERROR for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
