-- Decision 0029 F3 (R-56, SQLI-07), PRD-Local-Mac-Deployment LM-05: a member reads its workspace's
-- artifacts and writes none. The API writes artifact bytes with the service key and never overwrites
-- one (adapters/object_storage.py), and no browser path writes Storage, so a member's insert, update or
-- delete could only turn a published artifact into a missing one. Anonymous callers read no Storage
-- object, so they lose EXECUTE on can_access_artifact too. Applied as the database superuser after
-- storage.sql, which keeps its bytes, by persistent_install.py and app_db.py, with its history row.
-- Locks: ACCESS EXCLUSIVE on storage.objects for each of the three policy drops, milliseconds each,
-- since no row is read.
-- Data: none. Objects, their bytes and the read policy are unchanged.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
drop policy if exists artifact_write on storage.objects;
drop policy if exists artifact_update on storage.objects;
drop policy if exists artifact_delete on storage.objects;
revoke execute on function public.can_access_artifact(text) from anon;
