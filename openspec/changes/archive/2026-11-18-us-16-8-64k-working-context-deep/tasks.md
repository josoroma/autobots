## 1. The context

- [x] 1.1 Set `CONTEXT_TOKENS` to 64,000, `RESERVED_PROMPT_TOKENS` to 64,000, `CompactionPolicy.context_chars` to 192,000, `LARGE_TOOL_CHARS` to 48,000 and `READ_PAGES_IN_VIEW` to 16. Check: unit tests read each value.
- [x] 1.2 Update the tests that pin the old values. Check: the agent unit tests and the `fast` profile pass.

## 2. Scenarios

- [x] 2.1 Show that 28 search results of about 14,000 characters stay in view, and that a 60,000-character output read back in 15 pages has all 15 in view. Check: unit tests of `offload_large` with the default policy.
- [x] 2.2 Run the `db` profile, since the loop's compaction runs there. Check: it passes.

## 3. Records

- [x] 3.1 Update `CODEBASE.md` and the operations runbook. Check: harness profile passes.
