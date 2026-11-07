## ADDED Requirements

### Requirement: Promotion is gated on a held-out replay

A memory or skill proposal SHALL be promoted only after the latest held-out replay of it has passed. A replay SHALL run each held-out task as an ordinary run with the proposal applied to that run alone. It passes when every task's run has succeeded, with at least one task. The held-out tasks SHALL come from the owner who requested the replay, never from the proposal, and a task drawn from a run the proposal cites or came from SHALL be refused. A reviewer's text checks SHALL NOT pass a proposal alone.

#### Scenario: Gate promotion on a real replay
- **GIVEN** a memory or skill proposal, and held-out regression tasks it wasn't drawn from
- **WHEN** the replay runs before promotion
- **THEN** promotion needs its passing result, and a reviewer's text checks can no longer pass a proposal alone

### Requirement: Promotion is refused without a passing replay

When the latest replay failed, is still running, or wasn't run, an owner's promotion SHALL be refused with that reason. The active version SHALL stay unchanged, and rollback SHALL still work.

#### Scenario: Refuse without a passing replay
- **GIVEN** the replay failed or didn't run
- **WHEN** an owner tries to promote the proposal
- **THEN** it is refused with the reason, the active version is unchanged and rollback still works
