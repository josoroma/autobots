"""Persisted JSON documents, each one model its writer and its readers share (refactor plan R-51,
XTYP-03, PRUN-08, XDUP-04). None is a public contract, and no route returns one.

They are records as `persistence/records.py` defines them: frozen, lenient (a field a model
doesn't know is ignored), and versioned by a `record_version` that is absent while it is 1. A
stored row is read as it is, and what an older release left out is a default that each model
names. Each writes the bytes its writer always wrote, so snapshots and receipts stored before
compare equal. tests/fixtures/stored/ holds every shape each one reads.
"""

import json
from collections.abc import Mapping
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError

from autobots.contracts.runs import (
    ApprovalDecided,
    ApprovalRequested,
    ArtifactMissing,
    ArtifactPublished,
    EffectReconciled,
    RunStatusChanged,
    ToolUseCompleted,
    ToolUseStarted,
)
from autobots.domain.effects import ApprovalStatus, ReceiptStatus
from autobots.domain.models import PROFILES, BindingSource, RolePolicy, UnknownModelProfile
from autobots.domain.runs import RunStatus
from autobots.persistence.records import LENIENT, StoredRecord

# The policy snapshot: public.runs.policy_snapshot

_SOURCES = frozenset(source.value for source in BindingSource)


class FrozenRoute(BaseModel):
    """A profile's identities as admission froze them, so a release that points the profile at
    another model can't move the run (model-gateway rule). A field it doesn't name is ignored, so
    another frozen identity needs `record_version` 2 and a reader for it, or `frozen_policy` would
    never compare it."""

    model_config = LENIENT

    wire_id: str
    canonical_id: str


class PolicySnapshot(StoredRecord):
    """The role policy admission froze for a run. `runs.admit` writes it, and a child stores its
    parent's document as it was read (Decision 0015).

    Its maps hold text as stored, so a profile since retired, or a source this release doesn't
    know, still reads; `worker_inference.frozen_policy` decides what a worker may route on. What
    older shapes leave out reads as empty:

    - `sources` before US-15.8 (6f31f38) recorded them (PRD-Studio MD-02): no source is known.
    - `routes` before 4b0e816 froze them, as the upgrade qualifier's prior release, 8cba043,
      writes: no route was frozen, so none can have moved.
    - everything, in the column's default `{}` (migration 20261105000007): nothing is bound, and
      `version` is 0.

    `version` is the role policy's (ROLE_POLICY_VERSION), not the document's.
    """

    version: int = 0
    bindings: Mapping[str, str] = Field(default_factory=dict)
    sources: Mapping[str, str] = Field(default_factory=dict)
    routes: Mapping[str, FrozenRoute] = Field(default_factory=dict)

    @classmethod
    def of(cls, policy: RolePolicy) -> Self:
        """What admission freezes: each role's profile, where it came from, and each bound
        profile's identities now."""
        return cls(
            version=policy.version,
            bindings={role.value: profile.value for role, profile in policy.bindings.items()},
            sources={role.value: source.value for role, source in policy.sources.items()},
            routes={
                profile.value: FrozenRoute(
                    wire_id=PROFILES[profile].wire_id, canonical_id=PROFILES[profile].canonical_id
                )
                for profile in set(policy.bindings.values())
            },
        )

    def source(self, role: str) -> BindingSource | None:
        """Where a role's binding came from, or None when that wasn't recorded or isn't known."""
        found = self.sources.get(role)
        return BindingSource(found) if found in _SOURCES else None

    def stored(self) -> str:
        """As `runs.admit` always wrote it: sorted keys and `json.dumps`' separators."""
        return json.dumps(self.document(), sort_keys=True)


def read_policy_snapshot(stored: object) -> PolicySnapshot:
    """A stored snapshot as it is. One that can't be read binds nothing, so it is refused as an
    unknown profile is, and no model is chosen for its run."""
    try:
        return PolicySnapshot.model_validate(stored)
    except ValidationError:
        raise UnknownModelProfile("this run's frozen policy can't be read") from None


# A run event's payload: public.run_events.payload

# Each public type a writer stores (contracts/runs.py). Result text is only ever sent live, so it is
# never one, and no private payload is stored.
StoredEvent = (
    RunStatusChanged
    | ArtifactPublished
    | ArtifactMissing
    | ApprovalRequested
    | ApprovalDecided
    | EffectReconciled
    | ToolUseStarted
    | ToolUseCompleted
)


# Idempotency receipts: app_private.idempotency_receipts.result


class StoredReceipt(StoredRecord):
    """The first result under an idempotency key, which a repeat with the same content replays
    (SP-014). One model per operation, read by `runs.existing_receipt` for that operation alone."""

    def stored(self) -> str:
        """As each writer always stored its result: `json.dumps`, in field order."""
        return json.dumps(self.document())


class AdmissionReceipt(StoredReceipt):
    """`admit_run`, by `runs.admit`, since US-4.1."""

    run_id: UUID
    version: int
    status: RunStatus


class TransitionReceipt(StoredReceipt):
    """A person's run command sent with a key, by `runs.apply_command`. Its operation is the
    command's name, since US-4.1."""

    version: int
    status: RunStatus


class ApprovalDecisionReceipt(StoredReceipt):
    """`decide_approval`, by `approvals.decide`, since US-5.3."""

    status: ApprovalStatus


class EffectRulingReceipt(StoredReceipt):
    """`reconcile_effect`, by `reconciliation.record_evidence`, since US-5.4."""

    status: ReceiptStatus


class ModelCallReconciliationReceipt(StoredReceipt):
    """`reconcile_model_call`, by POST /v1/runs/{run_id}/model-calls/reconcile, since US-4.8."""

    reconciled_calls: int


class ExpertCreatedReceipt(StoredReceipt):
    """`create_expert`, by `experts.create_expert`, since US-5.1."""

    expert_id: UUID


class ExpertVersionReceipt(StoredReceipt):
    """`add_expert_version`, by `experts.add_version`, since US-5.1."""

    version: int


class SessionCreatedReceipt(StoredReceipt):
    """`create_session`, by `experts.create_session`, since US-5.1."""

    session_id: UUID


class WorkflowCreatedReceipt(StoredReceipt):
    """`create_workflow`, by `workflows.create_workflow`, since US-6.1."""

    workflow_id: UUID


class WorkflowVersionReceipt(StoredReceipt):
    """`publish_workflow`, by `workflows.publish_version`, since US-6.1."""

    version: int


class ExecutionReceipt(StoredReceipt):
    """`create_execution`, by `workflows.create_execution`. Without `run_id` from US-6.1 (9a0fb39)
    until US-6.2 (902d1cd) gave each execution its run."""

    execution_id: UUID
    run_id: UUID | None = None


class RoutineCreatedReceipt(StoredReceipt):
    """`create_routine`, by `routines.create_routine`, since US-7.1."""

    routine_id: UUID


class RoutineVersionReceipt(StoredReceipt):
    """`edit_routine`, by `routines.add_routine_version`, since US-7.1."""

    version: int


class ReplayReceipt(StoredReceipt):
    """`replay_candidate`, by `improvements.request_replay`, since US-13.2."""

    replay_id: UUID
