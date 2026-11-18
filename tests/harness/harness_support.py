"""What the harness tests share (refactor plan R-66: THRN-03, THRN-04, THRN-07, THRN-08, THRN-09, THRN-11).

It puts the repository's scripts on the path and loads the hook dispatcher once. It also gives one hardened Git
fixture recipe, stub executables, script copies and a child runner with a default timeout. A valid configuration
root and a passing harness report give each known-bad fixture exactly one change to make. A test case base names
the list an assertion searched. Standard library only, like the harness profile itself (AGENTS.md).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))

import harness_lib  # noqa: E402 - imported after the scripts path is added
import instruction_checks  # noqa: E402
import verify  # noqa: E402
from harness_lib import (  # noqa: E402
    activation_errors,
    adapter_status,
    config_errors,
    fingerprint,
    input_manifest,
    reduced_env,
    report_state,
)

# What the test modules import from here, so the scripts path is set before any script loads.
__all__ = [
    'CLI_TIMEOUT',
    'GIT_ENV',
    'ROOT',
    'HarnessTestCase',
    'activation_errors',
    'adapter_status',
    'config_errors',
    'copy_dispatcher',
    'copy_scripts',
    'edit_json',
    'executable_stub',
    'fingerprint',
    'fixture_repo',
    'git',
    'harness_lib',
    'harness_report',
    'hook',
    'input_manifest',
    'instruction_checks',
    'load_script',
    'reduced_env',
    'report_state',
    'run_cli',
    'sha256',
    'specs_cli',
    'story_body',
    'valid_agents',
    'valid_root',
    'verify',
    'version_stub',
    'write_stub',
]

# A child that hangs fails the test that started it, well inside the harness profile's own cap (THRN-07).
CLI_TIMEOUT = 30
# No global or system Git configuration reaches a fixture repository, so a developer's hooks, templates or signing
# never run inside one, whichever way the suite is started (THRN-08).
GIT_ENV = {**reduced_env(), 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}
GIT_OPTIONS = ('-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false',
               '-c', f'core.hooksPath={os.devnull}')
# The scripts a copied dispatcher needs beside it: harness_lib reads each profile's checks from the registry in
# qualification/ (R-65), and its configuration checks from instruction_checks.py.
DISPATCHER_SCRIPTS = ('scripts/harness_lib.py', 'scripts/instruction_checks.py', 'scripts/qualification')


def load_script(name: str, path: Path) -> ModuleType:
    """A script loaded as a module under `name`, registered so that what it defines can be pickled or patched."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


hook = load_script('autobots_hook', ROOT / '.claude/hooks/dispatch.py')


def run_cli(argv: Sequence[str], **options: Any) -> subprocess.CompletedProcess[Any]:
    """`subprocess.run` with its output captured, no check and CLI_TIMEOUT, unless the caller says otherwise."""
    options.setdefault('capture_output', True)
    options.setdefault('check', False)
    options.setdefault('timeout', CLI_TIMEOUT)
    return subprocess.run(list(argv), **options)


