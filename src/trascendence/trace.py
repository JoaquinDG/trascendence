"""Append-only JSONL traces. The file is the record, the renderer is disposable.

Every tool in this repo writes one trace and every report can be rebuilt from
that trace by `replay.py` with no model call, no network, and no access to the
tool that produced it. The rule is stronger than "we log things": a trace has
to carry the *inputs* a derived number was computed from, not only the number,
so replay can recompute and compare rather than reprint.

That is what makes the traces worth trusting. A record that only contains
conclusions cannot be checked; a record that contains the inputs can be checked
by anyone, including someone who thinks the conclusion is wrong.

Schemas, one JSON object per line, `type` on every record:

| schema | records |
|---|---|
| `trascendence.calibration.v1` | `config`, one `answer` per (run, question), `summary` |
| `trascendence.drift.v1` | `config`, `inputs` (every answer compared), one `question` row each, `summary` |
| `trascendence.declaration.v1` | `config`, `inputs` (both charters, the changelog entry), one `finding` each, `summary` |
| `trascendence.attribution.v1` | `config`, `inputs` (the unlabeled texts), one `trial` each, `summary` |
| `trascendence.review.v1` | `config`, `inputs` (events, drift rows, detector findings), one `marker` each, `summary` |
| `trascendence.gate.v1` | `config`, `inputs` (the review summary), `evidence` lines, `recommendation` |

Real pilot traces contain real colleagues and belong under `data/`, which is
gitignored. The traces committed here are all synthetic.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterator

Tracer = Callable[[dict], None]


class JsonlTrace:
    """Append-only JSONL writer.

    Callable, so it drops straight into any `tracer=` parameter. Opens per
    write rather than holding a handle: a record that exists only in a buffer
    when the process dies is a record that was not written.
    """

    def __init__(self, path: str | Path, schema: str) -> None:
        self.path = Path(path)
        self.schema = schema
        self.records: list[dict] = []

    def __call__(self, record: dict) -> None:
        entry = {"schema": self.schema, **record}
        self.records.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")


def null_tracer(record: dict) -> None:
    """Discard. The default everywhere, so nothing writes to disk by accident."""


def read(path: str | Path) -> list[dict]:
    """Every record in a trace file, in order. Blank lines ignored."""
    out: list[dict] = []
    with Path(path).open() as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def records_of(trace: list[dict], type_: str) -> Iterator[dict]:
    for r in trace:
        if r.get("type") == type_:
            yield r


def one(trace: list[dict], type_: str) -> dict:
    """The single record of a type. Raises if there is not exactly one."""
    found = list(records_of(trace, type_))
    if len(found) != 1:
        raise ValueError(f"expected exactly one {type_!r} record, found {len(found)}")
    return found[0]


def schema_of(trace: list[dict]) -> str:
    schemas = {r.get("schema") for r in trace}
    if len(schemas) != 1:
        raise ValueError(f"trace mixes schemas: {sorted(str(s) for s in schemas)}")
    return schemas.pop()


def digest(*parts: Any) -> str:
    """Short stable hash of the inputs, for pinning what a run was given.

    Twelve hex characters. Enough to notice that the charter changed between a
    baseline and a monthly check, which is the only question it is asked.
    """
    h = hashlib.sha256()
    for p in parts:
        h.update(json.dumps(p, sort_keys=True, default=str).encode())
    return h.hexdigest()[:12]
