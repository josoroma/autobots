-- Why a tool refused, so a stopped run can be diagnosed afterwards. A code and a category, never what
-- the model wrote. Nullable, as earlier receipts have neither and most receipts never fail. Adding
-- nullable columns with no default takes a brief lock and rewrites nothing.
alter table app_private.tool_receipts
  add column failure_code text,
  add column failure_detail text;
