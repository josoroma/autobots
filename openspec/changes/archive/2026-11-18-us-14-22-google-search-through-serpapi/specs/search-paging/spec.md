# Spec Delta

## MODIFIED Requirements

### Requirement: A short page stops the paging

Paging SHALL stop and report `no_more` at a page that adds nothing new. It SHALL also stop at a page with fewer than 10 results, unless the provider's reply says whether another page exists. Then that signal decides, as SerpApi's does for `google_search` (Decision 0032 G3).

#### Scenario: A short page stops the paging
- **GIVEN** a fake Jina transport whose first page is full and whose second page holds 4 results
- **WHEN** search_web version 2 is called with max_results 30
- **THEN** it sends two requests, returns 14 results, and reports pages 2 and stopped no_more
