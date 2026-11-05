#!/usr/bin/env python3
"""Validate work-item completion evidence against DH-W01-06. Runs no check and calls no model.

Exit codes: 0 valid, 1 not complete, with every reason listed, 2 unusable request.
A valid record shows that its evidence is internally consistent and current. It does not show that
a recorded assertion was correct, so review and meaningful tests remain necessary.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
import sys

from harness_lib import input_manifest, project_root

SCHEMA = 'autobots.work-evidence/v1'
CLASSES = {'static', 'mock', 'disposable', 'local_runtime', 'live'}
TRANSPORTS = {'none', 'mock', 'openrouter_live'}
STATUSES = {'passed', 'failed', 'error', 'skipped', 'not_run'}
AVAILABILITY = {'not_created', 'available', 'deleted', 'unavailable'}
SECTIONS = ('Plan', 'Implementation', 'Review', 'Verification', 'Runbook')
HASH = re.compile(r'[0-9a-f]{64}')
WORK_ITEM_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9.-]*')
PLACEHOLDER = '{{'
SECRET_PATTERNS = (re.compile(r'sk-or-[A-Za-z0-9_-]{8,}'), re.compile(r'sk-ant-[A-Za-z0-9_-]{8,}'),
                   re.compile(r'\b[A-Z][A-Z0-9_]*(?:API_KEY|SECRET|PASSWORD|TOKEN)=\S+'),
                   re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'))
# These change after verification by design. A runbook has its own revision hash.
RECORD_FILES = {'SPECS.md', 'CODEBASE.md'}
RECORD_PREFIXES = ('docs/engineering/work-items/', 'docs/engineering/runbooks/')
LOCKFILES = ('pnpm-lock.yaml', 'services/agent/uv.lock')
CONFIG_FILES = {'.gitignore', 'package.json', 'pnpm-workspace.yaml', '.node-version',
                'services/agent/pyproject.toml', 'services/agent/.python-version'}
VERIFIER_PREFIXES = ('scripts/', 'tests/harness/', 'tests/toolchain/')


def digest(items: Mapping[str, str]) -> str:
    return hashlib.sha256(json.dumps(items, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def fingerprints(root: Path) -> dict:
    manifest = input_manifest(root)
    source = {path: value for path, value in manifest.items()
              if path not in RECORD_FILES and not path.startswith(RECORD_PREFIXES)}
    def chosen(*prefixes: str, names: frozenset[str] | set[str] = frozenset()) -> dict[str, str]:
        return {path: value for path, value in source.items() if path.startswith(prefixes) or path in names}
    return {'source_manifest_sha256': digest(source),
            'nonsecret_config_sha256': digest(chosen('.claude/', names=CONFIG_FILES)),
            'lockfiles_sha256': {path: manifest.get(path, 'absent') for path in LOCKFILES},
            'generated_contracts_sha256': digest(chosen('contracts/generated/')),
            'verifier_sha256': digest(chosen(*VERIFIER_PREFIXES))}


def text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and PLACEHOLDER not in value


def nonempty_texts(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(text(item) for item in value)


def check_errors(check: object, covered: set[str]) -> list[str]:
    if not isinstance(check, dict):
        return ['a check is not an object.']
    name = check.get('id') if text(check.get('id')) else '(unnamed)'
    label = f'check {name}'
    errors = []
    status, code = check.get('status'), check.get('exit_code')
    observed = check.get('observed')
    if status not in STATUSES:
        return [f'{label}: unknown status {status!r}.']
    if not nonempty_texts(check.get('requirement_ids')):
        errors.append(f'{label}: names no requirement.')
    if not text(check.get('target_ref')):
        errors.append(f'{label}: names no target.')
    klass, transport = check.get('verification_class'), check.get('model_transport')
    if klass not in CLASSES or transport not in TRANSPORTS:
        errors.append(f'{label}: unknown verification class or model transport.')
    elif (klass == 'live') != (transport == 'openrouter_live'):
        errors.append(f'{label}: class {klass} cannot use model transport {transport}; a fake model cannot satisfy a live gate.')
    if not text(check.get('expected')):
        errors.append(f'{label}: states no expected assertion.')
    if status in {'skipped', 'not_run'}:
        if code is not None or observed is not None or check.get('finished_at_utc') is not None:
            errors.append(f'{label}: status {status} contradicts a recorded execution result.')
        errors.append(f'{label}: was {status}; only an executed passing check satisfies completion.')
        return errors
    if not text(observed):
        errors.append(f'{label}: status {status} records no observed result.')
    if not nonempty_texts(check.get('command_argv')):
        errors.append(f'{label}: status {status} records no command.')
    if not text(check.get('started_at_utc')) or not text(check.get('finished_at_utc')):
        errors.append(f'{label}: status {status} records no execution times.')
    if status == 'passed':
        if code != 0 or isinstance(code, bool):
            errors.append(f'{label}: passed contradicts exit code {code!r}.')
        elif nonempty_texts(check.get('requirement_ids')):
            covered.update(check['requirement_ids'])
    else:
        if status == 'failed' and code in (0, None):
            errors.append(f'{label}: failed contradicts exit code {code!r}.')
        errors.append(f'{label}: {status}; a required check has not passed.')
    return errors


def review_errors(review: object, current_source: str) -> list[str]:
    if not isinstance(review, dict):
        return ['review: missing.']
    errors = []
    author, reviewer = review.get('author_id'), review.get('reviewer_id')
    if not text(author):
        errors.append('review: names no author.')
    if not text(reviewer):
        errors.append('review: names no reviewer.')
    elif reviewer == author:
        errors.append('review: the reviewer is the author; a self-review is not independent.')
    if review.get('reviewed_fingerprint') != current_source:
        errors.append('review: the reviewed fingerprint is not the current source manifest.')
    if review.get('outcome') != 'approved':
        errors.append(f"review: outcome is {review.get('outcome')!r}, not approved.")
    findings = review.get('findings')
    if not isinstance(findings, list):
        return [*errors, 'review: findings are not a list.']
    for finding in findings:
        if not isinstance(finding, dict) or finding.get('severity') not in {'blocking', 'nonblocking'}:
            errors.append('review: a finding has no valid severity.')
        elif finding['severity'] == 'blocking' and finding.get('disposition') != 'resolved':
            errors.append(f"review: blocking finding {finding.get('id', '(unnamed)')} is not resolved.")
    return errors


def relative_inside(root: Path, value: object, base: str) -> Path | None:
    """A file path inside `base`, after resolving, or None. Manifest text never leaves the repository."""
    if not isinstance(value, str) or not value or value.startswith('/') or '\0' in value:
        return None
    path = (root / value).resolve()
    return path if path.is_relative_to((root / base).resolve()) else None


def runbook_errors(root: Path, runbook: object, evidence_id: object) -> list[str]:
    if not isinstance(runbook, dict):
        return ['runbook: missing.']
    path = relative_inside(root, runbook.get('path'), 'docs/engineering/runbooks')
    if path is None or not path.is_file():
        return ['runbook: the path is not an existing file under docs/engineering/runbooks.']
    errors = []
    content = path.read_bytes()
    if b'TEMPLATE, not an exercised procedure' in content or PLACEHOLDER.encode() in content:
        errors.append('runbook: is still a template.')
    if runbook.get('revision_sha256') != hashlib.sha256(content).hexdigest():
        errors.append('runbook: revision_sha256 does not match the current file.')
    exercised = runbook.get('exercised_evidence_ids')
    if not isinstance(exercised, list) or evidence_id not in exercised:
        errors.append('runbook: was not exercised by this evidence.')
    return errors


def raw_errors(root: Path, raw: object, checks: Sequence, work_item: str, evidence_id: object) -> list[str]:
    if not isinstance(raw, dict):
        return ['raw_artifacts: missing.']
    errors = []
    expected_root = f'.checks/{work_item}/{evidence_id}/'
    if raw.get('local_root') != expected_root:
        errors.append(f'raw_artifacts: local_root must be {expected_root}.')
    availability = raw.get('availability')
    if availability not in AVAILABILITY:
        errors.append('raw_artifacts: unknown availability.')
    if not text(raw.get('retention')):
        errors.append('raw_artifacts: declares no retention policy.')
    artifacts = [artifact for check in checks if isinstance(check, dict)
                 for artifact in (check.get('artifacts') or [])]
    if availability == 'not_created' and artifacts:
        errors.append('raw_artifacts: not_created contradicts referenced artifacts.')
    for artifact in artifacts:
        name = artifact.get('path') if isinstance(artifact, dict) else None
        path = relative_inside(root, name, expected_root)
        if path is None or not HASH.fullmatch(str(artifact.get('sha256'))):
            errors.append(f'raw_artifacts: {name!r} needs a path under {expected_root} and a sha256.')
        elif availability == 'available':
            if not path.is_file():
                errors.append(f'raw_artifacts: {name} is recorded available and is missing.')
            elif hashlib.sha256(path.read_bytes()).hexdigest() != artifact['sha256']:
                errors.append(f'raw_artifacts: {name} does not match its recorded hash.')
    return errors


def manifest_errors(root: Path, work_item: str, evidence_id: str, manifest: object) -> list[str]:
    if not isinstance(manifest, dict):
        return ['manifest: is not an object.']
    if manifest.get('schema_version') != SCHEMA:
        return [f'manifest: schema_version is not {SCHEMA}.']
    errors = []
    if manifest.get('template') is not False:
        errors.append('manifest: is a template, not executed evidence.')
    if manifest.get('work_item_id') != work_item:
        errors.append('manifest: names a different work item.')
    if manifest.get('evidence_id') != evidence_id:
        errors.append('manifest: names a different evidence id.')
    requirements = manifest.get('requirement_ids')
    if not nonempty_texts(requirements):
        errors.append('manifest: names no requirement.')
        requirements = []
    current = fingerprints(root)
    recorded = manifest.get('fingerprint')
    recorded = recorded if isinstance(recorded, dict) else {}
    for key, value in current.items():
        if recorded.get(key) != value:
            errors.append(f'fingerprint: {key} is stale or missing; inputs changed after this evidence.')
    versions = manifest.get('tool_versions')
    if not isinstance(versions, dict) or not versions:
        errors.append('manifest: records no tool versions.')
    checks = manifest.get('checks')
    if not isinstance(checks, list) or not checks:
        errors.append('manifest: records no checks; an empty suite is not a pass.')
        checks = []
    covered: set[str] = set()
    for check in checks:
        errors.extend(check_errors(check, covered))
    for requirement in requirements:
        if requirement not in covered:
            errors.append(f'coverage: no passing check covers {requirement}.')
    errors.extend(review_errors(manifest.get('review'), current['source_manifest_sha256']))
    errors.extend(runbook_errors(root, manifest.get('runbook'), evidence_id))
    errors.extend(raw_errors(root, manifest.get('raw_artifacts'), checks, work_item, evidence_id))
    return errors


def record_errors(content: str) -> list[str]:
    errors = []
    if PLACEHOLDER in content or re.search(r'^Status: TEMPLATE$', content, flags=re.MULTILINE):
        errors.append('work record: is still a template.')
    parts = re.split(r'^## (.+)$', content, flags=re.MULTILINE)
    sections = {parts[index].strip(): parts[index + 1].strip() for index in range(1, len(parts) - 1, 2)}
    for name in SECTIONS:
        if not sections.get(name):
            errors.append(f'work record: the {name} section is missing or empty.')
    return errors


def secret_errors(label: str, content: str) -> list[str]:
    return [f'{label}: contains a recognizable secret; redact it.' for pattern in SECRET_PATTERNS
            if pattern.search(content)][:1]


def completion_errors(root: Path, work_item: str) -> list[str]:
    """Every reason this work item is not complete. An empty list is the only passing result."""
    record = root / 'docs/engineering/work-items' / f'{work_item}.md'
    try:
        content = record.read_text()
    except (OSError, UnicodeError):
        return [f'work record: {record.relative_to(root)} is missing or unreadable.']
    errors = record_errors(content)
    match = re.search(r'^Evidence: (\S+)$', content, flags=re.MULTILINE)
    if match is None or PLACEHOLDER in match[1] or not WORK_ITEM_ID.fullmatch(match[1]):
        return [*errors, 'work record: names no evidence id.']
    evidence_id = match[1]
    directory = root / 'docs/engineering/evidence' / work_item
    manifest_path = directory / f'{evidence_id}.json'
    try:
        raw = manifest_path.read_text()
        manifest = json.loads(raw)
    except (OSError, ValueError):
        return [*errors, f'manifest: {manifest_path.relative_to(root)} is missing or not valid JSON.']
    errors.extend(secret_errors('manifest', raw))
    if PLACEHOLDER in raw:
        errors.append('manifest: still holds template placeholders.')
    errors.extend(manifest_errors(root, work_item, evidence_id, manifest))
    try:
        summary = (directory / 'summary.md').read_text()
    except (OSError, UnicodeError):
        errors.append('summary: is missing or unreadable.')
    else:
        if PLACEHOLDER in summary or evidence_id not in summary:
            errors.append('summary: is still a template or does not name this evidence.')
        errors.extend(secret_errors('summary', summary))
    return errors


def mark_complete(root: Path, work_item: str) -> bool:
    record = root / 'docs/engineering/work-items' / f'{work_item}.md'
    content = record.read_text()
    updated, count = re.subn(r'^Status: .*$', 'Status: COMPLETE', content, count=1, flags=re.MULTILINE)
    if count != 1:
        return False
    record.write_text(updated)
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('verb', choices=('fingerprints', 'validate', 'complete'))
    parser.add_argument('work_item', nargs='?')
    parser.add_argument('--project-root', type=Path, default=project_root())
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    if args.verb == 'fingerprints':
        print(json.dumps(fingerprints(root), indent=2, sort_keys=True))
        return 0
    if args.work_item is None or not WORK_ITEM_ID.fullmatch(args.work_item):
        print('ERROR: a work item id is required, such as US-1.8.', file=sys.stderr)
        return 2
    errors = completion_errors(root, args.work_item)
    if errors:
        for error in errors:
            print(f'FAIL: {error}')
        print(f'{args.work_item} is not complete: {len(errors)} problem(s). Status left unchanged.')
        return 1
    if args.verb == 'complete' and not mark_complete(root, args.work_item):
        print('ERROR: the work record has no Status line.', file=sys.stderr)
        return 2
    print(f"PASS: {args.work_item} evidence is valid{' and marked COMPLETE' if args.verb == 'complete' else ''}. "
          'This does not establish H1 or product acceptance.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
