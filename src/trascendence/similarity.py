"""Lexical similarity, and a loud sign saying that is all it is.

Every number in this repository that compares two pieces of text goes through
here. There is exactly one metric, it is token overlap, and it does not know
what words mean. Two answers that say the same thing in different vocabulary
score as different; two answers that reach opposite conclusions in shared
vocabulary score as similar.

That blind spot is not a footnote. A sibling project shipped a lexical
divergence score, watched it call three models that fully agreed "sharply
contested", and demoted the metric rather than keep a number that misleads in
the direction the project exists to prevent. The same discipline applies here,
so:

- `measures_meaning` is a module constant set to `False`, and every report that
  prints a similarity number prints that fact underneath it.
- Drift verdicts are relative to the baseline's *own* run-to-run variance
  rather than to an absolute threshold, which is what keeps a purely lexical
  metric usable: whatever vocabulary noise the persona has, the baseline has it
  too, and the comparison is against that noise rather than against 1.0.
- Replacing this with an embedding model or a judge is the single highest-value
  upgrade to this repo, and it stops being free, which is why it is honest P2
  work rather than a weekend regex.
"""

from __future__ import annotations

import re
import unicodedata

#: This module compares vocabulary, not meaning. Surfaces that print its
#: numbers are required to say so; `tests/test_similarity.py` pins it.
measures_meaning = False

_WORD = re.compile(r"[a-z0-9']+")

# Function words carry no persona signal and dominate short answers, so a
# Jaccard over raw tokens mostly measures English. This list is deliberately
# small and dumb: a real stoplist is a tuning knob, and a tuning knob on the
# only metric in the repo is a place to accidentally tune the result.
STOPWORDS = frozenset(
    """
    a an and are as at be been but by can do does for from had has have how i if
    in into is it its me my not of on or our so than that the their them then
    there these they this to too up us was we were what when which who will with
    would you your it's i'm
    """.split()
)


def normalize(text: str) -> str:
    """Fold case, strip accents and punctuation, collapse whitespace."""
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(_WORD.findall(folded.lower()))


def tokens(text: str, *, drop_stopwords: bool = True) -> list[str]:
    words = normalize(text).split()
    if drop_stopwords:
        words = [w for w in words if w not in STOPWORDS]
    return words


def jaccard(a: str, b: str) -> float:
    """Token-set overlap in [0, 1]. 1.0 means the same vocabulary, nothing more."""
    sa, sb = set(tokens(a)), set(tokens(b))
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: list[float]) -> float:
    """Population standard deviation. Zero for fewer than two values."""
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return (sum((v - m) ** 2 for v in values) / len(values)) ** 0.5


def pairwise(texts: list[str]) -> list[float]:
    """Every unordered pair's similarity. Empty for fewer than two texts."""
    out: list[float] = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            out.append(jaccard(texts[i], texts[j]))
    return out


def distinctive(text: str, others: list[str], *, top: int = 12) -> list[str]:
    """Tokens in `text` that are rare across `others`, most distinctive first.

    Used by the offline attribution judge. Crude on purpose: it is a floor for
    the probe, not a model, and a probe whose judge is strong is a probe whose
    result you cannot separate from the judge.
    """
    mine = tokens(text)
    if not mine:
        return []
    other_sets = [set(tokens(o)) for o in others]
    scored: dict[str, float] = {}
    for w in set(mine):
        elsewhere = sum(1 for s in other_sets if w in s)
        scored[w] = mine.count(w) / (1.0 + elsewhere * len(other_sets))
    return sorted(scored, key=lambda w: (-scored[w], w))[:top]
