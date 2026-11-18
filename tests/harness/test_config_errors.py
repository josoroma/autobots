"""project_configuration: config_errors over a synthetic valid root, one change at a time (scripts/harness_lib.py).

Rule links, the AGENTS.md mapping, activation refusals, the hook settings and the instruction-file checks. Link
presence does not show a link is apt. Split from test_assistant_assets.py and test_hooks.py by the unit under
test (refactor plan R-66, THRN-03, THRN-04).
"""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

from harness_support import (
    ROOT,
    HarnessTestCase,
    activation_errors,
    adapter_status,
    config_errors,
    edit_json,
    valid_agents,
    valid_root,
    verify,
    version_stub,
)


def setting(*path: str | int, value: object) -> Callable[[Any], None]:
    """A change that sets the value at `path` in a JSON document."""
    def change(data: Any) -> None:
        for key in path[:-1]:
            data = data[key]
        data[path[-1]] = value
    return change


def removed(*path: str) -> Callable[[Any], None]:
    """A change that removes the key at `path` from a JSON document."""
    def change(data: Any) -> None:
        for key in path[:-1]:
            data = data[key]
        data.pop(path[-1])
    return change


class HookSettings(HarnessTestCase):
    """The hook configuration's own refusals, each one change from a valid root, so the whole list is asserted
    (THRN-09). Moved from test_hooks.py, whose roots held only the two JSON files."""

    def setUp(self) -> None:
        self.root = valid_root(self.enterContext(tempfile.TemporaryDirectory()))
        self.settings = json.loads((self.root / '.claude/settings.json').read_text())

    def write_settings(self) -> None:
        (self.root / '.claude/settings.json').write_text(json.dumps(self.settings))

    def test_empty_hook_groups_are_not_an_enabled_configuration(self):
        self.settings['hooks'] = {key: [] for key in self.settings['hooks']}
        self.write_settings()
        self.assertEqual(config_errors(self.root), [f'{event}: expected one nonempty hook group.' for event in self.settings['hooks']])

    def test_disabled_and_async_hook_configuration_is_rejected(self):
        self.settings['disableAllHooks'] = True
        self.write_settings()
        self.assertEqual(config_errors(self.root), ['Baseline settings permit only the reviewed hooks; disabling hooks or changing '
                                                    'model/env/permissions is unsupported.'])
        self.settings.pop('disableAllHooks')
        self.settings['hooks']['PreToolUse'][0]['hooks'][0]['async'] = True
        self.write_settings()
        self.assertEqual(config_errors(self.root), ['PreToolUse: unexpected or missing handler options; asynchronous enforcement '
                                                    'is unsupported.'])

    def test_missing_interpreter_is_a_configuration_error(self):
        edit_json(self.root / '.claude/autobots.json', setting('python_executable', value='/nonexistent/python3.12'))
        # The hooks still name the real interpreter, so each now differs from the configured one too.
        self.assertEqual(config_errors(self.root), ['Configure an existing absolute path to the qualified Python 3.12+ interpreter.',
                                                    *(f'{event}: only the local Python dispatcher is supported.' for event in self.settings['hooks'])])


class RuleLinkTests(HarnessTestCase):
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
                       '../../docs/PRD/PRD-Development-Harness.md#dh-091-work-item-evidence-contract'):
            with self.subTest(target=target):
                self.rule.write_text(f'# Rule\n\nSee [target]({target}).\n')
                self.assertEqual(config_errors(self.root), [])

    def test_rule_without_allowed_link_fails(self):
        cases = {
            'no link': '# Rule\n\nNo link.\n',
            'non-DH-W PRD anchor': '# Rule\n\nSee [DH-07](../../docs/PRD/PRD-Development-Harness.md'
                                   '#dh-07-supabase-migrations-seeds-and-database-quality).\n',
            'PRD without anchor': '# Rule\n\nSee [PRD](../../docs/PRD/PRD-Development-Harness.md).\n',
            'other file': '# Rule\n\nSee [source](../../source.md).\n',
            'missing file': '# Rule\n\nSee [runner](../../scripts/absent.py).\n',
            'named in prose only': '# Rule\n\nSee scripts/verify.py and `autobots-review-change`.\n',
            'inside inline code': '# Rule\n\nSee `[runner](../../scripts/verify.py)`.\n',
            'inside a fence': '# Rule\n\n```text\n[runner](../../scripts/verify.py)\n```\n',
            'external': '# Rule\n\nSee [runner](https://example.invalid/scripts/verify.py).\n',
        }
        # A target that doesn't resolve is also a broken link, which project_configuration reports first (THRN-05).
        broken = {'non-DH-W PRD anchor': '../../docs/PRD/PRD-Development-Harness.md#dh-07-supabase-migrations-seeds-and-database-quality',
                  'missing file': '../../scripts/absent.py'}
        for name, text in cases.items():
            with self.subTest(case=name):
                self.rule.write_text(text)
                errors = config_errors(self.root)
                self.assertEqual(errors, [*([f'.claude/rules/fixture.md: {broken[name]}: broken link.'] if name in broken else []),
                                          '.claude/rules/fixture.md: no Markdown link to an allowed check or review target.'])

    def test_removed_target_invalidates_the_link(self):
        (self.root / 'scripts/verify.py').unlink()
        self.assertMentions(config_errors(self.root), 'no Markdown link')

    def test_outside_the_root_does_not_count(self):
        self.rule.write_text('# Rule\n\nSee [runner](../../../scripts/verify.py).\n')
        self.assertMentions(config_errors(self.root), 'no Markdown link')


