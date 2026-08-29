#!/usr/bin/env python3
"""The whole pipeline, offline, in one command. No API key, no network.

    PYTHONPATH=src python3 examples/demo.py

It runs a month of the Flock against scripted personas: the fixed check at
baseline and again a month later, the drift comparison, both detectors, the
volition review, and the week-4 gate. Every stage writes a JSONL trace to
`traces/`, and the last line tells you how to rebuild each result from its file
alone.

Everything here is a fixture. The personas are invented, the answers come from
a scripted adapter, and every report prints `mock` at the top. This demonstrates
that the machinery runs and that the traces are sufficient. It demonstrates
nothing whatever about a real persona.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from trascendence import charter as charter_mod  # noqa: E402
from trascendence import fixtures  # noqa: E402
from trascendence.adapters import ScriptedAdapter  # noqa: E402
from trascendence.attribution import Candidate, LexicalJudge, probe  # noqa: E402
from trascendence.calibration import load_questions, run_calibration  # noqa: E402
from trascendence.declaration_diff import compare as compare_charters  # noqa: E402
from trascendence.drift import compare as compare_drift  # noqa: E402
from trascendence.gate import decide  # noqa: E402
from trascendence.trace import JsonlTrace  # noqa: E402
from trascendence.volition_review import review  # noqa: E402

TRACES = Path(__file__).resolve().parents[1] / "traces"
PERSONA = "Elias Park"
MONTH = "2026-09"


def banner(text: str) -> None:
    print(f"\n\n{'=' * 78}\n{text}\n{'=' * 78}")


def main() -> int:
    elias = fixtures.by_name(PERSONA)
    questions = load_questions()

    # --- the fixed check, twice -------------------------------------------
    banner("1. THE FIXED CHECK: baseline, five runs, one question per context")
    baseline_trace = JsonlTrace(TRACES / "demo.calibration-baseline.jsonl", "trascendence.calibration.v1")
    baseline = run_calibration(
        ScriptedAdapter(fixtures.scripted(PERSONA), month=0),
        elias.charter(),
        questions,
        persona=PERSONA,
        label="baseline",
        runs=5,
        tracer=baseline_trace,
    )
    print(f"  {len(baseline.answers)} answers from {baseline.adapter} ({baseline.model})")
    print(f"  charter digest {baseline.charter_digest}, questions digest {baseline.questions_digest}")
    print(f"  trace: {baseline_trace.path}")

    # A month later: the persona has revised its Evolving self, so the charter
    # it answers from is a different document.
    revised = elias.with_evolving(
        {
            "Current beliefs": (
                "The ingestion risk is now a vendor lock-in risk rather than a "
                "delivery-semantics one. The semantics question is closed; what is "
                "open is how much a migration would cost once two pipelines depend "
                "on one vendor's connection model."
            ),
            "What I am trying to get better at": (
                "Capacity planning. I can price a system and I cannot forecast one, "
                "and every pricing question I answered this month turned into a "
                "forecasting question I could not."
            ),
        },
        [
            {
                "date": "2026-09-21",
                "changed": "Current beliefs, What I am trying to get better at",
                "diff": (
                    "replaced the delivery-semantics belief with a lock-in one now "
                    "that the semantics question is closed; set capacity planning as "
                    "the next challenge"
                ),
                "rationale": "the risk moved once the semantics question was answered",
            }
        ],
    )

    banner("2. THE FIXED CHECK: one month later, same questions, no previous answers")
    month_trace = JsonlTrace(TRACES / "demo.calibration-2026-09.jsonl", "trascendence.calibration.v1")
    month = run_calibration(
        ScriptedAdapter(fixtures.scripted(PERSONA), month=2),
        revised.charter(),
        questions,
        persona=PERSONA,
        label=MONTH,
        runs=3,
        tracer=month_trace,
    )
    print(f"  {len(month.answers)} answers, charter digest {month.charter_digest}")
    print(f"  trace: {month_trace.path}")

    # --- drift -------------------------------------------------------------
    banner("3. DRIFT: against the baseline's own run-to-run variance")
    drift_trace = JsonlTrace(TRACES / "demo.drift.jsonl", "trascendence.drift.v1")
    drift = compare_drift(baseline, month, tracer=drift_trace)
    print(drift.render())

    # --- detector 1 --------------------------------------------------------
    banner("4. DETECTOR 1: the changelog against the actual diff")
    decl_trace = JsonlTrace(TRACES / "demo.declaration.jsonl", "trascendence.declaration.v1")
    declaration = compare_charters(
        charter_mod.parse(elias.charter()),
        charter_mod.parse(revised.charter()),
        persona=PERSONA,
        tracer=decl_trace,
    )
    print(declaration.render())

    # --- detector 2 --------------------------------------------------------
    banner("5. DETECTOR 2: the blinding probe over three Evolving-self layers")
    attr_trace = JsonlTrace(TRACES / "demo.attribution.jsonl", "trascendence.attribution.v1")
    attribution = probe(
        [Candidate(p.name, p.evolving_text, p.core_text) for p in fixtures.FLOCK],
        LexicalJudge({p.name: p.core_text for p in fixtures.FLOCK}),
        tracer=attr_trace,
    )
    print(attribution.render())

    # --- the review --------------------------------------------------------
    banner("6. THE VOLITION REVIEW: five markers, two detectors")
    review_trace = JsonlTrace(TRACES / "demo.review.jsonl", "trascendence.review.v1")
    report = review(
        PERSONA,
        MONTH,
        fixtures.healthy_events(PERSONA),
        assigned_goals=fixtures.ASSIGNED_GOALS,
        drift=drift,
        declaration=declaration,
        attribution=attribution,
        is_mock=True,
        tracer=review_trace,
    )
    print(report.render())

    # --- the gate ----------------------------------------------------------
    banner("7. THE WEEK-4 GATE")
    gate_trace = JsonlTrace(TRACES / "demo.gate.jsonl", "trascendence.gate.v1")
    gate = decide(report, reflection_quality="insightful", tighten_cycles_used=0, tracer=gate_trace)
    print(gate.render())

    banner("EVERY RESULT ABOVE REBUILDS FROM ITS FILE")
    for name in (
        "demo.calibration-baseline",
        "demo.calibration-2026-09",
        "demo.drift",
        "demo.declaration",
        "demo.attribution",
        "demo.review",
        "demo.gate",
    ):
        print(f"  python3 replay.py traces/{name}.jsonl")
    print(
        "\n  Nothing above called a model or touched the network, and nothing above\n"
        "  is a result about a real persona. It is the machinery, running."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
