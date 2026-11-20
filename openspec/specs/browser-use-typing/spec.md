# browser-use-typing Specification

## Purpose
TBD - created by archiving change us-17-4-pressing-typing-submitting-under. Update Purpose after archive.

## Requirements

### Requirement: Types and submits within the allowed domains

While a call is YOLO, browser-use SHALL be able to type, click and submit by `GET` or `POST` on the call's domains, and the run SHALL record each submit's domain and path without the typed values or the query.

#### Scenario: Types and submits within the allowed domains
- **GIVEN** YOLO on, and a browse_goal call on browser-use within its Expert's domains
- **WHEN** its task needs a form typed into and submitted
- **THEN** it types, clicks and submits on those domains, and the run records each submit's domain and path, without the typed values or the query

### Requirement: Leaving the domains ends the call

A click or submit that leads outside the call's domains SHALL be refused by the egress proxy and SHALL end the call with `refused_action`.

#### Scenario: Leaving the domains ends the call
- **GIVEN** the same call
- **WHEN** a click or a submit leads to a host outside the allowed domains
- **THEN** the egress proxy refuses it and the call stops with refused_action

### Requirement: Nothing to sign in or pay with

The box SHALL hold no key, password, cookie or card, Chromium SHALL refuse downloads, and a file chooser SHALL offer no host file.

#### Scenario: Nothing to sign in or pay with
- **GIVEN** any browse on browser-use
- **WHEN** it runs
- **THEN** the box holds no key, password, cookie or card, Chromium refuses downloads, and a file chooser offers no host file

### Requirement: A bot check stops the call

A bot check or CAPTCHA, recognised from the page itself, SHALL end the call with `bot_check`, and nothing SHALL try to solve it, hide from it or retry around it.

#### Scenario: A bot check stops the call
- **GIVEN** a site answers with a bot check or a CAPTCHA
- **WHEN** browser-use meets it
- **THEN** nothing tries to solve it, hide from it or retry around it, and the call stops with bot_check

### Requirement: What it saw is kept

Each browser-use step under YOLO SHALL keep one screenshot in the run's private storage, and the run's tool row SHALL show them with each submit's domain and path.

#### Scenario: What it saw is kept
- **GIVEN** a browse on browser-use under YOLO
- **WHEN** it finishes, however it stops
- **THEN** each of its steps has one screenshot kept in the run's private storage, and the run's tool row shows them with each submit's domain and path

### Requirement: A typed result

A call that names an output schema SHALL return a result valid against it, whose declared link fields keep their query while visited URLs stay bare, or SHALL stop with `invalid_action`.

#### Scenario: A typed result
- **GIVEN** the call names an output schema
- **WHEN** browser-use finishes
- **THEN** the output carries a result valid against that schema whose declared link fields keep their query while visited URLs stay bare, or the call stops with invalid_action
