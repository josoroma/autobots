-- SP-018 and LM-07: worker liveness, and retention that never removes a receipt or another workspace's data.
create table app_private.worker_heartbeats (
  worker_id text primary key check (char_length(worker_id) between 1 and 200),
  state text not null check (state in ('running', 'draining', 'stopped')),
  claims_inference boolean not null,
  started_at timestamptz not null default now(),
  beat_at timestamptz not null default now()
);

-- No row, or a null window, keeps everything. Idempotency keys outlive run content, per SP-014.
create table app_private.workspace_retention (
  workspace_id uuid primary key references public.workspaces (id),
  run_days integer check (run_days >= 1),
  receipt_days integer check (receipt_days >= 1),
  updated_by uuid not null,
  updated_at timestamptz not null default now(),
  check (run_days is null or receipt_days is null or receipt_days >= run_days)
);

create table app_private.retention_log (
  id bigint generated always as identity primary key,
  workspace_id uuid not null references public.workspaces (id),
  run_id uuid,
  action text not null,
  detail jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now()
);

alter table public.runs add column content_purged_at timestamptz;
grant select (content_purged_at) on public.runs to authenticated;

alter table public.artifacts drop constraint artifacts_status_check;
alter table public.artifacts add constraint artifacts_status_check
  check (status in ('staged', 'published', 'failed', 'missing', 'expired'));
alter table public.artifacts add column bytes_removed_at timestamptz;

revoke all on app_private.worker_heartbeats, app_private.workspace_retention, app_private.retention_log
  from public, anon, authenticated;
grant select, insert, update on app_private.worker_heartbeats, app_private.workspace_retention
  to autobots_runtime;
grant select, insert on app_private.retention_log to autobots_runtime;

-- The runtime role can't delete, so this is the one way run content goes. It keeps the run row, its events,
-- evidence and every tool receipt, because a retry or replay is answered from those.
create function app_private.purge_run_content(p_workspace uuid, p_run uuid, p_cutoff timestamptz)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare
  target public.runs%rowtype;
  tree uuid;
  checkpoints bigint := 0;
  files bigint := 0;
  offloads bigint := 0;
  summaries bigint := 0;
  artifacts bigint := 0;
begin
  select * into target from public.runs where id = p_run and workspace_id = p_workspace for update;
  if not found then
    return jsonb_build_object('refused', 'run_not_found');
  end if;
  if target.content_purged_at is not null then
    return jsonb_build_object('refused', 'already_purged');
  end if;
  if target.status not in ('succeeded', 'failed', 'cancelled') then
    return jsonb_build_object('refused', 'run_active');
  end if;
  if target.updated_at >= p_cutoff then
    return jsonb_build_object('refused', 'inside_window');
  end if;
  tree := coalesce(target.root_run_id, target.id);
  if exists (select 1 from public.runs r where coalesce(r.root_run_id, r.id) = tree
             and r.status not in ('succeeded', 'failed', 'cancelled')) then
    return jsonb_build_object('refused', 'run_tree_active');
  end if;
  if exists (select 1 from public.runs r where r.continues_run_id = p_run
             and r.status not in ('succeeded', 'failed', 'cancelled')) then
    return jsonb_build_object('refused', 'continuation_active');
  end if;
  if exists (select 1 from app_private.tool_receipts t where t.run_id = p_run
             and t.status in ('started', 'unknown')) then
    return jsonb_build_object('refused', 'unresolved_effect');
  end if;
  if exists (select 1 from app_private.run_obligations o where o.run_id = p_run and o.status = 'open') then
    return jsonb_build_object('refused', 'open_obligation');
  end if;
  if target.checkpoint_thread_id is not null then
    delete from agent_runtime.checkpoint_writes where thread_id = target.checkpoint_thread_id;
    delete from agent_runtime.checkpoint_blobs where thread_id = target.checkpoint_thread_id;
    delete from agent_runtime.checkpoints where thread_id = target.checkpoint_thread_id;
    get diagnostics checkpoints = row_count;
  end if;
  delete from app_private.run_files where run_id = p_run;
  get diagnostics files = row_count;
  delete from app_private.run_offloads where run_id = p_run;
  get diagnostics offloads = row_count;
  delete from app_private.run_summaries where run_id = p_run;
  get diagnostics summaries = row_count;
  update public.artifacts set status = 'expired' where run_id = p_run and status <> 'expired';
  get diagnostics artifacts = row_count;
  update public.runs set content_purged_at = now() where id = p_run;
  insert into app_private.retention_log (workspace_id, run_id, action, detail)
    values (p_workspace, p_run, 'run_content_purged', jsonb_build_object(
      'checkpoints', checkpoints, 'files', files, 'offloads', offloads,
      'summaries', summaries, 'artifacts', artifacts));
  return jsonb_build_object('purged', true, 'checkpoints', checkpoints, 'files', files,
                            'offloads', offloads, 'summaries', summaries, 'artifacts', artifacts);
end;
$$;

-- An expired key only stops answering a retry. The effect's own receipt in tool_receipts stays.
create function app_private.expire_idempotency_receipts(p_workspace uuid, p_cutoff timestamptz)
returns bigint
language plpgsql security definer set search_path = ''
as $$
declare
  removed bigint;
begin
  delete from app_private.idempotency_receipts i
    where i.workspace_id = p_workspace and i.created_at < p_cutoff
      and not exists (select 1 from public.runs r where r.workspace_id = p_workspace
                      and r.status not in ('succeeded', 'failed', 'cancelled')
                      and (r.id::text = i.target or r.id::text = i.result ->> 'run_id'));
  get diagnostics removed = row_count;
  if removed > 0 then
    insert into app_private.retention_log (workspace_id, action, detail)
      values (p_workspace, 'idempotency_keys_expired', jsonb_build_object('keys', removed));
  end if;
  return removed;
end;
$$;

revoke all on function app_private.purge_run_content(uuid, uuid, timestamptz) from public, anon, authenticated;
revoke all on function app_private.expire_idempotency_receipts(uuid, timestamptz) from public, anon, authenticated;
grant execute on function app_private.purge_run_content(uuid, uuid, timestamptz) to autobots_runtime;
grant execute on function app_private.expire_idempotency_receipts(uuid, timestamptz) to autobots_runtime;
