---
name: autobots-review-change
description: Independently review an Autobots change against source requirements, correctness, boundaries and current evidence without modifying the author's implementation. Use for review and completion assessment.
---

# Review independently

Relevant paths: `docs/engineering/work-items/<id>.md`, `docs/engineering/evidence/<id>/` and `docs/engineering/runbooks/<id>.md`.

Read `.claude/autobots.json`, the mapped contract, selected work item, source requirements and current evidence. Establish the reviewed source/config/lock/verifier fingerprint; a commit alone does not cover uncommitted files.

Delegate to `autobots-reviewer` in a separate context with explicit changed paths, baseline/final content or diff, acceptance IDs and evidence locations. The reviewer has only Read, Grep and Glob. It returns findings; the caller persists the review record. Do not silently repair code while presenting the result as independent review.

Assess observable behavior, failure/recovery cases, API/state compatibility, secrets/authorization and whether executed assertions prove the claimed acceptance. Distinguish blocking defects from suggestions. A mock response, passing parser or old report cannot establish live behavior. Missing current evidence is a gap, not a passing result.

Return findings ordered by severity with path/location, concrete consequence, source requirement and suggested correction; also record inspected invariants, reviewer identity/context, fingerprint and limitations. If no defects are found, state the scope reviewed rather than asserting universal correctness.

After an author fixes a finding, inspect its resolution and affected evidence. A reviewer that edits implementation becomes an author for that scope and requires another independent review. Follow [DH-W03 and DH-W06](../../../docs/PRD/PRD-Development-Harness.md#dh-091-work-item-evidence-contract); review adds no user-permission ceremony.
