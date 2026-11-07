# Tasks

## 1. Record (Record the three fields with the proposal)

- [x] 1.1 Migrate `runs.started_by` and the five approval columns, with the trigger that keeps them immutable
- [x] 1.2 Record who started a run at admission, through the run and workflow routes, and carry it to child runs
- [x] 1.3 Store the requester, scope snapshot and policy version with each approval request in the gateway, and pin the policy version in a unit test

## 2. Show (both scenarios)

- [x] 2.1 Return the fields in the approval view, regenerate the contract and clients, and show them in the inbox with "not recorded" for older requests

## 3. Observe (both scenarios)

- [x] 3.1 Cover both scenarios in the database check and the approvals browser spec on a disposable stack
