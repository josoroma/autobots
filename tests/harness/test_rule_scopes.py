"""R-04: every path glob in a project rule matches a tracked file, so the rule loads for real code."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FRONTMATTER = re.compile(r'\A---\n(.*?)\n---\n', re.S)


def glob_pattern(glob: str) -> re.Pattern[str]:
    """`**/` matches no folder or several, `*` stays within one folder."""
    out, index = '', 0
    while index < len(glob):
        if glob.startswith('**/', index):
            out, index = out + '(?:.*/)?', index + 3
        elif glob.startswith('**', index):
            out, index = out + '.*', index + 2
        elif glob[index] == '*':
            out, index = out + '[^/]*', index + 1
        else:
            out, index = out + re.escape(glob[index]), index + 1
    return re.compile(out + r'\Z')


def scope_errors(rules: Path, files: list[str]) -> list[str]:
    errors = []
    for rule in sorted(rules.glob('*.md')):
        match = FRONTMATTER.match(rule.read_text())
        for glob in re.findall(r'^\s*-\s+"([^"]+)"', match.group(1), re.M) if match else ():
            if not any(glob_pattern(glob).match(path) for path in files):
                errors.append(f'{rule.name}: {glob} matches no tracked file')
    return errors


def tracked(root: Path) -> list[str]:
    return subprocess.run(['git', 'ls-files'], cwd=root, capture_output=True, text=True, check=True).stdout.split()


class RuleScopes(unittest.TestCase):
    def test_every_rule_glob_matches_a_tracked_file(self) -> None:
        self.assertEqual(scope_errors(ROOT / '.claude/rules', tracked(ROOT)), [])

    def test_a_glob_that_matches_nothing_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            rules = Path(folder)
            (rules / 'fixture.md').write_text('---\npaths:\n  - "apps/web/**/*"\n  - "services/agent/graphs/**/*"\n---\n')
            self.assertEqual(scope_errors(rules, ['apps/web/app/page.tsx']),
                             ['fixture.md: services/agent/graphs/**/* matches no tracked file'])

    def test_the_model_gateway_rule_covers_the_model_admission_adapter(self) -> None:
        text = (ROOT / '.claude/rules/model-gateway.md').read_text()
        globs = re.findall(r'^\s*-\s+"([^"]+)"', FRONTMATTER.match(text).group(1), re.M)
        path = 'services/agent/src/autobots/adapters/loop_middleware.py'
        self.assertTrue(any(glob_pattern(glob).match(path) for glob in globs))


if __name__ == '__main__':
    unittest.main()
