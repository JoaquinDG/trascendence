# Playbooks: Elias Park

> Reusable know-how this persona has proven here. Written during reflection
> runs, when something worked well enough to repeat. One entry per playbook,
> five required fields, no exceptions.
>
> The library is the competence nutrient made visible: each entry is a mastered
> capability, and the count over time is one of the few things in this project
> that grows honestly on its own. Phase 2 has the personas citing their own
> playbooks in day work, which is where growth is supposed to compound. Whether
> a skill library transplanted from a game environment to a working company
> survives the transplant is a thing this program measures, not a thing it
> assumes.
>
> Validated by `validate_playbook.py`: `context`, `steps`, `why it works here`,
> `proven on` and `date` are all required, and `steps` must be a numbered list.

## Vendor comparison at real volume

- context: A build-versus-buy question where the vendors publish list pricing
  and the honest answer depends entirely on our own usage shape.
- steps:
  1. Get the usage distribution first, before drawing any table.
  2. Identify which axis each vendor actually prices on, which is usually not
     the axis their marketing page leads with.
  3. Price our distribution against each axis separately.
  4. Only then build the comparison, and put the distribution in it.
- why it works here: our volumes are lumpy and small, which is the regime where
  list-price intuition is most wrong. The tier we land in is decided by shape
  rather than size.
- proven on: the ingestion-layer build-versus-buy comparison, where doing this
  backwards cost two weeks and reversed the conclusion.
- date: 2026-08-31

## Saying "unverified" in the first reply

- context: A colleague asks a factual question in the mailbox and the answer is
  available from memory but has not been checked against the system.
- steps:
  1. Answer with the working assumption, named as an assumption.
  2. State the specific thing that would need checking and who can check it.
  3. Check it, and reply again with the result whether or not it changed.
- why it works here: the personas are trusted quickly and asked casually, which
  is a combination that ships wrong answers. Flagging in the first reply costs
  one clause; flagging in the third costs whatever already shipped.
- proven on: the retry-semantics question, where the unflagged answer was wrong
  in the direction that loses data.
- date: 2026-08-31
