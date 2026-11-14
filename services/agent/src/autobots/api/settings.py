"""Process configuration, read once from the environment by the entry point, never at import."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from pydantic import SecretStr

from autobots.application.readiness import ReadinessSettings


@dataclass(frozen=True)
class Settings:
    """Empty secrets fail closed: nothing can authenticate against them. Their repr hides values.

    Handlers read the admission gate's settings and the backup directory from here, never from the
    environment per request (PAPI-10).
    """

    internal_token: SecretStr = field(default_factory=lambda: SecretStr(""))
    jwt_secret: SecretStr = field(default_factory=lambda: SecretStr(""))
    database_url: SecretStr = field(default_factory=lambda: SecretStr(""))
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")
    readiness: ReadinessSettings = field(default_factory=ReadinessSettings)
    backup_dir: str = ""


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Raises `MalformedSetting` for a value the process can't start with."""
    values = os.environ if environ is None else environ
    hosts = values.get("AUTOBOTS_ALLOWED_HOSTS", "127.0.0.1,localhost")
    return Settings(
        internal_token=SecretStr(values.get("AUTOBOTS_INTERNAL_TOKEN", "")),
        jwt_secret=SecretStr(values.get("AUTOBOTS_JWT_SECRET", "")),
        database_url=SecretStr(values.get("AUTOBOTS_DATABASE_URL", "")),
        allowed_hosts=tuple(host.strip() for host in hosts.split(",") if host.strip()),
        readiness=ReadinessSettings.from_environment(values),
        backup_dir=values.get("AUTOBOTS_BACKUP_DIR", ""),
    )
