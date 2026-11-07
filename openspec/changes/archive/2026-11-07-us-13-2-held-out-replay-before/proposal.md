## Why

US-13.2, PRD 8.5 and SP-016: promotion is gated by a reviewer's text checks, which a text match can pass where a real replay would catch the problem (Decision 0011's M33, review finding N-new-2). [Decision 0016](../../../docs/engineering/decisions/0016-held-out-replay.md) defines the replay that replaces them.

## What Changes

- An owner requests a replay of a proposal that passed its evidence and authority checks. The request gives held-out tasks, each a goal with criteria, and a spending limit per task.
- Each task becomes an ordinary run with the proposal applied: a skill as reference text in that run's instructions, a memory as a hit in that run's memory search only. Nothing else sees the proposal.
- A task whose goal is the goal of a run the proposal cites or came from is refused, since that's what it was drawn from.
- Promotion requires the latest replay to have passed, meaning every run `succeeded`. Otherwise it's refused with `replay_required`, `replay_running` or `replay_failed`, and the active version stays as it was.
- A reviewer's text cases become optional. They can still fail a proposal, but they no longer pass one.
- The candidate view shows the latest replay's status and its runs.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `improvements`: promotion is gated on a held-out replay.

## Impact

A migration adding `app_private.improvement_replays` and `app_private.improvement_replay_runs`. Also `application/improvements.py`, `application/memory.py`, `contracts/improvements.py`, `api/improvement_routes.py`, the generated contract and clients, `tests/db/improvement_check.py`, `scripts/app_db.py`'s improvement cases, and the API tests. No screen, by Decision 0009. **The persistent install needs this migration applied before it runs this code.** That isn't done here.
