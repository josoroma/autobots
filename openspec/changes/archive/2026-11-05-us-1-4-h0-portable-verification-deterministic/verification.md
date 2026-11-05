# Verification — us-1-4-h0-portable-verification-deterministic

Change: us-1-4-h0-portable-verification-deterministic
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `5587a9f`, working tree with this change. No application model call, service or database.

## Scenarios

**Run independently of Claude: observed.**
- `env -i PATH=… HOME=…` real tree: `harness`, `fast` and `full` each exit 0, status `passed`, inputs stable. `full` ran all 17 checks, including `next build`, in about 17 seconds. `fast` recorded `build` as `not_run`.
- Arranged, `sandbox-exec` denying outbound network, control `curl` to openrouter.ai exit 7: `full` exit 0. No model credential was present and no inference was possible.
- Arranged, `PATH=/usr/bin:/bin`: `full` exit 2, status `error`, "nothing was downloaded or installed".
- Arranged in a disposable copy with its own Git history and bootstrapped environments, deleted afterwards. Clean `fast` exit 0. Real Python fault `import os`: `fast` and `full` exit 1 on `ruff_check`. Real TypeScript fault: `fast` exit 1 on `typecheck`, Python steps `not_run`. Corrected: exit 0. `.venv` moved away: `full` exit 2, and it was not recreated.
- `db` and `operations` exit 2, `not_implemented`.
- Fixtures: step timeout and missing executable exit 2, failure outranks unavailable, a step changing a tracked file fails the guard, and a report goes stale on an untracked input. `OPENROUTER_API_KEY` set in the parent does not reach a step or the report. No key name or `sk-or-` value appears in the three real reports.

**Handle unsafe hook input: observed on fixtures.** `tests/harness/test_hooks.py`, run as part of 133 passing harness tests:
- Malformed, oversized, unsupported event or tool: exit 2, empty stdout, nothing echoed, no traceback, through a real dispatcher process.
- Timeout: a real process with stdin held open exits 2 at the shortened deadline; the override cannot extend it. A fake `ruff` that sleeps gives "timed out".
- Missing executable: a missing `harness_lib` gives exit 2, not a traceback. A missing `ruff` and an unstartable one give diagnostics. A missing configured interpreter is a configuration error.
- Symlinks: a loop, `.env` pointing at a plain file, and a plain name pointing at `.env.local` are all denied; an escaping edit is rejected.
- Metacharacters: a filename with `;`, `$()`, backticks, quotes, spaces and Unicode reached a fake `ruff` as one argument after `--`; no marker file appeared, and the name is not in the diagnostic. `ruff` output containing a private value is not echoed.

## Findings

- **Bugs fixed:** a symlink loop raised `RuntimeError` and a broken library import raised at load time. Either gave a traceback and exit 1, which does not block a tool. An unknown tool name was silently allowed.
- **Deviation from DH-05:** `PostToolUse` names the affected domains and `Stop` derives staleness from fingerprints. No dirty marker is stored, because it would duplicate the fingerprint and could disagree with it.
- **Not run by any profile:** generated contract drift (no contract exists), browser fixtures (none configured) and `tests/toolchain` (its copies bootstrap from registries).
- **Deliberate faults here are a sample.** The TypeScript, Python, contract, state and model-transport fault matrix and manifest qualification belong to US-1.6.
- **Event delivery is not qualified.** This session's own hooks did fire: the `PostToolUse` domain message appeared, and `PreToolUse` refused a command over 20,000 characters. These are incidental observations. `assistant.event_delivery_qualification` stays `not_tested`.
- **`sandbox-exec` is deprecated by Apple**, and it denied only outbound IP, as the control confirms. It says nothing about whether a future test reaches the network.
- **Runbook:** the added section's commands were run as written. The other sections are unchanged.
- This is not H0, H1 or product acceptance.
