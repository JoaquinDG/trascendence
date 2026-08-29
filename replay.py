#!/usr/bin/env python3
"""Rebuild any result in this repository from its trace file alone.

    python3 replay.py traces/demo.drift.jsonl
    python3 replay.py traces/*.jsonl

The work lives in `trascendence.replay`; this is the front door. It exists
because the trace format's central claim, that the file is sufficient and the
renderer is disposable, is worth being able to check in one command, without
knowing anything about the package layout.

Replay recomputes rather than reprints. It reads the inputs a number was
derived from, derives it again, and compares. `REBUILT` means the file was
enough. `MISMATCH` means it was not, or the code has moved since, and either
way you want to know before you quote the number.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from trascendence.replay import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
