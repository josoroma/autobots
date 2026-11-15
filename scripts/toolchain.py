#!/usr/bin/env python3
"""Explicit lock, prepare, version and check verbs for the pinned Node and Python toolchains.

`versions`, `check` and `node-bin` never install. `lock` writes the two locks and `bootstrap` writes
Git-ignored environments, and only when asked. Runtimes are found among existing installs and
selected for child processes only; nothing here changes the machine's shell, PATH or global tools.

Exit codes: 0 passed, 1 a check failed, 2 prerequisite unavailable or usage error.
Passing `check` is local evidence about these environments. It is not a verify.py profile and
establishes neither H0, H1 nor product acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness_lib import EXIT_FAILED as EXIT_FAILED
from harness_lib import EXIT_PASSED as EXIT_PASSED
from harness_lib import EXIT_UNAVAILABLE as EXIT_UNAVAILABLE
from harness_lib import project_root, reduced_env, run_bounded
from harness_lib import utc as utc

# A pinned tool, manifest or prepared environment is missing: exit code 2. One class for every script
# (SCRP-08), so a script that imports it from here catches what disposable_db.py raises too.
from qualification.errors import Unavailable as Unavailable
from qualification.profiles import LONG as LONG
from qualification.profiles import SHORT as SHORT
from qualification.profiles import STEPS


def git_paths(root: Path, *arguments: str) -> list[str]:
    result = subprocess.run(['git', '-C', str(root), *arguments, '-z'], capture_output=True, check=False)
    if result.returncode:
        raise ValueError(f"git {arguments[0]} failed: {result.stderr.decode(errors='replace').strip()}")
    return [item for item in result.stdout.decode().split('\0') if item]


def digest(path: Path) -> str:
    if path.is_symlink():
        return 'symlink:' + hashlib.sha256(os.readlink(path).encode()).hexdigest()
    if not path.exists():
        return 'absent'
    if path.is_dir():
        raise ValueError(f'cannot hash directory entry {path.name}; its contents would go unchecked')
    return hashlib.sha256(path.read_bytes()).hexdigest() + (':executable' if os.access(path, os.X_OK) else '')


AGENT = Path('services/agent')
PYPROJECT = AGENT / 'pyproject.toml'
UV_LOCK = AGENT / 'uv.lock'
PNPM_LOCK = Path('pnpm-lock.yaml')
PACKAGE_JSON = Path('package.json')
WEB_PACKAGE = Path('apps/web/package.json')
NODE_PIN = Path('.node-version')
PYTHON_PIN = AGENT / '.python-version'
VENV = AGENT / '.venv'
SITE_PACKAGES = VENV / 'lib/python3.12/site-packages'
PNPM_VIRTUAL_STORE = Path('node_modules/.pnpm')
REPORT = Path('.checks/toolchain/latest.json')
GUARDED_FILES = (UV_LOCK, PNPM_LOCK, PYPROJECT, PACKAGE_JSON, Path('pnpm-workspace.yaml'), WEB_PACKAGE,
                 Path('packages/api-client/package.json'), Path('packages/db-types/package.json'),
                 NODE_PIN, PYTHON_PIN)
# Locked because deepagents 0.7.32 requires both adapters; owned code never imports them.
UNUSED_TRANSITIVE = ('anthropic', 'langchain-anthropic', 'google-genai', 'langchain-google-genai')

XDG_LOCATIONS = {'XDG_STATE_HOME': 'state', 'XDG_CACHE_HOME': 'cache',
                 'XDG_DATA_HOME': 'data', 'XDG_CONFIG_HOME': 'config'}

PROBE_TIMEOUT = 10.0
SEMVER = re.compile(r'\d+\.\d+\.\d+')
OUTPUT_LIMIT = 16000


@dataclass(frozen=True)
class Pins:
    node: str
    python: str
    uv: str
    pnpm: str


@dataclass(frozen=True)
class Tools:
    node_dir: str
    python: str
    uv: str
    corepack: str
    pins: Pins


@dataclass(frozen=True)
class Step:
    id: str
    argv: tuple[str, ...]
    cwd: Path
    timeout: float = SHORT
    # A step that exits 0 but does not print this has failed.
    expect_output: str | None = None


def read_pins(root: Path) -> Pins:
    try:
        node = (root / NODE_PIN).read_text().strip()
        python = (root / PYTHON_PIN).read_text().strip()
        required = tomllib.loads((root / PYPROJECT).read_text())['tool']['uv']['required-version']
        manager = json.loads((root / PACKAGE_JSON).read_text())['packageManager']
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise Unavailable(f'cannot read a toolchain pin: {type(error).__name__}: {error}') from error
    uv = required.removeprefix('==')
    match = re.fullmatch(r'pnpm@(\d+\.\d+\.\d+)\+sha512\.[0-9a-f]{128}', manager)
    if match is None or not all(SEMVER.fullmatch(pin) for pin in (node, python, uv)):
        raise Unavailable('a toolchain pin is not an exact version')
    return Pins(node=node, python=python, uv=uv, pnpm=match[1])


def probe_env() -> dict[str, str]:
    env = reduced_env()
    if 'HOME' in os.environ:
        env['HOME'] = os.environ['HOME']
    return env


def observed_version(executable: str) -> str | None:
    try:
        result = subprocess.run([executable, '--version'], env=probe_env(), capture_output=True, text=True,
                                errors='replace', timeout=PROBE_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = SEMVER.search(result.stdout) if result.returncode == 0 else None
    return match[0] if match else None


def candidates(name: str, extra: Iterable[Path] = ()) -> Iterator[str]:
    """Each executable called `name` on the process search path, then under `extra`."""
    seen = set()
    for directory in [*os.environ.get('PATH', '').split(os.pathsep), *map(str, extra)]:
        path = Path(directory) / name if directory else None
        if path is None or path in seen or not path.is_file() or not os.access(path, os.X_OK):
            continue
        seen.add(path)
        yield str(path)


def find_pinned(name: str, wanted: str, extra: Iterable[Path] = ()) -> str:
    """The first install reporting exactly the pinned version. The search path is never named."""
    for candidate in candidates(name, extra):
        if observed_version(candidate) == wanted:
            return candidate
    raise Unavailable(f'{name} {wanted} is required and was not found; nothing was downloaded or installed')


def nvm_bin(pins: Pins) -> Path:
    return Path.home() / '.nvm/versions/node' / f'v{pins.node}/bin'


def find_tools(root: Path) -> Tools:
    pins = read_pins(root)
    node = find_pinned('node', pins.node, [nvm_bin(pins)])
    node_dir = str(Path(node).parent)
    corepack = Path(node_dir) / 'corepack'
    if not os.access(corepack, os.X_OK):
        raise Unavailable(f'corepack is required beside node {pins.node} and was not found')
    return Tools(node_dir=node_dir, python=find_pinned('python3.12', pins.python),
                 uv=find_pinned('uv', pins.uv), corepack=str(corepack), pins=pins)


def child_env(root: Path, tools: Tools, *, verifying: bool) -> dict[str, str]:
    """Reduced environment, so no credential is inherited, with tool state inside the repository."""
    env = probe_env()
    env.update(PATH=os.pathsep.join(filter(None, [tools.node_dir, env.get('PATH')])),
               UV_CACHE_DIR=str(root / '.uv/cache'),
               UV_PYTHON=tools.python,
               UV_PYTHON_DOWNLOADS='never',
               COREPACK_HOME=str(root / '.corepack'),
               COREPACK_ENABLE_AUTO_PIN='0',
               COREPACK_ENABLE_DOWNLOAD_PROMPT='0',
               NEXT_TELEMETRY_DISABLED='1',
               # pnpm 12.16.1 refuses stateDir in pnpm-workspace.yaml and otherwise writes its
               # update-check state under HOME, so the XDG base directories stay in the repository.
               # User-level tool configuration is left out too, so it cannot affect resolution.
               **{name: str(root / '.cache/xdg' / leaf) for name, leaf in XDG_LOCATIONS.items()})
    if verifying:
        env.update(UV_OFFLINE='1', UV_NO_SYNC='1', COREPACK_ENABLE_NETWORK='0')
    return env


def lock_steps(root: Path, tools: Tools) -> list[Step]:
    return [Step('python_lock_write', (tools.uv, 'lock'), root / AGENT, LONG),
            Step('node_lock_write', (tools.corepack, 'pnpm', 'install', '--lockfile-only'), root, LONG)]


def bootstrap_steps(root: Path, tools: Tools) -> list[Step]:
    return [Step('python_install', (tools.uv, 'sync', '--locked'), root / AGENT, LONG),
            Step('node_install', (tools.corepack, 'pnpm', 'install', '--frozen-lockfile'), root, LONG)]


def check_steps(root: Path, tools: Tools) -> list[Step]:
    """Everything `check` runs after its prerequisites, each with its registered deadline (qualification/profiles.py).
    Tests scan this list for install launchers."""
    agent = root / AGENT
    venv_bin = root / VENV / 'bin'
    web_script = (tools.corepack, 'pnpm', '--filter', '@autobots/web', 'run')

    def step(step_id: str, argv: tuple[str, ...], cwd: Path, expect_output: str | None = None) -> Step:
        return Step(step_id, argv, cwd, STEPS[step_id].timeout, expect_output)

    return [
        step('python_lock', (tools.uv, 'lock', '--check', '--offline'), agent),
        step('python_env', (tools.uv, 'sync', '--check', '--locked', '--offline'), agent),
        step('ruff_check', (str(venv_bin / 'ruff'), 'check'), agent),
        step('ruff_format', (str(venv_bin / 'ruff'), 'format', '--check'), agent),
        step('mypy', (str(venv_bin / 'mypy'),), agent),
        step('pytest', (str(venv_bin / 'pytest'),), agent),
        # R-07: repository Python, from the root, under ruff.toml and mypy.ini.
        step('repo_ruff_check', (str(venv_bin / 'ruff'), 'check', 'scripts', 'tests', '.claude/hooks'), root),
        step('repo_mypy', (str(venv_bin / 'mypy'),), root),
        step('node_lock', (tools.corepack, 'pnpm', 'install', '--frozen-lockfile', '--lockfile-only', '--offline'), root),
        step('node_version', (tools.corepack, 'pnpm', 'run', '--silent', 'node:version'), root, expect_output=f'v{tools.pins.node}'),
        step('lint', (*web_script, 'lint'), root),
        step('format_check', (*web_script, 'format:check'), root),
        step('typegen', (*web_script, 'typegen'), root),
        step('typecheck', (*web_script, 'typecheck'), root),
        step('build', (*web_script, 'build'), root),
    ]


def run_step(step: Step, env: Mapping[str, str]) -> dict[str, Any]:
    """Run one step in its own process group, so a timeout also ends what it started (harness_lib.run_bounded)."""
    record: dict[str, Any] = {'id': step.id, 'argv': [Path(step.argv[0]).name, *step.argv[1:]],
                              'started_at_utc': utc(), 'exit_code': None, 'status': 'error', 'output': ''}
    result = run_bounded(step.argv, cwd=step.cwd, env=env, timeout=step.timeout, stderr=subprocess.STDOUT)
    if result.exit_code is None:
        shown = f'timed out after {step.timeout} seconds' if result.failure == 'timeout' else str(result.failure)
        record.update(output=shown, finished_at_utc=utc())
        return record
    passed = result.exit_code == 0 and (step.expect_output is None or step.expect_output in result.stdout)
    record.update(exit_code=result.exit_code, status='passed' if passed else 'failed',
                  output=result.stdout[-OUTPUT_LIMIT:], finished_at_utc=utc())
    return record


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'absent'


def entry_names(directory: Path, pattern: str = '*') -> list[str]:
    return sorted(path.name for path in directory.glob(pattern)) if directory.is_dir() else []


# The delivery plugin's hook rewrites this record on its own schedule. No check writes it.
DELIVERY_RECORD = 'openspec/delivery/goal.md'


def snapshot(root: Path) -> dict[str, Any]:
    """What verification must not change. Names, not contents, so bytecode and builds do not trip it."""
    changed = {*git_paths(root, 'diff', '--no-renames', '--name-only', 'HEAD'),
               *git_paths(root, 'ls-files', '--others', '--exclude-standard')} - {DELIVERY_RECORD}
    return {'guarded': {path.as_posix(): file_hash(root / path) for path in GUARDED_FILES},
            'changed': {path: digest(root / path) for path in sorted(changed)},
            'dist_info': entry_names(root / SITE_PACKAGES, '*.dist-info'),
            'pnpm_entries': entry_names(root / PNPM_VIRTUAL_STORE)}


def snapshot_differences(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    differences = []
    for section in ('guarded', 'changed'):
        for path in sorted(before[section].keys() | after[section].keys()):
            if before[section].get(path) != after[section].get(path):
                differences.append(f'changed: {path}')
    for section, label in (('dist_info', 'python environment'), ('pnpm_entries', 'node_modules/.pnpm')):
        for name in sorted(set(before[section]) ^ set(after[section])):
            differences.append(f'changed: {label}: {name}')
    return sorted(set(differences))


def write_report(root: Path, report: Mapping[str, Any]) -> None:
    path = root / REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def run_guarded(root: Path, steps: Sequence[Step], env: Mapping[str, str]) -> tuple[int, dict[str, Any]]:
    """Run steps in order, stopping at the first failure, then fail on any change even if all passed."""
    before = snapshot(root)
    records = []
    for step in steps:
        record = run_step(step, env)
        records.append(record)
        print(f"{'PASS' if record['status'] == 'passed' else 'FAIL'}: {step.id}")
        if record['status'] != 'passed':
            print(record['output'], file=sys.stderr)
            break
    differences = snapshot_differences(before, snapshot(root))
    for difference in differences:
        print(f'FAIL: guard: {difference}', file=sys.stderr)
    passed = not differences and len(records) == len(steps) and all(r['status'] == 'passed' for r in records)
    return (EXIT_PASSED if passed else EXIT_FAILED), {
        'schema_version': 'autobots.toolchain-check/v1',
        'status': 'passed' if passed else 'failed',
        'model_transport': 'none',
        'not_established': ['H0', 'H1', 'product acceptance'],
        'steps': records,
        'guard_differences': differences,
    }


def pnpm_prepared(root: Path, pins: Pins) -> bool:
    return bool(list((root / '.corepack/v1/pnpm').glob(f'{pins.pnpm}*')))


def missing_prepared_paths(root: Path, tools: Tools) -> list[str]:
    missing = []
    if not (root / VENV / 'bin/python').exists():
        missing.append(f'{VENV}/bin/python')
    if not (root / 'node_modules').is_dir():
        missing.append('node_modules')
    if not pnpm_prepared(root, tools.pins):
        missing.append(f'.corepack entry for pnpm {tools.pins.pnpm}')
    return missing


def check(root: Path) -> int:
    started = utc()
    try:
        tools = find_tools(root)
        missing = missing_prepared_paths(root, tools)
        if missing:
            raise Unavailable('not prepared, run bootstrap explicitly; missing: ' + ', '.join(missing))
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        write_report(root, {'schema_version': 'autobots.toolchain-check/v1', 'status': 'error',
                            'model_transport': 'none', 'started_at_utc': started,
                            'reason': str(error), 'steps': []})
        return EXIT_UNAVAILABLE
    code, report = run_guarded(root, check_steps(root, tools), child_env(root, tools, verifying=True))
    write_report(root, report | {'started_at_utc': started, 'finished_at_utc': utc()})
    return code


def run_explicit(root: Path, steps: Sequence[Step], env: Mapping[str, str]) -> int:
    """Run `lock` or `bootstrap`, the only verbs allowed to reach a registry."""
    for step in steps:
        record = run_step(step, env)
        print(record['output'])
        print(f"{'PASS' if record['status'] == 'passed' else 'FAIL'}: {step.id}")
        if record['status'] != 'passed':
            return EXIT_FAILED
    return EXIT_PASSED


def uv_locked_versions(text: str) -> dict[str, str]:
    return {package['name']: package.get('version', '') for package in tomllib.loads(text).get('package', [])}


def pnpm_importers(text: str) -> dict[str, dict[str, str]]:
    """Direct dependency versions per importer. Standard library only, so a line parser, not YAML."""
    importers: dict[str, dict[str, str]] = {}
    importer = package = None
    inside = False
    for line in text.splitlines():
        if line and not line[0].isspace():
            inside = line == 'importers:'
            continue
        if not inside or not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key, _, value = line.strip().partition(':')
        key, value = key.strip("'\""), value.strip()
        if indent == 2:
            importer = key
            importers[importer] = {}
        elif indent == 6:
            package = key
        elif indent == 8 and key == 'version' and importer is not None and package is not None:
            importers[importer][package] = value.split('(', 1)[0]
    return importers


def read_or_none(path: Path) -> str | None:
    try:
        return path.read_text()
    except OSError:
        return None


def script_output(step: Step, env: Mapping[str, str]) -> str | None:
    record = run_step(step, env)
    return record['output'].strip() if record['status'] == 'passed' else None


def versions(root: Path) -> int:
    """Report pins, what each lock holds and what actually runs. Reads only; never fetches pnpm."""
    tools = find_tools(root)
    env = child_env(root, tools, verifying=True)
    pyproject = tomllib.loads((root / PYPROJECT).read_text())
    groups = pyproject.get('dependency-groups', {}).get('dev', [])
    python_direct = dict(re.sub(r'\[[^\]]*\]', '', item).split('==', 1)
                         for item in [*pyproject['project']['dependencies'], *groups])
    uv_text = read_or_none(root / UV_LOCK)
    python_locked = uv_locked_versions(uv_text) if uv_text is not None else {}
    web = json.loads((root / WEB_PACKAGE).read_text())
    node_direct = {**web.get('dependencies', {}), **web.get('devDependencies', {})}
    pnpm_text = read_or_none(root / PNPM_LOCK)
    node_locked = pnpm_importers(pnpm_text).get('apps/web', {}) if pnpm_text is not None else {}
    # Corepack creates its home just by starting, so an unprepared tree does not start it.
    pnpm_version = script_node = None
    if pnpm_prepared(root, tools.pins):
        pnpm_version = script_output(Step('pnpm_version', (tools.corepack, 'pnpm', '--version'), root), env)
        script_node = script_output(Step('node_version', (tools.corepack, 'pnpm', 'run', '--silent', 'node:version'), root), env)
    print(json.dumps({
        'runtime': {
            'node': {'pin': tools.pins.node, 'selected': observed_version(str(Path(tools.node_dir) / 'node')),
                     'through_package_script': script_node},
            'pnpm': {'pin': tools.pins.pnpm, 'through_corepack': pnpm_version},
            'corepack': observed_version(tools.corepack),
            'python': {'pin': tools.pins.python, 'selected': observed_version(tools.python)},
            'uv': {'pin': tools.pins.uv, 'selected': observed_version(tools.uv)},
        },
        'python_direct': {name: {'pin': pin, 'locked': python_locked.get(name)}
                          for name, pin in sorted(python_direct.items())},
        'python_unused_transitive': {name: python_locked.get(name) for name in UNUSED_TRANSITIVE},
        'node_direct': {name: {'pin': pin, 'locked': node_locked.get(name)}
                        for name, pin in sorted(node_direct.items())},
    }, indent=2))
    return EXIT_PASSED


def node_bin(root: Path) -> int:
    """Print the directory of the pinned Node, found as `find_tools` finds it, on the search path and then under nvm,
    so the Makefile never runs another Node that happens to come first (SQLI-11). Absent, it prints nothing."""
    pins = read_pins(root)
    print(Path(find_pinned('node', pins.node, [nvm_bin(pins)])).parent)
    return EXIT_PASSED


def main(argv: Sequence[str] | None = None) -> int:
    if sys.version_info < (3, 12):  # noqa: UP036 - a guard for an older interpreter running this script
        print('ERROR: Python 3.12+ is required; use the qualified python3.12 interpreter.', file=sys.stderr)
        return EXIT_UNAVAILABLE
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('verb', choices=('versions', 'lock', 'bootstrap', 'check', 'node-bin'))
    parser.add_argument('--project-root', type=Path, default=project_root())
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
        if args.verb == 'check':
            return check(root)
        if args.verb == 'versions':
            return versions(root)
        if args.verb == 'node-bin':
            return node_bin(root)
        tools = find_tools(root)
        steps = lock_steps(root, tools) if args.verb == 'lock' else bootstrap_steps(root, tools)
        return run_explicit(root, steps, child_env(root, tools, verifying=False))
    except (Unavailable, OSError, ValueError, KeyError, TypeError) as error:
        print(f'ERROR: {type(error).__name__}: {error}', file=sys.stderr)
        return EXIT_UNAVAILABLE


if __name__ == '__main__':
    raise SystemExit(main())
