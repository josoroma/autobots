-- MP-04 and MP-05: versioned provider settings and workspace model policy, for optimistic concurrency.
create table app_private.provider_settings (
  workspace_id uuid primary key references public.workspaces (id),
  version integer not null default 0 check (version >= 0),
  auth_status text not null default 'missing'
    check (auth_status in ('missing', 'configured', 'invalid', 'unavailable')),
  validated_at timestamptz
);

create table app_private.model_policies (
  workspace_id uuid primary key references public.workspaces (id),
  version integer not null check (version >= 1),
  default_profile text not null check (default_profile in ('openrouter_deepseek_flash', 'openrouter_astra')),
  role_overrides jsonb not null default '{}'::jsonb
);

revoke all on app_private.provider_settings, app_private.model_policies from public, anon, authenticated;
grant select, insert, update on app_private.provider_settings, app_private.model_policies to autobots_runtime;
