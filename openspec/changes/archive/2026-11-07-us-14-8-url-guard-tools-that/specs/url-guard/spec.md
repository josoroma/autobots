## ADDED Requirements

### Requirement: Unsafe URLs are refused before any request

Every URL a tool fetches, or sends to a provider, SHALL pass one guard before any request names it: `https` only, no userinfo, a bounded length, and a host whose every DNS answer is a public address. A refusal SHALL be a typed code.

#### Scenario: Refuse unsafe URLs before any request
- **GIVEN** a URL that isn't https, carries userinfo, exceeds the length bound, or has any DNS answer that is loopback, private, link-local, carrier-grade NAT, multicast, reserved, unspecified or cloud metadata
- **WHEN** a tool submits it to the guard with a fake resolver and transport
- **THEN** it is refused with a typed code and no request is sent

### Requirement: Redirects are revalidated and bounded

A guarded fetch SHALL check each redirect target before requesting it, and SHALL follow at most three redirects.

#### Scenario: Revalidate every redirect
- **GIVEN** a fake transport that redirects
- **WHEN** the guarded fetch follows it
- **THEN** each target is revalidated, an unsafe target is refused, and a fourth redirect is refused with a typed code

### Requirement: Size and time are capped

A guarded fetch SHALL stop with a typed code when a response exceeds its size cap or its time cap.

#### Scenario: Cap size and time
- **GIVEN** a fake response larger than the size cap or slower than the time cap
- **WHEN** it is fetched through the guard
- **THEN** the fetch stops with a typed code
