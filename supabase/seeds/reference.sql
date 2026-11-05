-- Required reference data, SP-006. Repeatable: a newer seed_version updates identity fields, and a label a user edited stays.
insert into public.model_profiles (profile_id, canonical_id, wire_id, label, seed_version) values
  ('openrouter_deepseek_flash', 'deepseek/deepseek-v4.1-flash-20261017', 'deepseek/deepseek-v4.1-flash-1017', 'DeepSeek Flash', 1),
  ('openrouter_terra', 'openai/gpt-6.1-terra-20261026', 'openai/gpt-6.1-terra', 'Terra', 1)
on conflict (profile_id) do update set
  canonical_id = excluded.canonical_id,
  wire_id = excluded.wire_id,
  seed_version = excluded.seed_version
where public.model_profiles.seed_version < excluded.seed_version;
