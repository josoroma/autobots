"""A real worker process around a scripted model, restarted if it dies. No provider is involved.

The script depends only on the goal and what the conversation holds, so a restarted worker carries
on from what its checkpoint restored. It kills itself once, when told to, inside a model call.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psycopg
from autobots.adapters.loop_middleware import ModelRoute
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.application.compaction import SUMMARY_MARKER
from autobots.application.goal_loop import LoopConfig, process_next
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import SecretStr

URL = os.environ['AUTOBOTS_DATABASE_URL']
MARKER = Path(os.environ['AUTOBOTS_TEST_DIED_MARKER'])
ROUTE = ModelRoute('executor', 'openrouter_terra', 'fixture/model', 1000)
TASKS = [{'id': 'report', 'title': 'Write the totals report', 'criteria': ['c1'], 'expected_evidence': 'the published report'}]
PLAN = ('propose_plan', {'tasks': TASKS})
READ = ('read_run_file', {'path': 'inputs/data.md'})
PUBLISH = ('publish_artifact', {'path': 'outputs/report.md', 'version': 1})
DONE = ('complete_task', {'task_id': 'report', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/report.md'}], 'summary': 'Reported the total of the two counts.'})
FINISHED = 'The report is ready.'
# A second death, for a run page test, since the first marker is the slice's.
DIED_AGAIN = MARKER.with_name(MARKER.name + '-again')
# One provider failure on a run, retried, so a finished run has a failed call to show.
FLAKED = MARKER.with_name(MARKER.name + '-flaked')
# Long enough for a person's controls to meet a run that's really running.
SLOW_SECONDS = 2.0


def replies(messages: Any, name: str) -> list[dict[str, Any]]:
    return [json.loads(message.content) for message in messages if message.type == 'tool' and message.name == name]


LONG = 'x' * 6_000
COMPACT_TASKS = [{'id': 'report', 'title': 'Write the long report', 'criteria': ['c1'], 'expected_evidence': 'the published report'}]
COMPACT_STEPS = (('propose_plan', {'tasks': COMPACT_TASKS}),
                 *(('save_artifact', {'path': f'outputs/part-{n}.md', 'content': LONG}) for n in range(6)),
                 ('save_artifact', {'path': 'outputs/report.md', 'content': '# Totals\n\nTotal: 5\n'}),
                 PUBLISH, DONE)
POSITION: dict[str, int] = {}
PART_TASK = {'id': 'k', 'title': 'Do the part', 'criteria': ['c1'], 'expected_evidence': 'a file'}
PART_STEPS = (('propose_plan', {'tasks': [PART_TASK]}),
              ('save_artifact', {'path': 'outputs/child-1/part.md', 'content': 'the part'}),
              ('publish_artifact', {'path': 'outputs/child-1/part.md', 'version': 1}),
              ('complete_task', {'task_id': 'k', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/child-1/part.md'}], 'summary': 'Did the part.'}))


def scripted(name: str, steps: tuple, final: str) -> Any:
    """Compaction takes earlier replies out of the model's view, so the position lives here."""
    position = POSITION.get(name, 0)
    POSITION[name] = position + 1
    return steps[position] if position < len(steps) else final


