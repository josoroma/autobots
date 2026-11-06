# Decision 0008: US-10.1's result stands, with two limits published

**Date:** 2026-11-06. **Authority:** the user, asked about both while delivering EPIC-10, chose to accept each one.

## Decision

- **Plan rejections:** task success stays at 104 of 120, 86.7%, against the 85% target, and nothing is changed to raise it. 13 of the 16 failures involved a rejected plan, so a run has little margin once its one repair is spent. This is published as a release limitation.
- **The corpus:** the 40 held-out tasks were written by the assistant, with no owner review, and scoring checks strings rather than quality. The results are kept, and the release record says so.

## Why

Both targets were met as measured. A fix would need more paid calls and a new held-out corpus, because this one can't be reused for measurement after tuning.

## What this doesn't establish

That the product is good at these tasks in general, that the tasks are independent of their author, or that any output's quality was judged by a person. Neither H1 nor product acceptance follows from it.

## Reversal

Fix plan rejections or review the corpus, then run a new held-out corpus. The earlier result stays on record as what it measured.
