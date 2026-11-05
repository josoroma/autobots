# Verification — us-3-3-model-admission-spending-uncertain

Change: us-3-3-model-admission-spending-uncertain
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `fff9dd4`, working tree with this change. Real Postgres on a disposable target with fixture money, and fixtures through the real SDK. No paid call or real credential. `--profile db` and `full` exit 0.

## Scenarios

**Reserve shared budgets: observed with real concurrent connections.**
- Ten simultaneous attempts: exactly 2 admitted and 8 refused `no_inference_slot`. A settled attempt frees its slot.
- With slots raised, ten simultaneous reservations of $0.30 against the $1 run cap: exactly 3 admitted, 900000 reserved, 7 refused, and no overrun.
- 79% gives no warning, 80% gives one, exactly 100% is admitted, and one more micro-dollar gives `budget_exceeded`.
- A descendant run shares its root's budget.
- UTC rollover: at 23:59:59 the $5 daily cap refuses; two seconds later, after UTC midnight, the same workspace is at 20%. A local-offset time buckets by its UTC day.
- `authenticated` is denied the ledger.

**Keep uncertain charges explicit: observed.** A partial stream keeps the row as `uncertain`, with the full reservation, the accumulated text and no charge. That reservation still blocks new admission, and reconciling with a reported charge releases the difference. Cancelling before dispatch owes nothing. Cancelling after dispatch is `uncertain`. An uncertain attempt can't be quietly settled. A failure known to precede acceptance releases the money and keeps its row. `call_with_policy` makes no second attempt after an uncertain outcome. A missing reported charge stays open, and isn't invented. Incomplete output refuses to yield tool calls.

**Bound safe retries: observed on fixtures.** A retry waits at least `Retry-After`, 7 seconds in the fixture. At most two retries happen. A wait past the root deadline stops them, and so does cancellation. 401, 402 and unexplained statuses aren't retried. Every attempt is its own row against the same model and budget.

## Findings

- **The SDK's default retry loop was a real defect, now closed.** `openrouter` retries 5XX and connection errors with backoff for up to an hour by default, and `ChatOpenRouter(max_retries=0)` leaves that in place, which would silently redispatch paid calls past any budget or retry limit. The first test run hung on it. `chat_model` now always builds its SDK client with retries off, and tests show one request for each of 401, 402, 429, 500, 502 and 503, and for a connection error.
- **Nothing dispatches through this yet.** `dispatch` is a callable that worker stories supply, so the end-to-end path isn't exercised.
- **Real SDK failure mapping is partial.** A test shows 401, 402, 429 and 500 reach the SDK's exception with their status. Parsing `Retry-After` from it, and converting a real dropped SSE stream into `PARTIAL_STREAM`, aren't implemented, because no streaming adapter exists yet. US-3.4 or the worker story must add them, and until then a real stream failure wouldn't be classified. This is the biggest gap for this scenario in practice.
- **A crashed worker holds its slot.** Slots are counted from `reserved` and `dispatched` rows, with no expiry. US-4.2's leases must reclaim them, or a crash can leave the workspace without slots.
- **Budgets aren't connected to pricing data yet.** `worst_case_cost` takes `Pricing`, and no code reads it from the catalog.
- **Defaults:** the migration's defaults are $1 and $5 and two slots, as MP-07 says. No admin route changes them yet. Context and output limits are not enforced here.
- **`call_with_policy`'s cancellation raises `OTHER`,** a placeholder until the worker's cancellation type exists.
- This is not H1 or product acceptance.
