"""Precedence, encryption and secret handling, on fixtures. Real rows run in scripts/app_db.py."""

import asyncio
import json
import logging
import pickle
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import SecretStr

from autobots.application.credentials.crypto import (
    CredentialDecryptionError,
    Sealed,
    associated_data,
    seal,
    unseal,
)
from autobots.application.credentials.master_key import (
    MasterKeyUnavailable,
    create_master_key,
    load_master_key,
)
from autobots.application.credentials.precedence import (
    ConfigRootError,
    looks_usable,
    resolve_environment_key,
)
from autobots.application.credentials.store import (
    CredentialReference,
    CredentialStorageUnavailable,
    CredentialUnreadable,
    ProviderCredentialStore,
    ResolvedCredential,
)

REPOSITORY = Path(__file__).resolve().parents[3]
CASES = json.loads((REPOSITORY / "contracts/fixtures/credential-precedence.json").read_text())
KEY = bytes(range(32))
PLAINTEXT = "sk-or-arranged-not-a-real-key"


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_shared_precedence_case(case: dict[str, Any], tmp_path: Path) -> None:
    for name, content in case["files"].items():
        (tmp_path / name).write_text(content)
    found = resolve_environment_key(case["process"], str(tmp_path), case["mode"])
    expected = case["expected"]
    if expected is None:
        assert found is None
    else:
        assert found is not None
        assert (found.source, found.value) == (expected["source"], expected["value"])


def test_a_relative_root_is_refused() -> None:
    with pytest.raises(ConfigRootError):
        resolve_environment_key({}, "relative/config", "development")


def test_a_candidate_repr_hides_its_value(tmp_path: Path) -> None:
    candidate = resolve_environment_key({"OPENROUTER_API_KEY": PLAINTEXT}, str(tmp_path), "test")
    assert PLAINTEXT not in repr(candidate)


@pytest.mark.parametrize(
    ("value", "usable"),
    [
        ("sk-or-v1-abcdef", True),
        ("has space inside", False),
        ("short", False),
        ("sk-or-\nabcdefgh", False),
        ("sk-or-\u00e9abcdefgh", False),
    ],
)
def test_local_shape_check(value: str, usable: bool) -> None:
    assert looks_usable(value) is usable


def test_encryption_round_trips_with_a_fresh_nonce() -> None:
    workspace, credential = uuid4(), uuid4()
    aad = associated_data(workspace, "openrouter", credential, 1)
    first, second = seal(KEY, PLAINTEXT, aad), seal(KEY, PLAINTEXT, aad)
    assert first.nonce != second.nonce
    assert first.ciphertext != second.ciphertext
    assert PLAINTEXT.encode() not in first.ciphertext
    assert (len(first.nonce), len(first.tag)) == (12, 16)
    assert unseal(KEY, first, aad) == PLAINTEXT


def test_each_kind_of_tampering_fails() -> None:
    workspace, credential = uuid4(), uuid4()
    aad = associated_data(workspace, "openrouter", credential, 1)
    sealed = seal(KEY, PLAINTEXT, aad)
    flipped = bytes([sealed.ciphertext[0] ^ 1]) + sealed.ciphertext[1:]
    for key, body, data in (
        (bytes(32), sealed, aad),
        (KEY, Sealed(flipped, sealed.nonce, sealed.tag), aad),
        (KEY, Sealed(sealed.ciphertext, bytes(12), sealed.tag), aad),
        (KEY, Sealed(sealed.ciphertext, sealed.nonce, bytes(16)), aad),
        (KEY, sealed, associated_data(uuid4(), "openrouter", credential, 1)),
        (KEY, sealed, associated_data(workspace, "openrouter", credential, 2)),
    ):
        with pytest.raises(CredentialDecryptionError):
            unseal(key, body, data)


