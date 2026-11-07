# Tasks

## 1. Adapters (all three scenarios)

- [x] 1.1 Add `search_web` and `extract_website_content` as `httpx` adapters with an injectable transport, ceilings, reader mode only, the guard and labelled, size-capped output
- [x] 1.2 Register them in the loop, the execution contract and the Expert-grantable set

## 2. Observe

- [x] 2.1 Cover request shape, model options, refusals, the guard and typed codes with a fake transport
- [x] 2.2 Cover refused and allowed calls through the gateway and the tool-use record on a disposable stack
