<p align="center">
  <img src="docs/assets/autobots-logo.svg" alt="Autobots" width="260">
</p>

<p align="center">
  <a href="README.md">Product overview</a> ·
  <a href="README-DEV.md">Developer guide</a> ·
  <b>Deep research, live</b> ·
  <a href="SPECS.md">Backlog</a> ·
  <a href="CODEBASE.md">Codebase</a>
</p>

# Deep research, the Deep-Research-Content-Writer way

Autobots can research a topic the way [Deep-Research-Content-Writer](https://github.com/josoroma/Deep-Research-Content-Writer) does: search Google, read the best pages, number them as sources, and write one cited document with a report on how well that went. It does this two ways: as an Expert you give a topic to, and as a workflow of two agent steps and an approval.

This page explains how, and then what really happened when both ran live on the owner's install for the topic "langchain for deep agents", on 2026-11-18 and 2026-11-19. It took five attempts, and the failures are recorded with what fixed them. These are one-off observations on one install, not a benchmark.

[Decision 0034](docs/engineering/decisions/0034-deep-research-like-content-writer.md) sets every choice here. [US-16.6](SPECS.md#us-166-deep-research-runs-like-deep-research-content-writer), [US-16.8](SPECS.md#us-168-a-64k-working-context-for-deep-research) and [US-16.9](SPECS.md#us-169-the-plan-survives-compaction) built it, and [US-16.7](SPECS.md#us-167-live-deep-research-on-the-install-documented) is these runs.

## Contents

- [What the reference does](#what-the-reference-does)
- [How Autobots runs it](#how-autobots-runs-it)
  - [As an Expert](#as-an-expert)
  - [As a workflow](#as-a-workflow)
  - [The limits that make it fit](#the-limits-that-make-it-fit)
- [What the live runs did](#what-the-live-runs-did)
  - [Five attempts](#five-attempts)
  - [The Expert run](#the-expert-run)
  - [The workflow execution](#the-workflow-execution)
- [Compared with the reference](#compared-with-the-reference)
- [Run it yourself](#run-it-yourself)
- [Where it is defined](#where-it-is-defined)

## What the reference does

Deep-Research-Content-Writer is a Python command line and API. It takes a topic and an optional reader goal, and goes through four stages:

1. **Search:** three Google pages of ten results, through SerpApi.
2. **Collect:** it reads up to 30 of those pages with `trafilatura`, and keeps the readable ones as numbered sources.
3. **Author:** a synthesis chooses the document's format. Then it writes one document of 2,000 to 5,000 words, with a linked table of contents, `[S-NN]` citations, References and a closing "Why this format". A citation gate in code repairs dangling citations.
4. **Report:** the run is `succeeded`, or `degraded` when fewer than 80% of its pages were read or it found too few sources.

## How Autobots runs it

Autobots has no special pipeline for this. The same agent loop that runs every goal runs these phases, with the tools an Expert grants, inside a durable, metered and budgeted run.

| The reference | Autobots |
|---|---|
| A SerpApi Google search, three pages of ten | `google_search` with `max_results: 30`, which pages through SerpApi itself |
| Pages read with `trafilatura` | `google_extract`, which reads up to five pages a call directly from their sites, obeying robots.txt, and converts them with `trafilatura` |
| Numbered sources | `research/sources.md`, the sources numbered S-01 onward with their excerpts |
| A synthesis that chooses the format | `research/synthesis.md` |
| One long document | `content.md`, 1,800 to 2,400 words, written with one `save_artifact` |
| A citation gate in code | The model's own check phase, and in the workflow a second agent that re-checks every citation |
| A report, `succeeded` or `degraded` | `report.md`, with the same 80% rule and at least 15 sources |
| A run workspace you can resume | Run files under `outputs/`, published as artifacts. A run is checkpointed and survives restarts |

### As an Expert

**Deep research writer** is one of the seven Experts the concept seed creates. It grants eight tools: `google_search`, `google_extract`, `search_web`, `extract_website_content`, `read_artifact`, `read_run_file`, `save_artifact` and `publish_artifact`. Every run also has the plan tools, `propose_plan` and `complete_task`.

Its instructions follow the reference's phases, in order:

1. **Plan, once:** search, collect, synthesize, write, check, publish. When a plan is in force, continue it.
2. **Search:** `google_search` for up to 30 results, and once or twice more with close variants when fewer than 20 are useful. `search_web` only when Google isn't available.
3. **Collect:** read the best pages five at a time, aiming for 15 to 30, and save the sources after each batch.
4. **Synthesize:** the findings, the gaps and the document's format.
5. **Write:** 1,800 to 2,400 words, so the whole document fits in one 4,096-token reply. It goes in `save_artifact`, never in a reply.
6. **Check:** every `[S-NN]` against the sources, and the status by the 80% and 15-source rule.
7. **Publish:** all four files, then one short final line.

The full text is in [`concept_seed.py`](services/agent/src/autobots/operations/concept_seed.py). The owner can edit it in the Experts editor, and each save is a new version.

### As a workflow

<p align="center">
  <img src="docs/assets/readme/deep-research-workflow.svg" alt="The Deep research content writer workflow: input, Research and write by the Deep research writer, to string, Check and report by the same Expert as reviewer, the owner's approval, and output. The research step publishes sources, synthesis, content and report. Only their artifact IDs reach the check step, which reads them back with read_artifact and publishes a corrected content.md and review.md. Observed: approved by the owner and succeeded, 45 model calls, 49 tool calls, US$0.45 of a US$3.75 budget, 17 sources cited, degraded with 18 of 30 pages read, and no key in any artifact." width="100%">
</p>

**Deep research content writer** is one of the seven seeded workflows. It is published when `google_search` is available on the install, and a draft otherwise.

- **Research and write** assigns the topic to the Deep research writer. It runs as a child run with its own plan, and writes only under `outputs/child-1/`.
- **To string** turns that step's result into the next step's goal. A child returns only references: its outcome and its published artifact IDs, never their text.
- **Check and report** gives that goal to the same Expert. Given artifact IDs instead of a topic, it reviews instead of researching. It reads the artifacts whole with `read_artifact`, checks every citation, publishes a corrected `content.md` if needed and a `review.md`, and doesn't search again.
- **Approval** waits for the owner in Approvals. Nothing after it runs until they decide.

Two things made this possible:
- **`read_artifact`** reads a published artifact of the run's workspace by its ID, in pages of lines. It is read-only, needs no key and isn't metered.
- **Experts' tools for agent steps.** A workflow execution is granted the tools of the Experts its agent steps name. Before this, a child's grant, the intersection of its Expert's and its parent's, held only the general tools, so an agent step couldn't search or read pages.

### The limits that make it fit

Decision 0034 raised these for every run, on the owner's choice:

| Limit | Before | Now |
|---|---|---|
| Output tokens per model call | 512 | 4,096, about 3,000 words |
| Model calls, tool dispatches, child runs per run tree | 24, 40, 4 | 64, 96, 8 |
| Active time per run tree | 15 minutes | 45 minutes |
| Metered tool calls per run tree | 20 | 40 |
| Time for one model call | 120 seconds | 300 seconds |
| Working context | 8K tokens | 64K tokens, compacted toward 192,000 characters |
| Tool output kept in view | 4,000 characters, two read-back pages | 48,000 characters, sixteen read-back pages |
| Prompt tokens reserved per call | 32,000 | 64,000 |

A compacted call also sees the run's plan, with each task marked done or open, so a long run continues its plan instead of proposing a new one. The budget, US$0.25 to US$5.00 a run, and the workspace's daily limit still bound what a run spends, and every call still reserves its worst case before it is sent.

## What the live runs did

### Five attempts

All five ran for "langchain for deep agents" on the owner's persistent install, started from the Studio, with OpenRouter and SerpApi keys. Each budget was at most US$5.00, and the later ones were lower to stay within the workspace's daily limit.

| # | Date | Run | Outcome | Cost | What it taught |
|---|---|---|---|---|---|
| 1 | 2026-11-18 | Expert | Failed: model calls limit | US$0.506340 | With an 8K context, 28 search results were offloaded to three read-back pages, but only two stayed in view. The run re-read them in turn until its 64 model calls ran out, with nothing written. [US-16.8](SPECS.md#us-168-a-64k-working-context-for-deep-research) moved every run to a 64K context |
| 2 | 2026-11-19 | Expert | Failed: repair limit | US$0.232595 | It searched, read and saved its sources, then lost its plan at its first compaction. It proposed a new one twice, and the plan guard refused both. [US-16.9](SPECS.md#us-169-the-plan-survives-compaction) pins the plan through compaction |
| 3 | 2026-11-19 | Expert | **Succeeded** | US$0.522194 | [The Expert run](#the-expert-run) below |
| 4 | 2026-11-19 | Workflow | Failed: research step stopped, plan incomplete | US$0.254494 | The research step finished search, collect and synthesize, then re-proposed its plan without a reason, which was refused, and ended its turn with write, check and publish still open. The instructions now say to propose the plan once, to keep the document to one reply, and never to put it in a reply. That was saved as Expert version 2 in the Experts editor |
| 5 | 2026-11-19 | Workflow | **Succeeded**, approved by the owner at its gate | US$0.453547 | [The workflow execution](#the-workflow-execution) below |

The five cost US$1.97 together. No run came near its budget: what stopped the failures were the run-tree limits, which is what they are for.

### The Expert run

Run 3, the Deep research writer at version 1, with a US$4.75 budget. It took about eight minutes.

- **Spend:** US$0.522194, in 43 model calls and 49 tool calls, with one repair.
- **Tools:** `google_search` 4, `google_extract` 11, `search_web` 2, `extract_website_content` 1, `read_offload` 6, `read_run_file` 3, `save_artifact` 10, `publish_artifact` 4, `complete_task` 6 and `propose_plan` 2, of which one was refused.
- **Plan:** all six tasks completed.

It published four artifacts:

| Artifact | Bytes | What it holds |
|---|---|---|
| `research/sources.md` | 8,648 | The sources it kept, numbered, with excerpts |
| `research/synthesis.md` | 3,063 | Findings, gaps and the chosen format |
| `content.md` | 18,022 | "LangChain Deep Agents: A Practical Guide to Building and Operating Them": about 2,450 words with a linked table of contents, H2 and H3 sections, References S-01 to S-12 and a cited "Why this format" |
| `report.md` | 2,561 | **Degraded:** 12 sources cited, under 15 |

The sources were mostly the LangChain documentation's Deep Agents pages, the LangChain blog and the project's GitHub repository.

### The workflow execution

Run 5, the workflow at version 1 with the Expert at version 2, with a US$3.75 budget. The whole tree made 45 model calls and 49 tool calls for US$0.453547, all of it in the two agent steps.

**Research and write** took about seven minutes and US$0.398622. It proposed one plan and completed all six tasks, with no refusal: `google_search` 3, `google_extract` 8, `save_artifact` 12, `read_run_file` 3, `complete_task` 6, `publish_artifact` 4 and `propose_plan` 1, 37 tool calls.

| Artifact | Bytes | What it holds |
|---|---|---|
| `research/sources.md` | 8,949 | 17 sources, numbered, with excerpts |
| `research/synthesis.md` | 3,502 | Findings, gaps and the chosen format |
| `content.md` | 16,367 | "LangChain for Deep Agents: a practical guide": about 2,300 words, 8 sections and 6 subsections, citing S-01 to S-17 |
| `report.md` | 2,586 | **Degraded:** 18 of 30 page requests were readable, 60%, under the 80% rule. The 15-source rule was met |

**Check and report** took about 80 seconds and US$0.054925, in 12 tool calls: `read_artifact` 4, `read_run_file` 1, `save_artifact` 2, `publish_artifact` 2, `complete_task` 2 and `propose_plan` 1. It read all four artifacts, then checked each citation against the saved excerpts, not only the source titles. It found claims that those excerpts didn't fully support, such as context offloading, a managed deployment option and the shape of the example's call. It narrowed or labelled each one.

| Artifact | Bytes | What it holds |
|---|---|---|
| `content.md` | 15,379 | The corrected guide, about 2,150 words, still citing exactly S-01 to S-17 |
| `review.md` | 2,413 | **Final status: degraded**, with the checks it made and what it couldn't confirm, such as running the example code |

**Approval** then held the check step's exact result, its outcome and its two artifact IDs, for the owner. The owner approved it about nine minutes later in Approvals, which takes two presses. The output step completed, and the execution succeeded. Nothing was spent after the agent steps.

No artifact of any run held a key: every one was scanned for the shapes of OpenRouter, SerpApi, Tavily, Jina, GitHub and Google keys, JWTs and 64-character hex secrets.

## Compared with the reference

- **Length.** Autobots aims for 1,800 to 2,400 words, against the reference's 2,000 to 5,000, because one save is one reply of at most 4,096 tokens. The three documents came out at about 2,150 to 2,450 words.
- **Sources and status.** The runs cited 12 and 17 sources. The reference's two published examples cited 18 and 22. All four documents were reported `degraded`, for different reasons: here too few sources, or too few pages read; there over 5,000 words and too few sources.
- **Citation checks.** The reference repairs citations in code. Here the model checks them in its check phase, and the workflow's second agent re-checks them against the saved excerpts. That found and fixed overclaims, which a syntax-level gate wouldn't, but it is a model's judgment, not a guarantee.
- **Counts.** The agents estimate word counts and can't list every failed URL, because they have no code tool in this grant. The run's own records hold the exact tool calls.
- **What Autobots adds.** Every call is metered and reserved before it's sent, the run survives a restart, every tool call is recorded with its inputs and outcome, and the workflow stops for the owner before it delivers.

## Run it yourself

You need an install with inference on, an OpenRouter key and a SerpApi key. Spending is real.

1. Set the SerpApi key at **Settings → Keys & vars**, or as `SERPAPI_API_KEY` for the worker and the API ([operations runbook](docs/engineering/runbooks/operations.md)).
2. Seed the concept Experts and workflows into your workspace, as the [local app runbook](docs/engineering/runbooks/local-app.md#seed-the-concept-experts-and-workflows-optional) shows. On a workspace that already has the others, it adds only these two.
3. **As an Expert:** in the composer, pick the Deep research writer, write the topic and, if you like, the reader's goal, set a budget, and start. Follow it on its run page: the plan, every tool call, and the artifacts as they are published.
4. **As a workflow:** open **Workflows → Deep research content writer**, and run its published version with the topic as its `in` input and a budget. Each agent step links to its own child run. When it reaches the approval, decide it in **Approvals**.

## Where it is defined

| What | Where |
|---|---|
| The choices: limits, tools, the Expert, the workflow and these runs | [Decision 0034](docs/engineering/decisions/0034-deep-research-like-content-writer.md) |
| The Expert's instructions and the workflow's steps | [`services/agent/src/autobots/operations/concept_seed.py`](services/agent/src/autobots/operations/concept_seed.py) |
| `read_artifact` | [PRD-Tool-Catalog](docs/PRD/PRD-Tool-Catalog.md#file-tools) FI-02 and [`artifact_tool.py`](services/agent/src/autobots/application/artifact_tool.py) |
| The seed's Experts and workflows | [PRD-Studio](docs/PRD/PRD-Studio.md#seed) SD-01 and SD-02 |
| The stories and their delivered changes | [US-16.6 to US-16.9](SPECS.md#us-166-deep-research-runs-like-deep-research-content-writer) in SPECS.md, archived under [openspec/changes/archive/](openspec/changes/archive/) |
