# Verification — us-4-5-private-artifacts-staged-publication

Change: us-4-5-private-artifacts-staged-publication
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `0df1b6d`, working tree with this change. A real disposable Supabase stack, with real Storage, PostgREST, Postgres and the API and web app in a browser. No model call beyond a scripted fake. `scripts/qualify_identity.py` exit 0, 91 cases. `--profile full` passed, and `scripts/app_db.py types` regenerated the row types.

## Scenarios

**Publish a verified object: observed.**
- A real upload was read back and compared, then committed `published` with its sha256 and size, and an `artifact.published` event. The stored bytes equal the input.
- The object path sits under the workspace and run. A member can't select the path column (403). Repeating an operation returns the same artifact with 1 row.
- Unsafe names, types outside the allowed set and oversized files are refused before storing.
- Another workspace sees no metadata (PostgREST `[]`), can't fetch the object from Storage (400), and gets 404 from the API. A signed-out download gets 401. The adapter refuses an unscoped path. A member downloads the verified bytes as an attachment with `nosniff` and `no-store`.
- `publish_artifact` works through the gateway and the scripted loop, with bytes from the run's saved file, and honors path grants. It is only offered when storage is configured.

**Reconcile interrupted publication: observed, with interruptions arranged by a wrapper over real Storage.**
- Interrupted before the upload and after it, both rows stay `staged`, and members can't see them.
- Recovery published the verifiable one, reported `never.md` as incomplete and marked it `failed`, and removed an orphan object that had no row. Running it again changes nothing.
- An existing object with other bytes is refused with `artifact_hash_mismatch`, and never published.
- A published object that is deleted or altered is reported `missing` by recovery, with an `artifact.missing` event. The API returns 409 and no bytes, and checks each download's hash, so an altered object isn't served even before recovery runs.
- A stale worker's publish stays `staged`. An interrupted tool call reports `unknown`, and replaying it finishes the same operation with 1 row.

## Findings

- **Event sequences no longer follow the run version.** `sequence = version` would have collided with the first event that isn't a status change, so `runs.event_sequence` assigns them. Sequences for status-only runs are unchanged.
- **Nothing calls `reconcile_run` on a schedule yet.** It's a function, which US-4.7's recovery should call.
- **The download route has no generated client,** because the generator requires a JSON response model, and it's marked out of the OpenAPI schema. The 30-second BFF timeout and buffered bodies suit these small text files, and larger ones would need streaming.
- **Judgment calls:** a 1 MB cap, three text media types, and removing orphans during recovery. PRD 5.3 allows removal, and the sources don't fix the cap or types. Retention isn't built.
- **The API process now holds the service role key** when `AUTOBOTS_SERVICE_ROLE_KEY` is set. The worker's Storage access will need the same when a worker process exists.
- **Not checked:** the real process-death path for publication, since a wrapper raised the interruption. Backup and restore of objects belongs to the operations stories.
