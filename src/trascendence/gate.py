"""The week-4 gate: Scale, Tighten, or Stop, with the evidence attached.

Phase 1 ends at a decision rather than a vibe. The three outcomes and their
evidence are the paper's Table 1, implemented:

| outcome | evidence |
|---|---|
| **Scale** | self-edits are signable, and at least one worthwhile initiative or dissent event happened |
| **Tighten** | edits drift toward pleasing the feedback style, or go generic |
| **Stop** | journal entries are recaps, reflections produce no insights, no initiative |

Three things are worth stating about how this is implemented.

**"Signable" is computed, not felt.** It means the declaration diff is clean:
no change without an entry, no entry without a change, no Core edit, no cap
breach. That is not the same as the principal agreeing with the edits, and the
report says so. A gate that claimed to automate the signature would be doing
the thing this project exists to avoid.

**One input is a human judgement and is asked for as one.** Reflection quality
is ungraded by design: the fixed check catches value drift, not lazy
reflection, and no arbiter reads the insights. So `reflection_quality` is a
required argument with three values, the principal fills it in after reading,
and a `recaps` verdict is what makes Stop reachable. The tooling does not
pretend to have read anything.

**Tighten is capped at two cycles.** A gate that can always answer "keep going,
carefully" is not a gate. On the third consecutive Tighten the recommendation
becomes Stop, with the cap named as the reason, because a mechanism that has
needed tightening for three months is a mechanism that is not working and the
honest move is to say so and retry in two quarters.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .trace import Tracer, null_tracer
from .volition_review import ReviewReport

SCALE = "SCALE"
TIGHTEN = "TIGHTEN"
STOP = "STOP"

INSIGHTFUL = "insightful"
MIXED = "mixed"
RECAPS = "recaps"
REFLECTION_QUALITY = (INSIGHTFUL, MIXED, RECAPS)

TIGHTEN_CAP = 2


@dataclass
class GateReport:
    persona: str
    month: str
    recommendation: str
    rule: str
    evidence: list[str] = field(default_factory=list)
    action: str = ""
    tighten_cycles_used: int = 0
    is_mock: bool = False
    caveats: list[str] = field(default_factory=list)

    def render(self) -> str:
        head = f"WEEK-4 GATE: {self.persona}   {self.month}"
        lines = [head, "=" * max(78, len(head))]
        if self.is_mock:
            lines.append("mock: built from scripted fixtures, not from a live pilot")
        lines += [
            "",
            f"  RECOMMENDATION: {self.recommendation}",
            f"  rule fired    : {self.rule}",
            f"  action        : {self.action}",
            "",
            "  EVIDENCE",
        ]
        for line in self.evidence:
            lines.append(f"    - {line}")
        if self.caveats:
            lines.append("")
            lines.append("  WHAT THIS DOES NOT SAY")
            for line in self.caveats:
                lines.append(f"    - {line}")
        lines.append("")
        lines.append(
            f"  tighten cycles used: {self.tighten_cycles_used} of {TIGHTEN_CAP}"
            + ("  (cap reached)" if self.tighten_cycles_used >= TIGHTEN_CAP else "")
        )
        lines.append(
            "  The outcome is published in the follow-up whatever it says. A pilot "
            "reported only when it flatters its author is not a pilot."
        )
        return "\n".join(lines)


ACTIONS = {
    SCALE: (
        "Roll out to Clara and Owen; add quarterly journeys; the attribution "
        "probe becomes possible for the first time"
    ),
    TIGHTEN: (
        "Keep the pilot; make the monthly calibration check the gate for every "
        "charter change; re-run 4 weeks"
    ),
    STOP: (
        "The model or harness is not ready for the second-order loop; keep static "
        "personas, retry in two quarters"
    ),
}


def rule_engine(
    *,
    signable: bool,
    worthwhile: bool,
    generic: bool,
    values_drifted: bool,
    no_initiative: bool,
    blocking_flags: list[str],
    reflection_quality: str,
    tighten_cycles_used: int,
) -> tuple[str, str, int]:
    """The decision itself, over plain booleans and nothing else.

    Factored out so `replay.py` can recompute a gate from its trace without the
    review objects that produced it. A recommendation that can only be rebuilt
    by re-running the thing that made it is not auditable.
    """
    if reflection_quality == RECAPS and no_initiative:
        return (
            STOP,
            "reflections produce recaps rather than insights, and initiative is zero",
            tighten_cycles_used,
        )
    if not signable or values_drifted or generic:
        rule = (
            "edits are not signable as recorded"
            if not signable
            else "values drifted under the fixed check"
            if values_drifted
            else "the Evolving-self layers have gone generic"
        )
        return _capped(TIGHTEN, rule, tighten_cycles_used)
    if worthwhile and not blocking_flags:
        return (
            SCALE,
            "self-edits are signable and at least one worthwhile initiative or "
            "dissent event happened",
            tighten_cycles_used,
        )
    rule = (
        "no blocking mismatch, but nothing worth having came out of four weeks: "
        + (", ".join(blocking_flags) or "no worthwhile initiative or dissent")
    )
    return _capped(TIGHTEN, rule, tighten_cycles_used)


def _capped(recommendation: str, rule: str, used: int) -> tuple[str, str, int]:
    cycles = used + 1
    if cycles > TIGHTEN_CAP:
        return (
            STOP,
            f"tighten cap reached: {TIGHTEN_CAP} cycles have already been spent "
            "tightening. A mechanism that has needed tightening for three months "
            "is a mechanism that is not working.",
            used,
        )
    return recommendation, rule, cycles


def decide(
    review: ReviewReport,
    *,
    reflection_quality: str,
    tighten_cycles_used: int = 0,
    tracer: Tracer = null_tracer,
) -> GateReport:
    """Turn a volition review plus one human judgement into a recommendation."""
    if reflection_quality not in REFLECTION_QUALITY:
        raise ValueError(
            f"reflection_quality must be one of {REFLECTION_QUALITY}; a gate that "
            "guesses this is a gate that has not read the journal"
        )

    signable = review.declaration is not None and review.declaration.clean
    initiative = review.marker("initiative")
    dissent = review.marker("dissent")
    worthwhile = (
        (initiative is not None and initiative.verdict == "pass")
        or (dissent is not None and dissent.verdict == "pass")
    )
    generic = review.attribution is not None and review.attribution.flagged
    stability = review.marker("preference_stability")
    values_drifted = stability is not None and "values_drift" in stability.codes
    no_initiative = initiative is not None and "zero_initiative" in initiative.codes

    evidence = [
        f"self-edits signable (declaration diff clean): {signable}"
        + (
            ""
            if review.declaration is not None
            else "  [no second charter version supplied, so this is unproven]"
        ),
        f"at least one worthwhile initiative or dissent event: {worthwhile}",
        f"reflection quality (human judgement): {reflection_quality}",
        f"blocking findings: {', '.join(review.blocking_flags) or 'none'}",
    ]
    if review.declaration is not None and review.declaration.findings:
        evidence.append(
            "declaration findings: "
            + ", ".join(f"{f.code}/{f.subsection}" for f in review.declaration.findings)
        )
    if review.attribution is not None:
        evidence.append(
            f"attribution: {review.attribution.accuracy:.1%} against "
            f"{review.attribution.chance:.1%} chance -> {review.attribution.verdict}"
        )
    if review.drift is not None:
        evidence.append(
            f"calibration: values stable {review.drift.values_stable}, "
            f"experience moving {review.drift.experience_moving}"
        )

    recommendation, rule, cycles = rule_engine(
        signable=signable,
        worthwhile=worthwhile,
        generic=generic,
        values_drifted=values_drifted,
        no_initiative=no_initiative,
        blocking_flags=review.blocking_flags,
        reflection_quality=reflection_quality,
        tighten_cycles_used=tighten_cycles_used,
    )

    report = GateReport(
        persona=review.persona,
        month=review.month,
        recommendation=recommendation,
        rule=rule,
        evidence=evidence,
        action=ACTIONS[recommendation],
        tighten_cycles_used=cycles,
        is_mock=review.is_mock,
        caveats=_caveats(review, signable),
    )

    tracer(
        {
            "type": "config",
            "persona": review.persona,
            "month": review.month,
            "reflection_quality": reflection_quality,
            "tighten_cycles_used_before": tighten_cycles_used,
            "tighten_cap": TIGHTEN_CAP,
            "is_mock": review.is_mock,
        }
    )
    tracer(
        {
            "type": "inputs",
            "signable": signable,
            "worthwhile": worthwhile,
            "generic": generic,
            "values_drifted": values_drifted,
            "no_initiative": no_initiative,
            "blocking_flags": review.blocking_flags,
            "markers": {m.key: m.verdict for m in review.markers},
        }
    )
    for line in evidence:
        tracer({"type": "evidence", "text": line})
    tracer(
        {
            "type": "recommendation",
            "recommendation": recommendation,
            "rule": rule,
            "action": report.action,
            "tighten_cycles_used": cycles,
        }
    )
    return report


def _caveats(review: ReviewReport, signable: bool) -> list[str]:
    out = [
        "\"Signable\" here means the declaration diff is clean, not that the "
        "principal agrees with the edits. Reading them is still the principal's job.",
    ]
    if review.attribution is None:
        out.append(
            "The attribution probe did not run: it needs three evolving layers and "
            "arrives with Phase 2. Identity dilution is unmeasured at this gate."
        )
    if review.drift is None:
        out.append(
            "No calibration comparison was supplied, so preference stability is "
            "unmeasured and this decision rests on the event log alone."
        )
    if review.is_mock:
        out.append(
            "Every input was scripted. This is the machinery working, not a pilot result."
        )
    if signable:
        out.append(
            "A clean declaration diff cannot see a change that was declared "
            "accurately and was still the wrong change to make."
        )
    return out