def test_master_key_creation_is_exclusive_and_private(tmp_path: Path) -> None:
    path = tmp_path / "secrets/master.key"
    create_master_key(path)
    original = path.read_bytes()
    assert len(original) == 32
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    with pytest.raises(MasterKeyUnavailable):
        create_master_key(path)
    assert path.read_bytes() == original
    assert load_master_key(path) == original


class OneRow:
    """A connection whose every query answers `row`, as one stored credential."""

    def __init__(self, row: tuple[object, ...]) -> None:
        self.row = row

    async def execute(self, *_: object) -> "OneRow":
        return self

    async def fetchone(self) -> tuple[object, ...]:
        return self.row


def test_a_row_this_master_key_cant_open_is_unreadable_storage(tmp_path: Path) -> None:
    """The store translates the cipher's failure itself, so its callers handle only its own
    errors, and a missing or wrong key with encrypted rows stays an error (refactor plan R-41,
    POPS-09, SP-007)."""
    workspace, credential = uuid4(), uuid4()
    path = tmp_path / "secrets/master.key"
    create_master_key(path)
    sealed = seal(bytes(32), PLAINTEXT, associated_data(workspace, "openrouter", credential, 1))
    row = (credential, 1, sealed.ciphertext, sealed.nonce, sealed.tag)
    with pytest.raises(CredentialUnreadable) as caught:
        asyncio.run(ProviderCredentialStore(OneRow(row), path).load_active(workspace))
    assert isinstance(caught.value, CredentialStorageUnavailable)
    assert caught.value.code == "credential_storage_unavailable"
    assert isinstance(caught.value.__cause__, CredentialDecryptionError)
    assert PLAINTEXT not in str(caught.value)


@pytest.mark.parametrize("problem", ["missing", "short", "open file", "open parent", "link"])
def test_an_unsafe_master_key_is_refused(tmp_path: Path, problem: str) -> None:
    path = tmp_path / "secrets/master.key"
    create_master_key(path)
    if problem == "missing":
        path.unlink()
    elif problem == "short":
        path.write_bytes(b"short")
    elif problem == "open file":
        path.chmod(0o644)
    elif problem == "open parent":
        path.parent.chmod(0o755)
    else:
        target = tmp_path / "secrets/real.key"
        path.rename(target)
        path.symlink_to(target)
    with pytest.raises(MasterKeyUnavailable):
        load_master_key(path)
    assert problem != "missing" or not path.exists(), "no replacement was generated"


def resolved() -> ResolvedCredential:
    return ResolvedCredential(CredentialReference("app", uuid4(), 1), PLAINTEXT)


def test_a_resolved_credential_cannot_be_serialized() -> None:
    credential = resolved()
    with pytest.raises(TypeError):
        pickle.dumps(credential)
    with pytest.raises(TypeError):
        JsonPlusSerializer().dumps_typed(credential)
    with pytest.raises(TypeError):
        JsonPlusSerializer().dumps_typed({"state": {"nested": [credential]}})


def test_secret_str_is_not_safe_in_checkpoints() -> None:
    """Why `ResolvedCredential` avoids it. If upstream ever changes this, the rule can relax."""
    _, data = JsonPlusSerializer().dumps_typed(SecretStr(PLAINTEXT))
    assert PLAINTEXT.encode() in data


def test_a_reference_holds_no_secret_and_can_be_checkpointed() -> None:
    credential = resolved()
    reference = credential.reference
    assert PLAINTEXT not in repr(reference)
    kind, data = JsonPlusSerializer().dumps_typed(reference)
    assert PLAINTEXT.encode() not in data and kind


def test_secrets_stay_out_of_logs_and_repr(caplog: pytest.LogCaptureFixture) -> None:
    credential = resolved()
    logging.getLogger("fixture").warning("attempt with %s", credential)
    assert PLAINTEXT not in caplog.text
    assert PLAINTEXT not in repr(credential)
    assert PLAINTEXT not in str(credential)
    assert credential.client_secret().get_secret_value() == PLAINTEXT
