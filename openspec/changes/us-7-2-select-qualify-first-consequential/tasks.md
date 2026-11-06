## 1. The connector (scenario: Enforce the selected connector contract)

- [x] 1.1 Add `create_github_issue` with versioned contracts, a fixed repository and a per-attempt token, checked by `tests/test_github_issues.py` over a fake transport
- [x] 1.2 Tell definite refusals from uncertain outcomes, and settle uncertain ones by reading the marker back, checked by the same tests
- [x] 1.3 Register it, grant it per Expert and offer it in the Expert editor, checked by `tests/test_execution_contract.py` and the `full` profile
- [x] 1.4 Run it through the real gateway and approvals on a disposable database, in `tests/db/connector_check.py`: approval first, one issue after a repeat or a lost acknowledgment, and no token in any record
- [x] 1.5 Document setup in the operations runbook and `.env.example`, checked by reading them against the code

## 2. Scope (scenario: Reject out-of-scope work)

- [x] 2.1 Show in `tests/db/connector_check.py` that an ungranted tool or a repository argument is refused with no request sent

## 3. Live qualification (scenario: Enforce the selected connector contract)

- [x] 3.1 Add `scripts/qualify_github_connector.py`, which refuses a broad token or a public repository, checked by `tests/test_github_issues.py`
- [ ] 3.2 Run it against the owner's throwaway private repository, and record the result. Needs a token only the owner can create
