-- Synthetic H1 stub worker for DH-A09, not the product's worker. Uses database time.
create schema worker_fixture;

create table worker_fixture.jobs (
  id int primary key,
  status text not null default 'queued',
  owner text,
  generation bigint not null default 0,
  lease_expires_at timestamptz
);

create table worker_fixture.receipts (
  operation_id text primary key,
  job_id int not null references worker_fixture.jobs (id),
  generation bigint not null
);

create table worker_fixture.effects (
  id bigserial primary key,
  operation_id text not null,
  job_id int not null references worker_fixture.jobs (id)
);

create function worker_fixture.claim(worker text, lease interval) returns bigint
  language sql as $$
    update worker_fixture.jobs set
      status = 'running', owner = worker, generation = generation + 1,
      lease_expires_at = clock_timestamp() + lease
    where id = (
      select id from worker_fixture.jobs
      where status = 'queued' or (status = 'running' and lease_expires_at < clock_timestamp())
      order by id for update skip locked limit 1
    )
    returning generation
  $$;

create function worker_fixture.heartbeat(job int, fence bigint, lease interval) returns boolean
  language sql as $$
    with changed as (
      update worker_fixture.jobs set lease_expires_at = clock_timestamp() + lease
      where id = job and generation = fence and status = 'running' and lease_expires_at >= clock_timestamp()
      returning 1
    )
    select exists (select 1 from changed)
  $$;

create function worker_fixture.apply_effect(job int, fence bigint, operation text) returns text
  language plpgsql as $$
  declare
    held boolean;
  begin
    select generation = fence and status = 'running' and lease_expires_at >= clock_timestamp()
      into held from worker_fixture.jobs where id = job for update;
    if exists (select 1 from worker_fixture.receipts where operation_id = operation) then
      return 'duplicate';
    end if;
    if held is not true then
      return 'fenced';
    end if;
    insert into worker_fixture.effects (operation_id, job_id) values (operation, job);
    insert into worker_fixture.receipts (operation_id, job_id, generation) values (operation, job, fence);
    return 'applied';
  end
  $$;

create function worker_fixture.complete(job int, fence bigint) returns boolean
  language sql as $$
    with changed as (
      update worker_fixture.jobs set status = 'succeeded', lease_expires_at = null
      where id = job and generation = fence and status = 'running' and lease_expires_at >= clock_timestamp()
      returning 1
    )
    select exists (select 1 from changed)
  $$;

insert into worker_fixture.jobs (id) values (1);
