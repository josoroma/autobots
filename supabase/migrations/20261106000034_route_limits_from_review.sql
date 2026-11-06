-- US-11.12's review: two limits the stored qualification left out. Both are in the evidence it cites.
update agent_runtime.route_qualifications
  set limits = limits || ' Concurrent admission on a live route wasn''t tested.';
update agent_runtime.route_qualifications
  set limits = limits || ' One real goal, repeated on disposable stacks at this limit, went 0 of 5.'
  where profile = 'openrouter_deepseek_flash';
update agent_runtime.route_qualifications
  set limits = limits || ' One real goal, repeated on disposable stacks at this limit, went 5 of 5.'
  where profile = 'openrouter_terra';
