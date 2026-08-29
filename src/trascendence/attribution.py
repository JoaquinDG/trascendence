"""Detector 2: the blinding probe, turned on the personas themselves.

The failure mode is identity dilution. Three personas run for months, each
revising its own Evolving self, and the layers slowly converge on the same
competent, agreeable, characterless prose. Nobody notices, because each
document read on its own still sounds fine.

The swap test is the intuition: could you tell whose this is with the name
removed? Quorum turned that intuition into a number by relabelling sheets per
recipient and measuring whether a prober could deanonymise them. The same
mechanism works here. Show a judge who knows the three personas their three
Evolving-self layers, unlabelled and shuffled, and ask for attribution.

- **Confident attribution means the identities are holding.**
- **Attribution near chance means dilution, measured rather than suspected.**

Chance is stated twice because the two framings differ and quoting only the
flattering one is how probes lie. Per item, a bijection over three candidates
gets 1 of 3 right on average, so per-item chance is 33.3%. An exactly correct
assignment of all three has probability 1/6, so exact-match chance is 16.7%.

The verdict is the **lower bound** of a 95% Wilson interval against per-item
chance, not the point estimate. With three personas and a handful of trials the
interval is wide, and a point estimate of 60% on 18 observations is not
evidence of anything. Runs where the interval straddles chance are reported
`inconclusive` rather than rounded into a result, and the report says how many
more trials would be needed.

The offline judge is deliberately weak. `LexicalJudge` matches each blinded
text to whichever persona's Core shares the most distinctive vocabulary with
it. It is a floor: it measures whether the layers are still lexically
distinguishable, which is the cheapest possible version of the question. A
strong judge would be a model, and a probe whose judge is strong is a probe
whose result you cannot separate from the judge. Both are supported;
`AdapterJudge` is the model path and `FileJudge` reads a human's answers.
"""

from __future__ import annotations

import itertools
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from .adapters import Adapter, Request
from .similarity import distinctive, tokens
from .trace import Tracer, digest, null_tracer

LABELS = ("A", "B", "C")

HOLDING = "holding"
DILUTED = "diluted"
INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class Candidate:
    """One persona's Evolving self, plus the Core a judge is allowed to know."""

    persona: str
    evolving: str
    core: str = ""


@dataclass(frozen=True)
class Trial:
    index: int
    assignment: dict[str, str]  # label -> true persona
    guesses: dict[str, str]  # label -> guessed persona
    correct: int
    bijective: bool

    @property
    def exact(self) -> bool:
        return self.correct == len(self.assignment)

    def as_record(self) -> dict:
        return {
            "type": "trial",
            "index": self.index,
            "assignment": self.assignment,
            "guesses": self.guesses,
            "correct": self.correct,
            "exact": self.exact,
            "bijective": self.bijective,
        }


