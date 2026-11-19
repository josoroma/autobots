# Proposal: A 64K working context for deep research

Story: **US-16.8**, by [Decision 0034](../../../docs/engineering/decisions/0034-deep-research-like-content-writer.md) L6 to L8.

## Why

The first live Deep research writer run failed at its 64-model-call limit after US$0.51, with nothing written. Its 28 Google results were offloaded, being longer than 4,000 characters, and only two read-back pages stayed in view, so the model re-read the same three pages until it ran out of calls. The owner chose a 64K working context.

## What Changes

- The context budget is 64K tokens, from 8K, and compaction works toward 192,000 characters, from 24,000.
- Tool output up to 48,000 characters stays in view, from 4,000, and the latest 16 read-back pages stay in view, from 2.
- Each model call reserves 64,000 prompt tokens, from 32,000.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `run-limits`: adds the working context every run gets.

## Impact

`domain/models.py` (`CONTEXT_TOKENS`, `RESERVED_PROMPT_TOKENS`), `application/compaction.py` (`CompactionPolicy`, `LARGE_TOOL_CHARS`, `READ_PAGES_IN_VIEW`), the tests that pin them, `CODEBASE.md` and the operations runbook. No migration or contract change. The run workspace already reports the context budget from `CONTEXT_TOKENS`.
