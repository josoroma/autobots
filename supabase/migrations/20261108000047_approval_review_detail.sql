-- US-15.15, PRD-Studio GH-06: what a reviewer approves beyond the arguments, such as each file's diff
-- against a base branch head. Bound to that head: if it moves, the connector stops with base_moved
-- and the request returns to pending with a diff against the new head (Decision 0022 D15).
alter table public.approval_requests add column review_detail jsonb
  check (review_detail is null or jsonb_typeof(review_detail) = 'object');
