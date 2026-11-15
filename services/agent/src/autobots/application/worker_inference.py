"""What a worker needs to serve any admitted run: its frozen route, and a client per attempt.

Nothing here outlives an attempt except references. The key is read inside each attempt, so a
rotation reaches the next call without a restart, and no key or client can reach graph state.
"""

import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg

from autobots.adapters.models.catalog import (
    RESERVED_PROMPT_TOKENS,
    CatalogSnapshot,
    ModelUnavailable,
    parse_catalog,
    validated_entry,
)
from autobots.adapters.models.factory import (
    PreparedAttempt,
    UnsupportedRequestOption,
    chat_model,
    prepare_attempt,
)
from autobots.application import browsing_tool
from autobots.application.credentials.store import (
    CredentialBlocked,
    CredentialMissing,
    CredentialReference,
    CredentialStorageUnavailable,
)
from autobots.application.goal_loop import UNBOUND, LoopConfig
from autobots.application.loop_admission import current_invocation
from autobots.application.model_admission import (
    CostUnavailable,
    ModelAdmission,
    worst_case_cost,
)
from autobots.application.model_attempts import FailureClass, ProviderFailure
from autobots.application.provider_settings import (
    CredentialRefused,
    ProviderContext,
    ProviderSettings,
)
from autobots.application.runs import frozen_snapshot
from autobots.application.sql import SqlConnection
from autobots.application.tool_definitions import Browsing
from autobots.application.tool_keys import key_sources
from autobots.application.worker_leases import Lease
from autobots.contracts.persisted import PolicySnapshot, read_policy_snapshot
from autobots.domain.models import (
    MAX_OUTPUT_TOKENS,
    PROFILES,
    ModelRole,
    ModelRoute,
    RolePolicy,
    UnknownModelProfile,
    approved_profile,
    approved_role,
)
from autobots.logs import log_event

logger = logging.getLogger("autobots.worker")
ROLE = ModelRole.EXECUTOR
OPTIONS: Mapping[str, Any] = {"max_tokens": MAX_OUTPUT_TOKENS}
# Sooner than MP-02's five minutes, so a slow call doesn't turn into an expired catalog.
CATALOG_REFRESH = timedelta(minutes=4)
INTENT_FAILURES = {
    "credentials_required": FailureClass.CREDENTIALS_REQUIRED,
    "credential_invalid": FailureClass.INVALID_CREDENTIAL,
    "credential_unavailable": FailureClass.CREDENTIAL_UNAVAILABLE,
}


def _log_refusal(what: str, error: Exception) -> None:
    """These all fail closed, and the type is what's safe to say about why."""
    log_event(logger, "inference.refused", logging.WARNING, what=what, error=error)


