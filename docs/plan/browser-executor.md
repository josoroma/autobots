# Plan: isolated browser executor, admitted browser model, and goal-driven browsing

**Date:** 2026-11-07. **Status:** approved by the owner as [Decision 0018](../engineering/decisions/0018-browser-executor.md), and superseded as a source by [PRD-Tool-Catalog.md](../../PRD-Tool-Catalog.md#isolated-browser-executor). Kept as the reasoning behind them.

This drafts the two prerequisites [US-14.12](../../SPECS.md#us-1412-goal-driven-browsing) is blocked on, by [Decision 0017](../engineering/decisions/0017-tool-catalog.md#conflicts-with-existing-rules) C3 and C4, and proposes answers to US-14.12's three open questions. Like [the tool-catalog plan](tool-catalog.md), it is input for a decision and a PRD addition, not a backlog edit. [Section 8](#8-draft-stories-in-specs-style) holds the stories in SPECS style, ready for ingestion once the owner approves.

## Contents

1. [What US-14.12 is waiting for](#1-what-us-1412-is-waiting-for)
2. [The shape: agent in the worker, browser in a box](#2-the-shape-agent-in-the-worker-browser-in-a-box)
3. [What exists today](#3-what-exists-today)
4. [Isolated browser executor](#4-isolated-browser-executor)
5. [Admitted browser model](#5-admitted-browser-model)
6. [The browse_goal tool](#6-the-browse_goal-tool)
7. [Decisions the owner makes](#7-decisions-the-owner-makes)
8. [Draft stories in SPECS style](#8-draft-stories-in-specs-style)
9. [Risks](#9-risks)
10. [Sources consulted](#10-sources-consulted)

## 1. What US-14.12 is waiting for

| Blocker | Rule it comes from | What would clear it |
|---|---|---|
| **An isolated executor** | PRD 9.1: arbitrary execution, a "shell or browser action with broad capabilities", is "disabled until isolated executor and policy are qualified". PRD 9.3: `FilesystemBackend` "is not a security sandbox". `ToolRegistry.register` refuses `arbitrary_execution`. | A browser that can't reach this Mac, its services, its files or its credentials, with bounded resources and a lifetime tied to the run's lease (US-14.13 below) |
| **An admitted-model adapter** | `AGENTS.md`: every application model call uses the two approved OpenRouter profiles and the shared gateway, with no alternative provider. `.claude/rules/model-gateway.md`: budgets, reservations and receipts apply to every call. `AdmittedModel` refuses a call outside an admitted dispatch. | browser-use's model calls made as ordinary admitted calls of the run, never by browser-use's own clients (US-14.14 below) |
| **Three open questions** | US-14.12's Open Questions | Proposed answers in [section 6](#6-the-browse_goal-tool), decided in [section 7](#7-decisions-the-owner-makes) |

## 2. The shape: agent in the worker, browser in a box

browser-use is two things: an **agent loop** that asks a model what to do next, and a **browser** it drives over the Chrome DevTools Protocol (CDP). The plan separates them.

```
worker process (trusted)                       disposable container (untrusted)
┌─────────────────────────────────┐            ┌──────────────────────────────┐
│ ToolGateway → browse_goal        │   CDP      │ headless Chromium, non-root  │
│   browser-use Agent loop         │──────────▶ │ no host mounts, no env       │
│   AdmittedBrowserModel ──▶ model │ (loopback, │ read-only root, tmpfs only   │
│     admission, reservation,      │  random    │ CPU, memory, pids capped     │
│     receipt, OpenRouter profile  │  port,     └──────────────┬───────────────┘
│   step and time budget           │  token)                   │ all web traffic
└─────────────────────────────────┘                            ▼
                                               ┌──────────────────────────────┐
                                               │ egress proxy (the URL guard) │
                                               │ https only, public IPs only, │
                                               │ connect pinned to the        │
                                               │ checked address              │
                                               └──────────────────────────────┘
```

- **The model never runs in the container.** The agent loop stays in the worker, so its model calls go through the same admission, budgets and receipts as every other call, and no key ever enters the container. browser-use defines its own async chat-model protocol (`ainvoke(messages, output_format)`), which an Autobots adapter can implement.
- **The browser never runs on the host.** browser-use can drive a browser elsewhere through `Browser(cdp_url=...)`. Chromium runs in a disposable container whose only way out is a proxy that applies the URL guard.
- **The worker never trusts the page.** Page text reaches the model as third-party data, as web tools already label it, and the tool's result is labelled the same way.

The alternative, running browser-use whole inside the container with a key or a model proxy, puts the agent loop beside untrusted pages and needs a model channel out of the box. It's rejected here.

## 3. What exists today

- **Gateway and record:** `ToolGateway` checks grants, schemas, ownership, approvals and the metered limit, then records every dispatch (US-14.3). `arbitrary_execution` is refused at registration and at dispatch (`capability_disabled`).
- **Admission:** `adapters/loop_middleware.py` has `AdmittedModel`, which answers only inside an admitted dispatch, and `LoopMiddleware._admitted_call`, which reserves, records an invocation ticket and settles spend. `ModelRoute` comes from the run's frozen policy. `ModelRole` already has `researcher`.
- **URL guard:** `adapters/url_guard.py` (US-14.8) checks scheme, userinfo, length and every DNS answer, and revalidates redirects. Its known gap is DNS rebinding between check and connect, partly closed by a connected-peer check.
- **Docker:** disposable Compose projects exist for qualification (`infra/disposable/`, `scripts/disposable_db.py`) with target guards, and `tool_env()` gives a child process no inherited credentials. Nothing yet starts a container per tool call.
- **Catalog:** `browse_goal` is a planned descriptor, `disabled_by_policy` with reason `isolated_executor_not_qualified`, never registered.

## 4. Isolated browser executor

**Proposed story: US-14.13.**

### 4.1 Container

| Property | Proposal |
|---|---|
| Image | A pinned Chromium image by digest. Candidates: the official Playwright image for the pinned Playwright version (already used for browser tests), or a minimal `chromium-headless-shell` image. Chosen by decision B1 |
| User | Non-root, no added capabilities (`--cap-drop=ALL`), `no-new-privileges`, default seccomp profile |
| Filesystem | Read-only root; a size-capped `tmpfs` for the profile and cache; no bind mounts, no volumes, no Docker socket |
| Environment | Empty apart from what Chromium needs. Never the worker's environment: no `OPENROUTER_API_KEY`, no provider keys, no database URL |
| Resources | CPU 1, memory 1 GiB, pids 256, by decision B2 |
| Network | An internal Docker network with no route out except the egress proxy. CDP published on `127.0.0.1` only, on a random port, guarded by a per-session token |
| Lifetime | One container per `browse_goal` call. Removed when the call ends, fails, times out, is cancelled, or the lease is lost. A sweeper removes any left by a crashed worker, by a label naming the run and generation |

### 4.2 Egress proxy

The only way out of the browser network. It applies the URL guard to every request, including subresources, redirects and WebSocket upgrades:

- `https` only (port 443), with `CONNECT` targets checked like any guarded URL.
- Every DNS answer must be public; the proxy then **connects to the address it checked**, which closes US-14.8's rebinding gap for this path.
- No loopback, private, link-local, carrier-grade NAT, metadata or multicast destination, so the browser can't reach Supabase on `127.0.0.1:55321`, the API, the Docker host or cloud metadata.
- Per-call caps on bytes and requests, and a log of hosts (not paths or queries) for the tool-use record.

Where it runs is decision B3: a small sidecar container on both networks, or a proxy inside the worker on a loopback port. The sidecar keeps the browser network fully internal; the in-worker proxy avoids building an image. The draft recommends the sidecar.

### 4.3 Lease and cancellation

The executor is owned by one attempt. The worker heartbeats as today; losing the lease, a run cancel, or the tool's time budget closes the CDP session and removes the containers. Cancellation reaches the browser within one step.

### 4.4 Qualification

The story is done when a disposable run shows each refusal live, not from a fake: the browser can't fetch `http://127.0.0.1:<API port>`, the Supabase port, `169.254.169.254`, a private address, or a public name that resolves to loopback; it can't read a host file by `file://`; a download is refused or discarded; it can't exceed its memory or pids; and cancelling the run removes the container within a bounded time. This is the qualification PRD 9.1 asks for, and the only thing that would lift `capability_disabled` for this one tool.

## 5. Admitted browser model

**Proposed story: US-14.14.**

- **Adapter.** `AdmittedBrowserModel` implements browser-use's chat-model protocol. Each `ainvoke` becomes one admitted call of the run: a reservation against the run's budget, an invocation ticket and receipt, the run's frozen policy for the `researcher` role on an approved OpenRouter profile, the shared transport, and settlement of actual spend. Uncertain outcomes follow the existing rules (no blind repeat).
- **No other model path.** browser-use's own clients are never constructed. Any call browser-use would make for itself (for example a page-extraction helper) either goes through the adapter or is turned off; a test proves a call outside the adapter fails as `UnadmittedModelCall`.
- **Structured output.** browser-use asks for typed actions. The adapter passes `output_format` as the route's structured-output mode where the profile supports it, and otherwise refuses with a typed code. Whether Terra's route enforces it is checked, not assumed (`.claude/rules/model-gateway.md`).
- **Budget.** Each step is one model call, counted in the run's `model_calls` and spend, so a browsing tool can't spend outside the run's limits. Its steps are also capped by the tool's own `max_steps`.
- **Signature check.** browser-use's protocol is third-party and versioned; the story pins the browser-use version and tests the adapter against it with a scripted model, offline.

## 6. The browse_goal tool

Proposed answers to US-14.12's open questions.

### 6.1 Contract

| Input | Constraint |
|---|---|
| `task` | 1–2000 characters: what to find out |
| `start_url` | Guarded `https` URL |
| `allowed_domains` | 1–10 domains; navigation outside them is refused by the proxy for this call |
| `max_steps` | 1–20, default 10 |
| `max_seconds` | 10–300, default 120 |

| Output | Meaning |
|---|---|
| `summary` | The agent's final answer, labelled third-party, cut to the shared text budget |
| `visited` | URLs visited, without query or fragment |
| `steps`, `model_calls` | What it used |
| `stopped` | `done`, `max_steps`, `max_seconds`, `refused_action`, `cancelled` |

Public fields: `start_url`, `allowed_domains`, `max_steps`, `stopped`, `steps`, `visited` count. Never `summary` or page text.

### 6.2 What it may do

The first version **reads only**: navigate, click links, scroll, read and extract. It may not type into fields, submit forms, sign in, upload or download. Those actions are removed from the agent's action set, and the proxy refuses non-`GET` requests that carry a body, so a click that would submit is stopped there too. Typing and submitting would later need an approval per action, bound to the action's arguments, under a separate decision.

### 6.3 The URL guard in the browser

Every navigation and subresource request passes the proxy's guard, and `allowed_domains` narrows navigation further. Subresources from other public hosts (images, scripts) are allowed but counted; private destinations are never reachable.

### 6.4 Class and grants

`browse_goal` stays `arbitrary_execution`. The registry allows that class for a tool only when its executor reports qualified (US-14.13's check), and only through an Expert grant with approval `always`: each call waits for a person, who sees the task, start URL and allowed domains. It counts as one metered call, and its model calls count as the run's model spend.

## 7. Decisions the owner makes

| # | Decision | Recommendation |
|---|---|---|
| B1 | Browser image | The official Playwright image for the pinned Playwright version, by digest |
| B2 | Resource caps | 1 CPU, 1 GiB memory, 256 pids, 256 MiB `tmpfs`, 300 seconds |
| B3 | Where the egress proxy runs | A sidecar container on the internal and default networks |
| B4 | Model role and profile | `researcher`, on the run's frozen policy (Terra by default) |
| B5 | Allowed actions | Read only, as section 6.2; typing and submitting need their own decision |
| B6 | Approval | Every call, as `always`, with task, start URL and domains shown |
| B7 | Adding `browser-use` | Pinned in `uv.lock` by the story that needs it (US-14.14), with its dependency tree reviewed; Chromium only in the image, never on the host |
| B8 | Live qualification | Only the isolation tests in 4.4 run live, on a disposable stack, with a scripted model. A run with a real model is a separate, owner-capped task |

## 8. Draft stories in SPECS style

**Draft for ingestion. Not in `SPECS.md`.** Their sources would be a PRD addition (sections 4 to 6) and a decision answering section 7, neither written yet. Once they exist, US-14.12's two `External:` lines become dependencies on US-14.13 and US-14.14, and its open questions are answered by the decision.

````markdown
### US-14.13: Isolated browser executor

Status: BLOCKED

As a workspace owner
I want a browser that runs in a disposable container with no way to reach this Mac, its services, its files or its credentials
So that a browsing tool can read the web without arbitrary access.

Source:
- [Proposed isolated browser executor](PRD-Tool-Catalog.md#isolated-browser-executor) — not yet written.
- [Tool contract](PRD-LangChain-Deep-Agents.md#91-tool-contract)
- [Filesystem and execution boundaries](PRD-LangChain-Deep-Agents.md#93-filesystem-and-execution-boundaries)
- [SP-005](docs/engineering/option-b-contract.md#sp-005--local-services-and-isolation)

Acceptance Criteria:

```gherkin
Scenario: The browser can't reach this Mac or a private network
  Given a running executor on a disposable stack
  When its browser requests the API's and Supabase's loopback ports, the Docker host, a private address, the metadata address, a public name resolving to loopback, or a file URL
  Then each is refused by the egress proxy or the browser, and a public https page loads

Scenario: Nothing of the host enters the container
  Given an executor started by a worker that holds model and provider keys
  When its environment, filesystem and mounts are inspected
  Then no key, database URL, host path or Docker socket is present, the root is read-only and it runs as a non-root user without added capabilities

Scenario: Bounded and owned
  Given a browsing call in progress
  When it exceeds its memory or time cap, the run is cancelled, or the worker loses its lease
  Then the browser stops within a bounded time, its containers are removed, and a sweeper removes any a crashed worker left
```

Dependencies:
- US-14.8
- US-14.3
- External: The owner's decision on B1, B2 and B3.

Tasks:
- [ ] Start and remove a pinned, hardened browser container per call, with CDP on loopback behind a token.
- [ ] Add the egress proxy that applies the URL guard and connects to the address it checked.
- [ ] Tie the executor to the attempt's lease and to cancellation, with a labelled sweeper.
- [ ] Qualify every refusal live on a disposable stack.

Open Questions:
- None beyond the External decision.

### US-14.14: Admitted model for browser-use

Status: BLOCKED

As a workspace owner
I want every model call a browsing tool makes to be an admitted call of its run
So that browsing spends only within the run's budget, on an approved profile, with receipts.

Source:
- [Proposed admitted browser model](PRD-Tool-Catalog.md#admitted-browser-model) — not yet written.
- [Decision 0017, C4](docs/engineering/decisions/0017-tool-catalog.md#conflicts-with-existing-rules)
- [SP-008](docs/engineering/option-b-contract.md)

Acceptance Criteria:

```gherkin
Scenario: Each step is an admitted call
  Given a browser-use agent driven by a scripted model through the adapter
  When it takes three steps
  Then three invocations are reserved, recorded and settled on the run's frozen role and profile, and counted in the run's model calls and spend

Scenario: No other model path
  Given the browser-use agent
  When anything tries a model call outside the adapter, or the run's budget is exhausted
  Then the call is refused as unadmitted or budget_exceeded, and nothing is sent

Scenario: Structured actions are enforced or refused
  Given a route that does or doesn't enforce structured output
  When the agent asks for a typed action
  Then the route enforces it, or the call is refused with a typed code before it is sent
```

Dependencies:
- US-3.3
- External: The owner's decision on B4 and B7.

Tasks:
- [ ] Pin browser-use, and implement its chat-model protocol over model admission, reservations, receipts and the frozen route.
- [ ] Prove no other model path with a scripted model, offline.

Open Questions:
- None beyond the External decision.
````

**US-14.12, revised** (for the same ingestion):

- **Dependencies:** US-14.3, US-14.8, US-14.13, US-14.14, and External: the owner's decision on B5 and B6.
- **Scenarios,** replacing "Stays disabled until qualified": a read-only browse against a public test site on a disposable stack, with a scripted model, that returns a labelled summary and the visited URLs and is recorded as a tool use; a navigation outside `allowed_domains` and a form submission refused; `max_steps` and `max_seconds` stopping it with `stopped` set; each call held for approval; and, with the executor unqualified, `browse_goal` still `disabled_by_policy` and refused.
- **Open Questions:** none, once the decision answers section 6.

## 9. Risks

- **Escape is the whole risk.** A Chromium exploit from a hostile page lands in the container; the controls in 4.1 bound what it reaches. Keep the image current: an old browser is the most likely escape.
- **The proxy is the boundary.** A bug in it reopens loopback access. It needs its own refusal tests, run live (4.4), not only fakes.
- **CDP is powerful.** Whoever reaches the CDP port controls the browser. Loopback-only, a random port and a per-session token keep it to the worker.
- **Prompt injection.** Pages will try to steer the agent. Read-only actions, allowed domains and approval per call limit what a steered agent can do; page text stays third-party data.
- **Spend.** Twenty steps is twenty model calls. The run's budget and `max_steps` both bound it, and approval shows the limits.
- **Dependency weight.** browser-use brings a large dependency tree; Chromium stays in the image, never on the host.
- **Third-party protocol drift.** browser-use's model protocol and `Browser(cdp_url=...)` are versioned upstream; the adapter pins a version and is tested against it.

## 10. Sources consulted

- Repository: `PRD-Tool-Catalog.md`, Decision 0017, `SPECS.md` (US-14.12), `adapters/loop_middleware.py`, `adapters/url_guard.py`, `application/tool_gateway.py`, `domain/models.py`, `infra/disposable/`, `scripts/disposable_db.py`.
- [browser-use: remote browsers](https://docs.browser-use.com/customize/browser/remote), for `Browser(cdp_url=...)`.
- [Mozilla.ai cookbook: browser-use with any LLM](https://docs.mozilla.ai/cookbooks/browser-use-with-any-llm), for a custom model implementing browser-use's `ainvoke(messages, output_format)` protocol.
- [tessl.io: browser-use LLM integration](https://tessl.io/registry/tessl/pypi-browser-use/0.7.0/files/docs/llm-integration.md), third-party notes on that protocol. Both protocol sources are third-party; the story confirms the protocol against the pinned version's own source.
