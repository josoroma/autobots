#!/usr/bin/env python3
"""Bounded local Claude event adapter; guardrails, not an execution sandbox."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
FAILURE = 'Autobots hook input/configuration failed validation; no sensitive input was logged.'
sys.path.insert(0, str(ROOT / 'scripts'))
try:
    from harness_lib import check_domains, evidence_state, reduced_env
except Exception:  # A broken or missing library must block, not print a traceback and exit 1.
    print(FAILURE, file=sys.stderr)
    raise SystemExit(2) from None

# A PostToolUse event for a 127 KB PRD edit exceeded the old 64 KiB cap; it appears to carry the file.
MAX_INPUT = 1048576
MAX_PATH_BYTES = 4096
# Below the 10-second timeout in `.claude/settings.json`, so the dispatcher ends itself first.
DEADLINE_SECONDS = 9.0
DEADLINE_OVERRIDE = 'AUTOBOTS_HOOK_DEADLINE_SECONDS'
DIAGNOSTIC_TIMEOUT = 3.0
GIT_TIMEOUT = 2.0
WORKTREES = Path('.claude/worktrees')
SUPPORTED_TOOLS = {'Read', 'Write', 'Edit', 'MultiEdit', 'Bash'}
EDIT_TOOLS = {'Write', 'Edit', 'MultiEdit'}
UNKNOWN_ROOT = 'Git could not say which checkout this session is in, so nothing was judged against it.'
RUFF = Path('services/agent/.venv/bin/ruff')


def is_secret(path: Path) -> bool:
    # Case-folded, because this machine's default filesystem is case-insensitive.
    name = path.name.casefold()
    if name in {'stack.env', 'app.env', 'owner.env', 'master.key', 'provider-master.key', 'backup.key'}:
        return True
    return (name == '.env' or name.startswith('.env.')) and not name.endswith('.example')


def resolve_path(root: Path, raw: object) -> Path | None:
    """The canonical path, or None for anything not usable as one. The raw text is only ever data."""
    if (not isinstance(raw, str) or not raw or '\0' in raw
            or len(raw.encode('utf-8', 'surrogatepass')) > MAX_PATH_BYTES):
        return None
    path = Path(raw)
    try:
        return (root / path).resolve() if not path.is_absolute() else path.resolve()
    except (OSError, RuntimeError, ValueError):  # Python 3.12 raises RuntimeError on a symlink loop.
        return None


def registered_worktrees(home: Path) -> list[Path]:
    """Live worktrees Git has registered for this checkout's repository. Raises if Git cannot answer."""
    # The allowlisted environment drops GIT_DIR and the like, and the ceiling stops Git searching above `home`.
    result = subprocess.run(['git', 'worktree', 'list', '--porcelain', '-z'], cwd=home,
                            env={**reduced_env(), 'GIT_CEILING_DIRECTORIES': str(home.parent)},
                            stdin=subprocess.DEVNULL, capture_output=True, timeout=GIT_TIMEOUT, check=True)
    worktrees = []
    for record in result.stdout.decode('utf-8', 'surrogateescape').split('\0\0'):
        first, *attributes = record.split('\0')
        if first.startswith('worktree ') and not {'bare', 'prunable'}.intersection(
                attribute.partition(' ')[0] for attribute in attributes):
            worktrees.append(Path(first.removeprefix('worktree ')))
    return worktrees


def session_root(home: Path, raw_cwd: object) -> Path | None:
    """The registered worktree under `home` holding the session, `home`, or None if Git cannot answer.

    `cwd` is hook input and follows `cd`, so it selects only among worktrees Git registered strictly
    inside `.claude/worktrees`. No value selects a root permitting an edit `home` would refuse. It does
    choose whose reports `Stop` reads. None is not `home`: the session may be in a worktree, and `home`
    would be wider than that.
    """
    cwd = resolve_path(home, raw_cwd)
    place = home / WORKTREES
    if cwd is None or not cwd.is_relative_to(place):
        return home  # Every event in the main checkout lands here, and pays for no Git process.
    try:
        worktrees = registered_worktrees(home)
    except TimeoutError:  # The dispatcher's own deadline, which must still block.
        raise
    except (subprocess.SubprocessError, OSError):
        return None
    # `cwd` is canonical, so a registered path since swapped for a link cannot hold it.
    held_by = [path for path in worktrees if place in path.parents and cwd.is_relative_to(path) and path.is_dir()]
    return max(held_by, key=lambda path: len(path.parts), default=home)


