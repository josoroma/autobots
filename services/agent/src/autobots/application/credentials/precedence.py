"""MP-03's source order. Shared fixtures in `contracts/fixtures/` keep TypeScript identical."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

VARIABLE = "OPENROUTER_API_KEY"
PROCESS_SOURCE = "process_environment"


class ConfigRootError(ValueError):
    """Every native process must share an absolute root, never one inferred from its directory."""


@dataclass(frozen=True)
class EnvironmentCandidate:
    source: str
    value: str

    def __repr__(self) -> str:
        return f"EnvironmentCandidate(source={self.source!r}, value=<hidden>)"


def parse_dotenv(text: str) -> dict[str, str]:
    """The subset used here: comments, `export`, single or double quotes, and trailing comments."""
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[name] = value
    return values


def dotenv_order(mode: str) -> list[str]:
    files = [f".env.{mode}.local", ".env.local", f".env.{mode}", ".env"]
    return [name for name in files if not (name == ".env.local" and mode == "test")]


def resolve_environment_key(
    process_environment: Mapping[str, str], config_root: str, mode: str
) -> EnvironmentCandidate | None:
    """The first non-whitespace value wins, and resolution stops there, even if it is bad."""
    root = Path(config_root)
    if not root.is_absolute():
        raise ConfigRootError("the configuration root must be absolute")
    value = process_environment.get(VARIABLE, "")
    if value.strip():
        return EnvironmentCandidate(PROCESS_SOURCE, value.strip())
    for name in dotenv_order(mode):
        path = root / name
        if path.is_file():
            value = parse_dotenv(path.read_text()).get(VARIABLE, "")
            if value.strip():
                return EnvironmentCandidate(name, value.strip())
    return None


def looks_usable(value: str) -> bool:
    """A local shape check only. Authentication is separate, and failing either blocks fallback."""
    return (
        value.isascii()
        and value.isprintable()
        and not any(c.isspace() for c in value)
        and len(value) >= 8
    )
