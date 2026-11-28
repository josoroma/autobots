"""Admitting model-backed work: POST /v1/runs's use case, and the gate every path to a model call
passes first (refactor plan R-31, PAPI-02, PAPI-04, PPRD-09 and XDUP-08).

`admit_from_request` runs a request's nine steps in a fixed order, and the first refusal is the
answer. Only the last step writes anything, so a refused request leaves nothing behind. Admission
records intent, the run, its job and first event in one transaction, and a worker that claims the
job executes it (option-b-contract SP-012).

The gate is `require_model_ready`, `workspace_role_policy` with its offered check, `chosen_limit`
and `require_tools_available`, and `expert_overrides` turns an Expert's bindings into run
overrides. A goal run, a resume, a held-out replay, a workflow execution, a routine's occurrence,
the run intent check and the run preview use it. Where they differ on purpose, the difference is an
argument at the call site, not a missing line.
"""

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Self
from uuid import UUID

from autobots.application.experts import RunBinding, resolve_binding
from autobots.application.experts import expert_overrides as expert_overrides
from autobots.application.model_admission import remaining_daily_micro_usd
from autobots.application.model_source import not_offered_locally, offered_local_profiles
from autobots.application.runs import AdmissionResult, Fresh, RunAdmission, admit
from autobots.application.sql import SqlConnection, SqlPool
from autobots.application.tool_catalog import Catalog
from autobots.application.tool_keys import key_sources
from autobots.contracts.plans import InputDocument, RequiredArtifact
from autobots.contracts.run_commands import RunRequest
from autobots.domain.budgets import require_budget
from autobots.domain.errors import Refusal, RefusalKind
from autobots.domain.models import (
    ModelProfileId,
    ModelSource,
    ProfileNotOffered,
    RolePolicy,
    is_offered,
    require_offered,
    resolve_role_policy,
)

# Says whether a workspace can make model calls now: "ready", or the code that refuses. It reports,
# and never starts anything.
CredentialCheck = Callable[[UUID], Awaitable[str]]


class ModelNotReady(Refusal):
    """Model-backed work needs a usable OpenRouter key. `code` says what's wrong with this one."""


class PolicyNotOffered(ProfileNotOffered):
    """A resolved profile isn't offered for new runs. `named` when the request itself named it,
    which makes it a bad request. Otherwise it's a saved choice to change, a conflict."""

    def __init__(self, reason: str, *, named: bool) -> None:
        super().__init__(reason, kind=RefusalKind.INVALID if named else RefusalKind.CONFLICT)
        self.named = named


RequestRefusal = Literal["session_required", "budget_conflict", "owner_required"]


class AdmissionRefused(Refusal):
    """The request's own shape, or who sent it, refuses it, and nothing is written."""

    kind = RefusalKind.INVALID
    kinds = MappingProxyType({"owner_required": RefusalKind.FORBIDDEN})

    def __init__(self, code: RequestRefusal) -> None:
        super().__init__(code)


# The gate


async def require_model_ready(check: CredentialCheck, workspace_id: UUID, *, needed: bool) -> None:
    """The key gate, when the work `needed` a model. The worker checks again before it dispatches
    anything, so passing here never stands in for that check."""
    if not needed:
        return
    code = await check(workspace_id)
    if code != "ready":
        raise ModelNotReady(code)


# Decision 0041 A8: one local model answers every role, so on Local a role can't be given another.
ROLE_OVERRIDE_ON_LOCAL = (
    "On the Local source, one local model answers every role, so a role override isn't offered."
)
# On Local the workspace default names the one local model, so saving none, or a Local row
# without one, is refused (Decision 0041 A8).
NO_LOCAL_DEFAULT = (
    "On the Local source, choose an offered local model as the workspace default in "
    "Settings → Models."
)


