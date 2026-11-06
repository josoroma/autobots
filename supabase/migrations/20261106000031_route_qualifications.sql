-- US-11.1, finding B6: what each route's own live qualification found. Separate from authentication and the
-- catalog, so neither can be mistaken for it. A route with no row reads as not qualified. A later round adds
-- its result by migration, with its date and limits, once that round has actually run.
create table agent_runtime.route_qualifications (
  profile text primary key,
  canonical_id text not null,
  status text not null check (status in ('qualified_with_limits', 'not_qualified')),
  qualified_on date not null,
  configuration text not null,
  limits text not null,
  evidence text not null
);

revoke all on agent_runtime.route_qualifications from public, anon, authenticated;
grant select on agent_runtime.route_qualifications to autobots_runtime;

-- From docs/engineering/evidence/US-3.4/summary.md#outcome and Decisions 0004 and 0005.
insert into agent_runtime.route_qualifications (profile, canonical_id, status, qualified_on, configuration, limits, evidence) values
  ('openrouter_deepseek_flash', 'deepseek/deepseek-v4.1-flash-20261017', 'qualified_with_limits', '2026-11-05',
   'Requested as deepseek/deepseek-v4.1-flash-1017. Required parameters on, no fallbacks, no retries, 512 output tokens. langchain-openrouter 0.2.9, openrouter 0.11.46.',
   'Strict nested output is unsupported and stays disabled. A refusal appears only in the text. Cancellation stopped our side, and whether the provider stopped and what it charged are unknown. The upstream provider was not reported. Real fragmentation of streamed tool arguments was covered only by a fake transport. Three trials per fixture on one day, which says nothing about task quality.',
   'US-3.4'),
  ('openrouter_terra', 'openai/gpt-6.1-terra-20261026', 'qualified_with_limits', '2026-11-05',
   'Requested as openai/gpt-6.1-terra. Required parameters on, no fallbacks, no retries, 512 output tokens. langchain-openrouter 0.2.9, openrouter 0.11.46.',
   'Strict nested output passes only with closed objects. A refusal appears only in the text. Cancellation stopped our side, and whether the provider stopped and what it charged are unknown. The upstream provider was not reported. Three trials per fixture on one day, which says nothing about task quality.',
   'US-3.4');
