"""Static and fixture checks for shared instructions and the optional assistant adapter.

Link presence does not show a link is apt, and passing here shows nothing about whether
project rules load in a live session or whether events are delivered. Fixture adapter states
cover arranged conditions only. Allowlisted qualification literals make a later honest change
fail on purpose: recording qualification needs evidence and a deliberate change to the check.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import harness_lib  # noqa: E402
from harness_lib import activation_errors, adapter_status, config_errors, line_links, report_state, unfenced_lines  # noqa: E402
import verify  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


specs = load_module('autobots_specs_for_assets', ROOT / 'scripts/specs.py')
arrangement = load_module('autobots_forward_arrangement', ROOT / 'tests/harness/forward_arrangement.py')

STATES = {'inactive', 'configured_unqualified'}
SKILL_KEYS = {'name', 'description', 'disable-model-invocation', 'allowed-tools'}
AGENT_KEYS = {'name', 'description', 'tools', 'disallowedTools', 'model'}
RULE_KEYS = {'paths'}
READ_ONLY_TOOLS = {'Read', 'Grep', 'Glob'}
RETAINED_FIXTURE = ROOT / 'docs/engineering/evidence/HARNESS-ADAPT-001/forward-fixture'

# Representative paths are DH-03's repository structure. They show this matcher's reading of
# each glob; how the live client matches rule paths is not established here.
RULE_PATHS = {
    'contracts.md': ['contracts/generated/openapi.json', 'packages/api-client/index.ts',
                     'packages/db-types/index.ts', 'services/agent/src/autobots/contracts/run.py',
                     'services/agent/src/autobots/domain/run.py'],
    'database.md': ['supabase/migrations/0001_init.sql', 'packages/db-types/index.ts',
                    'services/agent/src/autobots/adapters/persistence/runs.py'],
    'infrastructure.md': ['infra/supabase/README.md', 'services/agent/Dockerfile',
                          'infra/supabase/docker-compose.yml', 'infra/supabase/docker-compose.yaml',
                          'scripts/operations/backup.sh'],
    'model-gateway.md': ['services/agent/src/autobots/adapters/models/gateway.py',
                         'services/agent/src/autobots/application/run.py',
                         'services/agent/src/autobots/graphs/run.py',
                         'apps/web/app/api/settings/route.ts',
                         'apps/web/src/app/api/settings/route.ts'],
    'nextjs.md': ['apps/web/app/page.tsx'],
    'python-worker.md': ['services/agent/pyproject.toml'],
}
UNRELATED_PATH = 'docs/engineering/work-items/US-1.2.md'


def frontmatter(text: str) -> dict[str, str] | None:
    """Top-level keys and their one-line values, or None without frontmatter."""
    if not text.startswith('---\n') or '\n---\n' not in text[4:]:
        return None
    header = text[4:].split('\n---\n', 1)[0]
    found = {}
    for line in header.splitlines():
        match = re.match(r'([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$', line)
        if match:
            found[match[1]] = match[2].strip()
    return found


def frontmatter_errors(root: Path) -> list[str]:
    errors = []
    for path in sorted((root / '.claude/skills').glob('*/SKILL.md')):
        keys = frontmatter(path.read_text()) or {}
        errors += [f'{path.relative_to(root)}: key {key}' for key in keys.keys() - SKILL_KEYS]
        if keys.get('name') != path.parent.name:
            errors.append(f'{path.relative_to(root)}: name does not match its directory.')
    for path in sorted((root / '.claude/agents').glob('*.md')):
        keys = frontmatter(path.read_text()) or {}
        errors += [f'{path.relative_to(root)}: key {key}' for key in keys.keys() - AGENT_KEYS]
        if keys.get('name') != path.stem:
            errors.append(f'{path.relative_to(root)}: name does not match its file.')
        if 'model' in keys and keys['model'] != 'inherit':
            errors.append(f'{path.relative_to(root)}: model must be inherit.')
    for path in sorted((root / '.claude/rules').glob('*.md')):
        keys = frontmatter(path.read_text()) or {}
        errors += [f'{path.relative_to(root)}: key {key}' for key in keys.keys() - RULE_KEYS]
    return errors


def instruction_files(root: Path) -> list[Path]:
    return [root / 'AGENTS.md', root / 'CLAUDE.md',
            *sorted((root / '.claude/rules').glob('*.md')),
            *sorted((root / '.claude/skills').glob('*/SKILL.md')),
            *sorted((root / '.claude/agents').glob('*.md'))]


def broken_links(paths: list[Path], root: Path) -> list[str]:
    broken = []
    for path in paths:
        for line in unfenced_lines(path.read_text()):
            for target in line_links(line):
                parsed = urlsplit(target.removeprefix('<').removesuffix('>'))
                if parsed.scheme or parsed.netloc:
                    continue
                destination = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
                label = f'{path.relative_to(root)}: {target}'
                if not destination.is_file():
                    broken.append(label)
                elif parsed.fragment and destination.suffix == '.md' and unquote(parsed.fragment) not in (
                        specs.source_locations(destination.read_text())[0]):
                    broken.append(label)
    return broken


def rule_globs(text: str) -> list[str]:
    header = text[4:].split('\n---\n', 1)[0]
    return re.findall(r'^\s+-\s+"([^"]+)"\s*$', header, flags=re.MULTILINE)


def glob_matches(pattern: str, path: str) -> bool:
    expression = ''
    index = 0
    while index < len(pattern):
        if pattern.startswith('**/', index):
            expression += '(?:.*/)?'
            index += 3
        elif pattern.startswith('**', index):
            expression += '.*'
            index += 2
        elif pattern[index] == '*':
            expression += '[^/]*'
            index += 1
        else:
            expression += re.escape(pattern[index])
            index += 1
    return re.fullmatch(expression, path) is not None


def tool_set(text: str) -> set[str]:
    return {tool.strip() for tool in (frontmatter(text) or {}).get('tools', '').split(',')}


def ingestor_grammar_errors(text: str) -> list[str]:
    """The field-order sentence must name `Change:` directly after `Status:`, and preserve it."""
    errors = []
    sentence = re.search(r'in this order:[^\n]*', text)
    fields = re.findall(r'`([^`]+)`', sentence[0]) if sentence else []
    if fields[:2] != ['Status:', 'Change:']:
        errors.append('The story field order does not name `Change:` directly after `Status:`.')
    if re.search(r'[Pp]reserve an existing `Change:`', text) is None:
        errors.append('Nothing tells the ingestor to preserve an existing `Change:` line.')
    return errors


def valid_root(directory: str) -> Path:
    """A synthetic root that passes `config_errors`, so each negative fixture changes one thing.

    It does not depend on the real rule content, which arrives through the protected-path
    procedure. Its settings and activation fields come from the real files.
    """
    root = Path(directory).resolve()
    for name in ('.claude/rules', '.claude/agents', '.claude/skills/autobots-verify-change',
                 '.claude/skills/autobots-review-change', 'scripts'):
        (root / name).mkdir(parents=True)
    config = json.loads((ROOT / '.claude/autobots.json').read_text())
    config['documents'] = {key: 'source.md' for key in config['documents']}
    (root / '.claude/autobots.json').write_text(json.dumps(config))
    shutil.copyfile(ROOT / '.claude/settings.json', root / '.claude/settings.json')
    (root / 'source.md').write_text('# Source\n')
    (root / 'PRD-Development-Harness.md').write_text('# PRD\n\n### DH-09.1. Work-item evidence contract\n')
    for name in ('verify.py', 'specs.py'):
        (root / 'scripts' / name).write_text('# fixture\n')
    for name in ('autobots-verify-change', 'autobots-review-change'):
        (root / f'.claude/skills/{name}/SKILL.md').write_text(f'---\nname: {name}\ndescription: Fixture.\n---\n\n# Skill\n')
    (root / '.claude/agents/autobots-reviewer.md').write_text(
        '---\nname: autobots-reviewer\ndescription: Fixture.\ntools: Read, Grep, Glob\nmodel: inherit\n---\n\n# Agent\n')
    (root / '.claude/rules/fixture.md').write_text(
        '---\npaths:\n  - "fixture/**/*"\n---\n\n# Rule\n\nChecked by [the runner](../../scripts/verify.py).\n')
    (root / 'AGENTS.md').write_text(valid_agents())
    return root


def valid_agents(extra: str = '', rows: tuple[str, ...] | None = None) -> str:
    link = '[`scripts/verify.py`](scripts/verify.py)'
    labels = rows if rows is not None else ('Opening paragraph', 'Work protocol',
                                            '`.claude/settings.json`', '`CLAUDE.md`')
    table = ''.join(f'| {label} | {link} | none |\n' for label in labels)
    return ('# Contract\n\nOpening.\n\n## Work protocol\n\n- A rule.\n\n' + extra
            + '## Rule checks and review\n\n| Source | Check | Review |\n|---|---|---|\n' + table)


def edit_json(path: Path, change) -> None:
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


def write_stub(directory: Path, body: str, *, name: str = 'claude') -> tuple[Path, Path]:
    """A fake CLI recording its arguments. It is the only `claude` these tests run."""
    record = directory / f'{name}.args'
    stub = directory / name
    stub.write_text(f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> "{record}"\n{body}\n')
    stub.chmod(0o755)
    return stub, record


def version_stub(directory: Path, version: str = '2.1.314') -> tuple[Path, Path]:
    return write_stub(directory, f"printf '{version} (Claude Code)\\n'")


def specs_cli(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / 'scripts/specs.py'), *arguments],
                          capture_output=True, text=True, timeout=30)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def story_body(text: str, identifier: str) -> str:
    match = re.search(rf'^### {re.escape(identifier)}:.*?(?=^### |\Z)', text, flags=re.MULTILINE | re.DOTALL)
    return match[0]


class RuleLinkTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = valid_root(temporary.name)
        self.rule = self.root / '.claude/rules/fixture.md'

    def test_valid_fixture_has_no_errors(self):
        self.assertEqual(config_errors(self.root), [])

    def test_each_allowed_target_counts(self):
        for target in ('../../scripts/verify.py', '../../scripts/specs.py', 
                       '../skills/autobots-verify-change/SKILL.md', '../skills/autobots-review-change/SKILL.md',
                       '../agents/autobots-reviewer.md',
                       '../../PRD-Development-Harness.md#dh-091-work-item-evidence-contract'):
            with self.subTest(target=target):
                self.rule.write_text(f'# Rule\n\nSee [target]({target}).\n')
                self.assertEqual(config_errors(self.root), [])

    def test_rule_without_allowed_link_fails(self):
        cases = {
            'no link': '# Rule\n\nNo link.\n',
            'non-DH-W PRD anchor': '# Rule\n\nSee [DH-07](../../PRD-Development-Harness.md'
                                   '#dh-07-supabase-migrations-seeds-and-database-quality).\n',
            'PRD without anchor': '# Rule\n\nSee [PRD](../../PRD-Development-Harness.md).\n',
            'other file': '# Rule\n\nSee [source](../../source.md).\n',
            'missing file': '# Rule\n\nSee [runner](../../scripts/absent.py).\n',
            'named in prose only': '# Rule\n\nSee scripts/verify.py and `autobots-review-change`.\n',
            'inside inline code': '# Rule\n\nSee `[runner](../../scripts/verify.py)`.\n',
            'inside a fence': '# Rule\n\n```text\n[runner](../../scripts/verify.py)\n```\n',
            'external': '# Rule\n\nSee [runner](https://example.invalid/scripts/verify.py).\n',
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self.rule.write_text(text)
                errors = config_errors(self.root)
                self.assertEqual(errors, ['.claude/rules/fixture.md: no Markdown link to an allowed check or review target.'])

    def test_removed_target_invalidates_the_link(self):
        (self.root / 'scripts/verify.py').unlink()
        self.assertTrue(any('no Markdown link' in error for error in config_errors(self.root)))

    def test_outside_the_root_does_not_count(self):
        self.rule.write_text('# Rule\n\nSee [runner](../../../scripts/verify.py).\n')
        self.assertTrue(any('no Markdown link' in error for error in config_errors(self.root)))


class AgentsMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = valid_root(temporary.name)
        self.agents = self.root / 'AGENTS.md'

    def test_mapping_heading_is_exempt_from_needing_a_row(self):
        self.assertEqual(config_errors(self.root), [])

    def test_missing_file(self):
        self.agents.unlink()
        self.assertTrue(any('AGENTS.md: unreadable' in error for error in config_errors(self.root)))

    def test_missing_mapping_section(self):
        self.agents.write_text('# Contract\n\n## Work protocol\n\n- A rule.\n')
        self.assertEqual(config_errors(self.root), ['AGENTS.md: missing the "## Rule checks and review" section.'])

    def test_row_with_only_a_disallowed_link(self):
        text = self.agents.read_text().replace(
            '| Work protocol | [`scripts/verify.py`](scripts/verify.py) | none |',
            '| Work protocol | [source](source.md) | none |')
        self.agents.write_text(text)
        self.assertEqual(config_errors(self.root), ['AGENTS.md: row "Work protocol" has no link to an allowed check or review target.'])

    def test_row_naming_a_target_only_in_prose(self):
        text = self.agents.read_text().replace(
            '| Work protocol | [`scripts/verify.py`](scripts/verify.py) | none |',
            '| Work protocol | `scripts/verify.py` | none |')
        self.agents.write_text(text)
        self.assertEqual(config_errors(self.root), ['AGENTS.md: row "Work protocol" has no link to an allowed check or review target.'])

    def test_link_in_the_first_cell_does_not_count(self):
        text = self.agents.read_text().replace(
            '| Work protocol | [`scripts/verify.py`](scripts/verify.py) | none |',
            '| [Work protocol](scripts/verify.py) | none | none |')
        self.agents.write_text(text)
        self.assertEqual(config_errors(self.root), ['AGENTS.md: row "Work protocol" has no link to an allowed check or review target.'])

    def test_new_heading_with_no_row(self):
        self.agents.write_text(valid_agents(extra='## New rules\n\n- Another rule.\n\n'))
        self.assertEqual(config_errors(self.root), ['AGENTS.md: no mapping row for "New rules".'])

    def test_heading_after_the_mapping_section_needs_a_row(self):
        self.agents.write_text(valid_agents() + '\n## Later rules\n\n- Another rule.\n')
        self.assertEqual(config_errors(self.root), ['AGENTS.md: no mapping row for "Later rules".'])

    def test_each_required_row(self):
        everything = ('Opening paragraph', 'Work protocol', '`.claude/settings.json`', '`CLAUDE.md`')
        for missing in ('Opening paragraph', '.claude/settings.json', 'CLAUDE.md'):
            with self.subTest(missing=missing):
                rows = tuple(row for row in everything if row.replace('`', '') != missing)
                self.agents.write_text(valid_agents(rows=rows))
                self.assertEqual(config_errors(self.root), [f'AGENTS.md: no mapping row for "{missing}".'])

    def test_a_heading_in_a_fence_needs_no_row(self):
        self.agents.write_text(valid_agents(extra='```text\n## Not a heading\n```\n\n'))
        self.assertEqual(config_errors(self.root), [])


class AdapterStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        (base / 'root').mkdir()
        (base / 'bin').mkdir()
        self.root = valid_root(str(base / 'root'))
        self.bin = base / 'bin'

    def status(self, stub: Path, **arguments) -> dict:
        return adapter_status(self.root, lookup=lambda name: str(stub) if name == 'claude' else None, **arguments)

    def assert_status(self, status: dict, state: str, reason: str) -> None:
        # Whole values: `inactive` contains "active", and `configured_unqualified` contains "qualified".
        self.assertEqual(status['state'], state)
        self.assertEqual(status['reason'], reason)
        self.assertIn(status['state'], STATES)
        self.assertEqual(status['model_route'], 'not_checked')

    def test_empty_lookup_is_inactive(self):
        self.assert_status(adapter_status(self.root, lookup=lambda name: None), 'inactive', 'unavailable')

    def test_process_path_decides_availability(self):
        stub, record = version_stub(self.bin)
        with mock.patch.dict(os.environ, {'PATH': str(self.bin)}):
            status = adapter_status(self.root)
        self.assert_status(status, 'configured_unqualified', 'delivery_unverified')
        self.assertEqual(record.read_text(), '--version\n')
        empty = self.bin / 'empty'
        empty.mkdir()
        with mock.patch.dict(os.environ, {'PATH': str(empty)}):
            self.assert_status(adapter_status(self.root), 'inactive', 'unavailable')

    def test_versions_compare_numerically(self):
        cases = {'2.1.200': ('inactive', 'version_below_minimum'),
                 '2.1.99': ('inactive', 'version_below_minimum'),
                 '2.1.295': ('configured_unqualified', 'delivery_unverified'),
                 '2.1.314': ('configured_unqualified', 'delivery_unverified'),
                 '2.1.1000': ('configured_unqualified', 'delivery_unverified')}
        for version, (state, reason) in cases.items():
            with self.subTest(version=version):
                stub, record = version_stub(self.bin, version)
                record.unlink(missing_ok=True)
                status = self.status(stub)
                self.assert_status(status, state, reason)
                self.assertEqual(status['observed_version'], version)
                self.assertEqual(status['minimum_version'], '2.1.295')
                self.assertEqual(record.read_text(), '--version\n')

    def test_failing_and_unparsable_versions(self):
        cases = {'failing': 'exit 3', 'failing with a version': "printf '2.1.314 (Claude Code)\\n'; exit 3",
                 'unparsable': "printf 'not a version\\n'", 'two parts': "printf '2.1 (Claude Code)\\n'",
                 'suffix': "printf '2.1.314-beta (Claude Code)\\n'", 'empty': ':'}
        for name, body in cases.items():
            with self.subTest(case=name):
                stub, record = write_stub(self.bin, body)
                record.unlink(missing_ok=True)
                status = self.status(stub)
                self.assert_status(status, 'inactive', 'version_unknown')
                self.assertNotIn('observed_version', status)
                self.assertEqual(record.read_text(), '--version\n')

    def test_unstartable_command_is_unknown(self):
        stub = self.bin / 'claude'
        stub.write_text('not a program\n')
        stub.chmod(0o644)
        self.assert_status(self.status(stub), 'inactive', 'version_unknown')

    def test_hanging_command_returns_promptly_and_leaves_nothing_running(self):
        pid_file = self.bin / 'pid'
        stub, record = write_stub(self.bin, f'echo $$ > "{pid_file}"\nsleep 30')
        began = time.monotonic()
        status = self.status(stub, timeout=0.3)
        self.assertLess(time.monotonic() - began, 5)
        self.assert_status(status, 'inactive', 'version_unknown')
        self.assertEqual(record.read_text(), '--version\n')
        group = int(pid_file.read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.killpg(group, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            self.fail('The stub process group is still running.')

    def test_probe_environment_carries_no_inherited_credential(self):
        seen = self.bin / 'seen'
        stub, _ = write_stub(self.bin, f'printf "%s" "${{AUTOBOTS_SENTINEL_CREDENTIAL-unset}}" > "{seen}"\n'
                                       "printf '2.1.314 (Claude Code)\\n'")
        with mock.patch.dict(os.environ, {'AUTOBOTS_SENTINEL_CREDENTIAL': 'present'}):
            self.status(stub)
        self.assertEqual(seen.read_text(), 'unset')

    def test_executable_path_is_not_recorded(self):
        stub, _ = version_stub(self.bin)
        status = self.status(stub)
        self.assertEqual(set(status), {'state', 'reason', 'minimum_version', 'observed_version', 'model_route'})
        self.assertNotIn(str(self.bin), json.dumps(status))

    def test_first_matching_condition_wins(self):
        stub, record = version_stub(self.bin, '2.1.200')
        edit_json(self.root / '.claude/autobots.json', lambda data: data['assistant'].pop('minimum_version_for_blocking_hook_failure'))
        (self.root / 'AGENTS.md').unlink()
        self.assert_status(adapter_status(self.root, lookup=lambda name: None), 'inactive', 'unavailable')
        self.assert_status(self.status(stub), 'inactive', 'minimum_unknown')
        self.assertFalse(record.exists())

    def test_invalid_configuration_is_inactive_and_runs_nothing(self):
        stub, record = version_stub(self.bin)
        (self.root / 'AGENTS.md').unlink()
        self.assert_status(self.status(stub), 'inactive', 'configuration_invalid')
        self.assertFalse(record.exists())

    def test_unreadable_configuration_is_inactive(self):
        stub, _ = version_stub(self.bin)
        (self.root / '.claude/autobots.json').write_text('{bad')
        self.assert_status(self.status(stub), 'inactive', 'minimum_unknown')


class ActivationRefusalTests(unittest.TestCase):
    """Each negative configuration gives errors and an inactive adapter, with a compatible stub."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()

    def fresh(self, name: str) -> tuple[Path, Path, Path]:
        directory = self.base / re.sub(r'\W', '_', name)
        (directory / 'root').mkdir(parents=True)
        (directory / 'bin').mkdir()
        stub, record = version_stub(directory / 'bin')
        return valid_root(str(directory / 'root')), stub, record

    def assert_refused(self, name: str, file: str, change, expected_error: str, reason: str) -> None:
        with self.subTest(case=name):
            root, stub, record = self.fresh(name)
            self.assertEqual(config_errors(root), [])
            edit_json(root / file, change)
            errors = config_errors(root)
            self.assertTrue(any(expected_error in error for error in errors), errors)
            status = adapter_status(root, lookup=lambda _: str(stub))
            self.assertEqual(status['state'], 'inactive')
            self.assertEqual(status['reason'], reason)
            self.assertFalse(record.exists())

    def test_qualification_claims(self):
        config = '.claude/autobots.json'
        for value in ('not_tested_but_active', 'qualified', 'active', '', None):
            self.assert_refused(f'assistant {value}', config,
                                lambda data, v=value: data['assistant'].__setitem__('event_delivery_qualification', v),
                                'assistant.event_delivery_qualification', 'configuration_invalid')
        for value in ('not_qualified_one_pretooluse_event_observed_but_active', 'qualified', 'not_tested', None):
            self.assert_refused(f'plugin {value}', config,
                                lambda data, v=value: data['upstream']['delivery_plugin'].__setitem__('event_delivery_qualification', v),
                                'upstream.delivery_plugin.event_delivery_qualification', 'configuration_invalid')
        self.assert_refused('assistant removed', config, lambda data: data['assistant'].pop('event_delivery_qualification'),
                            'assistant.event_delivery_qualification', 'configuration_invalid')
        self.assert_refused('plugin removed', config, lambda data: data['upstream'].pop('delivery_plugin'),
                            'upstream.delivery_plugin.event_delivery_qualification', 'configuration_invalid')

    def test_model_configuration(self):
        config = '.claude/autobots.json'
        self.assert_refused('model changed', config, lambda data: data['assistant'].__setitem__('model_configuration', 'changed'),
                            'assistant.model_configuration', 'configuration_invalid')
        self.assert_refused('model removed', config, lambda data: data['assistant'].pop('model_configuration'),
                            'assistant.model_configuration', 'configuration_invalid')

    def test_minimum_version(self):
        config = '.claude/autobots.json'
        key = 'minimum_version_for_blocking_hook_failure'
        self.assert_refused('minimum removed', config, lambda data: data['assistant'].pop(key), key, 'minimum_unknown')
        for value in ('2.1', 'latest', '2.1.295-beta', '', 2, None):
            self.assert_refused(f'minimum {value}', config,
                                lambda data, v=value: data['assistant'].__setitem__(key, v), key, 'minimum_unknown')

    def test_prompt_and_agent_hooks(self):
        for event in ('PreToolUse', 'Stop'):
            for kind in ('prompt', 'agent'):
                self.assert_refused(f'{event} {kind}', '.claude/settings.json',
                                    lambda data, e=event, k=kind: data['hooks'][e][0]['hooks'][0].__setitem__('type', k),
                                    'only the local Python dispatcher', 'configuration_invalid')

    def test_model_env_and_permissions_settings(self):
        for key, value in (('model', 'fixture-model'), ('env', {'FIXTURE': '1'}), ('permissions', {'allow': ['Bash']})):
            self.assert_refused(f'settings {key}', '.claude/settings.json',
                                lambda data, k=key, v=value: data.__setitem__(k, v),
                                'only the reviewed hooks', 'configuration_invalid')

    def test_real_activation_fields_pass_unedited(self):
        self.assertEqual(activation_errors(json.loads((ROOT / '.claude/autobots.json').read_text())), [])


