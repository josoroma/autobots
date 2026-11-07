# Decision 0016: What a held-out replay is, and what passes it

**Date:** 2026-11-07. **Authority:** the owner, who asked the delivery session to answer [US-13.2's three open questions](../../../SPECS.md#us-132-held-out-replay-before-promotion) with the best-reasoned option, and to continue. That schedules the story, which [Decision 0013](0013-release-closure.md#decision) left for them to do after the release. Each answer below is the option the session reasoned best. The owner can change any of them under US-13.2's ID.

## Decision

| Question | Choice |
|---|---|
| **Which held-out tasks, and who keeps them apart** | The owner writes them when they request a replay: each is a goal with its acceptance criteria, stored with that replay. A proposal's own suggested cases are never used. The server refuses a task whose goal is the goal of a run the proposal cites as evidence or came from, since that's what it was drawn from |
| **Whether a replay uses a real model, and who authorizes its spending** | Yes. Each task is an ordinary run, through the shared gateway on the workspace's model policy, with the proposal applied: a skill as reference text in that run's instructions, a memory as a hit in that run's memory search only. The owner authorizes each replay by requesting it, with a stated spending limit per task, as PRD 9.2 has a person's Run authorize bounded calls. This story's checks use a scripted model only, and no paid replay is authorized or run under it |
| **What counts as passing** | Every task's run ends `succeeded`, so its own verification of the task's criteria passed, with at least one task. A run that fails, is cancelled or hasn't finished means no pass. A failed replay can be followed by a new one, and only the latest counts |

**Its place in promotion:** the replay takes the place of the reviewer's text checks as what lets a proposal pass. The evidence and authority checks still run first. A replay can only be requested once they pass, so text claiming authority never reaches a model. A reviewer's text cases become optional. They can still fail a proposal, but they can't pass one.

**Spending and the install:** nothing here authorizes a paid call under Decision 0013, or a persistent change. A replay's runs spend only when an owner requests one on a stack with a key.

## Requirements revised

None. PRD 8.5's "run regression tasks" is met by this replay. SP-016 is unchanged.

## What this gives up

- **A replay runs without the Expert's own tools.** Each task gets the default goal loop's grants, so a skill written for one Expert's tools is tested without them.
- **"Drawn from" is matched on exact goal text.** A held-out task that paraphrases an evidence run's goal isn't caught. The owner writes the tasks and is trusted to keep them apart.
- **Passing is the task's own verification,** which is only as strong as the criteria the owner wrote.
- **No screen.** Improvements have API routes and no screen in this release (Decision 0009).

## Reversal

Each choice can change later under US-13.2's ID. Promotions made under it keep their replay records.