def next_step(goal: str, messages: Any) -> Any:
    """Each step uses what the tools really returned, so a refused tool can't reach a total."""
    if 'slice-only-claims' in goal:
        return 'It is all done, trust me.'
    if SUMMARY_MARKER in str(messages[-1].content):
        return 'Arranged summary: the long parts were saved.'
    compact = re.search(r'slice-compact-\d+', goal)
    if compact:
        # Slow at the start, so a person can read the page before anything compacts.
        if POSITION.get(compact.group(0), 0) < 3:
            time.sleep(SLOW_SECONDS)
        return scripted(compact.group(0), COMPACT_STEPS, FINISHED)
    if 'slice-child-part' in goal:
        return scripted(goal, PART_STEPS, 'The part is done.')
    delegate = re.search(r'slice-delegate expert=([0-9a-f-]{36})', goal)
    if delegate:
        assign = ('assign_specialist', {'expert_id': delegate.group(1), 'goal': 'slice-child-part', 'criteria': ['Finish the part']})
        lead = {'id': 'p', 'title': 'Delegate', 'criteria': ['c1'], 'expected_evidence': 'a child result'}
        done = ('complete_task', {'task_id': 'p', 'evidence': [{'kind': 'note', 'reference': 'the child reported'}], 'summary': 'The part came back.'})
        return scripted(delegate.group(0), (('propose_plan', {'tasks': [lead]}), assign, done), FINISHED)
    if not replies(messages, 'propose_plan'):
        return PLAN
    if not replies(messages, 'read_run_file'):
        return READ
    document = replies(messages, 'read_run_file')[-1]
    if document['outcome'] != 'succeeded':
        return 'The document could not be read.'
    if not replies(messages, 'calculate'):
        values = [float(number) for number in re.findall(r': (\d+)', document['output']['content'])]
        return ('calculate', {'operation': 'sum', 'values': values})
    total = replies(messages, 'calculate')[-1]
    if total['outcome'] != 'succeeded':
        return 'The total could not be calculated.'
    if not replies(messages, 'save_artifact'):
        value = int(total['output']['result']) + (1 if 'slice-wrong-total' in goal else 0)
        return ('save_artifact', {'path': 'outputs/report.md', 'content': f'# Totals\n\nTotal: {value}\n'})
    if 'slice-no-artifact' not in goal and not replies(messages, 'publish_artifact'):
        if 'slice-complete' in goal and not MARKER.exists():
            MARKER.write_text('died')
            os.kill(os.getpid(), signal.SIGKILL)
        if 'slice-uncertain' in goal and not DIED_AGAIN.exists():
            DIED_AGAIN.write_text('died')
            os.kill(os.getpid(), signal.SIGKILL)
        return PUBLISH
    if not replies(messages, 'complete_task'):
        return DONE
    return FINISHED


class ProviderFlake(Exception):
    status_code = 500


class GoalScript(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return 'goal-script'

    def bind_tools(self, tools: Any, **_: Any) -> Any:
        return self

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **_: Any) -> ChatResult:
        goal = ' '.join(str(message.content) for message in messages if message.type == 'human')
        if 'slice-failed-call' in goal and not FLAKED.exists():
            FLAKED.write_text('failed once')
            raise ProviderFlake('arranged')
        if 'slice-slow' in goal:
            time.sleep(SLOW_SECONDS)
        step = next_step(goal, messages)
        metadata = {'finish_reason': 'stop', 'cost': 0.0001}
        if isinstance(step, str):
            message = AIMessage(content=step, response_metadata=metadata)
        else:
            position = sum(item.type == 'ai' for item in messages)
            message = AIMessage(content='', response_metadata=metadata, tool_calls=[{'name': step[0], 'args': step[1], 'id': f'call-{position}', 'type': 'tool_call'}])
        if 'slice-reasoned' in goal:
            # Arranged: what a real route can return, which reaches checkpoints and must go no further.
            message.additional_kwargs['reasoning_details'] = [{'type': 'reasoning.encrypted', 'data': 'PROTECTED-REASONING', 'index': 0}]
        return ChatResult(generations=[ChatGeneration(message=message)])


async def worker() -> None:
    store = SupabaseObjectStore(os.environ['AUTOBOTS_STORAGE_BASE'], SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE']))
    config = LoopConfig(route=ROUTE, object_store=store, heartbeat_seconds=0.5, lease_seconds=2)
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        while True:
            await process_next(db, URL, f'fixture-{os.getpid()}', GoalScript, config)
            await asyncio.sleep(0.2)


def main() -> None:
    """Stands in for whatever restarts a worker. A real supervisor isn't part of this story."""
    if len(sys.argv) > 1 and sys.argv[1] == 'run':
        asyncio.run(worker())
        return
    while True:
        subprocess.run([sys.executable, __file__, 'run'], check=False)


if __name__ == '__main__':
    main()
