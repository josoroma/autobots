## ADDED Requirements

### Requirement: Jina search is bounded and recorded

`search_web` SHALL return at most its requested number of results, no more than 10, as titles, URLs and snippets labelled third-party, recorded as a tool use. A request beyond the ceiling SHALL be refused before any request.

#### Scenario: Search against a fake transport
- **GIVEN** a granted search_web tool, a fake key and a fake s.jina.ai transport
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
