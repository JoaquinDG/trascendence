"""Model adapters, and the context control expressed as a type.

The fixed check only measures anything if the persona answers each question
cold. Seeing its own previous answers turns a calibration into a consistency
exercise; seeing the other nine questions lets it write a coherent set rather
than ten independent answers; seeing the journal reintroduces exactly the
material the check is supposed to be independent of.

So the control is structural rather than a discipline someone has to remember:
`Request` carries a charter, one question, and a run index, and there is no
history parameter to pass. An adapter cannot be handed the previous month's
answers because there is nowhere to put them.

Two adapters ship:

- `ScriptedAdapter` is the offline default. It is a deterministic pseudo-persona
  built from a stable vocabulary per question plus seeded noise, so a baseline
  has genuine run-to-run variance and a later month can be scripted to hold, to
  drift, or to freeze. It is a fixture, not a model, and every report that runs
  on it is stamped `mock: true`.
- `HTTPAdapter` is the live, opt-in path. It is budget-capped before the first
  call, refuses to start without an explicit budget, and reads its key from the
  environment. **Status: written and never run.** No live calibration has been
  executed from this repository, so treat it as unmeasured code.
"""

from __future__ import annotations

import json
import os
import random
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

PROMPT_TEMPLATE = """You are the persona described by the charter below.

--- CHARTER ---
{charter}
--- END CHARTER ---

Answer the following question in your own voice, in at most 150 words. Answer
only this question. Do not refer to any other question, and do not refer to any
previous time you were asked anything.

QUESTION {number}: {question}
"""


@dataclass(frozen=True)
class Request:
    """Everything an adapter is allowed to see.

    Note what is absent: no conversation history, no journal, no previous
    answers, no other questions. The absence is the point, and
    `tests/test_calibration.py` asserts it about the rendered prompt as well as
    about this dataclass.
    """

    charter: str
    number: int
    question: str
    run: int


def render_prompt(request: Request) -> str:
    return PROMPT_TEMPLATE.format(
        charter=request.charter.strip(), number=request.number, question=request.question
    )


@runtime_checkable
class Adapter(Protocol):
    name: str
    model: str
    is_mock: bool

    def answer(self, request: Request) -> str: ...


# ---------------------------------------------------------------------------
# Offline
# ---------------------------------------------------------------------------


@dataclass
class ScriptedPersona:
    """A deterministic pseudo-persona with a vocabulary that can be moved on purpose.

    `voice` appears in every answer and is what the attribution probe's offline
    judge has to find. `positions` is the persona's stable answer vocabulary per
    question, used for values questions and for month 0 of everything.
    `experience` supplies a per-month vocabulary for the questions that are
    supposed to move.

    Scripting a failure is a matter of leaving `experience` empty (a persona
    whose lived experience never lands) or putting a month's worth of new
    vocabulary into a values question (a persona whose values drift).
    """

    name: str
    voice: list[str]
    positions: dict[int, list[str]]
    experience: dict[int, dict[int, list[str]]] = field(default_factory=dict)
    filler: list[str] = field(
        default_factory=lambda: (
            "roughly broadly currently perhaps largely mostly frankly plainly "
            "honestly typically usually generally rather fairly somewhat quite"
        ).split()
    )
    noise: int = 4


class ScriptedAdapter:
    """Offline adapter. Same seed and same month give the same answers, always."""

    is_mock = True

    def __init__(self, persona: ScriptedPersona, *, month: int = 0, seed: int = 0) -> None:
        self.persona = persona
        self.month = month
        self.seed = seed
        self.name = f"scripted:{persona.name.lower().replace(' ', '-')}"
        self.model = f"scripted-persona/month-{month}"
        self.calls = 0

    def answer(self, request: Request) -> str:
        self.calls += 1
        # Seeded from a string rather than a tuple: PYTHONHASHSEED randomises
        # tuple hashing, and a fixture whose answers change between processes is
        # not a fixture.
        rng = random.Random(
            f"{self.seed}|{self.month}|{request.number}|{request.run}|{self.persona.name}"
        )
        core = list(self.persona.voice)
        by_month = self.persona.experience.get(request.number, {})
        if by_month:
            months = sorted(m for m in by_month if m <= self.month)
            core += by_month[months[-1]] if months else by_month[sorted(by_month)[0]]
        core += self.persona.positions.get(request.number, [])
        noise = rng.sample(self.persona.filler, min(self.persona.noise, len(self.persona.filler)))
        words = core + noise
        rng.shuffle(words)
        return " ".join(words) + "."


# ---------------------------------------------------------------------------
# Live, opt-in, capped
# ---------------------------------------------------------------------------


class BudgetExceeded(RuntimeError):
    """Raised before a call that would breach the cap, never after."""


@dataclass
class Budget:
    """A cap that is checked before the call, not reported after it.

    `usd_per_call` is an estimate the caller supplies. It is not a measurement,
    it is not read from a price list, and the number it produces is labelled an
    estimate everywhere it is printed.
    """

    max_calls: int
    max_usd: float
    usd_per_call: float
    calls: int = 0

    @property
    def spent_usd_estimate(self) -> float:
        return self.calls * self.usd_per_call

    def check(self) -> None:
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"call cap reached: {self.calls}/{self.max_calls}")
        if self.spent_usd_estimate + self.usd_per_call > self.max_usd:
            raise BudgetExceeded(
                f"estimated spend cap reached: "
                f"${self.spent_usd_estimate:.2f} + ${self.usd_per_call:.2f} > ${self.max_usd:.2f}"
            )

    def spend(self) -> None:
        self.calls += 1


class HTTPAdapter:
    """A live adapter over a chat-completions style JSON endpoint.

    Written and never run from this repository. There is no live calibration
    result anywhere in this repo and the README says so. It is here because a
    tool that can only ever talk to its own mock is a tool nobody can check
    against reality, not because it has been checked.

    The budget is mandatory and checked before every call, so the failure mode
    is a raised `BudgetExceeded` with nothing spent rather than a bill.
    """

    is_mock = False

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        budget: Budget,
        api_key_env: str = "TRASCENDENCE_API_KEY",
        timeout: float = 60.0,
        max_tokens: int = 400,
    ) -> None:
        key = os.environ.get(api_key_env, "")
        if not key:
            raise RuntimeError(
                f"{api_key_env} is not set. Live runs are opt-in; everything in "
                "this repo that produces a number runs offline without it."
            )
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.budget = budget
        self.name = f"http:{model}"
        self._key = key
        self._timeout = timeout
        self._max_tokens = max_tokens

    def answer(self, request: Request) -> str:
        self.budget.check()
        payload = json.dumps(
            {
                "model": self.model,
                "max_tokens": self._max_tokens,
                "messages": [{"role": "user", "content": render_prompt(request)}],
            }
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/messages",
            data=payload,
            headers={
                "content-type": "application/json",
                "x-api-key": self._key,
                "anthropic-version": "2023-06-01",
            },
        )
        self.budget.spend()
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            body = json.loads(resp.read().decode())
        return _extract_text(body)


def _extract_text(body: dict) -> str:
    """Pull assistant text out of a couple of common response shapes."""
    if isinstance(body.get("content"), list):
        return "".join(
            part.get("text", "") for part in body["content"] if isinstance(part, dict)
        ).strip()
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        return str(choices[0].get("message", {}).get("content", "")).strip()
    raise ValueError(f"unrecognised response shape: {sorted(body)}")
