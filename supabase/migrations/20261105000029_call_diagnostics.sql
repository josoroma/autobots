-- What a provider reply said about itself, so a stopped run can be diagnosed afterwards. No message
-- content. Nullable, as earlier calls have none of this and a failed call has no reply. Adding nullable
-- columns with no default takes a brief lock and rewrites nothing.
alter table app_private.model_invocations
  add column finish_reason text,
  add column input_tokens integer,
  add column output_tokens integer,
  add column reasoning_tokens integer,
  add column tool_names text[],
  add column invalid_tool_calls integer;