def guard(root: Path, tool: str, value: dict) -> str | None:
    if tool in {'Read', 'Write', 'Edit', 'MultiEdit'}:
        raw = value.get('file_path')
        path = resolve_path(root, raw)
        if path is None:
            return 'A supported file tool needs a concrete, bounded and resolvable file_path.'
        # The link's own name counts too: `.env` pointing elsewhere is still treated as a secret.
        # The install's whole record is private, wherever `--install-dir` isn't pointed elsewhere.
        if (is_secret(Path(raw)) or is_secret(path) or 'application support/autobots/secrets' in path.as_posix().casefold()
                or '.local/share/autobots-install/' in path.as_posix().casefold()):
            return 'Secret files are outside ordinary coding-agent access; use the documented credential workflow.'
        if tool != 'Read' and not path.is_relative_to(root.resolve()):
            return 'Project edit would escape the workspace (including resolved symlinks).'
    if tool == 'Bash':
        command = value.get('command')
        if not isinstance(command, str) or len(command) > 20000:
            return 'Expected a bounded command string.'
        # Deliberately narrow guard. Arbitrary shell/MCP behavior is not confined here.
        dangerous = [r'\bsupabase\s+db\s+reset\b',
                     r'\bdocker\s+(?:system|volume)\s+prune\b',
                     r'\bdocker\s+volume\s+rm\b',
                     r'\bdocker(?:-compose|\s+compose\b|\s+container\b)[^\n;&|]*\bdown\b[^\n;&|]*(?:--volumes|(?:^|\s)-[a-zA-Z]*v\b)',
                     r'(?i)\b(?:cat|head|tail|less|more)\s+[^\n;&|]*\.env(?:\.(?!example\b)[\w.-]+)?["\x27]?(?=[\s;&|]|$)',
                     r'(?i)provider-master\.key',
                     r'(?i)\b(?:cat|head|tail|less|more|cp|mv|scp|rsync|tar|base64|xxd|od|strings|bat|dd|open|sed|awk|nl|sort|xargs)\b[^\n;&|]*\b(?:master|backup)\.key\b',
                     r'(?i)\.local/share/autobots-install/',
                     r'(?i)\bautobots-install/[^\s;&|]*(?:stack|app|owner)\.env']
        if any(re.search(pattern, command) for pattern in dangerous):
            return 'This operation needs the explicit target-guarded maintenance/credential workflow; ordinary coding hooks cannot authorize it.'
    return None


