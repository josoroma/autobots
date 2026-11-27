"""A workspace's Model source behind the BFF (Decision 0041 A1, A7, A13; US-23.3). Any member reads
it, and only the owner switches it, at the version they saw (MP-05)."""

import os
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from autobots.adapters.models.local_health import Health, runtime_health
from autobots.adapters.models.local_server import local_port
from autobots.api.dependencies import MemberWorkspace, OwnerWorkspace
from autobots.api.errors import reworded
from autobots.api.model_policy_routes import POLICY_CHANGED, policy_pool
from autobots.api.resources import AppResources, app_resources
from autobots.api.security import require_internal
from autobots.application.local_offering import LOCAL_NAMES, local_offers
from autobots.application.model_policy import PolicyChanged, read_model_policy
from autobots.application.model_source import (
    SourceRolesUncovered,
    grants_browsing,
    roles_needed,
    switch_model_source,
)
from autobots.application.provider_settings import read_route_qualifications
from autobots.application.sql import SqlConnection
from autobots.contracts.settings import (
    LocalProfileState,
    LocalRuntime,
    ModelSourceState,
    ModelSourceUpdate,
)
from autobots.domain.models import PROFILES, ModelProfileId, ModelSource

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


def runtime_port(resources: AppResources) -> int:
    return resources.local_port if resources.local_port is not None else local_port(os.environ)


async def local_health(
    resources: AppResources, profile: ModelProfileId, *, with_digest: bool
) -> Health:
    return await runtime_health(
        PROFILES[profile],
        runtime_port(resources),
        with_digest=with_digest,
        transport=resources.local_transport,
        digests=resources.local_digests,
    )


async def source_state(
    connection: SqlConnection, workspace_id: UUID, resources: AppResources
) -> ModelSourceState:
    stored = await read_model_policy(connection, workspace_id)
    offers = local_offers(await read_route_qualifications(connection))
    offered = [offer.profile for offer in offers if offer.offered]
    needed = roles_needed(await grants_browsing(connection, workspace_id))
    shown = (
        ModelProfileId(stored.local_profile)
        if stored.local_profile is not None
        else (offered[0] if offered else None)
    )
    runtime = None
    if shown is not None:
        health = await local_health(resources, shown, with_digest=True)
        runtime = LocalRuntime(
            status=health.status,
            port=runtime_port(resources),
            served_model_id=health.served_model_id,
            sha256_matches=health.sha256_matches,
            sha256_checking=health.sha256_checking,
        )
    return ModelSourceState(
        schema_version=1,
        version=stored.version,
        source=stored.model_source.value,
        local_profile=None
        if stored.local_profile is None
        else ModelProfileId(stored.local_profile),
        local_profiles=[
            LocalProfileState(
                profile=offer.profile,
                name=LOCAL_NAMES.get(offer.profile, PROFILES[offer.profile].wire_id),
                offered=offer.offered,
                reason=offer.reason,
                qualified_on=offer.qualified_on,
                limits=offer.limits,
                # No run's match is recorded before US-23.4 to US-23.6 (Decision 0041 A7).
                matched_runs=[],
            )
            for offer in offers
        ],
        roles_needed=[role.value for role in needed],
        roles_uncovered=[] if offered else [role.value for role in needed],
        runtime=runtime,
    )


@router.get(
    "/settings/model-source", operation_id="getModelSource", response_model=ModelSourceState
)
async def get_model_source(request: Request, workspace_id: MemberWorkspace) -> ModelSourceState:
    """Where this workspace's model calls go, what Local offers, and the runtime's health."""
    async with policy_pool(request).connection() as connection:
        return await source_state(connection, workspace_id, app_resources(request))


@router.put(
    "/settings/model-source", operation_id="putModelSource", response_model=ModelSourceState
)
async def put_model_source(
    body: ModelSourceUpdate, request: Request, workspace_id: OwnerWorkspace
) -> ModelSourceState:
    """A switch: refused naming the roles no offered local profile covers, refused as a conflict at
    a stale version, and otherwise kept with OpenRouter's saved choices left as they are."""
    try:
        async with policy_pool(request).connection() as connection:
            await switch_model_source(
                connection,
                workspace_id,
                expected_version=body.expected_version,
                source=ModelSource(body.source),
                local_profile=body.local_profile,
            )
            return await source_state(connection, workspace_id, app_resources(request))
    except PolicyChanged as refused:
        raise reworded(refused, POLICY_CHANGED) from None
    except SourceRolesUncovered as refused:
        raise reworded(refused, refused.reason) from None
