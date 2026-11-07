# Tasks

## 1. Adapters (all three scenarios)

- [x] 1.1 Add the four Tavily tools as `httpx` adapters with an injectable transport, the PRD's ceilings, inference options off, the guard on every URL, labelled and size-capped output and typed failures
- [x] 1.2 Register them in the loop, the execution contract and the Expert-grantable set

## 2. Observe

- [x] 2.1 Cover request shape, refusals, the guard, truncation and typed codes with a fake transport
- [x] 2.2 Cover a refused and an allowed call through the gateway and the tool-use record on a disposable stack
