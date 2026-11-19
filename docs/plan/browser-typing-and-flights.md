# Plan: typing and submitting in browsing (YOLO), and flight prices

**Date:** 2026-11-19. **Status:** a draft for the owner. Nothing here is implemented. The owner has decided [T1, T2 and T10](#10-decisions-the-owner-makes); the rest of [section 10](#10-decisions-the-owner-makes) is open. [Section 11](#11-draft-stories-in-specs-style) holds stories in SPECS style, ready for ingestion once the owner approves.

This plan builds on [the local small models plan](local-small-models.md), whose [section 9](local-small-models.md#9-browsing-with-browser-use-locally) puts [browser-use](https://github.com/browser-use/browser-use) in the isolated browser box. It does two things:
- It lets browsing start without approval and type, click and submit, behind a Settings checkbox that is on by default.
- It uses that to get flight prices as JSON, from a workflow whose inputs are the trip.

## Contents

1. [What the owner decided](#1-what-the-owner-decided)
2. [What YOLO opens, and what stays](#2-what-yolo-opens-and-what-stays)
3. [The setting](#3-the-setting)
4. [Which engine runs](#4-which-engine-runs)
5. [Flight prices: the goal and the workflow](#5-flight-prices-the-goal-and-the-workflow)
6. [Engine A: a google_flights tool through SerpApi](#6-engine-a-a-google_flights-tool-through-serpapi)
7. [Engine B: browser-use, typing and clicking](#7-engine-b-browser-use-typing-and-clicking)
8. [flights.json](#8-flightsjson)
9. [Before filming](#9-before-filming)
10. [Decisions the owner makes](#10-decisions-the-owner-makes)
11. [Draft stories in SPECS style](#11-draft-stories-in-specs-style)
12. [Risks](#12-risks)
13. [Sources consulted](#13-sources-consulted)

## 1. What the owner decided

[Decision 0018](../engineering/decisions/0018-browser-executor.md) B5 makes browsing read-only: "Typing and submitting need their own decision, with approval per action". On 2026-11-19 the owner answered that rule:

> we want this in yolo mode via a checkbox in settings, by default Typing and submitting in yolo mode.

So typing and submitting become a workspace setting, **"Let browsing type and submit (YOLO)"**. It is a checkbox in Settings and **on by default**. When it is on, typing and submitting need no approval per action.

Asked whether YOLO also skips the approval of each `browse_goal` call (T2), the owner answered the same day: **"Yes, skip it"**. While YOLO is on, a browse starts at once, with no approval at all. With it off, every call waits for a person, as today.

This amends:
- Decision 0018 B5 and B6. B6 now holds only while YOLO is off.
- [Decision 0020](../engineering/decisions/0020-own-browsing-loop.md) L2, whose action set stays read-only for Autobots' own loop.
- [D9](local-small-models.md#12-decisions-the-owner-makes) and [US-17.7](local-small-models.md#us-177-browse_goal-on-browser-use-in-the-isolated-executor) of the local small models plan, which kept browser-use read-only at the network.

Without an approval, nobody would look at a call's `allowed_domains` before it ran, and the model writes them. So the owner decided [T10](#10-decisions-the-owner-makes) the same day, **"Yes, from the Expert"**: under YOLO, a browse may use only domains the owner listed in the Expert's grant. The boundary is still a person's choice.

## 2. What YOLO opens, and what stays

**With YOLO on, inside a `browse_goal` call that starts without approval, on the allowed domains only, browsing may:**
- type into fields, pick from menus, date pickers and dialogs, and press Enter;
- click any element, not only links;
- submit forms, by `GET` or `POST`, including the page's own background requests.

**Whatever the checkbox says:**

| Guard | How it is enforced | Hard? |
|---|---|---|
| **The call's approval** (B6) | With YOLO off only. With YOLO on, the call starts at once (T2) | **None under YOLO** |
| **Who sets the domains** | The owner, in the Expert's grant (T10). The call's `allowed_domains` must fall within it, or the call is refused before a container starts | Yes |
| **Allowed domains** | The egress proxy connects only to the call's domains (B3). browser-use's own `allowed_domains` also refuses navigation | Yes, at the network |
| **No sign-in** | The box gets no key, password, cookie or saved profile, and browser-use's `sensitive_data` is never passed | Yes: there is nothing to sign in with |
| **No payment** | The box holds no card or account data, and sellers' and payment hosts aren't on the list unless someone puts them there | Yes, for the data. Listing a seller in an Expert's domains is the owner's choice (T10) |
| **No files** | Chromium's policy turns downloads off, and a file chooser sees only the box's empty `tmpfs` | Yes |
| **Caps** | 1 CPU, 1 GiB, 256 processes, and the call's time limit (B2). Every model call is admitted against the run's budget (Decision 0020 L3) | Yes |
| **What it types, and where it submits within the domains** | The task's instructions only | **No.** browser-use's model writes Python, and its README calls domain restrictions "a guard for an aligned model, not a sandbox". The proxy sees only which host a tunnel goes to, not what is sent inside it |

So YOLO amounts to: **it starts without asking and may type and submit anything, but only on the domains its Expert allows (T10), with nothing to sign in or pay with.**

## 3. The setting

- **Where:** Settings → Browsing, a checkbox labelled "Let browsing type and submit (YOLO)", with one line saying what it allows. Only the owner changes it.
- **Default:** on for every workspace (T1). Whether existing workspaces get it on when it ships is [T3](#10-decisions-the-owner-makes).
- **Frozen when the run is admitted:** the run's snapshot records it, as it records the model policy, so a run behaves the same from start to end.
- **Turning it off is immediate.** The next `browse_goal` call of any run, admitted before or after, waits for approval and runs read-only. Turning it on applies to newly admitted runs only.
- **Shown in the run, since no approval card appears:**
  - The composer's disclosure says browsing may start, type and submit without asking.
  - The tool row's public fields show `typing: on` and the domains.
- **Recorded:** each submit's domain and path, without the typed values or the query, as `bare()` already does for visited URLs.
- **The Expert's domains (T10):** an Expert that grants `browse_goal` lists the domains it may browse, set by the owner in the Expert's editor. Under YOLO:
  - A call whose `allowed_domains` aren't all inside that list is refused before a container starts.
  - An Expert with no list can't browse.

  Changing the list makes a new Expert version, as any change to a grant does.
- **Separate from the browsing switch:** turning browsing on at all stays `AUTOBOTS_BROWSER_EXECUTOR`, or its Keys & vars override ([Decision 0025](../engineering/decisions/0025-keys-and-vars.md) V4). YOLO only says what browsing may do once it's on.

## 4. Which engine runs

| YOLO | Engine | Why |
|---|---|---|
| **On** | browser-use 1.0 in the box (the plan's US-17.6 and US-17.7) | It types, clicks and submits, and reads pages built by scripts |
| **Off** | Autobots' own loop (Decision 0020) | Read-only by construction: its only actions are open a link, go to a URL, scroll and finish |

**Recommended (T4):** read-only browsing stays on Autobots' loop, and the plan's D9 drops its "`GET` and `HEAD` only at the proxy" rule. Enforcing methods at the network would mean intercepting TLS in the box, with a box-local certificate authority. That adds a lot of new trust machinery for a mode the text loop already covers. The alternative is to build that interception and let browser-use run read-only too.

## 5. Flight prices: the goal and the workflow

**The example:** prices and a link to book a round trip from Costa Rica to New York, leaving 2026-12-20 and returning 2027-01-20, for 2 adults and a child aged 5, returned as JSON.

**Expert "Flight finder":**
- Its grant is the flights engine (section 6 or 7) and `save_artifact`. For engine B, its browse domains are google.com and gstatic.com (T10).
- Its instructions:
  - Map ages to passenger types: 2 to 11 is a child, under 2 an infant.
  - Search once.
  - Write `flights.json` from what the tool or the page returned, never typing or estimating a price.
  - Record when the prices were seen.
  - Never sign in, never continue to a seller, never pay.

**Workflow "Flight prices":**

```text
input trip (json) ──▶ transform to_string ──▶ agent: Flight finder ──▶ output
                                              (optional) ──▶ agent: Flight checker
```

- Every block exists today ([domain/workflows.py](../../services/agent/src/autobots/domain/workflows.py)): an `input` node of type `json`, the `to_string` transform, and an `agent` step whose one input is the goal text.
- The optional checker compares each price and link in `flights.json` with the tool's recorded output, as the deep research workflow's check step does with its excerpts.
- The run card takes inputs as a JSON text area today ([run-version-card.tsx](../../apps/web/components/workflow-editor/run-version-card.tsx)):

```json
{"origin": "SJO", "destination": "JFK,EWR,LGA", "depart": "2026-12-20", "return": "2027-01-20", "adults": 2, "children_ages": [5], "currency": "USD"}
```

Separate fields for Salida, Regreso, Origen, Destino, Adultos and Niños would need two things:
- A form drawn from the input node's declared fields.
- A way to build the agent's single goal from several inputs, such as a `template` transform.

That is [T8](#10-decisions-the-owner-makes).

## 6. Engine A: a google_flights tool through SerpApi

A new tool beside `google_search` and `google_map`, on the SerpApi key the workspace already has ([Decision 0032](../engineering/decisions/0032-google-search-through-serpapi.md)). It needs no browser and no typing. From [SerpApi's Google Flights API](https://serpapi.com/google-flights-api) and [booking options](https://serpapi.com/google-flights-booking-options), read on 2026-11-19:

- **One search per leg.** `departure_id` and `arrival_id` each take several airports separated by commas. `type=1` is a round trip, with `outbound_date`, `return_date`, `adults`, `children`, `infants_in_seat` and `infants_on_lap`.
- **A round trip is a chain:**
  1. The first search returns outbound flights.
  2. Their `departure_token` returns the return flights.
  3. A `booking_token` returns the booking options: who sells it, at what price, and the fare's conditions.

  For the top 3 offers, that's about 7 searches. The tool runs the whole chain itself, so prices and links never pass through the model's own typing.
- **The link to book:** every search returns `search_metadata.google_flights_url`, a Google Flights link pre-filled with the trip. A seller's own link is a `booking_request` (a URL plus form data to send by `POST`), not a plain link. So each offer gives its sellers' names and prices, and a Google Flights link from the booking-options search.
- **Price basis:** SerpApi describes `price` only as "This ticket price in the selected currency". Whether it is the total for every traveller or per person is checked in rehearsal (section 9).
- **The tool's profile:**
  - It's read-only, so it needs no approval, like `google_search`.
  - It's in the Google group, so the group's switch turns it off ([Decision 0033](../engineering/decisions/0033-google-toolkit-and-tool-switches.md)).
  - It's metered per SerpApi search.
  - Tests use a fake transport.

## 7. Engine B: browser-use, typing and clicking

With YOLO on, `browse_goal` on browser-use in the box. The API calls come from browser-use's README, read on 2026-11-19 (1.0.6):

```python
from pydantic import BaseModel
from browser_use import Agent, Browser, ChatOpenAI

class Leg(BaseModel):
    depart: str; arrive: str; stops: int; airlines: list[str]

class Offer(BaseModel):
    total_price: float; currency: str; price_basis: str
    outbound: Leg; back: Leg; booking_url: str

class Flights(BaseModel):
    search_url: str; offers: list[Offer]

task = (
    "On Google Flights, search a round trip from San José, Costa Rica (SJO) to New York (all airports), "
    "leaving 2026-12-20 and returning 2027-01-20, for 2 adults and 1 child aged 5, economy. "
    "Type into From, To and the dates, set the passengers, press Search, and sort by price. "
    "For the 3 cheapest, open each one and copy its total price, times, stops, airlines "
    "and the address of its booking options page. "
    "Never sign in, never continue to a seller, never pay."
)

agent = Agent(
    task,
    llm=ChatOpenAI("researcher", base_url="http://<admitted endpoint>/v1"),   # US-17.6
    browser=Browser("chromium", headless=True,
                    allowed_domains=["google.com", "*.google.com", "*.gstatic.com"]),
    output_model_schema=Flights,       # browser-use's typed result
)
result = await agent.run()
flights = result.structured_output
```

- **What it does:**
  1. It types "SJO" and picks the suggestion, then types "New York" and picks "all airports".
  2. It fills both dates.
  3. It opens the passengers dialog and presses + for the second adult and + for the child.
  4. It presses Search and sorts by price.
  5. It opens the three cheapest offers.

  browser-use draws brackets around what it clicks or types into, which films well.
- **It stops at the sellers.** "Continue" to an airline or agency leaves the allowed domains, so the proxy refuses it and the call ends with `refused_action`.
- **Bot checks:** Google may answer a fresh headless Chromium with a bot check. Nothing tries to solve it. browser-use's judge reports `bot_block_or_captcha_detected`, and the call stops with a typed reason (US-17.9).
- **The link keeps its query:** a Google Flights link works only with its `tfs=…` parameter, while `browse_goal` strips queries from visited URLs. A typed result's link fields keep theirs (T6).
- **Time:** this is likely 20 to 30 browser actions, more than the 300-second cap (B2) allows. The cap for interactive calls is set from rehearsal (T7).

## 8. flights.json

The same shape from either engine. Every `…` and `null` comes from the engine's output:

```json
{
  "query": {"origin": ["SJO"], "destination": ["JFK", "EWR", "LGA"], "depart": "2026-12-20",
            "return": "2027-01-20", "adults": 2, "children_ages": [5], "currency": "USD"},
  "observed_at": "…",
  "source": "Google Flights, through SerpApi | Google Flights, read by browser-use",
  "search_url": "https://www.google.com/travel/flights?…",
  "price_insights": {"lowest_price": null, "price_level": null, "typical_price_range": null},
  "offers": [
    {"rank": 1, "total_price": null, "price_basis": "…", "airlines": [],
     "outbound": {"depart": "…", "arrive": "…", "stops": null, "duration_minutes": null, "flights": []},
     "return": {"depart": "…", "arrive": "…", "stops": null, "duration_minutes": null, "flights": []},
     "book_with": [{"seller": "…", "price": null}],
     "booking_url": "https://www.google.com/travel/flights?…"}
  ],
  "notes": ["Prices as seen at observed_at, and they change. You book; Autobots doesn't buy."]
}
```

`price_insights` comes from SerpApi only. browser-use fills what the page shows.

## 9. Before filming

1. **Probe the bot check** (five minutes, no model): load Google Flights in the box's Chromium through the proxy and see what it serves. If it serves a bot check, engine B is off the table for Google.
2. **Engine A first:**
   - Run the tool for 1 adult, then for 2 adults and a child. That settles the price basis.
   - Open `google_flights_url` and the booking-options link, and check that they show the same trip and itinerary.
3. **One rehearsal per engine:**
   - Check that it stopped as done, and its call and search counts.
   - Check that every price in `flights.json` equals the tool's output, or the page.
   - Check the cost, and that no request reached a seller.
4. **Fix and repeat** until two rehearsals in a row are clean, then capture:
   - the trip input
   - the browse starting without an approval, under YOLO
   - the run
   - `flights.json`
   - the link opened in a browser, showing the same price

## 10. Decisions the owner makes

| # | Question | Options, recommended first |
|---|---|---|
| T1 | Typing and submitting in browsing? | **Decided 2026-11-19: a Settings checkbox, "Let browsing type and submit (YOLO)", on by default** |
| T2 | Does YOLO also skip the approval of each `browse_goal` call? | **Decided 2026-11-19: yes, "Yes, skip it".** No approval at all while YOLO is on. With it off, every call waits, as today |
| T3 | Existing workspaces when it ships | **On, as for new ones, with a one-time notice on Home** · off until the owner checks it |
| T4 | What runs with YOLO off? | **Autobots' read-only loop. The plan's D9 drops `GET` and `HEAD` at the proxy** · browser-use, read-only through TLS interception in the box |
| T5 | Where else can it be turned off? | **Workspace only, frozen at admission, with turning it off immediate** · also per Expert |
| T6 | Links in a typed result keep their query? | **Yes, for declared link fields of a typed result only.** Visited URLs stay bare · no |
| T7 | Time limit for interactive calls | **Set from rehearsal, with the box's cap (B2) raised to match** · keep 300 seconds |
| T8 | A form for workflow inputs? | **Later: the JSON input is enough to start** · now, with a form drawn from input fields and a `template` transform |
| T9 | Add `google_flights` (engine A)? | **Yes, as the dependable path for prices** · browser-use only |
| T10 | With no approval, who sets a browse's domains? | **Decided 2026-11-19: "Yes, from the Expert".** The owner lists the domains an Expert may browse, such as google.com and gstatic.com for Flight finder. Under YOLO, a call naming any other domain is refused before a container starts, and an Expert with no domains can't browse |

## 11. Draft stories in SPECS style

For ingestion after the owner's decision. The identifiers continue [the local small models plan's](local-small-models.md#13-draft-stories-in-specs-style) and are proposals. Ingestion assigns the real ones.

### US-17.8: Typing and submitting in browsing, a Settings checkbox

As a workspace owner
I want one checkbox that lets browsing type, click and submit
So that goals that need a search form run without stopping to ask, while the domains and the box's limits stay in force.

Acceptance Criteria:

```gherkin
Scenario: On by default
  Given a new workspace
  When the owner opens Settings → Browsing
  Then "Let browsing type and submit (YOLO)" is checked

Scenario: No approval while it is on
  Given the checkbox is on when a run is admitted
  When an Expert's browse_goal call is made
  Then it starts without waiting for approval, and the tool row shows typing on and its domains

Scenario: The domains come from the Expert
  Given the checkbox is on, and an Expert whose grant allows browsing google.com and gstatic.com
  When its browse_goal call names any other domain
  Then the call is refused before any container starts

Scenario: An Expert with no domains can't browse
  Given the checkbox is on, and an Expert that grants browse_goal with no domains listed
  When its browse_goal call is made
  Then the call is refused before any container starts, with a reason that names the missing list

Scenario: Turning it off is immediate
  Given a run admitted with the checkbox on
  When the owner unchecks it and the run makes another browse_goal call
  Then that call waits for approval and runs read-only on Autobots' own loop

Scenario: Only the owner changes it
  Given a signed-in workspace member who isn't the owner
  When they try to change the checkbox
  Then the request is refused and the setting is unchanged
```

Dependencies:
- The owner's decisions T1, T2 and T10, and the open T3 to T5

### US-17.9: browse_goal types and submits on browser-use

As a workspace owner
I want browser-use to type, click and submit on the allowed domains when the checkbox is on
So that a browse can use a search form, and stops at the edge of the domains its Expert allows.

Acceptance Criteria:

```gherkin
Scenario: Types and submits within the allowed domains
  Given the checkbox is on, and a browse_goal call on browser-use with allowed domains google.com and gstatic.com
  When its task needs a search form
  Then it types, clicks and submits on those domains, and the run records each submit's domain and path without the typed values

Scenario: Leaving the domains ends the call
  Given the same call
  When a click or a submit leads to a host outside the allowed domains
  Then the egress proxy refuses it and the call stops with refused_action

Scenario: Nothing to sign in or pay with
  Given any browse on browser-use
  When it runs
  Then the box holds no key, password, cookie or card, Chromium refuses downloads, and a file chooser offers no host file

Scenario: A bot check stops the call
  Given a site answers with a bot check or a CAPTCHA
  When browser-use meets it
  Then nothing tries to solve it, and the call stops with a typed reason

Scenario: A typed result
  Given the call names an output schema
  When browser-use finishes
  Then the output carries a result valid against that schema, its declared link fields keep their query, or the call stops with invalid_action
```

Dependencies:
- US-17.7
- US-17.8

### US-17.10: google_flights through SerpApi

As a workspace owner
I want a flights tool that returns round-trip offers, sellers and a link to book
So that a goal can price a trip from structured data, without a browser.

Acceptance Criteria:

```gherkin
Scenario: A round trip with its top offers
  Given the workspace's SerpApi key, origin SJO, destination JFK,EWR,LGA, 2026-12-20 to 2027-01-20, 2 adults and a child aged 5
  When the tool is called for 3 offers
  Then it returns up to 3 offers, each with its price, legs, sellers and a Google Flights link, with the search link and the time seen, using at most 7 searches

Scenario: Ages become passenger types
  Given children's ages of 5 and 1
  When the tool builds its search
  Then the 5-year-old counts as a child and the 1-year-old as an infant

Scenario: Switched off with the Google group
  Given the owner switched the Google group off
  When an Expert calls google_flights
  Then it is refused as switched off, before any search

Scenario: No paid call in tests
  Given the test suite
  When the tool's tests run
  Then they use a fake transport and no SerpApi search is made
```

Dependencies:
- Decision 0032 and Decision 0033

### US-17.11: The Flight prices Expert and workflow

As a workspace owner
I want a workflow that takes a trip and returns flights.json
So that I get prices and a link to book, and do the booking myself.

Acceptance Criteria:

```gherkin
Scenario: A trip in, flights.json out
  Given the Flight prices workflow and the trip as its JSON input
  When it is executed
  Then flights.json is published, every price and link in it equals the flights tool's output, and it records when the prices were seen

Scenario: Nothing is bought
  Given the same execution
  When it finishes
  Then no request reached a seller or payment host, and the run's tool uses are the flights tool and save_artifact only
```

Dependencies:
- US-17.10, or US-17.9 for the browser-use version

## 12. Risks

- **The default is the permissive one, and nothing asks first.** With YOLO on, a browse starts without approval (T2), and a page's text can steer the model. Within the allowed domains it could then post a comment, fill in a contact form, vote or create an account with made-up details. The Expert's domain list, which the owner sets (T10), is what bounds it. A broad list, such as a whole platform where anyone can post, widens what a steered model can do.
- **Spend without a pause.** Each browse step is a paid model call, and no approval stands between a goal and its browsing. The run's budget and the call's step and time caps are what bound it.
- **The task is typed into third-party sites.** Whatever the goal contains, such as names, dates or routes, may be sent to the allowed domains.
- **Sites' terms and bot checks.** Some sites forbid automated use or block it. A bot check stops the call; nothing solves it.
- **Pages change.** browser-use reads the page as it is. A change to Google Flights' layout can break engine B overnight, while engine A depends on SerpApi's parsing.
- **Prices move.** `flights.json` is a snapshot at `observed_at`, not a quote.
- **The README's promise changes.** Its "Asks before it acts" says browsing needs an approval every time. Under YOLO, the default, it doesn't. When this ships, the README must say browsing asks only with YOLO off, and Decision 0018 B6 must be amended in the same change.

## 13. Sources consulted

- [Decision 0018](../engineering/decisions/0018-browser-executor.md) B1 to B8, and [Decision 0020](../engineering/decisions/0020-own-browsing-loop.md) L1 to L6.
- [Decision 0025](../engineering/decisions/0025-keys-and-vars.md) V4, [Decision 0032](../engineering/decisions/0032-google-search-through-serpapi.md) and [Decision 0033](../engineering/decisions/0033-google-toolkit-and-tool-switches.md).
- The code:
  - [browsing_tool.py](../../services/agent/src/autobots/application/browsing_tool.py), [browsing_loop.py](../../services/agent/src/autobots/application/browsing_loop.py) and [contracts/browsing.py](../../services/agent/src/autobots/contracts/browsing.py).
  - [egress_proxy.py](../../services/agent/src/autobots/adapters/egress_proxy.py), which checks the host of each `CONNECT` and can't see methods inside TLS.
  - [serpapi.py](../../services/agent/src/autobots/adapters/serpapi.py), [domain/workflows.py](../../services/agent/src/autobots/domain/workflows.py) and [run-version-card.tsx](../../apps/web/components/workflow-editor/run-version-card.tsx).
- [browser-use's README](https://github.com/browser-use/browser-use), read on 2026-11-19 at 1.0.6: `Agent`, `Browser('chromium')`, `allowed_domains`, `output_model_schema`, `structured_output` and the judge.
- [SerpApi Google Flights API](https://serpapi.com/google-flights-api) and [booking options](https://serpapi.com/google-flights-booking-options), read on 2026-11-19.
