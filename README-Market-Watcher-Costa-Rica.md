<p align="center">
  <img src="docs/assets/autobots-logo.svg" alt="Autobots" width="260">
</p>

<p align="center">
  <a href="README.md">Product overview</a> ·
  <a href="README-DEV.md">Developer guide</a> ·
  <a href="README-Deep-Research-Content-Writer.md">Deep research, live</a> ·
  <a href="README-YouTube-Transcript.md">YouTube transcript, live</a> ·
  <b>Market watcher Costa Rica, live</b> ·
  <a href="SPECS.md">Backlog</a> ·
  <a href="CODEBASE.md">Codebase</a>
</p>

# A market note for Costa Rica

Market watcher Costa Rica is an Expert that turns market moves into one short note for people in Costa Rica: households, small businesses and anyone paid in colones. It reads the dollar and the euro in colones, Brent crude oil and arabica coffee, works out what moved over a month and over a year, and explains why that matters in Costa Rica. It writes in Spanish as used in Costa Rica. The **Costa Rica market note** workflow runs the same Expert as one agent step.

Neither is part of the concept seed. The owner asked for them on their install on 2026-11-20, and they were created there through the app's own API. This page records what they are, how to make them, and the two live runs of 2026-11-20 that the film shows.

## Contents

- [The Expert](#the-expert)
  - [Its instructions](#its-instructions)
  - [What keeps it honest](#what-keeps-it-honest)
- [The workflow](#the-workflow)
- [Making them on an install](#making-them-on-an-install)
- [The live runs](#the-live-runs)
  - [The Expert run](#the-expert-run)
  - [The workflow execution](#the-workflow-execution)
  - [What the note said](#what-the-note-said)
  - [What it cost](#what-it-cost)
- [How it got here](#how-it-got-here)
- [What this shows, and what it doesn't](#what-this-shows-and-what-it-doesnt)
- [Where it is defined](#where-it-is-defined)

## The Expert

| | |
|---|---|
| **Name** | Market watcher Costa Rica, version 2 |
| **Purpose** | Tracks prices and exchange rates from a Costa Rican point of view, and explains what moved and why it matters for people in Costa Rica. |
| **Tools** | `market_history` (Market price history, Yahoo Finance's chart endpoint), `calculate`, `read_csv`, `save_artifact`, `publish_artifact` |
| **Model** | The workspace setting: Terra for every role, Sol for `researcher` |

`market_history` reads daily or weekly closes for up to five Yahoo Finance symbols, with each close's change from the one before. It needs no key and costs nothing, but it is unofficial and rate limited, and it says so in its result. It counts as a metered call.

### Its instructions

```text
Write for people in Costa Rica: households, small businesses and anyone paid in colones. Unless the
goal asks for another language, write in Spanish as used in Costa Rica.

Propose one plan with one task, and don't propose another.

1. Gather the data with tools, never from memory:
   - market_history with symbols CRC=X (the dollar in colones), EURCRC=X (the euro in colones),
     BZ=F (Brent crude oil) and KC=F (arabica coffee), period 1mo, interval 1d. Then the same
     symbols with period 1y, interval 1wk, for context.
   - calculate for every change you report: the change and the percentage change over the month
     and over the year.
2. Explain what moved, the largest moves first, in plain words: the colón against the dollar and
   the euro, oil and coffee.
3. Explain why it matters in Costa Rica, only where it follows from the numbers: dollar loans, rent
   or prices paid by people earning colones; the price of imported goods; fuel at the pump, which
   follows oil prices and the exchange rate with a delay; coffee growers' income; and income earned
   in dollars from tourism, exports or remittances. Say what is uncertain.
4. Save market-note.md with save_artifact and publish it with publish_artifact. Its sections:
   Resumen (three bullets); Qué se movió (a table with the indicator, start and end values with
   their dates, and the percentage change); Por qué importa en Costa Rica; Para tener en cuenta
   (the limits below); Fuentes (each tool's source and when it was read). Then complete the task
   with the published file as evidence.

Rules:
- Every number comes from a tool result, with its date. Never invent or estimate one.
- Yahoo Finance's CRC=X is a market quote, not the Banco Central de Costa Rica's reference
  exchange rate, and the two can differ. Say so.
- Don't state the central bank's policy rate, fuel prices in colones or salaries unless a tool
  returned them.
- No forecasts and no advice to buy, sell or borrow: this is information, not financial advice.
```

### What keeps it honest

- **Numbers come from tools.** Every figure in the note is a tool result with its date, and every change is a `calculate` call. The model doesn't do arithmetic in its head.
- **A quote is said to be a quote.** `CRC=X` is Yahoo's market quote, not the Banco Central de Costa Rica's reference rate, and the note says so.
- **Information, not advice.** No forecasts, and no advice to buy, sell or borrow.
- **The usual run limits.** A US$0.25 to US$5.00 budget, reserved before each model call. The tools are read-only apart from saving and publishing its own file, so no approval is needed.

## The workflow

**Costa Rica market note**, version 1: `focus` (input, "What to track") → `track` (agent: Market watcher Costa Rica, "Track and explain for Costa Rica") → `out` (output).

Its description reads: "Say what to track, or keep the default goal. Market watcher Costa Rica pulls exchange rates, oil and coffee, explains what moved and why it matters in Costa Rica, and publishes market-note.md." The agent step runs as its own child run with the Expert's tools, and only its result passes to the output.

## Making them on an install

They live in the owner's workspace, not in the seed. To make them on another install:

1. **The Expert.** Experts → New Expert. Name it "Market watcher Costa Rica", paste the purpose and the instructions above, tick Market price history, Calculate, Read CSV, Save file and Publish artifact, and save.
2. **The workflow.** Workflows → New workflow, named "Costa Rica market note". Graph: an `input` node `focus` of type `string` labelled "What to track", an `agent` node `track` naming the Expert and labelled "Track and explain for Costa Rica", and an `output` node `out`. Link `focus.value` to `track.goal` and `track.result` to `out.value`. Validate and publish it.
3. **A key.** A working OpenRouter key in Settings → Models, and the worker started with `make start-worker INFERENCE=enabled`.

## The live runs

Both ran on 2026-11-20 on the owner's install, with Expert version 2 and a US$1.00 budget each. Times are UTC.

### The Expert run

Run `f5a4b0d6…`, started from Home's composer with the goal "Tracks prices and exchange rates, and explains what moved and why it matters." and the Expert picked.

| Time | Event |
|---|---|
| 13:54:37.9 | Admitted, with the model policy frozen |
| 13:54:43.9 | One plan task: "Consultar y calcular las variaciones y publicar la nota de mercado" |
| 13:54:45 | `market_history`: one month, daily, for `CRC=X`, `EURCRC=X`, `BZ=F` and `KC=F` (873 ms) |
| 13:54:48 | `market_history`: one year, weekly, same symbols (833 ms) |
| 13:55:09 | 16 `calculate` calls: each change and each percentage, over the month and the year |
| 13:55:46 | `save_artifact`: `market-note.md`, 6,607 bytes |
| 13:55:48 | `publish_artifact` |
| 13:55:51 | `complete_task`, with the published file as evidence |
| 13:55:54.1 | Succeeded |

8 model calls and 22 tool calls in 1 minute 16 seconds, with 153,771 input and 3,690 output tokens. Verification: an artifact was published. No content check was defined for this goal.

### The workflow execution

Execution `3c78d9b5…` (run `e3188c46…`), started at 13:54:53.0 with `focus` = "The colón against the dollar and the euro, oil and coffee: what moved this month and why it matters."

- **It waited** in the queue while the worker finished the Expert run, until 13:55:54.
- **Its agent step**, child run `9edd40f8…`, ran from 13:55:54.2 to 13:57:24.6, 90 seconds. It made the same 22 tool calls (2 market reads, 16 calculations, save, publish, plan and complete) and published its own `market-note.md`, 6,887 bytes.
- **Its counts are kept on the workflow's run**, as a child's spend is: 9 model calls, 184,635 input and 4,422 output tokens. The child run's own Usage line reads 0 model and 0 tool calls, while its 22 tool rows and its spend are shown.
- **It succeeded** in 152 seconds from start to finish, queue included.

Its prices were read a minute after the Expert run's, and they had already moved: Brent's last close was US$89.05 instead of US$89.02, and coffee's 270.00 instead of 269.80.

### What the note said

The Expert run's note, "Nota de mercados para Costa Rica", in its own words for the month:

| Indicador | Inicio | Final | Cambio porcentual |
|---|---:|---:|---:|
| Brent (BZ=F), USD según Yahoo | 108,79 (20 oct. 2026) | 89,02 (20 nov. 2026) | −18,17 % |
| Café arábica (KC=F), USX según Yahoo | 311,30 (20 oct. 2026) | 269,80 (20 nov. 2026) | −13,33 % |
| Euro (EURCRC=X), colones por euro | ₡493,60 (19 oct. 2026) | ₡490,32 (20 nov. 2026) | −0,66 % |
| Dólar (CRC=X), colones por dólar | ₡439,66 (19 oct. 2026) | ₡441,73 (20 nov. 2026) | +0,47 % |

Over about a year, from the week labelled 17 November 2025: Brent +42.30 %, coffee −32.55 %, the euro −12.74 % and the dollar −9.52 % in colones.

**Why it matters, as the note explains it:**
- **Fuel and imports.** Cheaper Brent eases imported fuel costs, while a slightly dearer dollar works the other way. Pump prices follow with a delay and can't be read off the table.
- **Dollar loans and rent.** For someone earning colones, a fixed dollar payment needed a few more colones at the end of the month, and fewer than a year ago.
- **Coffee.** A lower international reference can squeeze growers' income, though what a farm receives depends on quality, contracts and timing.
- **Tourism, exports and remittances.** The same dollars bought a few more colones over the month, and fewer than a year ago.

**The limits it named:**
- `CRC=X` is Yahoo's quote, not the central bank's reference rate.
- Yahoo is unofficial, and its latest closes may be provisional.
- Yahoo's 20 November coffee close sat below the day's low that the same response reported, so the note asks for it to be checked before anyone relies on it.
- Futures are market references, not prices paid in Costa Rica.
- The note is information, not financial advice.

### What it cost

| Run | Spent | Budget |
|---|---:|---:|
| Expert run `f5a4b0d6…` | US$0.061958 | US$1.00 |
| Workflow run `e3188c46…` (its step `9edd40f8…`) | US$0.068171 | US$1.00 |
| **In all** | **US$0.130129** | |

## How it got here

- **First version.** Version 1 also granted `inflation_rates`, and its instructions asked for Costa Rica's and the United States' inflation from the World Bank. Its run that morning (`12fe25fd…`, 09:34 UTC, US$0.073818) succeeded, but the World Bank lookup failed, and the note said so.
- **The owner's call.** The owner then asked for the inflation tool and its World Bank code to be removed. [Decision 0036](docs/engineering/decisions/0036-inflation-rates-removed.md) retired `inflation_rates` (US-18.1). Version 2 of this Expert dropped it from its tools and instructions, and the workflow's description dropped the word.
- **The monthly workflow.** The seeded monthly workflow was renamed "Monthly FX note" with the rename that [Decision 0037](docs/engineering/decisions/0037-workflow-rename.md) added (US-19.1).

## What this shows, and what it doesn't

**It shows:**
- **The path.** An Expert with a Costa Rican brief, five granted tools and plain rules took a one-line goal to a published, dated, sourced note in Spanish, for about six cents, on the owner's real OpenRouter key.
- **The workflow.** The same Expert ran inside a workflow as its own child run.
- **Honest limits.** The note named its limits, including a doubtful close in its own data.

**It doesn't show:**
- **That the figures are right.** They are Yahoo's, read once. No content check was defined, so the runs verified that a note was published, not what it says.
- **Official rates or prices.** Nothing here is the Banco Central de Costa Rica's rate, a pump price or a policy rate.
- **H1 or product acceptance.**

A 2 minute 53 second narrated film of these two runs, `05-market-watcher-costa-rica.mp4`, was made with the other films in `docs/video/`, a folder kept out of the repository. It shows the Studio's screens as they were captured after the runs, and synthetic narration.

## Where it is defined

- **The Expert and the workflow.** In the owner's workspace, as described above. They are not in [`operations/concept_seed.py`](services/agent/src/autobots/operations/concept_seed.py), whose Market watcher and "Monthly FX note" are the general versions.
- **`market_history`.** [`services/agent/src/autobots/adapters/market_data.py`](services/agent/src/autobots/adapters/market_data.py), with its contract in [`contracts/market_tools.py`](services/agent/src/autobots/contracts/market_tools.py) and its spec in [`openspec/specs/market-data`](openspec/specs/market-data/spec.md).
- **Retired tools.** [`openspec/specs/retired-tools`](openspec/specs/retired-tools/spec.md) and Decision 0036.
- **Renaming a workflow.** [`openspec/specs/workflow-definition`](openspec/specs/workflow-definition/spec.md) and Decision 0037.
