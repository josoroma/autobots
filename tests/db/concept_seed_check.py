"""US-15.25: the concept seed on a disposable stack, in a fresh workspace, with no GitHub variables.

Migrations alone must have created none of it. Run twice, it leaves each Expert and workflow once.
It holds no secret, leaves nothing pending, and follows SD-02: the GitHub-only workflows and Interview
synthesis are drafts, the rest published, and Experts are saved without their unavailable tools. JSON
cases out.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import psycopg

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = sys.argv[1]
ROOT = Path(__file__).resolve().parents[2]
EXPERTS = ['Market watcher', 'Research analyst', 'Brief writer', 'Issue triager', 'Code maintainer']
WORKFLOWS = ['Weekly competitor brief', 'Monthly FX and inflation note', 'Nightly test triage', 'Interview synthesis',
             'Release notes from merged PRs', 'Vendor due diligence']
DRAFTS = {'Nightly test triage', 'Release notes from merged PRs', 'Interview synthesis'}
SECRET = re.compile(r'sk-or-|sk-[A-Za-z0-9]{16,}|eyJ[A-Za-z0-9_-]{10,}|ghp_|github_pat_|Bearer |password\s*[:=]|secret\s*[:=]', re.IGNORECASE)
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:400], 'passed': bool(passed)})


def rows(db: psycopg.Connection, sql: str, *values: Any) -> list[tuple[Any, ...]]:
    return list(db.execute(sql, values).fetchall())


def run_seed() -> dict[str, Any]:
    # Only what the seed needs: no GitHub or provider variable reaches it.
    env = {'PATH': os.environ.get('PATH', ''), 'AUTOBOTS_DATABASE_URL': URL, 'PYTHONPATH': os.environ.get('PYTHONPATH', ''),
           'PYTHONDONTWRITEBYTECODE': '1'}
    done = subprocess.run([sys.executable, '-m', 'autobots.operations.concept_seed', '--workspace', WORKSPACE],
                          env=env, capture_output=True, text=True, timeout=120, check=False)
    if done.returncode:
        raise SystemExit(f'the seed failed: {done.stderr[-400:]}')
    return json.loads(done.stdout.strip().splitlines()[-1])


def main() -> None:
    with psycopg.connect(URL, autocommit=True) as db:
        before = rows(db, 'select count(*) from public.experts where workspace_id = %s', WORKSPACE)[0][0] + \
            rows(db, 'select count(*) from public.workflows where workspace_id = %s', WORKSPACE)[0][0]
        named = [path.name for path in [*(ROOT / 'supabase/migrations').glob('*.sql'), *(ROOT / 'supabase').glob('seed*.sql'),
                                        *(ROOT / 'supabase/seeds').glob('*.sql')]
                 if any(name in path.read_text() for name in EXPERTS + WORKFLOWS)]
        check('migrations and reference seeds alone create none of it', 'an empty workspace, and no migration or seed names them',
              (before, named), before == 0 and not named)
        first, second = run_seed(), run_seed()
        experts = rows(db, 'select name, count(*) from public.experts where workspace_id = %s and name = any(%s) group by name', WORKSPACE, EXPERTS)
        flows = rows(db, 'select name, count(*) from public.workflows where workspace_id = %s and name = any(%s) group by name', WORKSPACE, WORKFLOWS)
        check('run twice, each Expert and workflow is there once', '5 Experts and 6 workflows, once each',
              (sorted(experts), sorted(flows)), sorted(name for name, count in experts if count == 1) == sorted(EXPERTS)
              and sorted(name for name, count in flows if count == 1) == sorted(WORKFLOWS))
        kept = set(second['experts'].values()) | set(second['workflows'].values())
        check('the second run keeps what the first made, and overwrites nothing', 'all kept', kept, kept == {'kept'})
        versions = rows(db, 'select e.name, count(v.version) from public.experts e join public.expert_versions v on v.expert_id = e.id '
                            'where e.workspace_id = %s group by e.name', WORKSPACE)
        check('each Expert has exactly one version after two runs', 'one each', sorted(versions), all(count == 1 for _, count in versions))

        states = {name: (latest, drafted) for name, latest, drafted in rows(
            db, 'select w.name, w.latest_version, exists (select 1 from public.workflow_drafts d where d.workflow_id = w.id) '
                'from public.workflows w where w.workspace_id = %s', WORKSPACE)}
        drafts = sorted(name for name, (latest, drafted) in states.items() if latest == 0 and drafted)
        published = sorted(name for name, (latest, drafted) in states.items() if latest == 1 and not drafted)
        check('with no GitHub variables, the GitHub workflows and Interview synthesis are drafts, and the other three are published',
              f'drafts {sorted(DRAFTS)}', (drafts, published), drafts == sorted(DRAFTS) and published == sorted(set(WORKFLOWS) - DRAFTS))
        unavailable = {name: report['unavailable'] for name, report in first['workflows'].items() if isinstance(report, dict) and report.get('draft')}
        check('a draft names the unavailable tools that made it one', 'GitHub tools for the two, none for Interview synthesis', unavailable,
              unavailable.get('Interview synthesis') == [] and all(tool.startswith(('github_', 'create_github')) for tool in
                                                                  unavailable.get('Nightly test triage', []) + unavailable.get('Release notes from merged PRs', []))
              and unavailable.get('Nightly test triage') and unavailable.get('Release notes from merged PRs'))

        configs = {name: config for name, config in rows(
            db, 'select e.name, v.config from public.experts e join public.expert_versions v on v.expert_id = e.id and v.version = e.latest_version '
                'where e.workspace_id = %s', WORKSPACE)}
        github = {name: [tool for tool in configs[name]['tools'] if 'github' in tool] for name in ('Issue triager', 'Code maintainer')}
        said = {name: 'Saved without' in configs[name]['purpose'] and 'github' in configs[name]['purpose'] for name in ('Issue triager', 'Code maintainer')}
        check('Issue triager and Code maintainer are saved without their GitHub tools, and say so in their purpose', 'no GitHub tool, said',
              (github, said), github == {'Issue triager': [], 'Code maintainer': []} and all(said.values()))
        check('the tools that are available are kept', 'Code maintainer keeps its file tools; Market watcher keeps its tools',
              (configs['Code maintainer']['tools'], configs['Market watcher']['tools']),
              {'search_files', 'read_code_file', 'patch_code_file', 'write_code_file'} <= set(configs['Code maintainer']['tools'])
              and {'calculate', 'read_csv', 'save_artifact'} <= set(configs['Market watcher']['tools']))
        labels = rows(db, "select v.graph -> 'nodes' from public.workflow_versions v join public.workflows w on w.id = v.workflow_id "
                          "where w.workspace_id = %s and w.name = 'Vendor due diligence'", WORKSPACE)
        steps = [node.get('label') for node in labels[0][0] if node.get('block') == 'agent'] if labels else []
        check('a published workflow carries its SD-02 steps', 'Research the vendor, then Compare and recommend', steps,
              steps == ['Research the vendor', 'Compare and recommend'])

        stored = json.dumps(rows(db, 'select v.config from public.experts e join public.expert_versions v on v.expert_id = e.id where e.workspace_id = %s', WORKSPACE)
                            + rows(db, 'select v.graph from public.workflows w join public.workflow_versions v on v.workflow_id = w.id where w.workspace_id = %s', WORKSPACE)
                            + rows(db, 'select graph from public.workflow_drafts where workspace_id = %s', WORKSPACE), default=str)
        source = (ROOT / 'services/agent/src/autobots/operations/concept_seed.py').read_text()
        found = [match.group(0) for text in (stored, source) for match in SECRET.finditer(text)]
        check('neither the seed nor what it stored holds a key, token or password', 'none', found or 'none', not found)
        pending = rows(db, 'select (select count(*) from public.runs where workspace_id = %s), '
                           '(select count(*) from app_private.run_jobs where workspace_id = %s), '
                           '(select count(*) from public.routine_occurrences o join public.routines r on r.id = o.routine_id where r.workspace_id = %s)',
                       WORKSPACE, WORKSPACE, WORKSPACE)[0]
        check('nothing is pending: no run, job or routine occurrence', '0, 0, 0', pending, pending == (0, 0, 0))
    print(json.dumps({'cases': cases}))


main()
