# Tasks

## 1. Deterministic check (Check the continuation request)

- [x] 1.1 Add the comparison of a reply's reasoning metadata with the continuation request, reporting safe paths only
- [x] 1.2 Cover survived, dropped, altered and reordered through the real SDK with a fake transport
- [x] 1.3 Check the worker's real continuation path in the worker inference qualifier, and that no metadata reaches logs or activity events

## 2. Capped trial (Trial each enabled route live, Report loss honestly, Stop at the shared cap)

- [x] 2.1 Add the paid runner with the shared ledger and refusal before sending, covered with a fake transport
- [x] 2.2 Run it on each enabled route, and record the result and key usage beside the ledger
- [x] 2.3 Report any loss to the owner, without changing LC-23's text
