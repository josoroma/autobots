# Decision 0009: Release scope, from US-10.2's blocking findings

**Date:** 2026-11-06. **Authority:** the user, who asked to triage [the release record's 11 blocking findings](../evidence/US-10.2/summary.md#blocking-findings) together and chose one option for each group. Each choice below was the option recommended to them.

## Decision

| Finding | Choice |
|---|---|
| **B1**, no real install | Build a guarded migration path, then stand up and exercise a real persistent stack on this Mac. It uses its own ports, since others were held by an unrelated project, and it doesn't touch that project |
| **B2**, Mac sleep | The owner sleeps this Mac once during a run, on a disposable stack with a scripted model, following a written procedure. Wake handling is built only if that test shows it's needed |
| **B3**, required screens | Build a core subset, and move the rest to later scope. See [revisions](#requirements-revised) |
| **B4 and B5**, review and H1 | One independent review of the final code, which also repeats Gate 0 and settles the 41 minors and open majors. Decision 0003 stays for routine stories. Claude's crash and timeout hook behavior is marked not qualified, and H1 is assessed afterward |
| **B6**, false UI messages | Correct the goal message, and store each route's qualification with its date and limits, so Settings can show it |
| **B7**, design | Move forms to shared components, then capture both-theme screenshots and measure contrast once across all named surfaces, when screens are final |
| **B8**, one role runs | Revised: one model route per run in this release |
| **B9**, run controls | Add pause, cancel, resume and model-call reconciliation to the run page |
| **B10**, named mechanisms | No LangGraph store in this release. Reasoning metadata gets a check, including a capped live trial, as LC-23 stands |
| **B11**, memory scope | Revised: memory is scoped to the workspace in this single-owner release |

| **B3**, run screens | Add a story for what the first choice left open: a model picker, the role map and budgets in the run workspace, costs, errors and evidence links in the inspector, and the MP-07 disclosure at run creation |
| **B6**, LC-17's gate | Revised: no runtime gate. Application code must not request an unqualified feature, enforced by a test |
| **B3**, approval reason | The inbox shows the policy's reason, written by the server, not a model's |
| **B2**, proving a fix | If wake handling has to be built, the owner sleeps this Mac a second time to prove it |

**Spending:** up to US$1 in total, for the reasoning trial and for goals on the real install, using the key in `.env`. It covers nothing else. It's counted by the ledger, which holds a call's worst case until it settles, and actual key usage is recorded beside it.

**What this authorizes:** US-11.2's paid trial, and US-11.3's real stack, persistent database, data and configuration outside this repository, and goals, within the spending above. These are the delivery rule's stopping points for those two stories only. Everything else still stops there.

## Requirements revised

IDs stay, and each requirement's text is edited to match.

- **LC-01, LC-25 and MP-A08:** a run dispatches through one route, its `executor` binding. All 14 bindings still resolve and freeze, and any others that differ don't take effect. A summarizer that differs pauses the run with `route_not_bound`.
- **LC-17:** application code doesn't request an unqualified feature, enforced by a test, with its test date and configuration visible.
- **LC-16:** one workspace can't read another's memory. Separation between users in a workspace is later scope.
- **LC-29:** the worker and checkpointer pass in `agent_runtime`. Memory lives in its own table, and a LangGraph store is later scope.
- **LC-33 and DH-W03:** routine delivery follows Decision 0003, with one independent review of the final code before a release.
- **PRD 12.1:** chat, routines, memory, improvements, skill and knowledge versions, and an Expert test run are later scope. Their API routes stay where they exist.

## What this gives up

- **Role overrides do nothing yet.** A person can set them, and only the executor's takes effect.
- **No chat, and no screens for routines or memory.** A person reaches those through the API.
- **A shared workspace doesn't separate members' memory,** so this release doesn't suit several people sharing one.
- **A single final review** catches defects later than one per story, as reviews here have repeatedly found real ones.

## What this doesn't establish

Anything about the product's readiness. These stories have to be delivered and observed, and US-10.2 assessed again. H1 and product acceptance aren't claimed.

## Reversal

Each revision can be built later under its existing ID. The real install's data stays on this Mac until the owner removes it.
