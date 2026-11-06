-- US-11.12: a late provider report settles an uncertain call too, so a reconciled charge records who
-- supplied it. Nullable, as a row from before this can't say, and the inspector says that instead.
alter table app_private.model_invocations
  add column charge_source text check (charge_source in ('provider', 'owner'));
