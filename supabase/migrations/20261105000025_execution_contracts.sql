-- PRD 10.3 and SP-015: what a saved run depends on, and which framework release may continue saved work.
alter table public.runs add column execution_contract jsonb;

-- Everything admitted so far ran under the first graph state and these tool versions, so this records a fact.
-- Bindings aren't touched. Runs admitted from now on record theirs at admission.
update public.runs set execution_contract = '{"graph_state": 1, "recorded_by": "upgrade", "tools": {"assign_specialist": 1, "calculate": 1, "complete_task": 1, "propose_improvement": 1, "propose_plan": 1, "publish_artifact": 1, "read_offload": 1, "read_run_file": 1, "save_artifact": 1, "search_memory": 1}}'::jsonb;

-- A release's identity is its version, migrations and the SQL the code relies on. A new row is added by a
-- migration only after the qualification in the upgrade runbook has passed for that release.
create table agent_runtime.adapter_qualifications (
  fingerprint text primary key,
  package_version text not null,
  migrations integer not null check (migrations >= 0),
  qualified_at timestamptz not null default now()
);

revoke all on agent_runtime.adapter_qualifications from public, anon, authenticated;
grant select on agent_runtime.adapter_qualifications to autobots_runtime;

insert into agent_runtime.adapter_qualifications (fingerprint, package_version, migrations)
  values ('1f37850a6de6954e84e3c34e65943a7009a091e1b76995f30666aa835de88fcb', '3.2.0', 10);
