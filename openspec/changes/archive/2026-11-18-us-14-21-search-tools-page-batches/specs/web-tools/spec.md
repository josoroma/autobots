# Spec Delta

## MODIFIED Requirements

### Requirement: Jina search is bounded and recorded

`search_web` version 1 SHALL return at most its requested number of results, no more than 10, as titles, URLs and snippets labelled third-party, recorded as a tool use. A request beyond the ceiling SHALL be refused before any request. Version 2 pages its results as the `search-paging` capability specifies.

#### Scenario: Search against a fake transport
- **GIVEN** a granted search_web tool at version 1, a fake key and a fake s.jina.ai transport
- **WHEN** the model searches with max_results within 10
- **THEN** it returns validated results with title, URL and snippet, labelled third-party and recorded as a tool use, and a request beyond the ceiling is refused before any request
