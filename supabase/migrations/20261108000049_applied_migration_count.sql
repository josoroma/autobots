-- US-15.18, PRD-Studio OP-02 and Decision 0022 D5: how many migrations this database has applied, as a
-- number only. The history belongs to whichever runner applied it: the guarded install's or a disposable
-- target's, and the runtime role can read neither. This function returns their count, and nothing of the
-- rows: no name, checksum or time. Only migration files count, not the Storage policy row the install
-- also records. With neither history present it returns null.
create function app_private.applied_migration_count() returns integer
language plpgsql stable security definer set search_path = ''
as $$
declare
  history text;
  applied integer;
begin
  if to_regclass('autobots_install.migrations') is not null then
    history := 'autobots_install.migrations';
  elsif to_regclass('autobots_disposable.migrations') is not null then
    history := 'autobots_disposable.migrations';
  else
    return null;
  end if;
  execute format('select count(*)::integer from %s where name ~ %L', history, '^[0-9]{14}_[a-z0-9_]+\.sql$')
    into applied;
  return applied;
end;
$$;

revoke all on function app_private.applied_migration_count() from public, anon, authenticated;
grant execute on function app_private.applied_migration_count() to autobots_runtime;
