# model-source Specification

## Purpose
A workspace's Model source, OpenRouter or Local, which decides where every model call of a new run goes, never mixed and never as a fallback (Decision 0041 A1, A7, A8, A10 to A13; US-23.3).

## Requirements

### Requirement: OpenRouter is the default
Every new and existing workspace SHALL be on OpenRouter until its owner switches, with its saved default and role overrides as they were, and every role resolving as MP-01 says.

#### Scenario: OpenRouter is the default, as today
- **GIVEN** a new workspace, and one that existed before the change with a saved default and role overrides
- **WHEN** their model policies are shown and a run is admitted in each
- **THEN** Model source is OpenRouter in both, the saved choices are as they were, every role resolves as MP-01 says today with researcher on Sol, and no picker lists a local profile

### Requirement: Switching to Local needs offered profiles for the roles
A switch to Local SHALL be refused, naming the roles that have no offered local profile, until offered local profiles cover `executor`, and also `researcher` while any Expert grants `browse_goal`.

#### Scenario: Local can't be chosen before offered profiles cover the roles
- **GIVEN** no offered local profile, a workspace with an Expert that grants browse_goal, and a workspace with none
- **WHEN** the owner of each switches Model source to Local
- **THEN** each switch is refused with the roles that have no offered local profile, executor and researcher in the first and executor in the second, and both stay on OpenRouter

### Requirement: Only an owner switches, at the version they saw
Only the workspace's owner SHALL switch Model source (MP-05), and a switch at a stale settings version SHALL be refused as a conflict.

#### Scenario: Only an owner or admin switches
- **GIVEN** Bonsai 2.5 offered, a member who isn't an owner or admin, and an owner holding a stale settings version
- **WHEN** each switches Model source to Local
- **THEN** the member is refused as forbidden, the stale switch is refused as a conflict, and the source stays OpenRouter

### Requirement: On Local every role is on one local profile
On Local, every role SHALL resolve to the Local default profile, a run SHALL freeze that route, pickers SHALL list offered local profiles only, saving a workspace role override SHALL be refused, and a run that names a role override SHALL be refused `model_not_offered`.

#### Scenario: On Local every role is on one local profile
- **GIVEN** Bonsai 2.5 offered, and the owner has switched Model source to Local
- **WHEN** the model policy is shown and a run is admitted
- **THEN** every role resolves to Bonsai 2.5's profile, the run freezes the Local source with its route, every picker lists offered local profiles only, saving a workspace role override is refused, and a run that names a role override is refused model_not_offered

### Requirement: Limits follow the route
A run's call time, active time and output cap SHALL follow its frozen executor route, from Decision 0041's measurements table for a local route and Decision 0034 for OpenRouter.

#### Scenario: Limits follow the local route
- **GIVEN** Bonsai 2.5 offered, one run admitted on Local and one admitted on OpenRouter
- **WHEN** their frozen limits are read
- **THEN** the Local run's are 64K context, 4,096 output tokens with thinking off, 1,800 seconds a call, 240 active minutes, 64 model calls and 96 tool dispatches, and the OpenRouter run keeps 300 seconds a call and 45 active minutes

### Requirement: Local sends nothing to OpenRouter
On Local, no OpenRouter key SHALL be read and nothing SHALL be sent to OpenRouter, its catalog included, and the disclosure SHALL say so.

#### Scenario: Local sends nothing to OpenRouter
- **GIVEN** Model source is Local, no OpenRouter key set, a fake local server serving Bonsai 2.5's pinned model ID, and a fake OpenRouter transport that fails if it is touched
- **WHEN** the composer is opened and a run runs to the end
- **THEN** the disclosure said nothing goes to OpenRouter and that tool calls still leave the Mac, every model call went to the local server reserving US$0, no key was read, and no request reached OpenRouter, its catalog included

### Requirement: The browser box's model calls follow the source
On Local, the admitted endpoint SHALL answer browser-use on the run's frozen local `researcher` route, and still refuse an image the route isn't qualified for.

#### Scenario: The browser box's model calls follow the source
- **GIVEN** Model source is Local, and an offered local profile covers the researcher role
- **WHEN** a run's browse_goal starts browser-use in the box and it sends a chat completion to the admitted endpoint, and then one carrying an image
- **THEN** the first call is admitted on the run's frozen local researcher route, answered by the local runtime, reserves US$0, and nothing reaches OpenRouter, and the second is refused content_not_qualified before anything is sent

### Requirement: A run on a switched-off source waits
A model call whose frozen route is on the source switched off SHALL be refused `model_source_disabled` before anything is sent to either source, and the run SHALL wait with that reason.

#### Scenario: A run on a switched-off source waits
- **GIVEN** Bonsai 2.5 offered, and a run admitted on an OpenRouter route waiting for an approval
- **WHEN** the owner switches Model source to Local and approves, and then switches back, cancels the run or continues it as a linked new run
- **THEN** its next model call is refused model_source_disabled before anything is sent to either source, the run waits with that reason, after the switch back its call goes to OpenRouter on its frozen route, a cancel ends it, and the linked new run is admitted on Local

### Requirement: Saved choices are kept per source
Switching to Local and back SHALL leave the OpenRouter default and role overrides as they were.

#### Scenario: Switching back restores saved choices
- **GIVEN** a default and role overrides saved under OpenRouter, and Bonsai 2.5 offered
- **WHEN** the owner switches to Local and back to OpenRouter
- **THEN** the OpenRouter default and role overrides are as they were

### Requirement: The Model source panel
Settings → Models SHALL show a Model source panel above the provider panel and the model policy, with what Decision 0041 A13 lists.

#### Scenario: The Model source panel
- **GIVEN** Bonsai 2.5 offered with no matched run, Inkling 2 Mini not offered, and a fake local server serving Bonsai 2.5's model ID
- **WHEN** the owner opens Settings → Models
- **THEN** a Model source panel sits above the provider panel and the model policy, and shows each local profile as offered or not with the reason, the runs it has matched, the runtime's health with the model ID it serves and whether the pinned SHA-256 matches, the roles it covers, and "US$0.00 per model call" with a note that tool calls such as SerpApi, Jina and YouTube still leave the Mac

### Requirement: Home shows the local model's health
On Local, Home's model service SHALL read from the runtime's health check, with no request to OpenRouter.

#### Scenario: Home shows the local model's health
- **GIVEN** Model source is Local
- **WHEN** a member opens Home while a fake local server serves Bonsai 2.5's model ID, and again with nothing on its port
- **THEN** the service chip reads "Local model ready" the first time and says the local model isn't running the second, from the runtime's health check, and no request reaches OpenRouter
