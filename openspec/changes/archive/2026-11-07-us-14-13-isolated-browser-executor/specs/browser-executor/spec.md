## ADDED Requirements

### Requirement: The browser can't reach this Mac or a private network

The executor's browser SHALL reach only `https` on public addresses of the hosts its call names, through an egress proxy that connects to the address it checked. Loopback, the Docker host, private, link-local, carrier-grade NAT and metadata addresses, names resolving to them, `file://` URLs, downloads, requests with a body, and requests or bytes past the per-call caps SHALL be refused, and the proxy's log SHALL name hosts without paths or queries.

#### Scenario: The browser can't reach this Mac or a private network
- **GIVEN** an executor on a disposable stack whose browser a scripted model drives
- **WHEN** the browser requests, directly or through a redirect, subresource or WebSocket upgrade, the API's or Supabase's loopback ports, the Docker host, a private address, the metadata address, a public name resolving to loopback, a file:// URL, a download, a non-GET request with a body, or more bytes or requests than the per-call cap
- **THEN** each is refused by the egress proxy or the browser, the proxy's log names hosts without paths or queries, and a GET to the qualification host https://example.com/, which the URL guard admits, loads through the proxy connected to the address it checked

### Requirement: Nothing of the host enters the container

The browser container SHALL run the digest-pinned image as a non-root user with all capabilities dropped, `no-new-privileges`, a read-only root, a 256 MiB `tmpfs` and caps of 1 CPU, 1 GiB and 256 processes, with no mount, volume, Docker socket, key or database URL, only on its internal network, and its DevTools SHALL be reachable only on loopback with the session token.

#### Scenario: Nothing of the host enters the container
- **GIVEN** an executor started by a worker that holds model and provider keys and a database URL
- **WHEN** the browser container and its CDP endpoint are inspected
- **THEN** it runs the digest-pinned Playwright image as a non-root user with all capabilities dropped, no-new-privileges, a read-only root, a 256 MiB tmpfs and caps of 1 CPU, 1 GiB memory and 256 processes, with no bind mount, volume, Docker socket, key or database URL, only the internal network behind the egress proxy, and CDP published on 127.0.0.1 on a random port that refuses a connection without the session token

### Requirement: A session is bounded and owned by one attempt

A session SHALL end, closing CDP and removing its containers, when a cap is enforced, the time cap is reached, the run is cancelled or the worker loses its lease, and a sweeper SHALL remove sessions a crashed worker left.

#### Scenario: Bounded and owned by one attempt
- **GIVEN** a browsing call in progress whose containers are labelled with its run and generation
- **WHEN** it exceeds its memory or process cap, reaches 300 seconds, the run is cancelled, or the worker loses its lease
- **THEN** the CDP session closes and its containers are removed, and a sweeper removes the labelled containers a crashed worker left

### Requirement: Qualified only after the live check

The executor SHALL report qualified only from a passing live check that observed every listed refusal, at the current image definitions and code.

#### Scenario: Qualified only after the live check
- **GIVEN** the executor's live qualification check on a disposable stack with a scripted model
- **WHEN** any refusal it lists is not observed, and then when every one is observed
- **THEN** the executor reports not qualified in the first case, and qualified only in the second
