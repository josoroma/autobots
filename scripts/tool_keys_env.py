#!/usr/bin/env python3
"""Decisions 0024 (K2, K7) and 0025 (V5), PRD-Tool-Catalog PK-06 and PK-07: values from a `.env`
file, for `make start`.

`tool_values` gives the Tavily and Jina keys and the GitHub repository and token that have a non-blank
value, and `switch_values` gives `AUTOBOTS_BROWSER_EXECUTOR=enabled`, and only when the file sets exactly
that. scripts/local_app.py passes them to the API and the worker. Browsing still needs a passing executor
qualification at the current code (AB-02).

The file is parsed as data and never sourced, as the app parses `.env` (harness_lib.parse_dotenv), and
no other variable is passed. As a command, it prints each value as one `export NAME='value'` line, quoted
so a shell reads it as data. A missing file prints nothing. Nothing that could carry a value goes to stderr.
"""

import shlex
import sys
from pathlib import Path

from harness_lib import parse_dotenv

# Decision 0025 V5 adds the GitHub pair, under the same rules.
NAMES = ('TAVILY_API_KEY', 'JINA_API_KEY', 'GITHUB_REPOSITORY', 'GITHUB_TOKEN')
SWITCH = 'AUTOBOTS_BROWSER_EXECUTOR'


def tool_values(text: str) -> dict[str, str]:
    values = parse_dotenv(text, 'app')
    return {name: values[name].strip() for name in NAMES if values.get(name, '').strip()}


def switch_values(text: str) -> dict[str, str]:
    return {SWITCH: 'enabled'} if parse_dotenv(text, 'app').get(SWITCH, '').strip() == 'enabled' else {}


def exports(text: str) -> list[str]:
    return [f'export {name}={shlex.quote(value)}' for name, value in tool_values(text).items()]


def switch(text: str) -> list[str]:
    return [f'export {name}={value}' for name, value in switch_values(text).items()]


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
