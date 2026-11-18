## Why

US-15.25 implements [PRD-Studio SD-01 and SD-02](../../../../docs/PRD/PRD-Studio.md#seed), under [Decision 0022 D8 and D14 to D17](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision) and SP-015. A new workspace starts empty. The owner asked for the concept Experts and workflows as an optional starting point.

## What Changes

- **A new `autobots.operations.concept_seed`** (`python -m … --workspace <id>`) seeds SD-02's five Experts and six workflows into one named workspace, through the app's own `create_expert`, `create_workflow`, `publish_version` and `save_draft`. It acts as the workspace owner.
- **Kept apart from migrations, and repeatable:**
  - a name that already exists in the workspace is kept exactly as it is, so nothing is overwritten;
  - idempotency keys guard each write;
  - it writes no secret and admits no run.
- **Tool availability** is read from the catalog for this process's environment:
  - an Expert is saved without its unavailable tools, and its purpose says which;
  - Nightly test triage and Release notes from merged PRs are drafts while their GitHub tools are unavailable;
  - Interview synthesis is always a draft;
  - the other three are published.
- **Graphs:** IR version 2, with SD-02's labelled agent steps. A `to_string` transform sits between agents, because an agent's result is JSON and the next goal is text.
- **The local-app runbook** says how to run it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `experts`: the concept seed.

## Impact

- New `operations/concept_seed.py` and `tests/test_concept_seed.py`.
- New `tests/db/concept_seed_check.py`, registered in `qualify_identity.py` on a fresh `seed-o` workspace.
- `docs/engineering/runbooks/local-app.md`.
