## 1. Version checks (scenario: Preserve execution semantics during upgrade)

- [x] 1.1 Execution contract recorded at admission and for saved runs, with the compatibility rule
- [x] 1.2 Worker gate, resume refusal and a recorded reason
- [x] 1.3 A misrouted worker pauses a saved run instead of failing it

## 2. Adapter qualification (scenario: Qualify adapter migrations)

- [x] 2.1 Adapter identity and recorded qualifications, stopping claims and admission when absent
- [x] 2.2 Comparison with the adapter's own setup, grants and search-path checks

## 3. Exercise (all scenarios)

- [x] 3.1 `scripts/qualify_upgrade.py` from a prior release's code and migrations
- [x] 3.2 Upgrade runbook
