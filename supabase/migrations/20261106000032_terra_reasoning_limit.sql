-- What US-11.2's live trial found on Terra, added to that route's stored limits, so Settings says it too.
update agent_runtime.route_qualifications
  set limits = limits || ' Across a tool call, the pinned SDK removes the encrypted reasoning item''s id: in all 3 live trials that returned metadata, on 2026-11-06, though each continuation still worked. LC-23 is partial here.'
  where profile = 'openrouter_terra';