@dataclass(frozen=True)
class WorkspacePolicy:
    """A workspace's saved model policy: its default and its role overrides, or neither, and its
    Model source (Decision 0041 A1). On Local, `local_profile` answers every role, and
    `offered_local` is what the Local source offers now."""

    default_profile: str | None = None
    role_overrides: Mapping[str, str] | None = None
    model_source: ModelSource = ModelSource.OPENROUTER
    local_profile: str | None = None
    offered_local: frozenset[ModelProfileId] = frozenset()

    def for_new_work(
        self,
        *,
        run_role_overrides: Mapping[str, str] | None = None,
        run_profile: ModelProfileId | None = None,
        require_offer: bool,
    ) -> RolePolicy:
        """The policy a run started now freezes, in MP-01's order over the run's overrides and this
        saved policy (PRD-Model-Providers MP-01). With `require_offer`, a profile not offered for
        new runs refuses, and no other is put in its place."""
        if self.model_source is ModelSource.LOCAL:
            return self._on_local(run_role_overrides, run_profile, require_offer=require_offer)
        policy = resolve_role_policy(
            run_role_overrides=run_role_overrides,
            run_profile=run_profile.value if run_profile else None,
            workspace_default=self.default_profile,
            workspace_role_overrides=self.role_overrides,
        )
        if require_offer:
            try:
                require_offered(policy.bindings.values())
            except ProfileNotOffered as refused:
                named = run_profile is not None and not is_offered(run_profile)
                raise PolicyNotOffered(refused.reason, named=named) from None
        return policy

    def _on_local(
        self,
        run_role_overrides: Mapping[str, str] | None,
        run_profile: ModelProfileId | None,
        *,
        require_offer: bool,
    ) -> RolePolicy:
        """Every role on one offered local profile: the run's own, if it names one, else the Local
        default. OpenRouter's saved choices don't apply (Decision 0041 A1, A8)."""
        if run_role_overrides:
            raise PolicyNotOffered(ROLE_OVERRIDE_ON_LOCAL, named=True)
        chosen = run_profile if run_profile is not None else self.local_profile
        if chosen is None:
            raise PolicyNotOffered(NO_LOCAL_DEFAULT, named=False)
        profile = ModelProfileId(chosen)
        if require_offer and profile not in self.offered_local:
            raise PolicyNotOffered(not_offered_locally(profile), named=run_profile is not None)
        return resolve_role_policy(
            run_profile=run_profile.value if run_profile else None,
            workspace_default=profile.value,
        )


