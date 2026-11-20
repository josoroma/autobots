"""US-15.25, US-16.6, US-17.5 and US-18.1: the concept seed on a disposable stack, in a fresh workspace, with no GitHub variables.

Migrations alone must have created none of it. Run twice, it leaves each Expert and workflow once.
It holds no secret, leaves nothing pending, and follows SD-02: the GitHub-only workflows, Interview
synthesis and, with no SerpApi key, Deep research content writer are drafts, and, with no browser executor, so
is Transcript; the rest are published, and Experts are saved without their unavailable tools.

A second workspace, seeded first with only the six earlier Experts and workflows as an install before
US-16.6 was, with the Market watcher and its monthly workflow as they were before US-18.1, then gets
the real seed twice with a SerpApi key: it adds the Deep research writer and publishes its workflow,
adds "Monthly FX note" beside the old monthly workflow, and changes nothing else (Decision 0034 S1,
Decision 0036 R7). The fresh workspace's Market watcher has no inflation_rates. JSON cases out.
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
WORKSPACE, EARLIER = sys.argv[1], sys.argv[2]
ROOT = Path(__file__).resolve().parents[3]
EXPERTS = ['Market watcher', 'Research analyst', 'Brief writer', 'Issue triager', 'Code maintainer', 'Google bot',
           'Deep research writer', 'Transcript reader']
WORKFLOWS = ['Weekly competitor brief', 'Monthly FX note', 'Nightly test triage', 'Interview synthesis',
             'Release notes from merged PRs', 'Vendor due diligence', 'Deep research content writer', 'Transcript']
DRAFTS = {'Nightly test triage', 'Release notes from merged PRs', 'Interview synthesis', 'Deep research content writer', 'Transcript'}
WRITER = 'Deep research writer'
RESEARCH = 'Deep research content writer'
READER, TRANSCRIPT = 'Transcript reader', 'Transcript'
MONTHLY, OLD_MONTHLY = 'Monthly FX note', 'Monthly FX and inflation note'
SECRET = re.compile(r'sk-or-|sk-[A-Za-z0-9]{16,}|eyJ[A-Za-z0-9_-]{10,}|ghp_|github_pat_|Bearer |password\s*[:=]|secret\s*[:=]', re.IGNORECASE)
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:400], 'passed': bool(passed)})


def rows(db: psycopg.Connection, sql: str, *values: Any) -> list[tuple[Any, ...]]:
    return list(db.execute(sql, values).fetchall())


# The seed as it was before US-16.6: only its first six Experts and workflows. Its Market watcher and
# monthly workflow are as they were before US-18.1, when inflation_rates was still a tool, so the old
# seed's save rules are arranged here: the name is known and not dropped (Decision 0036 R7).
EARLIER_SEED = """import sys
from dataclasses import replace
import autobots.application.experts as experts
import autobots.operations.concept_seed as seed
from autobots.domain.tools import EXPERT_TOOLS
experts.EXPERT_TOOLS = {**EXPERT_TOOLS, 'inflation_rates': 1}
experts.drop_retired = lambda config: config
usable = seed.available_tools
seed.available_tools = lambda environ, tools: usable(environ, tools) | {'inflation_rates'}
current = seed.WORKFLOWS[1].graph
def monthly(ids):
    graph = current(ids)
    for node in graph['nodes']:
        if node['id'] == 'in':
            node.pop('label', None)
        if node['id'] == 'pull':
            node['label'] = 'Pull rates and inflation'
    return graph
watcher = replace(seed.EXPERTS[0], purpose='Tracks prices, exchange rates and inflation, and explains what moved and why it matters.',
                  tools=('market_history', 'inflation_rates', *seed.EXPERTS[0].tools[1:]))
old = replace(seed.WORKFLOWS[1], name='Monthly FX and inflation note',
              description='Name the currency pairs and countries. Rates and inflation are pulled into a short note.', graph=monthly)
