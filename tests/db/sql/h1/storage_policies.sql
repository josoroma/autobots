-- Synthetic H1 fixture, applied after storage-api has created its own schema.
insert into storage.buckets (id, name, public) values ('workspace-files', 'workspace-files', false)
on conflict (id) do nothing;

drop policy if exists member_read on storage.objects;
drop policy if exists member_write on storage.objects;
create policy member_read on storage.objects for select to authenticated
  using (bucket_id = 'workspace-files' and app.is_member(((storage.foldername(name))[1])::uuid));
create policy member_write on storage.objects for insert to authenticated
  with check (bucket_id = 'workspace-files' and app.is_member(((storage.foldername(name))[1])::uuid));
