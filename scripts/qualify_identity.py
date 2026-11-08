#!/usr/bin/env python3
"""Real local Auth, membership, PostgREST and Storage on a disposable pinned stack, with nonprivileged identities.

Creates a new project with generated secrets, migrates it, bootstraps two owners through the Auth
admin API, then drives real sign-in, the Python API, the BFF and each exposed service. It removes
only that project. No model is called, and nothing persistent is touched.

Exit codes: 0 passed, 1 a case failed, 2 prerequisite unavailable.
OpenRouter itself is a local fake that logs each request, and it holds no real credential.
Passing establishes neither H1 nor product acceptance.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from urllib import error, request

from app_db import AppStack, apply_migrations, bootstrap, seed
from disposable_db import (PROJECT_PREFIX, Cases, Refused, Target, Unavailable, free_port, other_resources,
                           remove_stack, require_identity, rows, run, tool_env)
from harness_lib import fingerprint, project_root
from qualify_web import BROWSERS, run_problems, start, stop, summarize, wait_until_up
from supabase_stack import generated_values, require_images, require_rendered
from toolchain import child_env, find_tools

REPORT = Path('.checks/identity/qualification.json')
STORAGE_SQL = Path('supabase/bootstrap/storage.sql')
BUCKET = 'workspace-artifacts'
PYTHON = Path('services/agent/.venv/bin/python')


def http(method: str, url: str, headers: Mapping[str, str] | None = None, body: bytes | None = None) -> tuple[int, str]:
    try:
        with request.urlopen(request.Request(url, data=body, method=method, headers=dict(headers or {})), timeout=20) as reply:
            return reply.status, reply.read().decode(errors='replace')
    except error.HTTPError as failure:
        return failure.code, failure.read().decode(errors='replace')


def denied(status: int) -> bool:
    return 400 <= status < 500


def bootstrap_owner(root: Path, base: str, service_key: str, database_url: str, email: str, password: str) -> dict:
    result = subprocess.run([str(root / PYTHON), '-m', 'autobots.operations.bootstrap_owner', '--email', email, '--workspace-name', email],
                            env={**tool_env(), 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1',
                                 'AUTOBOTS_SUPABASE_URL': base, 'AUTOBOTS_SERVICE_ROLE_KEY': service_key,
                                 'AUTOBOTS_OWNER_PASSWORD': password, 'AUTOBOTS_DATABASE_URL': database_url},
                            capture_output=True, text=True, timeout=60, check=False)
    if result.returncode:
        raise Unavailable(f'owner bootstrap failed: {result.stderr.strip()[-200:]}')
    return json.loads(result.stdout)


def password_token(base: str, anon: str, email: str, password: str) -> tuple[int, str]:
    status, body = http('POST', f'{base}/auth/v1/token?grant_type=password', {'apikey': anon, 'Content-Type': 'application/json'},
                        json.dumps({'email': email, 'password': password}).encode())
    return status, json.loads(body).get('access_token', '') if status == 200 else ''


def auth_cases(cases: Cases, base: str, anon: str, email: str, password: str) -> None:
    status, _ = http('POST', f'{base}/auth/v1/signup', {'apikey': anon, 'Content-Type': 'application/json'},
                     json.dumps({'email': 'stranger@example.invalid', 'password': secrets.token_hex(16)}).encode())
    cases.check('public signup is refused', 'a 4xx refusal', str(status), denied(status))
    status, _ = password_token(base, anon, email, 'not-the-password')
    cases.check('a wrong password gets no token', 'a 4xx refusal', str(status), denied(status))


def rest_cases(cases: Cases, stack: AppStack, base: str, anon: str, token_a: str, token_b: str, run_a: str) -> None:
    def rest(path: str, token: str | None = None, method: str = 'GET', extra: Mapping[str, str] | None = None, body: bytes | None = None) -> tuple[int, str]:
        headers = {'apikey': anon, **({'Authorization': f'Bearer {token}'} if token else {}), **(extra or {})}
        return http(method, f'{base}/rest/v1/{path}', headers, body)
    status, body = rest(f'runs?select=id&id=eq.{run_a}', token_a)
    cases.check('a member reads its run through PostgREST', 'one row', f'{status} {body[:70]}', status == 200 and run_a in body)
    status, body = rest(f'runs?select=id&id=eq.{run_a}', token_b)
    cases.check('another workspace reads no run through PostgREST', 'no rows', f'{status} {body[:40]}', status == 200 and json.loads(body) == [])
    status, _ = rest('runs?select=id')
    cases.check('anonymous is refused on runs', 'a 4xx refusal', str(status), denied(status))
    status, _ = rest('runs?select=id', f'{token_a[:-4]}AAAA')
    cases.check('a forged token is refused on runs', 'a 4xx refusal', str(status), denied(status))
    status, _ = rest('runs?select=lease_generation', token_a)
    cases.check('lease columns are refused', 'a 4xx refusal', str(status), denied(status))
    status, _ = rest('runs', token_a, 'POST', {'Content-Type': 'application/json'}, b'{"limit_micro_usd": 1}')
    cases.check('a member cannot write runs through PostgREST', 'a 4xx refusal', str(status), denied(status))
    stack.migrator('create table app_private.canary (id int);\ncreate table agent_runtime.canary (id int);\n')
    for schema in ('app_private', 'agent_runtime'):
        status, _ = rest('canary', token_a, extra={'Accept-Profile': schema})
        cases.check(f'{schema} is not an exposed PostgREST schema', 'refused', str(status), denied(status))
    status, _ = rest('canary', token_a)
    cases.check('a private table is absent from the public schema', 'a 4xx refusal', str(status), denied(status))
    status, body = http('GET', f'{base}/rest/v1/', {'apikey': stack.values['SERVICE_ROLE_KEY'], 'Authorization': f"Bearer {stack.values['SERVICE_ROLE_KEY']}"})
    listed = status == 200 and ('canary' in body or 'app_private' in body or 'agent_runtime' in body)
    cases.check('private schemas are absent from the PostgREST description', 'absent', f'{status}, listed {listed}', status == 200 and not listed)
    published = rows(stack, "select count(*) from pg_publication_tables where schemaname in ('app_private', 'agent_runtime');")
    cases.check('private schemas are in no Realtime publication', '0 tables', published, published == '0')
    grants = rows(stack, "select count(*) from information_schema.role_usage_grants where false;")
    cases.check('authenticated holds no usage on private schemas', 'none',
                rows(stack, "select has_schema_privilege('authenticated', 'app_private', 'usage')::text || ',' || has_schema_privilege('anon', 'agent_runtime', 'usage')::text;"),
                grants == '0' and rows(stack, "select has_schema_privilege('authenticated', 'app_private', 'usage') or has_schema_privilege('anon', 'agent_runtime', 'usage');") == 'f')


def storage_cases(cases: Cases, base: str, anon: str, token_a: str, token_b: str, workspace_a: str, workspace_b: str) -> None:
    def storage(method: str, path: str, token: str | None, body: bytes | None = None, kind: str = 'text/plain') -> tuple[int, str]:
        headers = {'apikey': anon, **({'Authorization': f'Bearer {token}'} if token else {}), **({'Content-Type': kind} if body is not None else {})}
        return http(method, f'{base}/storage/v1/{path}', headers, body)
    target = f'{BUCKET}/{workspace_a}/note.txt'
    status, _ = storage('POST', f'object/{target}', token_a, b'artifact bytes')
    cases.check('a member uploads to its workspace', '200', str(status), status == 200)
    status, body = storage('GET', f'object/authenticated/{target}', token_a)
    cases.check('a member reads its object', '200 and the bytes', f'{status}', status == 200 and body == 'artifact bytes')
    for label, token in (('another workspace', token_b), ('anonymous', None), ('a forged token', f'{token_a[:-4]}AAAA')):
        status, body = storage('GET', f'object/authenticated/{target}', token)
        cases.check(f'{label} cannot read the object', 'a 4xx refusal', str(status), denied(status) and 'artifact bytes' not in body)
    status, _ = storage('POST', f'object/{BUCKET}/{workspace_a}/intruder.txt', token_b, b'x')
    cases.check('another workspace cannot upload there', 'a 4xx refusal', str(status), denied(status))
    status, _ = storage('POST', f'object/{BUCKET}/not-a-uuid/x.txt', token_a, b'x')
    cases.check('an unscoped path is refused', 'a 4xx refusal', str(status), denied(status))
    status, _ = storage('POST', f'object/{BUCKET}/{workspace_b}/x.txt', token_a, b'x')
    cases.check('a member cannot upload to another workspace', 'a 4xx refusal', str(status), denied(status))
    listing = json.dumps({'prefix': workspace_a}).encode()
    status, body = storage('POST', f'object/list/{BUCKET}', token_b, listing, 'application/json')
    cases.check('another workspace lists nothing', 'no objects', f'{status} {body[:40]}', status == 200 and 'note.txt' not in body)
    status, body = storage('POST', f'object/list/{BUCKET}', token_a, listing, 'application/json')
    cases.check('a member lists its object', 'the object', f'{status}', status == 200 and 'note.txt' in body)
    storage('DELETE', f'object/{target}', token_b)
    status, body = storage('GET', f'object/authenticated/{target}', token_a)
    cases.check('another workspace cannot delete the object', 'still readable', str(status), status == 200 and body == 'artifact bytes')
    status, _ = storage('GET', f'object/public/{target}', None)
    cases.check('the bucket has no public read', 'a 4xx refusal', str(status), denied(status))


def artifact_cases(root: Path, cases: Cases, stack: AppStack, base: str, db_port: int, anon: str, token_a: str, token_b: str,
                   workspace_a: str, workspace_b: str) -> dict[str, str]:
    """Publication and recovery against real Storage, through the runtime role."""
    url = f'postgresql://autobots_runtime:{stack.runtime_password}@127.0.0.1:{db_port}/postgres'
    result = subprocess.run([str(root / PYTHON), str(root / 'tests/db/artifact_check.py'), workspace_a, workspace_b],
                            env={**tool_env(), 'AUTOBOTS_DATABASE_URL': url, 'AUTOBOTS_STORAGE_BASE': base, 'AUTOBOTS_STORAGE_ANON': anon,
                                 'AUTOBOTS_STORAGE_SERVICE': stack.values['SERVICE_ROLE_KEY'], 'AUTOBOTS_TOKEN_A': token_a, 'AUTOBOTS_TOKEN_B': token_b,
                                 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1'},
                            capture_output=True, text=True, errors='replace', timeout=240, check=False)
    if result.returncode:
        cases.check('the artifact check ran', 'exit 0', f'exit {result.returncode}: {result.stderr.strip()[-380:]}', False)
    if not result.stdout.strip():
        return {}
    report = json.loads(result.stdout.strip().splitlines()[-1])
    for case in report['cases']:
        cases.check(case['id'], case['expected'], case['observed'], case['passed'])
    extra_env: dict[str, str] = {}
    for check_file, arguments, label in (('verification_check.py', [workspace_a], 'verification'),
                                         ('assignment_check.py', [workspace_a, str(root / PYTHON)], 'assignment'),
                                         ('approval_check.py', [workspace_a, workspace_b], 'approval'),
                                         ('effect_check.py', [workspace_a, workspace_b, str(root / PYTHON)], 'effect'),
                                         ('workflow_run_check.py', [workspace_a, str(root / PYTHON)], 'workflow run'),
                                         ('blocker_check.py', [workspace_a], 'blocker'),
                                         ('major_check.py', [workspace_a, workspace_b], 'major'),
                                         ('connector_check.py', [workspace_a], 'connector'),
                                         ('wake_check.py', [workspace_a], 'wake'),
                                         ('review_check.py', [workspace_a], 'review'),
                                         ('improvement_check.py', [workspace_a, workspace_b], 'improvement'),
                                         ('provider_key_check.py', [workspace_a], 'provider key'),
                                         # Last, so no later check's cleanup ends the run it leaves claimed for the browser.
                                         ('tool_use_view_check.py', [workspace_a], 'tool-use view')):
        checked = subprocess.run([str(root / PYTHON), str(root / 'tests/db' / check_file), *arguments],
                                 env={**tool_env(), 'AUTOBOTS_DATABASE_URL': url, 'AUTOBOTS_STORAGE_BASE': base, 'AUTOBOTS_STORAGE_SERVICE': stack.values['SERVICE_ROLE_KEY'],
                                      'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1'},
                                 capture_output=True, text=True, errors='replace', timeout=240, check=False)
        if checked.returncode:
            (root / '.checks/identity').mkdir(parents=True, exist_ok=True)
            (root / f'.checks/identity/{check_file}.err').write_text(checked.stderr)
            cases.check(f'the {label} check ran', 'exit 0', f'exit {checked.returncode}: {checked.stderr.strip()[-380:]}', False)
        if checked.stdout.strip():
            output = json.loads(checked.stdout.strip().splitlines()[-1])
            extra_env.update(output.get('browser_env', {}))
            for case in output['cases']:
                cases.check(case['id'], case['expected'], case['observed'], case['passed'])
    # US-13.1: an older request, arranged as the migration finds one. Only the superuser bypasses the trigger.
    legacy = extra_env.get('AUTOBOTS_TEST_APPROVAL_LEGACY')
    if legacy:
        cleared = stack.sql("begin;\nset local session_replication_role = replica;\n"
                            "update public.approval_requests set policy_reason = null, resource_target = null, requested_by = null, requested_by_agent = null, "
                            f"scope_snapshot = null, policy_version = null, policy_rule = null where id = '{legacy}';\ncommit;\n")
        cases.check('an older request is arranged with nothing recorded', 'exit 0', f'exit {cleared.returncode}', cleared.returncode == 0)
        for column, filled_in in (('requested_by_agent', '{"kind": "coordinator"}'), ('scope_snapshot', '{"tools": {}, "paths": []}'), ('policy_version', 'approval-policy/1')):
            filled = stack.runtime(f"update public.approval_requests set {column} = '{filled_in}' where id = '{legacy}';\n")
            cases.check(f"an older request's {column} can't be filled in", 'refused as immutable', filled.stderr.strip()[-120:],
                        filled.returncode != 0 and 'immutable' in filled.stderr)
    # Arranged for the run workspace: text a model wrote, a raw framework event, and lost history.
    loop_run, gap_run = report.get('loop_run', ''), report.get('run_id', '')
    arranged = stack.runtime(
        f"insert into app_private.plan_evidence (run_id, task_id, evidence, summary) values ('{loop_run}', 'a', '[]', 'used sk-or-leaked-value-here');\n"
        f"update public.runs set event_sequence = event_sequence + 1 where id = '{loop_run}';\n"
        f"insert into public.run_events (run_id, sequence, schema_version, payload, occurred_at) select '{loop_run}', event_sequence, 1, "
        f"""'{{"type": "model.reasoning", "text": "PROTECTED-REASONING"}}', now() from public.runs where id = '{loop_run}';\n"""
        f"delete from public.run_events where run_id = '{gap_run}' and sequence < 3;\n")
    cases.check('the run workspace fixtures are arranged', 'exit 0', f'exit {arranged.returncode}: {arranged.stderr[-200:]}', arranged.returncode == 0)
    return {**extra_env, 'AUTOBOTS_TEST_LOOP_RUN': loop_run, 'AUTOBOTS_TEST_ARTIFACT_RUN': report.get('run_id', ''), 'AUTOBOTS_TEST_ARTIFACT_ID': report.get('artifact_id', ''),
            'AUTOBOTS_TEST_ARTIFACT_TEXT': report.get('expected_text', ''), 'AUTOBOTS_TEST_ARTIFACT_GONE': report.get('gone_id', ''),
            'AUTOBOTS_TEST_ARTIFACT_TAMPERED': report.get('tampered_id', '')}


def browser_cases(root: Path, cases: Cases, stack: AppStack, base: str, db_port: int, email: str, password: str,
                  workspace_a: str, workspace_b: str, email_b: str, password_b: str, email_c: str, password_c: str,
                  artifacts: Mapping[str, str]) -> None:
    tools = find_tools(root)
    web = root / 'apps/web'
    next_bin, playwright = web / 'node_modules/.bin/next', web / 'node_modules/.bin/playwright'
    browsers = root / BROWSERS
    if not any(browsers.glob('chromium-*')):
        raise Unavailable(f'no browser under {BROWSERS}; install the pinned one deliberately')
    env = {**child_env(root, tools, verifying=True), 'PLAYWRIGHT_BROWSERS_PATH': str(browsers)}
    built = subprocess.run([str(next_bin), 'build'], env=env, cwd=web, capture_output=True, text=True, errors='replace', timeout=300, check=False)
    cases.check('the web app builds', 'exit 0', f'exit {built.returncode}', built.returncode == 0)
    if built.returncode:
        print(built.stdout[-1200:], file=sys.stderr)
        return
    from qualify_web import free_port as any_port
    internal = secrets.token_hex(32)
    api_port, web_port = any_port(), any_port()
    config_root = Path(tempfile.mkdtemp(prefix='autobots-config-'))
    # The arranged installation key. Only workspace B is granted it, so A exercises the app store.
    (config_root / '.env.local').write_text('OPENROUTER_API_KEY=sk-or-valid-arranged-installation\\n')
    stack.sql(f"insert into app_private.installation_credential_grants values ('{workspace_b}');\\n")
    upstream_log = root / '.checks/identity/upstream.log'
    upstream_log.parent.mkdir(parents=True, exist_ok=True)
    upstream_log.write_text('')
    catalog_down = config_root / 'catalog-down'
    backups = config_root / 'backups'
    backups.mkdir(parents=True, exist_ok=True)
    # Arranged: a delayed occurrence, on a routine that's off so no worker evaluates it.
    routine = '44444444-4444-4444-8444-444444444444'
    arranged = stack.sql(f"insert into public.routines (id, workspace_id, name, enabled, evaluated_until) values ('{routine}', '{workspace_a}', 'Arranged nightly report', false, now());\n"
                         f"insert into public.routine_versions (routine_id, version, config, created_by) values ('{routine}', 1, '{{}}', '{workspace_a}');\n"
                         f"insert into public.routine_occurrences (routine_id, occurrence_time, routine_version, status, reason) values ('{routine}', '2026-11-05T03:00:00Z', 1, 'missed', 'host_away');\n")
    cases.check('the delayed occurrence is arranged', 'exit 0', f'exit {arranged.returncode}', arranged.returncode == 0)
    api_url, web_url = f'http://127.0.0.1:{api_port}', f'http://127.0.0.1:{web_port}'
    runtime_url = f'postgresql://autobots_runtime:{stack.runtime_password}@127.0.0.1:{db_port}/postgres'
    api_env = {**tool_env(), 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1', 'AUTOBOTS_INTERNAL_TOKEN': internal,
               'AUTOBOTS_JWT_SECRET': stack.values['JWT_SECRET'], 'AUTOBOTS_DATABASE_URL': runtime_url,
               'AUTOBOTS_SUPABASE_URL': base, 'AUTOBOTS_SERVICE_ROLE_KEY': stack.values['SERVICE_ROLE_KEY'], 'AUTOBOTS_STREAM_SECONDS': '4',
               'AUTOBOTS_CONFIG_ROOT': str(config_root), 'AUTOBOTS_PROVIDER_MASTER_KEY_FILE': str(config_root / 'secrets/master.key'),
               'AUTOBOTS_TEST_UPSTREAM_LOG': str(upstream_log), 'AUTOBOTS_TEST_CATALOG_DOWN': str(catalog_down), 'AUTOBOTS_BACKUP_DIR': str(backups), 'NODE_ENV': 'production'}
    web_env = {**env, 'AUTOBOTS_INTERNAL_TOKEN': internal, 'AUTOBOTS_API_URL': api_url, 'AUTOBOTS_ALLOWED_ORIGIN': web_url, 'NODE_ENV': 'production',
               'AUTOBOTS_SUPABASE_URL': base, 'AUTOBOTS_SUPABASE_ANON_KEY': stack.values['ANON_KEY']}
    screenshots = root / '.checks/identity/screenshots'
    screenshots.mkdir(parents=True, exist_ok=True)
    report = root / '.checks/identity/playwright.json'
    report.unlink(missing_ok=True)
    processes = []
    try:
        processes.append(start([str(root / PYTHON), str(root / 'tests/web/fixture_upstream_api.py'), str(api_port)], api_env, root))
        processes.append(start([str(next_bin), 'start', '-H', '127.0.0.1', '-p', str(web_port)], web_env, web))
        wait_until_up(f'{api_url}/v1/health', processes[0])
        wait_until_up(web_url, processes[1])
        browser_env = {**env, **artifacts, 'AUTOBOTS_WEB_URL': web_url, 'AUTOBOTS_TEST_OWNER_EMAIL': email, 'AUTOBOTS_TEST_OWNER_PASSWORD': password,
                                     'AUTOBOTS_TEST_WORKSPACE_A': workspace_a, 'AUTOBOTS_TEST_WORKSPACE_B': workspace_b,
                                     'AUTOBOTS_TEST_OWNER_B_EMAIL': email_b, 'AUTOBOTS_TEST_OWNER_B_PASSWORD': password_b,
                                     'AUTOBOTS_TEST_MEMBER_EMAIL': email_c, 'AUTOBOTS_TEST_MEMBER_PASSWORD': password_c,
                                     'AUTOBOTS_TEST_UPSTREAM_LOG': str(upstream_log), 'AUTOBOTS_TEST_CATALOG_DOWN': str(catalog_down), 'AUTOBOTS_TEST_BACKUP_DIR': str(backups),
                                     'AUTOBOTS_TEST_SERVICE_KEY': stack.values['SERVICE_ROLE_KEY'], 'AUTOBOTS_WEB_REPORT': str(report),
                                     'AUTOBOTS_WEB_OUTPUT': str(root / '.checks/identity/results'), 'AUTOBOTS_WEB_SCREENSHOTS': str(screenshots),
                                     'AUTOBOTS_TEST_VISUAL_DIR': str(root / '.checks/identity/visual')}
        result = subprocess.run([str(playwright), 'test', 'browser/workflows.spec', 'browser/operations', 'approvals', 'effects', 'experts', 'models', 'identity', 'settings', 'runs', 'artifacts', 'run-workspace', '--config', 'playwright.config.ts'], cwd=web, capture_output=True, text=True, errors='replace', timeout=240, check=False,
                                env=browser_env)
        # A real restart, then Settings reads the stored records. Then one is removed, under the same key.
        stop(processes[0])
        processes[0] = start([str(root / PYTHON), str(root / 'tests/web/fixture_upstream_api.py'), str(api_port)], api_env, root)
        wait_until_up(f'{api_url}/v1/health', processes[0])
        qualification_reports = [root / '.checks/identity/playwright-qualification-1.json', root / '.checks/identity/playwright-qualification-2.json']
        qualification_codes = []
        for report_path, title in zip(qualification_reports, ('after an API restart', 'a route with no record')):
            report_path.unlink(missing_ok=True)
            if title == 'a route with no record':
                stack.sql("create table public.arranged_route_rows as select * from agent_runtime.route_qualifications;\ndelete from agent_runtime.route_qualifications where profile = 'openrouter_terra';\n")
            ran = subprocess.run([str(playwright), 'test', 'browser/qualification', '-g', title, '--config', 'playwright.config.ts'], cwd=web, capture_output=True, text=True, errors='replace', timeout=120, check=False,
                                 env={**browser_env, 'AUTOBOTS_WEB_REPORT': str(report_path)})
            qualification_codes.append(ran.returncode)
            if ran.returncode:
                print(ran.stdout[-1500:], file=sys.stderr)
        stack.sql("delete from agent_runtime.route_qualifications;\ninsert into agent_runtime.route_qualifications select * from public.arranged_route_rows;\ndrop table public.arranged_route_rows;\n")
        # A saved choice naming DeepSeek can't be made through the product now, so each is arranged.
        saved_choices = (('a saved default naming DeepSeek', "default_profile = 'openrouter_deepseek_flash', role_overrides = '{}'"),
                         ('a saved override on another role', "default_profile = 'openrouter_terra', role_overrides = '{\"coder\": \"openrouter_deepseek_flash\"}'"),
                         ('a saved executor override', "default_profile = 'openrouter_terra', role_overrides = '{\"executor\": \"openrouter_deepseek_flash\"}'"),
                         ('a saved Expert binding', "default_profile = 'openrouter_terra', role_overrides = '{}'"))
        for index, (title, setting) in enumerate(saved_choices, start=1):
            report_path = root / f'.checks/identity/playwright-saved-choice-{index}.json'
            report_path.unlink(missing_ok=True)
            qualification_reports.append(report_path)
            arranged = stack.runtime(f"update app_private.model_policies set version = version + 1, {setting} where workspace_id = '{workspace_a}';\n")
            cases.check(f'the saved choice is arranged: {title}', 'exit 0', f'exit {arranged.returncode}', arranged.returncode == 0)
            ran = subprocess.run([str(playwright), 'test', 'browser/saved-choice', '-g', title, '--config', 'playwright.config.ts'], cwd=web, capture_output=True, text=True, errors='replace', timeout=120, check=False,
                                 env={**browser_env, 'AUTOBOTS_WEB_REPORT': str(report_path)})
            qualification_codes.append(ran.returncode)
            if ran.returncode:
                print(ran.stdout[-1500:], file=sys.stderr)
        # US-15.3: readiness as a member. First with no worker heartbeat, then with an arranged one
        # dated ahead, so it stays fresh for the whole run, and removed afterwards.
        for index, title in enumerate(("names the service that isn't ready", 'all local services ready'), start=1):
            report_path = root / f'.checks/identity/playwright-readiness-{index}.json'
            report_path.unlink(missing_ok=True)
            qualification_reports.append(report_path)
            if index == 2:
                stack.runtime("insert into app_private.worker_heartbeats (worker_id, state, claims_inference, beat_at) "
                              "values ('arranged-readiness', 'running', true, clock_timestamp() + interval '15 minutes');\n")
            ran = subprocess.run([str(playwright), 'test', 'browser/readiness', '-g', title, '--config', 'playwright.config.ts'], cwd=web, capture_output=True, text=True, errors='replace', timeout=180, check=False,
                                 env={**browser_env, 'AUTOBOTS_WEB_REPORT': str(report_path)})
            qualification_codes.append(ran.returncode)
            if ran.returncode:
                print(ran.stdout[-1500:], file=sys.stderr)
        stack.runtime("delete from app_private.worker_heartbeats where worker_id = 'arranged-readiness';\n")
        # The slice runs last, with a worker, so nothing above sees its jobs claimed.
        stack.runtime("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done';\n")
        # Arranged: the settings suite changed the workspace default, and the fixture worker's route is the original.
        stack.runtime("update app_private.model_policies set default_profile = 'openrouter_terra', role_overrides = '{}';\n")
        slice_report = root / '.checks/identity/playwright-slice.json'
        slice_report.unlink(missing_ok=True)
        worker_env = {**tool_env(), 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1', 'AUTOBOTS_DATABASE_URL': runtime_url,
                      'AUTOBOTS_STORAGE_BASE': base, 'AUTOBOTS_STORAGE_SERVICE': stack.values['SERVICE_ROLE_KEY'],
                      'AUTOBOTS_TEST_DIED_MARKER': str(config_root / 'worker-died')}
        processes.append(start([str(root / PYTHON), str(root / 'tests/web/fixture_worker.py')], worker_env, root))
        slice_result = subprocess.run([str(playwright), 'test', 'slice', '--config', 'playwright.config.ts'], cwd=web, capture_output=True, text=True, errors='replace', timeout=900, check=False,
                                      env={**browser_env, 'AUTOBOTS_WEB_REPORT': str(slice_report)})
        if slice_result.returncode:
            print(slice_result.stdout[-2500:], file=sys.stderr)
    finally:
        for process in processes:
            stop(process)
    if not report.exists():
        print(result.stdout[-1500:], result.stderr[-800:], file=sys.stderr)
        raise Unavailable('the browser suite produced no report')
    if result.returncode:
        print(result.stdout[-2500:], file=sys.stderr)
    found, _ = summarize(report)
    if slice_report.exists():
        found.extend(summarize(slice_report)[0])
    else:
        cases.check('the slice suite produced a report', 'a report', 'none', False)
    for report_path in qualification_reports:
        if report_path.exists():
            found.extend(summarize(report_path)[0])
        else:
            cases.check('the qualification suite produced a report', 'a report', 'none', False)
    for case in found:
        cases.check(f"browser: {case['id']}", 'passed', case['status'], case['status'] == 'passed')
    runs = [('main suite', report, result.returncode), ('slice suite', slice_report, slice_result.returncode),
            *((f'qualification suite {index + 1}', path, code) for index, (path, code) in enumerate(zip(qualification_reports, qualification_codes)))]
    for label, path, code in runs:
        problems = run_problems(path, code)
        cases.check(f'the {label} ran to a clean exit', 'exit 0, with tests', ', '.join(problems) or 'exit 0', not problems)
    calls = sorted(set(upstream_log.read_text().splitlines()))
    cases.check('only key metadata and the catalog reached the fake upstream', 'GET /key and GET /models only', ', '.join(calls),
                calls == ['GET /api/v1/key', 'GET /api/v1/models'])
    row = rows(stack, f"select count(*) filter (where position('sk-or'::bytea in ciphertext) > 0) from app_private.provider_credentials where workspace_id = '{workspace_a}';")
    versions = rows(stack, f"select count(*) from app_private.provider_credentials where workspace_id = '{workspace_a}';")
    cases.check('stored rows hold no plaintext key', '0 of the rows', f'{row} of {versions}', row == '0' and versions != '0')
    shutil.rmtree(config_root, ignore_errors=True)


def qualify(root: Path) -> int:
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    gateway_port = free_port()
    db_port = free_port([gateway_port])
    target = Target(project, db_port, gateway_port)
    stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=generated_values(gateway_port, db_port))
    stack.migrator_password, stack.runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    require_identity(target, tool_env())
    if run(['docker', 'info', '--format', '{{.ServerVersion}}'], tool_env(), 30).returncode:
        raise Unavailable('the Docker engine is not reachable')
    (root / REPORT).unlink(missing_ok=True)
    rendered = require_rendered(stack)
    require_images(rendered)
    cases = Cases(model_transport='mock')
    before = other_resources(project)
    started_at = time.monotonic()
    base = f'http://127.0.0.1:{gateway_port}'
    anon = stack.values['ANON_KEY']
    email_a, email_b = 'owner-a@example.invalid', 'owner-b@example.invalid'
    password_a, password_b = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    try:
        started = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
        if started.returncode:
            raise Unavailable(f'the stack did not start: {started.stderr[-300:]}')
        bootstrap(stack, root)
        applied, problem = apply_migrations(stack, root / 'supabase/migrations')
        if problem or seed(stack, root).returncode:
            raise Unavailable(f'migrations failed: {problem}')
        stored = stack.sql((root / STORAGE_SQL).read_text())
        cases.check('Storage policies apply', 'exit 0', f'{applied} migrations, exit {stored.returncode}', stored.returncode == 0)
        if stored.returncode:
            print(stored.stderr[-500:], file=sys.stderr)
        runtime_url = f'postgresql://autobots_runtime:{stack.runtime_password}@127.0.0.1:{db_port}/postgres'
        owner_a = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], runtime_url, email_a, password_a)
        owner_b = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], runtime_url, email_b, password_b)
        cases.check('owners are bootstrapped through the Auth admin API', 'two users', f'{bool(owner_a)}, {bool(owner_b)}', owner_a != owner_b)
        auth_cases(cases, base, anon, email_a, password_a)
        status_a, token_a = password_token(base, anon, email_a, password_a)
        status_b, token_b = password_token(base, anon, email_b, password_b)
        cases.check('owners sign in with a local password', '200 each', f'{status_a}, {status_b}', status_a == status_b == 200)
        run_a = '11111111-1111-4111-8111-111111111111'
        stack.runtime(f"insert into public.runs (id, workspace_id, limit_micro_usd) values ('{run_a}', '{owner_a['workspace_id']}', 1);\n")
        rest_cases(cases, stack, base, anon, token_a, token_b, run_a)
        storage_cases(cases, base, anon, token_a, token_b, owner_a['workspace_id'], owner_b['workspace_id'])
        artifacts = artifact_cases(root, cases, stack, base, db_port, anon, token_a, token_b, owner_a['workspace_id'], owner_b['workspace_id'])
        email_c, password_c = 'member-c@example.invalid', secrets.token_urlsafe(24)
        owner_c = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], runtime_url, email_c, password_c)
        stack.runtime(f"insert into public.workspace_members (workspace_id, user_id, role) values ('{owner_a['workspace_id']}', '{owner_c['user_id']}', 'member');\\n")
        # Arranged: a run in a workspace with no key at all, since admission would refuse one.
        email_d, password_d = 'owner-d@example.invalid', secrets.token_urlsafe(24)
        owner_d = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], runtime_url, email_d, password_d)
        no_key_run = '33333333-3333-4333-8333-333333333333'
        stack.runtime(f"insert into public.runs (id, workspace_id, limit_micro_usd, goal_summary) values ('{no_key_run}', '{owner_d['workspace_id']}', 1, 'Arranged in a workspace with no key');\n")
        artifacts = {**artifacts, 'AUTOBOTS_TEST_NO_KEY_RUN': no_key_run, 'AUTOBOTS_TEST_NO_KEY_EMAIL': email_d, 'AUTOBOTS_TEST_NO_KEY_PASSWORD': password_d}
        # US-15.3, arranged: a member of workspace A only, who isn't its owner.
        email_f, password_f = 'reader-f@example.invalid', secrets.token_urlsafe(24)
        reader = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], runtime_url, email_f, password_f)
        stack.runtime(f"insert into public.workspace_members (workspace_id, user_id, role) values ('{owner_a['workspace_id']}', '{reader['user_id']}', 'member');\n"
                      f"delete from public.workspace_members where workspace_id = '{reader['workspace_id']}' and user_id = '{reader['user_id']}';\n")
        artifacts = {**artifacts, 'AUTOBOTS_TEST_READER_EMAIL': email_f, 'AUTOBOTS_TEST_READER_PASSWORD': password_f}
        # US-15.4, arranged: an owner whose workspace holds 101 runs, so a second page exists, and three
        # with spend: one reserved, one with an unreported charge and one fully reported.
        email_g, password_g = 'runs-g@example.invalid', secrets.token_urlsafe(24)
        lister = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], runtime_url, email_g, password_g)
        listed = lister['workspace_id']
        spend_runs = ('44444444-4444-4444-8444-000000000001', '44444444-4444-4444-8444-000000000002', '44444444-4444-4444-8444-000000000003')
        stack.runtime(
            "insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, created_at, policy_snapshot) "
            f"select gen_random_uuid(), '{listed}', (array['queued','succeeded','paused','waiting_input'])[1 + n % 4], "
            "'Filler run ' || n, 1000000, now() - make_interval(mins => 200 + n), "
            "'{\"bindings\": {\"executor\": \"openrouter_terra\"}}'::jsonb from generate_series(1, 98) n;\n"
            "insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, created_at, policy_snapshot) values "
            f"('{spend_runs[0]}', '{listed}', 'running', 'Spend held in reserve', 1000000, now() - interval '3 minutes', '{{\"bindings\": {{\"researcher\": \"openrouter_sol\"}}}}'), "
            f"('{spend_runs[1]}', '{listed}', 'failed', 'Spend never reported', 1000000, now() - interval '2 minutes', '{{}}'), "
            f"('{spend_runs[2]}', '{listed}', 'succeeded', 'Spend fully reported', 1000000, now() - interval '1 minute', '{{}}');\n"
            "insert into app_private.model_invocations (id, workspace_id, root_run_id, run_id, role, profile, wire_id, attempt, spend_day, "
            "reserved_micro_usd, charged_micro_usd, status, failure_class) values "
            f"(gen_random_uuid(), '{listed}', '{spend_runs[0]}', '{spend_runs[0]}', 'executor', 'openrouter_terra', 'w', 1, current_date, 180000, null, 'reserved', null), "
            f"(gen_random_uuid(), '{listed}', '{spend_runs[1]}', '{spend_runs[1]}', 'executor', 'openrouter_terra', 'w', 1, current_date, 30000, null, 'uncertain', 'charge_not_reported'), "
            f"(gen_random_uuid(), '{listed}', '{spend_runs[2]}', '{spend_runs[2]}', 'executor', 'openrouter_terra', 'w', 1, current_date, 0, 70000, 'succeeded', null);\n")
        artifacts = {**artifacts, 'AUTOBOTS_TEST_RUNS_EMAIL': email_g, 'AUTOBOTS_TEST_RUNS_PASSWORD': password_g}
        # US-15.6, arranged by SQL, as a grant naming an unconfigured connector is refused at save:
        # three Experts with known tools, one with three runs.
        email_h, password_h = 'experts-h@example.invalid', secrets.token_urlsafe(24)
        curator = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], runtime_url, email_h, password_h)
        curated = curator['workspace_id']
        expert_rows = (('55555555-5555-4555-8555-000000000001', 'Market watcher',
                        '{"tools": ["market_history", "inflation_rates", "calculate", "read_csv", "save_artifact", "read_run_file"], "role_bindings": {"executor": "openrouter_terra"}}'),
                       ('55555555-5555-4555-8555-000000000002', 'Issue triager', '{"tools": ["read_csv", "create_github_issue"]}'),
                       ('55555555-5555-4555-8555-000000000003', 'Brief writer', '{"tools": ["save_artifact"]}'))
        stack.runtime(''.join(
            f"insert into public.experts (id, workspace_id, name, latest_version) values ('{identifier}', '{curated}', '{name}', 1);\n"
            f"insert into public.expert_versions (expert_id, version, config, created_by) values ('{identifier}', 1, '{config}', '{curator['user_id']}');\n"
            for identifier, name, config in expert_rows)
            + "insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, expert_id, created_at) "
              f"select gen_random_uuid(), '{curated}', 'succeeded', 'Watch ' || n, 1000000, '{expert_rows[0][0]}', now() - make_interval(mins => 10 * n) "
              "from generate_series(1, 3) n;\n")

        # US-15.7, arranged: an Expert that granted read_csv only in an older version, and a published
        # workflow whose agent step uses Issue triager, which grants read_csv now.
        old_granter, flow = '55555555-5555-4555-8555-000000000004', '55555555-5555-4555-8555-000000000005'
        graph = ('{"nodes": [{"id": "start", "block": "input", "version": 1, "config": {}}, '
                 f'{{"id": "triage", "block": "agent", "version": 1, "config": {{"expert_id": "{expert_rows[1][0]}"}}}}, '
                 '{"id": "done", "block": "output", "version": 1, "config": {}}], "links": []}')
        stack.runtime(
            f"insert into public.experts (id, workspace_id, name, latest_version) values ('{old_granter}', '{curated}', 'Old granter', 2);\n"
            f"insert into public.expert_versions (expert_id, version, config, created_by) values "
            f"('{old_granter}', 1, '{{\"tools\": [\"read_csv\"]}}', '{curator['user_id']}'), "
            f"('{old_granter}', 2, '{{\"tools\": [\"calculate\"]}}', '{curator['user_id']}');\n"
            f"insert into public.workflows (id, workspace_id, name, latest_version) values ('{flow}', '{curated}', 'Nightly triage', 1);\n"
            f"insert into public.workflow_versions (workflow_id, version, graph, graph_hash, block_versions, source, created_by) "
            f"values ('{flow}', 1, '{graph}', 'arranged', '{{}}', 'user', '{curator['user_id']}');\n")
        artifacts = {**artifacts, 'AUTOBOTS_TEST_EXPERTS_EMAIL': email_h, 'AUTOBOTS_TEST_EXPERTS_PASSWORD': password_h}
        # US-15.8, arranged: an owner whose workspace saves no default and one role override, and a run
        # admitted with a run role override, through the admission code (tests/db/model_sources.py).
        email_i, password_i = 'models-i@example.invalid', secrets.token_urlsafe(24)
        chooser = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], runtime_url, email_i, password_i)
        sourced = subprocess.run([str(root / PYTHON), str(root / 'tests/db/model_sources.py'), chooser['workspace_id'], chooser['user_id']],
                                 capture_output=True, text=True, errors='replace', timeout=120, check=False, cwd=root,
                                 env={**tool_env(), 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1', 'AUTOBOTS_DATABASE_URL': runtime_url})
        if sourced.returncode:
            raise Unavailable(f'the binding-source run could not be arranged: {sourced.stderr[-500:]}')
        sources = json.loads(sourced.stdout.strip().splitlines()[-1])
        cases.check('a run admitted with a run role override records its sources', 'executor run_override, coder workspace_override, researcher builtin_default',
                    str({role: sources['sources'].get(role) for role in ('executor', 'coder', 'researcher')}),
                    (sources['sources'].get('executor'), sources['sources'].get('coder'), sources['sources'].get('researcher'))
                    == ('run_override', 'workspace_override', 'builtin_default'))
        artifacts = {**artifacts, 'AUTOBOTS_TEST_MODELS_EMAIL': email_i, 'AUTOBOTS_TEST_MODELS_PASSWORD': password_i, 'AUTOBOTS_TEST_MODELS_RUN': sources['run_id']}
        # Its own workspace with no key, as the one above asserts that it holds exactly one run.
        email_e, password_e = 'owner-e@example.invalid', secrets.token_urlsafe(24)
        owner_e = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], runtime_url, email_e, password_e)
        arranged_runs = subprocess.run([str(root / PYTHON), str(root / 'tests/db/browser_runs.py'), owner_a['workspace_id'], owner_e['workspace_id']], capture_output=True, text=True, errors='replace', timeout=120, check=False, cwd=root,
                                       env={**tool_env(), 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1', 'AUTOBOTS_DATABASE_URL': runtime_url, 'AUTOBOTS_STORAGE_BASE': base, 'AUTOBOTS_STORAGE_SERVICE': stack.values['SERVICE_ROLE_KEY']})
        if arranged_runs.returncode:
            raise Unavailable(f'the browser runs could not be arranged: {arranged_runs.stderr[-500:]}')
        arranged_ids = json.loads(arranged_runs.stdout.strip().splitlines()[-1])
        cases.check('the browser runs are arranged', 'waiting_approval and succeeded', str(arranged_ids['states']), arranged_ids['states'] == {'waiting': 'waiting_approval', 'finished': 'succeeded'})
        artifacts = {**artifacts, 'AUTOBOTS_TEST_STALE_SESSION': arranged_ids['stale_session'], 'AUTOBOTS_TEST_STALE_EXPERT': arranged_ids['stale_expert'], 'AUTOBOTS_TEST_WAITING_RUN': arranged_ids['waiting_run'], 'AUTOBOTS_TEST_FILES_RUN': arranged_ids['keyless_run'], 'AUTOBOTS_TEST_FILES_EMAIL': email_e, 'AUTOBOTS_TEST_FILES_PASSWORD': password_e}
        browser_cases(root, cases, stack, base, db_port, email_a, password_a, owner_a['workspace_id'], owner_b['workspace_id'],
                      email_b, password_b, email_c, password_c, artifacts)
    finally:
        remove_stack(stack)
    label = f'label=com.docker.compose.project={project}'
    left = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout
            + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip()
    cases.check('cleanup removed the owned containers and volumes', 'none left', left or 'none', not left)
    after = other_resources(project)
    cases.check('other Docker resources are untouched', 'same', f'{len(before)} before, {len(after)} after', before == after)
    passed = all(record['status'] == 'passed' for record in cases.records)
    path = root / REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'schema_version': 'autobots.identity-qualification/v1', 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
                                'duration_seconds': round(time.monotonic() - started_at, 1), 'input_fingerprint': fingerprint(root),
                                'status': 'passed' if passed else 'failed', 'target_class': 'disposable', 'project': project, 'cases': cases.records,
                                'not_established': ['H1', 'product acceptance', 'the persistent stack', 'a running Realtime service']}, indent=2) + '\n')
    return 0 if passed else 1


def main() -> int:
    try:
        return qualify(project_root())
    except Refused as refusal:
        print(f'REFUSED before any change: {refusal}', file=sys.stderr)
        return 1
    except Unavailable as error_:
        print(f'ERROR: {error_}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
