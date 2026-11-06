# Independent read of the release record, second version

`autobots-reviewer`, in a separate read-only context that didn't write the record. It read the second version against the PRDs, decisions, story records, and code or tests where a row turned on them. Saved in substance. Nothing was executed, and no hash was computed.

**Outcome: changes_required.** 11 blocking, 10 nonblocking. The record was then corrected for all of them, and the corrected version wasn't read again.

## Blocking

| ID | Finding | What was done |
|---|---|---|
| RR-1 | "H1: met, with one stated limit" overclaimed. H1.3 asks that DH-W01–06 records be complete, Decision 0012 revises only the hook clause, and Decision 0003 leaves H1 claims unaffected | **H1 is no longer claimed.** Put to the owner as decision 1 |
| RR-2 | MP-A06 was "Partial, accepted", where Decision 0005 accepts only DeepSeek's strict nested output | Split, and the rest is partial |
| RR-3 | MP-A07 wasn't partial, though "Unsupported selectors fail honestly" was never exercised | Partial |
| RR-4 | DS-04, DS-05 and LC-34 weren't partial, though keyboard order, disabled controls, and zoom and reduced motion in both themes weren't observed | Partial, with the gaps listed |
| RR-5 | LC-25 wasn't partial, though no instrumented dispatch inventory exists | Partial |
| RR-6 | PRD 12.2's metrics were listed only as a limit, with no decision revising them | Decision 6 |
| RR-7 | DeepSeek stays selectable with no task qualification, listed only as a limit | Decision 4 |
| RR-8 | The two-call workload is unmeasured, with no decision revising the target | Decision 5 |
| RR-9 | Items marked "later" in US-11.12's dispositions were a reviewer's suggestion, not an owner's decision, including fields PRD 9.2 requires | Decision 7, with LC-10 partial |
| RR-10 | "Nothing below can be settled by another check" was false, as most partial rows need no owner | Separated what engineering can close |
| RR-11 | Revisions for US-3.4 and LIVE-GOAL-1 were wrong or missing, and LC-12 cites a run at a configuration not in the repository | Corrected from their records |

## Nonblocking

RR-12 (LC-09's accepted corner), RR-13 (two sleeps, only one with the fix, and a scripted model), RR-14 (Studio, and what "restart" ran), RR-15 (tokens where the refusal counts bytes), RR-16 (runbooks missing from the table), RR-17 (class vocabulary), RR-18 (no H0 line), RR-19 (LC-17's test scope), RR-20 (LC-08 and US-10.1's real kills), RR-21 (binding limits). All corrected in the record.

## What the reviewer found sound

- **No promotion to live:** no template, skip, mock or disposable result is presented as live.
- **Figures** matched their sources: checks, cases, contrast, migrations, spend, trials.
- **Coverage:** every LC, MP, LM, DS, DH-A and DH-W ID has a row.

## Limits of the read

Records for US-4.x, US-5.x, US-6.x, US-7.1, US-9.2 and US-9.3, and most `tests/db` bodies, weren't read, so rows resting only on them were checked against the record's text and the PRD. `.checks` files can be edited by hand.

Outcome line as returned: `outcome: changes_required`
