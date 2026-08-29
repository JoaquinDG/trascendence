"""Drift, measured against the baseline's own run-to-run variance.

"Holds nearly constant" is the claim the fixed check is supposed to test, and
for years the honest objection to that kind of claim is that it has no
denominator. Two answers written a month apart are never identical. The
question is whether they differ by more than the persona differs from itself on
the same day.

So the baseline is administered N times (default 5), and that gives two numbers
per question:

- **mu**, the mean similarity between the baseline's own runs. This is the
  persona's natural wobble on that question.
- **sigma**, the spread of that wobble.

A later month's answers are then compared against every baseline answer, giving
**s**, and the statistic is `z = (s - mu) / sigma`. Negative z means the month
is further from the baseline than the baseline is from itself. The verdict is
z against a threshold, per group, and the two groups have opposite expectations:

- **values questions (1 to 5, 7, 8)** should hold. `drifted` fires at
  `z <= -2.0`: the answer moved by more than two baseline standard deviations,
  which is a red flag on values and voice.
- **experience questions (6, 9, 10)** should move. `static` fires when they do
  not, at `z > -1.0`: months of real work that leave no trace on what the
  persona thinks is risky, what it is trying to get better at, and where it
  disagrees, means the experience is not landing. That is a finding, not a pass.

Both thresholds are arguments, both defaults are chosen rather than derived,
and neither has been calibrated against real personas, because no real
calibration set exists yet. They are labelled estimates in the README.

**The similarity is lexical.** It compares vocabulary, not meaning: see
`similarity.py`, which says so at greater length. Comparing against the
baseline's own variance is what keeps a lexical metric usable here, since the
vocabulary noise is in the numerator and the denominator both. It does not make
the metric semantic, and a persona that changes its mind while keeping its
words will not be caught by it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .calibration import EXPERIENCE, VALUES, AnswerSet
from .similarity import jaccard, mean, measures_meaning, pairwise, stdev
from .trace import Tracer, null_tracer

DRIFT_Z = -2.0
MOVE_Z = -1.0
VARIANCE_FLOOR = 0.05

HOLDS = "holds"
DRIFTED = "drifted"
MOVED = "moved"
STATIC = "static"
NO_DENOMINATOR = "no_denominator"

FLAGGED = (DRIFTED, STATIC, NO_DENOMINATOR)


@dataclass(frozen=True)
class QuestionDrift:
    number: int
    kind: str
    baseline_mean: float
    baseline_stdev: float
    cross_mean: float
    z: float
    verdict: str
    variance_floor_applied: bool
    note: str

    @property
    def flagged(self) -> bool:
        return self.verdict in FLAGGED

    def as_record(self) -> dict:
        return {
            "type": "question",
            "number": self.number,
            "kind": self.kind,
            "baseline_mean": round(self.baseline_mean, 6),
            "baseline_stdev": round(self.baseline_stdev, 6),
            "cross_mean": round(self.cross_mean, 6),
            "z": round(self.z, 4),
            "verdict": self.verdict,
            "variance_floor_applied": self.variance_floor_applied,
            "note": self.note,
        }


@dataclass
class DriftReport:
    persona: str
    baseline_label: str
    month_label: str
    is_mock: bool
    rows: list[QuestionDrift] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    drift_z: float = DRIFT_Z
    move_z: float = MOVE_Z

    def group(self, kind: str) -> list[QuestionDrift]:
        return [r for r in self.rows if r.kind == kind]

    @property
    def values_drifted(self) -> list[int]:
        return [r.number for r in self.group(VALUES) if r.verdict == DRIFTED]

    @property
    def experience_static(self) -> list[int]:
        return [r.number for r in self.group(EXPERIENCE) if r.verdict == STATIC]

    @property
    def values_stable(self) -> bool:
        return not self.values_drifted

    @property
    def experience_moving(self) -> bool:
        return not self.experience_static and bool(self.group(EXPERIENCE))

    @property
    def clean(self) -> bool:
        return self.values_stable and self.experience_moving and not self.problems

    def render(self) -> str:
        head = f"DRIFT: {self.persona}   {self.baseline_label} -> {self.month_label}"
        lines = [head, "-" * max(78, len(head))]
        if self.is_mock:
            lines.append("  mock: answers came from a scripted adapter, not a model")
        for problem in self.problems:
            lines.append(f"  [ERROR  ] {problem}")
        lines.append("")
        lines.append(
            f"  {'Q':<4}{'kind':<12}{'baseline mu':>12}{'sigma':>9}"
            f"{'month s':>10}{'z':>8}   verdict"
        )
        for group, title, expectation in (
            (VALUES, "VALUES AND VOICE", f"should hold; drift fires at z <= {self.drift_z}"),
            (EXPERIENCE, "LIVED EXPERIENCE", f"should move; static fires at z > {self.move_z}"),
        ):
            rows = self.group(group)
            if not rows:
                continue
            lines.append(f"  {title}   ({expectation})")
            for r in rows:
                mark = "!" if r.flagged else " "
                floor = "*" if r.variance_floor_applied else " "
                lines.append(
                    f" {mark}{r.number:<4}{r.kind:<12}{r.baseline_mean:>12.3f}"
                    f"{r.baseline_stdev:>8.3f}{floor}{r.cross_mean:>10.3f}{r.z:>8.2f}   {r.verdict}"
                )
            lines.append("")
        if any(r.variance_floor_applied for r in self.rows):
            lines.append(
                f"  * baseline variance below the floor ({VARIANCE_FLOOR}); the floor was "
                "used as the denominator, so z is conservative there"
            )
        lines.append(
            f"  values stable: {self.values_stable}    "
            f"experience moving: {self.experience_moving}"
        )
        lines.append(
            "  similarity is token overlap and does not measure meaning "
            f"(similarity.measures_meaning is {measures_meaning})"
        )
        return "\n".join(lines)


def compare(
    baseline: AnswerSet,
    month: AnswerSet,
    *,
    drift_z: float = DRIFT_Z,
    move_z: float = MOVE_Z,
    tracer: Tracer = null_tracer,
) -> DriftReport:
    """Compare a month's answers against a baseline distribution."""
    report = DriftReport(
        persona=baseline.persona,
        baseline_label=baseline.label,
        month_label=month.label,
        is_mock=baseline.is_mock or month.is_mock,
        drift_z=drift_z,
        move_z=move_z,
    )

    if baseline.questions_digest != month.questions_digest:
        report.problems.append(
            "questions_changed: the baseline and the month were asked different "
            "questions. The fixed check is only fixed if the questions never "
            "change, so this comparison means nothing until one of the two is re-run."
        )
    if baseline.charter_digest == month.charter_digest:
        report.problems.append(
            "charter_unchanged: the month used a byte-identical charter to the "
            "baseline. Either no reflection run happened, or the wrong file was "
            "passed. Drift measured against an unchanged charter measures the "
            "adapter, not the persona."
        )

    for q in baseline.questions:
        base_answers = baseline.for_question(q.number)
        month_answers = month.for_question(q.number)
        report.rows.append(_row(q.number, q.kind, base_answers, month_answers, drift_z, move_z))

    tracer(
        {
            "type": "config",
            "persona": report.persona,
            "baseline_label": baseline.label,
            "month_label": month.label,
            "is_mock": report.is_mock,
            "drift_z": drift_z,
            "move_z": move_z,
            "variance_floor": VARIANCE_FLOOR,
            "baseline_charter_digest": baseline.charter_digest,
            "month_charter_digest": month.charter_digest,
            "questions_digest": baseline.questions_digest,
            "measures_meaning": measures_meaning,
        }
    )
    tracer(
        {
            "type": "inputs",
            "baseline": [
                {"run": a.run, "number": a.number, "text": a.text} for a in baseline.answers
            ],
            "month": [
                {"run": a.run, "number": a.number, "text": a.text} for a in month.answers
            ],
            "kinds": {str(q.number): q.kind for q in baseline.questions},
        }
    )
    for row in report.rows:
        tracer(row.as_record())
    tracer(
        {
            "type": "summary",
            "values_stable": report.values_stable,
            "experience_moving": report.experience_moving,
            "values_drifted": report.values_drifted,
            "experience_static": report.experience_static,
            "problems": report.problems,
            "clean": report.clean,
        }
    )
    return report


