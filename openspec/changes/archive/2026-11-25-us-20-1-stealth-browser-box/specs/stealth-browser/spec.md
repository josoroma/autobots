## ADDED Requirements

### Requirement: It says what it is

The stealth browser SHALL be Google Chrome, headed, with the workspace's time zone, Chrome's default languages and software WebGL, and SHALL NOT name a user agent, device, GPU, brand or fingerprint that isn't its own.

#### Scenario: It says what it is
- **GIVEN** the stealth browser's container with no outside network, for a workspace whose time zone is America/Costa_Rica
- **WHEN** a page there reads its user agent, brands, screen, time zone, languages and WebGL
- **THEN** nothing says Headless, the brands name Google Chrome, the screen is a desktop size, the time zone is America/Costa_Rica, the languages are Chrome's default, and WebGL is present and names its software renderer

### Requirement: The box still holds

A stealth session SHALL keep the box's hardening, caps, proxy, guard and cleanup, with a fresh profile each call. Only its browser container's process cap SHALL differ: 512.

#### Scenario: The box still holds
- **GIVEN** a stealth session and a box session on a disposable stack
- **WHEN** each container is inspected and driven past its process cap, and another stealth session follows
- **THEN** the stealth container has the box's hardening and other caps and holds no key, cookie, card or host file, the stealth session ends at 512 processes and the box's at 256, and the next stealth session starts with a fresh profile

### Requirement: Qualified apart

The stealth browser SHALL report qualified only while the executor is qualified, its own live check observed every case it requires at today's fingerprint, and its image carries that fingerprint.

#### Scenario: Qualified apart
- **GIVEN** the stealth browser's qualification on a disposable stack with a scripted driver, reaching only Decision 0018's qualification hosts
- **WHEN** a case it requires isn't observed, and then when every refusal BX-05 lists and every case of its own is observed on the stealth image
- **THEN** it reports not qualified in the first, and qualified in the second only while the executor is qualified and the image carries today's fingerprint

### Requirement: The owner sets an Expert's browser

An Expert's version SHALL name its browser, `box` or `stealth`, set in the Expert editor and shown on the Expert's card.

#### Scenario: The owner sets an Expert's browser
- **GIVEN** an Expert that grants browse_goal
- **WHEN** the owner sets its browser to stealth beside its browse domains in the editor and saves
- **THEN** a new version holds stealth, the earlier version is unchanged, and the Expert's card and editor show the browser

### Requirement: An Expert on box keeps its bytes

The browser SHALL be left out of an Expert's stored configuration, request and receipt while it is `box`.

#### Scenario: An Expert on box keeps its bytes
- **GIVEN** an Expert version saved before the change, and the receipt of its save
- **WHEN** it is read, the same request is sent again, and the owner saves a revision that keeps the browser on box
- **THEN** each version reads as box, no stored configuration names a browser, and the repeated request matches its receipt

### Requirement: The owner chooses, not the model

No input of `browse_goal` SHALL name a browser.

#### Scenario: The owner chooses, not the model
- **GIVEN** an Expert set to box, and a scripted model whose task asks for another browser
- **WHEN** it browses
- **THEN** it runs on the box's browser, and no input of any browse_goal version names a browser

### Requirement: Either engine drives the Expert's browser

The browser SHALL be the Expert's whichever engine drives it, and the tool row SHALL show `browser: stealth` for a stealth Expert.

#### Scenario: Either engine drives the Expert's browser
- **GIVEN** an Expert set to stealth with example.com as its domain, the stealth browser and browser-use qualified, and a scripted model on a disposable stack
- **WHEN** a run browses with YOLO on, and browses again after YOLO is turned off and the call is approved
- **THEN** the first runs on browser-use and the second on Autobots' read-only loop, both on the stealth browser with each engine's own limits, and each tool row shows browser: stealth

### Requirement: No quiet fallback

While the stealth browser isn't qualified, a call of an Expert set to it SHALL be refused `stealth_browser_unqualified` before any container starts, and SHALL NOT run on another browser.

#### Scenario: No quiet fallback
- **GIVEN** an Expert set to stealth, the stealth browser not qualified, and the executor and browser-use qualified
- **WHEN** a run calls browse_goal with YOLO on, and again with YOLO off and the call approved
- **THEN** each call is refused with stealth_browser_unqualified before any container starts, and nothing runs on the box's browser

### Requirement: A changed user agent ends the call

On both browsers, a request whose user agent isn't the browser's own SHALL be refused before it leaves. A top-frame navigation under one SHALL end the call with `refused_action`.

#### Scenario: A changed user agent ends the call
- **GIVEN** a browse on browser-use of the qualification host, on the box's browser and on the stealth browser
- **WHEN** model-written code sets another user agent over CDP and then opens a page
- **THEN** the request is refused before it leaves, and the call ends refused_action with no further model call

### Requirement: Nothing is seeded with stealth

The concept seed SHALL create no Expert set to `stealth`.

#### Scenario: Nothing is seeded with stealth
- **GIVEN** a new workspace where browse_goal is available
- **WHEN** the concept seed runs
- **THEN** every seeded Expert reads as box, the Transcript reader included
