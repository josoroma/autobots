# Verification — us-3-1-server-credential-precedence-encrypted

Change: us-3-1-server-credential-precedence-encrypted
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `6dc31ce`, working tree with this change. Fixtures and a real disposable Postgres. Keys are arranged placeholders, and master keys were temporary. No real credential, OpenRouter call or persistent target. `--profile db` under `env -i` exit 0, with 59 of 59 `app_db` cases. `full`, `fast` and `harness` exit 0, with 151 pytest tests.

## Scenarios

**Preserve source precedence: observed in both languages.** `contracts/fixtures/credential-precedence.json` has 18 cases, read by both pytest and `node --test`: full source order, test mode skipping `.env.local`, whitespace-only and empty entries treated as absent, trimming, quotes, `export` and comments, and `NEXT_PUBLIC_*` not counting. A nonempty bad higher value is returned rather than skipped. Against the real store, a granted workspace with an unusable installation key raises `credential_invalid`, though a valid app credential exists. An ungranted workspace ignores the installation key.

**Persist only protected secret material: observed, except browser state.**
- Real rows through `autobots_runtime`: no plaintext in the row, a 12-byte nonce and a 16-byte tag. `authenticated` and `anon` are denied, and no credential table is in `public`.
- Rotation: `1:superseded,2:active`, the same credential ID, the next attempt uses version 2 without a restart, and the key is not regenerated.
- A ciphertext moved to another workspace fails to decrypt. A wrong key, flipped ciphertext, wrong nonce, wrong tag, and wrong workspace or version all fail.
- `ResolvedCredential` is refused by `pickle` and by LangGraph's checkpoint serializer, including nested in state. A `CredentialReference` serializes and holds no secret. Repr, str and logs show no plaintext.
- **Browser state:** no route or UI touches credentials yet, so this holds by absence. US-3.2 owns the real path.

**Handle key loss: observed.** With rows present and the key removed: reads and writes both raise `credential_storage_unavailable`, no replacement file appears, and no new row is written. Fixtures refuse a missing, short, world-readable, open-parent and symlinked key. Creation is exclusive, and an existing key is unchanged.

## Findings

- **`SecretStr` and dataclasses are written to LangGraph checkpoints in plaintext.** Observed with `JsonPlusSerializer`. `ResolvedCredential` began as a frozen dataclass with `SecretStr`, and its `__reduce_ex__` guard passed `pickle` while the checkpoint serializer wrote the key. It is now a plain class, with a test. **Worker stories must keep `SecretStr`, and any client holding a key, out of graph state.** `test_secret_str_is_not_safe_in_checkpoints` pins this behavior.
- **"Invalid" is only a shape check here.** Real authentication is US-3.2's, and blocking on an authentication failure of a higher-priority key must be enforced there.
- **`ChatOpenRouter` holds a `SecretStr`,** which is fine only while it stays inside an attempt.
- **Config root and mode aren't wired into a running process.** The functions take them explicitly; US-3.2 wires them.
- **Python and TypeScript parse a small dotenv subset,** not `@next/env`'s full grammar. Fixtures keep the two implementations identical, but a multi-line or interpolated value in a real file could differ from what Next.js itself loads into `process.env`.
- **Loss recovery isn't implemented.** Replacing credentials after a real key loss needs an explicit procedure, stated in the runbook.
- **`app_db` prints no plaintext,** but the fixture values are placeholders by design. No real key has been through this path.
- This is not H1 or product acceptance.
