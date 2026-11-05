-- MP-06: encrypted application credentials, with direct server SQL only. Ciphertext, never plaintext.
create table app_private.provider_credentials (
  credential_id uuid not null,
  version integer not null check (version >= 1),
  workspace_id uuid not null references public.workspaces (id),
  provider text not null check (provider = 'openrouter'),
  ciphertext bytea not null,
  nonce bytea not null check (octet_length(nonce) = 12),
  tag bytea not null check (octet_length(tag) = 16),
  key_version integer not null check (key_version >= 1),
  status text not null check (status in ('active', 'superseded', 'deleted')),
  created_at timestamptz not null default now(),
  primary key (credential_id, version)
);

create unique index provider_credentials_one_active
  on app_private.provider_credentials (workspace_id, provider) where status = 'active';

-- Workspaces explicitly allowed to use the installation's environment key, MP-03.
create table app_private.installation_credential_grants (
  workspace_id uuid primary key references public.workspaces (id)
);

revoke all on all tables in schema app_private from public, anon, authenticated;
grant select, insert, update on app_private.provider_credentials to autobots_runtime;
grant select on app_private.installation_credential_grants to autobots_runtime;
