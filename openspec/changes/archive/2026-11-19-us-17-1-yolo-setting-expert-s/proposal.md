# Proposal

## Why

US-17.1 in SPECS.md: [Decision 0035](../../../docs/engineering/decisions/0035-browser-use-typing-and-transcripts.md#decision) Y1 to Y4, Y13 and Y15. The owner decided three things:
- Browsing gets a workspace setting, "Let browsing type and submit (YOLO)", on by default.
- While it is on, a `browse_goal` call starts without approval.
- Its domains must come from the list the owner keeps on each Expert.

Today every `browse_goal` call waits for a person (Decision 0018 B6), and nothing on an Expert says where it may browse. Every later story of EPIC-17 depends on this one: browser-use runs only under YOLO, and the Transcript reader's domains live on its Expert.

## What Changes

- **A workspace setting.** It is kept in a new `app_private.browsing_settings` table, where no row means on, with an optimistic version. It is read by every member, changed only by the owner, and served at `GET` and `PUT /v1/settings/browsing`. The table also records when the owner has seen the one-time Home notice (`POST /v1/settings/browsing/notice`).
- **A frozen flag.** Admission freezes the setting in a new `runs.browsing_yolo` column. A child takes its parent's value. Runs admitted before this change read as off.
- **A call is YOLO** only while both the run's frozen value and the workspace's current value are on (Y4).
- **The approval gate.** `ApprovalPolicy` gains an optional waiver, read for each call. `browse_goal`'s waiver is "the call is YOLO", so a YOLO call is released without approval, and any other call still waits on every call (B6).
- **The Expert's browse domains.** `ExpertConfig` gains `browse_domains`. A change to it makes a new Expert version, as any config change does. Under YOLO, `browse_goal` refuses before any container starts:
  - `browse_domains_missing`, from an Expert with no list;
  - `browse_domain_not_granted`, for a domain outside the list.
- **The tool row.** A YOLO call's tool row records `typing: on` beside its public `allowed_domains`.
- **Studio.**
  - Settings → Browsing, with the checkbox and one line saying what it allows.
  - A one-time notice on Home.
  - The Expert editor's browse domain list, for an Expert that grants `browse_goal`.
- **Words.** `browse_goal`'s guide and its approval reason, the Tools page's approval label for it, and the Expert cards' approval note now say that approval on every call applies with YOLO off. The guide adds Y13's rule for wikis and forums.
- **Documents.**
  - PRD-Tool-Catalog AB-01, AB-02 and TC-02, and PRD-Studio SE-02 and Home.
  - `README.md`, `README-DEV.md`, the operations runbook and `CODEBASE.md`.

## Capabilities

### New Capabilities
- `browsing-yolo`: the YOLO setting, its freezing and its effect on approval, the Expert's browse domains, and how both show in the Studio.

### Modified Capabilities
- None as requirements. `goal-driven-browsing`'s approval on every call now holds only with YOLO off, which `browsing-yolo` states. `experts` gains a field, with its versioning unchanged.

## Impact

- **Database:** one migration, `20261119000065_browsing_yolo.sql`. It adds the `browsing_settings` table and the `runs.browsing_yolo` column, with the default `false`.
- **Python:** `application/browsing_settings.py` (new), plus changes to `application/runs.py` (admission), `application/tool_definitions.py` and `tool_gateway.py` (the waiver), `application/tool_uses.py` (`typing` in the public input), `application/browsing_tool.py`, `contracts/experts.py`, a new `contracts/browsing_settings.py`, `api/settings_routes` and the tool guide.
- **Web:** `app/settings/browsing`, the Settings navigation, a Home notice, the Expert editor, and the Tools and Experts texts.
- **Contracts:** OpenAPI and the TypeScript client are regenerated.
- **Behaviour:** browsing still runs on Autobots' read-only loop. Y15's engine choice arrives with US-17.3. Until then a YOLO call starts without approval and reads only.
