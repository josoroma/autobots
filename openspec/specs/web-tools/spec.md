# web-tools Specification

## Purpose
TBD - created by archiving change us-14-6-tavily-search-extract-map. Update Purpose after archive.

## Requirements

### Requirement: Tavily calls are bounded and recorded

Tavily's tools SHALL refuse arguments beyond their schema ceilings, or options they don't offer, before any request. An allowed call SHALL return validated output labelled third-party, cut to size with a notice, and SHALL be recorded as a tool use.

#### Scenario: Bounded calls against a fake transport
- **GIVEN** a granted Tavily tool, a fake key and a fake transport
- **WHEN** the model calls it with an argument beyond a schema ceiling, and then with allowed arguments
- **THEN** the first is refused before any request, and the second returns validated output labelled third-party, truncated at max_output_bytes with a notice, and recorded as a tool use

### Requirement: No provider-side inference

No Tavily tool SHALL offer an option that makes Tavily generate an answer or follow natural-language instructions, and every request SHALL send such options off or not at all.

#### Scenario: No provider-side inference
- **GIVEN** any Tavily tool call against a fake transport
- **WHEN** its request is built
- **THEN** include_answer, auto_parameters and natural-language instructions are absent or off, and no tool schema offers them

### Requirement: Tavily URLs pass the guard

Every URL a Tavily tool sends SHALL pass the URL guard first.

#### Scenario: URLs pass the guard
- **GIVEN** tavily_extract, tavily_map or tavily_crawl named with a URL the guard refuses
- **WHEN** it is called against a fake transport
- **THEN** it fails with the guard's typed code and the transport receives no request

### Requirement: Jina search is bounded and recorded

`search_web` version 1 SHALL return at most its requested number of results, no more than 10, as titles, URLs and snippets labelled third-party, recorded as a tool use. A request beyond the ceiling SHALL be refused before any request. Version 2 pages its results as the `search-paging` capability specifies.

#### Scenario: Search against a fake transport
- **GIVEN** a granted search_web tool at version 1, a fake key and a fake s.jina.ai transport
- **WHEN** the model searches with max_results within 10
- **THEN** it returns validated results with title, URL and snippet, labelled third-party and recorded as a tool use, and a request beyond the ceiling is refused before any request

### Requirement: Jina extraction uses reader mode only

`extract_website_content` SHALL use Jina's reader with no model-based option, and SHALL return the URL, markdown labelled third-party and cut to size with a notice, and links.

#### Scenario: Extract in reader mode without provider inference
- **GIVEN** a granted extract_website_content tool and a fake r.jina.ai transport
- **WHEN** it is called with a URL the guard admits
- **THEN** the request uses reader mode with no model-based reader option, and the output is the URL, markdown labelled third-party and truncated at max_output_bytes with a notice, and links

### Requirement: Jina URLs pass the guard

`extract_website_content` SHALL send no URL the guard refuses.

#### Scenario: URLs pass the guard
- **GIVEN** extract_website_content named with a URL the guard refuses
- **WHEN** it is called against a fake transport
- **THEN** it fails with the guard's typed code and the transport receives no request
