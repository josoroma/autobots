"""Disposable-copy arrangement for the toolchain tests. Nothing here touches the real environments.

Copies live under the Git-ignored `.checks/US-1.3/copies/`, each with its own Git repository and
its own caches, so a fresh bootstrap reaches the registries. An unreachable registry fails the
test that needs it, and is never a skip.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / 'scripts'))

import toolchain  # noqa: E402
from harness_lib import reduced_env  # noqa: E402
from toolchain import git_paths  # noqa: E402

COPY_BASE = REPO_ROOT / '.checks/US-1.3/copies'
# What the arranged tree needs to prepare and check itself. The upstream checkout, PRDs and records stay out.
COPY_FILES = {'.gitignore', '.node-version', 'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml',
              'docs/engineering/runbooks/toolchains.md', 'scripts/harness_lib.py',
              'scripts/toolchain.py'}
COPY_PREFIXES = ('apps/', 'contracts/', 'packages/', 'services/', 'tests/toolchain/')
# Applied to a copy only when its `.gitignore` lacks them, so a copy is clean however the real file stands.
CANDIDATE_IGNORES = ('.corepack/', '.uv/', '.cache/', 'next-env.d.ts')
TOOL_TIMEOUT = 900.0

# N7: anything that could install or download at verification time.
LAUNCHER_RULES = (
    (re.compile(r'\buv\s+run\b'), None),
    (re.compile(r'\buv\s+sync\b'), '--check'),
    (re.compile(r'\bnpx\b'), None),
    (re.compile(r'\bdlx\b'), None),
    (re.compile(r'\bpnpm\s+(?:install|i)\b'), '--frozen-lockfile'),
)


def launcher_violations(commands: Sequence[str]) -> list[str]:
    found = []
    for command in commands:
        for pattern, required in LAUNCHER_RULES:
            if pattern.search(command) and (required is None or required not in command):
                found.append(command)
    return found


def tool_env() -> dict[str, str]:
    """The reduced environment the tools get, so tests inherit no credential."""
    env = reduced_env()
    if 'HOME' in os.environ:
        env['HOME'] = os.environ['HOME']
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def copy_candidates() -> list[str]:
    paths = git_paths(REPO_ROOT, 'ls-files', '-co', '--exclude-standard')
    return [path for path in paths if (path in COPY_FILES or path.startswith(COPY_PREFIXES))
            and (REPO_ROOT / path).is_file()]


def apply_candidate_ignores(root: Path) -> None:
    path = root / '.gitignore'
    present = path.read_text().splitlines() if path.exists() else []
    missing = [line for line in CANDIDATE_IGNORES if line not in present]
    if missing:
        path.write_text('\n'.join([*present, *missing]) + '\n')


def init_repository(root: Path) -> None:
    git = ('git', '-C', str(root), '-c', 'user.name=toolchain-test', '-c', 'user.email=toolchain-test@invalid',
           '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null')
    for arguments in (('init', '-q'), ('add', '-A'), ('commit', '-q', '-m', 'arranged copy')):
        subprocess.run([*git, *arguments], check=True, capture_output=True, env=tool_env())


def make_copy(destination: Path | None = None) -> Path:
    """A new tree holding this repository's toolchain paths, with no environment and no cache."""
    if destination is None:
        COPY_BASE.mkdir(parents=True, exist_ok=True)
        destination = Path(tempfile.mkdtemp(prefix='copy-', dir=COPY_BASE))
    for relative in copy_candidates():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, target)
    apply_candidate_ignores(destination)
    init_repository(destination)
    return destination


def remove_copy(root: Path) -> None:
    """Delete a copy. Package stores hold read-only entries, so make them writable first."""
    def retry(function, path, _error) -> None:
        os.chmod(Path(path).parent, stat.S_IRWXU)
        os.chmod(path, stat.S_IRWXU)
        function(path)
    if root.resolve().is_relative_to(COPY_BASE.resolve()):
        shutil.rmtree(root, onexc=retry)


def run_toolchain(root: Path, verb: str) -> subprocess.CompletedProcess[str]:
    """Run the copy's own `scripts/toolchain.py` against the copy."""
    return subprocess.run([sys.executable, str(root / 'scripts/toolchain.py'), verb, '--project-root', str(root)],
                          cwd=root, env=tool_env(), capture_output=True, text=True, errors='replace',
                          timeout=TOOL_TIMEOUT, check=False)


def bootstrap_copy(root: Path) -> None:
    result = run_toolchain(root, 'bootstrap')
    if result.returncode != 0:
        raise AssertionError(f'bootstrap of the disposable copy failed, exit {result.returncode}: '
                             f'{result.stdout[-2000:]}{result.stderr[-2000:]}')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def failed_steps(result: subprocess.CompletedProcess[str]) -> list[str]:
    return re.findall(r'^FAIL: (\w+)$', result.stdout, flags=re.MULTILINE)


def python_distributions(root: Path) -> list[str]:
    return toolchain.entry_names(root / toolchain.SITE_PACKAGES, '*.dist-info')


def pnpm_entries(root: Path) -> list[str]:
    return toolchain.entry_names(root / toolchain.PNPM_VIRTUAL_STORE)


def uv_pip(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run `uv pip` on a copy's environment, with the same pinned tools and repository-local state."""
    tools = toolchain.find_tools(root)
    return subprocess.run([tools.uv, 'pip', *arguments, '--python', str(root / toolchain.VENV / 'bin/python')],
                          cwd=root / toolchain.AGENT, env=toolchain.child_env(root, tools, verifying=False),
                          capture_output=True, text=True, errors='replace', timeout=TOOL_TIMEOUT, check=False)
