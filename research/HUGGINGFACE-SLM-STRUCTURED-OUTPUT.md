# Hugging Face local models for tools, structured results, and AutoGPT-style agents

> **Historical research — deployment recommendation superseded.** The current app runs locally on this Mac with local Supabase/Docker and **OpenRouter-only inference**. Local model candidates and proposed qualification steps in this report are not active app requirements. See the [current deployment contract](../PRD-Local-Mac-Deployment.md) and [provider contract](../PRD-Model-Providers.md). Recorded observations remain unchanged.

Research date: **2026-11-04**. Target: **Apple M3 Pro, 36 GiB unified memory**. This is source-based evaluation and a qualification plan. No candidate weights were downloaded or run for this report, and no runtime packages were installed. The only local model results remain the [Bonsai HTTP probe](local-model-probe.json).

## 1. Recommendation

**Keep Bonsai as the initial model, qualify structured output independently, and benchmark Qwen3.8-27B at 4-bit before considering a replacement.** For cheaper specialist work, shortlist Qwen3.5-4B and Granite 4.2 3B. Add NuExtract3 only if document extraction becomes a substantial workload.

The decisive findings are:

1. **A model replacement cannot repair the observed missing dependency.** MTPLX rejected `response_format: json_schema` because `llguidance` was absent. That request did not measure Bonsai's ability to produce schema-valid results. Either qualify the decoder dependency in an isolated environment or use a validated function-result protocol.
2. **Bonsai 2 is already Qwen3.8-27B-derived.** Its ternary/Hadamard representation changes the storage and execution requirements. Comparing it with conventional Qwen3.8 MLX quantizations is useful, but does not introduce an independent model family. The `qwen35` substring in an architecture identifier does not identify the model's release generation. [Prism model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-mlx-2bit)
3. **Within the requested Qwen 3.8 range of 8B–27B, I verified 27B only.** The official catalog contains 27B, Flash-Next and 2.4T-A95B variants, including FP8 releases. I found no official Qwen3.8-8B, -9B or -14B. Qwen3.5-9B is a real smaller alternative from a different generation. [Official Qwen repository](https://github.com/QwenLM/Qwen3.8), [dated catalog snapshot](qwen38-official-catalog.json)
4. **Start the larger-model comparison at 4-bit.** Standard Qwen3.8-27B MLX weights occupy about 16.05 GB; an MTPLX dynamic-quantization pack with sidecars occupies about 20.68 GB. These are different artifacts. Neither size establishes actual resident memory or application performance.

The existing PRD role constants remain on `mtplx-bonsai-2-27b-optimized-speed`. The candidates below are an evaluation catalog, not an activated routing configuration.

## 2. What each layer must solve

| Layer | Responsibility | What it cannot establish alone |
|---|---|---|
| Model | Choose an appropriate tool, infer arguments, extract evidence, plan and review | Valid JSON or a correct business decision on every request |
| Chat template and parser | Render tools/history and convert native model output into API tool calls | Authorization or argument correctness |
| Constrained decoder | Restrict generation to its supported grammar/schema language | Factual grounding, appropriate tool selection, full JSON Schema semantics |
| Application validator | Check types, required fields, unknown fields, limits, references and business rules | Whether a schema-valid answer is factually correct without task-specific checks |
| Executor | Apply permissions, idempotency, budgets and recovery rules | Turn a malformed or unauthorized model suggestion into a valid action |

The [actual probe](local-model-probe.json) established automatic and forced named function round trips and short text streaming. It did **not** establish streamed tool calls, universal schema compliance, meaningful planning quality, or agent recovery. The schema error was HTTP 400, not a generated malformed answer.

Prefer one of these explicit protocols:

- **Decoder-constrained result:** a qualified `response_format` request, followed by parsing, original-schema validation and semantic checks.
- **Function-based result:** a synthetic function such as `submit_plan` or `submit_extraction`, followed by exactly the same validation. This function records a candidate result; it does not execute the plan.

For the second route, require the expected function name, a complete call with an identifier, schema-valid arguments, and an acceptable completion status. Reject extra calls and unexpected executable tools. Allow at most one bounded repair attempt; otherwise return a typed validation failure. Never execute partially streamed arguments, guess a truncated JSON suffix, or treat plain text as an authorized call.

## 3. Qwen 3.8: parameter count, precision, and actual MLX choices

**27B** means the model's parameter class. **4-bit, 6-bit and 8-bit** describe weight representations. `Qwen3.8-27B-8bit` is a 27B model; it is not an 8B model.

Qwen's official 27B release is Apache 2.0, with a hybrid attention architecture and native multimodal inputs. Its published agent benchmarks make it a relevant candidate for planning and execution, but do not predict a quantized M3 Pro deployment's completion rate. Its nominal 262K context is also not a usable-memory promise for this Mac. [Official model card](https://huggingface.co/Qwen/Qwen3.8-27B)

### 3.1 Standard MLX comparison

Sizes below sum selected `.safetensors` weight files from the Hugging Face API. They exclude tokenizer/configuration files and any separately distributed MTP head. GB means 1,000,000,000 bytes; GiB means 1,073,741,824 bytes. The host's 36 GiB is approximately 38.65 GB.

| Verified artifact | Weight size | Assessment for this 36 GiB Mac |
|---|---:|---|
| [mlx-community/Qwen3.8-27B-4bit](https://huggingface.co/mlx-community/Qwen3.8-27B-4bit) | **16.05 GB / 14.95 GiB** | **First standard MLX candidate.** Plausible memory headroom; must measure under the actual application. |
| [PocketAiHub/Qwen3.8-27B-MLX, `6bit/`](https://huggingface.co/PocketAiHub/Qwen3.8-27B-MLX/tree/main/6bit) | **22.78 GB / 21.21 GiB** | Secondary precision experiment after 4-bit. Less headroom for context, buffers, browser and database. |
| [mlx-community/Qwen3.8-27B-8bit](https://huggingface.co/mlx-community/Qwen3.8-27B-8bit) | **29.50 GB / 27.48 GiB** | Poor default for this full application. Weights alone consume most of the machine's memory. |
| [mlx-community/Qwen3.8-27B-bf16](https://huggingface.co/mlx-community/Qwen3.8-27B-bf16) | **54.71 GB / 50.96 GiB** | Exceeds physical memory before inference overhead. Exclude from this host's implementation plan. |
| [PocketAiHub/Qwen3.8-27B-MLX, experimental `2bit/`](https://huggingface.co/PocketAiHub/Qwen3.8-27B-MLX/tree/main/2bit) | **11.01 GB / 10.26 GiB** | Do not prioritize for agents: the publisher records failed tool and vision checks. |

`mlx-community/Qwen3.8-27B-6bit` was not publicly retrievable during this research. The verified 6-bit recommendation refers specifically to PocketAiHub's **subdirectory**, not a guessed standalone repository. Downloading the entire multi-variant PocketAiHub repository would unnecessarily retrieve all precisions; any later download should select one variant and its provenance files.

These converters are distinct from the original Qwen publisher. The MLX Community cards record conversion using **mlx-vlm 0.6.8**. That is useful provenance, not proof that every OpenAI-compatible MLX server implements the tools, reasoning and schema features our clients require. [4-bit artifact card](https://huggingface.co/mlx-community/Qwen3.8-27B-4bit), [configuration](https://huggingface.co/mlx-community/Qwen3.8-27B-4bit/blob/10c35caafbb80f7dc6a7a432cdd11af10a6d4818/config.json)

### 3.2 MTPLX choices compatible with the project's direction

These packs retain MTP/vision sidecars, so their full weight totals differ from standard MLX conversions. The publisher's names describe intended profiles; they do not establish our relative speed or quality.

| Verified pack | Total weight files, including sidecars | Decision |
|---|---:|---|
| Existing Ternary-Bonsai-2-27B-MTPLX-Optimized-Speed | Historical verified **8.85 GB full artifact**, including non-weight files | Keep as measured protocol baseline; its larger task quality remains unmeasured. |
| [Qwen3.8-27B-MTPLX-Bare-Speed](https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Bare-Speed) | **16.29 GB / 15.17 GiB** | Lower-memory MTPLX comparator; quantify any task-quality loss. |
| [Qwen3.8-27B-MTPLX-Optimized-Speed](https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed) | **20.68 GB / 19.26 GiB** | Preferred *MTPLX* Qwen candidate if measured memory headroom permits. Compare completed tasks per minute against Bonsai and the smaller pack. |
| [Qwen3.8-27B-MTPLX-Optimized-Quality](https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Quality) | **29.95 GB / 27.90 GiB** | Defer on this host; memory cost needs a demonstrated task-quality benefit. |

The [MTPLX release registry](https://mtplx.com/releases/models.json) specifies minimum engine **2.7.0** for these Qwen3.8-27B packs; installed **2.12.2** meets that published floor. This is metadata compatibility, not a successful local load. Discover the actual served ID from `/v1/models`. The [registry snapshot](qwen38-mtplx-registry.json) pins the relevant revisions. Optimized Speed uses mixed precision despite its 4-bit label, explaining much of the larger footprint.

Do not infer compatibility from the `.safetensors` extension. Preserve each artifact's tokenizer, template, quantization metadata and runtime contract. Bonsai's Hadamard representation especially requires its matching loader. MTP can accelerate token generation through speculative decoding; measure realized speedup and overhead. It is not a planner or a second agent. Report MTP enabled/disabled, depth, head revision and memory separately in every comparison.

### 3.3 What the published measurements actually support

PocketAI's [pinned feature-suite record](https://huggingface.co/PocketAiHub/Qwen3.8-27B-MLX/blob/dcc3732f8c93ccf5580bf7a55e4ae639a40f194c/benchmarks/4k-feature-suite.json) reports an **M5 Max with 128 GB**, MLX 0.32.0 and mlx-vlm 0.6.8. Its 4-, 6- and 8-bit builds passed 8/8 tool cases; experimental 2-bit passed 3/8 and failed the vision check. Reported suite peaks were approximately 21.80, 29.54 and 37.27 GB for 4/6/8-bit.

The timing sample used one warmed 4K retrieval request producing **nine tokens**. These results justify an initial precision shortlist, not a throughput promise, long-horizon quality ranking, or certification of another publisher's conversion. Allocator peak also differs from whole-machine memory pressure and process RSS. The experimental 2-bit findings do not establish anything about Bonsai's different ternary method. [Saved publisher record](qwen38-publisher-4k-feature-suite.json)

### 3.4 Integration details that can break an agent loop

| Detail | Required implementation/evaluation response |
|---|---|
| Qwen 3.8 thinking defaults to `xhigh`; historical thinking preservation defaults on | Set modes explicitly. Benchmark non-thinking, medium and low where supported; compare whole-task success and time rather than isolated response speed. |
| Native tool syntax is XML-like, using `<tool_call>`, `<function=...>` and `<parameter=...>` | Verify the runtime parser reconstructs typed API arguments, identifiers and tool results. A generic JSON tool parser is insufficient. |
| The pinned chat template rejects system messages after the beginning | Normalize trusted system instructions into the initial system message. Do not promote retrieved text or tool output into that trusted role. Test framework-generated histories. |
| Template/tool/runtime settings can override client settings | Record the rendered mode and effective server configuration; a request field being accepted is not evidence it was applied. |
| Reasoning and constrained output interact | Begin schema tests with thinking disabled. Qualify any reasoning-plus-grammar combination separately. Never include reasoning markup in a final JSON payload. |

Sources: [Qwen's mode documentation](https://huggingface.co/Qwen/Qwen3.8-27B), [pinned chat template](https://huggingface.co/Qwen/Qwen3.8-27B/blob/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/chat_template.jinja). Bonsai's publisher specifically documents **medium**, with `low` behaving close to `xhigh`; do not assume all Qwen-derived models expose equivalent reasoning controls. [Bonsai card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-mlx-2bit)

## 4. Smaller open-weight models worth evaluating

“Open source” is used loosely for models. This shortlist prefers Apache 2.0/MIT weight licenses; it does not assert that every publisher releases its full training data and reproducible training pipeline. Role assignments below are hypotheses to test.

| Candidate and primary source | Why it is relevant | Verified Mac artifact / footprint | Proposed role |
|---|---|---|---|
| [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B), Apache 2.0 | Small general model with tool-use support and an existing MTPLX packaging path | [MTPLX Optimized Speed](https://huggingface.co/Youssofal/Qwen3.5-4B-MTPLX-Optimized-Speed); core file ~2.37 GB plus MTP files and metadata | Routing, simple extraction, bounded tool execution, summaries |
| [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B), Apache 2.0 | Real 9B option in the requested parameter range; **not Qwen 3.8** | [MLX 4-bit](https://huggingface.co/mlx-community/Qwen3.5-9B-4bit), **5.95 GB** weights; [MTPLX pack](https://huggingface.co/Youssofal/Qwen3.5-9B-MTPLX-Optimized-Speed), ~8.67 GB weights | General executor; planning/review candidate if it meets task gates |
| [Granite 4.2 3B](https://huggingface.co/ibm-granite/granite-4.2-3b), Apache 2.0 | Tool use, structured-output training, reasoning controls; different family from Bonsai/Qwen | IBM's [official q4 MLX](https://huggingface.co/ibm-granite/granite-4.2-3b-q4-mlx), **2.06 GB** weights | Bounded execution, extraction and an experimental reviewer from a different family |
| [SmolLM3-3B](https://huggingface.co/HuggingFaceTB/SmolLM3-3B), Apache 2.0 | Documented tool formats and an open training approach; useful compact baseline | [Community MLX 4-bit](https://huggingface.co/mlx-community/SmolLM3-3B-4bit), **1.73 GB** weights | Routing, summarization, narrow functions |
| [NuExtract3](https://huggingface.co/numind/NuExtract3), Apache 2.0 base | Specialized document-to-structure model; 4B language class with additional multimodal components | Publisher's [MLX 4-bit](https://huggingface.co/numind/NuExtract3-mlx-4bits), **3.03 GB** weights; quantized card omits license metadata, so retain/check upstream license and notices | Document extraction, not general agent orchestration |

Granite's official MLX instructions require explicit sampling/template handling. SmolLM3 documents XML/JSON and Python-style tool formats; choose a parser-based format and never execute model-produced Python text as a tool call. Neither model's output training guarantees JSON Schema enforcement. [Granite MLX card](https://huggingface.co/ibm-granite/granite-4.2-3b-q4-mlx), [SmolLM3 card](https://huggingface.co/HuggingFaceTB/SmolLM3-3B)

**NuExtract requires a distinct adapter.** Its structured extraction input uses a NuExtract template, not arbitrary JSON Schema passed through unchanged. The documented conversion utility returns both a template and dropped branches. Treat dropped constraints as explicit incompatibilities; validate output against the original schema regardless. It is a specialist candidate for evidence extraction, not a solution to the runtime's missing grammar engine. [NuExtract3 instructions](https://huggingface.co/numind/NuExtract3)

Secondary permissive candidates are [Phi-4-mini-instruct](https://huggingface.co/microsoft/Phi-4-mini-instruct) (MIT, ~3.8B, function calling) and [Ministral-3-3B-Instruct-2512](https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512) (Apache 2.0, tools and vision). They add evaluation cost before resolving the current decoder issue; defer them unless the first shortlist fails a specific requirement.

Keep these outside the permissive-license shortlist:

- [LFM3-1.7B](https://huggingface.co/LiquidAI/LFM3-1.7B) has official MLX variants and targets lightweight local tasks. Its card discourages complex multistep reasoning/agentic coding. The [LFM Open License](https://huggingface.co/LiquidAI/LFM3-1.7B/blob/main/LICENSE) includes a revenue-linked commercial restriction; it is not an Apache/MIT substitute.
- [FunctionGemma-270m-it](https://huggingface.co/google/functiongemma-270m-it) uses custom Gemma terms and gated access. Google positions it for function calling with task-specific tuning, rather than general dialogue. Consider it only for a narrow trained router. [Google model documentation](https://ai.google.dev/gemma/docs/functiongemma/model_card)

Do not rank these candidates by copying BFCL percentages from different cards. Benchmark version, task subset, reasoning budget, quantization and scoring can differ. A small model trained for extraction may outperform a larger model on that workload while failing a planning task.

### 4.1 Follow-up: 8B–27B models with native JSON tool bodies

**For the specific MTPLX strict-tool format requirement, start with Qwen3-14B; use Qwen3-8B as the smaller comparator.** Both the official templates and these MLX conversions teach JSON `name`/`arguments` objects inside `<tool_call>` markers. This removes the Qwen3.8 XML-body mismatch without establishing better overall agent quality.

| Candidate | Verified MLX artifact | Disk weights | Strict-format assessment |
|---|---|---:|---|
| Qwen3-14B | [mlx-community/Qwen3-14B-4bit](https://huggingface.co/mlx-community/Qwen3-14B-4bit) | **8.31 GB** | Clean initial JSON-body/template match; Apache 2.0 |
| Qwen3-8B | [mlx-community/Qwen3-8B-4bit](https://huggingface.co/mlx-community/Qwen3-8B-4bit) | **4.61 GB** | Same native format with a smaller footprint; Apache 2.0 |
| Qwen2.5-14B-Instruct | [mlx-community/Qwen2.5-14B-Instruct-4bit](https://huggingface.co/mlx-community/Qwen2.5-14B-Instruct-4bit) | **8.31 GB** | Older baseline; converted template has a double-braced instructional example that differs from current upstream. Inspect/pin the template before qualification. Apache 2.0. |
| DeepHermes 3 Mistral 24B Preview | [mlx-community/DeepHermes-3-Mistral-24B-Preview-4bit](https://huggingface.co/mlx-community/DeepHermes-3-Mistral-24B-Preview-4bit) | **13.26 GB** | Apache 2.0, documented JSON tool protocol, but the shipped template lacks tool rendering. Requires an adapter; lower priority than the clean Qwen3 matches. |

I performed **tokenizer-only encoding checks** using the existing environment and the pinned converted artifacts' tokenizer files. For all three, `<tool_call>` encodes to `[151657]` and `</tool_call>` to `[151658]`. Qwen3 also has single-token thinking markers. No model weights were downloaded and no generation or llguidance binding was tested. The [inspection record](strict-tool-candidate-inspection.json) includes exact revisions, tokenizer hashes and weight sizes. The model tokenizers are small support files, not model-weight downloads.

The official templates provide the native-format evidence: [Qwen3-14B](https://huggingface.co/Qwen/Qwen3-14B/blob/40c069824f4251a91eefaf281ebe4c544efd3e18/tokenizer_config.json), [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B/blob/b968826d9c46dd6066d109eabc6255188de91218/tokenizer_config.json), [Qwen2.5-14B](https://huggingface.co/Qwen/Qwen2.5-14B-Instruct/blob/cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8/tokenizer_config.json). The [older converted Qwen2.5 template](https://huggingface.co/mlx-community/Qwen2.5-14B-Instruct-4bit/blob/dad510143ae5cdb1466778bde3161460f9e9f604/tokenizer_config.json) illustrates why a base model's capabilities cannot simply be attributed to every conversion.

**MTPLX can use a generic autoregressive loading path.** Installed 2.12.2 delegates ordinary models to `mlx_lm.load`, whose installed 0.31.3 includes Qwen3, Qwen2 and Llama implementations. Missing native MTP heads does not prevent this fallback. Treat these as ordinary autoregressive candidates and do not promise MTP acceleration. [Pinned loader](https://github.com/youssofal/MTPLX/blob/9882703f3105363ddc37eca9f97aa09a1d387112/mtplx/runtime.py#L1219), [fallback construction](https://github.com/youssofal/MTPLX/blob/9882703f3105363ddc37eca9f97aa09a1d387112/mtplx/backends/registry.py#L2216)

Other possible candidates require additional adaptation. [Hermes 3 Llama 3.1 8B](https://huggingface.co/NousResearch/Hermes-3-Llama-3.1-8B) and [Hermes 2 Pro Llama 3 8B](https://huggingface.co/NousResearch/Hermes-2-Pro-Llama-3-8B) have upstream JSON tool-use templates, but inspected community 4-bit conversions retain only a generic template that ignores tools. They require a pinned tool-use template and carry custom Llama terms. Qwen3-VL-8B-Instruct also uses JSON tool bodies, but the installed generic MLX-LM loader serves its text component and drops vision weights; choose plain Qwen3 for this text-only experiment.

Conversion evidence: [Hermes 3 tokenizer configuration](https://huggingface.co/mlx-community/Hermes-3-Llama-3.1-8B-4bit/blob/3fde32264814f68c3d6d71ac333adf447523288a/tokenizer_config.json), [Hermes 2 Pro tokenizer configuration](https://huggingface.co/mlx-community/Hermes-2-Pro-Llama-3-8B-4bit/blob/817b2706f3a705739e5dffe4a196d054c9bd8363/tokenizer_config.json), [Qwen3-VL text-only loader](https://github.com/ml-explore/mlx-lm/blob/ed1fca4cef15a824c5f1702c80f70b4cffc8e4dd/mlx_lm/models/qwen3_vl.py).

[DeepHermes 3 Mistral 24B Preview](https://huggingface.co/NousResearch/DeepHermes-3-Mistral-24B-Preview) is a permissively licensed non-Qwen alternative whose documented protocol matches the JSON body. Its converted tokenizer encodes tool boundaries as `[131075]` and `[131076]`, but its default template does not render tool schemas/history. A matching output example therefore does not make it ready for the API's `tools` parameter. The installed MLX-LM implementation maps Mistral to its Llama loader, providing a plausible AR loading route; loading, adapter correctness and strict generation remain untested. [Pinned template](https://huggingface.co/mlx-community/DeepHermes-3-Mistral-24B-Preview-4bit/blob/b88d5c8f9db41fc38c0b9538dca74c8aa309592a/tokenizer_config.json), [loader mapping](https://github.com/ml-explore/mlx-lm/blob/ed1fca4cef15a824c5f1702c80f70b4cffc8e4dd/mlx_lm/utils.py#L46)

The qualification status is **native template match plus architecture-supported loading**, not a verified strict-tool replacement. `llguidance` remains required. Begin with thinking disabled, validate grammar/tokenizer binding and streaming, and retain the strict-mode limitations described below: named/required tool choices are unsupported, and ordinary text is still allowed. Matching the grammar does not force tool selection or guarantee correct arguments.

## 5. Next implementation milestone

### 5.0 Non-MLX alternative: GGUF with llama.cpp and Metal

**MLX is optional on this Mac.** llama.cpp can run GGUF weights using Apple's GPU through its Metal backend. This route has its own model loaders, templates and constraint implementation; it does not require repairing the MTPLX Python environment. [Metal build documentation](https://github.com/ggml-org/llama.cpp/blob/cd959bae99ff4bed22bef2604f45241c09bbb8c8/docs/build.md)

For an **8B–20B parameter limit**, there is still no verified official Qwen3.8 release in range. The modern official-family candidate is **Qwen3.5-9B**. A newly verified community alternative named **Qwen3.8-9B-Distill** exists: Empero describes it as a Qwen3.5-9B student trained on Qwen3.8-2.4T-A95B teacher outputs. It is not an official Qwen3.8-9B release. [Official release catalog](https://github.com/QwenLM/Qwen3.8), [community model provenance](https://huggingface.co/empero-ai/Qwen3.8-9B-Distill)

| Non-MLX candidate | Artifact size | Recommended treatment |
|---|---:|---|
| [Unsloth Qwen3.5-9B GGUF](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF), `Qwen3.5-9B-Q4_K_M.gguf` | **5.68 GB** language-weight file; vision projector additional | First baseline when an official model within 8B–20B is required; conversion is third-party |
| [Empero Qwen3.8-9B-Distill GGUF](https://huggingface.co/empero-ai/Qwen3.8-9B-Distill-GGUF), `Qwen3.8-9B-Q4_K_M.gguf` | **5.78 GB** | Experimental community distillation; compare against official Qwen3.5-9B using the same task harness |
| [Ollama Qwen3.8-27B Q4_K_M](https://ollama.com/library/qwen3.8:27b-q4_K_M) | Approximately **18 GB** packaged download | Actual official Qwen3.8 lineage, but outside the requested parameter range; consider only if that constraint is relaxed |

These are download sizes, not peak RAM or measured throughput. The Empero Q6_K file is 7.56 GB and Q8_0 is 9.79 GB. Its publisher reports limited reasoning benchmarks; that does not establish tool-use, agent, vision or quantized Mac performance. Evaluate it as a community candidate, not a demonstrated upgrade. Exact revisions and file sizes are in the [non-MLX metadata snapshot](non-mlx-model-snapshot.json).

**The earlier XML-body mismatch is specific to MTPLX's strict grammar.** Current llama.cpp detects Qwen XML templates and provides a matching function/parameter parser and grammar. Schema-constrained documents are a separate supported operation. An XML-native model can therefore remain a candidate: it does not need an older JSON-native model solely to satisfy MTPLX's implementation. [Pinned template detection](https://github.com/ggml-org/llama.cpp/blob/cd959bae99ff4bed22bef2604f45241c09bbb8c8/common/chat.cpp#L1414), [Qwen parser and grammar](https://github.com/ggml-org/llama.cpp/blob/cd959bae99ff4bed22bef2604f45241c09bbb8c8/common/parsers/qwen3-coder.cpp), [server API](https://github.com/ggml-org/llama.cpp/blob/cd959bae99ff4bed22bef2604f45241c09bbb8c8/tools/server/README.md)

For this alternative, qualify **llama.cpp v0.9.0**, commit `cd959bae99ff4bed22bef2604f45241c09bbb8c8`, with one inference slot and 8K context initially. Ollama is a convenient alternative, but select an explicit GGUF tag such as [`qwen3.5:9b-q4_K_M`](https://ollama.com/library/qwen3.5:9b-q4_K_M), approximately 6.6 GB including its packaged components. Its catalog also contains MLX variants, so an unqualified default model tag is insufficient to establish the intended backend. Ollama v0.40.14's OpenAI request mapping lacks `tool_choice`; do not assume forced-selection parity with llama.cpp or the existing probe. [llama.cpp release](https://github.com/ggml-org/llama.cpp/releases/tag/v0.9.0), [Ollama request mapping](https://github.com/ollama/ollama/blob/9a3e8177767245acc62b735eba7d5d8a553606d0/openai/openai.go#L110)

Retain application validation and repeat the tool/schema probes for the chosen server. The subsequent requested Qwen3.8-27B test used the **already installed llama.cpp 0.8.0**, rather than upgrading to the 0.9.0 candidate discussed above. Existing model-role defaults remain unchanged.

**Local test follow-up, November 4:** the exact Ollama Q4_K_M language blob was downloaded and SHA-256 verified, then served with an 8K context and one slot, configured for Metal. Nested strict JSON passed **3/3**; automatic and required-single-tool round trips passed **3/3 each**, including separate streaming checks. The reviewed result is **13 qualified cases, 1 unsupported capability and 1 failed task**. Native named selection silently fell back to `auto`; the invoice task selected the right tools but supplied **38 instead of 42**. Median server-reported decode speed was **7.47 tokens/s**, median first-content latency **10.43 s** for an uncached 863-token prompt, and peak observed RSS **16.57 GiB**, with normal pressure and no swap growth during the test. Bonsai was restored and verified. This demonstrates a usable non-MLX structured-output path for the tested cases, not general autonomous-agent reliability. [Full test report](QWEN38-GGUF-TEST-RESULTS.md), [reviewed capability assessment](qwen38-gguf-assessment.json)

### 5.1 Qualify the dependency with Bonsai first

Create a separate environment reproducing the installed MTPLX 2.12.2, MLX 0.32.2 and mlx-lm 0.31.3 environment, then resolve and pin the compatible `llguidance` dependency. Record the resolved environment and platform/wheel provenance. Installed MTPLX metadata declares `llguidance>=1.8` for its server extra; presence alone is not qualification. [Local inspection](LOCAL-MODEL-EVIDENCE.md)

PyPI currently lists **llguidance 1.9.1**, Python ≥3.10, and a macOS ARM64 stable-ABI wheel of approximately **3.14 MB**, providing a concrete qualification candidate for the existing Python 3.12 host. This is a small dependency experiment before any multi-gigabyte model download; actual import, schema and MTPLX compatibility remain to be tested. [PyPI release](https://pypi.org/project/llguidance/1.9.1/), [wheel metadata snapshot](llguidance-wheel-snapshot.json)

**Qualify two distinct MTPLX interfaces.** Version 2.12.2 implements document constraints through `response_format` for serial AR/MTP. Its separate strict-tool mode requires `MTPLX_TOOL_CALL_STRICT=1`, `llguidance` and appropriate single-token markers. Strict tools accept omitted/`auto` or `none`, reject named/`required` choices, and can still produce ordinary text. Constrained `response_format` plus nonempty `tools` is rejected when strict-tool mode is enabled. The existing forced-tool pass therefore does not qualify strict mode. [Pinned constraint implementation](https://github.com/youssofal/MTPLX/blob/v2.12.2/mtplx/constrained.py), [request validation](https://github.com/youssofal/MTPLX/blob/v2.12.2/mtplx/server/openai.py)

The strict-tool grammar expects a JSON `name`/`arguments` body inside tool markers, while the Qwen3.8 template teaches XML-like function/parameter bodies. Ordinary XML parsing support does not establish strict-grammar compatibility. Test that mismatch explicitly; any template or grammar adaptation becomes part of the evaluated configuration. For initial qualification, separate JSON-only planning/review requests with tools omitted from tool-selection requests. [Strict grammar source](https://github.com/youssofal/MTPLX/blob/v2.12.2/mtplx/constrained.py), [Qwen template](https://huggingface.co/Qwen/Qwen3.8-27B/blob/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/chat_template.jinja)

An MLX model artifact does not itself provide schema serving: the inspected stock [MLX-LM server](https://github.com/ml-explore/mlx-lm/blob/736ab0d8c1d0edc79c3d798044fe6904e2fa23be/mlx_lm/server.py) has no equivalent `response_format` grammar path. For each chosen server, verify its actual enforcement route. Test the decoder's [documented schema subset](https://github.com/guidance-ai/llguidance/blob/3d698ee07b3a67b0aef50fb6058612e8fd30aca2/docs/json_schema.md), tokenizer binding, imports and truncation behavior; a legal partial prefix is not a completed valid document.

Run the existing harmless probe unchanged, then add adversarial schemas and both client SDK paths. Preserve Bonsai's weights, prompt cases and mode so this experiment isolates decoder integration from model selection. A failure should produce a recorded incompatibility rather than a silent unconstrained fallback.

If that route fails qualification, use `submit_plan`/`submit_extraction` as an explicit function-based result strategy. For LangChain, select the qualified function-calling/ToolStrategy route explicitly; for the Vercel adapter, advertise strict structured-output support only after the actual transport passes. Both architectures still need server-side validation, independent of SDK capability flags.

### 5.2 Evaluate models with the same harness

| Experiment | Coverage and decision rule |
|---|---|
| Runtime identity | Exact artifact revision, served ID, template/parser, engine/dependency versions, effective context and sampling settings; no implicit cloud fallback |
| 100 protocol cases | Tool selection/arguments/results, required and named choice, streamed argument assembly, no-tool cases, nested objects, arrays, enums, nulls, Unicode, extra fields, unsupported schemas and truncation |
| Schema enforcement | Every accepted result validates against the original application schema; unsupported constraints produce an explicit error or documented validation route. Zero invalid accepted results. Track first-pass success separately from repaired success. |
| Semantics | Verify arithmetic, extracted spans, source references, nonexistent tools, ambiguous requests and insufficient evidence. Valid JSON is not a correct plan. |
| 40 held-out agent tasks × 3 trials | Shared tools, goal criteria, budgets and input evidence; research, file transformations, tool-failure recovery, planning revisions, review and honest incomplete outcomes |
| Context | Start with short/4K smoke cases; use 8K for the common comparison. Try 16K only after measuring headroom. Include long tool results and compaction. |
| Performance | Cold load, warm/cold first token, prefill, decode, full-task p50/p95, retries, cancellations, MLX allocator peak, process RSS, memory pressure, swap growth and sustained thermal behavior |
| Durability and policy | Kill/restart around calls and tool commits; no duplicate effects, unauthorized execution, path escape, or cross-workspace access |

Retain the PRDs' provisional gates: **at least 98% first-pass protocol success**, **at least 85% held-out task completion**, and **zero policy/replay failures**. These are proposed acceptance criteria, not observed results. Define expected outcomes before running: explicit rejection passes a designated unsupported-schema negative test, while rejection fails a required supported-schema positive test. Accepting malformed output always fails. Keep every predeclared case in the denominator and report positive/negative subsets separately. Model-based review is supporting evidence; deterministic checks and task-grounded human assessment establish correctness. A different model family does not guarantee statistically independent review errors.

Keep the existing shared budgets: one active inference slot, 24 model calls, 40 tool calls, 15 minutes active time, one repair attempt, maximum child depth two and four child runs. Do not keep Bonsai and a 27B 4-bit model resident together initially. Serial model switching has load costs; measure whether specialist routing saves enough work to justify them.

### 5.3 Candidate order and promotion

1. **Bonsai + qualified `llguidance`**, or validated function results, establishes the working contract.
2. **Qwen3.8-27B 4-bit standard MLX** is the smaller conventional precision comparator. Qualify its serving adapter before agent tests.
3. **Qwen3.8-27B MTPLX Optimized Speed** compares a fuller MTP-aware pack on the existing serving architecture. Stop on sustained memory pressure; test Bare Speed if headroom is inadequate.
4. **Qwen3.5-4B and Granite 4.2 3B** compete for cheap, bounded roles. Use Qwen3.5-9B when the smaller models fail useful executor tasks and the 27B choices are too expensive.
5. **NuExtract3** enters only the document extraction evaluation. Compare extraction accuracy and evidence fidelity, not general conversation scores.

Promote a candidate only when it passes correctness gates and improves an explicit objective: completed tasks per minute, memory headroom, extraction accuracy, or review error detection. A model with more bits, more parameters or a newer release date is not automatically the better AutoGPT component.

## 6. Evidence and reproducibility

- [Hugging Face metadata snapshot](huggingface-slm-snapshot.json): exact IDs, revisions, license metadata and per-file weight sizes; metadata only.
- [Official Qwen 3.8 catalog snapshot](qwen38-official-catalog.json): records which official model IDs were discoverable on this research date.
- [PocketAI feature-suite copy](qwen38-publisher-4k-feature-suite.json) and [release-manifest copy](qwen38-publisher-release-manifest.json): **publisher measurements**, not local test results. Their source is revision `dcc3732f8c93ccf5580bf7a55e4ae639a40f194c`. The release manifest retains a `packaged-not-published` status despite publicly retrievable files; use it as provenance, not a deployment certification.
- [Actual Bonsai probe](local-model-probe.json) and [probe source](probe_local_model.py): the local behavioral evidence.
- [Architecture comparison](../PRD-Comparison-Recommendation.md): the application/runtime decision remains separate from this model shortlist.

Key pinned revisions:

| Artifact | Revision |
|---|---|
| Qwen/Qwen3.8-27B | `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` |
| mlx-community/Qwen3.8-27B-4bit | `10c35caafbb80f7dc6a7a432cdd11af10a6d4818` |
| Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed | `1d5087d2062c02b279180a53e4016cf9cd7a3d7e` |
| PocketAiHub/Qwen3.8-27B-MLX | `dcc3732f8c93ccf5580bf7a55e4ae639a40f194c` |
| mlx-community/Qwen3.5-9B-4bit | `8b2b98c00a6b4d291155e4890773ca8f769aee53` |
| ibm-granite/granite-4.2-3b-q4-mlx | `0c6f39b1827afd5eb2c1c3b13751929857434953` |

Missing evidence is explicit: no local candidate quality scores, RAM peaks, speed estimates, or SDK/schema passes have been manufactured from model cards. The next experiment should produce comparable result records before changing a role's default model.
