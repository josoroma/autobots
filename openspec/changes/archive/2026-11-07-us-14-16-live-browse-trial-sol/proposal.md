## Why

US-14.16 and Decision 0019 S6: the owner authorized **one** live `browse_goal` trial with a real model on Sol, capped at US$1. It shows browsing working once from start to finish, not only with a scripted model.

## What Changes

- `autobots.operations.browse_trial` runs the trial, and `scripts/browse_trial.py` drives it on a disposable stack. It is in no verification profile.
- The trial's own process reads only `OPENROUTER_API_KEY` from the owner's key file, as the route qualification does.
- Run setup: an Expert granting `browse_goal`, and a run admitted with no model choice, so `researcher` is frozen on Sol, with a US$1 budget.
- The call: one `browse_goal` call from `https://example.com/` with `allowed_domains` `example.com` and `iana.org`, approved for the owner and run through the real gateway, approval, loop middleware, admission and isolated executor.
- Each step's model is the shared factory (`chat_model` over the SDK client, `require_parameters`, no fallbacks) on the researcher's prepared attempt from a fresh catalog. Only the credential comes from the key file instead of the workspace's stored key.
- Before the session is removed, the trial records the proxy's connected hosts.
- The result goes to `.checks/browse-trial/result.json`. A second start refuses before any container or model call unless `--owner-requested-repeat` is given.

## Capabilities

### New Capabilities

- `live-browse-trial`: the capped, once-only live browse.

### Modified Capabilities

None.

## Impact

`services/agent/src/autobots/operations/browse_trial.py`, `scripts/browse_trial.py`, offline tests, and the operations runbook. This makes one paid run of at most US$1.
