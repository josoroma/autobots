# Inkling 2 Mini and Bonsai 2.5 on this Mac, measured by hand

**Date:** 2026-11-27. **For:** [Decision 0041](../docs/engineering/decisions/0041-local-model-source.md) A15, the measurements before any story. **Kind:** by-hand observations on the owner's Mac with synthetic prompts. They aren't a qualification: US-3.4's suite didn't run, and nothing went through Autobots' gateway.

## What ran

| | |
|---|---|
| Mac | Apple M3 Pro, 36 GiB, macOS 27.2.1. The Studio's Next.js, API and worker were running, with Docker's stacks for Autobots and three other projects |
| Docker | The limit stayed at 24,576 MiB. Docker restarted at 08:21:54, after Bonsai's correctness run, so its VM held 6.3 GB at the start and 8.6 GB later, against 24 GB before |
| Runtime | Homebrew's llama.cpp 1.1.0 (build 12774, commit `171527522`), upgraded from 0.8.0 with the owner's approval. Homebrew also moved whisper.cpp from 1.9.5 to 1.9.6, since it shares ggml |
| Bonsai 2.5 | `prism-ml/Ternary-Bonsai-2.5-27B-GGUF` at `28a7093c`, `Ternary-Bonsai-2.5-27B-Q2_0.gguf`, 7,673,194,848 bytes, SHA-256 `84496171…b3b9fa`. Sampling from its card's non-thinking settings. Thinking off by `enable_thinking: false` |
| Inkling 2 Mini | `unsloth/Inkling-2-Mini-GGUF` at `8078d149`, `Inkling-2-Mini-UD-Q3_K_XL.gguf`, 13,631,779,296 bytes, SHA-256 `e2d03e8c…273639`. The owner read Thinking Machines' Model Acceptable Use Policy first (A6). Temperature 1.0, from its `generation_config.json`. Thinking requested off by `reasoning_effort: none` |
| Server | `llama-server -c 65536 -np 1 -fa on -ngl 99 --jinja --reasoning-format deepseek` on `127.0.0.1:9931` |
| Probe | [`probe_llama_server.py`](probe_llama_server.py). Raw results and server logs are in the ignored `.checks/local-models/` |

Both weights are pinned in `~/Models/DOWNLOAD-MANIFEST.json`, and each was checked against its SHA-256 when downloaded. `verify-models.py` wasn't run: the manifest still lists three models that `~/Models/README-MODELS.md` says were removed in October, so it would fail on those.

## Correctness

| Probe | Bonsai 2.5 | Inkling 2 Mini |
|---|---|---|
| Plain answer ("ready", 32-token cap) | Pass, 0.8 s | **Fail:** its reasoning used the whole cap. With 1,024 tokens it answered "ready" after about 40 tokens of reasoning, at `none` and at `minimal` alike |
| Automatic tool call | Pass: `calculate("840 * 0.125")` | Pass, the same call |
| Required tool call (`tool_choice: required`) | Pass: `calculate("17 + 25")` | **Fail:** it wrote "4242…" until its 2,048 tokens ran out, with no tool call. The same question with `auto` made the right call in 3.6 s |
| A tool's result answered | Pass: "105" | Pass: "105" |
| One of two tools chosen | Pass: `market_history("BZ=F")` | Pass: `market_history("BZ=F", 5)` |
| JSON-schema output | Pass: San José, 610,000 | Pass: San José, 475,000 |
| Streaming with usage | Pass, first text in 0.5 s | Pass, first text in 3.0 s |
| Thinking off | No reasoning returned | 459 characters of reasoning before a one-line answer |
| Thinking on | 370 characters of reasoning, then the answer | 576 characters of reasoning, then the answer |
| A paragraph in Costa Rican Spanish | Written, in formal neutral Spanish | Written with 3,000 tokens of room. About three-quarters of the 427 tokens were reasoning. With 400 tokens it wrote nothing |

The owner reads the Spanish in the raw results: `spanish_for_the_owner` in each JSON file.

## Speed

Synthetic English prompts. Each larger prompt began with the smaller one, so the cache served that part, and "new tokens" counts only what was read.

| | Bonsai 2.5 | Inkling 2 Mini |
|---|---|---|
| Reading 8,000 new tokens | 89 tokens a second | 143 tokens a second |
| Reading 24,500 more, to 32K | 63 tokens a second (6.5 minutes) | 90 tokens a second (4.7 minutes) |
| Reading 30,500 more, to 62K | 46 tokens a second (11 minutes) | 53 tokens a second (9.8 minutes) |
| The same 32K start again, with a new question | 515 new tokens, 12 s | 515 new tokens, 14 s |
| Writing, short context | 11.4 tokens a second | 19.7 tokens a second |
| Writing at 32K | 7.0 tokens a second | 13.6 tokens a second |
| Writing at 62K | 4.0 tokens a second | 10.1 tokens a second |
| Load time | 6 to 16 s | 12 s |

**The prompt cache works.** A repeated start costs only its new tokens. Without it, every call of a long run would pay the reading time again.

**Reading is the limit on this chip.** Bonsai is dense, so every token passes through all 27B parameters. Inkling uses 3.4B active parameters but runs its middle layers three times, and it reads only 1.1 to 1.6 times faster here. The publishers' Apple figures are from M4 Pro and M5 Pro chips, not this M3 Pro.

## Memory

| | Bonsai 2.5 | Inkling 2 Mini |
|---|---|---|
| Peak footprint of `llama-server`, at a 64K context | 9.4 GB | 6.7 GB |
| Swap, before and after | 5.4 → 8.0 GB (speed run). 9.8 → 18.5 GB (correctness run, before Docker restarted) | 7.9 → 13.5 GB |

The footprint excludes the weights' file pages, which macOS can drop and read again: 7.7 GB for Bonsai and 13.6 GB for Inkling. Swap grew during every run, so the Mac had no room to spare.

## What this means for the runs

These are estimates from the table, at 50 to 90 tokens a second reading and 4 to 20 writing, with the cache working. They aren't measurements of a run.

| Run | On OpenRouter | Expected here |
|---|---|---|
| Market watcher | 76 s | About 10 to 15 minutes. One reply of about 2,500 tokens takes 2 to 6 minutes to write |
| Deep research | About 9 minutes | About 1.5 to 3 hours. 25,335 written tokens alone take 30 to 90 minutes |
| Transcript, the prose | About 3.5 minutes | About 10 to 25 minutes for about 11,000 written tokens, plus the browse |

**Today's limits would stop these runs** (Decision 0034, set per local route by A11):
- **Call time.** A single reply of 4,096 tokens takes 3.5 to 17 minutes here, against 300 seconds allowed.
- **Active time.** Deep research is past 45 minutes.

## What it settles, and what it doesn't

- **Bonsai 2.5 passes every correctness probe,** and its thinking switches off. It is the candidate for the first local profile, for every role (A8). It is slow: deep research would take hours.
- **Inkling 2 Mini is faster, but fails two things the gateway relies on.**
  - Required tool calls fail under llama.cpp 1.1.0, so US-3.4's suite would fail too.
  - It can't stop thinking, so every reply needs room for reasoning.

  It can be offered only if the gateway never sends it `required`, and its route gets a larger output cap (A9). Either way, US-3.4's suite decides, not this probe. A later llama.cpp may fix `required`.
- **Not established:**
  - whether either model completes any Autobots run;
  - whether browser-use can drive a browse with either;
  - whether the Spanish reads as Costa Rican;
  - how either behaves with Autobots' own tool schemas and history.

  Stories LS-1 to LS-6 cover those.
