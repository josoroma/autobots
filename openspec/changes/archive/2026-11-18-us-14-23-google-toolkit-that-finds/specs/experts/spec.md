# Spec Delta

## MODIFIED Requirements

### Requirement: The concept seed adds Google bot

The concept seed SHALL also create Google bot (PRD-Studio SD-02, Decisions 0032 G8 and 0033 K8), granted:
- `google_search`, `google_map`, `google_extract` and `google_crawl`;
- `save_artifact` and `publish_artifact`.

It SHALL be created once, and saved without its unavailable tools, saying so in its purpose.

#### Scenario: The concept seed adds Google bot
- **GIVEN** a disposable stack, a fresh workspace and no SerpApi, Jina or GitHub variable
- **WHEN** the concept seed runs twice
- **THEN** six Experts exist once each, Google bot among them, granted google_extract, save_artifact and publish_artifact, saved without google_search, google_map and google_crawl, and its purpose says so
