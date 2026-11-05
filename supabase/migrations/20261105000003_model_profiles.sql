-- Reference rows for the two approved profiles, and a data-preserving run column. An expanding change.
create table public.model_profiles (
  profile_id text primary key check (profile_id in ('openrouter_deepseek_flash', 'openrouter_astra')),
  canonical_id text not null,
  wire_id text not null,
  label text not null,
  seed_version integer not null check (seed_version >= 1)
);

alter table public.model_profiles enable row level security;
revoke all on public.model_profiles from public, anon, authenticated;
grant select on public.model_profiles to authenticated;
grant select on public.model_profiles to autobots_runtime;
grant update (label) on public.model_profiles to autobots_runtime;
create policy read_profiles on public.model_profiles for select to authenticated, autobots_runtime using (true);
create policy runtime_label on public.model_profiles for update to autobots_runtime using (true) with check (true);

alter table public.runs add column goal_summary text not null default '';
grant select (goal_summary) on public.runs to authenticated;
