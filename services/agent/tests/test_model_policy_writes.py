"""The workspace model policy's read and versioned writes, through the API in process (refactor plan
R-55, PAPI-01; PRD-Model-Providers MD-02 and MD-03).

A save or a reset locks the policy row, refuses a stale expected version with nothing written, and
otherwise writes the next version in the same transaction. A choice that isn't approved is refused
before any connection opens. No database or model is used.
"""

import asyncio
import json
from uuid import UUID

import pytest

from autobots.application.model_policy import PolicyChanged, save_model_policy, validated_choice
from autobots.domain.errors import RefusalKind
from autobots.domain.models import ModelProfileId, ProfileNotOffered, UnknownModelProfile
from fake_api import MEMBER, OWNER, WORKSPACE, ApiClient, FakeDatabase

READ = (
    "select version, default_profile, role_overrides from app_private.model_policies "
    "where workspace_id = %s"
)
SAVE_LOCK = "select version from app_private.model_policies where workspace_id = %s for update"
RESET_LOCK = (
    "select version, default_profile from app_private.model_policies "
    "where workspace_id = %s for update"
)
UPSERT = "insert into app_private.model_policies "
STALE = {"code": "stale_version", "message": "The policy changed. Reload and try again."}
SOL = "openrouter_sol"
TERRA = "openrouter_terra"


def put(client: ApiClient, body: dict[str, object], user: UUID = OWNER) -> tuple[int, object]:
    reply = client.http.put("/v1/settings/model-policy", headers=client.headers(user), json=body)
    return reply.status_code, reply.json()


def reset(client: ApiClient, expected: int, user: UUID = OWNER) -> tuple[int, object]:
    reply = client.http.post(
        "/v1/settings/model-policy/reset",
        headers=client.headers(user),
        json={"expected_version": expected},
    )
    return reply.status_code, reply.json()


def statements(client: ApiClient) -> list[str]:
    """The log without role questions, so connections, transactions and statements read in order."""
    return [entry for entry in client.log if entry != "role_in"]


def test_a_workspace_with_no_saved_policy_reads_version_0_with_no_default(
    api_client: ApiClient,
) -> None:
    reply = api_client.http.get("/v1/settings/model-policy", headers=api_client.headers(MEMBER))
    assert reply.status_code == 200
    body = reply.json()
    assert (body["version"], body["default_profile"], body["role_overrides"]) == (0, None, {})
    assert statements(api_client) == ["connect", READ, "release"]


def test_a_saved_policy_reads_as_saved(api_client: ApiClient) -> None:
    api_client.database.answer(READ, (4, SOL, {"executor": TERRA}))
    body = api_client.http.get("/v1/settings/model-policy", headers=api_client.headers()).json()
    assert (body["version"], body["default_profile"], body["role_overrides"]) == (
        4,
        SOL,
        {"executor": TERRA},
    )
    bindings = {item["role"]: item["profile"] for item in body["policy"]["bindings"]}
    assert bindings["executor"] == TERRA and bindings["planner"] == SOL


def test_a_save_locks_the_row_then_writes_the_next_version_in_one_transaction(
    api_client: ApiClient,
) -> None:
    api_client.database.answer(SAVE_LOCK, (2,))
    status, body = put(
        api_client,
        {"expected_version": 2, "default_profile": SOL, "role_overrides": {"executor": TERRA}},
    )
    assert status == 200
    assert isinstance(body, dict)
    assert (body["version"], body["default_profile"], body["role_overrides"]) == (
        3,
        SOL,
        {"executor": TERRA},
    )
    log = statements(api_client)
    assert log[:3] == ["connect", "begin", SAVE_LOCK]
    assert log[3].startswith(UPSERT) and log[4:] == ["commit", "release"]
    (written,) = api_client.database.written("app_private.model_policies")
    assert written == (WORKSPACE, 3, SOL, json.dumps({"executor": TERRA}))


def test_a_first_save_writes_version_1(api_client: ApiClient) -> None:
    status, body = put(
        api_client, {"expected_version": 0, "default_profile": None, "role_overrides": {}}
    )
    assert status == 200 and isinstance(body, dict) and body["version"] == 1
    (written,) = api_client.database.written("app_private.model_policies")
    assert written == (WORKSPACE, 1, None, "{}")


