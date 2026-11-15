-- R-50 (PTOL-06), Decisions 0018 B6 and 0020 L5: an approval that releases a call leaving no receipt,
-- such as browse_goal's, is consumed in the releasing transaction, so the same call again waits for a
-- person (SP-013). Consuming is not a status: the request stays approved until it returns to review.
-- The column stays private, as authenticated's column grants on the table don't name it.
-- Locks: ACCESS EXCLUSIVE on public.approval_requests for the catalog change only; a nullable column with
-- no default rewrites and scans nothing, so it holds for milliseconds whatever the table's size.
-- Data: none. Existing requests read as never consumed.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
alter table public.approval_requests add column consumed_at timestamptz;
