-- US-11.7: why policy is asking, and what the action touches, written by the server with the request.
-- Nullable, as a request saved before this has neither, and the inbox says so instead of guessing.
alter table public.approval_requests
  add column policy_reason text,
  add column resource_target text;
