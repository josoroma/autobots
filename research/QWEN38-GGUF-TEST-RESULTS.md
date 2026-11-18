# Qwen3.8 GGUF local qualification results

> **Historical test report — model recommendation superseded.** The final app design uses **OpenRouter-only inference**, with all application services and Supabase/Docker on this Mac. Neither Qwen nor Bonsai is an active app backend. Recommendations below reflect the earlier local-model investigation; actual results and raw evidence remain unchanged. See the [current deployment contract](../docs/PRD/PRD-Local-Mac-Deployment.md).

Tested **2026-11-04** on an **Apple M3 Pro with 36 GiB unified memory**. The result is **13 qualified bounded cases, one unsupported API contract, and one failed task**. The model handled the tested schema, streaming and simple calculator requests, but supplied **38 instead of 42** during a two-step invoice task. Keep this configuration as an **experimental non-MLX structured-output backend**, not the autonomous clone's default. Existing model-role constants remain assigned to Bonsai.

The test server was stopped and **Bonsai was restored on port 8080**, with its expected model identity verified. The Qwen test port is closed and the private restoration pointer was removed. [Assessment](qwen38-gguf-assessment.json), [restoration check](qwen38-gguf-restoration-check.json)

## Artifact and executed configuration

This experiment served the **exact language-model GGUF blob from Ollama's `qwen3.8:27b-q4_K_M` tag using the existing llama.cpp server and Apple's Metal backend**. It did not run the Ollama daemon or qualify Ollama's API. The separately packaged vision projector was not downloaded; the server advertised text-only input/output. [Published Ollama tag](https://ollama.com/library/qwen3.8:27b-q4_K_M), [recorded artifact metadata](qwen38-gguf-artifact.json)

| Item | Evidence |
|---|---|
| Model | Qwen3.8, 27B class; server reports 27,320,697,856 parameters and Q4_K - Medium |
| Verified GGUF size | **16,810,714,464 bytes**, approximately **16.81 GB** |
| Verified GGUF SHA-256 | `f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d` |
| Ollama manifest SHA-256 | `25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e` |
| Retained model file | `~/Models/Qwen3.8-27B-Q4_K_M-Ollama/Qwen3.8-27B-Q4_K_M.gguf` |
| Executed runtime | **llama.cpp 0.8.0**, build **11960**, commit **8642541b2**, AppleClang 21.0.0.21000334, Darwin ARM64 |
| Endpoint during testing | `http://127.0.0.1:18081`, alias `qwen38-local-qualification` |
| Effective context/concurrency | **8,192 tokens**, **one slot**, confirmed through server properties |

The completed file matched the expected size and SHA-256 before loading. The Ollama tag's approximately 18 GB packaged size includes other components; it is not this language-weight file's size or resident memory. The `qwen35` architecture label does not change the model's Qwen3.8 release lineage. [Verification](qwen38-gguf-verification.json), [session and server properties](qwen38-gguf-session.json)

The recorded launch requested `MTL0`, all GPU layers, fitting disabled, batch 512, microbatch 128, and F16 key/value caches. Metal was selected, but the retained log does **not independently enumerate the offloaded layer count**; “all layers” is the requested setting. Speculative decoding was `none`, and the log identifies unused next-token-prediction tensors: **this was not an MTP benchmark**. Prompt reuse and context shifting were disabled. No vision, agent mode or web UI was enabled.

Thinking was disabled through server reasoning flags, zero reasoning budget and `enable_thinking: false`. The timing script observed no thinking output. Protocol requests explicitly used temperature 1.0, top-p 0.95, top-k 20, min-p 0, presence penalty 0 and repeat penalty 1.0. The request's min-p value overrode the server default of approximately 0.05. The separate timing preset is documented below. The executed runtime is the installed **0.8.0**, not the newer 0.9.0 discussed in earlier research. [Pinned server documentation](https://github.com/ggml-org/llama.cpp/blob/8642541b255bfb5dc39cd351a178be09013a55d6/tools/server/README.md), [Qwen parser](https://github.com/ggml-org/llama.cpp/blob/8642541b255bfb5dc39cd351a178be09013a55d6/common/parsers/qwen3-coder.cpp)