class ReportTests(unittest.TestCase):
    def test_runner_records_status_and_report_state_still_accepts_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = valid_root(directory)

            def passing_check(_root, name, argv):
                return {'id': name, 'class': 'static_or_fixture', 'model_transport': 'none', 'command_argv': argv,
                        'exit_code': 0, 'status': 'passed', 'output': 'Ran 1 test\n'}

            output = io.StringIO()
            with (mock.patch.object(verify, 'project_root', lambda: root),
                  mock.patch.object(verify, 'run_check', passing_check),
                  mock.patch.object(verify, 'adapter_status',
                                    lambda path: harness_lib.adapter_status(path, lookup=lambda _: None)),
                  mock.patch.object(sys, 'argv', ['verify.py', '--profile', 'harness']),
                  contextlib.redirect_stdout(output)):
                code = verify.main()
            self.assertEqual(code, 0)
            summary = json.loads(output.getvalue())
            self.assertEqual(summary['assistant_adapter'], {'state': 'inactive', 'reason': 'unavailable'})
            report = json.loads((root / '.checks/harness/latest.json').read_text())
            self.assertEqual(report['assistant_adapter'], {'state': 'inactive', 'reason': 'unavailable',
                                                           'minimum_version': '2.1.295', 'model_route': 'not_checked'})
            self.assertEqual(len(report['checks']), 3)
            self.assertIn('Claude event delivery', report['not_tested'])
            self.assertTrue(report_state(root)[0])


