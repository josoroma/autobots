# Proposal

## Why

US-21.1 in SPECS.md: [Decision 0039](../../../docs/engineering/decisions/0039-browse-result-saved-to-a-file.md#decision). A browse's long typed result reaches the model, which must retype it into `save_artifact`. A reply holds 4,096 output tokens, so a long one can't be saved.

## What Changes

- **`browse_goal` version 4.** An optional `save` beside `output_schema` has the worker write the validated result to a run file. The output names the file in place of the result, or says why it wasn't saved. Versions 1 to 3 keep their schemas. New grants take version 4.
- **The Transcript reader's seeded instructions** save that way, then publish.
- **Documents.** PRD-Tool-Catalog AB-05, PRD-Studio SD-02, the tool guide, `README-YouTube-Transcript.md`, `README-DEV.md` and `CODEBASE.md`.

## Capabilities

### New Capabilities
- `saved-browse-result`: a browse's typed result saved straight to a run file.

### Modified Capabilities
- None as requirements. `transcript-reader` and `browser-use-typing` hold as written.

## Impact

Contracts, the browsing tool, typed results, the grant map, the seed and their checks. No migration, no API contract, no web change and no fingerprinted file, so the browser images stay qualified.