## Protocol results and the task failure

The [protocol probe](probe_qwen38_gguf.py) completed **15 cases using 25 HTTP requests** in **162.18 seconds**. Repeated cases used seeds 42, 43 and 44. Tools and text were capped at 256 output tokens; schema requests at 512; the deliberate truncation case at one. Each request had a hard 180-second deadline and the suite an 1,800-second budget. Only fixed local fixtures were available. [Raw probe evidence](qwen38-gguf-probe.json)

| Case | Observed result |
|---|---|
| Health and model identity | **Qualified** |
| Automatic strict calculator, three seeds | **3/3 qualified**: arguments 17 and 25, call IDs and tool-result continuation to 42 |
| Required mode with one allowed calculator, three seeds | **3/3 qualified** |
| Nested strict JSON, three seeds | **3/3 qualified**: required fields, nested objects, enum, bounded arrays, nullable value and no additional properties |
| Text SSE | **Qualified**: assembled text, completion marker, finish reason and usage |
| Required single-tool SSE | **Qualified**: assembled tool arguments/ID and completed result round trip |
| Deliberately truncated JSON | **Qualified negative check**: incomplete output was rejected, not accepted as a complete document |
| Native named tool choice | **Unsupported**, despite a correct calculator response |
| Bounded invoice audit | **Failed semantic check** before executing the proposed verification |

