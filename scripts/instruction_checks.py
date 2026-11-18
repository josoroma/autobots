"""Checks of the project's instruction files: skills, agents, rules, AGENTS.md and CLAUDE.md (refactor plan R-66, THRN-05).

One frontmatter parser serves every check here and `harness_lib.config_errors`, which reports what these find as
`project_configuration` errors (PRD-Development-Harness DH-05). tests/harness/test_instruction_assets.py holds
their known-good and known-bad fixtures. Standard library only.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from harness_lib import line_links, unfenced_lines

SKILL_KEYS = frozenset({'name', 'description', 'disable-model-invocation', 'allowed-tools'})
AGENT_KEYS = frozenset({'name', 'description', 'tools', 'disallowedTools', 'model'})
RULE_KEYS = frozenset({'paths'})
FRONTMATTER_KEY = re.compile(r'([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$')


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Top-level keys and their one-line values, or None without frontmatter. The header opens on the first line and
    ends at the next line that is `---` by itself, never at a `---` inside a value."""
    if not text.startswith('---\n') or '\n---\n' not in text[4:]:
        return None
    header = text[4:].split('\n---\n', 1)[0]
    found = {}
    for line in header.splitlines():
        match = FRONTMATTER_KEY.match(line)
        if match:
            found[match[1]] = match[2].strip()
    return found


def frontmatter_errors(root: Path) -> list[str]:
    """Keys outside each kind's allowed set, a name that differs from its path, and a model other than inherit."""
    errors = []
    for path in sorted((root / '.claude/skills').glob('*/SKILL.md')):
        keys = parse_frontmatter(path.read_text()) or {}
        errors += [f'{path.relative_to(root)}: key {key}' for key in sorted(keys.keys() - SKILL_KEYS)]
        if keys.get('name') != path.parent.name:
            errors.append(f'{path.relative_to(root)}: name does not match its directory.')
    for path in sorted((root / '.claude/agents').glob('*.md')):
        keys = parse_frontmatter(path.read_text()) or {}
        errors += [f'{path.relative_to(root)}: key {key}' for key in sorted(keys.keys() - AGENT_KEYS)]
        if keys.get('name') != path.stem:
            errors.append(f'{path.relative_to(root)}: name does not match its file.')
        if 'model' in keys and keys['model'] != 'inherit':
            errors.append(f'{path.relative_to(root)}: model must be inherit.')
    for path in sorted((root / '.claude/rules').glob('*.md')):
        keys = parse_frontmatter(path.read_text()) or {}
        errors += [f'{path.relative_to(root)}: key {key}' for key in sorted(keys.keys() - RULE_KEYS)]
    return errors


def instruction_files(root: Path) -> list[Path]:
    return [root / 'AGENTS.md', root / 'CLAUDE.md',
            *sorted((root / '.claude/rules').glob('*.md')),
            *sorted((root / '.claude/skills').glob('*/SKILL.md')),
            *sorted((root / '.claude/agents').glob('*.md'))]


def broken_links(paths: list[Path], root: Path) -> list[str]:
    """Each local link in `paths` whose file is missing, or whose fragment names no heading or anchor there."""
    # Loaded only when a fragment is checked, so this module stays light.
    from specs import source_locations

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
                        source_locations(destination.read_text())[0]):
                    broken.append(label)
    return broken


def broken_link_errors(root: Path) -> list[str]:
    """The broken links of every instruction file that exists, as configuration errors."""
    return [f'{label}: broken link.' for label in broken_links([path for path in instruction_files(root) if path.is_file()], root)]


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
    return {tool.strip() for tool in (parse_frontmatter(text) or {}).get('tools', '').split(',')}


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
