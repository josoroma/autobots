-- US-15.6: three Experts with known tools, and three runs of Market watcher. Arranged by SQL, as a grant
-- naming an unconfigured connector is refused at save. Synthetic rows for the disposable identity
-- qualification only (DH-07). scripts/qualify_identity.py runs it as the runtime role, with the
-- experts-h owner's workspace and user.

insert into public.experts (id, workspace_id, name, latest_version) values ('55555555-5555-4555-8555-000000000001', ${workspace}, 'Market watcher', 1);
insert into public.expert_versions (expert_id, version, config, created_by) values ('55555555-5555-4555-8555-000000000001', 1,
  '{"tools": ["market_history", "inflation_rates", "calculate", "read_csv", "save_artifact", "read_run_file"], "role_bindings": {"executor": "openrouter_terra"}}', ${user});
insert into public.experts (id, workspace_id, name, latest_version) values ('55555555-5555-4555-8555-000000000002', ${workspace}, 'Issue triager', 1);
insert into public.expert_versions (expert_id, version, config, created_by) values ('55555555-5555-4555-8555-000000000002', 1,
  '{"tools": ["read_csv", "create_github_issue"]}', ${user});
insert into public.experts (id, workspace_id, name, latest_version) values ('55555555-5555-4555-8555-000000000003', ${workspace}, 'Brief writer', 1);
insert into public.expert_versions (expert_id, version, config, created_by) values ('55555555-5555-4555-8555-000000000003', 1,
  '{"tools": ["save_artifact"]}', ${user});
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, expert_id, created_at)
  select gen_random_uuid(), ${workspace}, 'succeeded', 'Watch ' || n, 1000000, '55555555-5555-4555-8555-000000000001', now() - make_interval(mins => 10 * n)
  from generate_series(1, 3) n;
