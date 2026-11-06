#!/usr/bin/env python3
"""A queued run reaches a verified artifact under the product's worker entry point, on a disposable stack.

The worker is `autobots.operations.worker.main` with the real SDK and adapter. Only the HTTP transport and
catalog fetch are fakes, hostnames beyond loopback are refused, and every key is an arranged value, so this
makes no paid call and says nothing about a live route, which stays with US-3.4. Exit 0 passed, 1 a case failed, 2 a
prerequisite is missing.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile
import time

from app_db import AppStack, apply_migrations, bootstrap, seed
from disposable_db import (PROJECT_PREFIX, Refused, Target, Unavailable, free_port, other_resources,
                           remove_stack, require_identity, run, tool_env)
from harness_lib import fingerprint, project_root
from qualify_identity import PYTHON, STORAGE_SQL, bootstrap_owner, password_token
from qualify_operations import Checks, Ops, api_call, conditions, exited, wait
from supabase_stack import generated_values, require_images, require_rendered

REPORT = Path('.checks/worker-inference/qualification.json')
DRIVER = 'tests/db/product_inference_worker.py'
HELPER = 'tests/db/product_inference_check.py'
DEEPSEEK = 'openrouter_deepseek_flash'
TERRA = 'openrouter_terra'
DEEPSEEK_WIRE = 'deepseek/deepseek-v4.1-flash-1017'
TERRA_WIRE = 'openai/gpt-6.1-terra'
# 32,000 input and 512 output tokens at the fake catalog's prices.
DEEPSEEK_WORST = 33_024
TERRA_WORST = 34_560
KEY_ONE, KEY_TWO, KEY_B, KEY_REJECTED = 'arranged-key-one', 'arranged-key-two', 'arranged-key-b', 'arranged-rejected-key'
FLAGS = {'require_parameters': True, 'allow_fallbacks': False}
CHAT_URL = 'https://openrouter.ai/api/v1/chat/completions'
RETRY_AFTER = 3


# What a Terra request may carry, MP-07's unadvertised sampler and parallel-tool flags left out.
REQUEST_FIELDS = frozenset({'model', 'messages', 'tools', 'tool_choice', 'max_tokens', 'provider', 'stream'})
REASONING_EFFORTS = frozenset({'minimal', 'low', 'medium', 'high'})


def request_shape_problems(fields: list[str], reasoning: object) -> list[str]:
    """One request as sent. A flag that isn't advertised, or a reasoning setting that isn't one."""
    problems = [f'unexpected field {name}' for name in fields if name not in REQUEST_FIELDS and name != 'reasoning']
    if 'reasoning' in fields:
        if not isinstance(reasoning, dict) or set(reasoning) - {'effort', 'summary'} or reasoning.get('effort') not in REASONING_EFFORTS:
            problems.append('reasoning has an unknown shape or is turned off')
    return problems


def key_id(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def qualify(root: Path) -> int:
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    gateway_port = free_port()
    db_port = free_port([gateway_port])
    api_port = free_port([gateway_port, db_port])
    target = Target(project, db_port, gateway_port)
    stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=generated_values(gateway_port, db_port))
    stack.migrator_password, stack.runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    require_identity(target, tool_env())
    if run(['docker', 'info', '--format', '{{.ServerVersion}}'], tool_env(), 30).returncode:
        raise Unavailable('the Docker engine is not reachable')
    (root / REPORT).unlink(missing_ok=True)
    require_images(require_rendered(stack))
    cases = Checks()
    input_fingerprint = fingerprint(root)
    before = other_resources(project)
    started_at = time.monotonic()
    base = f'http://127.0.0.1:{gateway_port}'
    logs = root / '.checks/worker-inference/logs'
    logs.mkdir(parents=True, exist_ok=True)
    for old in logs.glob('*.log'):
        old.unlink()
    config_root = Path(tempfile.mkdtemp(prefix='autobots-inference-'))
    requests_file = config_root / 'requests.jsonl'
    ops = Ops(root, stack, base, db_port, logs)
    provider_env = {'AUTOBOTS_CONFIG_ROOT': str(config_root), 'NODE_ENV': 'production',
                    'AUTOBOTS_PROVIDER_MASTER_KEY_FILE': str(config_root / 'secrets/master.key')}
    driver_env = {'AUTOBOTS_TEST_REQUESTS': str(requests_file), 'AUTOBOTS_TEST_REJECTED_KEY': KEY_REJECTED, 'AUTOBOTS_WORKER_INFERENCE': 'enabled'}

    def helper(*argv: str, env: dict[str, str] | None = None) -> str:
        result = subprocess.run([str(root / PYTHON), str(root / HELPER), *argv], env={**ops.env, **provider_env, **(env or {})},
                                capture_output=True, text=True, errors='replace', timeout=90, check=False)
        if result.returncode:
            raise Unavailable(f'{argv[0]} failed: {result.stderr.strip()[-400:]}')
        return result.stdout

    def save_key(workspace: str, key: str) -> None:
        helper('save-key', workspace, env={'AUTOBOTS_TEST_KEY': key})

    def admit(workspace: str, tag: str, profile: str = DEEPSEEK) -> str:
        return helper('admit', workspace, tag, profile).strip().splitlines()[-1]

    def status(run_id: str) -> str:
        return ops.sql(f"select status from public.runs where id = '{run_id}';")

    def settled(run_id: str, wanted: str, seconds: float = 90) -> bool:
        return wait(lambda: status(run_id) == wanted, seconds)

    def sent(tag: str) -> list[dict]:
        if not requests_file.exists():
            return []
        lines = [json.loads(line) for line in requests_file.read_text().splitlines()]
        return [line for line in lines if f'[{tag}]' in line.get('goal', '')]

    def goal_view(token: str, run_id: str) -> tuple[str, list]:
        code, reply = api_call(api_port, ops.internal, token, 'GET', f'/v1/runs/{run_id}/workspace')
        if code != 200:
            return '', []
        view = json.loads(reply)
        return view.get('objective') or '', view.get('criteria') or []

    def invocations(run_id: str) -> str:
        return ops.sql(f"select coalesce(string_agg(distinct profile || '/' || wire_id || '/' || status || '/' || coalesce(failure_class, '-') || '/' "
                       f"|| coalesce(credential_version::text, '-') || '/' || reserved_micro_usd || '/' || coalesce(charged_micro_usd::text, '-'), ' '), 'none') "
                       f"from app_private.model_invocations where run_id = '{run_id}';")

    def reply_facts(run_id: str) -> list[str]:
        result = stack.runtime(f"select finish_reason || '/' || input_tokens || '/' || output_tokens || '/' || reasoning_tokens || '/' || tool_names::text "
                               f"|| '/' || invalid_tool_calls from app_private.model_invocations where run_id = '{run_id}' order by created_at;")
        return result.stdout.split()

    def verdict(run_id: str) -> str:
        return ops.sql(f"select passed::text || '/' || unmet::text from app_private.run_verifications where run_id = '{run_id}' order by created_at desc limit 1;")

    def stop_reason(run_id: str) -> str:
        return ops.sql(f"select coalesce(stop_reason, 'none') from app_private.run_usage where run_id = '{run_id}';")

    def resume(token: str, run_id: str) -> tuple[int, str]:
        version = ops.sql(f"select version from public.runs where id = '{run_id}';")
        return api_call(api_port, ops.internal, token, 'POST', f'/v1/runs/{run_id}/resume', json.dumps({'expected_version': int(version)}).encode(), {'Idempotency-Key': secrets.token_hex(8)})

    def verified_report(workspace: str, run_id: str) -> tuple[str, str]:
        return ops.sql(f"select passed::text from app_private.run_verifications where run_id = '{run_id}' order by created_at desc limit 1;"), helper('artifact', workspace, run_id)

    try:
        started = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
        if started.returncode:
            raise Unavailable(f'the stack did not start: {started.stderr[-300:]}')
        bootstrap(stack, root)
        applied, problem = apply_migrations(stack, root / 'supabase/migrations')
        if problem or seed(stack, root).returncode:
            raise Unavailable(f'migrations failed: {problem}')
        if stack.sql((root / STORAGE_SQL).read_text()).returncode:
            raise Unavailable('the storage setup failed')
        service = stack.values['SERVICE_ROLE_KEY']
        email_a, email_b = 'owner-a@example.invalid', 'owner-b@example.invalid'
        password_a, password_b = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        workspace_a = bootstrap_owner(root, base, service, ops.url, email_a, password_a)['workspace_id']
        workspace_b = bootstrap_owner(root, base, service, ops.url, email_b, password_b)['workspace_id']
        token_a = password_token(base, stack.values['ANON_KEY'], email_a, password_a)[1]
        token_b = password_token(base, stack.values['ANON_KEY'], email_b, password_b)[1]
        ops.api(api_port, config_root)
        wait(lambda: api_call(api_port, ops.internal, token_a)[0] == 200, 40)

        # Admission through the API a person uses: it reads this workspace's key before queueing anything.
        save_key(workspace_a, KEY_ONE)
        goal = json.dumps({'goal_text': 'Write the report [happy]', 'limit_micro_usd': 1_000_000,
                           'required_artifacts': [{'name': 'report.md', 'must_contain': ['Total: 42']}]}).encode()
        code, reply = api_call(api_port, ops.internal, token_a, 'POST', '/v1/runs', goal, {'Idempotency-Key': secrets.token_hex(8)})
        cases.check('the API admits a run for a workspace with a key', '202', code, code == 202)
        happy = json.loads(reply)['run_id']

        # Off by default: the entry point with no switch is what the runbook starts unless told otherwise.
        off = ops.spawn('switch-off', [str(root / PYTHON), '-m', 'autobots.operations.worker'], provider_env)
        beating = wait(lambda: ops.sql("select claims_inference::text from app_private.worker_heartbeats where state = 'running';") == 'false', 20)
        time.sleep(4)
        queued = ops.sql(f"select status from app_private.run_jobs where run_id = '{happy}';")
        code, body = api_call(api_port, ops.internal, token_a)
        cases.check('with no switch the worker claims nothing and says so', 'not claiming, queued, no_inference_worker', f'{beating}, {queued}, {conditions(body).get("worker")}',
                    beating and queued == 'queued' and conditions(body).get('worker') == 'no_inference_worker')
        off.send_signal(signal.SIGTERM)
        exited(off, 20)

        # Half-configured: the switch is on and there's nowhere to read a key from.
        partial = ops.spawn('switch-partial', [str(root / PYTHON), DRIVER], driver_env)
        exit_code = exited(partial, 60)
        partial_log = (logs / 'switch-partial.log').read_text(errors='replace')
        cases.check('the switch without its configuration refuses to start', 'non-zero, names the setting', f'{exit_code}', exit_code not in (0, None) and 'AUTOBOTS_CONFIG_ROOT' in partial_log)

        # The product worker, serving every remaining case without a restart.
        worker = ops.spawn('product-worker', [str(root / PYTHON), DRIVER], {**provider_env, **driver_env})
        finished = settled(happy, 'succeeded')
        passed, content = verified_report(workspace_a, happy) if finished else ('', '')
        cases.check('a queued run reaches a verified artifact under the product entry point', 'succeeded, verification passed, the bytes read back',
                    f'{status(happy)}, {passed}, {content!r}', finished and passed == 'true' and content.startswith('report.md\n') and 'Total: 42' in content)
        code, body = api_call(api_port, ops.internal, token_a)
        claiming = ops.sql("select claims_inference::text from app_private.worker_heartbeats where state = 'running';")
        cases.check('a claiming worker reads as one', 'claims true, worker_ready', f'{claiming}, {conditions(body).get("worker")}', claiming == 'true' and conditions(body).get('worker') == 'worker_ready')
        calls = sent('happy')
        cases.check('every request goes to OpenRouter under the frozen route and routing flags', 'terra by default, no fallback, 512 tokens',
                    f'{len(calls)} requests, {sorted({call["model"] for call in calls})}, {calls[0]["provider"] if calls else None}, {sorted({call["max_tokens"] for call in calls})}',
                    calls and all(call['url'] == CHAT_URL and call['model'] == TERRA_WIRE and call['provider'] == FLAGS and call['max_tokens'] == 512 and not call['models'] for call in calls))
        cases.check('the gateway offers the tools the plan needs', 'includes propose_plan and publish_artifact', calls[0]['tools'] if calls else None,
                    calls and {'propose_plan', 'save_artifact', 'publish_artifact', 'complete_task'} <= set(calls[0]['tools']))
        ledger = invocations(happy)
        cases.check('each attempt is reserved from the catalog price, settled from the reply and audited', f'{TERRA}/{TERRA_WIRE}/succeeded/-/1/{TERRA_WORST}/100',
                    ledger, ledger == f'{TERRA}/{TERRA_WIRE}/succeeded/-/1/{TERRA_WORST}/100')
        used = {call['key'] for call in calls}
        cases.check('the workspace key was used', 'key one', used == {key_id(KEY_ONE)}, used == {key_id(KEY_ONE)})
        facts = reply_facts(happy)
        cases.check('each call records what its reply said about itself', 'tool_calls, then stop, with 5, 7 and 3 tokens, and the tool named',
                    facts, facts == ['tool_calls/5/7/3/{propose_plan}/0', 'tool_calls/5/7/3/{save_artifact}/0', 'tool_calls/5/7/3/{publish_artifact}/0',
                                     'tool_calls/5/7/3/{complete_task}/0', 'stop/5/7/3/{}/0'])

        # Another run in the same process, frozen to the other profile.
        other = admit(workspace_a, 'other', DEEPSEEK)
        finished = settled(other, 'succeeded')
        calls = sent('other')
        ledger = invocations(other)
        cases.check('the route comes from each run, not the worker', 'same process, deepseek request and ledger', f'{status(other)}, {sorted({call["model"] for call in calls})}, {ledger}, alive {worker.poll() is None}',
                    finished and worker.poll() is None and bool(calls) and {call['model'] for call in calls} == {DEEPSEEK_WIRE} and ledger == f'{DEEPSEEK}/{DEEPSEEK_WIRE}/succeeded/-/1/{DEEPSEEK_WORST}/100')

        # Reasoning metadata on every tool reply, compared with each request that follows, US-11.2.
        reasoning = admit(workspace_a, 'reasoning', TERRA)
        finished = settled(reasoning, 'succeeded')
        compared = [call for call in sent('reasoning') if 'reasoning' in call]
        outcomes = sorted({call['reasoning'] for call in compared})
        cases.check('reasoning metadata comes back unchanged on every continuation', 'succeeded, every comparison survived', f'{status(reasoning)}, {len(compared)} comparisons, {outcomes}, {[call["differences"] for call in compared if call["differences"]][:2]}',
                    finished and len(compared) >= 4 and outcomes == ['survived'])
        leaked = ops.sql(f"select count(*) from public.run_events where run_id = '{reasoning}' and payload::text like '%ARRANGED-REASONING-MARKER%';")
        cases.check('it reaches no activity event', '0 events', f'{leaked} events', leaked == '0')

        # A workflow reaches the same worker, in the same process.
        flow = helper('workflow', workspace_a).strip().splitlines()[-1]
        flow_done = settled(flow, 'succeeded', 60)
        cases.check('the product worker runs a workflow to the end', 'succeeded', f'{status(flow)}, worker alive {worker.poll() is None}', flow_done and worker.poll() is None)

        # A long run compacts through the real SDK, under its summarizer role. WI-5.
        compacted = admit(workspace_a, 'compact', TERRA)
        before_view = goal_view(token_a, compacted)
        summaries_before = ops.sql(f"select count(*) from app_private.run_summaries where run_id = '{compacted}';")
        finished = settled(compacted, 'succeeded', 120)
        asked = sent('compact-summary')
        roles = ops.sql(f"select coalesce(string_agg(distinct role || '/' || status, ' '), 'none') from app_private.model_invocations where run_id = '{compacted}' and role = 'summarizer';")
        stored = ops.sql(f"select count(*) from app_private.run_summaries where run_id = '{compacted}';")
        cases.check('a long run summarizes through the real SDK and finishes', 'succeeded, a summarizer call with no tools, a stored summary',
                    f'{status(compacted)}, {stop_reason(compacted)}, {len(asked)} asked, {[call["tools"] for call in asked]}, {roles}, {stored} stored',
                    finished and bool(asked) and all(not call['tools'] for call in asked) and roles == 'summarizer/succeeded' and int(stored) >= 1)
        after = [line for line in sent('compact') if 'saw_summary' in line]
        cases.check('the summary is in the view of the calls that follow', 'seen', f'{sum(line["saw_summary"] for line in after)} of {len(after)}', any(line['saw_summary'] for line in after))
        passed, content = verified_report(workspace_a, compacted) if finished else ('', '')
        cases.check('and its result still verifies', 'verified, Total: 42', f'{passed}', passed == 'true' and 'Total: 42' in content)
        after_view = goal_view(token_a, compacted)
        cases.check('the goal and criteria the API shows are the same after compaction', 'identical, and present', f'{after_view}', bool(before_view[0]) and bool(before_view[1]) and before_view == after_view and summaries_before == '0')

        # LC-26: the shape of every request Terra's runs sent.
        terra_calls = [call for tag in ('compact', 'compact-summary', 'reasoning') for call in sent(tag) if 'fields' in call]
        problems = sorted({problem for call in terra_calls for problem in request_shape_problems(call['fields'], call.get('reasoning_field'))})
        routed = all(call.get('provider') == FLAGS and not call.get('models') for call in terra_calls)
        with_reasoning = sum('reasoning' in call['fields'] for call in terra_calls)
        cases.check("Terra's requests carry no unadvertised flag, and their routing flags are exact", 'no problems, and none of them sets reasoning', f'{len(terra_calls)} requests, {problems}, routing exact {routed}, {with_reasoning} with reasoning',
                    bool(terra_calls) and not problems and routed and with_reasoning == 0)

        # LC-25: every request the fake transport saw is on the ledger, by role, on the frozen route.
        inventory = ops.sql(f"select coalesce(string_agg(role || '/' || profile || '/' || wire_id || '=' || n, ' ' order by role), 'none') from (select role, profile, wire_id, count(*) n from app_private.model_invocations where run_id = '{compacted}' group by 1, 2, 3) t;")
        frozen = ops.sql(f"select coalesce(string_agg(distinct value, ' '), 'none') from public.runs, jsonb_each_text(policy_snapshot -> 'bindings') where id = '{compacted}';")
        billed = ops.sql(f"select count(*) from app_private.model_invocations where run_id = '{compacted}';")
        seen_requests = len([call for tag in ('compact', 'compact-summary') for call in sent(tag) if 'fields' in call])
        expected_inventory = ' '.join(sorted(f"{role}/{TERRA}/{TERRA_WIRE}" for role in ('executor', 'summarizer')))
        listed = ' '.join(sorted(item.split('=')[0] for item in inventory.split()))
        cases.check('the dispatch inventory matches the frozen role map, and no request is off the ledger', f'{expected_inventory}, as many requests as rows',
                    f'{inventory}; frozen {frozen}; {seen_requests} requests, {billed} rows', listed == expected_inventory and frozen == TERRA and str(seen_requests) == billed and {call['model'] for tag in ('compact', 'compact-summary') for call in sent(tag) if 'fields' in call} == {TERRA_WIRE})

        # A child through the same worker and SDK, on its parent's ledger. WI-5.
        lead = helper('admit-lead', workspace_a).strip().splitlines()[-1]
        settled_child = wait(lambda: ops.sql(f"select count(*) from app_private.assignments where parent_run_id = '{lead}' and status = 'finished';") == '1', 90)
        parent_failed = settled(lead, 'failed', 60)
        row = ops.sql(f"select r.status || '/' || a.outcome from app_private.assignments a join public.runs r on r.id = a.child_run_id where a.parent_run_id = '{lead}';")
        billed = ops.sql(f"select count(distinct run_id) || '/' || count(*) from app_private.model_invocations where root_run_id = '{lead}';")
        cases.check('a child runs through the product worker and bills its root', 'succeeded, 2 runs on the root ledger', f'{row}, {billed}',
                    settled_child and row == 'succeeded/succeeded' and billed.startswith('2/'))
        tree_roles = ops.sql(f"select string_agg(distinct role || '/' || profile || '/' || wire_id, ' ') from app_private.model_invocations where root_run_id = '{lead}';")
        tree_requests = len([call for tag in ('parent', 'child-part') for call in sent(tag) if 'fields' in call])
        cases.check("the tree's dispatches are on the root's ledger by role and frozen route, with none off it", f'executor on Terra, as many requests as rows', f'{tree_roles}; {tree_requests} requests, {billed}',
                    tree_roles == f'executor/{TERRA}/{TERRA_WIRE}' and billed == f'2/{tree_requests}' and {call['model'] for tag in ('parent', 'child-part') for call in sent(tag) if 'fields' in call} == {TERRA_WIRE})
        cases.check('its parent, which stops with no evidence of its own, fails', 'failed', status(lead), parent_failed)

        # Rotation reaches the next attempt with no restart.
        save_key(workspace_a, KEY_TWO)
        rotated = admit(workspace_a, 'rotated')
        finished = settled(rotated, 'succeeded')
        calls = sent('rotated')
        ledger = invocations(rotated)
        cases.check('a rotated key is used by the next run without a restart', 'key two, version 2 in the audit', f'{status(rotated)}, {ledger}',
                    finished and worker.poll() is None and bool(calls) and {call['key'] for call in calls} == {key_id(KEY_TWO)} and f'/succeeded/-/2/{DEEPSEEK_WORST}/100' in ledger)

        # A missing key, admitted directly since the API would refuse it: arranged, as a key removed after queueing.
        missing = admit(workspace_b, 'missing')
        paused = settled(missing, 'paused')
        cases.check('a missing key pauses the run before any reservation or request', 'paused, credentials_required, none, 0',
                    f'{status(missing)}, {stop_reason(missing)}, {invocations(missing)}, {len(sent("missing"))}',
                    paused and stop_reason(missing) == 'credentials_required' and invocations(missing) == 'none' and not sent('missing'))
        code, reply = resume(token_b, missing)
        cases.check("the API's resume refuses with no key", '409 credentials_required', f'{code} {reply[:80]}', code == 409 and 'credentials_required' in reply)
        save_key(workspace_b, KEY_B)
        code, reply = resume(token_b, missing)
        finished = settled(missing, 'succeeded')
        passed, content = verified_report(workspace_b, missing) if finished else ('', '')
        cases.check('adding a key and resuming finishes the same run', 'resume 200, succeeded, verified', f'{code}, {status(missing)}, {passed}',
                    code == 200 and finished and passed == 'true' and 'Total: 42' in content)

        # A key OpenRouter rejects: no retry, no other source, and nothing resumes until it's replaced.
        save_key(workspace_b, KEY_REJECTED)
        rejected = admit(workspace_b, 'rejected')
        paused = settled(rejected, 'paused')
        ledger = invocations(rejected)
        auth = ops.sql(f"select auth_status from app_private.provider_settings where workspace_id = '{workspace_b}';")
        cases.check('a 401 pauses after one request and marks the key invalid', 'paused, invalid_credential, 1 request, invalid',
                    f'{status(rejected)}, {stop_reason(rejected)}, {len(sent("rejected"))}, {auth}, {ledger}',
                    paused and stop_reason(rejected) == 'invalid_credential' and len(sent('rejected')) == 1 and auth == 'invalid' and '/failed_before_acceptance/invalid_credential/' in ledger)
        code, reply = resume(token_b, rejected)
        cases.check('a rejected key blocks resume', '409 credential_invalid', f'{code} {reply[:80]}', code == 409 and 'credential_invalid' in reply)
        save_key(workspace_b, KEY_B)
        code, reply = resume(token_b, rejected)
        finished = settled(rejected, 'succeeded')
        cases.check('a replaced key lets the run finish', 'resume 200, succeeded', f'{code}, {status(rejected)}', code == 200 and finished)

        # A provider reply the SDK can't parse: it answered, so the call may have been charged.
        malformed = admit(workspace_a, 'malformed')
        paused = settled(malformed, 'paused')
        ledger = invocations(malformed)
        cases.check('an unparseable success keeps its reservation and waits for a person', f'paused, uncertain_acceptance, 1 request, uncertain at {DEEPSEEK_WORST}',
                    f'{status(malformed)}, {stop_reason(malformed)}, {len(sent("malformed"))}, {ledger}',
                    paused and stop_reason(malformed) == 'uncertain_acceptance' and len(sent('malformed')) == 1 and f'/uncertain/uncertain_acceptance/2/{DEEPSEEK_WORST}/-' in ledger)
        code, reply = resume(token_a, malformed)
        cases.check('it cannot resume until reconciled', '409 uncertain_model_call', f'{code} {reply[:80]}', code == 409 and 'uncertain_model_call' in reply)

        # Cut off twice: the one repair runs out, and the ledger shows why the run stopped.
        cutoff = admit(workspace_a, 'cutoff')
        finished = settled(cutoff, 'failed')
        facts = reply_facts(cutoff)
        cases.check('a run cut off twice stops, and its ledger says so', 'failed, incomplete_output, 2 requests, length with a broken tool call on both',
                    f'{status(cutoff)}, {stop_reason(cutoff)}, {len(sent("cutoff"))}, {facts}',
                    finished and stop_reason(cutoff) == 'incomplete_output' and len(sent('cutoff')) == 2
                    and facts == ['length/5/7/3/{}/1'] * 2)

        # A rate limit: the provider's wait is honored, then the retries run out as the policy states.
        limited = admit(workspace_a, 'limited')
        finished = settled(limited, 'failed')
        calls = sent('limited')
        gaps = [round(after['at'] - before_call['at'], 1) for before_call, after in zip(calls, calls[1:])]
        cases.check('a 429 is retried twice, each after the time it asked for', f'failed, rate_limited, 3 requests, gaps of at least {RETRY_AFTER}s',
                    f'{status(limited)}, {stop_reason(limited)}, {len(calls)}, {gaps}',
                    finished and stop_reason(limited) == 'rate_limited' and len(calls) == 3 and all(gap >= RETRY_AFTER for gap in gaps))
        ledger = invocations(limited)
        cases.check('a refused attempt releases its reservation', 'failed_before_acceptance, charged 0', ledger, ledger.endswith('/0') and 'failed_before_acceptance/rate_limited' in ledger)

        # Each workspace's runs used only that workspace's keys, across every run that sent anything.
        used_a = {call['key'] for tag in ('happy', 'other', 'rotated', 'malformed', 'limited') for call in sent(tag)}
        used_b = {call['key'] for tag in ('missing', 'rejected') for call in sent(tag)}
        cases.check("one workspace's key never served another's run", 'A used its two keys, B its two', f'{len(used_a)} and {len(used_b)} keys',
                    used_a == {key_id(KEY_ONE), key_id(KEY_TWO)} and used_b == {key_id(KEY_B), key_id(KEY_REJECTED)})

        # Below the factory: name lookups and Python's own connects, so a stray can't leave unseen.
        lines = [json.loads(line) for line in requests_file.read_text().splitlines()]
        looked_up = [line for line in lines if 'refused_host' in line]
        connected = [line for line in lines if 'refused_connect' in line]
        controls = {line['refused_host'] for line in looked_up if line.get('control')} | {line['refused_connect'] for line in connected if line.get('control')}
        strays = [line for line in [*looked_up, *connected] if not line.get('control')]
        cases.check('a stray client is seen by name, on loopback and by literal address, and no real dispatch left the fake transport',
                    'all three controls caught, and no other', f'controls {sorted(controls)}, strays {strays}',
                    controls == {'openrouter.ai', '127.0.0.1:9', '198.51.100.1:80'} and not strays)

        # A clean stop.
        worker.send_signal(signal.SIGTERM)
        exit_code = exited(worker, 40)
        last = ops.sql("select state from app_private.worker_heartbeats where claims_inference;")
        cases.check('the inference worker stops on SIGTERM and says so', 'exit 0, stopped', f'{exit_code}, {last}', exit_code == 0 and last == 'stopped')

        # Work that needs no model must settle with no key, ahead of the refusal that would pause it.
        email_c, password_c = 'owner-c@example.invalid', secrets.token_urlsafe(24)
        workspace_c = bootstrap_owner(root, base, service, ops.url, email_c, password_c)['workspace_id']
        cancelling, verifying = admit(workspace_c, 'cancelling'), admit(workspace_c, 'verifying')
        helper('strand', workspace_c, cancelling, 'cancel')
        helper('strand', workspace_c, verifying, 'verify')
        states = f'{status(cancelling)}, {status(verifying)}'
        second = ops.spawn('product-worker-2', [str(root / PYTHON), DRIVER], {**provider_env, **driver_env})
        cancelled, judged = settled(cancelling, 'cancelled'), settled(verifying, 'failed')
        cases.check('with no key, a cancel still settles (arranged: its worker died)', 'cancelling, then cancelled, 0 requests', f'{states}, {status(cancelling)}, {len(sent("cancelling"))}',
                    states.startswith('cancelling') and cancelled and not sent('cancelling'))
        cases.check('with no key, a candidate is still judged (arranged: its worker died)', 'verifying, then failed on its unmet plan, not paused, 0 requests',
                    f'{states}, {status(verifying)}, {verdict(verifying)}, {len(sent("verifying"))}',
                    states.endswith('verifying') and judged and verdict(verifying).startswith('false/') and 'plan_incomplete' in verdict(verifying) and not sent('verifying'))

        # A configuration file the worker can't read: it was a claim loop before, blocking cancels too.
        unreadable_file = config_root / '.env'
        unreadable_file.write_bytes(b'\xff\xfe')
        unreadable = admit(workspace_c, 'unreadable')
        paused = settled(unreadable, 'paused')
        unreadable_file.unlink()
        cases.check('an unreadable configuration pauses the run instead of looping', 'paused, credential_unavailable, none, 0 requests',
                    f'{status(unreadable)}, {stop_reason(unreadable)}, {invocations(unreadable)}, {len(sent("unreadable"))}',
                    paused and stop_reason(unreadable) == 'credential_unavailable' and invocations(unreadable) == 'none' and not sent('unreadable'))
        second.send_signal(signal.SIGTERM)
        cases.check('the second worker stops cleanly too', 'exit 0', exited(second, 40), second.returncode == 0)

        # Across every run and process: nothing durable or logged holds a key, and nothing left loopback.
        runs = "'" + "','".join((happy, other, rotated, missing, rejected, malformed, limited, cancelling, verifying, unreadable)) + "'"
        blobs = ops.sql(f"select (select count(*) from agent_runtime.checkpoint_blobs where thread_id in ({runs})) || '/' || "
                        f"(select count(*) from agent_runtime.checkpoint_blobs where thread_id in ({runs}) and encode(blob, 'escape') like '%arranged-%') || '/' || "
                        f"(select count(*) from agent_runtime.checkpoint_writes where thread_id in ({runs}) and encode(blob, 'escape') like '%arranged-%');")
        counts = blobs.split('/')
        cases.check('checkpoints hold no key', 'some blobs, 0 and 0 with a key', blobs, len(counts) == 3 and int(counts[0]) > 0 and counts[1:] == ['0', '0'])
        refused = [json.loads(line) for line in requests_file.read_text().splitlines() if 'refused_host' in line]
        refused = [line for line in refused if not line.get('control')]
        cases.check('nothing tried to resolve a host beyond loopback', 'none, apart from the arranged control', refused or 'none', not refused)
        written = '\n'.join(path.read_text(errors='replace') for path in logs.glob('*.log'))
        planted = [key for key in (KEY_ONE, KEY_TWO, KEY_B, KEY_REJECTED, stack.runtime_password, service) if key in written]
        cases.check('no process log holds a key', 'none', len(planted), not planted)
        cases.check('no process log holds reasoning metadata', 'none', 'ARRANGED-REASONING-MARKER' in written, 'ARRANGED-REASONING-MARKER' not in written)
        cases.check('no step failed in either worker', 'no worker.step_failed', 'worker.step_failed' in written, 'worker.step_failed' not in written)
        stable = fingerprint(root)
        cases.check('the inputs held still for the whole run', 'same fingerprint', stable == input_fingerprint, stable == input_fingerprint)
    finally:
        ops.stop_all()
        remove_stack(stack)
        subprocess.run(['rm', '-rf', str(config_root)], check=False)
    label = f'label=com.docker.compose.project={project}'
    left = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout
            + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip()
    cases.check('cleanup removed the owned containers and volumes', 'none left', left or 'none', not left)
    after = other_resources(project)
    changed = sorted(set(before) ^ set(after))
    cases.check('other Docker resources are untouched', 'same', f'{len(before)} before, {len(after)} after, changed {changed[:8]}', before == after)
    # Everything up to cleanup ran with the fake transport in the process under test.
    for record in cases.records[:-2]:
        record['model_transport'] = 'mock'
    passed_all = all(record['status'] == 'passed' for record in cases.records)
    report = root / REPORT
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({'schema_version': 'autobots.worker-inference-qualification/v1', 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
                                  'duration_seconds': round(time.monotonic() - started_at, 1), 'input_fingerprint': input_fingerprint,
                                  'status': 'passed' if passed_all else 'failed', 'target_class': 'disposable', 'model_transport': 'fake', 'project': project, 'cases': cases.records,
                                  'not_established': ['H1', 'product acceptance', 'US-3.4', 'a live OpenRouter route', 'real response shapes or billing', 'the persistent stack']}, indent=2))
    for record in cases.records:
        if record['status'] != 'passed':
            print(f"FAILED {record['id']}: expected {record['expected']}, observed {record['observed']}", file=sys.stderr)
    print(f'{"PASS" if passed_all else "FAIL"}: worker inference qualification, {round(time.monotonic() - started_at)}s, report {REPORT}')
    return 0 if passed_all else 1


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
