# Measure the two-call workload

## Why

PRD 13.1 asks for stable operation with two model calls at once, and SP-021 says meet or explicitly revise. Every goal so far ran one at a time. Decision 0013 chose to measure it.

## What Changes

A runner kept with the evidence, as a file under `scripts/` would void US-12.3's binding. It runs two goals at once on Terra through the real API and two workers, on a disposable stack, sampling CPU, memory, disk and connections.

## Impact

No source change. Paid, under the shared ledger's US$1 cap.
