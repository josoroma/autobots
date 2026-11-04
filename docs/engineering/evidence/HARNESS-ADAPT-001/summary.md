# HARNESS-ADAPT-001 evidence

**Scope:** project-local OhMyOrch ingestion adaptation and deterministic repository tooling. Application delivery and complete H0/H1 are not claimed.

The [verification manifest](verification.json) records the final tested inputs and actual command outcomes. [Upstream provenance](upstream.json) identifies the pinned source. [Work record](../../work-items/HARNESS-ADAPT-001.md) contains the plan, changes and review; the [runbook](../../runbooks/development-harness.md) contains the exercised procedure.

## Observed results

- Backlog validation: 10 epics, 42 stories, 84 tasks; all 21 preserved SP requirements mapped. Navigation is derived and rendering is idempotent.
- Local behavioral suite: 45 passing parser/hook/report/configuration tests under Python 3.12.16. Negative fixtures reject malformed Gherkin, missing source locations, invalid/cyclic dependencies, stale navigation, path escapes, incomplete reports, empty/disabled/asynchronous hooks and stale fingerprints.
- Skills: all 13 passed the bundled skill validator; seven agents and seven path-scoped rules were reviewed. Read-only roles exclude shell and write tools.
- Independent forward ingestion: [retained synthetic fixture](forward-fixture/SPECS.md) has two READY stories, one missing-decision story and one source-conflict story. Prototype retry behavior remained descriptive. Only fixture SPECS changed; the ingestion summary stayed outside it.
- Unsupported Python 3.9 now returns an actionable nonzero error; hooks use the Mac's existing absolute Python 3.12 path. No interpreter was installed.
- The unimplemented database profile returns nonzero `not_implemented` and performs no database action.

## Review and corrections

Independent reviewers found and verified corrections for weak report acceptance, empty hook configuration, missing mapped-document fingerprints, disabled/asynchronous policy hooks, ingestor heading grammar and summary placement. The forward exercise found the Python PATH mismatch. These are observed corrections, not a claim that every conceivable behavior is tested.

## Boundaries and retention

No application dependencies installed; no database/container started or mutated; no provider credential read or changed; no paid inference. Claude Code version inspection and valid project settings are not actual hook-event delivery qualification. The hook guard is deliberately limited and is not an OS/shell sandbox.

Raw local command output is retained under `.checks/HARNESS-ADAPT-001/` and the latest profile output under `.checks/harness/`. Keep it through review/acceptance; if removed later, record its unavailability. The versioned manifest preserves expected/observed results, hashes and reproduction details; the synthetic forward fixture is retained here for direct validation. No secret-bearing logs are part of this evidence.
