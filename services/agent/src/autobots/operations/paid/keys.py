"""The OpenRouter key a paid entry point reads from the key file it is given, and nothing else."""

from pathlib import Path

from pydantic import SecretStr

from autobots.operations.cli import Refused

KEY_VARIABLE = "OPENROUTER_API_KEY"


def read_key(path: Path) -> SecretStr:
    """Only the one variable. Nothing here prints it, and no other value is kept."""
    for line in path.read_text().splitlines():
        name, separator, value = line.strip().removeprefix("export ").partition("=")
        if separator and name.strip() == KEY_VARIABLE:
            cleaned = value.strip().strip("\"'")
            if cleaned:
                return SecretStr(cleaned)
    raise Refused(f"{KEY_VARIABLE} isn't set in that file")