class InstructionAssetTests(unittest.TestCase):
    def test_real_project_configuration_has_no_errors(self):
        """The real tree keeps its rule links, AGENTS.md mapping and activation fields."""
        self.assertEqual(config_errors(ROOT), [])

    def test_real_links_resolve_including_fragments(self):
        self.assertEqual(broken_links(instruction_files(ROOT), ROOT), [])

    def test_broken_links_are_found(self):
        with tempfile.TemporaryDirectory() as directory:
            root = valid_root(directory)
            rule = root / '.claude/rules/fixture.md'
            for target in ('../../absent.md', '../../PRD-Development-Harness.md#absent-heading'):
                with self.subTest(target=target):
                    rule.write_text(f'# Rule\n\n[target]({target})\n')
                    self.assertEqual(broken_links([rule], root), [f'.claude/rules/fixture.md: {target}'])
            rule.write_text('# Rule\n\n[DH-W](../../PRD-Development-Harness.md#dh-091-work-item-evidence-contract) '
                            '[external](https://example.invalid/absent)\n\n```text\n[fenced](absent.md)\n```\n')
            self.assertEqual(broken_links([rule], root), [])

    def test_real_frontmatter_uses_only_allowed_keys_and_matching_names(self):
        self.assertEqual(frontmatter_errors(ROOT), [])
        self.assertEqual(len(list((ROOT / '.claude/skills').glob('*/SKILL.md'))), 13)
        self.assertEqual(len(list((ROOT / '.claude/agents').glob('*.md'))), 7)

    def test_frontmatter_faults_are_found(self):
        cases = [('.claude/skills/autobots-verify-change/SKILL.md',
                  '---\nname: autobots-verify-change\ndescription: Fixture.\ncontext: fork\n---\n', 'key context'),
                 ('.claude/skills/autobots-verify-change/SKILL.md',
                  '---\nname: other-name\ndescription: Fixture.\n---\n', 'name does not match'),
                 ('.claude/agents/autobots-reviewer.md',
                  '---\nname: autobots-reviewer\ndescription: Fixture.\ncolor: red\n---\n', 'key color'),
                 ('.claude/agents/autobots-reviewer.md',
                  '---\nname: other-name\ndescription: Fixture.\n---\n', 'name does not match'),
                 ('.claude/agents/autobots-reviewer.md',
                  '---\nname: autobots-reviewer\ndescription: Fixture.\nmodel: fixture-model\n---\n', 'model must be inherit'),
                 ('.claude/rules/fixture.md', '---\nglobs:\n  - "x/**"\n---\n', 'key globs')]
        for file, text, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = valid_root(directory)
                self.assertEqual(frontmatter_errors(root), [])
                (root / file).write_text(text)
                errors = frontmatter_errors(root)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(expected, errors[0])

    def test_real_rule_paths_match_representative_paths_only(self):
        scoped = {path.name: rule_globs(path.read_text()) for path in (ROOT / '.claude/rules').glob('*.md')
                  if (frontmatter(path.read_text()) or {}).keys() >= {'paths'}}
        self.assertEqual(scoped.keys(), RULE_PATHS.keys())
        for name, globs in scoped.items():
            self.assertTrue(globs, name)
            for representative in RULE_PATHS[name]:
                with self.subTest(rule=name, path=representative):
                    self.assertTrue(any(glob_matches(glob, representative) for glob in globs))
            for glob in globs:
                with self.subTest(rule=name, glob=glob):
                    self.assertTrue(any(glob_matches(glob, path) for path in RULE_PATHS[name]),
                                    'A glob with no representative path is untested.')
                    self.assertFalse(glob_matches(glob, UNRELATED_PATH))

    def test_glob_reading(self):
        self.assertTrue(glob_matches('**/Dockerfile*', 'Dockerfile'))
        self.assertTrue(glob_matches('**/Dockerfile*', 'a/b/Dockerfile.dev'))
        self.assertTrue(glob_matches('apps/web/**/*', 'apps/web/page.tsx'))
        self.assertFalse(glob_matches('apps/web/**/*', 'apps/webby/page.tsx'))
        self.assertFalse(glob_matches('**/*compose*.yml', 'compose.yaml'))

    def test_repeated_facts_agree(self):
        config = json.loads((ROOT / '.claude/autobots.json').read_text())
        project = json.loads((ROOT / '.claude/ohmyorch/project.json').read_text())
        commit = config['upstream']['commit']
        self.assertRegex(commit, r'^[0-9a-f]{40}$')
        for path in ('.claude/skills/autobots-spec-ingest/SKILL.md', '.claude/agents/autobots-spec-ingestor.md'):
            pins = re.findall(r'OhMyOrch/blob/([0-9a-f]+)/', (ROOT / path).read_text())
            self.assertTrue(pins, path)
            self.assertEqual(set(pins), {commit}, path)
        self.assertEqual(config['documents']['specs'], project['documents']['specs'])
        self.assertEqual(config['documents']['codebase'], project['documents']['codebase'])
        self.assertEqual(config['documents']['product'], project['documents']['prd'])

    def test_configured_profiles_match_the_runner(self):
        import verify
        declared = json.loads((ROOT / '.claude/autobots.json').read_text())['verification']
        self.assertEqual(tuple(declared['implemented_profiles']), verify.IMPLEMENTED_PROFILES)
        self.assertEqual(declared['pending_profiles'], [])


