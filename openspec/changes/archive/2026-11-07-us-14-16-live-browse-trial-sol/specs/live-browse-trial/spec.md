## ADDED Requirements

### Requirement: One live read-only browse within US$1

The trial SHALL run one approved read-only `browse_goal` call on a run whose researcher route is frozen on Sol with a US$1 budget, every model call admitted on Sol through the shared gateway, with the key read by the trial's own process, and SHALL record the summary's label, visited URLs, model calls, receipts, spend and the hosts the proxy connected to.

#### Scenario: One live read-only browse within US$1
- **GIVEN** the owner's authorized trial on the persistent or a disposable stack, the owner's key read from the key file by the trial's own process, a run whose researcher route is frozen on Sol with a US$1 budget, and one approved read-only browse_goal call
- **WHEN** it browses from https://example.com/ with allowed_domains example.com and iana.org
- **THEN** it returns a summary labelled third-party and the visited URLs, every model call is admitted with a reservation, invocation ticket and receipt on Sol through the shared gateway, the run's spend with its reservations stays within US$1, and the egress proxy connects to no host outside example.com and iana.org

### Requirement: Not repeated without the owner

A recorded trial SHALL refuse to start again without the owner's request, before any container starts or model call is made.

#### Scenario: Not repeated without the owner
- **GIVEN** the trial's recorded result
- **WHEN** the trial is started again without a new request from the owner
- **THEN** it refuses before any container starts or model call is made
