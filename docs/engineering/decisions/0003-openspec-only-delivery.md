# Decision 0003: OpenSpec-only delivery

**Date:** 2026-11-05. **Authority:** explicit user request in this session, because delivery was taking far too long: "stick to what open spec most do, get rid of extra stuff but respect open spec, specialist agents and the review rounds added that are not part of open spec get rid of them." **Supersedes:** the delivery gates, roles and records in [Decision 0002](0002-ohmyorch-delivery-loop.md), for `/ohmyorch:deliver`. Its commit policy, user decisions on provider SDKs, Node and pnpm, and its boundaries stand.

## Decision

`/ohmyorch:deliver` runs OpenSpec's lifecycle in the main session: `select` → `propose` → `implement` → `verify` → `archive` → `mark-done`. The OhMyOrch plugin was cut to this on a local, unpushed `openspec-only` branch of its checkout, commit `9f384fa`, recorded as `upstream.delivery_plugin.commit` in `.claude/autobots.json`. `upstream.commit` stays the ingestor's provenance. Removed: the planner, implementer, reviewer, tester and product-manager agents; `implementation-plan.md`, `review.md`, `test-report.md`, `completion.md` and their gates; the planning-handoff and context-preflight guards; the reopen action; the project's story manifest, evidence reviews, adversarial checks and protected-path procedure.

## What this gives up

Stated plainly, because the sources still ask for more:

- **No independent review.** The same session writes, verifies and archives a story, so its verification can share its author's blind spots. In the two stories run under the previous process, independent review caught real defects before archive. `PRD-Development-Harness.md` DH-W03 and `AGENTS.md` still describe independent review. This decision overrides them for routine delivery; those sources were not rewritten then, and [Decision 0009](0009-release-scope-from-blocking-findings.md#requirements-revised) has since revised DH-W03.
- **No per-story DH-W records or fingerprint binding.** A story's record is its archived OpenSpec change and its commit. Nothing mechanical detects a change made after verification.
- **A recorded `VERIFIED` is not invalidated if code changes afterwards.** The skills instruct re-verifying, and nothing enforces it.
- **Story acceptance is unchanged.** US-1.5 (work records, independent review and evidence templates) and US-1.8 (independent baseline review, exercised runbook) still require what they say, and they are delivered as written. H1 cannot be claimed without them.

`H0`, `H1` and product acceptance claims are unaffected: harness success, and a main-session verification, do not establish them.

## Reversal

Check out the plugin's `main` (`fddfbf53c8c10d45782796cc9a7edf95bc8d3a07`), reinstall it, then restore the bridge rule and `scripts/story_manifest.py` from commit `1515fc7`. Independent review can also be requested per story without reversing this.
