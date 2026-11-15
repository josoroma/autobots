-- R-56 (SQLI-17): SQL's one statement of the terminal run states, in which a run never resumes
-- (option-b-contract.md SP-010). A new migration calls it instead of restating the list, and
-- services/agent/tests/test_run_terminal_predicate.py pins it to domain/runs.py's TERMINAL. Function
-- bodies written before it keep their own copies until a migration replaces them.
-- Locks: none on any table; it adds one function to the catalog.
-- Data: none.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
create function app_private.run_is_terminal(status text) returns boolean
  language sql immutable parallel safe set search_path = ''
  as $$ select status in ('succeeded', 'failed', 'cancelled') $$;

revoke all on function app_private.run_is_terminal(text) from public, anon, authenticated;
grant execute on function app_private.run_is_terminal(text) to autobots_runtime;
