# Decision 0014: The release's last limits

**Date:** 2026-11-06. **Authority:** the owner, who went through [US-10.2's six open items](../evidence/US-10.2/summary.md#what-needs-the-owner) and chose one option for each. Items 2 to 6 took the recommended option. For item 1 they chose the alternative, recording the cause now.

## Decision

| Item | Choice |
|---|---|
| **A run can pause with no recorded cause** (LM-A09, PRD 13.1) | Record the cause now, in a new story. The pause itself isn't fixed, and it stays a stated limit |
| **Network loss, and a real provider across a sleep** (LM-A07) | Accepted as limits |
| **Unsupported selectors, and a provider's own stop on cancel** (MP-A06, MP-A07) | Accepted as limits |
| **Restarting Docker** (LM-A04, LM-07) | Means this project's containers, which is observed. A restart of Docker itself or of the Mac is a stated limit, as it would also stop `finance` and `mentor` |
| **Active time can go uncounted** (PRD 6.5) | Accepted as a limit. Model-call, tool and money limits don't depend on it |
| **What only the delivery session had accepted** | Accepted: after a stop, a step already running can send further paid calls (N-70). A page reload loses Continue's kept key, so a later press can start a second paid run. US-10.1's result stands across EPIC-11 and EPIC-12 without repeating its corpus |

**How the cause is recorded:** in the worker's structured log, by the delivery session's choice. A column would need a migration, leaving the stopped install behind the code unless a further persistent change were authorized. So the inspector doesn't show it. This can change later under the same story's ID.

**Spending and the install:** nothing here authorizes a paid call or a persistent change. Decision 0013's authority for those has ended.

## Requirements revised

IDs stay, and each requirement's text is edited to match.

- **LM-07 and LM-A04:** a restart means this project's containers. A restart of Docker itself or of the Mac is a stated limit.

Recorded by the delivery session, and not chosen by the owner:

- **Older text:** `PRD-Comparison-Recommendation.md` still says Docker restart. It's the rationale for Option B, and it reads under this decision without being rewritten.
- **Not revised:** PRD 13.1's stability target. It isn't met or changed, and the pause stays a stated limit against it.

## What this gives up

- **A person can still be asked to rule on a charge that may not exist.** They'd find the cause in a log, not on the screen.
- **A dropped connection to a real provider, in or out of a sleep, stays unobserved through this worker.**
- **A run can exceed 15 active minutes in rare clock cases,** still bounded by its calls, tools and money.
- **Task quality wasn't measured on the final code.** It rests on an earlier corpus, scored by string checks.

## Reversal

Each can be changed later under its existing ID. No data depends on these choices.
