# experts Specification

## Purpose
TBD - created by archiving change us-5-1-versioned-experts-direct-sessions. Update Purpose after archive.

## Requirements

### Requirement: Configuration versions
When a revision of an Expert with instructions, tools, skills and model-role binding is saved and new or existing sessions dispatch work, new work SHALL use the chosen revision and in-flight work SHALL preserve its frozen revision and permissions.

#### Scenario: Preserve configuration versions
- **GIVEN** an Expert with instructions, tools, skills and model-role binding
- **WHEN** a revision is saved and new or existing sessions dispatch work
- **THEN** new work uses the chosen revision and in-flight work preserves its frozen revision and permissions

### Requirement: Routing within granted scope
When an assignment is selected in a coordinator or direct Expert session, the configured Expert and allowed tools SHALL be visible, and no implicit model or broader connector grant MUST be added.

#### Scenario: Route within granted scope
- **GIVEN** a coordinator or direct Expert session
- **WHEN** an assignment is selected
- **THEN** the configured Expert and allowed tools are visible and no implicit model or broader connector grant is added

### Requirement: Expert cards show usage, effect filters and a way to start

Experts SHALL show each Expert's executor role and profile, its first four tools and a count of the rest, its run count and last run, Start run, and a note in words when a tool needs approval on every call. Experts SHALL filter by All, Can change things outside and Read only, with counts that add up, and by name.

#### Scenario: Card facts
- **GIVEN** an Expert whose latest version binds the executor to a profile and grants six tools, and which has three runs
- **WHEN** a member opens Experts
- **THEN** its card shows the executor role and profile, the first four tools followed by "+2", a run count of 3 with the time of the last run, and Start run

#### Scenario: Start run discloses first
- **GIVEN** an Expert's card
- **WHEN** the member activates Start run
- **THEN** run creation for that Expert shows the MP-07 disclosure, and nothing is sent until Run is pressed

#### Scenario: Can change things outside
- **GIVEN** Experts that grant a consequential tool and Experts that grant none
- **WHEN** the member picks Can change things outside, then types part of a name in the search
- **THEN** each filter shows its count, Can change things outside lists exactly the Experts with a consequential tool, and the search narrows the list by name

#### Scenario: Approval note
- **GIVEN** an Expert granting a tool that needs approval on every call, such as create_github_issue
- **WHEN** its card renders
- **THEN** the card says so in words, such as "Approval on every issue"

#### Scenario: Read only is the complement
- **GIVEN** an Expert whose only writing tool is save_artifact and another granting create_github_issue
- **WHEN** the person picks Read only, then Can change things outside
- **THEN** the first Expert is listed under Read only, the second under Can change things outside, and the two counts add up to All

### Requirement: An optional concept seed

A repeatable seed, separate from migrations, SHALL create in a chosen workspace, once each, the seven concept Experts and seven workflows that PRD-Studio SD-02 defines. Google bot is one of the seven, by Decision 0032 G8, and Deep research writer and Deep research content writer, by Decision 0034 E1 and F1. The seed:
- SHALL hold no key, token or password, and leave no job, run or routine occurrence pending;
- SHALL never overwrite what already exists;
- SHALL save an Expert without its unavailable tools and say so in its purpose;
- SHALL seed a workflow as a draft when a tool it needs is unavailable.

#### Scenario: Repeatable and separate from migrations
- **GIVEN** a disposable stack after migrations, and a chosen workspace
- **WHEN** the seed runs twice
- **THEN** the workspace holds once each the Experts Market watcher, Research analyst, Brief writer, Issue triager, Code maintainer, Google bot and Deep research writer, and the workflows Weekly competitor brief, Monthly FX note, Nightly test triage, Interview synthesis, Release notes from merged PRs, Vendor due diligence and Deep research content writer, and running migrations alone creates none of them

#### Scenario: No secrets and no pending work
- **GIVEN** the seed's files and the database after it runs
- **WHEN** they are scanned
- **THEN** they hold no key, token or password, and no job, run or routine occurrence is pending

#### Scenario: Unavailable tools seed a draft
- **GIVEN** the GitHub variables not set
- **WHEN** the seed runs
- **THEN** each workflow that needs an unavailable tool exists only as a draft, and the others are published

#### Scenario: Seed follows SD-02
- **GIVEN** a workspace without the GitHub variables set
- **WHEN** the seed runs
- **THEN** the seven Experts and seven workflows of SD-02 exist, Issue triager and Code maintainer are saved without their unavailable GitHub tools and say so in their purpose, Nightly test triage, Release notes from merged PRs and Interview synthesis are drafts, and the others are published unless a tool they need is unavailable

### Requirement: The concept seed adds Google bot

The concept seed SHALL also create Google bot (PRD-Studio SD-02, Decisions 0032 G8 and 0033 K8), granted:
- `google_search`, `google_map`, `google_extract` and `google_crawl`;
- `save_artifact` and `publish_artifact`.

It SHALL be created once, and saved without its unavailable tools, saying so in its purpose.

#### Scenario: The concept seed adds Google bot
- **GIVEN** a disposable stack, a fresh workspace and no SerpApi, Jina or GitHub variable
- **WHEN** the concept seed runs twice
- **THEN** seven Experts exist once each, Google bot among them, granted google_extract, save_artifact and publish_artifact, saved without google_search, google_map and google_crawl, and its purpose says so

### Requirement: The concept seed adds the Deep research writer and its workflow

The concept seed SHALL also create the Deep research writer (Decision 0034 E1 to E3), with its purpose, its instructions and its eight tools: `google_search`, `google_extract`, `search_web`, `extract_website_content`, `read_artifact`, `read_run_file`, `save_artifact` and `publish_artifact`. It SHALL create the Deep research content writer workflow (F1): input, Research and write, to string, Check and report, approval, output, both agent steps naming the Deep research writer. The workflow SHALL be published when `google_search` is available, and a draft otherwise (F2). Neither SHALL be created twice or changed when it already exists.

#### Scenario: The seed adds the Deep research writer and its workflow
- **GIVEN** a disposable database with a workspace that already has the earlier concept Experts and workflows, and SerpApi available
- **WHEN** the concept seed runs twice
- **THEN** the first run adds the Deep research writer with its purpose, instructions and eight tools and publishes the Deep research content writer workflow, everything that existed is unchanged, and the second run adds nothing

#### Scenario: Without SerpApi the workflow is a draft
- **GIVEN** a disposable database with no SerpApi key
- **WHEN** the concept seed runs
- **THEN** the Deep research writer is saved without google_search and its purpose says so, and the workflow is a draft

### Requirement: The seed's Market watcher tracks prices and exchange rates

The concept seed SHALL give the Market watcher no `inflation_rates`, and SHALL seed "Monthly FX note", with an input for the currency pairs and the step "Pull the rates", in place of "Monthly FX and inflation note" (Decision 0036 R7). It SHALL keep a Market watcher or "Monthly FX and inflation note" that already exists as it is.

#### Scenario: The seed on a new workspace
- **GIVEN** a new workspace
- **WHEN** the concept seed runs twice
- **THEN** the Market watcher tracks prices and exchange rates without inflation_rates, "Monthly FX note" is published with an input for the currency pairs and the step "Pull the rates", no "Monthly FX and inflation note" exists, and the second run adds nothing

#### Scenario: The seed on a workspace seeded before
- **GIVEN** a workspace where the concept seed ran before the change
- **WHEN** the seed runs again
- **THEN** the Market watcher and "Monthly FX and inflation note" are unchanged, and "Monthly FX note" is added beside them
