"""Real concurrent reservations through the runtime role, printed as JSON cases. Fixture money only."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import psycopg
from autobots.application.model_admission import (
    AdmissionRequest,
    BudgetExceeded,
    ModelAdmission,
    NoInferenceSlot,
    Ticket,
)
from checklib import Cases, run_check

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])


def request(root: UUID, cost: int, run: UUID | None = None, attempt: int = 1) -> AdmissionRequest:
    return AdmissionRequest(WORKSPACE, root, run or root, 'coder', 'openrouter_deepseek_flash', 'wire', attempt, cost)


async def admit_one(item: AdmissionRequest, at: datetime | None = None) -> Ticket:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as connection:
        return await ModelAdmission(connection).admit(item, at=at)


async def attempt_many(items: list[AdmissionRequest]) -> list[object]:
    return await asyncio.gather(*(admit_one(item) for item in items), return_exceptions=True)


async def main(cases: Cases) -> None:
    check = cases.check
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as connection:
        admission = ModelAdmission(connection)

        async def clear() -> None:
            # The runtime role cannot delete from the ledger, which is correct, so fixtures age out instead.
            await connection.execute("update app_private.model_invocations set status = 'cancelled', charged_micro_usd = 0, spend_day = '2000-01-01' where workspace_id = %s", (WORKSPACE,))
            await connection.execute('update app_private.model_spend_limits set slots = 2, run_limit_micro_usd = 1000000, daily_limit_micro_usd = 5000000 where workspace_id = %s', (WORKSPACE,))

        async def slots(count: int) -> None:
            await connection.execute(f'update app_private.model_spend_limits set slots = {count} where workspace_id = %s', (WORKSPACE,))

        with cases.scenario('inference slots'):
            root = uuid4()
            results = await attempt_many([request(root, 100) for _ in range(10)])
            admitted = [r for r in results if isinstance(r, Ticket)]
            refused = [r for r in results if isinstance(r, NoInferenceSlot)]
            check('ten concurrent attempts get exactly two slots', '2 admitted, 8 refused', f'{len(admitted)}, {len(refused)}', len(admitted) == 2 and len(refused) == 8)
            await admission.settle(admitted[0].invocation_id, 50)
            third = await admit_one(request(root, 100))
            check('a settled attempt frees its slot', 'admitted', third.reserved_micro_usd, third.reserved_micro_usd == 100)
        await clear()

        with cases.scenario('the run cap under concurrency'):
            root = uuid4()
            await connection.execute('insert into app_private.model_spend_limits (workspace_id) values (%s) on conflict (workspace_id) do nothing', (WORKSPACE,))
            await slots(100)
            results = await attempt_many([request(root, 300_000) for _ in range(10)])
            admitted = [r for r in results if isinstance(r, Ticket)]
            over_cap = [r for r in results if isinstance(r, BudgetExceeded)]
            total = await (await connection.execute('select sum(reserved_micro_usd) from app_private.model_invocations where root_run_id = %s', (root,))).fetchone()
            check('concurrent reservations cannot overrun the $1 run cap', '3 admitted, 900000 reserved', f'{len(admitted)}, {total[0] if total else None}',
                  len(admitted) == 3 and total is not None and total[0] == 900_000 and len(over_cap) == 7)
        await clear()

        with cases.scenario('the warning and the cap'):
            await slots(100)
            root = uuid4()
            first = await admit_one(request(root, 790_000))
            at_79 = first.warning
            second = await admit_one(request(root, 10_000))
            check('the warning starts at 80 percent', 'not at 79, yes at 80', f'{at_79}, {second.warning}, {second.run_percent}', not at_79 and second.warning and second.run_percent == 80)
            third = await admit_one(request(root, 200_000))
            check('exactly 100 percent is still admitted', '100', third.run_percent, third.run_percent == 100)
            await cases.refused('one more micro-dollar pauses admission', BudgetExceeded.code, admit_one(request(root, 1)), BudgetExceeded)
        await clear()

        with cases.scenario('a descendant'):
            await slots(100)
            root = uuid4()
            child = uuid4()
            await admit_one(request(root, 600_000))
            await cases.refused('a descendant shares the root budget', BudgetExceeded.code, admit_one(request(root, 600_000, run=child)), BudgetExceeded)
        await clear()

        with cases.scenario('the daily cap'):
            await slots(100)
            before = datetime(2026, 11, 5, 23, 59, 59, tzinfo=UTC)
            after = before + timedelta(seconds=2)
            for _ in range(5):
                await admit_one(request(uuid4(), 1_000_000), at=before)
            await cases.refused('the daily cap holds before UTC midnight', BudgetExceeded.code, admit_one(request(uuid4(), 1), at=before), BudgetExceeded)
            fresh = await admit_one(request(uuid4(), 1_000_000), at=after)
            check('the daily cap resets at UTC midnight', 'admitted, 20 percent', fresh.workspace_percent, fresh.workspace_percent == 20)
        await clear()

        with cases.scenario('a local-offset day'):
            offset = datetime(2026, 11, 5, 23, 30, tzinfo=UTC).astimezone(timezone(timedelta(hours=-6)))
            await slots(100)
            day_ticket = await admit_one(request(uuid4(), 5), at=offset)
            stored = await (await connection.execute('select spend_day::text from app_private.model_invocations where id = %s', (day_ticket.invocation_id,))).fetchone()
            day = stored[0] if stored else None
            check('a local-offset time buckets by its UTC day', '2026-11-05', day, day == '2026-11-05')
        await clear()

        with cases.scenario('a partial stream'):
            await slots(100)
            root = uuid4()
            ticket = await admit_one(request(root, 400_000))
            await admission.mark_dispatched(ticket.invocation_id)
            await admission.mark_uncertain(ticket.invocation_id, 'partial_stream', 'partial text')
            row = await (await connection.execute('select status, reserved_micro_usd, accumulated_output, charged_micro_usd from app_private.model_invocations where id = %s', (ticket.invocation_id,))).fetchone()
            check('a partial stream keeps the attempt and reservation', 'uncertain, 400000, the text, no charge', row, row == ('uncertain', 400_000, 'partial text', None))
            await cases.refused('the unresolved reservation still counts', BudgetExceeded.code, admit_one(request(root, 700_000)), BudgetExceeded)
            await admission.reconcile(ticket.invocation_id, 100_000)
            fits = await admit_one(request(root, 700_000))
            check('reconciling replaces the estimate with the reported charge', 'admitted', fits.run_percent, fits.run_percent == 80)
        await clear()

        with cases.scenario('cancellation and failure'):
            await slots(100)
            reserved = await admit_one(request(uuid4(), 100))
            dispatched = await admit_one(request(uuid4(), 100))
            await admission.mark_dispatched(dispatched.invocation_id)
            outcomes = (await admission.cancel(reserved.invocation_id), await admission.cancel(dispatched.invocation_id))
            check('cancelling before dispatch owes nothing; after dispatch is uncertain', 'cancelled, uncertain', outcomes, outcomes == ('cancelled', 'uncertain'))
            await cases.refused('an uncertain attempt cannot be quietly settled', None, admission.settle(dispatched.invocation_id, 1), ValueError)
            failed = await admit_one(request(uuid4(), 100))
            await admission.fail_before_acceptance(failed.invocation_id, 'network_before_acceptance')
            row = await (await connection.execute('select status, charged_micro_usd from app_private.model_invocations where id = %s', (failed.invocation_id,))).fetchone()
            check('a refusal before acceptance releases the money and keeps the row', 'recorded, charged 0', row, row == ('failed_before_acceptance', 0))
        await clear()


run_check(main)
