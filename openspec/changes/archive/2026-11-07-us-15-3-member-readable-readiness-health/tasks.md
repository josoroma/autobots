# Tasks

## 1. API (Nothing private in the member read)

- [x] 1.1 Add `ServiceReadiness` and `MemberReadiness` contracts and an auth-only OpenRouter state read with no network call
- [x] 1.2 Add `GET /v1/readiness` for workspace members, regenerate the contract and client, and add Python tests: states only, a worker without a heartbeat, a member who isn't the owner

## 2. Web (All ready; Name the service that isn't ready)

- [x] 2.1 Add the shell's health line and Home's service chips, each in words
- [x] 2.3 Separate each chip's service name from its state with a space, so the words read correctly to assistive technology (found by the first `db` run)
- [x] 2.2 Cover both scenarios in browser specs with axe on a disposable stack: "all ready" with an arranged heartbeat and configured key, and the worker absent
