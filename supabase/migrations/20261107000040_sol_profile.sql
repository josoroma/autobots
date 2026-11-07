-- US-14.15, Decision 0019 S1 and S2: openai/gpt-6.1-sol is a third approved profile. Approved isn't
-- offered: the application offers it for new runs only after its route is qualified, which a later
-- migration records with its date and limits.
alter table public.model_profiles drop constraint model_profiles_profile_id_check;
alter table public.model_profiles add constraint model_profiles_profile_id_check
  check (profile_id in ('openrouter_deepseek_flash', 'openrouter_terra', 'openrouter_sol'));

-- The row exists whether or not seeds run again, as readiness and settings read it.
insert into public.model_profiles (profile_id, canonical_id, wire_id, label, seed_version)
  values ('openrouter_sol', 'openai/gpt-6.1-sol-20260929', 'openai/gpt-6.1-sol', 'Sol', 1)
  on conflict (profile_id) do nothing;

alter table app_private.model_policies drop constraint model_policies_default_profile_check;
alter table app_private.model_policies add constraint model_policies_default_profile_check
  check (default_profile in ('openrouter_deepseek_flash', 'openrouter_terra', 'openrouter_sol'));

alter table app_private.model_invocations drop constraint model_invocations_profile_check;
alter table app_private.model_invocations add constraint model_invocations_profile_check
  check (profile in ('openrouter_deepseek_flash', 'openrouter_terra', 'openrouter_sol', 'openrouter_astra'));
