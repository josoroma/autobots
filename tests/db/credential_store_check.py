"""Real rows through the restricted runtime role, printed as JSON cases. Arranged key, placeholder values."""
from __future__ import annotations

import asyncio
import json
import os
import pickle
import sys
import tempfile
from pathlib import Path
from uuid import UUID

import psycopg
from autobots.application.credentials.precedence import EnvironmentCandidate
from autobots.application.credentials.store import (
    CredentialBlocked,
    CredentialMissing,
    CredentialStorageUnavailable,
    ProviderCredentialStore,
    resolve_for_attempt,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

FIRST, SECOND = 'sk-or-arranged-first-not-real', 'sk-or-arranged-second-not-real'


async def main() -> None:
    cases = []
    def check(name: str, expected: str, observed: object, passed: bool) -> None:
        cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})
    workspace = UUID(sys.argv[1])
    other = UUID(sys.argv[2])
    with tempfile.TemporaryDirectory() as directory:
        key_path = Path(directory) / 'secrets/master.key'
        connection = await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True)
        async with connection:
            store = ProviderCredentialStore(connection, key_path)
            try:
                await store.load_active(workspace)
                check('no credential is reported as missing', 'missing', 'loaded', False)
            except CredentialMissing as error:
                check('no credential is reported as missing', 'missing', error.code, True)
            check('no key exists before the first save', 'absent', key_path.exists(), not key_path.exists())
            first = await store.save(workspace, FIRST)
            check('the first save generates a private key', '0600 in 0700', oct(key_path.stat().st_mode & 0o777),
                  key_path.stat().st_mode & 0o777 == 0o600 and key_path.parent.stat().st_mode & 0o777 == 0o700)
            original_key = key_path.read_bytes()
            loaded = await store.load_active(workspace)
            check('the credential resolves for an attempt', 'the stored value, version 1', loaded.reference.version,
                  loaded.client_secret().get_secret_value() == FIRST and loaded.reference.version == 1)
            row = await (await connection.execute(
                "select ciphertext, nonce, tag, status from app_private.provider_credentials where workspace_id = %s", (workspace,))).fetchone()
            raw = b''.join(bytes(part) for part in row[:3])
            check('the row holds no plaintext', 'absent', FIRST.encode() in raw, FIRST.encode() not in raw and len(row[1]) == 12 and len(row[2]) == 16)
            second = await store.save(workspace, SECOND)
            counts = await (await connection.execute(
                "select string_agg(version::text || ':' || status, ',' order by version) from app_private.provider_credentials where workspace_id = %s", (workspace,))).fetchone()
            check('rotation supersedes the old version', '1:superseded,2:active', counts[0], counts[0] == '1:superseded,2:active' and second.credential_id == first.credential_id)
            rotated = await resolve_for_attempt(store, workspace, None)
            check('the next attempt uses the rotated key without a restart', 'version 2', rotated.reference.version,
                  rotated.reference.version == 2 and rotated.client_secret().get_secret_value() == SECOND)
            check('the key was not regenerated', 'same key', key_path.read_bytes() == original_key, key_path.read_bytes() == original_key)
            await connection.execute(
                "update app_private.provider_credentials set workspace_id = %s where workspace_id = %s", (other, workspace))
            try:
                await store.load_active(other)
                check('a row moved to another workspace fails to decrypt', 'refused', 'decrypted', False)
            except Exception as error:  # noqa: BLE001 - judged by its type, so only CredentialDecryptionError passes
                check('a row moved to another workspace fails to decrypt', 'refused', type(error).__name__, type(error).__name__ == 'CredentialDecryptionError')
            await connection.execute(
                "update app_private.provider_credentials set workspace_id = %s where workspace_id = %s", (workspace, other))
            bad = EnvironmentCandidate('.env', 'has space inside')
            good = EnvironmentCandidate('process_environment', 'sk-or-arranged-installation')
            used = await resolve_for_attempt(store, workspace, good)
            check('an ungranted workspace ignores the installation key', 'app version 2', used.reference.source, used.reference.source == 'app')
            for label, encode in (('pickle', pickle.dumps), ('the checkpoint serializer', JsonPlusSerializer().dumps_typed)):
                try:
                    encode(used)
                    check(f'{label} refuses a resolved credential', 'refused', 'encoded', False)
                except TypeError:
                    check(f'{label} refuses a resolved credential', 'refused', 'TypeError', True)
            print(json.dumps({'stage': 'needs_grant'}), flush=True)
            sys.stdin.readline()
            used = await resolve_for_attempt(store, workspace, good)
            check('a granted workspace uses the installation key', 'process_environment, no credential id', used.reference.source,
                  used.reference.source == 'process_environment' and used.reference.credential_id is None)
            try:
                await resolve_for_attempt(store, workspace, bad)
                check('an unusable installation key blocks fallback', 'blocked', 'fell through', False)
            except CredentialBlocked as error:
                check('an unusable installation key blocks fallback', 'blocked', error.code, True)
            key_path.unlink()
            try:
                await store.load_active(workspace)
                check('a lost key reports unavailable storage on read', 'unavailable', 'loaded', False)
            except CredentialStorageUnavailable as error:
                check('a lost key reports unavailable storage on read', 'unavailable', error.code, True)
            try:
                await store.save(workspace, 'sk-or-arranged-after-loss')
                check('a lost key refuses a write', 'unavailable', 'saved', False)
            except CredentialStorageUnavailable as error:
                check('a lost key refuses a write', 'unavailable', error.code, True)
            check('no replacement key was generated', 'absent', key_path.exists(), not key_path.exists())
            versions = await (await connection.execute(
                "select max(version) from app_private.provider_credentials where workspace_id = %s", (workspace,))).fetchone()
            check('nothing was stored in plaintext after the loss', 'still version 2', versions[0], versions[0] == 2)
    print(json.dumps({'cases': cases}))


asyncio.run(main())
