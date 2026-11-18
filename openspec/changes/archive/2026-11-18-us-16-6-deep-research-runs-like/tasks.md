## 1. Limits (Decision 0034 L1 to L4)

- [x] 1.1 Set `MAX_OUTPUT_TOKENS` to 4,096, the `RootLimits` defaults to 64 model calls, 96 tool dispatches, 8 children and 2,700 active seconds, `METERED_TOOL_CALLS` to 40, and the model call time to 300 seconds. Check: unit tests read each value, the fake OpenRouter request carries max_tokens 4096, and the reservation is computed at that size.
- [x] 1.2 Update the tests, database checks and comments that pin the old values. Check: `fast` and `db` profiles pass.

## 2. `read_artifact` (A1 to A4)

- [x] 2.1 Add `ReadArtifactInput` and `ReadArtifactOutput`, the tool definition over `artifacts.read_artifact`, its registry entry, `EXPERT_TOOLS` and `TOOL_VERSIONS` entries, its guide and its pinned schema digest. Check: catalog and execution-contract unit tests.
- [x] 2.2 Cover the refusals and the paging. Check: a disposable database check reads a published markdown artifact, a staged one, an image, a lost one and another workspace's.

## 3. Seed (E1 to E5, F1, F2, S1)

- [x] 3.1 Let `ExpertSeed` carry instructions, and add the Deep research writer with its purpose, instructions and eight tools. Check: concept seed unit tests.
- [x] 3.2 Add the Deep research content writer workflow, published when `google_search` is available, otherwise a draft. Check: the concept seed database check, with and without SerpApi, run twice.

## 4. The workflow on a scripted model

- [x] 4.1 Run the workflow on a disposable stack with a scripted model: the first step publishes four files, the second reads them with `read_artifact` and publishes its review, and the approved gate settles the output. Check: a scenario in the workflow run database check.

## 4b. Agent steps' tools (F3)

- [x] 4.2 Grant a workflow execution its agent steps' Experts' tools, narrowed by a requested list. Check: `test_workflow_grant.py`, and the workflow scenario's second step reading with `read_artifact`.

## 5. Records

- [x] 5.1 Update `CODEBASE.md` and the runbooks that state the limits. Check: harness profile passes.
