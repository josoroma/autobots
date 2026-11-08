# Verification — us-15-6-expert-card-facts-filters

Change: us-15-6-expert-card-facts-filters
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Findings

- **Completeness:** 3 of 3 tasks complete. 1 requirement added to `experts`.
- **"Card facts", "Can change things outside", "Approval note" and "Read only is the complement":** observed in `python3.12 scripts/verify.py --profile db` (exit 0). The browser test "Expert cards show their facts, filters and the approval note" passed against three Experts arranged by SQL in their own workspace:
  - Market watcher grants six tools, binds the executor to Terra, and has three runs.
  - Issue triager grants `read_csv` and `create_github_issue`.
  - Brief writer grants only `save_artifact`.
  
  The test asserts:
  - the filters read "All 3", "Can change things outside 1" and "Read only 2", which add up to All;
  - Market watcher's role line reads "executor · Terra · version 1", with `market_history` and "+2" among its tools, "3 runs · last N min ago", and "Start run with Market watcher";
  - Issue triager reads "Approval on every issue", and Brief writer has no note;
  - axe reports no violations;
  - Can change things outside lists only Issue triager, and Read only lists Brief writer and Market watcher (so `save_artifact` counts as read only, by D14);
  - searching "brief" leaves Brief writer.
  
  The Experts are arranged by SQL because a grant naming an unconfigured connector is refused at save.
- **"Start run discloses first":** observed in "Start run opens run creation with the disclosure, and sends nothing" (passed). Start run opens `/sessions/…`, whose disclosure reads "Nothing is sent until you press Run", and the workspace's run total is unchanged.
- **Also passed:** `slice-visual` on every screen in both themes, including Experts' keyboard order with Start run in each card's top row. `full` (exit 0) and `fast` (exit 0) passed on the final inputs.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
