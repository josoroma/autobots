# Tasks

## 1. Keys (A key stays out of durable state; No automatic live key check)

- [x] 1.1 Add `provider_key` and `provider_client`: read per attempt, a typed failure when missing, an injectable transport, no redirects
- [x] 1.2 Recognize Tavily, Jina and GitHub key shapes in log redaction and the evidence scan
- [x] 1.3 Cover the key's path through a real Deep Agents loop with a checkpointer on a disposable stack, and availability with sockets blocked

## 2. Refusals (A missing key disables only its provider's tools)

- [x] 2.1 Refuse run creation through a session, and a routine's occurrence, that grant an unavailable tool
- [x] 2.2 Cover runs, versions and the catalog in a browser spec on a disposable stack

## 3. Operators

- [x] 3.1 Document the tool keys and the `GITHUB_TOKEN` warning in the operations runbook and `.env.example`
