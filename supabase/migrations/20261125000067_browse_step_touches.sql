-- US-20.3, Decision 0038 Z11: what each step of a stealth browse pressed or typed into, as the action, the element's kind and
-- its label, never the typed value. Earlier rows and the box's browses have none. Direct server SQL only, as the table was.
-- Locks: an ACCESS EXCLUSIVE lock on `app_private.browse_steps` while one scan validates the new check, under a second on the
--   largest table, which holds at most 100 rows a browse. The constant default rewrites no row.
-- Data: none rewritten.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
alter table app_private.browse_steps
  add column touched jsonb not null default '[]'::jsonb check (jsonb_typeof(touched) = 'array');
