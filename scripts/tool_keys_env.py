#!/usr/bin/env python3
"""Decision 0024 K2 and PRD-Tool-Catalog PK-06: the Tavily and Jina keys from a `.env` file, for `make start`.

Prints one `export NAME='value'` line for each of the two keys that has a non-blank value, quoted so
the shell reads it as data. The file is parsed with the app's own `.env` parser and never sourced, and
no other variable is printed. A missing file prints nothing. Never prints anything to stderr that
could carry a value.
"""

import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/agent/src'))

from autobots.application.credentials.precedence import parse_dotenv  # noqa: E402

NAMES = ('TAVILY_API_KEY', 'JINA_API_KEY')


def exports(text: str) -> list[str]:
    values = parse_dotenv(text)
    return [f'export {name}={shlex.quote(values[name].strip())}' for name in NAMES if values.get(name, '').strip()]


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print('usage: tool_keys_env.py <path to .env>', file=sys.stderr)
        return 2
    path = Path(argv[0])
    if not path.is_file():
        return 0
    lines = exports(path.read_text(errors='replace'))
    if lines:
        print('\n'.join(lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