async def saved_workspace_policy(connection: SqlConnection, workspace_id: UUID) -> WorkspacePolicy:
    cursor = await connection.execute(
        "select default_profile, role_overrides, model_source, local_profile "
        "from app_private.model_policies where workspace_id = %s",
        (workspace_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return WorkspacePolicy()
    source = ModelSource(row[2])
    if source is ModelSource.OPENROUTER:
        return WorkspacePolicy(row[0], row[1])
    offered = await offered_local_profiles(connection)
    return WorkspacePolicy(row[0], row[1], source, row[3], offered)


async def workspace_role_policy(
    connection: SqlConnection,
    workspace_id: UUID,
    *,
    run_role_overrides: Mapping[str, str] | None = None,
    run_profile: ModelProfileId | None = None,
    require_offer: bool,
) -> RolePolicy:
    """The saved policy, read and resolved for new work, as `WorkspacePolicy.for_new_work`."""
    saved = await saved_workspace_policy(connection, workspace_id)
    return saved.for_new_work(
        run_role_overrides=run_role_overrides,
        run_profile=run_profile,
        require_offer=require_offer,
    )


async def chosen_limit(
    connection: SqlConnection, workspace_id: UUID, budget: int | None, *, otherwise: int
) -> int:
    """A chosen budget becomes the run's frozen limit once Decision 0022 D11's rules and what's left
    of today's cap allow it. With none chosen, the limit is `otherwise`. Raises BudgetRefused."""
    if budget is None:
        return otherwise
    require_budget(budget, await remaining_daily_micro_usd(connection, workspace_id))
    return budget


async def require_tools_available(
    connection: SqlConnection,
    workspace_id: UUID,
    tools: Iterable[str],
    environment: Mapping[str, str],
    catalog: Catalog,
) -> None:
    """Refuses work that grants a tool this install can't use now, before the work exists, with
    keys in PK-04's order over the workspace's saved items and `environment`, by the catalog the
    composition edge passes (PRD-Tool-Catalog PK-02 and PK-04). Raises ToolsUnavailable."""
    catalog.require_available(tools, await key_sources(connection, workspace_id, environment))


# POST /v1/runs


@dataclass(frozen=True)
class AdmissionInput:
    """What a run request asks for, as plain values, with who asks and under which key."""

    workspace_id: UUID
    user_id: UUID
    idempotency_key: str
    goal_text: str | None
    limit_micro_usd: int
    # The request named a limit, even one equal to the default, so a budget beside it conflicts.
    limit_named: bool
    budget_micro_usd: int | None
    session_id: UUID | None
    expert_id: UUID | None
    expert_version: int | None
    run_profile: ModelProfileId | None
    acceptance_criteria: tuple[str, ...]
    continues_run_id: UUID | None
    required_artifacts: tuple[RequiredArtifact, ...]
    input_documents: tuple[InputDocument, ...]

    @classmethod
    def of(
        cls, body: RunRequest, *, workspace_id: UUID, user_id: UUID, idempotency_key: str
    ) -> Self:
        return cls(
            workspace_id=workspace_id,
            user_id=user_id,
            idempotency_key=idempotency_key,
            goal_text=body.goal_text,
            limit_micro_usd=body.limit_micro_usd,
            limit_named="limit_micro_usd" in body.model_fields_set,
            budget_micro_usd=body.budget_micro_usd,
            session_id=body.session_id,
            expert_id=body.expert_id,
            expert_version=body.expert_version,
            run_profile=body.run_profile,
            acceptance_criteria=tuple(body.acceptance_criteria),
            continues_run_id=body.continues_run_id,
            required_artifacts=tuple(body.required_artifacts),
            input_documents=tuple(body.input_documents),
        )


async def admit_from_request(
    data: AdmissionInput,
    *,
    database: SqlPool,
    model_ready: CredentialCheck,
    role: Callable[[], Awaitable[str | None]],
    environment: Mapping[str, str],
    catalog: Catalog,
) -> AdmissionResult:
    """A run request's nine steps, in order, and the first refusal is the answer.

    1. An Expert is chosen through a session.
    2. A budget or a limit, and a budget within the rules and today's cap.
    3. A usable OpenRouter key.
    4. Only an owner pins an Expert version, so `role` is asked only then. It is asked before the
       admission's connection opens, as a membership store may borrow one of its own (PAPI-11).
    5. The workspace's saved policy is read.
    6. The session's routing resolves.
    7. No granted tool is unavailable, by `environment`'s keys and `catalog`.
    8. Every resolved profile is offered.
    9. The run is admitted under its idempotency key.

    Raises AdmissionRefused, BudgetRefused, ModelNotReady, ExpertRefused, ToolsUnavailable,
    PolicyNotOffered, IdempotencyConflict or LinkRefused.
    """
    if data.session_id is None and (data.expert_id is not None or data.expert_version is not None):
        raise AdmissionRefused("session_required")
    limit = await _request_limit(database, data)
    await require_model_ready(model_ready, data.workspace_id, needed=True)
    if data.expert_version is not None and await role() != "owner":
        # An earlier version could hold tools an owner has since removed (Decision 0011 M8).
        raise AdmissionRefused("owner_required")
    async with database.connection() as connection:
        saved = await saved_workspace_policy(connection, data.workspace_id)
        binding = await _session_binding(connection, data, environment, catalog)
        policy = saved.for_new_work(
            run_role_overrides=binding.role_bindings if binding else None,
            run_profile=data.run_profile,
            require_offer=True,
        )
        return await admit(
            connection,
            RunAdmission(
                workspace_id=data.workspace_id,
                actor_id=data.user_id,
                idempotency_key=data.idempotency_key,
                goal_text=data.goal_text,
                limit_micro_usd=limit,
                origin=Fresh(policy, binding, started_by=data.user_id),
                acceptance_criteria=data.acceptance_criteria,
                continues_run_id=data.continues_run_id,
                required_artifacts=data.required_artifacts,
                input_documents=data.input_documents,
                run_profile=data.run_profile.value if data.run_profile else None,
            ),
        )


async def _request_limit(database: SqlPool, data: AdmissionInput) -> int:
    """Step 2. A budget is read against today's cap on a connection of its own, released before the
    key check."""
    if data.budget_micro_usd is None:
        return data.limit_micro_usd
    if data.limit_named:
        raise AdmissionRefused("budget_conflict")
    async with database.connection() as connection:
        return await chosen_limit(
            connection, data.workspace_id, data.budget_micro_usd, otherwise=data.limit_micro_usd
        )


async def _session_binding(
    connection: SqlConnection,
    data: AdmissionInput,
    environment: Mapping[str, str],
    catalog: Catalog,
) -> RunBinding | None:
    """Steps 6 and 7, for a request through a session. Any other request has no binding."""
    if data.session_id is None:
        return None
    binding = await resolve_binding(
        connection,
        data.workspace_id,
        data.session_id,
        expert_id=data.expert_id,
        version=data.expert_version,
    )
    # PK-02: only a run that grants an unavailable tool is refused, before it exists.
    await require_tools_available(
        connection, data.workspace_id, binding.tools, environment, catalog
    )
    return binding
