-- R-56 (SQLI-13), Decision 0029 F3: a saved draft's graph is an object holding nodes and links arrays,
-- whichever path wrote it. An owner may still write a draft through PostgREST (US-15.12#1), so the API
-- also reads a draft that fails WorkflowGraph as absent rather than failing (application/workflows.py).
-- `is true` makes a missing key fail the check, where a bare comparison with null would pass it.
-- It is added NOT VALID, so every new write is checked at once; migration 61 validates the existing rows.
-- Locks: ACCESS EXCLUSIVE on public.workflow_drafts for the catalog change only, milliseconds whatever its
-- size, since NOT VALID reads no row.
-- Data: none.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
alter table public.workflow_drafts add constraint workflow_drafts_graph_shape
  check ((jsonb_typeof(graph) = 'object' and jsonb_typeof(graph -> 'nodes') = 'array'
          and jsonb_typeof(graph -> 'links') = 'array') is true) not valid;
