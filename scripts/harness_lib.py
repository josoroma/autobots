"""Local harness primitives; no network, package installation or model calls."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def input_manifest(root: Path) -> dict[str, str]:
    """Hash relevant nonsecret inputs, including untracked files, not report outputs."""
    root = root.resolve()
    paths = set(root.glob('PRD*.md'))
    paths.update(root / name for name in ('AGENTS.md', 'CLAUDE.md', 'CODEBASE.md',
                                         'SPECS.md', 'README.md', '.gitignore'))
    try:
        mapping = json.loads((root / '.claude/autobots.json').read_text()).get('documents', {})
        for value in mapping.values():
            if isinstance(value, str):
                mapped = (root / value).resolve()
                if mapped.is_relative_to(root.resolve()) and mapped.suffix == '.md':
                    paths.add(mapped)
    except (OSError, ValueError, AttributeError):
        pass  # Configuration validation reports malformed maps; never read outside root.
    for directory in ('.claude', 'scripts', 'tests/harness', 'docs/engineering'):
        base = root / directory
        if base.exists():
            paths.update(base.rglob('*'))
    manifest = {}
    for path in sorted(paths):
        relative = path.relative_to(root)
        if (not path.is_file() or path.is_symlink()
                or '__pycache__' in relative.parts
                or relative.as_posix().startswith('docs/engineering/evidence/')
                # OhMyOrch session state: rewritten on every delivery refresh and ignored by Git.
                or relative.as_posix().startswith(('.claude/ohmyorch/runtime/', '.claude/ohmyorch/backups/'))
                or path.name == 'approvals.local.json'
                or path.name == 'settings.local.json'
                or path.name.startswith('.env')
                or path.suffix in {'.pyc', '.log'}):
            continue
        manifest[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def fingerprint(root: Path) -> str:
    encoded = json.dumps(input_manifest(root), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode()).hexdigest()


def report_state(root: Path) -> tuple[bool, str]:
    report = root / '.checks/harness/latest.json'
    try:
        data = json.loads(report.read_text())
    except (OSError, ValueError):
        return False, 'No readable harness report exists.'
    if not isinstance(data, dict):
        return False, 'The harness report is not a valid result object.'
    if (data.get('schema_version') != 'autobots.harness-result/v1'
            or data.get('template') is not False
            or data.get('inputs_unchanged_during_check') is not True):
        return False, 'The report is a template, incomplete, or records changing inputs.'
    if data.get('status') != 'passed' or data.get('profile') != 'harness':
        return False, 'The last harness check did not pass.'
    checks = data.get('checks')
    required = {'project_configuration', 'backlog_validation', 'harness_behavior_tests'}
    if (not isinstance(checks, list) or len(checks) != len(required)
            or not all(isinstance(check, dict) for check in checks)
            or {check.get('id') for check in checks} != required
            or any(check.get('status') != 'passed' for check in checks)):
        return False, 'The report lacks the required successful checks.'
    for check in checks:
        if check['id'] != 'project_configuration' and check.get('exit_code') != 0:
            return False, 'The report does not record successful command execution.'
        if check['id'] == 'harness_behavior_tests' and (
                type(check.get('tests_executed')) is not int or check['tests_executed'] < 1):
            return False, 'An empty or missing behavioral suite cannot pass.'
    if (data.get('input_fingerprint') != fingerprint(root)
            or data.get('input_manifest') != input_manifest(root)):
        return False, 'Source/configuration inputs changed after the last harness check.'
    return True, 'Current repository harness checks passed; application checks remain separate.'


def config_errors(root: Path) -> list[str]:
    errors = []
    try:
        config = json.loads((root / '.claude/autobots.json').read_text())
        settings = json.loads((root / '.claude/settings.json').read_text())
    except (OSError, ValueError) as exc:
        return [f'Configuration unreadable: {type(exc).__name__}']
    if not isinstance(config, dict) or not isinstance(settings, dict):
        return ['Configuration must contain JSON objects.']
    interpreter = config.get('python_executable')
    if (not isinstance(interpreter, str) or not Path(interpreter).is_absolute()
            or not Path(interpreter).is_file() or not os.access(interpreter, os.X_OK)):
        errors.append('Configure an existing absolute path to the qualified Python 3.12+ interpreter.')
    documents = config.get('documents')
    if not isinstance(documents, dict):
        return ['Document mappings must be an object.']
    for key in ('specs', 'codebase', 'contract', 'product', 'harness', 'providers',
                'deployment', 'research', 'comparison'):
        value = documents.get(key)
        if not isinstance(value, str):
            errors.append(f'Missing document mapping: {key}')
            continue
        dest = (root / value).resolve()
        if not dest.is_relative_to(root.resolve()) or not dest.is_file() or dest.suffix != '.md':
            errors.append(f'Invalid local document mapping: {key}')
    if set(settings) != {'hooks'}:
        errors.append('Baseline settings permit only the reviewed hooks; disabling hooks or changing model/env/permissions is unsupported.')
    hooks = settings.get('hooks', {})
    if not isinstance(hooks, dict):
        return errors + ['Hook configuration must be an object.']
    expected = {'SessionStart', 'PreToolUse', 'PostToolUse', 'Stop', 'SubagentStop'}
    if set(hooks) != expected:
        errors.append('Unexpected or missing baseline hook events.')
    for event, groups in hooks.items():
        if not isinstance(groups, list) or len(groups) != 1:
            errors.append(f'{event}: expected one nonempty hook group.')
            continue
        for group in groups:
            if not isinstance(group, dict):
                errors.append(f'{event}: invalid hook group.')
                continue
            if set(group) - {'matcher', 'hooks'}:
                errors.append(f'{event}: unexpected hook group options.')
            matchers = {'PreToolUse': 'Read|Write|Edit|MultiEdit|Bash',
                        'PostToolUse': 'Write|Edit|MultiEdit'}
            if event in matchers and group.get('matcher') != matchers[event]:
                errors.append(f'{event}: expected the reviewed tool matcher.')
            if event not in matchers and 'matcher' in group:
                errors.append(f'{event}: no matcher is used in this baseline.')
            handlers = group.get('hooks')
            if not isinstance(handlers, list) or len(handlers) != 1:
                errors.append(f'{event}: expected one nonempty command handler.')
                continue
            for hook in handlers:
                if not isinstance(hook, dict):
                    errors.append(f'{event}: invalid hook handler.')
                    continue
                expected_keys = {'type', 'command', 'args', 'timeout'}
                if event == 'PreToolUse':
                    expected_keys.add('onFailure')
                if set(hook) != expected_keys:
                    errors.append(f'{event}: unexpected or missing handler options; asynchronous enforcement is unsupported.')
                if hook.get('type') != 'command' or hook.get('command') != interpreter:
                    errors.append(f'{event}: only the local Python dispatcher is supported.')
                if hook.get('args') != ['${CLAUDE_PROJECT_DIR}/.claude/hooks/dispatch.py']:
                    errors.append(f'{event}: unexpected dispatcher arguments.')
                if not isinstance(hook.get('timeout'), int) or not 1 <= hook['timeout'] <= 10:
                    errors.append(f'{event}: hook needs a bounded timeout.')
                if event == 'PreToolUse' and hook.get('onFailure') != 'block':
                    errors.append('PreToolUse must block on startup failure/timeout.')
    for directory in ('skills', 'agents', 'rules'):
        found = list((root / '.claude' / directory).rglob('*.md'))
        if not found:
            errors.append(f'No project {directory} exist.')
        for path in found:
            text = path.read_text()
            if directory in {'skills', 'agents'}:
                if not text.startswith('---\n') or '\n---\n' not in text[4:]:
                    errors.append(f'{path.relative_to(root)}: missing frontmatter.')
                    continue
                header = text.split('---', 2)[1]
                if not any(line.startswith('name:') for line in header.splitlines()):
                    errors.append(f'{path.relative_to(root)}: missing name.')
                if not any(line.startswith('description:') for line in header.splitlines()):
                    errors.append(f'{path.relative_to(root)}: missing description.')
            if '${CLAUDE_PLUGIN_ROOT}' in text or 'ohmyorch:contract' in text:
                errors.append(f'{path.relative_to(root)}: unresolved upstream plugin dependency.')
    return errors