def ruff_diagnostic(root: Path, path: Path) -> str | None:
    """Run the prepared linter on one file. Output is discarded, so file content never reaches a diagnostic."""
    executable = root / RUFF
    if not os.access(executable, os.X_OK):
        return 'The prepared ruff is unavailable, so its diagnostic did not run.'
    try:
        # An argument array after `--`: the filename is data, even if it looks like shell code or a flag.
        result = subprocess.run([str(executable), 'check', '--quiet', '--no-cache', '--', str(path)],
                                cwd=root / 'services/agent', env=reduced_env(), stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=DIAGNOSTIC_TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        return 'The ruff diagnostic timed out and proves nothing.'
    except OSError:
        return 'The prepared ruff could not start, so its diagnostic did not run.'
    return f'ruff reported findings, exit {result.returncode}.' if result.returncode else None


def post_edit_diagnostic(root: Path, raw: object) -> str:
    diagnostic = 'Relevant edits invalidate earlier check evidence. Run the portable verifier when the bounded change is ready.'
    path = resolve_path(root, raw)
    if path is None or not path.is_relative_to(root.resolve()):
        return diagnostic
    domains = check_domains(path.relative_to(root.resolve()).as_posix())
    profile = {frozenset({'harness'}): 'harness', frozenset({'db'}): 'db'}.get(frozenset(domains), 'fast')
    diagnostic = (f"Affected check domains: {', '.join(sorted(domains))}. This invalidates earlier check evidence. "
                  f'Run python3.12 scripts/verify.py --profile {profile} when the bounded change is ready.')
    if path.suffix != '.py' or not path.is_file() or path.stat().st_size > 262144:
        return diagnostic
    try:
        ast.parse(path.read_text())
    except (SyntaxError, UnicodeError, ValueError, OSError):
        return 'Edited Python has a syntax/read error; repair it before verification.'
    if domains == {'python'}:
        finding = ruff_diagnostic(root, path)
        if finding:
            return f'{finding} {diagnostic}'
    return diagnostic


def handle(home: Path, payload: dict) -> dict:
    """Only events that judge a checkout ask Git, and none exits 2 for it: `Bash` must stay usable, and `Stop` must end."""
    event = payload.get('hook_event_name')
    if event == 'SessionStart':
        return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext':
                'Autobots: read AGENTS.md and mapped SPECS. Run python3.12 scripts/verify.py --profile harness '
                'for the delivered repository checks. App/database/live-model gates remain separate.'}}
    if event == 'PreToolUse':
        tool, value = payload.get('tool_name'), payload.get('tool_input')
        if tool not in SUPPORTED_TOOLS or not isinstance(value, dict):
            raise ValueError('Invalid tool input envelope')
        root = session_root(home, payload.get('cwd')) if tool in EDIT_TOOLS else home
        reason = guard(root, tool, value) if root else f'{UNKNOWN_ROOT} Edits are refused until it can.'
        if reason:
            return {'hookSpecificOutput': {'hookEventName': event,
                    'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
        return {}  # No auto-approval; normal tool permission handling still applies.
    if event == 'PostToolUse':
        value = payload.get('tool_input', {})
        raw = value.get('file_path') if isinstance(value, dict) else None
        root = session_root(home, payload.get('cwd'))
        return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext':
                post_edit_diagnostic(root, raw) if root else UNKNOWN_ROOT}}
    if event == 'Stop':
        root = session_root(home, payload.get('cwd'))
        passed, reason = evidence_state(root) if root else (False, UNKNOWN_ROOT)
        if payload.get('stop_hook_active') is True:
            return {'systemMessage': reason + ' No repeat completion block; report any remaining limitation honestly.'}
        if not passed:
            return {'decision': 'block', 'reason': reason + ' Run python3.12 scripts/verify.py with the harness, fast, '
                    'full or db profile the change needs, or explain the unavailable prerequisite. '
                    'This hook does not certify application completion.'}
        return {}
    if event == 'SubagentStop':
        return {'systemMessage': 'Return scoped findings, changed paths and actual evidence. '
                                 'The coordinator owns integration checks and story status.'}
    raise ValueError('Unsupported hook event')


def deadline_seconds() -> float:
    """The override can only shorten the deadline, so an environment value cannot extend a hook."""
    try:
        wanted = float(os.environ.get(DEADLINE_OVERRIDE, DEADLINE_SECONDS))
    except ValueError:
        return DEADLINE_SECONDS
    return wanted if 0 < wanted < DEADLINE_SECONDS else DEADLINE_SECONDS


def expire(_signal: int, _frame: object) -> None:
    raise TimeoutError('hook deadline passed')


def main() -> int:
    if sys.version_info < (3, 12):
        print('Autobots hooks require the configured Python 3.12+ interpreter.', file=sys.stderr)
        return 2
    try:
        signal.signal(signal.SIGALRM, expire)
        signal.setitimer(signal.ITIMER_REAL, deadline_seconds())
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValueError('Oversized hook input')
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError('Expected object')
        output = handle(ROOT, payload)
        signal.setitimer(signal.ITIMER_REAL, 0)
    except Exception:  # Exit 2 is the documented block; any other exit would let a tool proceed.
        print(FAILURE, file=sys.stderr)
        return 2
    print(json.dumps(output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
