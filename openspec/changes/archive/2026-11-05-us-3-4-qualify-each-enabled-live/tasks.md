## 1. Real adapter behavior (scenario: Qualify real adapter behavior)

- [x] 1.1 Test that every approved profile has a qualification route with the same request and canonical IDs, in `test_route_qualification.py`, and confirm it fails against a route with a different ID
- [x] 1.2 Test that no application code outside the runner asks for strict output, and confirm it fails when a request for it is added
- [x] 1.3 State the final outcome and what stays open in the US-3.4 evidence, Decision 0005 and `CODEBASE.md`, checked by reading the recorded live reports for each route

## 2. Forced selection (scenario: Test forced selection honestly)

- [x] 2.1 Confirm from the recorded live reports that the named-tool fixture ran with competing tools and a conflicting prompt on each route, and read the fixture's scoring to confirm an automatic match can't pass it