class AgentsMappingTests(HarnessTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = valid_root(temporary.name)
        self.agents = self.root / 'AGENTS.md'

    def test_mapping_heading_is_exempt_from_needing_a_row(self):
        self.assertEqual(config_errors(self.root), [])

    def test_missing_file(self):
        self.agents.unlink()
        self.assertMentions(config_errors(self.root), 'AGENTS.md: unreadable')

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


class ActivationRefusalTests(HarnessTestCase):
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
            self.assertMentions(errors, expected_error)
            status = adapter_status(root, lookup=lambda _: str(stub))
            self.assertEqual(status['state'], 'inactive')
            self.assertEqual(status['reason'], reason)
            self.assertFalse(record.exists())

    def test_qualification_claims(self):
        config = '.claude/autobots.json'
        for value in ('not_tested_but_active', 'qualified', 'active', '', None):
            self.assert_refused(f'assistant {value}', config,
                                setting('assistant', 'event_delivery_qualification', value=value),
                                'assistant.event_delivery_qualification', 'configuration_invalid')
        for value in ('not_qualified_one_pretooluse_event_observed_but_active', 'qualified', 'not_tested', None):
            self.assert_refused(f'plugin {value}', config,
                                setting('upstream', 'delivery_plugin', 'event_delivery_qualification', value=value),
                                'upstream.delivery_plugin.event_delivery_qualification', 'configuration_invalid')
        self.assert_refused('assistant removed', config, removed('assistant', 'event_delivery_qualification'),
                            'assistant.event_delivery_qualification', 'configuration_invalid')
        self.assert_refused('plugin removed', config, removed('upstream', 'delivery_plugin'),
                            'upstream.delivery_plugin.event_delivery_qualification', 'configuration_invalid')

    def test_model_configuration(self):
        config = '.claude/autobots.json'
        self.assert_refused('model changed', config, setting('assistant', 'model_configuration', value='changed'),
                            'assistant.model_configuration', 'configuration_invalid')
        self.assert_refused('model removed', config, removed('assistant', 'model_configuration'),
                            'assistant.model_configuration', 'configuration_invalid')

    def test_minimum_version(self):
        config = '.claude/autobots.json'
        key = 'minimum_version_for_blocking_hook_failure'
        self.assert_refused('minimum removed', config, removed('assistant', key), key, 'minimum_unknown')
        for value in ('2.1', 'latest', '2.1.295-beta', '', 2, None):
            self.assert_refused(f'minimum {value}', config,
                                setting('assistant', key, value=value), key, 'minimum_unknown')

    def test_prompt_and_agent_hooks(self):
        for event in ('PreToolUse', 'Stop'):
            for kind in ('prompt', 'agent'):
                self.assert_refused(f'{event} {kind}', '.claude/settings.json',
                                    setting('hooks', event, 0, 'hooks', 0, 'type', value=kind),
                                    'only the local Python dispatcher', 'configuration_invalid')

    def test_model_env_and_permissions_settings(self):
        for key, value in (('model', 'fixture-model'), ('env', {'FIXTURE': '1'}), ('permissions', {'allow': ['Bash']})):
            self.assert_refused(f'settings {key}', '.claude/settings.json',
                                setting(key, value=value),
                                'only the reviewed hooks', 'configuration_invalid')

    def test_real_activation_fields_pass_unedited(self):
        self.assertEqual(activation_errors(json.loads((ROOT / '.claude/autobots.json').read_text())), [])


class InstructionChecksReported(HarnessTestCase):
    """project_configuration reports what scripts/instruction_checks.py finds, as it reports every other
    configuration fault, so moving those checks out of the tests lost none (refactor plan R-66, THRN-05)."""

    def setUp(self) -> None:
        self.root = valid_root(self.enterContext(tempfile.TemporaryDirectory()))

    def test_a_frontmatter_fault_is_a_configuration_error(self):
        (self.root / '.claude/agents/autobots-reviewer.md').write_text(
            '---\nname: autobots-reviewer\ndescription: Fixture.\nmodel: fixture-model\n---\n\n# Agent\n')
        self.assertEqual(config_errors(self.root), ['.claude/agents/autobots-reviewer.md: model must be inherit.'])

    def test_a_broken_link_is_a_configuration_error(self):
        (self.root / 'AGENTS.md').write_text(valid_agents(extra='See [the plan](plan.md).\n\n'))
        self.assertEqual(config_errors(self.root), ['AGENTS.md: plan.md: broken link.'])

    def test_the_verifier_reports_them_under_project_configuration(self):
        (self.root / '.claude/rules/fixture.md').write_text(
            '---\npaths:\n  - "fixture/**/*"\nglobs: x\n---\n\n# Rule\n\nChecked by [the runner](../../scripts/verify.py).\n')
        with mock.patch.object(verify, 'run_check', lambda *_: {'id': 'other', 'status': 'passed'}):
            checks = verify.harness_checks(self.root)
        self.assertEqual(checks[0], {'id': 'project_configuration', **verify.classify('project_configuration'), 'status': 'failed',
                                     'errors': ['.claude/rules/fixture.md: key globs']})


if __name__ == '__main__':
    unittest.main()
