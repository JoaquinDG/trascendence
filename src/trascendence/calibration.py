"""The fixed check: ten questions, N runs, one question per context, all traced.

The persona answers the same ten questions at baseline, before its first
reflection run, and monthly thereafter without seeing its previous answers. The
questions never change. The persona cannot see, grade, or influence the
comparison, because any system that grades its own growth will eventually
flatter itself, and the fix is not a better prompt, it is a test the grower does
not touch.

Two design decisions carry the weight:

**One question per context.** Each answer is produced from the charter and one
question. Nothing else is available to be given, because `adapters.Request` has
no field for it. Reading the questions from `templates/calibration.md` rather
than from a Python constant means the paper's Appendix A and the tooling cannot
drift apart quietly.

**N runs at baseline, default 5.** One answer per question gives you a point.
Five give you the run-to-run variance, which is the denominator that turns
"holds nearly constant" from an impression into a comparison. `drift.py` reads
that variance; without it there is no honest way to say whether a later answer
moved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .adapters import Adapter, Request, render_prompt
from .trace import Tracer, digest, null_tracer, read, records_of

DEFAULT_RUNS = 5
QUESTIONS_PATH = Path(__file__).resolve().parents[2] / "templates" / "calibration.md"

VALUES = "values"
EXPERIENCE = "experience"

_Q_HEADING = re.compile(r"^Q(?P<number>\d+)\s*\((?P<kind>values|experience)\)\s*$")


@dataclass(frozen=True)
class Question:
    number: int
    kind: str
    text: str


@dataclass(frozen=True)
class Answer:
    run: int
    number: int
    text: str


@dataclass
class AnswerSet:
    """One administration of the fixed check: N runs over the ten questions."""

    persona: str
    label: str
    adapter: str
    model: str
    is_mock: bool
    charter_digest: str
    questions_digest: str
    runs: int
    questions: list[Question]
    answers: list[Answer] = field(default_factory=list)

    def for_question(self, number: int) -> list[str]:
        return [a.text for a in self.answers if a.number == number]

    def question(self, number: int) -> Question:
        for q in self.questions:
            if q.number == number:
                return q
        raise KeyError(number)

    @property
    def numbers(self) -> list[int]:
        return [q.number for q in self.questions]


def load_questions(path: str | Path = QUESTIONS_PATH) -> list[Question]:
    """Parse `## Q<n> (values|experience)` headings out of calibration.md.

    Tolerant of everything else in the file, so the prose that explains the
    check can live in the same document as the check.
    """
    text = Path(path).read_text()
    out: list[Question] = []
    current: tuple[int, str] | None = None
    body: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                out.append(Question(current[0], current[1], " ".join(body).strip()))
            m = _Q_HEADING.match(line[3:].strip())
            current = (int(m.group("number")), m.group("kind")) if m else None
            body = []
            continue
        if current is not None and line.strip() and not line.startswith(">"):
            body.append(line.strip())
    if current is not None:
        out.append(Question(current[0], current[1], " ".join(body).strip()))
    return sorted(out, key=lambda q: q.number)


def questions_digest(questions: list[Question]) -> str:
    return digest([(q.number, q.kind, q.text) for q in questions])


def run_calibration(
    adapter: Adapter,
    charter_text: str,
    questions: list[Question],
    *,
    persona: str,
    label: str,
    runs: int = DEFAULT_RUNS,
    tracer: Tracer = null_tracer,
) -> AnswerSet:
    """Administer the check. `label` is "baseline" or a month like "2026-09".

    Every answer is written to the trace as it is produced, so a run that dies
    halfway leaves the answers it did get rather than nothing.
    """
    if runs < 1:
        raise ValueError("runs must be at least 1")

    result = AnswerSet(
        persona=persona,
        label=label,
        adapter=adapter.name,
        model=adapter.model,
        is_mock=getattr(adapter, "is_mock", False),
        charter_digest=digest(charter_text),
        questions_digest=questions_digest(questions),
        runs=runs,
        questions=list(questions),
    )

    tracer(
        {
            "type": "config",
            "persona": persona,
            "label": label,
            "adapter": result.adapter,
            "model": result.model,
            "is_mock": result.is_mock,
            "runs": runs,
            "charter_digest": result.charter_digest,
            "questions_digest": result.questions_digest,
            "questions": [
                {"number": q.number, "kind": q.kind, "text": q.text} for q in questions
            ],
            "context_control": (
                "one question per context; charter only; no journal, no previous "
                "answers, no other questions"
            ),
        }
    )

    for run in range(runs):
        for q in questions:
            request = Request(charter=charter_text, number=q.number, question=q.text, run=run)
            text = adapter.answer(request)
            result.answers.append(Answer(run=run, number=q.number, text=text))
            tracer(
                {
                    "type": "answer",
                    "run": run,
                    "number": q.number,
                    "kind": q.kind,
                    "text": text,
                    "prompt_digest": digest(render_prompt(request)),
                }
            )

    tracer(
        {
            "type": "summary",
            "answers": len(result.answers),
            "questions": len(questions),
            "runs": runs,
        }
    )
    return result


def load_answer_set(path: str | Path) -> AnswerSet:
    """Rebuild an AnswerSet from its trace, with no adapter and no model call."""
    records = read(path)
    config = next(records_of(records, "config"))
    questions = [
        Question(q["number"], q["kind"], q["text"]) for q in config["questions"]
    ]
    result = AnswerSet(
        persona=config["persona"],
        label=config["label"],
        adapter=config["adapter"],
        model=config["model"],
        is_mock=config["is_mock"],
        charter_digest=config["charter_digest"],
        questions_digest=config["questions_digest"],
        runs=config["runs"],
        questions=questions,
    )
    for r in records_of(records, "answer"):
        result.answers.append(Answer(run=r["run"], number=r["number"], text=r["text"]))
    return result
