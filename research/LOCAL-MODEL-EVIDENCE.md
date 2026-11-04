# Local model evidence and qualification plan

> **Historical evidence — earlier runtime plan superseded.** The current application uses **OpenRouter-only inference** with local Mac services and Supabase/Docker. This report does not require installing, starting or qualifying Bonsai for the app. See the [current deployment contract](../PRD-Local-Mac-Deployment.md) and [provider contract](../PRD-Model-Providers.md). Raw observations below are retained as recorded.

Research date: **2026-11-04**, America/Costa_Rica. Applies to both clone PRDs. This report separates current observations, historical local records, upstream claims, and proposed requirements.

Later follow-up: [Qwen3.8-27B Q4_K_M local test](QWEN38-GGUF-TEST-RESULTS.md) documents a separate non-MLX run using the exact Ollama language weights through installed llama.cpp. It does not alter the Bonsai observations below or repair its missing `llguidance` dependency.

## 1. What was actually inspected

| Item | Observation | Evidence |
|---|---|---|
| Host | Apple M3 Pro, 38,654,705,664 bytes = 36 GiB unified memory | Current `sysctl -n machdep.cpu.brand_string hw.memsize` |
| Model folder | `/Users/josoroma/Models/Ternary-Bonsai-2-27B-MTPLX-Optimized-Speed` exists | Current directory inspection |
| Serving runtime | MTPLX **2.12.2**, MLX **0.32.2**, mlx-lm **0.31.3** | Current installed distribution metadata in `~/Models/.venvs/mtplx` |
| Runtime environment | Dedicated Python 3.12 environment | Installed environment path; historical doctor report records Python 3.12.9 |
| Model identifier | `mtplx-bonsai-2-27b-optimized-speed` | Pack manifest and live `/v1/models` |
| Minimum runtime | MTPLX **2.12.0** | Pack's `min_engine_version` |
| Format | Custom ternary/Hadamard MLX pack, `prism_hadamard_qwen35`; safetensors weights | `config.json`, `mtplx_runtime.json`, model directory |
| Included components | Language/vision weights, MTP sidecar, tokenizer/template, Hadamard metadata, license/notice | Current directory inspection |
| Pack defaults | Temperature 1.0, top-p 0.95, top-k 20, MTP depth 1 | Local `mtplx_runtime.json` |
| Active probe context | 8,192 tokens, reported by `/v1/models` | Live smoke probe |
| Constrained JSON prerequisite | `llguidance` absent; installed MTPLX metadata lists `llguidance>=1.8` under the `server` extra | Current distribution metadata and HTTP 400 |

The runtime manifest also has an older `mtplx_version: 2.11.3` provenance field. It is **not** the installed runtime version and does not supersede `min_engine_version: 2.12.0`. The actual installed version was read separately.

Local evidence files, inspected without editing:

- [Model runtime manifest](/Users/josoroma/Models/Ternary-Bonsai-2-27B-MTPLX-Optimized-Speed/mtplx_runtime.json)
- [Pack manifest](/Users/josoroma/Models/Ternary-Bonsai-2-27B-MTPLX-Optimized-Speed/MTPLX_PACK_MANIFEST.json)
- [Existing model setup notes](/Users/josoroma/Models/README-MODELS.md)
- [Historical verification record](/Users/josoroma/Models/VERIFICATION.json)
- [Historical smoke tests](/Users/josoroma/Models/SMOKE-TESTS.json)
- [Installed runtime freeze snapshot](/Users/josoroma/Models/.runtimes/requirements-mtplx.txt)
- [Saved CLI help](/Users/josoroma/Models/.runtimes/mtplx-serve-help.txt)

The historical verification record reports Hugging Face revision `03bd60bb82755f2446f5083426dca9708eb8e0fe`, 18 checked files and 8,847,918,956 bytes with no errors. This research did **not** rehash the 8.85 GB model. A historical `2 + 2` smoke test passed; that alone was insufficient evidence for agent integration.

## 2. Live protocol experiment

A temporary localhost-only server was started on port **18080**, using the existing model/runtime. It was stopped after the experiment. No packages were installed, models downloaded, application built, or external action tools executed.

