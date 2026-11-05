# Verification — us-5-1-versioned-experts-direct-sessions

Change: us-5-1-versioned-experts-direct-sessions
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `e99143f`, working tree with this change. A real Deep Agents graph with a scripted model and real Postgres on a disposable target, plus the real API and web app in Chromium. `scripts/app_db.py types`: 335 cases passed. `scripts/qualify_identity.py` exit 0, 138 cases, including 5 new browser tests. `--profile full` passed.

## Scenarios

**Preserve configuration versions: observed.**
- A run admitted on version 1 was still running when version 2 removed a tool and changed the instructions. Its stored scope kept the tool, it saved a file with it through the gateway, and its system prompt held version 1's instructions.
- An existing session keeps its pinned revision by default, and new work can choose a later one. On version 2 the same tool is `tool_not_granted`, with no file, and the model is offered only the granted tools. The run records its session, Expert and revision.
- In the browser, an owner saves a revision, the old version's tools stay listed, and a session shows what it grants. The run page shows version 2.
- A stale revision conflicts, a repeated key returns the same Expert, and the runtime role can't rewrite a saved revision.
- Skills are saved in a revision and frozen with it, but nothing loads them, since skill versions are US-8.2. That part of "instructions, tools, skills" is stored and not exercised.

**Route within granted scope: observed.**
- A coordinator session shows its Experts with their real tools and models. A route to an unlisted Expert gives `route_not_granted`, a route with no Expert gives `route_needs_expert`, and the run page lists only the chosen Expert's tools.
- An Expert's model binding reaches only the roles it names, and the others keep the workspace setting. A worker route that differs is refused with `route_not_bound` and no call, and the bound route is recorded in admission as sent.
- A revision can't name a shell, an MCP-style tool, a plan tool, an unapproved model or an unknown role.
- Another workspace gets 404 on the Expert, on a session using it, and in the editor. A member can't create one (403).
- Connectors don't exist, so no connector grant can be added. This is the same as saying it isn't exercised.

## Findings

- **Fixed during this story:** `getSession` duplicated an existing operation ID, shown only as a warning, and the generator refused 201 responses. Sessions are now `getWorkSession` and `createWorkSession`.
- **A coordinator here routes by the user's choice among its list.** No model makes the choice, and specialists running under a coordinator are US-5.2.
- **The editor offers the executor role only.** The API takes all 14.
- **Owner-only revisions are my reading** of PRD 5.3, since a revision changes grants. A member's own sessions weren't exercised in the browser.
- **No independent review.** EPIC-4's first review found blockers in code that had passed these same kinds of tests, so this story's checks may have similar gaps.
