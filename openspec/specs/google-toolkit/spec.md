# google-toolkit Specification

## Purpose
A Google toolkit that finds with Google through SerpApi and reads pages directly from their sites, politely and through the URL guard: `google_map`, `google_extract` and `google_crawl` beside `google_search`, in one group (Decision 0033).

## Requirements

### Requirement: The Google group holds four tools

The group `google` SHALL hold `google_search`, `google_map`, `google_extract` and `google_crawl`, each version 1, with providers `serpapi`, `serpapi`, `direct` and `serpapi`. `google_search` SHALL keep its pinned digest, and the new tools' schemas SHALL be pinned. New grants SHALL take version 1. `search_web` and `tavily_search` SHALL stay in `web_search`.

#### Scenario: The Google group holds four tools
- **GIVEN** the registry the catalog and the worker are built from
- **WHEN** the catalog lists the group google and the schema-version pin test runs
- **THEN** google_search v1, google_map v1, google_extract v1 and google_crawl v1 appear once each in the group google with providers serpapi, serpapi, direct and serpapi, google_search keeps its pinned digest, the new tools' schemas are pinned, new grants take version 1, and search_web and tavily_search stay in web_search

### Requirement: google_map lists the pages Google has indexed for a site

`google_map` SHALL search SerpApi for `site:<host><path>`, built from its URL:
- the host lowercased;
- no scheme, query, fragment or trailing slash.

It SHALL page through the shared pager. It SHALL keep results on the site's host and its subdomains, and drop the rest. It SHALL return `base_url` and the URLs in Google's order, with the paging fields.

#### Scenario: google_map lists the pages Google has indexed for a site
- **GIVEN** google_map over a fake SerpApi transport whose two pages of results include a link on another host and one on a subdomain
- **WHEN** it is called with url https://Example.com/docs/?x=1#top and max_results 20
- **THEN** every request searches site:example.com/docs, the off-host link is dropped, the subdomain's link is kept, and the output holds base_url, the urls in Google's order, pages 2 and the stop reason

### Requirement: google_extract reads pages as markdown, politely

`google_extract` SHALL read pages with these limits:
- up to 5 pages, each through the URL guard;
- robots.txt read once per host;
- the user agent `Autobots/1.0 (local research agent)` on every request;
- at least one second between requests to one host.

Each result SHALL hold its URL, title, markdown and word count. The output SHALL be labelled third-party, with the text cut to the shared budget.

#### Scenario: google_extract reads pages as markdown, politely
- **GIVEN** a fake resolver and transport serving robots.txt and two HTML pages on one host and one HTML page on another, and a recorded sleep
- **WHEN** google_extract is called with those three URLs
- **THEN** each host's robots.txt is fetched once, every request carries the user agent Autobots/1.0 (local research agent), the two requests to the same host are at least one second apart, each result holds its url, title, markdown and word count, the output is labelled third-party, and the text is cut to the shared budget

### Requirement: robots.txt is obeyed and fails closed

A page that robots.txt disallows for Autobots SHALL fail `robots_disallowed` before it is requested. A 404 or 410 robots.txt SHALL allow. Any other robots.txt answer that isn't a readable file SHALL deny. A page whose final host after redirects disallows it SHALL fail `robots_disallowed`, and none of its text SHALL be returned.

#### Scenario: robots.txt is obeyed and fails closed
- **GIVEN** hosts whose robots.txt disallows a path for Autobots, answers 404, answers 500, and a page that redirects to a host whose robots.txt disallows it
- **WHEN** google_extract reads a URL on each
- **THEN** the disallowed path fails robots_disallowed with no page request, the 404 host's page is read, the 500 host's page fails robots_disallowed with no page request, and the redirected page fails robots_disallowed and none of its text is returned

### Requirement: Page failures are typed and never retried

A page failure SHALL be a typed code: `page_http_<status>`, `unsupported_media_type`, `no_readable_text` or the guard's `url_*` code. No page SHALL be requested more than once.

#### Scenario: Page failures are typed and never retried
- **GIVEN** pages that answer 404, a PDF, an HTML page with no readable text, and a URL whose host resolves to a private address
- **WHEN** google_extract reads each
- **THEN** they fail page_http_404, unsupported_media_type, no_readable_text and url_host_refused, the private address is never requested, and each page is requested at most once

### Requirement: google_crawl maps a site with Google, then reads its pages

`google_crawl` SHALL make one SerpApi search for up to `limit` pages of the site, 10 at most. It SHALL then read them as `google_extract` does, and return their markdown, the failures and `pages`.

#### Scenario: google_crawl maps a site with Google, then reads its pages
- **GIVEN** a fake SerpApi transport that returns three links on the site and one off it, and a fake site serving those pages
- **WHEN** google_crawl is called with that site and limit 5
- **THEN** it makes one SerpApi search and reads the three pages on the site, returns their markdown, lists any failures, and reports pages 1

### Requirement: Extraction opens no connection of its own

Extracting a page SHALL make no request beyond that page and its host's robots.txt.

#### Scenario: Extraction opens no connection of its own
- **GIVEN** an HTML page that references images, scripts and other sites, served by a fake transport
- **WHEN** google_extract reads it
- **THEN** the transport receives only that page's robots.txt and the page itself

### Requirement: One metered call each, with public fields only

A `google_extract` or `google_crawl` call SHALL be one tool use, counted once against the metered limit. Its public output SHALL hold counts, with no page text and no key.

#### Scenario: One metered call each, with public fields only
- **GIVEN** a disposable database, a run whose scope grants google_extract and google_crawl, and fake transports
- **WHEN** the gateway executes one call of each
- **THEN** each is one tool use counted once against the metered limit, its public output holds counts and no page text, and no key appears in the record

### Requirement: The new dependency is pinned and recorded

`trafilatura` SHALL be an exact pin at 2.3.1, locked with its transitive packages and named in the toolchain runbook's table.

#### Scenario: The new dependency is pinned and recorded
- **GIVEN** the Python manifest, its lock and the toolchain runbook
- **WHEN** the toolchain manifest test runs
- **THEN** trafilatura is an exact pin at 2.3.1, locked with its transitive packages, and named in the runbook's table