class IngestionAssetTests(unittest.TestCase):
    def test_real_ingestor_story_grammar_names_change(self):
        """`specs.py` accepts `Change:` as prose, so validating a backlog proves nothing about this wording."""
        self.assertEqual(ingestor_grammar_errors((ROOT / '.claude/agents/autobots-spec-ingestor.md').read_text()), [])

    def test_base_grammar_wording_is_refused(self):
        base = 'Each story contains, in this order: `Status:`, `As a` / `I want` / `So that`, `Source:`.\n'
        self.assertEqual(len(ingestor_grammar_errors(base)), 2)
        late = 'Each story contains, in this order: `Status:`, `Source:`, `Change:`. Preserve an existing `Change:` line.\n'
        self.assertEqual(len(ingestor_grammar_errors(late)), 1)

    def test_read_only_agents_have_only_read_tools(self):
        for name in ('autobots-spec-ingestor', 'autobots-reviewer', 'autobots-architect'):
            with self.subTest(agent=name):
                text = (ROOT / f'.claude/agents/{name}.md').read_text()
                self.assertEqual(tool_set(text), READ_ONLY_TOOLS)
                self.assertNotIn('disallowedTools', frontmatter(text))

    def test_paired_skill_owns_persistence_render_and_validate(self):
        skill = (ROOT / '.claude/skills/autobots-spec-ingest/SKILL.md').read_text()
        ingestor = (ROOT / '.claude/agents/autobots-spec-ingestor.md').read_text()
        self.assertIn('Delegate to `autobots-spec-ingestor`', skill)
        self.assertIn('Write only the mapped SPECS artifact', skill)
        self.assertIn('scripts/specs.py render --path', skill)
        self.assertIn('scripts/specs.py validate --path', skill)
        self.assertIn('the invoking `autobots-spec-ingest` skill owns persistence and validation', ingestor)
        self.assertNotIn('specs.py', ingestor)

    def test_retained_fixture_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / 'copy'
            shutil.copytree(RETAINED_FIXTURE, copy)
            arguments = ('--project-root', str(copy), '--path', 'SPECS.md')
            self.assertEqual(specs_cli('validate', *arguments).returncode, 0)
            before = sha256(copy / 'SPECS.md')
            self.assertEqual(specs_cli('render', *arguments).returncode, 0)
            self.assertEqual(sha256(copy / 'SPECS.md'), before)
            text = (copy / 'SPECS.md').read_text()
            self.assertNotRegex(text, r'(?m)^Status: DONE')
            self.assertIn('Status: NEEDS CLARIFICATION', story_body(text, 'US-1.3'))
            self.assertIn('Status: BLOCKED', story_body(text, 'US-1.4'))


