-- Review round 1, M21, M27 and M32. The monitor can name the node in progress, memory can belong to an
-- Expert, and a first promotion can be undone by pointing at no version.
alter table public.workflow_executions add column current_instance text;
grant update (current_instance) on public.workflow_executions to autobots_runtime;

alter table public.memory_items add column expert_id uuid references public.experts (id);
grant select (expert_id) on public.memory_items to authenticated;
create index memory_items_expert on public.memory_items (expert_id) where expert_id is not null;

alter table public.knowledge_heads alter column active_version drop not null;
