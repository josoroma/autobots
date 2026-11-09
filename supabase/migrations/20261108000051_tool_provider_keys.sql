-- US-14.17, Decision 0024 K3 and PRD-Tool-Catalog PK-05: a workspace may save a Tavily or Jina key,
-- sealed like the OpenRouter key (MP-06). Ciphertext only, never plaintext, and direct server SQL only.
alter table app_private.provider_credentials
  drop constraint provider_credentials_provider_check,
  add constraint provider_credentials_provider_check
    check (provider in ('openrouter', 'tavily', 'jina'));

-- Each workspace's optimistic version for each tool key, so a stale save or removal is refused.
create table app_private.tool_key_settings (
  workspace_id uuid not null references public.workspaces (id),
  provider text not null check (provider in ('tavily', 'jina')),
  version integer not null default 0 check (version >= 0),
  primary key (workspace_id, provider)
);

revoke all on app_private.tool_key_settings from public, anon, authenticated;
grant select, insert, update on app_private.tool_key_settings to autobots_runtime;
