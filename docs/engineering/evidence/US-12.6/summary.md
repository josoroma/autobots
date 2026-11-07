# US-12.6: the real install at the final code

**Class: live, on the real persistent install on this Mac.** Real OpenRouter calls on Terra, through the install's own API and `worker.main`, at US-12.3's binding, source fingerprint `05916d5e…`. Authorized by [Decision 0013](../../decisions/0013-release-closure.md), for this story alone. This doesn't establish H1 or product acceptance.

**Result: the code that ships ran on the install, and its goal succeeded.** The install is stopped again, with its data kept, at migration 35 of 35.

## What was done, in order

| Step | Result |
|---|---|
| `up` on the recorded project | Started |
| Backup | `backed_up`, all five volumes and the configuration |
| Restore to `autobots-disposable-ed85f795`, an isolated held copy | Held |
| Verify the copy | Passed, including a restore hold and an artifact reading back with its recorded hash |
| Apply on the copy first, with `--restored-copy` | Migrations 33, 34 and 35 applied |
| Remove the copy | Removed |
| Apply on the install | The same three, with 32 already applied |
| Start the API and web | Ready: database, schema, adapter, storage, disk and queue all `ok`. `worker_absent` until the goal's worker started, as expected |
| One goal | Below |
| Stop | API, web and containers stopped, and all 5 volumes kept |

## The goal

| | |
|---|---|
| Goal | `scripts/live_goal.py`'s report, with a required artifact, limit US$0.25, all reserved on the shared ledger first |
| Route | Terra, `openai/gpt-6.1-terra`, the default |
| Outcome | **`succeeded` in about 16 seconds**, verification passed, `report.md` published, 630 bytes, sha256 `7c9ce89c…` |
| Calls | 6, each with a reported charge |
| Reported cost | **US$0.005848** |
| Key usage | `0.916198135` to `0.922047135`, a rise of US$0.005849 |
| Shared ledger | **US$0.315650 of US$1**, which still holds US$0.25 from US-12.4's paused round |
| Afterward | The worker exited 0, no live worker claims inference, and the key is in no durable row or log |

## What stayed as it was

| | Before | After migrations | After the goal |
|---|---|---|---|
| Users, workspaces | 1, 1 | 1, 1 | 1, 1 |
| Runs, all succeeded | 1 | 1 | 2 |
| Published artifacts | 1 | 1 | 2 |
| Checkpoints | 15 | 15 | 30 |
| Events | 5 | 5 | 10 |
| Model calls | 6 | 6 | 12 |
| Migration history rows | 33 | 36 | 36 |

**Listeners:** gateway `127.0.0.1:55321`, database `127.0.0.1:55322`, API `127.0.0.1:8001`, web `127.0.0.1:3000`, and nothing else on those ports. **Other projects:** 32 lines of other projects' containers, ports and volumes, including `finance` and `mentor`, were identical before and after.

Nothing was reset or removed apart from the isolated copy, and nothing was spent beyond the decision.

## Limits

- **The earlier artifact's bytes weren't read back from the install itself,** though its copy verified against the recorded hash from this backup.
- **No browser opened the install in this story.** Readiness comes from the API's status, read with the owner's token. US-11.3 last used a real browser on it.
- **The refusal at the cap** was exercised on an arranged ledger, in US-11.3 and by `qualify_persistent_apply.py` in US-12.3's `db`. The real ledger hasn't come near it.
- **One goal.** It's what was seen once, and says nothing of long runs on the install, a real uncertain call, or sleep on it.
- **The install is stopped.** To use it, follow [the operations runbook's start](../../runbooks/operations.md#start).

The driver, `exercise_install.py`, is kept here, as a file under `scripts/` would void US-12.3's binding. Each step's result is in `report.json`.
