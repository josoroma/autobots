## ADDED Requirements

### Requirement: Each address once in each browser, with no model

The scoreboard SHALL open each address the owner names once in each browser, in the isolated executor, with no model call, and remove its containers.

#### Scenario: Each address once in each browser, with no model
- **GIVEN** the box's and the stealth browser's images, and https://example.com/ and https://example.org/ as the addresses named
- **WHEN** the scoreboard is run
- **THEN** it opens each address once in each browser in the isolated executor, makes no model call, records each as opened with its bytes and seconds, and removes its containers

### Requirement: Four results

The scoreboard SHALL record `opened`, `check`, `blocked` or `error` for each opening.

#### Scenario: Four results
- **GIVEN** scripted openings where a page opens, shows a check, is blocked, and fails to load
- **WHEN** the scoreboard records them
- **THEN** they read opened, check, blocked and error

### Requirement: Hosts only

What the scoreboard keeps and prints SHALL hold hosts, and no path, query or page text.

#### Scenario: Hosts only
- **GIVEN** an address with a path and a query
- **WHEN** the scoreboard finishes
- **THEN** what it keeps and prints holds its host, and no path, query or page text

### Requirement: Only the owner's to run

No verification profile SHALL run the scoreboard, and it SHALL open nothing without an address.

#### Scenario: Only the owner's to run
- **GIVEN** the verification profiles
- **WHEN** each profile's commands are listed, and the scoreboard is started with no address
- **THEN** no profile runs the scoreboard, and it opens nothing
