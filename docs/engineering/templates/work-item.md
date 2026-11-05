# {{work_item_id}} — {{title}}

Status: TEMPLATE
Evidence: {{evidence_id}}

This template has not been executed. Replace every `{{placeholder}}`, and set `Status: IN PROGRESS`. Only `scripts/evidence.py complete` sets `Status: COMPLETE`. Keep it proportional: a small fix may need only a few bullets in each section.

## Plan

DH-W01. Written before editing implementation.

- **Source:** {{SPECS_id_and_PRD_requirement_ids}}
- **Intended behavior and invariants:** {{behavior}}
- **Affected layers, contracts and states:** {{layers}}
- **Migration and operational impact:** {{impact}}
- **Verification and recovery plan:** {{plan}}

## Implementation

DH-W02.

- **Revision and changed paths:** {{revision_and_paths}}
- **Actual behavior:** {{behavior_observed}}
- **Contract, migration and configuration changes:** {{changes}}
- **Stubs, deferred work and deviations from the plan:** {{deviations}}

## Review

DH-W03. By someone other than the author, or a separate qualified context. A review that changes code becomes authorship and needs another review of that scope.

- **Author and reviewer:** {{author_id}}; {{reviewer_id}}
- **Reviewed fingerprint:** {{source_manifest_sha256}}
- **Findings and dispositions:** {{findings}}

## Verification

DH-W04. Manifest and summary: `docs/engineering/evidence/{{work_item_id}}/`.

- **Classes and model transport:** {{classes}}
- **Failures, errors, skips and limits:** {{limits}}

## Runbook

DH-W05.

- **Procedure:** {{runbook_link}}
- **Last exercised:** {{revision_date_and_result}}
- **Untested steps:** {{untested}}
