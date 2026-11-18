-- US-14.22, Decision 0032 G7 and PRD-Tool-Catalog GS-04: the SerpApi key for google_search is a Keys & vars
-- secret, sealed like the Tavily and Jina keys, so both provider lists gain serpapi. Direct server SQL only.
-- Locks: ACCESS EXCLUSIVE on app_private.provider_credentials and app_private.tool_key_settings while each CHECK
-- is replaced and its rows revalidated; a few rows per workspace, so milliseconds.
-- Data: none. No row is rewritten; existing rows already satisfy the wider lists.
-- Recovery: it applies in one transaction with its history row, so a failure leaves both constraints as they
-- were; apply it again.
alter table app_private.provider_credentials
  drop constraint provider_credentials_provider_check,
  add constraint provider_credentials_provider_check
    check (provider in ('openrouter', 'tavily', 'jina', 'github', 'serpapi'));

alter table app_private.tool_key_settings
  drop constraint tool_key_settings_provider_check,
  add constraint tool_key_settings_provider_check
    check (provider in ('tavily', 'jina', 'serpapi', 'github_token', 'github_repository', 'browser_executor'));
