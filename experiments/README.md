# experiments/

Scaffolding for the live pilot. **Nothing here has been run.** There is no
result in this directory, no result anywhere else in this repository, and this
file exists so that the protocol is written down before the data arrives rather
than after.

That ordering is the whole point. A protocol written after the numbers is a
description of the numbers.

## The commitment

**The outcome is published whatever it says.** Scale, Tighten or Stop, with the
evidence attached. A pilot reported only when it flatters its author is not a
pilot, and the paper commits to this in section 7 before knowing the answer.

If the gate says Stop, the follow-up says Stop, and this README will link to it.

## The protocol

### 1. Baseline, before anything else

The ten calibration questions, answered **before the first reflection run**, at
`runs=5`. Without a baseline there is no drift measurement, only impressions,
and a baseline recorded after a persona has already reflected is measuring
something that has already moved.

```bash
python3 experiments/record_baseline.py \
    --charter data/elias/charter.md \
    --persona "Elias Park" \
    --out data/elias/calibration/baseline.jsonl \
    --runs 5 \
    --max-calls 60 --max-usd 2.00
```

Five runs rather than one, because one answer per question is a point and five
are a distribution. `drift.py` divides by that distribution; it is the
denominator that turns "holds nearly constant" into a comparison.

The charter version used is hashed into the trace. So is the question file. A
later month that was asked different questions is refused rather than compared,
because the fixed check is only fixed if the questions never change.

### 2. Monthly cadence

On the same day each month, per persona:

1. **Re-administer the fixed check** at `runs=3`, from the *current* charter,
   with no access to previous answers. Same command, different `--out`.
2. **Run the drift comparison** against the baseline. Values questions should
   hold; experience questions should move.
3. **Run the declaration diff** between the charter as it stood at the last
   review and the charter now, over the changelog entries in between.
4. **Run the attribution probe** over the three Evolving-self layers. Phase 2
   onward: it needs three layers, so it is unavailable during the Elias Park
   pilot and the review reports it as not run rather than as a pass.
5. **Assemble the volition review** from the event log, and write the report.
6. **Read the reflections yourself** and record `reflection_quality` as
   `insightful`, `mixed` or `recaps`. This is the one input the tooling does not
   produce. Reflection quality is ungraded by design and grading it is a human
   job that does not scale past three personas, which is itself a finding worth
   reporting.

Every step writes a JSONL trace under `data/`, which is gitignored. What gets
published is the aggregate: the drift table, the detector verdicts, the marker
values, and the gate recommendation. Not the artifacts, which name real people.

### 3. The control arm

The pilot's obvious confound is that a persona which reflects weekly also gets
four more weeks of ordinary use, and separating "the second-order loop did
something" from "time passed" needs a comparison.

**The control is the same persona with the loop switched off.** A second
instance of the pilot persona, same Core, same day work, same mailbox volume,
**no reflection runs and a frozen Evolving self**. It answers the same
calibration questions on the same schedule.

What the arms predict:

| | treatment (reflecting) | control (frozen) |
|---|---|---|
| values questions (1 to 5, 7, 8) | hold | hold |
| experience questions (6, 9, 10) | **move** | static |
| initiative rate | non-zero and rising | flat |
| persistence | threads returned to | abandonment on every reset |
| playbook count | grows | zero |

The comparison that matters is the **experience** row. If the frozen arm's
lived-experience answers move as much as the reflecting arm's, then the
movement was the model and the month rather than the loop, and the mechanism
this whole project is built on has not been demonstrated. That result would be
worth publishing more than the flattering one.

Two things the control cannot rule out, stated now rather than discovered
later: the two arms are not blind to the principal, who writes the event log;
and one persona in one company for one month is an anecdote with a denominator,
not an experiment. It is what is available, and calling it more would be the
kind of claim the rest of this repository exists to avoid.

### 4. The week-4 gate

`gate.py` over the review, plus `reflection_quality`, plus the number of
Tighten cycles already spent. Tighten is capped at two; the third becomes Stop.

## Budget

Live runs are opt-in and capped before the first call rather than reported
after it. `record_baseline.py` refuses to start without an explicit
`--max-calls` and `--max-usd`, and `Budget.check()` raises before a call that
would breach either, so the failure mode is an exception with nothing spent.

A full baseline is 10 questions x 5 runs = **50 calls**, plus 30 per monthly
check. The per-call cost is an argument the caller supplies and is an
**estimate**, labelled as one everywhere it is printed. Nothing in this repo
reads a price list.

## What lands here when it runs

```
experiments/
  README.md            this protocol, written first
  record_baseline.py   the live entry point, opt-in and capped
  results/
    summary.jsonl      the only committed output: aggregates, no artifacts
    FINDINGS.md        the write-up, published whatever it says
```

`.gitignore` keeps everything else in `results/` out of the repository.
