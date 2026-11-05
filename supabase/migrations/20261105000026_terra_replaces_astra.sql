-- Decision 0004: openai/gpt-6.1-terra replaces openai/gpt-6-astra as the second approved profile.
-- Recorded invocations keep their true model. A saved run's frozen policy isn't rewritten, so a run bound
-- to Astra stops instead of silently moving to another model. A workspace or role that chose Astra goes
-- back to the DeepSeek default rather than to a model nobody chose.
delete from public.model_profiles where profile_id = 'openrouter_astra';
alter table public.model_profiles drop constraint model_profiles_profile_id_check;
alter table public.model_profiles add constraint model_profiles_profile_id_check
  check (profile_id in ('openrouter_deepseek_flash', 'openrouter_terra'));

-- The row exists whether or not seeds run again, as readiness and settings read it.
insert into public.model_profiles (profile_id, canonical_id, wire_id, label, seed_version)
  values ('openrouter_terra', 'openai/gpt-6.1-terra-20261026', 'openai/gpt-6.1-terra', 'Terra', 1)
  on conflict (profile_id) do nothing;

update app_private.model_policies set default_profile = 'openrouter_deepseek_flash'
  where default_profile = 'openrouter_astra';
update app_private.model_policies p set role_overrides = (
    select coalesce(jsonb_object_agg(e.key, e.value), '{}'::jsonb)
    from jsonb_each(p.role_overrides) e where e.value <> '"openrouter_astra"'::jsonb
  )
  where p.role_overrides::text like '%openrouter_astra%';
alter table app_private.model_policies drop constraint model_policies_default_profile_check;
alter table app_private.model_policies add constraint model_policies_default_profile_check
  check (default_profile in ('openrouter_deepseek_flash', 'openrouter_terra'));

alter table app_private.model_invocations drop constraint model_invocations_profile_check;
alter table app_private.model_invocations add constraint model_invocations_profile_check
  check (profile in ('openrouter_deepseek_flash', 'openrouter_terra', 'openrouter_astra'));