def test_a_stale_save_writes_nothing_and_rolls_back(api_client: ApiClient) -> None:
    api_client.database.answer(SAVE_LOCK, (5,))
    status, body = put(
        api_client, {"expected_version": 4, "default_profile": SOL, "role_overrides": {}}
    )
    assert (status, body) == (409, STALE)
    assert statements(api_client) == ["connect", "begin", SAVE_LOCK, "rollback", "release"]
    assert api_client.database.changes() == []


@pytest.mark.parametrize(
    ("choice", "refused"),
    [
        (
            {"default_profile": None, "role_overrides": {"not_a_role": TERRA}},
            {"code": "unknown_model", "message": "Choose an approved model and role."},
        ),
        (
            {"default_profile": "openrouter_deepseek_flash", "role_overrides": {}},
            {
                "code": "model_not_offered",
                "message": "DeepSeek isn't offered for new runs until it's qualified.",
            },
        ),
    ],
    ids=["unknown role", "profile not offered"],
)
def test_a_choice_that_isnt_approved_is_refused_before_any_connection(
    api_client: ApiClient, choice: dict[str, object], refused: dict[str, str]
) -> None:
    assert put(api_client, {"expected_version": 0, **choice}) == (422, refused)
    assert "connect" not in api_client.log


def test_only_the_owner_saves_or_resets(api_client: ApiClient) -> None:
    refused = {"code": "owner_required", "message": "Only the workspace owner can change this."}
    body: dict[str, object] = {"expected_version": 0, "default_profile": None, "role_overrides": {}}
    assert put(api_client, body, MEMBER) == (403, refused)
    assert reset(api_client, 0, MEMBER) == (403, refused)
    assert "connect" not in api_client.log


def test_a_reset_clears_every_override_and_keeps_the_default(api_client: ApiClient) -> None:
    api_client.database.answer(RESET_LOCK, (7, SOL))
    status, body = reset(api_client, 7)
    assert status == 200 and isinstance(body, dict)
    assert (body["version"], body["default_profile"], body["role_overrides"]) == (8, SOL, {})
    log = statements(api_client)
    assert log[:3] == ["connect", "begin", RESET_LOCK]
    assert log[3].startswith(UPSERT) and "'{}'" in log[3]
    assert log[4:] == ["commit", "release"]
    (written,) = api_client.database.written("app_private.model_policies")
    assert written == (WORKSPACE, 8, SOL)


def test_a_reset_with_no_saved_policy_starts_at_version_1(api_client: ApiClient) -> None:
    status, body = reset(api_client, 0)
    assert status == 200 and isinstance(body, dict)
    assert (body["version"], body["default_profile"]) == (1, None)


def test_a_stale_reset_writes_nothing_and_rolls_back(api_client: ApiClient) -> None:
    api_client.database.answer(RESET_LOCK, (7, SOL))
    assert reset(api_client, 6) == (409, STALE)
    assert statements(api_client) == ["connect", "begin", RESET_LOCK, "rollback", "release"]
    assert api_client.database.changes() == []


# Without HTTP: a worker, a tool or a script saves through the same function.


def test_a_stale_save_refuses_with_a_typed_refusal_outside_http() -> None:
    database = FakeDatabase([])
    database.answer(SAVE_LOCK, (3,))

    async def save() -> None:
        async with database.connection() as connection:
            await save_model_policy(
                connection,
                WORKSPACE,
                expected_version=2,
                default_profile=None,
                role_overrides={},
            )

    with pytest.raises(PolicyChanged) as refused:
        asyncio.run(save())
    assert (refused.value.code, refused.value.kind) == ("stale_version", RefusalKind.CONFLICT)
    assert database.changes() == []


def test_a_choice_is_validated_roles_first_then_offering() -> None:
    assert validated_choice(ModelProfileId.SOL, {"executor": ModelProfileId.TERRA}) == (
        SOL,
        {"executor": TERRA},
    )
    with pytest.raises(UnknownModelProfile):
        validated_choice(None, {"not_a_role": ModelProfileId.DEEPSEEK_FLASH})
    with pytest.raises(ProfileNotOffered):
        validated_choice(ModelProfileId.DEEPSEEK_FLASH, {})
