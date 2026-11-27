-- US-23.3, Decision 0041 A1 and A8: each workspace's Model source, OpenRouter or Local, and the Local default profile that
-- answers every role on Local. default_profile and role_overrides stay OpenRouter's, kept while Local is on, so switching back
-- restores them. A workspace with no row, and every row that exists, reads as OpenRouter.
-- Locks: ACCESS EXCLUSIVE on app_private.model_policies while two columns with constant defaults and their checks are added;
--   one row per workspace, so milliseconds.
-- Data: none rewritten. Existing rows read model_source 'openrouter' and local_profile null from the defaults.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
alter table app_private.model_policies
  add column model_source text not null default 'openrouter'
    constraint model_policies_model_source_check check (model_source in ('openrouter', 'local')),
  add column local_profile text
    constraint model_policies_local_profile_check check (local_profile in ('local_bonsai_2_5_27b', 'local_inkling_2_mini'));