seed.EXPERTS, seed.WORKFLOWS = (watcher, *seed.EXPERTS[1:6]), (seed.WORKFLOWS[0], old, *seed.WORKFLOWS[2:6])
raise SystemExit(seed.main(sys.argv[1:]))
"""


def run_seed(workspace: str = WORKSPACE, extra: dict[str, str] | None = None, earlier: bool = False) -> dict[str, Any]:
    # Only what the seed needs: no GitHub or provider variable reaches it, unless `extra` names one.
    env = {'PATH': os.environ.get('PATH', ''), 'AUTOBOTS_DATABASE_URL': URL, 'PYTHONPATH': os.environ.get('PYTHONPATH', ''),
           'PYTHONDONTWRITEBYTECODE': '1', **(extra or {})}
    module = ['-c', EARLIER_SEED] if earlier else ['-m', 'autobots.operations.concept_seed']
    done = subprocess.run([sys.executable, *module, '--workspace', workspace],
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
        check('run twice, each Expert and workflow is there once', f'{len(EXPERTS)} Experts and {len(WORKFLOWS)} workflows, once each',
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
        check('with no GitHub or SerpApi variable and no browser executor, the GitHub workflows, Interview synthesis, Deep research '
              'content writer and Transcript are drafts, and the other three are published',
              f'drafts {sorted(DRAFTS)}', (drafts, published), drafts == sorted(DRAFTS) and published == sorted(set(WORKFLOWS) - DRAFTS))
        unavailable = {name: report['unavailable'] for name, report in first['workflows'].items() if isinstance(report, dict) and report.get('draft')}
        check('a draft names the unavailable tools that made it one', 'GitHub tools for the two, none for Interview synthesis', unavailable,
              unavailable.get('Interview synthesis') == [] and all(tool.startswith(('github_', 'create_github')) for tool in
                                                                  unavailable.get('Nightly test triage', []) + unavailable.get('Release notes from merged PRs', []))
              and unavailable.get('Nightly test triage') and unavailable.get('Release notes from merged PRs'))
        check('with no SerpApi variable, Deep research content writer is a draft for want of google_search', "['google_search']",
              unavailable.get(RESEARCH), unavailable.get(RESEARCH) == ['google_search'])
        check('with no browser executor, Transcript is a draft for want of browse_goal', "['browse_goal']",
              unavailable.get(TRANSCRIPT), unavailable.get(TRANSCRIPT) == ['browse_goal'])

        configs = {name: config for name, config in rows(
            db, 'select e.name, v.config from public.experts e join public.expert_versions v on v.expert_id = e.id and v.version = e.latest_version '
                'where e.workspace_id = %s', WORKSPACE)}
        reader = configs.get(READER, {})
        check('with no browser executor, the Transcript reader is saved without browse_goal, says so, and lists no browse domains',
              'save_artifact and publish_artifact, "Saved without browse_goal" in its purpose, no browse domains',
              (reader.get('tools'), 'Saved without browse_goal' in reader.get('purpose', ''), reader.get('browse_domains', [])),
              reader.get('tools') == ['save_artifact', 'publish_artifact'] and 'Saved without browse_goal' in reader.get('purpose', '')
              and not reader.get('browse_domains'))
        github = {name: [tool for tool in configs[name]['tools'] if 'github' in tool] for name in ('Issue triager', 'Code maintainer')}
        said = {name: 'Saved without' in configs[name]['purpose'] and 'github' in configs[name]['purpose'] for name in ('Issue triager', 'Code maintainer')}
        check('Issue triager and Code maintainer are saved without their GitHub tools, and say so in their purpose', 'no GitHub tool, said',
              (github, said), github == {'Issue triager': [], 'Code maintainer': []} and all(said.values()))
        check('the tools that are available are kept', 'Code maintainer keeps its file tools; Market watcher keeps its tools',
              (configs['Code maintainer']['tools'], configs['Market watcher']['tools']),
              {'search_files', 'read_code_file', 'patch_code_file', 'write_code_file'} <= set(configs['Code maintainer']['tools'])
              and {'calculate', 'read_csv', 'save_artifact'} <= set(configs['Market watcher']['tools']))
        # Decision 0023 E7: an Expert that saves can publish, so a workflow step it runs can pass verification.
        publishing = {name: 'publish_artifact' in configs[name]['tools'] for name in ('Market watcher', 'Research analyst', 'Brief writer')}
        check('every concept Expert that saves files can also publish them', 'Market watcher, Research analyst and Brief writer publish',
              publishing, all(publishing.values()))
        # US-14.23, Decision 0033 K8: with no SerpApi variable, Google bot keeps google_extract, which needs no key, and says
        # what it was saved without.
        bot = configs.get('Google bot', {})
        purpose = bot.get('purpose', '')
        check('Google bot keeps google_extract and is saved without google_search, google_map and google_crawl, saying so',
              'google_extract, save_artifact and publish_artifact; purpose names the three missing tools', (bot.get('tools'), purpose),
              bot.get('tools') == ['google_extract', 'save_artifact', 'publish_artifact'] and 'Saved without' in purpose
              and all(tool in purpose for tool in ('google_search', 'google_map', 'google_crawl')))
        # US-16.6, Decision 0034 E1 to E3: with no SerpApi or Jina variable, the Deep research writer keeps the tools that
        # need no key, says what it was saved without, and carries its instructions.
        writer = configs.get(WRITER, {})
        check('the Deep research writer is saved without its keyed search tools, saying so, with its instructions',
              'google_extract, read_artifact, read_run_file, save_artifact and publish_artifact; three named; instructions',
              (writer.get('tools'), writer.get('purpose', '')[-160:], len(writer.get('instructions', ''))),
              writer.get('tools') == ['google_extract', 'read_artifact', 'read_run_file', 'save_artifact', 'publish_artifact']
              and all(tool in writer.get('purpose', '') for tool in ('google_search', 'search_web', 'extract_website_content'))
              and '<outputs>/content.md' in writer.get('instructions', '') and 'read_artifact' in writer.get('instructions', ''))
        labels = rows(db, "select v.graph -> 'nodes' from public.workflow_versions v join public.workflows w on w.id = v.workflow_id "
                          "where w.workspace_id = %s and w.name = 'Vendor due diligence'", WORKSPACE)
        steps = [node.get('label') for node in labels[0][0] if node.get('block') == 'agent'] if labels else []
        check('a published workflow carries its SD-02 steps', 'Research the vendor, then Compare and recommend', steps,
              steps == ['Research the vendor', 'Compare and recommend'])
        # US-18.1, Decision 0036 R7: prices and exchange rates only, and the monthly note under its new name.
        watcher = configs['Market watcher']
        check('the Market watcher tracks prices and exchange rates, without inflation_rates',
              'market_history and no inflation_rates; no inflation in its purpose', (watcher['tools'], watcher['purpose']),
              'market_history' in watcher['tools'] and 'inflation_rates' not in watcher['tools'] and 'inflation' not in watcher['purpose'].lower())
        graph = rows(db, "select v.graph -> 'nodes' from public.workflow_versions v join public.workflows w on w.id = v.workflow_id "
                         "where w.workspace_id = %s and w.name = %s", WORKSPACE, MONTHLY)
        labels = {node['id']: node.get('label') for node in graph[0][0]} if graph else {}
        old = rows(db, 'select count(*) from public.workflows where workspace_id = %s and name = %s', WORKSPACE, OLD_MONTHLY)[0][0]
        check('Monthly FX note is published with a Currency pairs input and a Pull the rates step, and no old monthly workflow exists',
              'Currency pairs, Pull the rates, 0 old', (labels.get('in'), labels.get('pull'), old),
              (labels.get('in'), labels.get('pull'), old) == ('Currency pairs', 'Pull the rates', 0))

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
        earlier_install(db)
    print(json.dumps({'cases': cases}))


def earlier_install(db: psycopg.Connection) -> None:
    """US-16.6: an install seeded before the Deep research writer existed gets it, and its workflow published once a
    SerpApi key is set (Decision 0034 S1, F2). Everything that was there stays as it was."""
    run_seed(EARLIER, earlier=True)
    snapshot = 'select e.name, e.latest_version, v.config from public.experts e join public.expert_versions v on v.expert_id = e.id ' \
               'where e.workspace_id = %s order by e.name, v.version'
    before = rows(db, snapshot, EARLIER)
    flows_before = rows(db, 'select name, latest_version from public.workflows where workspace_id = %s order by name', EARLIER)
    check('the arranged install has the six earlier Experts and workflows, without the newer ones', '6 and 6, none new',
          ([name for name, _, _ in before], [name for name, _ in flows_before]),
          len(before) == 6 and len(flows_before) == 6 and WRITER not in [name for name, _, _ in before])
    watcher = next((config for name, _, config in before if name == 'Market watcher'), {})
    check('the arranged install has the Market watcher with inflation_rates and the old monthly workflow, as seeded before US-18.1',
          f'inflation_rates granted, {OLD_MONTHLY} present', (watcher.get('tools'), [name for name, _ in flows_before]),
          'inflation_rates' in watcher.get('tools', []) and OLD_MONTHLY in [name for name, _ in flows_before]
          and MONTHLY not in [name for name, _ in flows_before])
    serpapi = {'SERPAPI_API_KEY': 'fake-serpapi-key-for-the-seed-check'}
    first, second = run_seed(EARLIER, serpapi), run_seed(EARLIER, serpapi)
    created = sorted(name for group in ('experts', 'workflows') for name, report in first[group].items() if report != 'kept')
    check('the first run adds only the Deep research writer, the Transcript reader, their workflows and Monthly FX note',
          f'{sorted([WRITER, RESEARCH, READER, TRANSCRIPT, MONTHLY])}', created,
          created == sorted([WRITER, RESEARCH, READER, TRANSCRIPT, MONTHLY]) and first['workflows'][RESEARCH] == {'published': 1}
          and first['workflows'][MONTHLY] == {'published': 1})
    after = [row for row in rows(db, snapshot, EARLIER) if row[0] not in (WRITER, READER)]
    flows_after = [row for row in rows(db, 'select name, latest_version from public.workflows where workspace_id = %s order by name', EARLIER)
                   if row[0] not in (RESEARCH, TRANSCRIPT, MONTHLY)]
    check('everything that existed is unchanged, the Market watcher with inflation_rates and the old monthly workflow included',
          'the same versions and configurations', 'same' if (after, flows_after) == (before, flows_before) else 'changed',
          (after, flows_after) == (before, flows_before))
    added = rows(db, 'select v.config from public.experts e join public.expert_versions v on v.expert_id = e.id where e.workspace_id = %s and e.name = %s',
                 EARLIER, WRITER)
    tools = added[0][0].get('tools') if added else None
    check('with a SerpApi key the Deep research writer is granted google_search, and not the Jina tools whose key is absent',
          'google_search, google_extract, read_artifact, read_run_file, save_artifact, publish_artifact', tools,
          tools == ['google_search', 'google_extract', 'read_artifact', 'read_run_file', 'save_artifact', 'publish_artifact'])
    flow = rows(db, "select w.latest_version, exists (select 1 from public.workflow_drafts d where d.workflow_id = w.id), "
                    "(select v.graph from public.workflow_versions v where v.workflow_id = w.id and v.version = 1) "
                    "from public.workflows w where w.workspace_id = %s and w.name = %s", EARLIER, RESEARCH)
    steps = [node.get('label') for node in flow[0][2]['nodes'] if node.get('block') == 'agent'] if flow and flow[0][2] else []
    check('the Deep research content writer is published with its two steps', 'version 1, no draft, Research and write, then Check and report',
          (flow[0][:2] if flow else None, steps), bool(flow) and flow[0][0] == 1 and not flow[0][1] and steps == ['Research and write', 'Check and report'])
    kept = set(second['experts'].values()) | set(second['workflows'].values())
    check('the second run adds nothing', 'all kept', kept, kept == {'kept'})


main()
