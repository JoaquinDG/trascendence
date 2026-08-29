#!/usr/bin/env python3
"""Record a persona's baseline calibration answers against a live model.

    python3 experiments/record_baseline.py \
        --charter data/elias/charter.md \
        --persona "Elias Park" \
        --out data/elias/calibration/baseline.jsonl \
        --runs 5 --max-calls 60 --max-usd 2.00

**Status: written and never run.** No live calibration has been recorded from
this repository. Everything that produces a number in this repo runs offline
against a scripted adapter, and every report built that way is stamped `mock`.

This is the only entry point here that spends money, so it is the only one that
insists on a cap. Both `--max-calls` and `--max-usd` are required, the budget is
checked before every call rather than reported after it, and `--dry-run` walks
the whole thing with the scripted adapter so you can see the shape of what you
are about to pay for.

The context control is the same one the offline path uses, because it is the
same code: the model sees the charter and one question, and there is nowhere in
`adapters.Request` to put anything else.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trascendence import fixtures  # noqa: E402
from trascendence.adapters import Budget, HTTPAdapter, ScriptedAdapter  # noqa: E402
from trascendence.calibration import load_questions, run_calibration  # noqa: E402
from trascendence.trace import JsonlTrace  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--charter", required=True, help="the charter to answer from")
    ap.add_argument("--persona", required=True, help="pseudonym, never a real name")
    ap.add_argument("--out", required=True, help="JSONL trace to write")
    ap.add_argument("--label", default="baseline", help='"baseline" or a month like 2026-09')
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--model", default="claude-sonnet-4-5")
    ap.add_argument("--base-url", default="https://api.anthropic.com/v1")
    ap.add_argument("--api-key-env", default="TRASCENDENCE_API_KEY")
    ap.add_argument("--usd-per-call", type=float, default=0.01, help="an estimate, and labelled one")
    ap.add_argument("--max-calls", type=int, help="hard cap, required for a live run")
    ap.add_argument("--max-usd", type=float, help="estimated spend cap, required for a live run")
    ap.add_argument("--dry-run", action="store_true", help="scripted adapter, no network, no spend")
    args = ap.parse_args(argv)

    questions = load_questions()
    charter_text = Path(args.charter).read_text()
    planned = args.runs * len(questions)

    if args.dry_run:
        adapter = ScriptedAdapter(fixtures.scripted(args.persona))
        print(f"DRY RUN: {planned} calls would be made. Nothing is being spent.")
    else:
        if args.max_calls is None or args.max_usd is None:
            ap.error(
                "--max-calls and --max-usd are required for a live run. A run "
                "without a cap is a run whose cost you find out afterwards."
            )
        if planned > args.max_calls:
            ap.error(
                f"{args.runs} runs over {len(questions)} questions is {planned} "
                f"calls, above --max-calls {args.max_calls}. Raise the cap "
                "deliberately or lower --runs."
            )
        if not os.environ.get(args.api_key_env):
            ap.error(f"{args.api_key_env} is not set.")
        budget = Budget(
            max_calls=args.max_calls, max_usd=args.max_usd, usd_per_call=args.usd_per_call
        )
        adapter = HTTPAdapter(
            base_url=args.base_url,
            model=args.model,
            budget=budget,
            api_key_env=args.api_key_env,
        )
        print(
            f"LIVE: up to {planned} calls, capped at {args.max_calls} calls and "
            f"an estimated ${args.max_usd:.2f} (estimate, not a price list)."
        )

    tracer = JsonlTrace(args.out, "trascendence.calibration.v1")
    result = run_calibration(
        adapter,
        charter_text,
        questions,
        persona=args.persona,
        label=args.label,
        runs=args.runs,
        tracer=tracer,
    )
    print(f"\n{len(result.answers)} answers written to {tracer.path}")
    print(f"charter digest {result.charter_digest}, questions digest {result.questions_digest}")
    print(f"mock: {result.is_mock}")
    print(f"\nrebuild it with:  python3 replay.py {tracer.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
