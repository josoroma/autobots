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

## ADDED Requirements

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
