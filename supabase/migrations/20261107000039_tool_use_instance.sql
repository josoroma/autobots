-- US-14.4, PRD-Tool-Catalog TV-02: a workflow's nodes share their execution's run, so a use
-- records the node instance that made it, for the monitor to show it under that node.
alter table app_private.tool_uses
  add column instance_key text check (instance_key is null or char_length(instance_key) between 1 and 200);
