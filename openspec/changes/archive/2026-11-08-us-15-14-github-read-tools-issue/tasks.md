# Tasks

## 1. Tools (Read tools against a fake transport; Bounded inputs; File content stays private)

- [x] 1.1 Add the four read tools as plain `httpx` adapters with an injectable transport over the shared repository configuration, with schema ceilings, public fields and fake-transport fixtures
- [x] 1.2 Register `create_github_issue` version 2 with optional `labels`, up to 10, keeping version 1 unchanged and registered

## 2. Keys (Key missing until both are set)

- [x] 2.1 Report `key_missing` for every GitHub tool until both variables are set, with a repair naming them, the token's scopes and a restart, and update the operations runbook with D6's permissions

## 3. Coverage

- [x] 3.1 Cover the scenarios with fake transports only: `test_github_reads.py`, `connector_check.py` through the real gateway on a disposable database, and `tools.spec.ts`
