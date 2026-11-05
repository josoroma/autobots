# Verification — us-8-1-scoped-memory-lexical-retrieval

Change: us-8-1-scoped-memory-lexical-retrieval
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `13871ab`, working tree with this change. A real Deep Agents graph with a scripted model, real admission and Postgres on a disposable target, and a small character budget set to force compaction. `scripts/app_db.py types`: 402 cases passed. `scripts/qualify_identity.py` exit 0, 239 cases. `--profile full` passed.

## Scenarios

**Preserve critical state through compaction: observed with a scripted model.**
- A long tool result is stored whole with its hash, and the model sees a pointer and a short preview.
- Past its budget, older turns became a summary under the run's frozen `summarizer` role, through admission like any other call.
- The goal, criteria and permissions appear in the view from the run's records, outside the summary, and an open wait appears in that state from its record. The stored goal is unchanged, and checkpoints keep the whole conversation.
- The summary's citation is the stored result, worked out by code, and the view names it.
- `read_offload` serves a stored result only to its own run. Another run gets `offload_not_found`. Reading it back from its own run isn't a separate case.
- No view separated a tool call from its results, across every call in the run, plus unit fixtures for every cut.
- A truncated summary stops with `compaction_failed`, stores nothing and fails the run. A short conversation isn't summarized.

**Keep memory scoped and local: observed.**
- A keyword finds memory with its provenance, and saved evidence with its path and hash. Another workspace's memory never appears, and that workspace sees only its own.
- Query text can't be malformed, a key-like value is masked in snippets, and `authenticated` can't read stored results.
- The service code holds no embedding or reranking client, by a search of its source.

## Findings

- **Budgets are in characters.** No tokenizer is pinned, so 8K tokens is approximated. The 512-token output limit isn't sent to a provider, since no real model runs here.
- **A summary costs a model call against the root's limit.** A run near its limit can stop on one. Worst-case cost is the same route's.
- **A summarizer bound to a different profile stops with `route_not_bound`,** because a worker holds one route today. All 14 roles default to the same profile, so that only arises from an explicit override.
- **Summaries cover by message position,** so they rely on the checkpointed list only growing. It does in this graph, and it isn't enforced.
- **Not exercised:** a real summarization trigger in the SDK, which `AdmittedModel` refuses, a pending approval in the state block in a live view, a member's API search through a browser, and the owner-note route.
- **No independent review.**
