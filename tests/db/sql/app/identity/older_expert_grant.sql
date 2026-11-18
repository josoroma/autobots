-- US-15.7: an Expert that granted read_csv only in an older version, and a published workflow whose agent
-- step uses Issue triager from experts.sql, which grants read_csv now. Synthetic rows for the disposable
-- identity qualification only (DH-07). scripts/qualify_identity.py runs it as the runtime role, after
-- experts.sql, with the experts-h owner's workspace and user.

insert into public.experts (id, workspace_id, name, latest_version) values ('55555555-5555-4555-8555-000000000004', ${workspace}, 'Old granter', 2);
insert into public.expert_versions (expert_id, version, config, created_by) values
  ('55555555-5555-4555-8555-000000000004', 1, '{"tools": ["read_csv"]}', ${user}),
  ('55555555-5555-4555-8555-000000000004', 2, '{"tools": ["calculate"]}', ${user});
insert into public.workflows (id, workspace_id, name, latest_version) values ('55555555-5555-4555-8555-000000000005', ${workspace}, 'Nightly triage', 1);
insert into public.workflow_versions (workflow_id, version, graph, graph_hash, block_versions, source, created_by) values
  ('55555555-5555-4555-8555-000000000005', 1,
   '{"nodes": [{"id": "start", "block": "input", "version": 1, "config": {}}, {"id": "triage", "block": "agent", "version": 1, "config": {"expert_id": "55555555-5555-4555-8555-000000000002"}}, {"id": "done", "block": "output", "version": 1, "config": {}}], "links": []}',
   'arranged', '{}', 'user', ${user});
