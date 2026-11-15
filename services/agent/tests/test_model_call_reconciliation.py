"""An owner's reconciliation of a run's oldest uncertain model call, through the API in process
(refactor plan R-55, PAPI-01; SP-012, US-4.8).

The run is checked first. Then, in one transaction: the key's receipt is read under its advisory
lock, the oldest open call is locked, reconciled from the reported charge and the receipt stored. A
repeat replays the first answer without locking anything again. No database or model is used.
"""

import asyncio
import json
from uuid import UUID

from autobots.application.reconciliation import reconcile_oldest_uncertain_call
from autobots.application.runs import request_hash
from fake_api import MEMBER, OWNER, WORKSPACE, ApiClient, FakeDatabase

RUN = UUID("0b000000-0000-4000-8000-0000000000c1")
CALL = UUID("0b000000-0000-4000-8000-0000000000c2")
RUN_EXISTS = "select 1 from public.runs where id = %s and workspace_id = %s"
KEY_LOCK = "select pg_advisory_xact_lock(hashtextextended(%s, 0))"
RECEIPT = "from app_private.idempotency_receipts"
OLDEST = (
    "select id from app_private.model_invocations "
    "where (run_id = %s or root_run_id = %s) "
    "and status = 'uncertain' and reconciled_at is null "
    "order by created_at limit 1 for update"
)
SETTLE = "update app_private.model_invocations set "
STORE = "insert into app_private.idempotency_receipts "
CHARGED = {"charged_micro_usd": 1200}


def reconcile(client: ApiClient, user: UUID = OWNER, key: str = "key-1") -> tuple[int, object]:
    reply = client.http.post(
        f"/v1/runs/{RUN}/model-calls/reconcile",
        headers=client.headers(user, **{"Idempotency-Key": key}),
        json=CHARGED,
    )
    return reply.status_code, reply.json()


def steps(client: ApiClient) -> list[str]:
    """Connections, transactions and statements, by the start of each statement."""
    names = {
        RUN_EXISTS: "run exists",
        KEY_LOCK: "key lock",
        "select request_hash, result " + RECEIPT: "receipt",
        OLDEST: "oldest open call",
        SETTLE: "settle",
        STORE: "store receipt",
    }
    found = []
    for entry in client.log:
        if entry == "role_in":
            continue
        found.append(next((name for part, name in names.items() if entry.startswith(part)), entry))
    return found


def test_the_oldest_open_call_is_settled_and_the_receipt_stored_in_one_transaction(
    api_client: ApiClient,
) -> None:
    api_client.database.answer(RUN_EXISTS, (1,))
    api_client.database.answer(OLDEST, (CALL,))
    api_client.database.answer(SETTLE, (CALL,))
    assert reconcile(api_client) == (200, {"schema_version": 1, "reconciled_calls": 1})
    assert steps(api_client) == [
        "connect",
        "run exists",
        "begin",
        "key lock",
        "receipt",
        "oldest open call",
        "settle",
        "store receipt",
        "commit",
        "release",
    ]
    settled = [values for text, values in api_client.database.statements if text.startswith(SETTLE)]
    assert settled == [(1200, "succeeded", "owner", CALL, "uncertain")]
    (stored,) = api_client.database.written("app_private.idempotency_receipts")
    assert stored == (
        WORKSPACE,
        OWNER,
        "reconcile_model_call",
        str(RUN),
        "key-1",
        request_hash({"charged": 1200}),
        json.dumps({"reconciled_calls": 1}),
    )


def test_with_no_open_call_nothing_is_settled_and_the_receipt_says_0(
    api_client: ApiClient,
) -> None:
    api_client.database.answer(RUN_EXISTS, (1,))
    assert reconcile(api_client) == (200, {"schema_version": 1, "reconciled_calls": 0})
    assert "settle" not in steps(api_client)
    (stored,) = api_client.database.written("app_private.idempotency_receipts")
    assert isinstance(stored, tuple) and stored[-1] == json.dumps({"reconciled_calls": 0})


def test_a_repeat_replays_the_first_answer_without_locking_a_call(api_client: ApiClient) -> None:
    api_client.database.answer(RUN_EXISTS, (1,))
    api_client.database.answer(RECEIPT, (request_hash({"charged": 1200}), {"reconciled_calls": 1}))
    assert reconcile(api_client) == (200, {"schema_version": 1, "reconciled_calls": 1})
    assert steps(api_client) == [
        "connect",
        "run exists",
        "begin",
        "key lock",
        "receipt",
        "commit",
        "release",
    ]
    assert api_client.database.changes() == []


def test_a_key_reused_for_another_charge_is_refused_and_rolled_back(api_client: ApiClient) -> None:
    api_client.database.answer(RUN_EXISTS, (1,))
    api_client.database.answer(RECEIPT, (request_hash({"charged": 99}), {"reconciled_calls": 1}))
    status, body = reconcile(api_client)
    assert (status, body) == (
        409,
        {
            "code": "idempotency_conflict",
            "message": "This key was already used with different content.",
        },
    )
    assert "rollback" in api_client.log and api_client.database.changes() == []


def test_a_run_not_in_this_workspace_is_not_found_before_any_transaction(
    api_client: ApiClient,
) -> None:
    status, body = reconcile(api_client)
    assert (status, body) == (
        404,
        {"code": "run_not_found", "message": "That run is not available."},
    )
    assert steps(api_client) == ["connect", "run exists", "release"]


def test_only_the_owner_reconciles(api_client: ApiClient) -> None:
    status, body = reconcile(api_client, MEMBER)
    assert status == 403 and isinstance(body, dict) and body["code"] == "owner_required"
    assert "connect" not in api_client.log


def test_effect_evidence_for_a_run_not_in_this_workspace_is_not_found(
    api_client: ApiClient,
) -> None:
    reply = api_client.http.post(
        f"/v1/runs/{RUN}/effects/op-1/reconcile",
        headers=api_client.headers(OWNER, **{"Idempotency-Key": "key-1"}),
        json={"outcome": "delivered", "evidence": "Seen in the destination", "generation": 1},
    )
    assert (reply.status_code, reply.json()["code"]) == (404, "run_not_found")
    assert steps(api_client) == ["connect", "run exists", "release"]


def test_the_reconciliation_runs_without_http() -> None:
    """A worker, a tool or a script settles a call through the same function."""
    database = FakeDatabase([])
    database.answer(OLDEST, (CALL,))
    database.answer(SETTLE, (CALL,))

    async def settle() -> int:
        async with database.connection() as connection:
            return await reconcile_oldest_uncertain_call(
                connection,
                workspace_id=WORKSPACE,
                actor_id=OWNER,
                run_id=RUN,
                idempotency_key="key-1",
                charged_micro_usd=1200,
            )

    assert asyncio.run(settle()) == 1
    assert database.log[1] == "begin" and database.log[-2:] == ["commit", "release"]
