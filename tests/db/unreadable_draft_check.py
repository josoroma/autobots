"""An unreadable workflow draft on a real database, through the runtime role (R-56, SQLI-13, Decision
0029 F3). JSON cases.

Migration 59's check refuses a graph that isn't an object holding nodes and links arrays. A draft the
check admits but WorkflowGraph refuses, as an owner could write through PostgREST (US-15.12#1), is
written here directly as the runtime role (arranged). The list and the workflow still load, reporting
it as unreadable rather than showing it, publishing it is refused, and discarding it removes it by key.

Argument: the workspace.
"""
from __future__ import annotations

import json
import os
import sys
from uuid import UUID, uuid4

import psycopg
from autobots.application.workflows import (
    WorkflowRefused,
    create_workflow,
    discard_draft,
    get_workflow,
    list_workflows,
    publish_draft,
)
from checklib import Cases, Db, run_check

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
ACTOR = uuid4()
# Passes the shape check, fails WorkflowGraph: the node has no block or version.
UNREADABLE = {'nodes': [{'id': 'x'}], 'links': []}
SAVE = 'insert into public.workflow_drafts (workflow_id, workspace_id, graph, saved_by) values (%s, %s, %s, %s)'


async def main(cases: Cases) -> None:
    async with Db.connect(URL, cases, WORKSPACE, ACTOR) as db:
        flow = await create_workflow(db.connection, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()),
                                     name=f'Unreadable draft {uuid4().hex[:8]}')
        for label, graph in (('no links array', {'nodes': []}), ('nodes that are not an array', {'nodes': {}, 'links': []}),
                             ('a graph that is not an object', [])):
            await cases.refused(f'the schema refuses a draft with {label}, whoever writes it', None,
                                db.connection.execute(SAVE, (flow.id, WORKSPACE, json.dumps(graph), ACTOR)), psycopg.errors.CheckViolation)
        await db.connection.execute(SAVE, (flow.id, WORKSPACE, json.dumps(UNREADABLE), ACTOR))
        stored = await db.value('select count(*) from public.workflow_drafts where workflow_id = %s', flow.id)
        cases.check('arranged: a draft the check admits and WorkflowGraph refuses', '1 row', stored, stored == 1)

        listed = {view.id: view for view in await list_workflows(db.connection, WORKSPACE)}
        shown = (listed[flow.id].draft, listed[flow.id].draft_unreadable) if flow.id in listed else 'not listed'
        cases.check('the workflow list still loads, reporting the draft as unreadable', 'no draft, unreadable', shown, shown == (None, True))
        view = await get_workflow(db.connection, WORKSPACE, flow.id)
        cases.check('the workflow still loads, reporting the draft as unreadable', 'no draft, unreadable',
                    (view.draft, view.draft_unreadable), (view.draft, view.draft_unreadable) == (None, True))
        await cases.refused('an unreadable draft is never published', 'workflow_draft_not_found',
                            publish_draft(db.connection, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id,
                                          idempotency_key=str(uuid4()), expected_version=0), WorkflowRefused)
        kept = await db.value('select count(*) from public.workflow_drafts where workflow_id = %s', flow.id)
        cases.check('a refused publish keeps the draft', '1 row', kept, kept == 1)

        discarded = await discard_draft(db.connection, WORKSPACE, flow.id)
        left = await db.value('select count(*) from public.workflow_drafts where workflow_id = %s', flow.id)
        cases.check('the owner discards it by its key', 'no draft, none unreadable, no row', (discarded.draft, discarded.draft_unreadable, left),
                    discarded.draft is None and not discarded.draft_unreadable and left == 0)
        await cases.refused('discarding it again finds no draft', 'workflow_draft_not_found',
                            discard_draft(db.connection, WORKSPACE, flow.id), WorkflowRefused)


run_check(main)
