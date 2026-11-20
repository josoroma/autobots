## ADDED Requirements

### Requirement: YOLO chooses the engine

A `browse_goal` call SHALL run on browser-use in the isolated executor, without approval, only while the call is YOLO and browser-use reports qualified. Otherwise it SHALL wait for approval when YOLO is off and run on Autobots' read-only loop.

#### Scenario: YOLO chooses the engine
- **GIVEN** an Expert granted browse_goal with its browse domains, and a run admitted with YOLO on
- **WHEN** the run makes a browse_goal call, and makes another after the owner turns YOLO off
- **THEN** the first runs on browser-use in the isolated executor without approval, and the second waits for approval and runs on Autobots' read-only loop

### Requirement: The contract is unchanged

A browse on browser-use SHALL take the same inputs and return the same output as one on the loop: a summary labelled third-party, visited URLs without query or fragment, steps, model calls and one of the same stop reasons. Every model call browser-use makes SHALL be one admitted call of the run through the browse's endpoint.

#### Scenario: The contract is unchanged
- **GIVEN** an Expert granted browse_goal, YOLO on and a scripted model
- **WHEN** it browses on browser-use from the qualification host https://example.com/ until the model reports done
- **THEN** the call takes the same inputs and starts without approval, every model call browser-use makes is one admitted call of the run through the endpoint, and it returns a summary labelled third-party, visited URLs without query or fragment, steps, model_calls and one of the same stop reasons

### Requirement: The domains and the box hold

Under browser-use, the egress proxy or Chromium's policy SHALL refuse a host outside the call's allowed domains and any download. A request a page makes on its own SHALL be counted and the browse SHALL continue. A navigation or download the model chose SHALL end the call with `refused_action`.

#### Scenario: The domains and the box hold
- **GIVEN** browser-use is driving the box's Chromium on an allowed domain
- **WHEN** a page or the model goes to a host outside the allowed domains, or starts a download
- **THEN** the egress proxy or Chromium's policy refuses it, a request the page makes on its own is counted and the browse continues, and a navigation or download the model chose ends the call with refused_action

### Requirement: Nothing reaches Browser Use's cloud

A browse on browser-use SHALL send nothing to Browser Use's gateway, cloud browser, telemetry or sync hosts.

#### Scenario: Nothing reaches Browser Use's cloud
- **GIVEN** a browse on browser-use on the run's frozen researcher route, driven by a scripted model through the endpoint
- **WHEN** it runs to the end
- **THEN** the proxy log shows no request to Browser Use's gateway, cloud browser, telemetry or sync hosts

### Requirement: Longer limits for browser-use only

A browse on browser-use SHALL run at most 40 steps and 600 seconds, by default 25 and 300, with a box cap of up to 600 seconds for its session only. A call on Autobots' loop SHALL run at most 20 steps and 300 seconds.

#### Scenario: Longer limits for browser-use only
- **GIVEN** a run admitted with YOLO on
- **WHEN** one browse_goal call on browser-use names no limits, another names 40 steps and 600 seconds, and after YOLO is turned off a call runs on Autobots' loop
- **THEN** the first runs with at most 25 steps and 300 seconds, the second with at most 40 steps and 600 seconds and a box cap of 600 seconds for its session only, and the loop's call runs at most 20 steps and 300 seconds

### Requirement: A refused model request ends the browse

When the endpoint refuses browser-use's model request with a typed reason, browser-use SHALL stop and `browse_goal` SHALL report that reason.

#### Scenario: A refused model request ends the browse
- **GIVEN** a browse on browser-use whose run's budget, model calls or time runs out, or whose run is cancelled
- **WHEN** browser-use sends its next request to the endpoint
- **THEN** the endpoint refuses it with a typed reason, browser-use stops, and browse_goal reports its stop reason

### Requirement: Qualified again for browser-use

The executor SHALL report browser-use qualified only from a passing live check, at the current browser-use image and sources, that observed every refusal it lists and found no key, cookie, host folder or credential in the container. Until then no call SHALL run on browser-use.

#### Scenario: Qualified again for browser-use
- **GIVEN** the executor's qualification check on a disposable stack with a scripted model, for the browser-use image built from the digest-pinned Playwright image with browser-use 1.0.6 from its own lock
- **WHEN** any refusal it lists is not observed or the container holds a key, cookie, host folder or credential, and then when every refusal is observed and the container holds none
- **THEN** the executor reports browser-use not qualified in the first case, with no call run on browser-use, and qualified only in the second
