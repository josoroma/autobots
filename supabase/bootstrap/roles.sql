-- Run once, as the database superuser, through the guarded wrapper. Passwords arrive as psql variables.
create role autobots_migrator login nosuperuser nocreatedb nocreaterole noinherit password :'migrator_password';
create role autobots_runtime login nosuperuser nocreatedb nocreaterole noinherit password :'runtime_password';

-- Only the migration identity may create objects.
grant create on database postgres to autobots_migrator;
grant usage, create on schema public to autobots_migrator;
revoke create on schema public from public, autobots_runtime;
grant usage on schema auth to autobots_migrator;
grant execute on function auth.uid() to autobots_migrator;

-- Lets the migrator grant to these roles without being a superuser.
grant anon, authenticated, service_role, autobots_runtime to autobots_migrator;
