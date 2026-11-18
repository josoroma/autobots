-- Fails on its second statement, so nothing from it may remain.
create table public.partial_migration (id int);
select no_such_column from public.runs;
