# Spec Delta

## ADDED Requirements

### Requirement: The concept seed adds Google bot

The concept seed SHALL also create Google bot, with `google_search`, `extract_website_content`, `save_artifact` and `publish_artifact` (PRD-Studio SD-02, Decision 0032 G8). It SHALL be created once, and saved without its unavailable tools, saying so in its purpose.

#### Scenario: The concept seed adds Google bot
- **GIVEN** a disposable stack, a fresh workspace and no SerpApi, Jina or GitHub variable
- **WHEN** the concept seed runs twice
- **THEN** six Experts exist once each, Google bot among them, granted save_artifact and publish_artifact, saved without google_search and extract_website_content, and its purpose says so

## MODIFIED Requirements

### Requirement: An optional concept seed

A repeatable seed, separate from migrations, SHALL create in a chosen workspace, once each, the six concept Experts and six workflows that PRD-Studio SD-02 defines. Google bot is one of the six, by Decision 0032 G8. The seed:
- SHALL hold no key, token or password, and leave no job, run or routine occurrence pending;
- SHALL never overwrite what already exists;
- SHALL save an Expert without its unavailable tools and say so in its purpose;
- SHALL seed a workflow as a draft when a tool it needs is unavailable.

#### Scenario: Repeatable and separate from migrations
- **GIVEN** a disposable stack after migrations, and a chosen workspace
- **WHEN** the seed runs twice
- **THEN** the workspace holds once each the Experts Market watcher, Research analyst, Brief writer, Issue triager, Code maintainer and Google bot, and the workflows Weekly competitor brief, Monthly FX and inflation note, Nightly test triage, Interview synthesis, Release notes from merged PRs and Vendor due diligence, and running migrations alone creates none of them

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
- **THEN** the six Experts and six workflows of SD-02 exist, Issue triager and Code maintainer are saved without their unavailable GitHub tools and say so in their purpose, Nightly test triage, Release notes from merged PRs and Interview synthesis are drafts, and the other three are published
