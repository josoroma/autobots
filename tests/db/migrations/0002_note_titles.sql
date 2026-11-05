-- Synthetic H1 fixture: an expanding follow-up migration that keeps existing rows.
alter table app.notes add column title text not null default 'untitled';
create index notes_workspace_id on app.notes (workspace_id);
