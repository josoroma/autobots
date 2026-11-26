# Proposal

## Why

US-22.1 in SPECS.md: [Decision 0040](../../../docs/engineering/decisions/0040-polished-transcript.md#decision). The owner wants a transcript without timestamps that reads as coherent prose. A model reply holds 4,096 output tokens, and no tool adds to a file, so a long document can't be written a section at a time.

## What Changes

- **`append_to_file` version 1**, a Files tool granted only through an Expert, adds text to the end of a run file under `outputs/` as a new version, through `run_files`.
- **The Transcript reader's seed:** the browse saves `transcript-timed.md`, and the model reads it 60 lines at a time and adds polished prose to `transcript.md`, then publishes both. Its tools become `browse_goal`, `read_run_file`, `append_to_file` and `publish_artifact`.
- **Documents.** PRD-Tool-Catalog FI-03, PRD-Studio SD-02, the tool guide, `README-YouTube-Transcript.md`, `README-DEV.md` and `CODEBASE.md`.

## Capabilities

### New Capabilities
- `polished-transcript`: adding to a run file, and the Transcript reader's polished prose.

### Modified Capabilities
- None as requirements.

## Impact

Contracts, `run_files`, the tool registry, grants, the seed and their checks. No migration, no API contract, no web change and no fingerprinted file.
