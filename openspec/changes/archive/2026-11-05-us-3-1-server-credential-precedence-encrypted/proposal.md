## Why

Runs must authenticate without persisting raw secrets, and SP-007, MP-03 and MP-06 require one source order across native processes, AES-256-GCM storage with a separately protected host key, and no replacement or plaintext path when that key is lost.

## What Changes

- Shared precedence in Python and TypeScript, driven by one fixture set: process environment, the dotenv files in order, then the encrypted app credential. Whitespace counts as absent, and a nonempty value stops resolution even when it's unusable.
- `crypto.py`: AES-256-GCM with a fresh nonce and associated data binding workspace, provider, credential and version.
- `master_key.py`: exclusive creation, `0700`/`0600` checks, and no replacement.
- `store.py` and a migration for `app_private.provider_credentials`: versioned rotation, references for durable state, an explicit grant for the installation key, and `ResolvedCredential`, which refuses to serialize.
- `.env.example` with an empty server-only entry.

**Limits:** no settings UI or live validation, which is US-3.2, and no authentication against OpenRouter. The installation-key "invalid" check here is a local shape check.

## Capabilities

### New Capabilities

- `provider-credentials`: source precedence, encrypted storage, rotation and key loss.

### Modified Capabilities

None.

## Impact

New `application/credentials/`, a migration, `.env.example`, shared fixtures and tests. Adds a direct `cryptography` pin, already locked transitively. Updates `scripts/app_db.py`, `scripts/verify.py`, runbooks and `CODEBASE.md`. Disposable database and temporary keys only. No real credential or model call.
