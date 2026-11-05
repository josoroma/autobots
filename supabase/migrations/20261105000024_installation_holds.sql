-- SP-018: a restored instance holds its work. While a hold exists no job is claimed, nothing is admitted,
-- and no routine or retention pass runs, so restoring can't replay a paid call or an external write.
create table app_private.installation_holds (
  hold text primary key check (hold in ('restore')),
  detail text not null default '',
  created_at timestamptz not null default now()
);

revoke all on app_private.installation_holds from public, anon, authenticated;
-- Read only: releasing a hold is an operator's step as the database owner, not something a process can do.
grant select on app_private.installation_holds to autobots_runtime;
