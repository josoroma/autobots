"""AES-256-GCM with a fresh nonce and authenticated associated data, MP-06."""

import os
from dataclasses import dataclass
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
TAG_BYTES = 16


class CredentialDecryptionError(Exception):
    """Wrong key, altered bytes or a row moved between identities. Holds no detail."""


@dataclass(frozen=True)
class Sealed:
    ciphertext: bytes
    nonce: bytes
    tag: bytes


def associated_data(workspace_id: UUID, provider: str, credential_id: UUID, version: int) -> bytes:
    """Binds a ciphertext to its identity, so copying a row to another workspace fails."""
    return f"{workspace_id}|{provider}|{credential_id}|{version}".encode()


def seal(key: bytes, plaintext: str, aad: bytes) -> Sealed:
    nonce = os.urandom(NONCE_BYTES)
    combined = AESGCM(key).encrypt(nonce, plaintext.encode(), aad)
    return Sealed(combined[:-TAG_BYTES], nonce, combined[-TAG_BYTES:])


def unseal(key: bytes, sealed: Sealed, aad: bytes) -> str:
    try:
        plaintext = AESGCM(key).decrypt(sealed.nonce, sealed.ciphertext + sealed.tag, aad)
    except (InvalidTag, ValueError) as error:
        raise CredentialDecryptionError from error
    return plaintext.decode()
