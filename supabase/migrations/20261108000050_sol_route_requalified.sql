-- US-16.4, Decision 0023 E5: Sol's route qualified live again on 2026-11-08, 39 calls with US-3.4's
-- runner and suite, in the same ledger and under the same US$1.20 cap as 2026-11-07 (US$0.28 committed
-- across both days). The findings matched the first pass. Settings shows the newer date.
update agent_runtime.route_qualifications
set qualified_on = '2026-11-08',
    configuration = 'Requested as openai/gpt-6.1-sol. Required parameters on, no fallbacks, no retries, 512 output tokens. langchain-openrouter 0.2.9, openrouter 0.11.46.',
    limits = 'Strict nested output is unsupported and stays disabled. A refusal appears only in the text. Cancellation stopped our side, and whether the provider stopped and what it charged are unknown. The upstream provider was not reported. Three trials per fixture on each of two days, 2026-11-07 and 2026-11-08, with the same results, which says nothing about task quality.',
    evidence = 'US-14.15, US-16.4'
where profile = 'openrouter_sol' and canonical_id = 'openai/gpt-6.1-sol-20260929';
