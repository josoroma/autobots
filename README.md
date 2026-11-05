# AutoGPT clone: local Mac application with OpenRouter

**PRDs finalized for implementation — November 4, 2026.** The application, workers, database, Auth, files and logs run locally on this Mac. **All model inference uses OpenRouter.** Start implementation with [SPECS.md](SPECS.md), the Option B execution entry point; it organizes the selected design and its normative companion contracts. Implementation and release qualification remain pending.

| Document | Purpose |
|---|---|
| [SPECS.md](SPECS.md) | Option B execution entry point: ordered work, prerequisites, completion workflow and evidence; preserves the underlying PRDs' authority |
| [Option B engineering contract](docs/engineering/option-b-contract.md) | Preserved SP-001–SP-021 decisions, API/run-state semantics and implementation boundaries |
| [CODEBASE.md](CODEBASE.md) | Descriptive current state; development tooling is distinct from the unimplemented product |
| [PRD-AutoGPT.md](PRD-AutoGPT.md) | Pinned-source reconstruction of current AutoGPT: Experts, workflows, Classic, loops, planning, tools, memory, logs and recovery |
| [PRD-NextJS.md](PRD-NextJS.md) | Local Next.js, AI SDK 7 and Workflow 5 alternative, with local Supabase and OpenRouter-only inference |
| [PRD-LangChain-Deep-Agents.md](PRD-LangChain-Deep-Agents.md) | Recommended local Next.js plus Python LangGraph/Deep Agents design, local Supabase and OpenRouter-only inference |
| [PRD-Development-Harness.md](PRD-Development-Harness.md) | First Option B milestone: `.claude` skills, agents, rules and command hooks; portable checks for Next.js, Python, contracts, workers, Docker, migrations and seeds |
| [PRD-Design-System.md](PRD-Design-System.md) | User-supplied shadcn Luma tokens, dark-default behavior, shared component styling and visual/accessibility evidence |
| [PRD-Model-Providers.md](PRD-Model-Providers.md) | Two approved OpenRouter models, `.env` key loading, in-app setup, encrypted credentials, routing and budgets |
| [PRD-Local-Mac-Deployment.md](PRD-Local-Mac-Deployment.md) | Local Supabase Docker deployment, Auth, private Storage, database connections, ports, backups and recovery |
| [PRD-Comparison-Recommendation.md](PRD-Comparison-Recommendation.md) | Capability comparison, recommended architecture, tradeoffs and shared qualification gates |

**Recommended direction:** native local Next.js interface + native local Python LangGraph/Deep Agents worker + **self-hosted Supabase in Docker on this Mac**. Supabase provides local PostgreSQL, Auth and private file Storage. The full TypeScript runtime remains an alternative on the same Mac. The app uses no hosted Supabase project, Vercel deployment, remote application worker or local model server.

**Interface:** use **shadcn Luma, dark by default**, with the exact [light/dark CSS tokens](docs/design/luma.css). An explicit light/dark choice persists locally and is applied before paint; the OS setting does not change the first-visit dark default. Shared semantic tokens govern every screen, including the sidebar, forms, approvals and workflow canvas. The [regenerated concept gallery](docs/imagine/index.html) illustrates this direction; earlier warm-neutral/forest-green concepts are superseded. Images remain concept artwork, and browser/accessibility qualification remains implementation work.

**First implementation work:** complete the development harness's **H0 foundation and H1 activated baseline** before feature code, product migrations or production worker logic. Shared instructions, project `.claude` skills/agents/rules, command-hook configuration and the specification/harness checker are now present. They adapt the requested OhMyOrch ingestor. Full application toolchain/database gates and actual Claude event delivery remain pending; the portable checker is usable independently. Development tooling adds no model/provider and does not start services. [Adaptation](docs/engineering/ohmyorch-adaptation.md) · [Runbook](docs/engineering/runbooks/development-harness.md) · [Evidence](docs/engineering/evidence/HARNESS-ADAPT-001/summary.md)

Run the delivered checks locally:

```sh
python3.12 scripts/specs.py validate
python3.12 scripts/verify.py --profile harness
```

Use the project skill `autobots-spec-ingest` to refresh the backlog. Its read-only agent proposes source-traceable stories; the caller persists them and regenerates navigation. The operations verification profile runs on disposable projects, so its pass is not H1 or product acceptance.

Every H0/H1 and product work item follows a proportional **plan → implement → independent review → verify → runbook + evidence** workflow. Record review findings and their disposition, run the required checks against the final changes, and retain reproducible evidence and remaining limitations. Update and exercise the relevant runbook in the qualified disposable environment; if operational behavior is unchanged, record that fact rather than inventing a procedure. Small changes use concise records, not skipped stages. [SPECS.md](SPECS.md) and the [development harness contract](PRD-Development-Harness.md) define the detailed workflow.

All **14 inference roles default to DeepSeek**. Users may select Terra for a run, workspace default or explicit role override:

| Requested canonical snapshot | Verified OpenRouter API request ID |
|---|---|
| `deepseek/deepseek-v4.1-flash-20261017` | `deepseek/deepseek-v4.1-flash-1017` |
| `openai/gpt-6.1-terra-20261026` | `openai/gpt-6.1-terra` |

The app must revalidate these catalog mappings before use. It reads server-only `OPENROUTER_API_KEY` from environment/`.env` configuration first. When absent, **Settings → Models → OpenRouter → Save & validate** accepts and securely stores a key. Keys stay out of browser storage, prompts, logs and durable workflow payloads. Without a valid key, local sign-in, settings, drafts and stored files remain available, while every model-backed operation waits. Saving a key does not launch a paid run. There is no fallback to a different model or inference provider.

Local hosting describes the application and its stored data; selected task context is sent to OpenRouter for inference. User-authorized network tools retain their separate permission policy. **Bonsai, MTPLX, MLX, llama.cpp and Ollama are outside the active application design.**

Supporting evidence:

- [OpenRouter public model catalog snapshot](research/openrouter-model-catalog.json)
- [Pinned local Supabase Docker source snapshot](research/supabase-local-deployment-snapshot.json)
- [Supabase client package evidence](research/supabase-nextjs-sdk.json)
- [Qwen3.8-27B Q4_K_M local test: results and limitations](research/QWEN38-GGUF-TEST-RESULTS.md)
- [Qwen capability assessment, including the named-tool fallback](research/qwen38-gguf-assessment.json)
- [Hugging Face SLM research and Qwen 3.8 MLX evaluation](research/HUGGINGFACE-SLM-STRUCTURED-OUTPUT.md)
- [Local model inspection and experiment](research/LOCAL-MODEL-EVIDENCE.md)
- [Actual HTTP probe results](research/local-model-probe.json)
- [Reproducible protocol probe](research/probe_local_model.py)
- [Registry dependency snapshot](research/dependency-snapshot.json)

The local-model reports above are **historical research from the superseded design**, not installation requirements, available app backends or current defaults. Their raw test results remain unchanged.

Neither the application nor its Supabase stack was installed or launched by this documentation update. OpenRouter catalog and SDK research do not constitute authenticated inference tests. The PRDs distinguish historical observations, finalized requirements and remaining implementation/release gates.
