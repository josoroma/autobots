# Proposal: Deep research runs like Deep-Research-Content-Writer

Story: **US-16.6**, by [Decision 0034](../../../docs/engineering/decisions/0034-deep-research-like-content-writer.md).

## Why

The owner asked that a run like [Deep-Research-Content-Writer](https://github.com/josoroma/Deep-Research-Content-Writer) work in Autobots, as an Expert and as a workflow. The reference reads up to 30 pages and writes 2,000 to 5,000 cited words. Autobots' limits can't do that: a 512-token reply holds about 380 words a save, a run tree gets 24 model calls, 20 metered calls, 4 child runs and 15 minutes, and a workflow's agents can't read each other's work. The owner chose to raise the limits for every run.

## What Changes

- **Limits (L1 to L4):** each model call asks for at most 4,096 output tokens and may take 300 seconds. A run tree allows 64 model calls, 96 tool dispatches, 8 child runs, 45 active minutes and 40 metered tool calls. The refusal codes are unchanged.
- **`read_artifact` v1 (A1 to A4):** a read-only Files tool that reads a published text artifact of the run's workspace by ID, in pages of lines. Only Experts grant it.
- **Deep research writer (E1 to E5):** a seeded Expert with instructions that follow the reference's phases. Given a topic it runs them all, and given a previous step's result it reviews.
- **Agent steps' tools (F3):** a workflow execution is granted its agent steps' Experts' tools, so a step can search and read artifacts. Until now a workflow's agents got only the general tools.
- **Deep research content writer (F1, F2):** a seeded workflow: Research and write, Check and report, approval, output. It's published when `google_search` is available, otherwise a draft.
- **Seed (S1):** an Expert seed can carry instructions. SD-01 lists seven Experts and seven workflows.

## Capabilities

### New Capabilities
- `run-limits`: the reply cap, call time and run-tree limits every run gets.
- `deep-research`: the Deep research writer's two roles and the workflow whose review step reads the first step's artifacts.

### Modified Capabilities
- `tool-use-record`: a root run tree may make 40 metered tool calls, from 20.
- `file-tools`: adds reading a published artifact by its ID.
- `experts`: the concept seed creates seven Experts and seven workflows, adding the Deep research writer and its workflow.

## Impact

- `domain/models.py`, `application/run_usage.py`, `application/tool_uses.py`, `application/loop_admission.py` and `adapters/loop_middleware.py` (limits).
- `contracts/file_tools.py`, a new `application/artifact_reader.py` tool definition, `adapters/tool_registry.py`, `domain/tools.py`, `domain/execution.py`, `domain/tool_guides.py` and the pinned schema digests (`read_artifact`).
- `operations/concept_seed.py` (Expert instructions, the new Expert and workflow).
- Tests in `services/agent/tests` and `tests/db/checks`, `CODEBASE.md` and the runbooks that state limits. No migration, no new package, no web change beyond what the catalog already renders.
