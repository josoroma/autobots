# Tasks

## 1. Storage (remove marks a routine removed and keeps its history)

- [x] 1.1 Migration 53: add `removed_at`, and make a routine's name unique only among live routines. Record it in schema readiness
- [x] 1.2 Add `remove_routine` and `run_routine_now` to the routine service. Removed routines are skipped by its lists, edits and evaluation, and a paused routine refuses `run`

## 2. Tool (The catalog lists cronjob; list runs without approval; Every other action waits; create and update; pause and resume; run; Granted only through an Expert; Only public fields)

- [x] 2.1 Add the input and output contracts, the group `automation` and the approval value `by_action`
- [x] 2.2 Add `cronjob` v1, register it in the loop registry and EXPERT_TOOLS, and approve per call with the gateway's `approval_when`

## 3. Screen

- [x] 3.1 Add the Automation group and the `by_action` approval label to the Tools page, and regenerate the contract and client

## 4. Coverage and docs

- [x] 4.1 Unit tests and a disposable database check with no model
- [x] 4.2 Update the runbook and CODEBASE
