# Deliberate fault fixtures

Known-good and known-bad inputs for `scripts/qualify_faults.py`, which `scripts/verify.py --profile full` runs. Each bad fixture is meant to fail, for the reason its case names. Do not fix one, and do not remove one to make a suite pass.

The `state` and `contract` checkers here are fixture checkers. They show the checks catch these faults, and are not the product's run state machine or contract generation, which later stories implement. The state table is copied from [SP-010](../../docs/engineering/option-b-contract.md#sp-010--canonical-run-states-and-transitions).
