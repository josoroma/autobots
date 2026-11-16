"""Candidate, regression, review and promotion, with rollback, PRD 8.5 and SP-016.

Generated or retrieved text is data here. Nothing in this module can reach an Expert's tools, a role
policy or a model default, and the checks below refuse text that claims it can.
"""

import json
import re
from collections import defaultdict
from types import MappingProxyType
from typing import Any, Literal
from uuid import UUID, uuid4

from autobots.application.idempotency import receipted
from autobots.application.knowledge import (
    NO_VERSION,
    REFERENCE_HEADER,
    activate,
    clear_head,
    promote,
    version_content,
)
from autobots.application.runs import (
    CommandKey,
    Fresh,
    Idempotent,
    RunAdmission,
    RunGrant,
    admit,
)
from autobots.application.sql import SqlConnection, all_rows, one, optional_row, stored
from autobots.contracts.improvements import (
    CANDIDATE_STATUSES,
    KNOWLEDGE_KINDS,
    CandidateView,
    ImprovementProposal,
    KnowledgeHead,
    KnowledgeKind,
    ReplayRunView,
    ReplayView,
)
from autobots.contracts.persisted import ReplayReceipt
from autobots.domain.errors import Refusal, RefusalKind
from autobots.domain.improvements import replay_verdict
from autobots.domain.models import RolePolicy
from autobots.domain.runs import RunStatus
from autobots.domain.tools import LOOP_TOOL_GRANTS
from autobots.persistence.rows import (
    CandidateCheckRow,
    CandidateDecisionRow,
    CandidateRow,
    ReplayRunRow,
)

# Text that tries to act as policy. It can still be stored as a note about what someone wrote, but
# not through this path, which is for content later runs will read as guidance.
AUTHORITY_CLAIMS = re.compile(
    r"(ignore (all |any )?(previous|prior|above)|disregard (the )?(rules|instructions|policy)"
    r"|(grant|give|enable|allow|add)\b.{0,40}\b(tool|tools|permission|permissions|access|shell)\b"
    r"|(use|switch to|change to)\b.{0,40}\b(model|gpt|claude|gemini|provider)\b"
    r"|system prompt|you are now|override\b.{0,40}\b(policy|rule|budget|limit))",
    re.IGNORECASE | re.DOTALL,
)


class ImprovementRefused(Refusal):
    kinds = MappingProxyType(
        {
            "candidate_not_found": RefusalKind.NOT_FOUND,
            "version_not_found": RefusalKind.NOT_FOUND,
        }
    )


async def propose(
    connection: SqlConnection,
    workspace_id: UUID,
    proposal: ImprovementProposal,
    source: dict[str, Any],
) -> UUID:
    """Only stores a proposal. Nothing reads it until it's promoted."""
    candidate_id = uuid4()
    await connection.execute(
        "insert into public.improvement_candidates (id, workspace_id, kind, key, content, "
        "evidence, regression_cases, source) values (%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            candidate_id,
            workspace_id,
            proposal.kind,
            proposal.key,
            proposal.content,
            json.dumps([item.model_dump() for item in proposal.evidence]),
            json.dumps([item.model_dump() for item in proposal.regression_cases]),
            json.dumps(source),
        ),
    )
    return candidate_id


# The tables evidence can name, by its kind.
EvidenceTable = Literal["public.runs", "public.artifacts"]


async def _found(
    connection: SqlConnection, table: EvidenceTable, workspace_id: UUID, ids: list[str]
) -> set[UUID]:
    """Which of `ids` name a row of `table` in this workspace, from one read."""
    if not ids:
        return set()
    cursor = await connection.execute(
        f"select id from {table} where workspace_id = %s and id = any(%s::uuid[])",
        (workspace_id, ids),
    )
    return {row[0] for row in await cursor.fetchall()}


