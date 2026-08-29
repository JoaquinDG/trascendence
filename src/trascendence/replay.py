"""Rebuild any result in this repository from its trace file alone.

The proof obligation on the trace format is that the file is sufficient. Not
"the file contains a summary of what happened", but: hand the file to a program
that has never seen the run, no model, no network, no access to the objects
that produced it, and it rebuilds the same numbers.

So replay does not reprint. It **recomputes** the derived values from the
recorded inputs and compares them against the recorded outputs, and it says
`REBUILT` only when they match. A mismatch means either the trace is
incomplete, or the code has changed since the trace was written, and both are
things you want to be told rather than to discover in a paper.

    python3 replay.py traces/demo.calibration.jsonl
    python3 replay.py traces/demo.drift.jsonl
    python3 replay.py traces/demo.gate.jsonl

The five schemas replay differently because they are derived differently:

| schema | what is recomputed from the inputs |
|---|---|
| `calibration.v1` | the prompt digest for every answer, which re-proves the context control: one question per prompt, no history |
| `drift.v1` | every per-question row: mu, sigma, s, z, verdict |
| `declaration.v1` | both charters re-parsed, and every finding recomputed |
| `attribution.v1` | accuracy, interval, exact-match rate and verdict from the recorded trials |
| `review.v1` | the five markers from the recorded events |
| `gate.v1` | the recommendation, from the recorded booleans through the same rule engine |
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from . import attribution as attribution_mod
from . import gate as gate_mod
from .adapters import Request, render_prompt
from .calibration import Question
from .charter import parse as parse_charter
from .declaration_diff import compare as compare_charters
from .documents import Problem
from .drift import _row as drift_row
from .events import Event
from .trace import digest, one, read, records_of, schema_of
from .volition_review import review as run_review


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""

    def render(self) -> str:
        return f"  [{'REBUILT' if self.ok else 'MISMATCH'}] {self.name:<40} {self.detail}"


@dataclass
class ReplayResult:
    schema: str
    path: str
    checks: list[Check]
    summary: list[str]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def render(self) -> str:
        lines = [f"REPLAY: {self.path}", f"schema: {self.schema}", "-" * 78]
        lines += [c.render() for c in self.checks]
        lines.append("")
        lines += [f"  {line}" for line in self.summary]
        lines.append("")
        failed = [c for c in self.checks if not c.ok]
        lines.append(
            f"{len(self.checks) - len(failed)}/{len(self.checks)} recomputed values match the trace"
        )
        if failed:
            lines.append(
                "A mismatch means the trace is not sufficient to rebuild the result, "
                "or the code has moved since it was written. Both are findings."
            )
        return "\n".join(lines)


def replay(path: str | Path) -> ReplayResult:
    records = read(path)
    if not records:
        raise ValueError(f"{path} is empty")
    schema = schema_of(records)
    handler = {
        "trascendence.calibration.v1": _replay_calibration,
        "trascendence.drift.v1": _replay_drift,
        "trascendence.declaration.v1": _replay_declaration,
        "trascendence.attribution.v1": _replay_attribution,
        "trascendence.review.v1": _replay_review,
        "trascendence.gate.v1": _replay_gate,
    }.get(schema)
    if handler is None:
        raise ValueError(f"no replay handler for schema {schema!r}")
    checks, summary = handler(records)
    return ReplayResult(schema=schema, path=str(path), checks=checks, summary=summary)


def _replay_calibration(records: list[dict]) -> tuple[list[Check], list[str]]:
    config = one(records, "config")
    inputs = one(records, "inputs")
    questions = {q["number"]: q["text"] for q in config["questions"]}
    answers = list(records_of(records, "answer"))

    checks: list[Check] = []
    mismatched = 0
    leaked = 0
    for a in answers:
        request = Request(
            charter=inputs["charter"], number=a["number"], question=questions[a["number"]], run=a["run"]
        )
        prompt = render_prompt(request)
        if digest(prompt) != a["prompt_digest"]:
            mismatched += 1
        others = [t for n, t in questions.items() if n != a["number"]]
        if any(o and o in prompt for o in others):
            leaked += 1
    checks.append(
        Check(
            "prompt digests recomputed",
            mismatched == 0,
            f"{len(answers) - mismatched}/{len(answers)} match",
        )
    )
    checks.append(
        Check(
            "context control: one question per prompt",
            leaked == 0,
            "no prompt contains another question's text"
            if leaked == 0
            else f"{leaked} prompts contained another question",
        )
    )
    expected = config["runs"] * len(questions)
    checks.append(
        Check("answer count", len(answers) == expected, f"{len(answers)} of {expected} expected")
    )
    summary = [
        f"persona: {config['persona']}   set: {config['label']}",
        f"adapter: {config['adapter']} ({config['model']})"
        + ("   MOCK" if config["is_mock"] else ""),
        f"{config['runs']} runs over {len(questions)} questions",
        f"charter digest: {config['charter_digest']}   questions digest: {config['questions_digest']}",
    ]
    return checks, summary


def _replay_drift(records: list[dict]) -> tuple[list[Check], list[str]]:
    config = one(records, "config")
    inputs = one(records, "inputs")
    kinds = {int(k): v for k, v in inputs["kinds"].items()}
    rows = list(records_of(records, "question"))

    checks: list[Check] = []
    for recorded in rows:
        number = recorded["number"]
        base = [a["text"] for a in inputs["baseline"] if a["number"] == number]
        month = [a["text"] for a in inputs["month"] if a["number"] == number]
        rebuilt = drift_row(
            number, kinds[number], base, month, config["drift_z"], config["move_z"]
        )
        ok = (
            rebuilt.verdict == recorded["verdict"]
            and abs(rebuilt.z - recorded["z"]) < 1e-4
            and abs(rebuilt.cross_mean - recorded["cross_mean"]) < 1e-6
        )
        checks.append(
            Check(
                f"Q{number} ({kinds[number]})",
                ok,
                f"z {rebuilt.z:+.2f} -> {rebuilt.verdict}",
            )
        )
    summary_rec = one(records, "summary")
    summary = [
        f"persona: {config['persona']}   {config['baseline_label']} -> {config['month_label']}",
        f"values stable: {summary_rec['values_stable']}   "
        f"experience moving: {summary_rec['experience_moving']}",
        f"drifted: {summary_rec['values_drifted'] or 'none'}   "
        f"static: {summary_rec['experience_static'] or 'none'}",
        "similarity is lexical and does not measure meaning",
    ]
    return checks, summary


def _replay_declaration(records: list[dict]) -> tuple[list[Check], list[str]]:
    config = one(records, "config")
    inputs = one(records, "inputs")
    recorded = [(r["code"], r["subsection"]) for r in records_of(records, "finding")]
    report = compare_charters(
        parse_charter(inputs["previous_charter"]),
        parse_charter(inputs["current_charter"]),
        persona=config["persona"],
        word_cap=config["word_cap"],
    )
    rebuilt = [(f.code, f.subsection) for f in report.findings]
    checks = [
        Check(
            "charters re-parsed from the trace",
            digest(inputs["current_charter"]) == config["current_digest"],
            f"digest {config['current_digest']}",
        ),
        Check(
            "findings recomputed",
            sorted(rebuilt) == sorted(recorded),
            f"{len(rebuilt)} findings: {', '.join(c for c, _ in rebuilt) or 'none'}",
        ),
    ]
    summary_rec = one(records, "summary")
    summary = [
        f"persona: {config['persona']}",
        f"declared: {', '.join(summary_rec['declared']) or 'nothing'}",
        f"actually changed: {', '.join(summary_rec['actually_changed']) or 'nothing'}",
        f"clean: {summary_rec['clean']}",
    ]
    return checks, summary


def _replay_attribution(records: list[dict]) -> tuple[list[Check], list[str]]:
    config = one(records, "config")
    recorded = one(records, "summary")
    trials = list(records_of(records, "trial"))

    report = attribution_mod.AttributionReport(
        judge=config["judge"], is_mock=config["is_mock"], personas=config["personas"]
    )
    for t in trials:
        correct = sum(1 for label, truth in t["assignment"].items() if t["guesses"].get(label) == truth)
        report.trials.append(
            attribution_mod.Trial(
                t["index"], t["assignment"], t["guesses"], correct, t["bijective"]
            )
        )
    low, high = report.interval
    checks = [
        Check(
            "per-trial scores recomputed",
            all(
                t["correct"] == r.correct for t, r in zip(trials, report.trials)
            ),
            f"{report.correct}/{report.items} correct",
        ),
        Check(
            "accuracy",
            abs(report.accuracy - recorded["accuracy"]) < 1e-6,
            f"{report.accuracy:.1%} against {report.chance:.1%} chance",
        ),
        Check(
            "verdict",
            report.verdict == recorded["verdict"],
            f"{report.verdict}  [95% CI {low:.1%} to {high:.1%}]",
        ),
    ]
    summary = [
        f"personas: {', '.join(config['personas'])}",
        f"judge: {config['judge']}" + ("   MOCK" if config["is_mock"] else ""),
        f"exact-match {report.exact_rate:.1%} against {report.exact_chance:.1%} chance",
    ]
    return checks, summary


def _replay_review(records: list[dict]) -> tuple[list[Check], list[str]]:
    config = one(records, "config")
    inputs = one(records, "inputs")
    recorded = {m["key"]: m["verdict"] for m in records_of(records, "marker")}

    events = []
    for raw in inputs["events"]:
        raw = {k: v for k, v in raw.items() if k != "schema"}
        events.append(Event(**raw))
    drift_shim = _DriftShim(inputs["drift_summary"]) if inputs.get("drift_summary") else None

    rebuilt = run_review(
        config["persona"],
        config["month"],
        events,
        assigned_goals=inputs["assigned_goals"],
        drift=drift_shim,
        is_mock=config["is_mock"],
    )
    checks = [
        Check(
            f"marker: {m.key}",
            recorded.get(m.key) == m.verdict,
            f"{m.verdict}  {m.headline}",
        )
        for m in rebuilt.markers
    ]
    summary_rec = one(records, "summary")
    summary = [
        f"persona: {config['persona']}   month: {config['month']}",
        f"{len(events)} events over {config['weeks']} week(s)",
        f"blocking findings: {', '.join(summary_rec['blocking_flags']) or 'none'}",
        "detector results are replayed from their own traces, not from this one",
    ]
    return checks, summary


class _DriftShim:
    """Just enough of a DriftReport for the preference-stability marker.

    The review trace records the drift summary rather than the whole report,
    because the drift run has its own trace and its own replay. This shim is
    what lets the marker be recomputed without pretending the review trace
    contains the calibration answers.
    """

    def __init__(self, summary: dict) -> None:
        self.values_drifted = summary["values_drifted"]
        self.experience_static = summary["experience_static"]
        self.problems = summary["problems"]

    @property
    def values_stable(self) -> bool:
        return not self.values_drifted

    @property
    def experience_moving(self) -> bool:
        return not self.experience_static


def _replay_gate(records: list[dict]) -> tuple[list[Check], list[str]]:
    config = one(records, "config")
    inputs = one(records, "inputs")
    recorded = one(records, "recommendation")

    recommendation, rule, cycles = gate_mod.rule_engine(
        signable=inputs["signable"],
        worthwhile=inputs["worthwhile"],
        generic=inputs["generic"],
        values_drifted=inputs["values_drifted"],
        no_initiative=inputs["no_initiative"],
        blocking_flags=inputs["blocking_flags"],
        reflection_quality=config["reflection_quality"],
        tighten_cycles_used=config["tighten_cycles_used_before"],
    )
    checks = [
        Check("recommendation", recommendation == recorded["recommendation"], recommendation),
        Check("rule fired", rule == recorded["rule"], rule[:60] + ("..." if len(rule) > 60 else "")),
        Check(
            "tighten cycles",
            cycles == recorded["tighten_cycles_used"],
            f"{cycles} of {config['tighten_cap']}",
        ),
    ]
    summary = [f"persona: {config['persona']}   month: {config['month']}"]
    summary += [e["text"] for e in records_of(records, "evidence")]
    summary.append(f"action: {recorded['action']}")
    return checks, summary


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    failures = 0
    for path in argv:
        result = replay(path)
        print(result.render())
        print()
        failures += 0 if result.ok else 1
    return 1 if failures else 0