The raw probe reports **14 passes and one failure** because its named-choice case inspected the response rather than proving selection enforcement. The server logged a type error for object-form `tool_choice` and used its default. At this pinned revision, request parsing expects a string and defaults to `auto`; the accepted selection values are `auto`, `none` and `required`. The only object-form request was the named-choice case. Its correct output is real, but it is **not evidence that native named selection worked**. The [offline assessment](assess_qwen38_gguf.py) therefore records 13 qualified, one unsupported and one failed, retaining the original report and its SHA-256. [Request parsing source](https://github.com/ggml-org/llama.cpp/blob/8642541b255bfb5dc39cd351a178be09013a55d6/tools/server/server-common.cpp#L1360), [accepted choices](https://github.com/ggml-org/llama.cpp/blob/8642541b255bfb5dc39cd351a178be09013a55d6/common/chat.cpp#L322)

With one available tool and a prompt explicitly naming it, automatic selection can produce the same answer as enforced named selection. Required mode plus one permitted tool remains a separately tested adapter alternative; it must not be relabeled native named-choice support.

For the invoice task, the model first loaded the correct fixture. It then proposed `verify_invoice_total` with `computed_total: 38`, although the line items require **2×9 + 3×8 = 42**. The tool-call shape and argument types were valid. The semantic validator rejected the incorrect value **before the verification fixture executed**, and no final audit response was requested. This was an attempted two-hop task with a failed second proposal, not two successfully executed tool hops. No external action occurred.

This failure illustrates the practical distinction: schema-valid output and correct tool syntax do not establish correct reasoning. The nested JSON tests reproduced supplied values; they were protocol checks, not difficult planning evaluations. The invoice result is one bounded failure, not a population-level failure rate, but it is sufficient to withhold autonomous-default promotion.

## Measured timing

The timing suite completed one warm-up followed by **three measured requests**. Each used **863 prompt tokens**, generated **128 completion tokens**, reported **zero cached prompt tokens**, and ended with `length`. These were deliberately truncated timing samples, **not completed task answers**. Warm-up is excluded from the statistics. [Original performance evidence](qwen38-gguf-performance.json), [corrected interpretation](qwen38-gguf-performance-summary.json)

| Measured run | First visible content | Request wall time | Server-reported decode rate | End-to-end rate |
|---|---:|---:|---:|---:|
| 1 | 9.6438 s | 26.4322 s | 7.5632 tok/s | 4.8426 tok/s |
| 2 | 10.4314 s | 27.4344 s | 7.4672 tok/s | 4.6657 tok/s |
| 3 | 10.8183 s | 27.8838 s | 7.4390 tok/s | 4.5905 tok/s |
| **Median** | **10.4314 s** | **27.4344 s** | **7.4672 tok/s** | **4.6657 tok/s** |

The headline decode rate is approximately **7.5 tokens/second**, with a measured range of **7.4390–7.5632**. First-content latency ranged from **9.6438 to 10.8183 seconds**. These figures describe this short, uncached workload with thinking disabled.

A metric correction matters here. The original script derived decode rate as `128 / predicted_ms`, while the server's explicit `predicted_per_second` uses **127 decode intervals** for these 128-token completions. That explains the original derived median of approximately 7.526 versus the server-reported **7.4672** used here. Raw evidence remains unchanged; the separate interpretation preserves both meanings. End-to-end rate continues to use actual completion tokens divided by whole-request wall time.

The timing preset was temperature 0.7, top-p 0.8, top-k 20, min-p 0, presence penalty 1.5, repeat penalty 1.0 and seed 42. It differs from the protocol preset. First-content latency excludes role-only SSE chunks; decode rate excludes prefill. Three short trials do not establish tail latency, sustained throughput, long-context performance, or a speed advantage over Bonsai. **No matched Bonsai timing comparison was performed.**

## Memory, lifecycle and restoration

Qwen became ready **10.239 seconds** after launch. Across **144 recorded memory observations**, including **142 with a Qwen process**, pressure remained at level **1**. Peak observed server RSS was **16.565765 GiB**. The post-Bonsai-stop swap baseline and peak were both **159.19 MiB**, so observed swap growth during Qwen testing was **zero**. The earlier pre-stop observation was approximately 262 MiB; it is not the Qwen baseline. [Memory summary](qwen38-gguf-memory-summary.json), [raw samples](qwen38-gguf-memory.jsonl), [session events](qwen38-gguf-session.json)

No memory guardrail fired. This supports feasibility for the tested 8K, single-slot workload, not unrestricted context or concurrency. RSS alone does not capture every unified-memory allocation, and host pressure/swap includes other applications.

Bonsai was stopped at **17:38:35.766 UTC** and its restored model identity was verified at **17:43:28.010 UTC**: approximately **292.24 seconds** of service unavailability. In Costa Rica local time, that was **11:38:35–11:43:28**. The protocol process exited 1 for the task failure; the timing process exited 0. **Both suites finished.** The supervisor's event named `qualification_interrupted` records the aggregate failed qualification; no memory or runtime interruption occurred. Cleanup and restoration completed. That event must not be described as a server crash or restoration failure.

The independent final check confirmed the restored Bonsai process identity, expected model listing, closed Qwen port and removed recovery pointer. The downloaded GGUF remains available; the experimental server does not remain running. [Final restoration check](qwen38-gguf-restoration-check.json)

## Recommendation and reproduction

Retain this backend for controlled structured-output experiments. Before promoting it, require broader tool-selection and task-quality evaluations, explicit named-choice adaptation, and actual client integration tests. Keep deterministic arithmetic and other checkable facts in tools, and validate semantics before committing effects. Existing planner, executor, reviewer and evaluator model assignments remain Bonsai.

To repeat the probes **after separately starting the intended server with the recorded configuration**:

```bash
python3 research/probe_qwen38_gguf.py --base-url http://127.0.0.1:18081 --model qwen38-local-qualification --out /tmp/qwen38-probe-rerun.json
python3 research/benchmark_qwen38_gguf.py --base-url http://127.0.0.1:18081 --model qwen38-local-qualification --out /tmp/qwen38-performance-rerun.json
```

Those commands do not start a server. The supervisor depended on a one-use private restoration bundle, now consumed; it is not a standalone reusable launch command. Preserve this run's evidence when arranging a new session.

This qualification did **not** test vision, the Ollama daemon, Vercel AI SDK or LangChain integration, durable execution, approvals, concurrent agents, long autonomous runs, or the separate MTPLX `llguidance` environment.
