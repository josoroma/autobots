# Verification — us-11-6-model-role-choice-settings

Change: us-11-6-model-role-choice-settings
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Choose the workspace default | PASS | `scripts/qualify_identity.py`, disposable stack, real browser. Models lists each approved model's canonical and wire identity. A run admitted before saving freezes Terra's executor. After the owner saves DeepSeek on the screen, a new run freezes DeepSeek and the earlier one still reads Terra. The choice survives a reload, and axe found nothing |
| Say what a role override does | PASS | The screen's text is asserted: only the executor's binding dispatches, others don't take effect, and a differing summarizer pauses with `route_not_bound`. With `coder` overridden it names `coder`. With only the executor overridden, it names the 13 others, says so of the summarizer, and holds after a reload, with the stored overrides exact |
| Refuse a stale save | PASS | A second session saves after this screen loaded. Saving here shows `Reload the page`, and the stored policy equals the second session's save |

Checks on the final code: `fast` and `harness` exit 0, the identity qualifier's cases all pass, and `openspec validate` is clean.

## Findings

**First test run:** one assertion was wrong, as "executor," appears in the screen's own sentence. It now checks the list itself. The code didn't change for this.

## Limits

- **That a differing summarizer really pauses isn't exercised here.** The screen says what Decision 0009 revised, and `goal_loop` holds that behavior, tested elsewhere.
- **The frozen choice was read, not run.** The scripted worker has one route, so these runs were cancelled, and no model was called.
- **A member's screen isn't asserted here.** A member reads the policy, and the route refuses their save, as `settings.spec` covers. The form still shows for them.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
