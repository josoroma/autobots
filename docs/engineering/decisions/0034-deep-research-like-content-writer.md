# Decision 0034: Deep research runs like Deep-Research-Content-Writer

**Date:** 2026-11-18. **Authority:** the owner. They asked that "a run similar to" [Deep-Research-Content-Writer](https://github.com/josoroma/Deep-Research-Content-Writer) "works with our autobot":
- an Expert for the research "langchain for deep agents";
- the same work interpreted as a workflow;
- once it works, README updates and a new README documenting how it works in real life.

In the session they chose two things:
- **Limits:** "Raise limits for all runs", the recommended option, with the reply, run-tree and metered-call values below.
- **Live runs:** "Both, up to US$5.00 each". The coordinator starts one Expert run and one workflow execution from the Studio, each with a US$5.00 budget.

This amends:
- [PRD-Model-Providers](../../PRD/PRD-Model-Providers.md) MP-07's initial limits, and the [Option B contract](../option-b-contract.md#sp-008--budgets-and-model-qualification)'s;
- [PRD-LangChain-Deep-Agents](../../PRD/PRD-LangChain-Deep-Agents.md)' shared initial candidate policy, whose values it sets on the owner's authority rather than from benchmark evidence;
- [PRD-Tool-Catalog](../../PRD/PRD-Tool-Catalog.md#tool-use-record) TU-06;
- [PRD-Studio](../../PRD/PRD-Studio.md#seed) SD-01 and SD-02.

It schedules US-16.6, US-16.7 and US-16.8. The owner can change any choice.

## What the reference does, and why today's limits can't

The reference takes a topic and an optional reader goal. It runs three Google pages of ten results through SerpApi, reads up to 30 pages with `trafilatura`, and keeps them as numbered sources. It then writes a synthesis that chooses the document's format, and one document of 2,000 to 5,000 words. That document has a linked table of contents, `[S-NN]` citations, References, and a closing "Why this format". A citation gate repairs dangling citations, and a report records whether the run `succeeded` or was `degraded`: degraded below 80% of pages read, or with too few sources.

Autobots couldn't do this with its limits as they were:
- **Per reply:** 512 output tokens. `save_artifact` replaces a whole file, so one save held about 380 words.
- **Per run tree:** 24 model calls, 40 tool dispatches, 20 metered tool calls, 4 child runs and 15 active minutes.
- **Between agents:** a workflow's agents get only references to each other's work, since a run reads only its own files.

## Limits for every run (US-16.6)

| # | Choice |
|---|---|
| **L1. Reply** | At most **4,096** output tokens per model call, from 512. Context stays 8K, the target compaction works to, and each call still reserves 32,000 prompt tokens. 4,096 tokens is about 3,000 words, so one save holds a 2,000 to 3,000-word document |
| **L2. Run tree** | **64** model calls (from 24), **96** tool dispatches (from 40, kept at 1.5 for each model call), **8** child runs (from 4) and **45** active minutes (from 15). One repair, two plan revisions, two child levels and two outstanding assignments are unchanged |
| **L3. Metered calls** | A root run tree may make at most **40** metered tool calls, from 20. TU-06's refusal, `tool_budget_exceeded`, is unchanged |
| **L4. Call time** | One model call may take up to **300** seconds, from 120, so a 4,096-token reply can finish streaming. A cancel still interrupts it at once |
| **L5. Spending** | Every call still reserves its worst case before it's sent, and the larger reply makes that reservation larger. The run's budget (US$0.25 to US$5.00) and the daily cap still bound what a run spends. The new limits apply to every pass a worker drives after it restarts with this code |

## A 64K working context (US-16.8)

The first live run of the Deep research writer (US-16.7) failed at its 64-model-call limit after US$0.51, with nothing written. Its one Google search returned 28 results, which were offloaded because they were longer than 4,000 characters. Reading them back took three pages, but only two read-back pages stayed in the model's view, so it re-read pages 0, 4,000 and 8,000 in turn until it ran out of calls. The owner chose a 64K working context ("use 64k").

| # | Choice |
|---|---|
| **L6. Context** | **64K** tokens, from 8K. Compaction works toward 192,000 characters, keeping the earlier 3 characters a token |
| **L7. Tool output in view** | Output up to **48,000** characters stays in the model's view, from 4,000. Longer output is offloaded as before and read back 4,000 characters a page, and the latest **16** pages stay in view, from 2, so anything offloaded can be read whole |
| **L8. Reservation** | Each call reserves **64,000** prompt tokens, from 32,000, so a full view is covered, and a larger request still reserves for its bytes. A view of 192,000 characters stays below Terra's 272,000-token long-prompt rate |

## Reading a published artifact (US-16.6)

| # | Choice |
|---|---|
| **A1. `read_artifact` v1** | In the Files group, it reads one published artifact of the run's workspace by its ID, in pages of lines like `read_run_file` v2: an `offset` from 0 and an optional `limit` of 1 to 20,000 lines. It returns `artifact_id`, `name`, `media_type`, `sha256`, `size_bytes`, `content`, `offset`, `total_lines` and `truncated`. It reads only text: markdown, plain text and JSON |
| **A2. Refusals** | `artifact_not_found` for an unknown ID, another workspace's artifact, or one that isn't published. `artifact_missing` when its stored bytes are gone or don't match their hash. `artifact_not_text` for any other media type. No content is returned with a refusal |
| **A3. Class** | Read-only, no network, no key and no approval, and it isn't metered. Only an Expert grants it, never a plain goal. Its output is untrusted text, like a run file's. Large output is offloaded as any tool's is |
| **A4. Why** | A workflow's agent step gets back only references (`AssignmentResult`): the child run, its outcome and its published artifact IDs. With this tool, the next step can read that work |

## The Deep research writer Expert (US-16.6)

| # | Choice |
|---|---|
| **E1. Expert** | **Deep research writer**: "Researches a topic the way Deep-Research-Content-Writer does: up to 30 Google results, the best pages read and numbered as sources, and one cited document of 2,000 to 3,000 words with references." |
| **E2. Tools** | `google_search`, `google_extract`, `search_web`, `extract_website_content`, `read_artifact`, `read_run_file`, `save_artifact` and `publish_artifact`. The plan tools come with every run |
| **E3. Instructions** | The reference's phases, in order: plan, search, collect, synthesize, write, check, publish. The full text is in `operations/concept_seed.py`. It saves `research/sources.md`, `research/synthesis.md`, `content.md` and `report.md` under its outputs folder, and publishes all four. That folder is `outputs/` in a direct run, and `outputs/child-N/` as a workflow step, which may write only there |
| **E4. Two roles by goal** | Given a topic, it runs every phase. Given a previous step's result, a JSON object with `artifact_ids`, it reviews instead. It reads those artifacts with `read_artifact`, checks every citation against the sources, publishes a corrected document if needed, and publishes `review.md`. It doesn't search again |
| **E5. Status** | A document is `succeeded` when at least 80% of the pages it tried were read and at least 15 sources are cited. Otherwise it's `degraded`, as in the reference. Its report records the counts |

## The Deep research content writer workflow (US-16.6)

| # | Choice |
|---|---|
| **F1. Steps** | input (the topic and the reader's goal) → Research and write (Deep research writer) → to string → Check and report (Deep research writer, as its reviewer) → approval → output |
| **F2. Seeded as** | Published when `google_search` is available on the install, otherwise a draft, like the other workflows of SD-02 |
| **F3. Agent steps get their Experts' tools** | A workflow execution's run is granted the workflow tools plus the tools of the Experts its agent steps name, at each Expert's current version. A child's grant intersects its Expert's with its parent's, so until now a workflow's agent steps got only the general tools: they couldn't search, read pages or read artifacts. The workflow's own blocks never call the added tools, each consequential one still needs its approval, and a requested tool list narrows them like the rest. This follows the [LangChain PRD](../../PRD/PRD-LangChain-Deep-Agents.md)'s "the same tool registry serves direct expert work, delegation, and visual workflows" |

## Seed (US-16.6)

| # | Choice |
|---|---|
| **S1. Seed** | The concept seed adds both, so SD-01 lists seven Experts and seven workflows. The seed never changes what already exists by name. On an install that already has the others, running it again adds only these two. An Expert seed may now carry instructions |

## Live runs (US-16.7)

| # | Choice |
|---|---|
| **R1. Runs** | After US-16.6 is delivered and the owner has updated the install, the coordinator starts two runs for "langchain for deep agents" from the Studio, on the owner's persistent install:<ul><li>one run of the Deep research writer Expert, with a US$5.00 budget;</li><li>one execution of the workflow, with a US$5.00 budget, approved by the owner at its gate.</li></ul>The coordinator neither starts a third run nor raises a budget |
| **R2. Record** | `README-Deep-Research-Content-Writer.md` documents what the two runs did: their outcomes, artifacts, counts, cost and limits as observed. `README.md` and `README-DEV.md` link to it. These are live, one-off observations, not a benchmark |
