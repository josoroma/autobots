-- R-56 (SQLI-12): Sol's route states the limit the other two routes already state (migration 34):
-- concurrent admission on a live route wasn't tested. US-14.15 and US-16.4 qualified Sol with US-3.4's
-- runner and suite, which list what they exercised without concurrent admission, and US-3.4's summary
-- says the runner never touched PRD-Model-Providers MP-A09. Stating a limit claims no qualification.
-- Locks: ROW EXCLUSIVE on agent_runtime.route_qualifications while one row is updated; three rows in all,
-- so milliseconds.
-- Data: appends one sentence to Sol's limits, only where the row exists and lacks it.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
update agent_runtime.route_qualifications
  set limits = limits || ' Concurrent admission on a live route wasn''t tested.'
  where profile = 'openrouter_sol'
    and position('Concurrent admission on a live route wasn''t tested.' in limits) = 0;
