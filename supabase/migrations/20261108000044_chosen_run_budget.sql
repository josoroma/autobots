-- US-15.9, Decision 0022 D11: a run's chosen budget, US$0.25 to US$5.00 with US$1.00 by default,
-- is frozen as its limit, and admission reserves against the lower of that and this ceiling.
-- The ceiling was US$1.00, which would have cut every chosen budget above it, so it becomes the
-- highest budget D11 allows. No screen or command sets it, so a row still at the old default
-- was never configured. The run's own limit, US$1.00 unless chosen, stays the effective cap.
alter table app_private.model_spend_limits alter column run_limit_micro_usd set default 5000000;
update app_private.model_spend_limits set run_limit_micro_usd = 5000000 where run_limit_micro_usd = 1000000;
