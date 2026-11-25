## ADDED Requirements

### Requirement: Challenge hosts only as parts of a page

A stealth browse on browser-use SHALL be able to load parts of a page from the challenge hosts. A top-frame navigation to one SHALL be refused and end the call with `refused_action`.

#### Scenario: Challenge hosts only as parts of a page
- **GIVEN** a stealth browse on browser-use of example.com, with the challenge hosts arranged as example.org
- **WHEN** the page loads a frame and a script from example.org, and then model-written code goes to example.org as a page
- **THEN** the frame and the script reach it, and the navigation is refused and ends the call refused_action

### Requirement: The list is fixed, and only browser-use on stealth reaches it

The challenge hosts SHALL be a fixed list in code, and only a session of browser-use on the stealth browser SHALL reach them.

#### Scenario: The list is fixed, and only browser-use on stealth reaches it
- **GIVEN** the challenge hosts in code
- **WHEN** a session is prepared for browser-use on stealth, for the read-only loop on stealth, and for either engine on the box's browser
- **THEN** only the first may reach challenges.cloudflare.com, captcha-delivery.com, datadome.co and their subdomains, and no other host is added to any

### Requirement: A check that clears

A check that is the page itself SHALL have 20 seconds to clear by itself, while the model's next request waits before admission.

#### Scenario: A check that clears
- **GIVEN** a check that is the page itself and clears by itself within 20 seconds, and a scripted model
- **WHEN** a stealth browse on browser-use meets it
- **THEN** the model's next request waits until it clears, no model call is made and nothing is pressed meanwhile, and the browse continues

### Requirement: A check that stays

A check that is the page and doesn't clear in its time SHALL end the call with `bot_check`, with nothing solved or retried.

#### Scenario: A check that stays
- **GIVEN** a check that is the page itself and doesn't clear
- **WHEN** a stealth browse on browser-use meets it and 20 seconds pass
- **THEN** the call ends bot_check with no model call meanwhile, and nothing solved or retried it

### Requirement: A widget that needs nobody

A Turnstile frame on a page SHALL NOT be a check.

#### Scenario: A widget that needs nobody
- **GIVEN** a page whose content loads and which embeds a Turnstile frame
- **WHEN** a stealth browse on browser-use reads the page
- **THEN** the call continues

### Requirement: A check that asks a person

A reCAPTCHA, hCaptcha or Arkose frame SHALL end the call with `bot_check` at first sight.

#### Scenario: A check that asks a person
- **GIVEN** a page with a reCAPTCHA checkbox or challenge, an hCaptcha frame or an Arkose frame
- **WHEN** a stealth browse on browser-use meets it
- **THEN** the call ends bot_check at first sight

### Requirement: Nothing solves

Nothing SHALL solve a check. browser-use SHALL be told never to press or answer one, and its model SHALL see no image.

#### Scenario: Nothing solves
- **GIVEN** a stealth browse on browser-use that meets a check, and a scripted model
- **WHEN** the call ends
- **THEN** browser-use was told never to press or answer a check, no model request carried an image, and the proxy log shows no host but the call's domains and the challenge hosts

### Requirement: The box's browser is unchanged

The box's browser SHALL keep its rule: any check ends the call at first sight, and the challenge hosts stay refused.

#### Scenario: The box's browser is unchanged
- **GIVEN** an Expert set to box and a browse on browser-use
- **WHEN** it meets a Turnstile frame, a Cloudflare challenge on the site's own host or a DataDome frame
- **THEN** the call ends bot_check at first sight, and the challenge hosts stay refused
