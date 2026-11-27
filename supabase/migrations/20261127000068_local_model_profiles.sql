-- US-23.1, Decision 0041 A2, A3 and A7: two local profiles served on this Mac by the owner's llama-server, Bonsai 2.5's Q2_0
-- and Inkling 2 Mini's UD-Q3_K_XL. Approved isn't offered: the application offers one only after its local route qualifies.
-- Locks: ACCESS EXCLUSIVE on public.model_profiles, app_private.model_policies and app_private.model_invocations while
--   each check is replaced and validated in one scan; the largest, model_invocations, holds one row per model call.
-- Data: none rewritten. Two model_profiles rows are inserted where absent.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
alter table public.model_profiles drop constraint model_profiles_profile_id_check;
alter table public.model_profiles add constraint model_profiles_profile_id_check
  check (profile_id in ('openrouter_deepseek_flash', 'openrouter_terra', 'openrouter_sol',
                        'local_bonsai_2_5_27b', 'local_inkling_2_mini'));

-- The rows exist whether or not seeds run again, as readiness and settings read them.
insert into public.model_profiles (profile_id, canonical_id, wire_id, label, seed_version) values
  ('local_bonsai_2_5_27b',
   'prism-ml/Ternary-Bonsai-2.5-27B-GGUF@28a7093cc25bc151cc2b284c5570f12ce343fdcf/Ternary-Bonsai-2.5-27B-Q2_0.gguf',
   'bonsai-2.5-27b-q2_0', 'Bonsai 2.5 (local)', 1),
  ('local_inkling_2_mini',
   'unsloth/Inkling-2-Mini-GGUF@8078d149286eec7193795413b9e0643da6d11fa1/Inkling-2-Mini-UD-Q3_K_XL.gguf',
   'inkling-2-mini-ud-q3_k_xl', 'Inkling 2 Mini (local)', 1)
  on conflict (profile_id) do nothing;

alter table app_private.model_policies drop constraint model_policies_default_profile_check;
alter table app_private.model_policies add constraint model_policies_default_profile_check
  check (default_profile in ('openrouter_deepseek_flash', 'openrouter_terra', 'openrouter_sol',
                             'local_bonsai_2_5_27b', 'local_inkling_2_mini'));

alter table app_private.model_invocations drop constraint model_invocations_profile_check;
alter table app_private.model_invocations add constraint model_invocations_profile_check
  check (profile in ('openrouter_deepseek_flash', 'openrouter_terra', 'openrouter_sol', 'openrouter_astra',
                     'local_bonsai_2_5_27b', 'local_inkling_2_mini'));
