# Runbook: a real Mac sleep during a run

What happens to a run when this Mac sleeps, observed on a disposable stack with a scripted model. A person sleeps the Mac. Nothing here sleeps it or uses `SIGSTOP`, and no paid call is made.

**Last exercised:** [as US-11.10 records](../../../openspec/changes/archive/2026-11-06-us-11-10-real-mac-sleep-proof/verification.md).

## Prerequisites

Docker with the pinned images, the prepared `services/agent/.venv`, and a person at this Mac. Close nothing else first, but expect anything running here to pause too, including Docker's VM and the assistant session.

## Procedure

1. Start the harness. It runs detached, so the sleep doesn't end it:

   ```sh
   python3.12 scripts/qualify_mac_sleep.py start
   ```

2. Wait until `.checks/mac-sleep/state.json` says `ready_to_sleep`, about two minutes. A run is then in progress, with a scripted model call taking 30 seconds, so a sleep will almost always land inside one. The run lasts about ten minutes, so sleep within about five.
3. **Sleep this Mac:** Apple menu, then Sleep. A closed lid also works if nothing external keeps the Mac awake.
4. **Stay asleep for at least two minutes,** which is past the 60-second lease. Check that the screen stayed dark.
5. **Wake it** and sign in. Don't press anything in the app. The harness keeps watching for up to ten minutes, and it does a person's steps once if the run settles paused: it records a charge for an uncertain call, then resumes.
6. Wait until the state says `done`, then read `.checks/mac-sleep/report.json`.

## What to observe

| | Before the sleep | After waking |
|---|---|---|
| Run status | `running`, here and from the API | The API and the database agree, and it's terminal or paused with a reason |
| Receipts | `saved_versions` and `receipts` so far | No path saved twice, and no `unknown` receipt left without a person's ruling |
| Reservations | `reserved` holds the call in flight | Nothing stays held unless a call is uncertain, and then it's the worst case until reconciled |
| Redispatch | Each step sent once | `steps_sent_more_than_once` is empty |
| A real sleep | | `sleep_seconds_by_clocks` is above 20, and `power_log` shows macOS's own `Sleep` and `Wake` |

## How it's assessed

`failures` lists any of `blind_redispatch`, `duplicate_effect`, `false_status` or `stranded_run`, against LC-31 and LM-A07. An empty list means none was seen in this one sleep, and no wake handling is built. Any entry means wake handling is built, and a person sleeps this Mac again under this same procedure. `SIGSTOP` alone never proves that.

## Failure symptoms

- **`no_sleep_during_the_run`:** the run finished first, or the Mac never really slept. Start again.
- **`arranging` for over five minutes:** read `.checks/mac-sleep/run.log`.

## Cleanup

It removes only its own `autobots-disposable-*` project, whatever the outcome. If it was killed, use the cleanup row in [the local Supabase runbook](local-supabase.md).