Exact launch configuration:

```sh
"$HOME/Models/.venvs/mtplx/bin/mtplx" serve \
  --model "$HOME/Models/Ternary-Bonsai-2-27B-MTPLX-Optimized-Speed" \
  --host 127.0.0.1 --port 18080 --no-auth \
  --context-window 8192 --max-tokens 512 --depth 1 \
  --reasoning off --agent-rewrites off --no-stats-footer \
  --scheduler-mode serial
```

`--no-auth` was used only for the short localhost probe; deployed access requires the application's chosen authentication/network boundary. `--agent-rewrites off` prevents the serving runtime's optional agent transcript rewrites from obscuring application-owned context behavior. Native macOS serves Metal inference; putting this MLX runtime into a Linux container is not the proposed deployment.

The client requested temperature 1.0, top-p 0.95, top-k 20, seed 42, `enable_thinking: false`, and a 160-token output cap. The complete reproducible probe and results are retained:

- [Probe script](probe_local_model.py)
- [Raw result record](local-model-probe.json)

| Check | Actual result | Interpretation |
|---|---|---|
| `/health` and `/v1/models` | Pass | Correct local model loaded, MTP active, effective context 8,192 |
| Automatic function selection | Pass | Produced `add_integers` with integer arguments 17 and 25, a call ID, and `finish_reason: tool_calls` |
| Tool-result continuation | Pass | Client supplied fixed calculator result 42; model answered `17 + 25 = 42` |
| Forced named function selection | Pass | Same valid arguments and successful continuation |
| Strict JSON schema | **Fail: HTTP 400** | Optional `llguidance` dependency is absent; runtime refuses unconstrained substitution |
| Text SSE | Pass | Text deltas, completion, `[DONE]`, and usage received |

Observed request-group wall times: automatic two-request tool roundtrip **6.280 s**; forced two-request roundtrip **3.812 s**; short text stream **0.553 s**. These are one-seed smoke timings with prefix-cache effects, short prompts and different output lengths. They are **not** comparative performance benchmarks, representative latency percentiles, or reliable tokens-per-second measurements.

The server's terminal diagnostics also reported a background warmup failure with `compressor_full` memory-pressure evidence; a later 2,560-token warmup completed and the request probes above succeeded. This reinforces the need to measure available system memory and swap under the full application workload. It does not establish that 36 GiB is insufficient for Bonsai, nor that longer contexts are safe. The terminal diagnostics were observed during the run; the JSON artifact retains the HTTP probe results, not the complete server log.

The schema failure returned:

```text
response_format type 'json_schema' requires the optional llguidance dependency
(pip install llguidance); refusing to silently return unconstrained output
```

This was a request for a two-field object, not a complex schema. Therefore neither PRD may assume schema support in the current installation. The scripts do not execute arbitrary functions selected by the model: only a fixed test calculator result is supplied.

## 3. Consequences for both architecture options

1. **Use the exact served ID.** A filesystem folder, Hugging Face repository ID, and HTTP model ID are different identifiers. Validate `/v1/models` at startup; fail if the configured model is absent.
2. **Keep every inference role on Bonsai.** Planner, executor, researcher, reviewer, evaluator, router, memory curator, and summarizer each get an explicit configurable role entry initially resolving to the same local endpoint/model. Subagent defaults and framework summarization defaults must be overridden as well.
3. **Do not enable schema support by declaration.** AI SDK `supportsStructuredOutputs` stays false until qualification. LangChain uses explicit tool/function strategies rather than an untested default JSON-schema route.
4. **Validate all tool arguments in application code.** The successful smoke test does not establish enforcement of the complete schema language or reliability across tasks. Reject unknown fields, tool names and identifiers before execution.
5. **Qualify structured output in an isolated runtime first.** Resolve and pin the MTPLX `server` extra's `llguidance` dependency in a separate test environment, rerun simple and adversarial schema cases, then test both client SDKs. Do not silently upgrade this existing shared environment. A valid alternate implementation is tool-call structured results plus server-side validation and bounded repair.
6. **Start with one inference slot.** Logical specialist contexts may be concurrent, but all generation competes for the same M3 Pro memory and compute. Release the model slot before a parent waits for child work, or a one-slot scheduler can deadlock.
7. **Use explicit context accounting.** Begin at the verified 8,192-token profile; budget system instructions, tools, history, retrieved evidence and output together. Large framework defaults may already exceed the usable prompt budget. Reduce the toolset and compact before attempting larger context.
8. **Treat MTP separately from planning.** MTP accelerates token generation using draft/verification mechanics. It is not a planner, reviewer, independent agent, or second opinion about the user's goal.
9. **Use lexical retrieval first.** Other embedding/reranking models are present in `~/Models`, but the user's initial requirement assigns only Bonsai. Neither embedding nor reranking compatibility is established by a chat endpoint. PostgreSQL full-text search/BM25 and metadata filters satisfy the first retrieval phase without introducing another model.
10. **Do not route local inference through a cloud-model default.** SDK provider objects must specify the local base URL/model. Cloud fallback, implicit gateway model strings and default Anthropic/OpenAI models are disabled. An OpenAI-compatible protocol does not mean requests use OpenAI's service.

