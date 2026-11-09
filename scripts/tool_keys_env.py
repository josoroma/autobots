#!/usr/bin/env python3
"""Decision 0024 K2 and K7, PRD-Tool-Catalog PK-06: values from a `.env` file, for `make start`.

By default, prints one `export NAME='value'` line for each of the Tavily and Jina keys that has a
non-blank value, quoted so the shell reads it as data. With `--browser-switch`, it prints only
`export AUTOBOTS_BROWSER_EXECUTOR=enabled`, and only when the file sets exactly that. Browsing still
needs a passing executor qualification at the current code (AB-02).

The file is parsed with the app's own `.env` parser and never sourced, and no other variable is
printed. A missing file prints nothing. Nothing that could carry a value goes to stderr.
"""

import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/agent/src'))

from autobots.application.credentials.precedence import parse_dotenv  # noqa: E402

NAMES = ('TAVILY_API_KEY', 'JINA_API_KEY')
SWITCH = 'AUTOBOTS_BROWSER_EXECUTOR'


def exports(text: str) -> list[str]:
    values = parse_dotenv(text)
    return [f'export {name}={shlex.quote(values[name].strip())}' for name in NAMES if values.get(name, '').strip()]


def switch(text: str) -> list[str]:
    return [f'export {SWITCH}=enabled'] if parse_dotenv(text).get(SWITCH, '').strip() == 'enabled' else []


def main(argv: list[str]) -> int:
    browser = argv[1:] == ['--browser-switch']
    if len(argv) != 1 and not browser:
        print('usage: tool_keys_env.py <path to .env> [--browser-switch]', file=sys.stderr)
        return 2
    path = Path(argv[0])
    if not path.is_file():
        return 0
    text = path.read_text(errors='replace')
    lines = switch(text) if browser else exports(text)
    if lines:
        print('\n'.join(lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
