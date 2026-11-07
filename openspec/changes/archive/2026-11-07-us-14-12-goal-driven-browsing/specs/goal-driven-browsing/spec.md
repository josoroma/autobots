## ADDED Requirements

### Requirement: A read-only browse is summarised and recorded

`browse_goal` SHALL browse read-only from its start URL within its allowed domains through the qualified executor and the admitted browsing loop, and SHALL return a third-party summary cut to the shared text budget, visited URLs without query or fragment, steps, model calls and why it stopped. It SHALL be recorded as one metered tool use with public fields only.

#### Scenario: A read-only browse is summarised and recorded
- **GIVEN** a qualified executor and the admitted browser model on a disposable stack, a scripted model, an Expert granting browse_goal and an approved call
- **WHEN** it browses from the qualification host https://example.com/ with allowed_domains example.com until the model reports done
- **THEN** it returns a summary labelled third-party and cut to the shared text budget, visited URLs without query or fragment, steps, model_calls and stopped set to done, and one metered tool use records only start_url, allowed_domains, max_steps, stopped, steps and the count of visited URLs, with each step counted as the run's model spend

### Requirement: Refusals and limits end the call

A navigation outside `allowed_domains`, a typing or submission attempt, or a navigation the browser refuses SHALL end the call at once with `refused_action`. An answer that isn't one valid action SHALL end it with `invalid_action`. Reaching `max_steps` or `max_seconds` SHALL stop it with that value. The output SHALL keep the summary so far and the URLs visited.

#### Scenario: Outside its domains, a submission, an invalid answer and its limits
- **GIVEN** an approved browse_goal call on the same disposable stack with a scripted model
- **WHEN** the model navigates outside allowed_domains, attempts typing or a form submission, answers with something other than one valid action, or runs past max_steps or max_seconds
- **THEN** a refused navigation or submission ends the call at once with stopped set to refused_action, nothing is submitted and no further step is taken, a submission that gets past the action set is refused by the egress proxy and ends the call the same way, an answer that isn't one valid action ends the call with stopped set to invalid_action, the output keeps the summary so far and the URLs visited, and reaching max_steps or max_seconds stops the call with stopped set to max_steps or max_seconds

### Requirement: Granted only through an Expert, approved on every call

`browse_goal` SHALL be grantable only through an Expert, and every call SHALL wait for a person's approval showing its task, start URL, allowed domains and limits, with no container started and no model call made before approval.

#### Scenario: Granted only through an Expert, approved on every call
- **GIVEN** a run that grants browse_goal other than through an Expert, and a run whose Expert grants it
- **WHEN** each proposes a browse_goal call
- **THEN** the first is refused with a typed code, and the second waits for a person's approval showing the task, start_url, allowed_domains and limits, with no container started and no model call made until it is approved

### Requirement: Disabled while unqualified

While the executor isn't qualified, `browse_goal` SHALL read `disabled_by_policy` with its repair and provider `autobots`, SHALL NOT be registered, and a grant naming it SHALL be refused with a typed code. The catalog's providers SHALL be only those TC-03 lists.

#### Scenario: Stays disabled while unqualified
- **GIVEN** the executor reports not qualified, or the admitted browser model is absent
- **WHEN** the catalog is read or a grant names browse_goal
- **THEN** browse_goal reads disabled_by_policy with its repair and provider autobots, it isn't registered, the grant is refused with a typed code, and the catalog's providers are only those TC-03 lists