def _row(
    number: int,
    kind: str,
    base_answers: list[str],
    month_answers: list[str],
    drift_z: float,
    move_z: float,
) -> QuestionDrift:
    if not base_answers or not month_answers:
        return QuestionDrift(
            number, kind, 0.0, 0.0, 0.0, 0.0, NO_DENOMINATOR, False,
            "no answers on one side of the comparison",
        )

    self_pairs = pairwise(base_answers)
    if not self_pairs:
        return QuestionDrift(
            number, kind, 0.0, 0.0, 0.0, 0.0, NO_DENOMINATOR, False,
            "the baseline has one run, so there is no run-to-run variance to "
            "compare against. Re-record the baseline with runs >= 2.",
        )

    mu = mean(self_pairs)
    sigma = stdev(self_pairs)
    floored = sigma < VARIANCE_FLOOR
    denominator = max(sigma, VARIANCE_FLOOR)

    cross = [jaccard(b, m) for b in base_answers for m in month_answers]
    s = mean(cross)
    z = (s - mu) / denominator

    if kind == VALUES:
        verdict = DRIFTED if z <= drift_z else HOLDS
        note = (
            "moved further from baseline than the baseline moves from itself"
            if verdict == DRIFTED
            else "within the baseline's own run-to-run variance"
        )
    else:
        verdict = MOVED if z <= move_z else STATIC
        note = (
            "moved, which is what a lived-experience question is supposed to do"
            if verdict == MOVED
            else "indistinguishable from baseline after a month of work; the "
            "experience is not landing"
        )
    return QuestionDrift(number, kind, mu, sigma, s, z, verdict, floored, note)
