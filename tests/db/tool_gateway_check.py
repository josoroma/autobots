"""The gateway on a real database, and a real Deep Agents loop with a fake model. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.tool_middleware import GatewayMiddleware, visible_tools
from autobots.application.runs import admit_run, apply_worker_command
from autobots.application.tool_gateway import ToolDefinition, ToolFailed, ToolGateway, ToolScope
from autobots.application.tools import default_registry, first_grants
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import RunCommand
from autobots.domain.tools import OperationClass
from deepagents import create_deep_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import BaseModel

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
cases = []
calls: list[str] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


class Nothing(BaseModel):
    note: str = ''


class Recording(GenericFakeChatModel):
    bound: list[list[str]] = []  # noqa: RUF012 - a pydantic field, whose default pydantic copies for each instance

    def bind_tools(self, tools: Any, **_: Any) -> Any:
        self.bound.append([getattr(tool, 'name', str(tool)) for tool in tools])
        return self


def counted(tool_id: str, result: Any = None, error: Exception | None = None, delay: float = 0, operation_class: OperationClass = OperationClass.REVERSIBLE_INTERNAL_WRITE, **options: Any) -> ToolDefinition:
    async def handler(_: Any, __: Any) -> BaseModel:
        calls.append(tool_id)
        if delay:
            await asyncio.sleep(delay)
        if error is not None:
            raise error
        return result or Nothing()
    return ToolDefinition(tool_id=tool_id, version=1, description='fixture', input_model=Nothing, output_model=Nothing, operation_class=operation_class, handler=handler, **options)


async def main() -> None:
    registry = default_registry()
    gateway = ToolGateway(registry)
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def running(paths: tuple[str, ...] = ('outputs',), tools: dict[str, int] | None = None) -> ToolScope:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='tools', limit_micro_usd=1000, policy=resolve_role_policy())
            lease = await claim_next(db, worker_id='tools', lease_seconds=120)
            return ToolScope(WORKSPACE, admitted.run_id, lease.generation, tools if tools is not None else first_grants(), paths)

        scope = await running()
        run = await gateway.execute(db, scope, 'calculate', {'operation': 'mean', 'values': [1, 2, 6]})
        check('a granted pure tool runs', 'succeeded, 3', (run.outcome.value, run.output), run.outcome.value == 'succeeded' and run.output == {'result': 3.0})

        # Validate before execution.
        for name, arguments, code in (
                ('calculate', {'operation': 'exec', 'values': [1]}, 'invalid_arguments'),
                ('calculate', {'operation': 'sum', 'values': [1], 'shell': 'rm'}, 'invalid_arguments'),
                ('calculate', {'operation': 'sum'}, 'invalid_arguments'),
                ('calculate', '{"operation": "su', 'invalid_arguments'),
                ('save_artifact', {'path': 'outputs/a.md'}, 'invalid_arguments')):
            result = await gateway.execute(db, scope, name, arguments)
            check(f'{name} with {str(arguments)[:40]} is refused', code, result.code, result.code == code)
        files = (await (await db.execute('select count(*) from app_private.run_files where run_id = %s', (scope.run_id,))).fetchone())[0]
        check('refused calls left no effect', '0 files', files, files == 0)

        # Run status and ownership, checked before the effect.
        registry.register(counted('guarded'))
        guarded = await running(tools={'guarded': 1})
        await apply_worker_command(db, guarded, RunCommand.REQUEST_INPUT)
        result = await gateway.execute(db, guarded, 'guarded', {})
        check('a run that is not owned cannot use a tool', 'lease_lost', result.code, result.code == 'lease_lost')
        guarded = await running(tools={'guarded': 1})
        await db.execute("update public.runs set status = 'verifying' where id = %s", (guarded.run_id,))
        result = await gateway.execute(db, guarded, 'guarded', {})
        check('a run outside running cannot use a tool', 'run_not_running', result.code, result.code == 'run_not_running')
        stale = await running(tools={'guarded': 1})
        stale = ToolScope(stale.workspace_id, stale.run_id, stale.generation + 1, stale.tools)
        result = await gateway.execute(db, stale, 'guarded', {})
        check('a stale generation cannot use a tool', 'lease_lost', result.code, result.code == 'lease_lost')
        foreign = ToolScope(uuid4(), scope.run_id, scope.generation, scope.tools, scope.paths)
        result = await gateway.execute(db, foreign, 'calculate', {'operation': 'sum', 'values': [1]})
        check('another workspace cannot use the run', 'run_not_found', result.code, result.code == 'run_not_found')
        check('none of those reached the tool', 'no calls', calls.count('guarded'), calls.count('guarded') == 0)

        # A timeout on a pure tool fails, and a timed out effect stays unknown.
        registry.register(counted('slow_pure', delay=1, operation_class=OperationClass.PURE, timeout_seconds=0.05, retries=1))
        slow = await running(tools={'slow_pure': 1})
        result = await gateway.execute(db, slow, 'slow_pure', {})
        check('a slow read fails after its bounded retry', 'tool_timeout, 2 calls', (result.code, calls.count('slow_pure')), result.code == 'tool_timeout' and calls.count('slow_pure') == 2)

        # Inherited capabilities are refused whatever the SDK attaches.
        for name in ('execute', 'ls', 'read_file', 'write_file', 'edit_file', 'glob', 'grep', 'task', 'delete', 'write_todos', 'mcp__server__tool', 'shell'):
            result = await gateway.execute(db, scope, name, {'command': 'id', 'file_path': '/etc/passwd', 'path': '/'})
            check(f'{name} is denied', 'tool_not_granted', result.code, result.code == 'tool_not_granted')
        registry.register(counted('remote_write', operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE))
        remote = await running(tools={'remote_write': 1})
        result = await gateway.execute(db, remote, 'remote_write', {})
        check('a consequential write needs an approval first', 'approval_pending, not called', (result.code, calls.count('remote_write')), result.code == 'approval_pending' and calls.count('remote_write') == 0)
        versioned = await running(tools={'calculate': 2})
        result = await gateway.execute(db, versioned, 'calculate', {'operation': 'sum', 'values': [1]})
        check('a version that does not exist is refused', 'tool_not_registered', result.code, result.code == 'tool_not_registered')

        for path in ('../other/secret.md', '/etc/passwd', 'outputs/../../x', 'outputs//x', 'private/x.md', 'outputs\\x', 'outputsx/a.md', '.env'):
            result = await gateway.execute(db, scope, 'save_artifact', {'path': path, 'content': 'x'})
            check(f'{path} is outside the grant', 'resource_not_granted', result.code, result.code == 'resource_not_granted')
        result = await gateway.execute(db, scope, 'read_run_file', {'path': '/etc/passwd'})
        check('a read outside the grant is refused', 'resource_not_granted', result.code, result.code == 'resource_not_granted')

        # Reuse the identity and the receipt. Each `running()` above ended the previous run's job.
        scope = await running()
        first = await gateway.execute(db, scope, 'save_artifact', {'path': 'outputs/report.md', 'content': 'one'})
        again = await gateway.execute(db, scope, 'save_artifact', {'path': 'outputs/report.md', 'content': 'one'})
        versions = (await (await db.execute('select count(*) from app_private.run_files where run_id = %s', (scope.run_id,))).fetchone())[0]
        check('a repeated save reuses its receipt', 'same output, replayed, 1 row', (again.replayed, again.operation_id == first.operation_id, versions), again.replayed and again.output == first.output and again.operation_id == first.operation_id and versions == 1)
        changed = await gateway.execute(db, scope, 'save_artifact', {'path': 'outputs/report.md', 'content': 'two'})
        check('different content is a different operation', 'version 2', changed.output['version'], changed.output['version'] == 2 and changed.operation_id != first.operation_id)
        read = await gateway.execute(db, scope, 'read_run_file', {'path': 'outputs/report.md'})
        check('a read sees the current version', 'two', read.output['content'], read.output['content'] == 'two')
        missing = await gateway.execute(db, scope, 'read_run_file', {'path': 'outputs/none.md'})
        check('a missing file is a clean failure', 'file_not_found', missing.code, missing.code == 'file_not_found')
        other = await running()
        hidden = await gateway.execute(db, other, 'read_run_file', {'path': 'outputs/report.md'})
        check("another run's file is not readable", 'file_not_found', hidden.code, hidden.code == 'file_not_found')

        # Across a new generation after a real lease loss.
        replay_scope = await running()
        saved = await gateway.execute(db, replay_scope, 'save_artifact', {'path': 'outputs/r.md', 'content': 'r'})
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (replay_scope.run_id,))
        replacement = await claim_next(db, worker_id='replacement', lease_seconds=120)
        fresh = ToolGateway(default_registry())
        next_scope = ToolScope(WORKSPACE, replay_scope.run_id, replacement.generation, first_grants(), ('outputs',))
        result = await fresh.execute(db, next_scope, 'save_artifact', {'path': 'outputs/r.md', 'content': 'r'})
        check('a replacement generation reuses the receipt', 'replayed, same output', (result.replayed, result.output == saved.output), result.replayed and result.output == saved.output)

        # An effect interrupted before its receipt.
        lost_scope = await running()
        arguments = {'path': 'outputs/lost.md', 'content': 'lost'}
        first = await gateway.execute(db, lost_scope, 'save_artifact', arguments)
        await db.execute("update app_private.tool_receipts set status = 'started', result = null where operation_id = %s", (first.operation_id,))
        result = await gateway.execute(db, lost_scope, 'save_artifact', arguments)
        rows = (await (await db.execute("select count(*) from app_private.run_files where run_id = %s and path = 'outputs/lost.md'", (lost_scope.run_id,))).fetchone())[0]
        check('a lost response is reconciled by readback, without repeating', 'succeeded, 1 row', (result.outcome.value, rows), result.outcome.value == 'succeeded' and rows == 1 and result.output == first.output)

        registry.register(counted('crashes', error=RuntimeError('token sk-or-secret-text')))
        crash = await running(tools={'crashes': 1})
        result = await gateway.execute(db, crash, 'crashes', {})
        check('an effect that raises is unknown, not failed', 'unknown', result.outcome.value, result.outcome.value == 'unknown')
        check('its error text stays out of what the model sees', 'no secret', 'sk-or' in result.for_model(), 'sk-or' not in result.for_model())
        before = calls.count('crashes')
        result = await gateway.execute(db, crash, 'crashes', {})
        check('an unknown effect with no readback is not repeated', 'unknown, not called', (result.outcome.value, calls.count('crashes') - before), result.outcome.value == 'unknown' and calls.count('crashes') == before)

        registry.register(counted('declined', error=ToolFailed('destination_refused')))
        declined = await running(tools={'declined': 1})
        result = await gateway.execute(db, declined, 'declined', {})
        check('a confirmed failure says so', 'failed', (result.outcome.value, result.code), result.outcome.value == 'failed' and result.code == 'destination_refused')
        before = calls.count('declined')
        await gateway.execute(db, declined, 'declined', {})
        check('a confirmed failure may be tried again', 'called again', calls.count('declined') - before, calls.count('declined') == before + 1)

        registry.register(counted('slow_write', delay=1, timeout_seconds=0.05))
        timed = await running(tools={'slow_write': 1})
        result = await gateway.execute(db, timed, 'slow_write', {})
        check('a timed out effect is unknown', 'unknown', result.outcome.value, result.outcome.value == 'unknown')

        # The lease is lost while the effect runs: the receipt keeps the truth.
        async def lose_lease(_: Any, context: Any) -> BaseModel:
            calls.append('during')
            await db.execute("update app_private.run_jobs set generation = generation + 1 where run_id = %s", (context.scope.run_id,))
            return Nothing()
        registry.register(ToolDefinition(tool_id='during', version=1, description='fixture', input_model=Nothing, output_model=Nothing, operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE, handler=lose_lease))
        during = await running(tools={'during': 1})
        result = await gateway.execute(db, during, 'during', {})
        status = (await (await db.execute('select status from app_private.tool_receipts where operation_id = %s', (result.operation_id,))).fetchone())[0]
        check('a result arriving after the lease is lost is recorded and refused', 'lease_lost, receipt succeeded', (result.code, status), result.code == 'lease_lost' and status == 'succeeded')

        # A real Deep Agents loop: the model tries everything, and only the gateway answers.
        loop_scope = await running()
        marker = Path(os.environ['AUTOBOTS_TOOL_TEMP']) / 'sdk-wrote-this.txt'
        attempts = [
            ('execute', {'command': f'touch {marker}'}), ('write_file', {'file_path': str(marker), 'content': 'x'}),
            ('read_file', {'file_path': '/etc/passwd'}), ('ls', {'path': '/'}), ('task', {'description': 'do it', 'subagent_type': 'general-purpose'}),
            ('mcp__server__tool', {}), ('calculate', {'operation': 'sum', 'values': [2, 3]}),
            ('save_artifact', {'path': 'outputs/loop.md', 'content': 'from the loop'}),
        ]
        model = Recording(messages=iter([
            AIMessage(content='', tool_calls=[{'name': name, 'args': args, 'id': f'call-{index}', 'type': 'tool_call'} for index, (name, args) in enumerate(attempts)]),
            AIMessage(content='done')]))
        model.bound = []
        agent = create_deep_agent(model=model, tools=visible_tools(gateway, loop_scope), middleware=[GatewayMiddleware(gateway, db, loop_scope)])
        sdk_tools = sorted(agent.nodes['tools'].bound.tools_by_name)
        check('the SDK still attaches its own tools, so hiding them alone would not be enough', 'execute among them', sdk_tools, 'execute' in sdk_tools)
        state = await agent.ainvoke({'messages': [('user', 'go')]})
        check('the model is shown only the granted tools', 'three names', model.bound[0], sorted(model.bound[0]) == ['calculate', 'read_run_file', 'save_artifact'])
        replies = {message.name: json.loads(message.content) for message in state['messages'] if message.type == 'tool'}
        denied = [name for name, _ in attempts[:6]]
        check('every inherited or unknown tool the model calls is denied', 'all tool_not_granted', {replies[name]['code'] for name in denied}, all(replies[name]['code'] == 'tool_not_granted' for name in denied))
        check('and nothing it asked for happened', 'no file', marker.exists(), not marker.exists())
        check('granted tools work through the loop', '5.0, saved', (replies['calculate']['output'], replies['save_artifact']['outcome']), replies['calculate']['output'] == {'result': 5.0} and replies['save_artifact']['outcome'] == 'succeeded')
        check('the loop finished', 'done', state['messages'][-1].content, state['messages'][-1].content == 'done')
    print(json.dumps({'cases': cases}))


asyncio.run(main())
