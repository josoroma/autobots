# Design

## Context

See proposal.md for why. The limits are constants: `MAX_OUTPUT_TOKENS` (domain/models.py), the `RootLimits` defaults (application/run_usage.py), `METERED_TOOL_CALLS` (application/tool_uses.py) and `model_call_seconds` (application/loop_admission.py and adapters/loop_middleware.py). Tests mostly read them by name. A workflow's agent step delegates through `assign_specialist`, whose `AssignmentResult` carries only references, and `read_run_file` reads only the calling run's files. `application/artifacts.read_artifact` already reads a published artifact for the download route, scoped by workspace and checked against its hash.

## Goals / Non-Goals

**Goals:** the Decision 0034 limits for every run; `read_artifact` so a workflow step can read an earlier step's published work; the Deep research writer and its workflow in the concept seed.

**Non-Goals:** per-Expert limits; a template transform for workflow goals; changing the context budget or the per-call prompt reservation; live runs (US-16.7).

## Decisions

- **One constant per limit.** Change the defaults in place, and keep the call time's two defaults equal, the middleware's and the admission's. Existing tests that build `RootLimits(...)` with explicit values keep them.
- **`read_artifact` wraps `artifacts.read_artifact`.** The tool resolves the workspace from the run's scope, never from arguments. It reuses `read_run_file` v2's line paging over the decoded text, and refuses a non-text media type before decoding. It needs the object store, like `publish_artifact`, and refuses with `RuntimeUnbound` without one. It's `READ_ONLY` and granted through `EXPERT_TOOLS`, so a plain goal never gets it.
- **Two roles in one Expert, chosen by its goal.** No transform can prefix a stage instruction, so the instructions say what to do with a topic and with a previous step's result (a JSON object with `artifact_ids`). The workflow's second step gets the first step's `AssignmentResult` as text, and reads the artifacts it names.
- **The seed carries instructions.** `ExpertSeed` gains an `instructions` field, empty by default, so the six earlier Experts are unchanged. The workflow lists `google_search` in its needs, so it is a draft without SerpApi.

## Risks / Trade-offs

- A larger reply reserves more for each call, so a small budget admits fewer calls. The budget and daily cap still bound spend.
- A 4,096-token document can still be cut by `length`. The existing single shorter retry applies, and the instructions target 2,000 to 2,800 words.
- The two-role switch depends on the model following the instructions. The scripted check proves the mechanism (artifacts flow through `read_artifact`), not the model's judgment. US-16.7's live runs observe that.
