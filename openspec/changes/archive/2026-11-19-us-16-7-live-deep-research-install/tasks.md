## 1. The install

- [x] 1.1 The owner restarts the install on this code with inference on, applies migration 64 and runs the concept seed. Check: the seed reports the Deep research writer created without any tool missing and the workflow published, and everything else kept (owner's terminal, 2026-11-18).
- [x] 1.2 Read the Studio's Experts and Workflows pages. Check: both are listed, and the earlier ones still are.

## 2. Live runs

The first Expert run failed at its 64-model-call limit after US$0.51, looping on offloaded search results; US-16.8 raised the working context to 64K. The second, on 64K, collected and saved its sources for US$0.23, then lost its plan at its first compaction and failed at its repair limit; US-16.9 pins the plan through compaction. The owner restarts the worker on each before the next run.


- [x] 2.1 Start the Deep research writer on "langchain for deep agents" from the composer with a US$5.00 budget, and follow it to its end. Check: its outcome, published artifacts and cost, read from the Studio and the API.
- [x] 2.1b The third Expert run succeeded on 64K with the plan pinned: US$0.52, 49 tool calls, four published artifacts, a 2,448-word guide citing 12 sources, reported degraded (under 15 sources). Check: the Studio run page and its artifacts.
- [x] 2.1c Tune the Deep research writer's instructions from the runs: propose the plan once, aim for 1,800 to 2,400 words so the document fits one reply, and never put it in a reply. Seed it, and save it as a new version of the install's Expert in the Experts editor. Check: the seed unit test, and the Expert's new version in the Studio.
- [x] 2.2 Start the Deep research content writer on "langchain for deep agents" with a US$5.00 budget, have the owner decide its gate, and follow it to its end. Check: its outcome, both steps' artifacts and its cost. Observed: the first execution's research step stopped with its plan incomplete (US$0.25), and the instructions were tuned (2.1c). The second, execution 3d24ce18 with a US$3.75 budget, succeeded after the owner approved its gate: research published sources, synthesis, a 17-source guide and a degraded report; check read them with read_artifact and published a corrected guide and review.md; 45 model calls, 49 tool calls, US$0.453547.
- [x] 2.3 Scan both runs' artifacts for key shapes. Check: none found. Observed: the Expert run's four artifacts and the workflow's six, scanned for OpenRouter, SerpApi, Tavily, Jina, GitHub and Google key shapes, JWTs and 64-character hex, found none. The failed attempts published none.

## 3. The README

- [x] 3.1 Write `README-Deep-Research-Content-Writer.md` from the runs as observed, and link it from `README.md` and `README-DEV.md`. Correct `README.md`'s seed counts. Check: every link and anchor resolves, and the harness profile passes.
- [x] 3.2 Note the live runs in `CODEBASE.md`. Check: harness profile passes.
