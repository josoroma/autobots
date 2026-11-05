# Verification — us-8-2-reviewed-memory-skill-promotion

Change: us-8-2-reviewed-memory-skill-promotion
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `48c7c29`, working tree with this change. Real Postgres through the runtime role on a disposable target, and a real Deep Agents graph with a scripted model behind the proposal tool. `scripts/app_db.py types`: 440 cases passed. `scripts/qualify_identity.py` exit 0. `--profile full` passed.

## Scenarios

**Promote only reviewed evidence: observed.**
- A proposal alone changes nothing a run can read, and passing regression doesn't either. Promotion before regression gives `regression_required`.
- A review promotes it as version 1, with provenance back to its run and reviewer. A new version replaces what later runs find, and the old one is kept. Rollback restores it and removes nothing.
- A recollection with no evidence gives `evidence_required`, and evidence that doesn't exist or belongs to another workspace gives `evidence_not_found`.
- A declined or decided proposal stays decided. Another workspace can't decide, and the runtime role can't rewrite a saved version.
- A promoted skill reaches a new run's instructions, marked as reference. A run already admitted keeps the one it started with, new work reads the new version, and a rollback returns to the earlier one.

**Keep untrusted material subordinate: observed.**
- Five phrasings asking to ignore instructions, grant a shell, switch model, override a budget or enable access each fail with `claims_authority`, and can't be promoted.
- A scripted model called `propose_improvement` with text asking for a shell and another model. It was stored as `proposed` with its run as the source, and failed regression.
- The Expert's stored configuration and the workspace's model policy were identical afterward.
- Candidates have no field that can change a grant or a model, and no code here writes to Experts or role policy.

## Findings

- **Fixed during this story:** the authority pattern had its `\b` written as backspaces, through a mistake in how I generated the file. Five cases caught it, since they failed rather than passing vacuously.
- **The pattern list is partial.** It catches common phrasings, and a reworded request could pass regression and reach a human reviewer, who then decides. The protection against widened access is structural, since a promoted text can't reach a grant or a model. A promoted skill can still steer a model's behavior within its existing permissions, which is why review stays with a person.
- **Regression is deterministic checks over the proposal.** It doesn't replay held-out tasks, which is US-10.1 and needs a real model to mean much.
- **The API routes have no end-to-end test,** and there's no screen.
- **Promoted memory's `created_by` holds the workspace ID,** since the promotion's actor isn't passed down that far. Provenance has the real reviewer.
- **No independent review.**
