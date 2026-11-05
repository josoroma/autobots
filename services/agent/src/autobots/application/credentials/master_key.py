"""The separate host master key. Never created over an existing or in place of a lost one."""

import os
import secrets
import stat
from pathlib import Path

KEY_BYTES = 32


class MasterKeyUnavailable(Exception):
    """Reported as unavailable storage. There is no plaintext or replacement path."""


def create_master_key(path: Path) -> None:
    """Exclusive creation with a 0700 parent and a 0600 file. Refuses anything already there."""
    if not path.is_absolute():
        raise MasterKeyUnavailable("the master key path must be absolute")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise MasterKeyUnavailable("a master key already exists and is never replaced") from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(secrets.token_bytes(KEY_BYTES))


def load_master_key(path: Path) -> bytes:
    """Refuses a missing, linked, wrong-sized or too-open key, without saying more."""
    try:
        if not path.is_absolute() or path.is_symlink():
            raise MasterKeyUnavailable("the master key is unavailable")
        file_mode = stat.S_IMODE(path.stat().st_mode)
        parent_mode = stat.S_IMODE(path.parent.stat().st_mode)
        if file_mode & 0o077 or parent_mode & 0o077:
            raise MasterKeyUnavailable("the master key's permissions are too open")
        key = path.read_bytes()
    except OSError as error:
        raise MasterKeyUnavailable("the master key is unavailable") from error
    if len(key) != KEY_BYTES:
        raise MasterKeyUnavailable("the master key is unavailable")
    return key
