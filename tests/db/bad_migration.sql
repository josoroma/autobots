-- Fails on its second statement, so nothing from it may remain.
create table app.partial_migration (id int);
select no_such_column from app.notes;
