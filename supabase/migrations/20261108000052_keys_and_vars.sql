-- US-14.18, Decision 0025 V2 and V4 and PRD-Tool-Catalog PK-07: Settings → Keys & vars. A workspace
-- may also save the GitHub token, sealed like the other keys, and two values that aren't secret: the
-- GitHub repository and the browsing switch. Direct server SQL only.
alter table app_private.provider_credentials
  drop constraint provider_credentials_provider_check,
  add constraint provider_credentials_provider_check
    check (provider in ('openrouter', 'tavily', 'jina', 'github'));

-- Each item keeps its optimistic version here. A value's current setting lives beside it, checked by
-- the database too, while a secret's row never holds anything but its version.
alter table app_private.tool_key_settings
  drop constraint tool_key_settings_provider_check,
  add constraint tool_key_settings_provider_check
    check (provider in ('tavily', 'jina', 'github_token', 'github_repository', 'browser_executor')),
  add column value text,
  add constraint tool_key_settings_value_check check (
    value is null
    or (provider = 'github_repository' and value ~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
    or (provider = 'browser_executor' and value in ('enabled', 'disabled'))
  );