class CatalogCache:
    """The last good catalog. A failed refresh keeps it until MP-02's own age check refuses it."""

    def __init__(
        self,
        fetch: Callable[[], Awaitable[dict[str, Any] | None]],
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._fetch = fetch
        self._now = now
        self._snapshot: CatalogSnapshot | None = None

    async def current(self) -> CatalogSnapshot:
        now = self._now()
        if self._snapshot is None or now - self._snapshot.retrieved_at >= CATALOG_REFRESH:
            try:
                payload = await self._fetch()
                if payload is not None:
                    self._snapshot = parse_catalog(payload, retrieved_at=now, revision="live")
            except (OSError, ValueError, TypeError, AttributeError) as error:
                # Unreachable or malformed, which leaves whatever was last good to age out.
                _log_refusal("catalog", error)
        if self._snapshot is None:
            raise ModelUnavailable("the model catalog could not be read")
        return self._snapshot


def frozen_policy(snapshot: PolicySnapshot | Mapping[str, object] | None) -> RolePolicy:
    """Exactly what admission froze, from its stored snapshot (contracts/persisted.py). Without
    an approved binding for this role, or with a snapshot that can't be read, there's no route."""
    stored = snapshot if isinstance(snapshot, PolicySnapshot) else read_policy_snapshot(snapshot)
    policy = {
        approved_role(role): approved_profile(bound) for role, bound in stored.bindings.items()
    }
    if ROLE not in policy:
        raise UnknownModelProfile("this run has no binding for the role")
    # A release that points a profile at another model mustn't move runs saved before it. A run
    # frozen before routes were has none to compare (PolicySnapshot).
    for name, route in stored.routes.items():
        current = PROFILES[approved_profile(name)]
        if (route.wire_id, route.canonical_id) != (current.wire_id, current.canonical_id):
            raise UnknownModelProfile("this run was frozen on another model for that profile")
    sources = {
        approved_role(role): source
        for role in stored.sources
        if (source := stored.source(role)) is not None
    }
    return RolePolicy(stored.version, policy, sources)


def prepared(
    policy: RolePolicy, catalog: CatalogSnapshot, role: ModelRole = ROLE
) -> tuple[PreparedAttempt, int]:
    """Fresh exact mapping, options and tools, and the most one call is reserved for."""
    attempt = prepare_attempt(policy, role, catalog, options=OPTIONS)
    entry = validated_entry(attempt.profile, catalog, datetime.now(UTC))
    if "tools" not in entry.supported_parameters:
        raise UnsupportedRequestOption("this model's catalog entry does not support tools")
    return attempt, worst_case_cost(entry.pricing, RESERVED_PROMPT_TOKENS, MAX_OUTPUT_TOKENS)


class AttemptModel:
    """What `AdmittedModel` delegates to. Each call opens its own client, used once."""

    def __init__(
        self,
        source: "InferenceSource",
        workspace_id: UUID,
        policy: RolePolicy,
        tools: Any = None,
        tool_options: Mapping[str, Any] | None = None,
        reserved_micro_usd: int | None = None,
        role: ModelRole = ROLE,
    ) -> None:
        self._source = source
        self._role = role
        self._workspace_id = workspace_id
        self._policy = policy
        self._reserved = reserved_micro_usd
        self._tools = tools
        self._tool_options = tool_options or {}

    def bind_tools(self, tools: Any, **options: Any) -> "AttemptModel":
        return AttemptModel(
            self._source,
            self._workspace_id,
            self._policy,
            tools,
            options,
            self._reserved,
            self._role,
        )

    async def ainvoke(self, messages: Any, stop: Any = None, **kwargs: Any) -> Any:
        client, used = await self._source.open_attempt(
            self._workspace_id, self._policy, reserved_micro_usd=self._reserved, role=self._role
        )
        target = client
        if self._tools is not None:
            target = client.bind_tools(self._tools, **self._tool_options)
        try:
            return await target.ainvoke(messages, stop=stop, **kwargs)
        except Exception as error:
            if getattr(error, "status_code", None) == 401:
                await self._source.reject_key(self._workspace_id, used)
            raise

    async def astream(self, messages: Any, stop: Any = None, **kwargs: Any) -> AsyncIterator[Any]:
        """The same attempt, streamed (Decision 0022's streaming decision). The caller assembles the
        chunks, so the ledger settles from the same usage and cost the whole reply reports."""
        client, used = await self._source.open_attempt(
            self._workspace_id, self._policy, reserved_micro_usd=self._reserved, role=self._role
        )
        target = client
        if self._tools is not None:
            target = client.bind_tools(self._tools, **self._tool_options)
        try:
            async for chunk in target.astream(messages, stop=stop, **kwargs):
                yield chunk
        except Exception as error:
            if getattr(error, "status_code", None) == 401:
                await self._source.reject_key(self._workspace_id, used)
            raise


@dataclass(frozen=True)
class InferenceSource:
    """One per worker. `client_factory` is None in production, which means the real SDK client."""

    database_url: str
    context: ProviderContext
    catalog: CatalogCache
    client_factory: Callable[[str], Any] | None = None
    # The isolated browser executor, or None where browsing isn't offered (US-14.12).
    browser: Any = None

    async def open_attempt(
        self,
        workspace_id: UUID,
        policy: RolePolicy,
        reserved_micro_usd: int | None = None,
        role: ModelRole = ROLE,
    ) -> tuple[Any, CredentialReference]:
        """Inside the attempt. Every refusal here is before sending, and classed as such."""
        try:
            attempt, fresh_worst = prepared(policy, await self.catalog.current(), role)
            if reserved_micro_usd is not None and fresh_worst > reserved_micro_usd:
                # The price rose during this job, so its reservation no longer covers a call.
                raise CostUnavailable("this call would cost more than was reserved")
        except ModelUnavailable:
            raise ProviderFailure(FailureClass.MODEL_UNAVAILABLE) from None
        except CostUnavailable:
            raise ProviderFailure(FailureClass.COST_UNAVAILABLE) from None
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url, autocommit=True
            ) as connection:
                settings = ProviderSettings(connection, self.context)
                credential = await settings.credential_for_attempt(workspace_id)
                invocation = current_invocation()
                version = credential.reference.version
                if invocation is not None and version is not None:
                    await ModelAdmission(connection).record_credential(invocation, version)
            client = chat_model(
                attempt, credential.client_secret(), client_factory=self.client_factory
            )
        except CredentialRefused as refused:
            raise ProviderFailure(INTENT_FAILURES[refused.code]) from None
        except CredentialMissing:
            raise ProviderFailure(FailureClass.CREDENTIALS_REQUIRED) from None
        except CredentialBlocked:
            raise ProviderFailure(FailureClass.INVALID_CREDENTIAL) from None
        except (
            # CredentialUnreadable among them, logged by its own type (POPS-09).
            CredentialStorageUnavailable,
            psycopg.Error,
            # An unreadable or malformed configuration file, or a client that wouldn't build.
            OSError,
            ValueError,
        ) as error:
            _log_refusal("credential", error)
            raise ProviderFailure(FailureClass.CREDENTIAL_UNAVAILABLE) from None
        return client, credential.reference

    async def reject_key(self, workspace_id: UUID, used: CredentialReference) -> None:
        """Best effort, so losing the database here can't hide the 401 it's reporting."""
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url, autocommit=True
            ) as connection:
                await ProviderSettings(connection, self.context).mark_invalid(workspace_id, used)
        except (psycopg.Error, OSError, ValueError) as error:
            _log_refusal("reject_key", error)

    async def _refusal(
        self, connection: SqlConnection, workspace_id: UUID, policy: RolePolicy
    ) -> tuple[str | None, int]:
        """Why this job shouldn't start, and otherwise the most one call could cost.

        Everything a job's configuration can raise ends here. `bind` runs before the loop's own
        gates, so an escape would keep a cancel or a finished candidate from ever settling.
        """
        try:
            code = await ProviderSettings(connection, self.context).run_intent(workspace_id)
        except (OSError, ValueError) as error:
            _log_refusal("credential", error)
            return FailureClass.CREDENTIAL_UNAVAILABLE.value, 0
        if code != "ready":
            return INTENT_FAILURES[code].value, 0
        try:
            return None, prepared(policy, await self.catalog.current())[1]
        except ModelUnavailable:
            return FailureClass.MODEL_UNAVAILABLE.value, 0
        except CostUnavailable as refused:
            return refused.code, 0

    async def _input_rate(self, profile: Any) -> tuple[int, int | None]:
        """Zero where no price can be read, which `_refusal` has already stopped. And any tier."""
        try:
            entry = validated_entry(profile, await self.catalog.current(), datetime.now(UTC))
        except ModelUnavailable:
            return 0, None
        if entry.pricing is None:
            return 0, None
        return entry.pricing.input_per_million, entry.pricing.tier_from_tokens

    async def bind(
        self, connection: SqlConnection, lease: Lease, config: LoopConfig
    ) -> tuple[Callable[[], Any], LoopConfig]:
        """The route comes from this run's frozen policy, never from the worker or the workspace."""
        try:
            policy = frozen_policy(await frozen_snapshot(connection, lease.run_id))
        except UnknownModelProfile:
            return _no_model, replace(config, route=UNBOUND)
        refusal, worst_case = await self._refusal(connection, lease.workspace_id, policy)
        profile = policy.profile_for(ROLE)
        rate, tier = await self._input_rate(profile)
        route = ModelRoute(ROLE.value, profile.id.value, profile.wire_id, worst_case, rate, tier)
        model = AttemptModel(self, lease.workspace_id, policy, reserved_micro_usd=worst_case)
        browsing = await self._browsing(connection, lease)
        return lambda: model, replace(config, route=route, refusal=refusal, browsing=browsing)

    async def _browsing(self, connection: SqlConnection, lease: Lease) -> Browsing | None:
        """`browse_goal` for this job, bound to the run's researcher route, while browsing is
        switched on and its executor qualified. The pass's tool set registers it from this
        (adapters/tool_registry.py)."""
        if self.browser is None:
            return None
        # Decision 0025 V6: the run's workspace decides, by its saved switch, then the environment.
        view = await key_sources(connection, lease.workspace_id, os.environ)
        if not browsing_tool.executor_ready(environ=view):
            return None
        bound = await self.role_route(connection, lease, ModelRole.RESEARCHER)
        if isinstance(bound, str):
            _log_refusal("browsing", UnknownModelProfile(bound))
            return None
        model, route = bound
        return Browsing(
            qualified=lambda: browsing_tool.executor_ready(environ=view),
            runtime=browsing_tool.BrowsingRuntime(self.browser, model, route),
        )

    async def role_route(
        self, connection: SqlConnection, lease: Lease, role: ModelRole
    ) -> tuple[AttemptModel, ModelRoute] | str:
        """Another role of the same run, as its frozen policy binds it, or why it can't be used.

        Browsing calls the `researcher` route this way (Decision 0020 L3). Each call it makes is
        still admitted by the loop's middleware, on this route and the run's budget.
        """
        try:
            policy = frozen_policy(await frozen_snapshot(connection, lease.run_id))
            profile = policy.profile_for(role)
        except (UnknownModelProfile, KeyError, ValueError):
            return "route_not_bound"
        try:
            worst_case = prepared(policy, await self.catalog.current(), role)[1]
        except UnsupportedRequestOption as unsupported:
            return unsupported.code
        except ModelUnavailable:
            return FailureClass.MODEL_UNAVAILABLE.value
        except CostUnavailable as refused:
            return refused.code
        rate, tier = await self._input_rate(profile)
        route = ModelRoute(role.value, profile.id.value, profile.wire_id, worst_case, rate, tier)
        model = AttemptModel(
            self, lease.workspace_id, policy, reserved_micro_usd=worst_case, role=role
        )
        return model, route


def _no_model() -> Any:
    """Handed over with an unbound route, which `run_goal` stops before any model is called."""
    return None
