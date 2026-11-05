-- Review round 1, M10, M11 and M15. Keys last as long as what they can answer for, a finished run's stale
-- obligation doesn't block retention, and a qualification covers the whole framework stack it was done on.
update app_private.workspace_retention set receipt_days = null where run_days is null;
alter table app_private.workspace_retention add constraint workspace_retention_keys_need_content
  check (receipt_days is null or run_days is not null);

update app_private.run_obligations o set status = 'met', response = 'cancelled', met_at = now()
  from public.runs r where r.id = o.run_id and o.status = 'open' and r.status in ('succeeded', 'failed', 'cancelled');

create or replace function app_private.expire_idempotency_receipts(p_workspace uuid, p_cutoff timestamptz)
returns bigint
language plpgsql security definer set search_path = ''
as $$
declare
  removed bigint;
begin
  delete from app_private.idempotency_receipts i
    where i.workspace_id = p_workspace and i.created_at < p_cutoff
      and not exists (
        select 1 from public.runs r
        where r.workspace_id = p_workspace
          and (r.id::text = i.target or r.id::text = i.result ->> 'run_id')
          and (
            r.status not in ('succeeded', 'failed', 'cancelled')
            or r.updated_at >= p_cutoff
            or exists (select 1 from app_private.tool_receipts t
                       where t.run_id = r.id and t.status in ('started', 'unknown'))
            or exists (select 1 from app_private.model_invocations m
                       where m.run_id = r.id and m.status = 'uncertain' and m.reconciled_at is null)
          )
      );
  get diagnostics removed = row_count;
  if removed > 0 then
    insert into app_private.retention_log (workspace_id, action, detail)
      values (p_workspace, 'idempotency_keys_expired', jsonb_build_object('keys', removed));
  end if;
  return removed;
end;
$$;

-- A terminal run can't resume, so nothing can still be waiting on an answer from it.
create or replace function app_private.purge_run_content(p_workspace uuid, p_run uuid, p_cutoff timestamptz)
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

alter table agent_runtime.adapter_qualifications add column evidence text not null default 'not recorded';
update agent_runtime.adapter_qualifications set evidence = 'tests/db/upgrade_check.py, adapter only';
insert into agent_runtime.adapter_qualifications (fingerprint, package_version, migrations, evidence)
  values ('2a3fcd6f5771329541d9b5c6582daf8d746a857e07d2fb88e6b89c34ab867e24', '3.2.0', 10, 'scripts/qualify_upgrade.py, disposable, scripted model');
