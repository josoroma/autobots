"""The real instruction files and the checks over them, with known-good and known-bad fixtures
(scripts/instruction_checks.py, PRD-Development-Harness DH-09).

Link presence does not show a link is apt, and passing here shows nothing about whether project rules load in a
live session. Split from test_assistant_assets.py, which also held the checks themselves (refactor plan R-66,
THRN-04, THRN-05).
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from harness_support import (
    ROOT,
    HarnessTestCase,
    config_errors,
    instruction_checks,
    sha256,
    specs_cli,
    story_body,
    valid_root,
    verify,
)

broken_links, frontmatter_errors, glob_matches = instruction_checks.broken_links, instruction_checks.frontmatter_errors, instruction_checks.glob_matches
ingestor_grammar_errors, instruction_files = instruction_checks.ingestor_grammar_errors, instruction_checks.instruction_files
parse_frontmatter, rule_globs, tool_set = instruction_checks.parse_frontmatter, instruction_checks.rule_globs, instruction_checks.tool_set
READ_ONLY_TOOLS = {'Read', 'Grep', 'Glob'}
RETAINED_FIXTURE = ROOT / 'docs/engineering/evidence/HARNESS-ADAPT-001/forward-fixture'

# Representative paths are DH-03's repository structure. They show this matcher's reading of
# each glob; how the live client matches rule paths is not established here.
RULE_PATHS = {
    'contracts.md': ['contracts/generated/openapi.json', 'packages/api-client/index.ts',
                     'packages/db-types/index.ts', 'services/agent/src/autobots/contracts/run.py',
                     'services/agent/src/autobots/domain/run.py'],
    'database.md': ['supabase/migrations/0001_init.sql', 'packages/db-types/index.ts',
                    'services/agent/src/autobots/persistence/runs.py'],
    'infrastructure.md': ['infra/supabase/README.md', 'infra/browser/proxy.Dockerfile',
                          'infra/supabase/docker-compose.yml', 'infra/supabase/docker-compose.yaml',
                          'scripts/qualify_operations.py', 'scripts/qualify_backup.py', 'scripts/qualify_upgrade.py',
                          'Makefile', 'scripts/persistent_install.py', 'scripts/local_backup.py'],
    'model-gateway.md': ['services/agent/src/autobots/adapters/models/gateway.py',
                         'services/agent/src/autobots/application/run.py',
                         'services/agent/src/autobots/adapters/loop_middleware.py',
                         'apps/web/app/api/settings/route.ts'],
    'nextjs.md': ['apps/web/app/page.tsx'],
    'python-worker.md': ['services/agent/pyproject.toml'],
}
UNRELATED_PATH = 'docs/engineering/work-items/US-1.2.md'


class InstructionAssetTests(HarnessTestCase):
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
        # Pinned, so adding or removing a skill or an agent is reviewed here (THRN-19).
        self.assertEqual(len(list((ROOT / '.claude/skills').glob('*/SKILL.md'))), 13, 'the project has 13 skills')
        self.assertEqual(len(list((ROOT / '.claude/agents').glob('*.md'))), 7, 'the project has 7 agents')

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
                  if (parse_frontmatter(path.read_text()) or {}).keys() >= {'paths'}}
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
        declared = json.loads((ROOT / '.claude/autobots.json').read_text())['verification']
        self.assertEqual(tuple(declared['implemented_profiles']), verify.IMPLEMENTED_PROFILES)
        self.assertEqual(declared['pending_profiles'], [])


class IngestionAssetTests(HarnessTestCase):
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
                self.assertNotIn('disallowedTools', parse_frontmatter(text))

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


if __name__ == '__main__':
    unittest.main()
