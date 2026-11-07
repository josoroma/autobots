# Tasks

## 1. Tool (A read-only browse is summarised and recorded)

- [x] 1.1 Define `browse_goal` v1's input and output contracts, limits and public fields, as `arbitrary_execution`, metered, approval always, provider `autobots`
- [x] 1.2 Implement its handler: one executor session for the call's domains, the request guard, a CDP page, and the US-14.14 loop on the run's researcher route through the current middleware, with the session removed when the call or the attempt ends

## 2. Refusals and limits (Outside its domains, a submission, an invalid answer and its limits)

- [x] 2.1 End the call `refused_action` on a navigation outside its domains or one the browser refuses, `invalid_action` on an invalid answer, and `max_steps` or `max_seconds` at its limits, keeping the summary so far

## 3. Grants (Granted only through an Expert, approved on every call; Stays disabled while unqualified)

- [x] 3.1 Admit `arbitrary_execution` in the registry and gateway only for a tool whose executor reports qualified, and refuse a run with no Expert behind it
- [x] 3.2 Grant it only through Experts, catalogued `disabled_by_policy` while unqualified, and bind it in the worker when the executor is qualified
- [x] 3.3 Remove the `browser_use` provider value from the catalog, contract, generated client and Tools screen

## 4. Coverage

- [x] 4.1 Cover the scenarios offline, and live on a disposable stack with the real executor, example.com and a scripted model
