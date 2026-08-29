# data/ is gitignored, on purpose, from the first commit

Nothing in this directory is committed except this file.

Trascendence is not a simulation. The pilot runs inside a working company,
among colleagues who did not sign up to be research subjects. A persona's
charter names the people it works with. Its journal records what surprised it
about a real meeting. Its calibration answers include, by design, question 10:
"one opinion you hold that you suspect the principal disagrees with." Its event
log is a week-by-week record of who pushed back on whom.

That material is exactly what the tooling in `src/trascendence/` reads. It is
also exactly what must never end up in a public repository, so the split is
structural rather than a matter of remembering:

- **Real pilot artifacts live here**, under `data/`, and `.gitignore` excludes
  the whole directory. The exclusion was in the first commit, before any
  artifact existed, because a rule added later is a rule that has already been
  broken once.
- **Everything committed is synthetic.** The fixtures under `evals/fixtures/`
  are invented personas written to exercise the detectors. They are not
  anonymized real data; they were never real.
- **The personas in this repository are pseudonyms.** Elias Park (technologist,
  the Phase 1 pilot), Clara (product), Owen (growth), collectively the Flock.
  The human they report to is "the principal". No real company, colleague, or
  internal tool is named anywhere in this repository, and
  `tests/test_anonymization.py` fails the build if one appears.

## Suggested layout

```
data/
  elias/
    charter.md              current charter
    charter.history/        dated snapshots, input to declaration_diff
    journal.md              append-only
    playbooks.md
    calibration/
      baseline.jsonl        N runs, recorded before the first reflection run
      2026-09.jsonl         monthly, answered without seeing previous answers
    events.jsonl            the five markers read this
  reviews/
    2026-09-elias.jsonl     volition_review output
    2026-09-elias.gate.jsonl
```

Every tool in this repo takes paths as arguments and defaults to nothing, so
pointing them at `data/` is a deliberate act rather than a default that leaks.

## If you are reproducing this

Do not ask for the pilot data. It is not being published, and the follow-up
paper will report aggregate results and the gate outcome rather than the
artifacts themselves. What is reproducible is the tooling: the fixtures, the
evals, and the offline demo all run with no keys and no access to anything
private.