async def _evidence_problems(
    connection: SqlConnection, workspace_id: UUID, evidence: list[Any]
) -> list[str]:
    """Each reference must be real, in this workspace. An invented recollection has none. One read
    per kind checks every reference (PPRD-11)."""
    if not evidence:
        return ["evidence_required"]
    runs = [str(item["id"]) for item in evidence if item["kind"] == "run"]
    artifacts = [str(item["id"]) for item in evidence if item["kind"] != "run"]
    found = {
        "run": await _found(connection, "public.runs", workspace_id, runs),
        "artifact": await _found(connection, "public.artifacts", workspace_id, artifacts),
    }
    return [
        f"evidence_not_found:{item['id']}"
        for item in evidence
        if UUID(str(item["id"])) not in found["run" if item["kind"] == "run" else "artifact"]
    ]


async def run_regression(
    connection: SqlConnection,
    workspace_id: UUID,
    candidate_id: UUID,
    cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Deterministic checks of the proposal. Passing them doesn't promote anything, and it's what
    lets an owner request a held-out replay, so text claiming authority never reaches a model.

    The cases come from the person reviewing. A proposer writing its own would certify itself.
    """
    async with connection.transaction():
        checked = await optional_row(
            connection,
            CandidateCheckRow,
            "select content, evidence, regression_cases, status from "
            "public.improvement_candidates where id = %s and workspace_id = %s for update",
            (candidate_id, workspace_id),
        )
        if checked is None:
            raise ImprovementRefused("candidate_not_found")
        content, evidence, regression_cases, status = (
            checked.content,
            checked.evidence,
            checked.regression_cases,
            checked.status,
        )
        if status not in {"proposed", "regression_failed"}:
            raise ImprovementRefused("candidate_not_open")
        failures = await _evidence_problems(connection, workspace_id, evidence)
        (proposed_by,) = await one(
            connection,
            "select source ->> 'run_id' from public.improvement_candidates where id = %s",
            (candidate_id,),
        )
        if proposed_by:
            cited = [str(item["id"]).lower() for item in evidence]
            (own_artifacts,) = await one(
                connection,
                "select count(*) from public.artifacts where id::text = any(%s) "
                "and run_id::text = %s",
                (cited, proposed_by.lower()),
            )
            if proposed_by.lower() in cited or own_artifacts:
                failures.append("evidence_is_its_own_run")
        if AUTHORITY_CLAIMS.search(content):
            failures.append("claims_authority")
        # Optional since US-13.2: they can fail a proposal, and only a held-out replay passes one.
        reviewer_cases = cases or []
        failures.extend(
            f"case_failed:{case['must_contain'][:40]}"
            for case in reviewer_cases
            if case["must_contain"] not in content
        )
        results = {
            "failures": failures,
            "cases": len(reviewer_cases),
            "proposer_cases_ignored": len(regression_cases),
        }
        await connection.execute(
            "update public.improvement_candidates set status = %s, regression_results = %s "
            "where id = %s",
            (
                "regression_failed" if failures else "regression_passed",
                json.dumps(results),
                candidate_id,
            ),
        )
    return results


async def _candidate_for_decision(
    connection: SqlConnection, workspace_id: UUID, candidate_id: UUID
) -> CandidateDecisionRow:
    """The candidate a decision or a replay acts on, under its row lock."""
    row = await optional_row(
        connection,
        CandidateDecisionRow,
        "select kind, key, content, status, evidence, source from "
        "public.improvement_candidates where id = %s and workspace_id = %s for update",
        (candidate_id, workspace_id),
    )
    if row is None:
        raise ImprovementRefused("candidate_not_found")
    return row


async def decide(
    connection: SqlConnection, workspace_id: UUID, candidate_id: UUID, actor_id: UUID, decision: str
) -> str:
    """A person's decision, and only after checks passed. Promotion adds a version."""
    async with connection.transaction():
        row = await _candidate_for_decision(connection, workspace_id, candidate_id)
        kind, key, content, status, evidence, source = (
            row.kind,
            row.key,
            row.content,
            row.status,
            row.evidence,
            row.source,
        )
        if status in {"promoted", "rejected"}:
            raise ImprovementRefused("candidate_already_decided")
        if decision == "reject":
            outcome = "rejected"
        else:
            if status != "regression_passed":
                raise ImprovementRefused("regression_required")
            replay = await replay_state(connection, candidate_id)
            if replay is None:
                raise ImprovementRefused("replay_required")
            if replay.state != "passed":
                raise ImprovementRefused(f"replay_{replay.state}")
            await promote(
                connection,
                workspace_id=workspace_id,
                candidate_id=candidate_id,
                kind=kind,
                key=key,
                content=content,
                provenance={
                    "evidence": evidence,
                    "source": source,
                    "reviewed_by": str(actor_id),
                    "replay_id": str(replay.id),
                },
                source_run=(source or {}).get("run_id"),
            )
            outcome = "promoted"
        await connection.execute(
            "update public.improvement_candidates set status = %s, reviewed_by = %s, "
            "reviewed_at = now() where id = %s",
            (outcome, actor_id, candidate_id),
        )
    return outcome


async def rollback(
    connection: SqlConnection, workspace_id: UUID, kind: KnowledgeKind, key: str, to_version: int
) -> KnowledgeHead:
    """Points back at an earlier version, or at none with 0, since a first promotion has nothing
    before it. Every version stays. Admitted work keeps its pinned skill, and reads memory live."""
    async with connection.transaction():
        if to_version == NO_VERSION:
            if not await clear_head(connection, workspace_id, kind, key):
                raise ImprovementRefused("version_not_found")
            return KnowledgeHead(schema_version=1, kind=kind, key=key, active_version=None)
        content = await version_content(connection, workspace_id, kind, key, to_version)
        if content is None:
            raise ImprovementRefused("version_not_found")
        await activate(connection, workspace_id, kind, key, to_version, content)
    return KnowledgeHead(schema_version=1, kind=kind, key=key, active_version=to_version)


def candidate_view(row: CandidateRow, replay: ReplayView | None) -> CandidateView:
    """An unknown stored kind or status raises, instead of reaching a client."""
    return CandidateView(
        id=row.id,
        kind=stored(KNOWLEDGE_KINDS, row.kind),
        key=row.key,
        content=row.content,
        status=stored(CANDIDATE_STATUSES, row.status),
        regression_results=row.regression_results,
        replay=replay,
    )


async def list_candidates(connection: SqlConnection, workspace_id: UUID) -> list[CandidateView]:
    rows = await all_rows(
        connection,
        CandidateRow,
        "select id, kind, key, content, status, regression_results from "
        "public.improvement_candidates where workspace_id = %s order by created_at desc limit 100",
        (workspace_id,),
    )
    replays = await _replay_states(connection, [row.id for row in rows])
    return [candidate_view(row, replays.get(row.id)) for row in rows]


def _normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


async def request_replay(
    connection: SqlConnection,
    *,
    workspace_id: UUID,
    candidate_id: UUID,
    actor_id: UUID,
    idempotency_key: str,
    tasks: list[dict[str, Any]],
    limit_micro_usd: int,
    policy: RolePolicy,
) -> UUID:
    """Each held-out task becomes an ordinary run with the proposal applied to it alone.

    The owner wrote the tasks, and one that is a goal the proposal came from is refused. Requesting
    is what authorizes the runs' spending, each up to the limit, Decision 0016.
    """
    command = Idempotent.of(
        CommandKey(workspace_id, actor_id, idempotency_key),
        "replay_candidate",
        str(candidate_id),
        {"tasks": tasks, "limit_micro_usd": limit_micro_usd},
    )
    async with receipted(connection, command, ReplayReceipt) as receipt:
        if receipt.prior is not None:
            return receipt.prior.replay_id
        row = await _candidate_for_decision(connection, workspace_id, candidate_id)
        kind, key, content, status, evidence, source = (
            row.kind,
            row.key,
            row.content,
            row.status,
            row.evidence,
            row.source,
        )
        if status in {"promoted", "rejected"}:
            raise ImprovementRefused("candidate_already_decided")
        if status != "regression_passed":
            raise ImprovementRefused("regression_required")
        cited = [str(item["id"]) for item in evidence]
        origin = (source or {}).get("run_id")
        cursor = await connection.execute(
            "select goal_text from public.runs where workspace_id = %s and goal_text is not null "
            "and (id::text = any(%s) or id::text = %s or id in (select run_id from "
            "public.artifacts where workspace_id = %s and id::text = any(%s)))",
            (workspace_id, cited, origin or "", workspace_id, cited),
        )
        drawn = {_normalized(found[0]) for found in await cursor.fetchall()}
        if any(_normalized(task["goal_text"]) in drawn for task in tasks):
            raise ImprovementRefused("task_drawn_from_proposal")
        replay_id = uuid4()
        await connection.execute(
            "insert into app_private.improvement_replays (id, workspace_id, candidate_id, "
            "requested_by) values (%s, %s, %s, %s)",
            (replay_id, workspace_id, candidate_id, actor_id),
        )
        # The default loop's grants, so a replay can't propose or reach anything an Expert adds.
        origin = Fresh(
            policy,
            RunGrant(
                instructions=REFERENCE_HEADER + f"{key}:\n{content}" if kind == "skill" else "",
                tools=dict(LOOP_TOOL_GRANTS),
            ),
            started_by=actor_id,
        )
        for position, task in enumerate(tasks):
            admitted = await admit(
                connection,
                RunAdmission(
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    idempotency_key=f"replay:{replay_id}:{position}",
                    goal_text=task["goal_text"],
                    limit_micro_usd=limit_micro_usd,
                    origin=origin,
                    acceptance_criteria=tuple(task["criteria"]),
                ),
            )
            await connection.execute(
                "insert into app_private.improvement_replay_runs (replay_id, run_id, position, "
                "task) values (%s, %s, %s, %s)",
                (replay_id, admitted.run_id, position, json.dumps(task)),
            )
        await receipt.store(ReplayReceipt(replay_id=replay_id))
    return replay_id


def _replay_view(rows: list[ReplayRunRow]) -> ReplayView:
    statuses = [RunStatus(row.status) for row in rows]
    return ReplayView(
        id=rows[0].replay_id,
        state=replay_verdict(statuses),
        runs=[
            ReplayRunView(run_id=row.run_id, goal_text=row.goal_text, status=status)
            for row, status in zip(rows, statuses, strict=True)
        ],
    )


async def _replay_states(
    connection: SqlConnection, candidate_ids: list[UUID]
) -> dict[UUID, ReplayView]:
    """Each candidate's latest replay with its runs in order, from one read (PPRD-11)."""
    if not candidate_ids:
        return {}
    rows = await all_rows(
        connection,
        ReplayRunRow,
        "select r.candidate_id, r.id as replay_id, rr.run_id, "
        "rr.task ->> 'goal_text' as goal_text, u.status "
        "from app_private.improvement_replays r "
        "join app_private.improvement_replay_runs rr on rr.replay_id = r.id "
        "join public.runs u on u.id = rr.run_id "
        "where r.id in (select distinct on (candidate_id) id "
        "from app_private.improvement_replays where candidate_id = any(%s) "
        "order by candidate_id, created_at desc, id) order by r.candidate_id, rr.position",
        (candidate_ids,),
    )
    grouped: dict[UUID, list[ReplayRunRow]] = defaultdict(list)
    for row in rows:
        grouped[row.candidate_id].append(row)
    return {candidate: _replay_view(found) for candidate, found in grouped.items()}


async def replay_state(connection: SqlConnection, candidate_id: UUID) -> ReplayView | None:
    """The latest replay only. Passed when every run succeeded, failed when any ended otherwise
    (domain improvements.replay_verdict)."""
    return (await _replay_states(connection, [candidate_id])).get(candidate_id)
