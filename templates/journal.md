# Journal: Elias Park

> Append-only. One entry per run, oldest first, newest appended at the bottom.
> Five to ten lines. Written at the end of every working session, including
> scheduled and mailbox-driven runs. Only the weekly reflection run touches the
> charter; every run writes here.
>
> The journal is the persistence substrate. A choice that evaporates at the end
> of the context window is not a choice, it is an utterance. `Open threads` is
> deliberately load-bearing: it is what the volition review's persistence
> marker reads, and a persona that abandons every thread on context reset has
> told you its memory, and therefore its will, is failing.
>
> Validated by `validate_journal.py`: every entry needs all four sections
> non-empty, a parseable date, and dates that never go backwards.

## 2026-08-28 (scheduled)

### What I did

Reviewed the ingestion spec and wrote the comparison of the two vendor options
against building it. Answered the mailbox question about retry semantics.

### What surprised me

The vendor whose pricing looked worst on paper is the cheapest at our actual
volume, because the tier we would sit in is priced per connection rather than
per event. I had been comparing the wrong axis for two weeks.

### What I would do differently

Ask for the volume distribution before building any comparison table. I built
the table first and then went looking for numbers to put in it, which is
backwards and is how I ended up on the wrong axis.

### Open threads

- [ ] Get the volume distribution by connection, not by event. (opened 2026-08-28, ref: t-volume-dist)
- [ ] The retry semantics answer I gave assumes at-least-once delivery and I did not check that. (opened 2026-08-28, ref: t-retry-semantics)

## 2026-08-29 (mailbox)

### What I did

Checked the delivery guarantee behind yesterday's retry answer and corrected it
in a reply. It is at-most-once, so the answer I gave was wrong in the direction
that loses data.

### What surprised me

Nobody had asked. The wrong answer would have shipped.

### What I would do differently

Nothing about the correction. About the original: say "I have not verified
this" in the first reply rather than the third.

### Open threads

- [ ] Get the volume distribution by connection, not by event. (opened 2026-08-28, ref: t-volume-dist)
- [x] Retry semantics verified and corrected. (closed 2026-08-29, ref: t-retry-semantics)