class ArrangementTests(unittest.TestCase):
    def setUp(self) -> None:
        checks = ROOT / '.checks'
        checks.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=checks, prefix='arrangement-test-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)

    def test_arranged_copy(self):
        copy = arrangement.arrange(self.base / 'nested/run')
        arguments = ('--project-root', str(copy), '--path', 'SPECS.md')
        self.assertEqual(specs_cli('validate', *arguments).returncode, 0)
        before = sha256(copy / 'SPECS.md')
        self.assertEqual(specs_cli('render', *arguments).returncode, 0)
        self.assertEqual(sha256(copy / 'SPECS.md'), before)
        text = (copy / 'SPECS.md').read_text()
        self.assertEqual(re.findall(r'(?m)^\| \[(SP-\d+)\]\([^)]+\) \| (US-[\d.]+) \|$', text),
                         [('SP-901', 'US-1.1'), ('SP-902', 'US-1.3')])
        self.assertNotIn('No `AGENTS.md` file exists', text)
        self.assertIn('CONTRACT.md#sp-901-missing-key-draft-preservation', story_body(text, 'US-1.1'))
        self.assertIn('CONTRACT.md#sp-902-retry-visibility', story_body(text, 'US-1.3'))
        self.assertIn('Status: READY', story_body(text, 'US-1.1'))
        self.assertIn('Status: IN PROGRESS\nChange: `openspec/changes/fixture-us-1-2/`\n', story_body(text, 'US-1.2'))
        self.assertIn('Status: NEEDS CLARIFICATION', story_body(text, 'US-1.3'))
        self.assertIn('Dependencies:\n- US-1.2\n', story_body(text, 'US-1.3'))
        self.assertIn('Status: BLOCKED', story_body(text, 'US-1.4'))
        self.assertIn('US_1_2 -.-> US_1_3', text)
        self.assertIn('When the composer draft changes', (copy / 'PRD.md').read_text())
        self.assertEqual(len(re.findall(r'(?m)^## SP-', (copy / 'CONTRACT.md').read_text())), 2)
        self.assertEqual(len((copy / 'AGENTS.md').read_text().splitlines()), 1)
        self.assertTrue((copy / '.claude/autobots.json').is_file())

    def test_arrangement_is_reproducible(self):
        first = arrangement.arrange(self.base / 'first')
        second = arrangement.arrange(self.base / 'second')
        names = sorted(path.relative_to(first) for path in first.rglob('*') if path.is_file())
        self.assertEqual(names, sorted(path.relative_to(second) for path in second.rglob('*') if path.is_file()))
        for name in names:
            self.assertEqual(sha256(first / name), sha256(second / name), name)

    def test_refuses_an_existing_destination(self):
        destination = self.base / 'exists'
        destination.mkdir()
        (destination / 'kept').write_text('kept')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            arrangement.arrange(destination)
        self.assertEqual((destination / 'kept').read_text(), 'kept')

    def test_refuses_a_destination_outside_checks(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaisesRegex(ValueError, 'must lie under'):
                arrangement.arrange(Path(outside) / 'run')
            self.assertFalse((Path(outside) / 'run').exists())
        with self.assertRaisesRegex(ValueError, 'must lie under'):
            arrangement.arrange(ROOT / '.checks')

    def test_command_line_refusal_exits_nonzero(self):
        destination = self.base / 'exists'
        destination.mkdir()
        result = subprocess.run([sys.executable, str(ROOT / 'tests/harness/forward_arrangement.py'), str(destination)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 2)
        self.assertIn('already exists', result.stderr)

    def test_missing_anchor_fails_and_leaves_no_destination(self):
        fixture = self.base / 'fixture'
        shutil.copytree(RETAINED_FIXTURE, fixture)
        specs_file = fixture / 'SPECS.md'
        specs_file.write_text(specs_file.read_text().replace('### US-1.2: Store application records locally\n\nStatus: READY',
                                                             '### US-1.2: Store application records locally\n\nStatus: BLOCKED'))
        destination = self.base / 'run'
        with self.assertRaisesRegex(ValueError, 'anchor'):
            arrangement.arrange(destination, fixture=fixture)
        self.assertFalse(destination.exists())
        self.assertEqual([path.name for path in self.base.iterdir() if path.name.startswith('.arranging-')], [])


if __name__ == '__main__':
    unittest.main()
