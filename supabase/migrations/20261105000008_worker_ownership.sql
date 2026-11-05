-- SP-012: checkpoint tables owned by migrations, and ownership enforced where the write happens.
-- These are the pinned langgraph-checkpoint-postgres 3.2.0 tables. Recording all ten versions means the
-- adapter's own setup has nothing left to do, and a worker never runs it.
create table agent_runtime.checkpoint_migrations (v integer primary key);

create table agent_runtime.checkpoints (
  thread_id text not null,
  checkpoint_ns text not null default '',
  checkpoint_id text not null,
  parent_checkpoint_id text,
  type text,
  checkpoint jsonb not null,
  metadata jsonb not null default '{}',
  primary key (thread_id, checkpoint_ns, checkpoint_id)
);

create table agent_runtime.checkpoint_blobs (
  thread_id text not null,
  checkpoint_ns text not null default '',
  channel text not null,
  version text not null,
  type text not null,
  blob bytea,
  primary key (thread_id, checkpoint_ns, channel, version)
);

create table agent_runtime.checkpoint_writes (
  thread_id text not null,
  checkpoint_ns text not null default '',
  checkpoint_id text not null,
  task_id text not null,
  idx integer not null,
  channel text not null,
  type text,
  blob bytea not null,
  task_path text not null default '',
  primary key (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

create index checkpoints_thread_id_idx on agent_runtime.checkpoints (thread_id);
create index checkpoint_blobs_thread_id_idx on agent_runtime.checkpoint_blobs (thread_id);
create index checkpoint_writes_thread_id_idx on agent_runtime.checkpoint_writes (thread_id);

insert into agent_runtime.checkpoint_migrations (v) select generate_series(0, 9);

-- The share lock serializes against a claim, so a write racing a new generation waits and then fails.
create function app_private.require_checkpoint_owner() returns trigger
language plpgsql set search_path = '' as $$
declare
  owner_generation bigint;
begin
  select generation into owner_generation from app_private.run_jobs
    where run_id = new.thread_id::uuid and status = 'claimed' and lease_expires_at > clock_timestamp()
    for share;
  if owner_generation is null
     or current_setting('autobots.fencing_generation', true) is distinct from owner_generation::text then
    raise exception 'this worker no longer owns the run' using errcode = 'AB001';
  end if;
  return new;
end;
$$;

create trigger checkpoints_owner before insert or update on agent_runtime.checkpoints
  for each row execute function app_private.require_checkpoint_owner();
create trigger checkpoint_blobs_owner before insert or update on agent_runtime.checkpoint_blobs
  for each row execute function app_private.require_checkpoint_owner();
create trigger checkpoint_writes_owner before insert or update on agent_runtime.checkpoint_writes
  for each row execute function app_private.require_checkpoint_owner();

revoke all on all tables in schema agent_runtime from public, anon, authenticated;
grant select on agent_runtime.checkpoint_migrations to autobots_runtime;
grant select, insert, update on agent_runtime.checkpoints, agent_runtime.checkpoint_blobs,
  agent_runtime.checkpoint_writes to autobots_runtime;
