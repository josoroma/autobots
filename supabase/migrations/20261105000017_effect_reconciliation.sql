-- SP-012: an unknown outcome is resolved from the destination or operator evidence, and recorded.
alter table app_private.tool_receipts
  add column can_readback boolean not null default false,
  add column evidence text,
  add column reconciled_by uuid,
  add column reconciled_at timestamptz;
