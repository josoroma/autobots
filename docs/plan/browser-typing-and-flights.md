# Plan: typing and submitting in browsing (YOLO), and flight prices

**Date:** 2026-11-19. **Status:** a draft for the owner. Nothing here is implemented. The owner decided [T1, T2 and T10](#10-decisions-the-owner-makes). On 2026-11-19 they delegated the rest, asking to "take senior decisions", and [section 10](#10-decisions-the-owner-makes) records each delegated choice. A later owner decision replaces any of them. [Section 11](#11-draft-stories-in-specs-style) holds stories in SPECS style, ready for ingestion once the owner approves.

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
9. [Build order and rehearsal](#9-build-order-and-rehearsal)
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

**Decided (T4, delegated):** read-only browsing stays on Autobots' loop, and the plan's D9 drops its "`GET` and `HEAD` only at the proxy" rule. Enforcing methods at the network would mean intercepting TLS in the box, with a box-local certificate authority. That adds a lot of new trust machinery for a mode the text loop already covers. The alternative is to build that interception and let browser-use run read-only too.

## 5. Flight prices: the goal and the workflow

**The example:** a family trip from Costa Rica to New York, leaving 2026-12-20 and returning 2027-01-20, for 2 adults and a child aged 5. It returns two things as JSON:
- The flight prices, with a link to book.
- A short guide: which airport suits the family, and things to do with a 5-year-old in winter.

Prices come from engine A. Google Flights blocks an automated browser (section 7.1), so browser-use doesn't price flights. browser-use does what sites allow: it types into Wikivoyage's search and reads the city's guide.

**Expert "Flight finder":**
- Its grant is `google_flights` and `save_artifact`.
- Its instructions:
  - Map ages to passenger types: 2 to 11 is a child, under 2 an infant.
  - Search once.
  - Write `flights.json` from the tool's output, never typing or estimating a price.
  - Record when the prices were seen.

**Expert "Trip guide":**
- Its grant is `browse_goal` on browser-use (YOLO), `read_artifact` and `save_artifact`. Its browse domains are `en.wikivoyage.org` (T10).
- Its instructions:
  1. Read `flights.json`.
  2. Type the destination into Wikivoyage's search, open the city's guide, and read "Get in", for the airports and getting into the city, and "Do".
  3. Write `trip.json`, with three things:
     - the cheapest offer for each arrival airport, with that airport's transfer notes;
     - three things to do with a young child in winter;
     - the guide page each one came from.
- What it must never do: edit or post on the wiki (T14), or sign in.

**Workflow "Family trip":**

```text
input trip (json, with fields) ──▶ to_string ──▶ agent: Flight finder ──▶ to_string ──▶ agent: Trip guide ──▶ output
```

- Every block exists today ([domain/workflows.py](../../services/agent/src/autobots/domain/workflows.py)): an `input` node of type `json`, the `to_string` transform and `agent` steps whose one input is the goal text.
- As in the deep research workflow, only the first step's result passes on. The Trip guide reads `flights.json` back by its artifact ID.
- The run card takes inputs as a JSON text area today ([run-version-card.tsx](../../apps/web/components/workflow-editor/run-version-card.tsx)). With T8, the `trip` input declares fields, and the run card draws a form from them: From, To, Leave, Return, Adults and Children's ages. The form sends the same object:

```json
{"origin": "SJO", "destination": "JFK,EWR,LGA", "depart": "2026-12-20", "return": "2027-01-20", "adults": 2, "children_ages": [5], "currency": "USD"}
```

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

With YOLO on, `browse_goal` runs browser-use in the box. Here it is for the Trip guide. The API calls come from browser-use's README, read on 2026-11-19 (1.0.6):

```python
from pydantic import BaseModel
from browser_use import Agent, Browser, ChatOpenAI

class Airport(BaseModel):
    code: str; getting_in: str; source_url: str

class Activity(BaseModel):
    name: str; why_for_a_child: str; source_url: str

class Guide(BaseModel):
    airports: list[Airport]; activities: list[Activity]

task = (
    "On Wikivoyage, type New York City into the search box and open the city's guide. "
    "From 'Get in', note how to reach the city from JFK, Newark (EWR) and LaGuardia (LGA). "
    "From 'Do' and 'See', pick three things to do with a 5-year-old in December and January. "
    "Give the address of the guide section each one came from. Never edit the wiki, never sign in."
)

agent = Agent(
    task,
    llm=ChatOpenAI("researcher", base_url="http://<admitted endpoint>/v1"),   # US-17.6, T11
    browser=Browser("chromium", headless=True, allowed_domains=["en.wikivoyage.org"]),   # T10
    output_model_schema=Guide,         # browser-use's typed result (T6)
)
result = await agent.run()
guide = result.structured_output
```

- **What it does:**
  1. It clicks the search box, types "New York City" and presses Enter.
  2. It opens the guide's "Get in" section, then "Do" and "See".
  3. It returns `Guide`.

  browser-use draws brackets around what it clicks or types into, which films well.
- **It stays on the domain.** A link to another site, such as Wikipedia or an attraction's own site, is refused by the proxy and browser-use. Whether that ends the call or lets it continue follows browser-use's own handling, mapped to `refused_action` when the call ends.
- **It never edits.** Wikivoyage is a wiki anyone can edit, and the proxy can't tell reading from editing on the same host. The instructions forbid editing (T14).
- **Bot checks:** a bot check or CAPTCHA ends the call with `bot_check`, and nothing tries to solve it (T12). browser-use's judge reports it as `bot_block_or_captcha_detected`.
- **Links keep their query** in a typed result's declared link fields (T6). Visited URLs stay bare.
- **What it saw:** each browser-use step keeps one screenshot, shown in the run's tool row (T15). With no approval under YOLO, this is how a person sees afterwards what it typed and clicked.
- **Time:** up to 600 seconds and 40 steps for browser-use calls (T7).

### 7.1 What sites allow an automated browser

On 2026-11-19, Playwright's Chromium on this Mac ran headless with a fresh profile, held to each site's own domains as the egress proxy would hold it. These probes run no model, and they stopped at the first bot check without trying to pass it.

| Site | Held to | What it got |
|---|---|---|
| Google Flights | google.com, gstatic.com | A reCAPTCHA page ("unusual traffic") before any flight showed |
| The US State Department's visa wait times | state.gov | Cloudflare: 403, "you have been blocked" |
| Costa Rica's central bank, exchange-rate table | bccr.fi.cr | 503, Service Unavailable |
| BlazeDemo, a practice flight site made for test automation | blazedemo.com | The page, with two drop-downs and Find Flights. Its only typed fields are its practice checkout |
| Wikivoyage | wikivoyage.org, wikimedia.org | The page. Typing "New York City" into its search and pressing Enter opened the city's guide, with its "Get in", "See" and "Do" sections |
| YouTube, a watch page | youtube.com, ytimg.com, ggpht.com, gstatic.com | The page, with no bot check. Pressing "...more" and then "Show transcript" opened the transcript panel. The owner's own film gave 24 lines (437 words), and a 21-minute video gave 169 lines. The video stream's host wasn't allowed, so no video was fetched |

So commercial travel and government sites turn a fresh headless browser away, and Autobots doesn't get around that (T12). browser-use types where sites allow it, and flight prices come from engine A (T9).

These ran outside the box. The box's Chromium on the same network is expected to fare the same, and US-17.9 checks that.

### 7.2 A second example: a video's transcript

The owner asked for browser-use to open a YouTube video, expand its description, press "Show transcript" and return the transcript as Markdown. The probe in 7.1 did exactly that, scripted, and it shows why this is browser-use's kind of work:
- "...more" and "Show transcript" are buttons, not links. Autobots' read-only loop can only open links (Decision 0020 L2), so only browser-use can do it.
- YouTube now renders the transcript as `transcript-segment-view-model` elements, in a panel whose `target-id` is `PAmodern_transcript_view`, not the older `ytd-transcript-segment-renderer`. browser-use reads the page as it is, so it copes with such changes better than a fixed script. That is also why the result must be checked.
- **What comes back is YouTube's own captions,** with their errors. In the owner's film, "52 cents later" came back as "52 seconds later", and "Checked work out" as "checked workout". The Markdown says so.

An Expert "Transcript reader" (US-17.13) holds these domains (T10): `youtube.com`, `ytimg.com`, `ggpht.com` and `gstatic.com`, without `googlevideo.com`, so no video is fetched. It publishes `transcript.md` with each line's timestamp. It is seeded with an empty domain list, so it can't browse until the owner adds YouTube's hosts (T16).

Two limits go with it:
- **YouTube's terms** forbid automated access without YouTube's permission. For the owner's own videos, YouTube Studio's subtitle download is the sanctioned way.
- **Another creator's transcript is their work.** An Expert may summarise it or quote it briefly. A full copy is for the owner's private use and is never published.

## 8. flights.json

Written by the Flight finder from `google_flights`. Every `…` and `null` comes from the tool's output:

```json
{
  "query": {"origin": ["SJO"], "destination": ["JFK", "EWR", "LGA"], "depart": "2026-12-20",
            "return": "2027-01-20", "adults": 2, "children_ages": [5], "currency": "USD"},
  "observed_at": "…",
  "source": "Google Flights, through SerpApi",
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

The Trip guide adds `trip.json`:
- `flights`: the cheapest offer for each arrival airport, copied from `flights.json`.
- `airports`: what the guide says about getting into the city from each one.
- `activities`: three things to do with the child, each with its guide link.

## 9. Build order and rehearsal

**Build order.** Each step is one story, delivered as one OpenSpec change once a decision record holds T1 to T16 and the stories are ingested into `SPECS.md`:

| # | Story | Why here |
|---|---|---|
| 1 | US-17.10 `google_flights` | It needs nothing else, and it gives real prices first |
| 2 | US-17.12 Input fields for a workflow | The form the trip is typed into |
| 3 | US-17.8 The YOLO setting and the Expert's domains | Every browser-use call depends on it |
| 4 | US-17.6 The admitted model endpoint | browser-use's model calls go through it, on OpenRouter (T11) |
| 5 | US-17.7 browser-use in the box | The engine and its image (T13), qualified again |
| 6 | US-17.9 Typing, `bot_check`, typed results and step screenshots | What YOLO lets it do, and what a person sees afterwards |
| 7 | US-17.11 The Family trip Experts and workflow | Everything above, used together |
| 8 | US-17.13 The Transcript reader Expert and workflow | Needs only US-17.9, so it can come before US-17.11 |

Every story uses fake transports in its tests. A live call happens only in rehearsal, at the owner's go.

**Rehearsal, before filming:**
1. **Prices:**
   - Run `google_flights` for 1 adult, then for 2 adults and a child. That settles the price basis.
   - Open `google_flights_url` and the booking-options link, and check that they show the same trip and itinerary.
2. **The guide:** one browse of Wikivoyage in the box. Check that:
   - it stopped as done;
   - its screenshots show the typing;
   - it stayed on `en.wikivoyage.org`;
   - it submitted nothing but the search.
3. **The workflow:** one Family trip execution. Check that:
   - every price in `trip.json` equals the tool's output;
   - every guide link was visited;
   - the cost and call counts are recorded.
4. **Fix and repeat** until two executions in a row are clean, then capture.

## 10. Decisions the owner makes

T1, T2 and T10 are the owner's. The rest were delegated on 2026-11-19 ("take senior decisions"). Where two options were close, the choice keeps today's behaviour, adds the least or is easier to reverse. A later owner decision replaces any of them.

| # | Question | Choice |
|---|---|---|
| T1 | Typing and submitting in browsing? | **Owner, 2026-11-19:** a Settings checkbox, "Let browsing type and submit (YOLO)", on by default |
| T2 | Does YOLO also skip the approval of each `browse_goal` call? | **Owner, 2026-11-19: "Yes, skip it".** No approval at all while YOLO is on. With it off, every call waits, as today |
| T3 | Existing workspaces when it ships | **Delegated:** on, as for new ones, with a one-time notice on Home. The owner asked for on by default, and the notice keeps the change from being silent |
| T4 | What runs with YOLO off? | **Delegated:** Autobots' read-only loop, and the local plan's D9 drops `GET` and `HEAD` at the proxy. The alternative, TLS interception in the box, adds trust machinery for a mode the loop already covers |
| T5 | Where else can it be turned off? | **Delegated:** the workspace only. It is frozen at admission, and turning it off applies at the next call. Per-Expert control is the domain list (T10) |
| T6 | Links in a typed result keep their query? | **Delegated:** yes, for declared link fields of a typed result only. Visited URLs stay bare |
| T7 | Time limit for browser-use calls | **Delegated:** up to 600 seconds and 40 steps, by default 300 and 25. The box's cap (B2) rises to 600 seconds for browser-use sessions only. Autobots' loop keeps 20 steps and 300 seconds. Rehearsal may lower them |
| T8 | A form for workflow inputs? | **Delegated:** now. A `json` input may declare fields, each with a name, a label and a type. The run card draws a form from them and sends the object, and validation checks the object against the fields. The agent still gets one goal, the object as text |
| T9 | Add `google_flights` (engine A)? | **Delegated:** yes, and it is how prices are got. browser-use doesn't price flights on Google Flights, which answers it with a reCAPTCHA (section 7.1) |
| T10 | With no approval, who sets a browse's domains? | **Owner, 2026-11-19: "Yes, from the Expert".** The owner lists the domains an Expert may browse. Under YOLO, a call naming any other domain is refused before a container starts, and an Expert with no list can't browse |
| T11 | Which model drives browser-use? | **Delegated:** the run's frozen `researcher` route, through the admitted endpoint (US-17.6), on OpenRouter today, where Sol is the default. US-17.6 doesn't wait for a local route |
| T12 | Bot checks | **Delegated:** a bot check or CAPTCHA ends the call with a new stop reason, `bot_check`. Nothing solves it, hides from it or retries around it: no stealth settings, no other user agent, and no Browser Use Cloud or its solver |
| T13 | Where browser-use runs | **Delegated:** its own image, built from the pinned Playwright image (B1). browser-use 1.0.6 gets its own uv-locked environment in `services/browser-use/`, and a container starts per call, as the executor does now. The executor is qualified again for it |
| T14 | Sites anyone can edit, such as a wiki or a forum | **Delegated:** allowed under YOLO, with the risk recorded (section 12). An Expert that browses one says in its instructions never to edit or post. A blocked-path list per Expert is a later decision, if one is needed |
| T15 | What does a person see of a browse that nobody approved? | **Delegated:** one screenshot per browser-use step, kept with the run and shown in its tool row, plus each submit's domain and path. Screenshots of third-party pages stay in the run's private storage, like its artifacts |
| T16 | Ship a YouTube Transcript reader? | **Delegated:** yes, seeded, but its browse domain list starts empty. It can't browse until the owner adds YouTube's hosts, which is where the owner accepts YouTube's terms (section 7.2). A seeded Expert never automates a site by default |

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
- Decisions T1 to T5 and T10

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
  Then nothing tries to solve it, and the call stops with bot_check

Scenario: What it saw is kept
  Given a browse on browser-use under YOLO
  When it finishes, however it stops
  Then each of its steps has one screenshot kept with the run, and the run's tool row shows them with each submit's domain and path

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

### US-17.11: The Family trip Experts and workflow

As a workspace owner
I want a workflow that takes a trip and returns its flight prices and a short guide as JSON
So that I get prices, a link to book and what to do there, and do the booking myself.

Acceptance Criteria:

```gherkin
Scenario: A trip in, flights.json and trip.json out
  Given the Family trip workflow, its Flight finder and Trip guide Experts, and the trip typed into its form
  When it is executed
  Then flights.json and trip.json are published, every price and link in them equals google_flights' output, every guide link is a page the browse visited, and both record when the prices were seen

Scenario: The guide is typed, not guessed
  Given the same execution, with YOLO on
  When the Trip guide browses
  Then its screenshots show the destination typed into Wikivoyage's search, and its recorded submits are that search only

Scenario: Nothing is bought or edited
  Given the same execution
  When it finishes
  Then no request reached a seller or payment host, the browse stayed on en.wikivoyage.org, and nothing was edited or posted
```

Dependencies:
- US-17.9
- US-17.10
- US-17.12

### US-17.12: Input fields for a workflow

As a workspace owner
I want a workflow's JSON input to declare its fields, and the run card to ask for them in a form
So that a person types the trip into labelled fields, not a block of JSON.

Acceptance Criteria:

```gherkin
Scenario: A form from the declared fields
  Given a published workflow whose json input declares origin, destination, depart, return, adults and children_ages, each with a label and a type
  When the owner opens its run card
  Then it shows one labelled field for each, and Run sends them as one object

Scenario: A wrong value is refused by name
  Given the same workflow
  When adults is sent as text, or a declared field is missing
  Then the execution is refused before it starts, naming the field

Scenario: Workflows without fields are unchanged
  Given a workflow whose inputs declare no fields
  When the owner opens its run card
  Then it shows the JSON inputs as it does today
```

Dependencies:
- Decision T8

### US-17.13: The Transcript reader Expert and workflow

As a workspace owner
I want an Expert and a workflow that turn a YouTube video into its transcript as Markdown
So that I get a video's words as a clean, timestamped file I can read, search and reuse.

Acceptance Criteria:

```gherkin
Scenario: A video in, transcript.md out
  Given YOLO on, the Transcript reader Expert with youtube.com, ytimg.com, ggpht.com and gstatic.com as its domains, and the Transcript workflow
  When it is executed with the watch address of one of the owner's own videos
  Then transcript.md is published with the video's title, its source address and every transcript line with its timestamp, and its line count equals the transcript panel's

Scenario: The steps are seen and the video isn't fetched
  Given the same execution
  When it finishes
  Then its step screenshots show "...more" and "Show transcript" pressed, and the proxy refused every request to googlevideo.com

Scenario: Seeded with no domains
  Given a new workspace
  When the owner opens the Transcript reader
  Then its browse domain list is empty, and a run of it is refused before any container starts, naming the missing list

Scenario: Only a YouTube watch address is accepted
  Given the Transcript workflow
  When its video input is not an https YouTube watch or youtu.be address
  Then the execution is refused before it starts, naming the input

Scenario: No transcript offered
  Given a video whose description has no transcript section
  When the Transcript reader browses it
  Then the run ends saying no transcript is offered, and publishes no file

Scenario: A bot check stops it
  Given YouTube answers with a bot check
  When the Transcript reader meets it
  Then the browse stops with bot_check, nothing tries to pass it, and no file is published
```

Dependencies:
- US-17.9
- Decisions T10, T12 and T16

## 12. Risks

- **The default is the permissive one, and nothing asks first.** With YOLO on, a browse starts without approval (T2), and a page's text can steer the model. Within the allowed domains it could then post a comment, fill in a contact form, vote or create an account with made-up details. The Expert's domain list, which the owner sets (T10), is what bounds it. A broad list, such as a whole platform where anyone can post, widens what a steered model can do.
- **Spend without a pause.** Each browse step is a paid model call, and no approval stands between a goal and its browsing. The run's budget and the call's step and time caps are what bound it.
- **The task is typed into third-party sites.** Whatever the goal contains, such as names, dates or routes, may be sent to the allowed domains.
- **Most commercial and government sites turn it away.** Google Flights, the State Department and Costa Rica's central bank all refused a fresh headless browser (section 7.1). browser-use's reach is the sites that allow automated reading, and a bot check stops the call with `bot_check` (T12).
- **Editable sites (T14).** On a wiki or a forum, the proxy can't tell reading from editing on the same host. Only the Expert's instructions stop an edit, and the step screenshots (T15) show one afterwards.
- **Sites' terms.** YouTube's terms, among others, forbid automated access without permission. YOLO makes such browsing possible, not permitted. The Expert's domain list is where the owner takes that decision (T10).
- **Pages change.** browser-use reads each page as it is, so a change to Wikivoyage's layout can break the Trip guide. The flights depend on SerpApi's parsing of Google Flights.
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
- The probes of section 7.1, run on 2026-11-19 with Playwright's Chromium. Their raw results stay in the ignored `.checks/probe`, because a bot-check page shows the network's public address.