## 4. What remains unproven

| Gate | Required experiment before production claim |
|---|---|
| SDK compatibility | Actual AI SDK WorkflowAgent provider serialization/replay and ChatOpenAI/Deep Agents tool roundtrips |
| Complete tool protocol | Streamed tool-call fragments/IDs, tool-choice none/required, malformed arguments, duplicate calls, nested schemas, enums and rejected calls |
| Agent capability | Multi-step research with cited artifacts; planning revision; recovery from tool failure; honest incomplete outcome; task-grounded review |
| Context | Large tool schemas, near-limit inputs, summarization fidelity, evidence retained across offload/compaction |
| Durability | Kill worker during inference, before/after tool commit, during approval and child execution; resume without duplicated effects |
| Safety | Adversarial tool output, path traversal/symlink escape, cross-workspace access, untrusted skill content and denied external actions |
| Performance | Warm/cold TTFT, p50/p95 task latency, RAM/swap, queue wait, cancellation latency and thermal behavior |
| Reasoning modes | Compare off against supported medium at equal resource budgets; do not assume xhigh improves completion |
| Vision | Actual image requests with task-relevant scoring; `/health` advertises vision but this experiment was text-only |
| Production transport | Authenticated access, disconnect/cancel behavior, model restart and unavailable-machine behavior |

## 5. Upstream evidence and its limits

Prism identifies Bonsai 2 as **Qwen3.8-27B-derived**. The architecture identifier `prism_hadamard_qwen35` is not a claim that the weights derive from Qwen3.5. Conventional Qwen3.8 MLX quantizations therefore provide a representation/runtime comparison within the same lineage. See the [follow-up model research](HUGGINGFACE-SLM-STRUCTURED-OUTPUT.md) for verified candidates, memory tradeoffs and qualification requirements.

The [MTPLX model card](https://huggingface.co/Youssofal/Ternary-Bonsai-2-27B-MTPLX-Optimized-Speed) identifies the specialized pack, its MTP head and minimum engine. The [MTPLX API documentation](https://github.com/youssofal/MTPLX/blob/main/docs/api.md) describes its compatibility routes. These are capability descriptions; the local result record is the authority for the checks actually run here.

The publisher's [Bonsai performance page](https://www.mtplx.com/models/bonsai-2-27b/) reports measurements on an M5 Max. This host is an M3 Pro, so those figures are not adopted as our throughput targets. [Prism's base model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-mlx-2bit) documents the underlying ternary model; automated generic library examples on model hosting pages are not proof that an unmodified loader can serve this specific custom pack.

The pack includes [LICENSE](/Users/josoroma/Models/Ternary-Bonsai-2-27B-MTPLX-Optimized-Speed/LICENSE) and [NOTICE.txt](/Users/josoroma/Models/Ternary-Bonsai-2-27B-MTPLX-Optimized-Speed/NOTICE.txt). Preserve applicable notices when redistributing artifacts. The independent clone should have its own application code and branding; AutoGPT Platform source licensing is discussed separately in the AutoGPT PRD.
