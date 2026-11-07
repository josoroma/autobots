-- US-14.15, Decision 0019 S4: Sol's route was qualified live on 2026-11-07, 39 calls under a US$1.20
-- cap, with US-3.4's runner and suite. What it found, for Settings to show beside the others.
insert into agent_runtime.route_qualifications (profile, canonical_id, status, qualified_on, configuration, limits, evidence) values
  ('openrouter_sol', 'openai/gpt-6.1-sol-20260929', 'qualified_with_limits', '2026-11-07',
   'Requested as openai/gpt-6.1-sol. Required parameters on, no fallbacks, no retries, 512 output tokens. langchain-openrouter 0.2.9, openrouter 0.11.46.',
   'Strict nested output is unsupported and stays disabled. A refusal appears only in the text. Cancellation stopped our side, and whether the provider stopped and what it charged are unknown. The upstream provider was not reported. Three trials per fixture on one day, which says nothing about task quality.',
   'US-14.15')
on conflict (profile) do nothing;
