# Decision 0015: What an approval request records about who, scope and policy

**Date:** 2026-11-07. **Authority:** the owner, who answered [US-13.1's four open questions](../../../SPECS.md#us-131-requester-scope-snapshot-and-policy-version-on-an-approval-request) and scheduled the story, which [Decision 0013](0013-release-closure.md#decision) left for them to do after the release. Each answer was the option recommended to them.

## Decision

| Question | Choice |
|---|---|
| **Who is the requester** when a model proposes the action | Both: the person who started the run, and the agent that proposed the call (its Expert ID and version, or the coordinator when the run has no Expert). A run doesn't record who started it today, so admission records it from now on |
| **What the scope snapshot holds** | The exact grants `scope_hash` is computed from: granted tools with their pinned versions, and granted paths. It's stored with the request, immutable, and must hash to the stored `scope_hash` |
| **Which policy the policy version names** | A versioned approval policy identifier held in the gateway's code, such as `approval-policy/1`, with the rule that fired: the tool is marked to wait for a person, or it's a consequential external write. The version changes whenever those rules or their reason text change |
| **Whether the inbox shows them** | Yes, below the reason and target. A request saved before these fields existed shows each as not recorded, as reason and target already do |

**Scheduling:** the `External:` dependency on US-13.1 is met by this decision. [US-13.2](../../../SPECS.md#us-132-held-out-replay-before-promotion) stays unscheduled.

**Spending and the install:** nothing here authorizes a paid call or a persistent change. The story's migration is proven on a disposable stack. Applying it to the real install is a separate persistent change that still stops for the owner, as in [Decision 0014](0014-release-limits-accepted.md#decision).

## Requirements revised

None. These answers fill in PRD 9.2's requester, scope snapshot and policy version without changing its text. PRD 12.1's inbox list is a minimum, and showing more doesn't revise it.

## What this gives up

- **Older requests and runs stay incomplete.** Nothing is backfilled, because the values weren't recorded and guessing them would invent history.
- **The policy version is only as honest as its bumps.** A rule change made without changing the version would go unrecorded. Review of gateway changes has to check it.
- **The requester is identity, not intent.** It shows who started the run and which agent proposed the call, not why the model chose it.

## Reversal

Each choice can change later under US-13.1's ID. Requests stored under it keep the fields they were stored with.