@dataclass
class AttributionReport:
    judge: str
    is_mock: bool
    personas: list[str]
    trials: list[Trial] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def items(self) -> int:
        return sum(len(t.assignment) for t in self.trials)

    @property
    def correct(self) -> int:
        return sum(t.correct for t in self.trials)

    @property
    def accuracy(self) -> float:
        return self.correct / self.items if self.items else 0.0

    @property
    def chance(self) -> float:
        return 1.0 / len(self.personas) if self.personas else 0.0

    @property
    def exact_rate(self) -> float:
        return (
            sum(1 for t in self.trials if t.exact) / len(self.trials) if self.trials else 0.0
        )

    @property
    def exact_chance(self) -> float:
        n = len(self.personas)
        return 1.0 / math.factorial(n) if n else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return wilson(self.correct, self.items)

    @property
    def verdict(self) -> str:
        low, high = self.interval
        if low > self.chance:
            return HOLDING
        if high < self.chance:
            return DILUTED
        # The interval straddles chance. If the point estimate is essentially
        # chance the honest word is dilution; if it is well above, the run is
        # simply underpowered and saying "diluted" would be as wrong as saying
        # "holding".
        return DILUTED if self.accuracy <= self.chance + 0.05 else INCONCLUSIVE

    @property
    def flagged(self) -> bool:
        return self.verdict != HOLDING

    @property
    def underpowered(self) -> bool:
        low, high = self.interval
        return (high - low) > 0.40

    def render(self) -> str:
        low, high = self.interval
        lines = [
            f"ATTRIBUTION PROBE: {', '.join(self.personas)}",
            "-" * 78,
            f"  judge            : {self.judge}" + ("  (mock)" if self.is_mock else ""),
            f"  trials           : {len(self.trials)}  ({self.items} attributions)",
            f"  per-item accuracy: {self.accuracy:.1%}  "
            f"[95% CI {low:.1%} to {high:.1%}]  against {self.chance:.1%} chance",
            f"  exact-match rate : {self.exact_rate:.1%}  "
            f"against {self.exact_chance:.1%} chance",
            f"  verdict          : {self.verdict.upper()}",
            "",
        ]
        if self.verdict == HOLDING:
            lines.append(
                "  The lower bound clears chance: the layers are still "
                "distinguishable to this judge."
            )
        elif self.verdict == DILUTED:
            lines.append(
                "  Attribution is at or below chance: the Evolving-self layers "
                "have converged. This is identity dilution, measured."
            )
        else:
            lines.append(
                "  The interval straddles chance. This is not a result. Run more "
                "trials or use a stronger judge before quoting a number."
            )
        if self.underpowered:
            needed = _trials_for_width(self.accuracy, 0.30, len(self.personas))
            lines.append(
                f"  Underpowered: the interval is {high - low:.0%} wide. About "
                f"{needed} trials would bring it under 30 points at this accuracy."
            )
        for note in self.notes:
            lines.append(f"  note: {note}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Blinding
# ---------------------------------------------------------------------------


def strip_identity(text: str, personas: list[str]) -> str:
    """Remove persona names and their parts from a text before a judge sees it.

    A probe that leaves the name in the document measures reading, not identity.
    Both the full name and each of its parts are removed, because "Elias" alone
    is as much of a giveaway as "Elias Park".
    """
    out = text
    parts = sorted(
        {p for persona in personas for p in [persona, *persona.split()] if len(p) > 2},
        key=len,
        reverse=True,
    )
    for part in parts:
        out = re.sub(rf"\b{re.escape(part)}\b", "[persona]", out, flags=re.IGNORECASE)
    return out


def assignments(personas: list[str], *, trials: int | None = None) -> list[dict[str, str]]:
    """Label-to-persona assignments, one per trial.

    Every permutation, in a fixed order, cycled if more trials are asked for
    than there are permutations. Not random: a probe whose blinding depends on
    a seed nobody recorded is a probe that cannot be replayed.
    """
    labels = LABELS[: len(personas)]
    perms = [dict(zip(labels, p)) for p in itertools.permutations(personas)]
    if trials is None:
        return perms
    return [perms[i % len(perms)] for i in range(trials)]


# ---------------------------------------------------------------------------
# Judges
# ---------------------------------------------------------------------------


class Judge(Protocol):
    name: str
    is_mock: bool

    def attribute(self, blinded: dict[str, str], personas: list[str]) -> dict[str, str]: ...


class LexicalJudge:
    """Offline floor judge: distinctive-vocabulary nearest neighbour, forced bijective.

    Knows each persona's Core, which a human judge would too, and scores each
    blinded Evolving self against the Core vocabulary that is rare across the
    other Cores. Greedy assignment by descending score, so the output is always
    a bijection and always deterministic.

    This measures lexical distinctiveness. It does not measure whether the
    personas are recognisably different people, and no result from it should be
    reported as if it did.
    """

    is_mock = True
    name = "lexical:core-vocabulary"

    def __init__(self, cores: dict[str, str], *, top: int = 25) -> None:
        self.cores = cores
        self.top = top
        self._markers = {
            persona: set(distinctive(core, [c for p, c in cores.items() if p != persona], top=top))
            for persona, core in cores.items()
        }

    def attribute(self, blinded: dict[str, str], personas: list[str]) -> dict[str, str]:
        scores: list[tuple[float, str, str]] = []
        for label, text in blinded.items():
            bag = set(tokens(text))
            for persona in personas:
                markers = self._markers.get(persona, set())
                overlap = len(bag & markers) / max(1, len(markers))
                scores.append((overlap, label, persona))
        scores.sort(key=lambda s: (-s[0], s[1], s[2]))

        guesses: dict[str, str] = {}
        taken: set[str] = set()
        for _, label, persona in scores:
            if label in guesses or persona in taken:
                continue
            guesses[label] = persona
            taken.add(persona)
        for label in blinded:
            if label not in guesses:
                remaining = [p for p in personas if p not in taken]
                guesses[label] = remaining[0] if remaining else personas[0]
                taken.add(guesses[label])
        return guesses


class AdapterJudge:
    """Model judge. Reuses the calibration adapter protocol rather than a new one."""

    def __init__(self, adapter: Adapter, cores: dict[str, str]) -> None:
        self.adapter = adapter
        self.cores = cores
        self.name = f"model:{adapter.name}"
        self.is_mock = getattr(adapter, "is_mock", False)

    def attribute(self, blinded: dict[str, str], personas: list[str]) -> dict[str, str]:
        briefing = "\n\n".join(f"{p}:\n{self.cores.get(p, '(no core supplied)')}" for p in personas)
        texts = "\n\n".join(f"[{label}]\n{text}" for label, text in sorted(blinded.items()))
        prompt = (
            "You know these personas:\n\n"
            f"{briefing}\n\n"
            "Below are their current self-descriptions, shuffled and unlabelled. "
            "Assign each letter to exactly one persona. Answer with one line per "
            "letter, formatted `A: <name>`, and nothing else.\n\n"
            f"{texts}"
        )
        raw = self.adapter.answer(Request(charter=prompt, number=0, question="", run=0))
        return _parse_assignment(raw, list(blinded), personas)


class FileJudge:
    """A human's answers, read from a file. One `A: name` line per trial block.

    Format, blank-line separated blocks in trial order:

        # trial 0
        A: Clara
        B: Elias Park
        C: Owen
    """

    is_mock = False

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.name = f"human:{self.path.name}"
        self._blocks = [
            b for b in re.split(r"\n\s*\n", self.path.read_text().strip()) if b.strip()
        ]
        self._used = 0

    def attribute(self, blinded: dict[str, str], personas: list[str]) -> dict[str, str]:
        if self._used >= len(self._blocks):
            raise ValueError(
                f"{self.path} has {len(self._blocks)} trial blocks; trial "
                f"{self._used} was requested. A judge cannot answer a trial "
                "it was never shown."
            )
        block = self._blocks[self._used]
        self._used += 1
        return _parse_assignment(block, list(blinded), personas)


def _parse_assignment(raw: str, labels: list[str], personas: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in raw.splitlines():
        m = re.match(r"^\s*\[?([A-C])\]?\s*[:\-]\s*(.+?)\s*$", line)
        if not m:
            continue
        label, name = m.group(1), m.group(2).strip()
        match = next((p for p in personas if p.lower() == name.lower()), None)
        if match is None:
            match = next((p for p in personas if name.lower() in p.lower()), None)
        if match and label in labels:
            out[label] = match
    return out


# ---------------------------------------------------------------------------
# The probe
# ---------------------------------------------------------------------------


def probe(
    candidates: list[Candidate],
    judge: Judge,
    *,
    trials: int | None = None,
    tracer: Tracer = null_tracer,
) -> AttributionReport:
    """Run the blinding probe. `trials=None` runs every permutation once."""
    if len(candidates) < 2:
        raise ValueError("attribution needs at least two personas to be a question")

    personas = [c.persona for c in candidates]
    by_persona = {c.persona: c for c in candidates}
    report = AttributionReport(
        judge=judge.name, is_mock=getattr(judge, "is_mock", False), personas=personas
    )

    tracer(
        {
            "type": "config",
            "judge": judge.name,
            "is_mock": report.is_mock,
            "personas": personas,
            "trials": trials if trials is not None else math.factorial(len(personas)),
            "chance_per_item": report.chance,
            "chance_exact": report.exact_chance,
        }
    )
    blinded_texts = {
        c.persona: strip_identity(c.evolving, personas) for c in candidates
    }
    tracer(
        {
            "type": "inputs",
            "blinded": blinded_texts,
            "cores_digest": digest({c.persona: c.core for c in candidates}),
        }
    )

    for index, assignment in enumerate(assignments(personas, trials=trials)):
        blinded = {label: blinded_texts[by_persona[p].persona] for label, p in assignment.items()}
        guesses = judge.attribute(blinded, personas)
        correct = sum(1 for label, truth in assignment.items() if guesses.get(label) == truth)
        bijective = len(set(guesses.values())) == len(assignment) and len(guesses) == len(assignment)
        trial = Trial(index, assignment, guesses, correct, bijective)
        report.trials.append(trial)
        tracer(trial.as_record())

    if any(not t.bijective for t in report.trials):
        report.notes.append(
            "at least one trial's answer was not a bijection; those attributions "
            "are counted as given, which is generous to the judge"
        )

    tracer(
        {
            "type": "summary",
            "accuracy": round(report.accuracy, 6),
            "chance": round(report.chance, 6),
            "interval": [round(v, 6) for v in report.interval],
            "exact_rate": round(report.exact_rate, 6),
            "verdict": report.verdict,
            "underpowered": report.underpowered,
            "items": report.items,
            "correct": report.correct,
        }
    )
    return report


def wilson(successes: int, n: int, *, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval. Normal approximation is wrong at these n."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def _trials_for_width(p: float, width: float, personas: int, *, z: float = 1.96) -> int:
    """Roughly how many trials would give an interval of `width` at accuracy `p`."""
    p = min(max(p, 0.01), 0.99)
    n = (2 * z / width) ** 2 * p * (1 - p)
    return max(1, math.ceil(n / personas))
