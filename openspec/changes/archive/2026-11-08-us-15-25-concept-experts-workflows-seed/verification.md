# Verification — us-15-25-concept-experts-workflows-seed

Change: us-15-25-concept-experts-workflows-seed
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension    | Status |
|--------------|--------|
| Completeness | 3/3 tasks, 1 requirement |
| Correctness  | 1/1 requirement, 4/4 scenarios observed |
| Coherence    | Follows design.md |

## Commands

- **`python3.12 scripts/verify.py --profile fast`:** exit 0, including `test_concept_seed.py`. Every one of the six graphs passes `validate_graph`, and the GitHub tools are available only with both variables set.
- **`python3.12 scripts/verify.py --profile db`:** exit 0 at 2026-11-08T19:36Z. `tests/db/concept_seed_check.py` ran the real command, `python -m autobots.operations.concept_seed`, twice into a fresh `seed-o` workspace, with no GitHub or provider variable in its environment.

## Scenario: Repeatable and separate from migrations — PASS (disposable stack)

- **Before seeding:** after migrations the workspace was empty, and no migration or seed file names any concept Expert or workflow.
- **After two runs:** each of the five Experts and six workflows exists exactly once, and each Expert has exactly one version.
- **Second run:** it reported every item as "kept", so nothing was overwritten.

## Scenario: No secrets and no pending work — PASS (disposable stack)

- **Secret scan:** the seed's source and every config, version graph and draft it stored were scanned for key, token and password shapes (`sk-`, `eyJ`, `ghp_`, `github_pat_`, `Bearer`, `password:`/`=`, `secret:`/`=`). None was found.
- **Pending work:** the workspace has 0 runs, 0 jobs and 0 routine occurrences.

## Scenario: Unavailable tools seed a draft — PASS (disposable stack)

With no GitHub variables:
- **Drafts:** Nightly test triage and Release notes from merged PRs exist only as drafts (version 0 with a draft). The seed's report names the unavailable GitHub tools that made each one a draft.
- **Published:** the others are published at version 1 with no draft, except Interview synthesis, which is always a draft.

## Scenario: Seed follows SD-02 — PASS (disposable stack)

- **Drafts and published:** Interview synthesis, Nightly test triage and Release notes from merged PRs are drafts. Monthly FX and inflation note, Vendor due diligence and Weekly competitor brief are published.
- **GitHub tools stripped:** Issue triager and Code maintainer hold no GitHub tool, and each purpose says "Saved without …" naming them.
- **Available tools kept:** Code maintainer keeps its file tools, and Market watcher keeps all five of its tools.
- **Steps:** Vendor due diligence's agent steps are labelled "Research the vendor", then "Compare and recommend".

## Findings

- **Interpretation (design.md):** SD-02 lists two inputs for some workflows. An agent's goal is one text input, so each of these takes one text input, and its description says what to put in it.
- **Interpretation (design.md):** Research analyst lacks its web-search tools without their keys and says so. Workflows using it are still published, as SD-02 says. A run's admission refuses an unavailable tool anyway.
- **Not established:** a seed against a persistent install, H1, or product acceptance.
