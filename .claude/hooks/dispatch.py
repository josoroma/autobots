#!/usr/bin/env python3
"""Bounded local Claude event adapter; guardrails, not an execution sandbox."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from harness_lib import report_state  # noqa: E402

MAX_INPUT = 65536


def is_secret(path: Path) -> bool:
    return ((path.name == '.env' or path.name.startswith('.env.'))
            and not path.name.endswith('.example')) or path.name == 'provider-master.key'


def guard(root: Path, tool: str, value: dict) -> str | None:
    if tool in {'Read', 'Write', 'Edit', 'MultiEdit'}:
        raw = value.get('file_path')
        if not isinstance(raw, str) or not raw:
            return 'A supported file tool needs a concrete file_path.'
        path = Path(raw)
        path = (root / path).resolve() if not path.is_absolute() else path.resolve()
        if is_secret(path) or ('Application Support/Autobots/secrets' in path.as_posix()):
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
                     r'\bdocker\s+(?:compose\b[^\n;&|]*|container\b[^\n;&|]*)\bdown\b[^\n;&|]*(?:--volumes|(?:^|\s)-[a-zA-Z]*v\b)',
                     r'\b(?:cat|head|tail|less|more)\s+[^\n;&|]*\.env(?:\s|$)',
                     r'provider-master\.key']
        if any(re.search(pattern, command) for pattern in dangerous):
            return 'This operation needs the explicit target-guarded maintenance/credential workflow; ordinary coding hooks cannot authorize it.'
    return None


def handle(root: Path, payload: dict) -> dict:
    event = payload.get('hook_event_name')
    if event == 'SessionStart':
        return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext':
                'Autobots: read AGENTS.md and mapped SPECS. Run python3.12 scripts/verify.py --profile harness '
                'for the delivered repository checks. App/database/live-model gates remain separate.'}}
    if event == 'PreToolUse':
        tool, value = payload.get('tool_name'), payload.get('tool_input')
        if not isinstance(tool, str) or not isinstance(value, dict):
            raise ValueError('Invalid tool input envelope')
        reason = guard(root, tool, value)
        if reason:
            return {'hookSpecificOutput': {'hookEventName': event,
                    'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
        return {}  # No auto-approval; normal tool permission handling still applies.
    if event == 'PostToolUse':
        value = payload.get('tool_input', {})
        raw = value.get('file_path') if isinstance(value, dict) else None
        diagnostic = 'Relevant edits invalidate earlier check evidence. Run the portable verifier when the bounded change is ready.'
        if isinstance(raw, str):
            path = Path(raw)
            path = (root / path).resolve() if not path.is_absolute() else path.resolve()
            if path.is_relative_to(root.resolve()) and path.suffix == '.py' and path.is_file() and path.stat().st_size <= 262144:
                try:
                    ast.parse(path.read_text())
                except (SyntaxError, UnicodeError, OSError):
                    diagnostic = 'Edited Python has a syntax/read error; repair it before verification.'
        return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': diagnostic}}
    if event == 'Stop':
        passed, reason = report_state(root)
        if payload.get('stop_hook_active') is True:
            return {'systemMessage': reason + ' No repeat completion block; report any remaining limitation honestly.'}
        if not passed:
            return {'decision': 'block', 'reason': reason + ' Run python3.12 scripts/verify.py --profile harness '
                    'or explain the unavailable prerequisite. This hook does not certify application completion.'}
        return {}
    if event == 'SubagentStop':
        return {'systemMessage': 'Return scoped findings, changed paths and actual evidence. '
                                 'The coordinator owns integration checks and story status.'}
    raise ValueError('Unsupported hook event')


def main() -> int:
    if sys.version_info < (3, 12):
        print('Autobots hooks require the configured Python 3.12+ interpreter.', file=sys.stderr)
        return 2
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValueError('Oversized hook input')
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError('Expected object')
        output = handle(ROOT, payload)
    except (ValueError, OSError, TypeError):
        print('Autobots hook input/configuration failed validation; no sensitive input was logged.', file=sys.stderr)
        return 2
    print(json.dumps(output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
