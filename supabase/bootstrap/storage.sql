-- Run as the database superuser after Storage has created its own schema, which the migration role cannot alter.
insert into storage.buckets (id, name, public) values ('workspace-artifacts', 'workspace-artifacts', false)
on conflict (id) do update set public = false;

create or replace function public.can_access_artifact(object_name text) returns boolean
  language sql stable security definer set search_path = ''
  as $$ select case
    when (storage.foldername(object_name))[1] ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    then public.is_workspace_member(((storage.foldername(object_name))[1])::uuid)
    else false
  end $$;

revoke all on function public.can_access_artifact(text) from public;
grant execute on function public.can_access_artifact(text) to authenticated;

drop policy if exists artifact_read on storage.objects;
drop policy if exists artifact_write on storage.objects;
drop policy if exists artifact_update on storage.objects;
drop policy if exists artifact_delete on storage.objects;
create policy artifact_read on storage.objects for select to authenticated
  using (bucket_id = 'workspace-artifacts' and public.can_access_artifact(name));
create policy artifact_write on storage.objects for insert to authenticated
  with check (bucket_id = 'workspace-artifacts' and public.can_access_artifact(name));
create policy artifact_update on storage.objects for update to authenticated
  using (bucket_id = 'workspace-artifacts' and public.can_access_artifact(name));
create policy artifact_delete on storage.objects for delete to authenticated
  using (bucket_id = 'workspace-artifacts' and public.can_access_artifact(name));