def git(directory: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    """Git in a fixture repository, with the hardened recipe."""
    return run_cli(['git', '-C', str(directory), *GIT_OPTIONS, *arguments], env=GIT_ENV, stdin=subprocess.DEVNULL,
                   timeout=15, check=True)


def fixture_repo(root: Path, *, worktrees: Iterable[str] = ()) -> Path:
    """A repository at `root` with one empty commit, and a worktree under .claude/worktrees for each name."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, 'init', '--quiet')
    git(root, 'commit', '--quiet', '--allow-empty', '-m', 'fixture')
    for name in worktrees:
        git(root, 'worktree', 'add', '--quiet', '-b', name, f'.claude/worktrees/{name}')
    return root


def executable_stub(path: Path, body: str, *, record: Path | None = None) -> Path:
    """A shell script at `path` that runs `body`, first appending its arguments to `record` when one is named."""
    path.parent.mkdir(parents=True, exist_ok=True)
    recording = f'printf \'%s\\n\' "$*" >> "{record}"\n' if record is not None else ''
    path.write_text(f'#!/bin/sh\n{recording}{body}\n')
    path.chmod(0o755)
    return path


def write_stub(directory: Path, body: str, *, name: str = 'claude') -> tuple[Path, Path]:
    """A fake CLI recording its arguments. It is the only `claude` these tests run."""
    record = directory / f'{name}.args'
    return executable_stub(directory / name, body, record=record), record


def version_stub(directory: Path, version: str = '2.1.314') -> tuple[Path, Path]:
    return write_stub(directory, f"printf '{version} (Claude Code)\\n'")


def copy_scripts(home: Path, *relative: str) -> None:
    """Copy each file or folder, relative to the repository, into `home` at the same place."""
    for name in relative:
        source, target = ROOT / name, home / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
        else:
            shutil.copy2(source, target)


def copy_dispatcher(home: Path) -> Path:
    """The hook dispatcher and the scripts it imports, copied into `home`. Returns the copied dispatcher."""
    copy_scripts(home, '.claude/hooks/dispatch.py', *DISPATCHER_SCRIPTS)
    return home / '.claude/hooks/dispatch.py'


def specs_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return run_cli([sys.executable, str(ROOT / 'scripts/specs.py'), *arguments], text=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def story_body(text: str, identifier: str) -> str:
    match = re.search(rf'^### {re.escape(identifier)}:.*?(?=^### |\Z)', text, flags=re.MULTILINE | re.DOTALL)
    if match is None:
        raise LookupError(f'no story {identifier}')
    return match[0]


# The three checks a passing harness report needs (scripts/verify.py's harness profile).
HARNESS_CHECKS = ({'id': 'project_configuration', 'status': 'passed'},
                  {'id': 'backlog_validation', 'status': 'passed', 'exit_code': 0},
                  {'id': 'harness_behavior_tests', 'status': 'passed', 'exit_code': 0, 'tests_executed': 1})


def harness_report(root: Path, **overrides: object) -> dict[str, Any]:
    """A passing harness report of `root` as it is now, with `overrides` replacing its fields (THRN-09)."""
    report: dict[str, Any] = {'schema_version': 'autobots.harness-result/v1', 'template': False, 'profile': 'harness',
                              'status': 'passed', 'inputs_unchanged_during_check': True, 'input_fingerprint': fingerprint(root),
                              'input_manifest': input_manifest(root), 'checks': [dict(check) for check in HARNESS_CHECKS]}
    report.update(overrides)
    return report


def valid_agents(extra: str = '', rows: tuple[str, ...] | None = None) -> str:
    link = '[`scripts/verify.py`](scripts/verify.py)'
    labels = rows if rows is not None else ('Opening paragraph', 'Work protocol',
                                            '`.claude/settings.json`', '`CLAUDE.md`')
    table = ''.join(f'| {label} | {link} | none |\n' for label in labels)
    return ('# Contract\n\nOpening.\n\n## Work protocol\n\n- A rule.\n\n' + extra
            + '## Rule checks and review\n\n| Source | Check | Review |\n|---|---|---|\n' + table)


def valid_root(directory: str | Path) -> Path:
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
    (root / 'docs/PRD').mkdir(parents=True)
    (root / 'docs/PRD/PRD-Development-Harness.md').write_text('# PRD\n\n### DH-09.1. Work-item evidence contract\n')
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


def edit_json(path: Path, change: Callable[[Any], object]) -> None:
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


class HarnessTestCase(unittest.TestCase):
    """A test case whose list assertions show the list, and the helpers the hook tests repeat."""

    def assertMentions(self, errors: Iterable[str], needle: str) -> None:
        """Some item of `errors` contains `needle`. A failure shows every item (THRN-11)."""
        seen = list(errors)
        if not any(needle in error for error in seen):
            self.fail(f'{needle!r} not in {seen}')

    def assertMentionsNone(self, errors: Iterable[str], needle: str) -> None:
        """No item of `errors` contains `needle`. A failure shows every item (THRN-11)."""
        seen = list(errors)
        if any(needle in error for error in seen):
            self.fail(f'{needle!r} in {seen}')

    def valid_report(self, root: Path) -> dict[str, Any]:
        return harness_report(root)

    def write_files(self, root: Path, names: tuple[str, ...]) -> None:
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)

    def dispatch(self, raw: bytes, script: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
        return run_cli([sys.executable, str(script or ROOT / '.claude/hooks/dispatch.py')], input=raw, env=env, timeout=15)

    def fake_ruff(self, root: Path, body: str) -> Path:
        return executable_stub(root / 'services/agent/.venv/bin/ruff', body)

    def post_edit(self, root: Path, file_path: object) -> str:
        response = hook.handle(root, {'hook_event_name': 'PostToolUse', 'tool_name': 'Edit',
                                      'tool_input': {'file_path': file_path}})
        context: str = response['hookSpecificOutput']['additionalContext']
        return context

    def git(self, directory: Path, *arguments: str) -> None:
        git(directory, *arguments)

    def checkout_with_worktrees(self, parent: Path) -> Path:
        """A real repository with worktrees `one` and `two`, the way a session's worktree is laid out."""
        return fixture_repo(parent / 'home', worktrees=('one', 'two'))

    def edit_denied(self, root: Path, path: Path) -> bool:
        return hook.guard(root, 'Edit', {'file_path': str(path)}) is not None
