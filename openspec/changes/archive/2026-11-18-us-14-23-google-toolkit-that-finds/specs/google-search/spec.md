# Spec Delta

## MODIFIED Requirements

### Requirement: google_search is a web search tool from SerpApi

`google_search` v1 SHALL be registered once in the group `google` (Decision 0033 K1), with:
- provider `serpapi`;
- operation class `read_only` and cost class `metered_provider`;
- the key requirement `SERPAPI_API_KEY`;
- a pinned schema digest.

New grants SHALL take version 1. Without a key from any source, it SHALL be `key_missing`, with a repair naming Settings → Keys & vars and `SERPAPI_API_KEY`.

#### Scenario: google_search is a web search tool from SerpApi
- **GIVEN** the registry the catalog and the worker are built from, and a workspace with no SerpApi key in any source
- **WHEN** the catalog lists the group google and the schema-version pin test runs
- **THEN** google_search v1 appears once with provider serpapi, operation class read_only, cost class metered_provider and key requirement SERPAPI_API_KEY, its schemas are pinned, new grants take version 1, and it is key_missing with a repair that names Settings → Keys & vars and SERPAPI_API_KEY
