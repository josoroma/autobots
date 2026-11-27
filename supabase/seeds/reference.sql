-- Required reference data, SP-006. Repeatable: a newer seed_version updates identity fields, and a label a user edited stays.
insert into public.model_profiles (profile_id, canonical_id, wire_id, label, seed_version) values
  ('openrouter_deepseek_flash', 'deepseek/deepseek-v4.1-flash-20261017', 'deepseek/deepseek-v4.1-flash-1017', 'DeepSeek Flash', 1),
  ('openrouter_terra', 'openai/gpt-6.1-terra-20261026', 'openai/gpt-6.1-terra', 'Terra', 1),
  ('openrouter_sol', 'openai/gpt-6.1-sol-20260929', 'openai/gpt-6.1-sol', 'Sol', 1),
  ('local_bonsai_2_5_27b',
   'prism-ml/Ternary-Bonsai-2.5-27B-GGUF@28a7093cc25bc151cc2b284c5570f12ce343fdcf/Ternary-Bonsai-2.5-27B-Q2_0.gguf',
   'bonsai-2.5-27b-q2_0', 'Bonsai 2.5 (local)', 1),
  ('local_inkling_2_mini',
   'unsloth/Inkling-2-Mini-GGUF@8078d149286eec7193795413b9e0643da6d11fa1/Inkling-2-Mini-UD-Q3_K_XL.gguf',
   'inkling-2-mini-ud-q3_k_xl', 'Inkling 2 Mini (local)', 1)
on conflict (profile_id) do update set
  canonical_id = excluded.canonical_id,
  wire_id = excluded.wire_id,
  seed_version = excluded.seed_version
where public.model_profiles.seed_version < excluded.seed_version;
