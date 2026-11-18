## MODIFIED Requirements

### Requirement: An optional concept seed

A repeatable seed, separate from migrations, SHALL create in a chosen workspace, once each, the seven concept Experts and seven workflows that PRD-Studio SD-02 defines. Google bot is one of the seven, by Decision 0032 G8, and Deep research writer and Deep research content writer, by Decision 0034 E1 and F1. The seed:
- SHALL hold no key, token or password, and leave no job, run or routine occurrence pending;
- SHALL never overwrite what already exists;
- SHALL save an Expert without its unavailable tools and say so in its purpose;
- SHALL seed a workflow as a draft when a tool it needs is unavailable.

#### Scenario: Repeatable and separate from migrations
- **GIVEN** a disposable stack after migrations, and a chosen workspace
- **WHEN** the seed runs twice
- **THEN** the workspace holds once each the Experts Market watcher, Research analyst, Brief writer, Issue triager, Code maintainer, Google bot and Deep research writer, and the workflows Weekly competitor brief, Monthly FX and inflation note, Nightly test triage, Interview synthesis, Release notes from merged PRs, Vendor due diligence and Deep research content writer, and running migrations alone creates none of them

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

## ADDED Requirements

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
