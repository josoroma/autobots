# Tasks

## 1. Guarded path (Refuse the wrong target)

- [x] 1.1 Add `scripts/persistent_install.py` with its recorded identity, once-only setup and guarded apply, and no reset
- [x] 1.2 Test each refusal on a disposable target in `scripts/qualify_persistent_apply.py`, in the `db` profile

## 2. The install (Stand up beside other projects)

- [x] 2.1 Choose and record the project name, ports, env files and data location outside this repository
- [x] 2.2 Stand it up, and compare its listeners and other projects' Docker state

## 3. Runbooks (Exercise the runbooks on the install)

- [x] 3.1 Follow the local Supabase, local app and operations runbooks, including a drain, a stop and a start
- [x] 3.2 Back up, restore into an isolated instance, verify, and follow the upgrade runbook for one real migration
- [x] 3.3 Correct what the runbooks say about a persistent stack, and fix what the real stack found

## 4. Real goal (Run a real goal under the shared cap)

- [x] 4.1 Reserve the goal's whole budget on the shared ledger before any request, and test the refusal
- [x] 4.2 Run one goal through the install's API and worker, record its outcome and cost, and leave the inference switch off
