# Python: domain, contracts and persistence

The domain package is pure and is the strongest code in this area. Its 11 modules import only the standard library and autobots.domain, and they hold the canonical run state machine, role-policy resolution, budgets, routine timing and workflow validation as small, tested functions. contracts/ has a good boundary toolkit: STRICT_CONTRACT, MicroUsd bounded by MAX_SAFE_INTEGER, UtcTimestamp, schema_version on 48 of 51 route responses, and cross-language fixtures. The main risks are at the seams between layers. Request and tool contracts double as the stored JSON format for Experts, routines, goals and plans (16 read sites, all refusing unknown fields, and only WorkflowGraph carries a version), so tightening a contract can make saved records unreadable. The routine configuration has two definitions whose trigger, budget and timezone rules differ (cronjob tool versus Routines API). A tool input accepts naive datetimes that the GitHub adapter cannot compare, so a date-only `since` makes the read fail with a generic tool_failed after a retry. Typing is uneven. At least 23 response fields are typed looser than vocabularies that SQL or sibling contracts already declare. Strictness is chosen per model and is off in 22 of 30 request bodies, so MicroUsd's strict-money promise does not hold where requests arrive. Nine domain enums are re-declared by hand as Literals in 10 places, with no parity check. The workflow domain runs on Mapping[str, Any]. Typed persistence rows exist for one entity (RunRow), while roughly 353 positional row reads elsewhere build DTOs by hand. Size is mostly healthy. Complexity concentrates in validate_graph (C901 21) and next_steps (14), and two contract modules pass 300 lines. pyproject.toml enforces no complexity rule, nothing checks layer purity, and pydantic is not a declared dependency. [Back to the review](../README.md)

Area `py-domain`, revision `156534da0bd5b19417f05d313077d767804b175b`, run `2026-11-12-09-52-30`. Every finding below was re-opened at its cited lines and recounted by an adversarial verifier.

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Ruff, format and strict mypy pass and versions are pinned, but no complexity rule is selected, pydantic is undeclared, layering is unchecked, and strictness is set per model rather than per field as DH-06 asks. |
| modules | 3 | domain is a pure leaf and contracts otherwise depend only on domain and persistence, but export.py imports the API app, tools.py serves three audiences, and contracts double as storage formats. |
| size | 4 | 40 of 42 files are under 300 lines and most functions are short. Complexity concentrates in validate_graph (21), next_steps (14) and two helpers. |
| functions | 4 | Domain functions are small and pure with explicit inputs. The exceptions are a few phase-heavy validators and a six-parameter helper. |
| structure | 3 | The domain and contracts layout is clear, but persistence/ holds one TypedDict, the OpenAPI exporter sits in contracts/, and run screens and tool families are split unevenly. |
| approach | 3 | The state machine, policy resolution and allowlist DTO mapping are exemplary, but stored JSON reuses request contracts, positional rows dominate, and the routine config has two definitions. |
| comments | 4 | Comments explain why and cite decisions and stories. A few docstrings leak Pydantic configuration notes into OpenAPI or describe history. |
| types | 3 | StrEnums, shared primitives and strict mypy are strong, but at least 23 loose response fields, per-model strictness, untyped workflow graphs and a naive-datetime tool input weaken the boundaries. |
| errors | 3 | Typed refusal codes exist, but in four shapes, with 13 copies of one constructor and each route mapping each exception by hand. |
| tests | 3 | Domain logic is well tested (state machine, workflows, budgets, execution table), but shared fixtures cover 4 of 170 schemas, and the since defect and transform parity are untested. |
| maintainability | 3 | The core is solid and readable, but storage formats, duplicated vocabularies and loose DTO types make contract changes riskier than they look. |

## Strengths

- **The domain stays pure.** All 11 domain modules import only the standard library and autobots.domain, and services/agent/src/autobots/persistence/rows.py imports only the standard library (grep of every import line). [services/agent/src/autobots/domain/__init__.py:1](../../../../services/agent/src/autobots/domain/__init__.py#L1) states the rule. Even key availability takes the environment as a parameter ([services/agent/src/autobots/domain/tool_catalog.py:105-112](../../../../services/agent/src/autobots/domain/tool_catalog.py#L105)).
- **The run lifecycle is a reviewed table.** [services/agent/src/autobots/domain/runs.py:22-128](../../../../services/agent/src/autobots/domain/runs.py#L22) encodes TERMINAL, NORMAL_EXITS, COMMANDS (actor and target) and COMMAND_SOURCES as data, and next_status refuses with CommandRefused. [services/agent/tests/test_contracts.py:103-160](../../../../services/agent/tests/test_contracts.py#L103) tests wrong actor, terminal states, idempotent cancel and the SP-010 exits.
- **Boundary primitives that state their reasons.** [services/agent/src/autobots/contracts/primitives.py:9-32](../../../../services/agent/src/autobots/contracts/primitives.py#L9) defines STRICT_CONTRACT, MicroUsd bounded by MAX_SAFE_INTEGER (with the JavaScript rationale) and UtcTimestamp (AfterValidator plus a JSON Schema pattern). The 29 cases in contracts/fixtures/boundary-cases.json are read by both [services/agent/tests/test_contracts.py:30](../../../../services/agent/tests/test_contracts.py#L30) and the TypeScript client tests ([packages/api-client/tests/contract.test.ts:8](../../../../packages/api-client/tests/contract.test.ts#L8)).
- **Allowlist mapping keeps new fields private.** [services/agent/src/autobots/contracts/adapters.py:26-42](../../../../services/agent/src/autobots/contracts/adapters.py#L26) names every public field, so a new domain field stays private by default. run_from_row raises on an unknown stored status instead of passing it to a client (adapters.py:9), which [services/agent/tests/test_contracts.py:86](../../../../services/agent/tests/test_contracts.py#L86) tests.
- **Versioned envelopes and explicit compatibility tables.** 48 of 51 route response models carry schema_version: Literal[1]. RunEvent is a typed envelope ([services/agent/src/autobots/contracts/runs.py:127-147](../../../../services/agent/src/autobots/contracts/runs.py#L127)). IR normalization keeps version 1 hashes stable ([services/agent/src/autobots/domain/workflows.py:15-18](../../../../services/agent/src/autobots/domain/workflows.py#L15), 199-211). The execution table lists explicitly compatible tool changes ([services/agent/src/autobots/domain/execution.py:10-76](../../../../services/agent/src/autobots/domain/execution.py#L10)) and is kept equal to the registry by [services/agent/tests/test_execution_contract.py:23-29](../../../../services/agent/tests/test_execution_contract.py#L23).
- **Cross-field invariants live in the schema.** [services/agent/src/autobots/contracts/cronjob.py:74-81](../../../../services/agent/src/autobots/contracts/cronjob.py#L74): each action takes only its own fields. [services/agent/src/autobots/contracts/tools.py:228-234](../../../../services/agent/src/autobots/contracts/tools.py#L228): 1 MiB in total and unique paths. [services/agent/src/autobots/contracts/browsing.py:38-49](../../../../services/agent/src/autobots/contracts/browsing.py#L38): the start URL must be inside allowed_domains. [services/agent/src/autobots/contracts/operations.py:42-50](../../../../services/agent/src/autobots/contracts/operations.py#L42): receipt retention outlives run retention.
- **Money is exact integers end to end.** No contract or domain type uses a float for money. [services/agent/src/autobots/domain/budgets.py:34-51](../../../../services/agent/src/autobots/domain/budgets.py#L34) checks range, step and daily cap with typed codes, and the role policy refuses unknown profiles instead of mapping them to a default ([services/agent/src/autobots/domain/models.py:109-120](../../../../services/agent/src/autobots/domain/models.py#L109)).
- **Comments explain why and cite their source.** [services/agent/src/autobots/domain/routines.py:43-47](../../../../services/agent/src/autobots/domain/routines.py#L43) (daylight-saving semantics), [services/agent/src/autobots/domain/models.py:69-72](../../../../services/agent/src/autobots/domain/models.py#L69) (why offering is checked where new work starts), [services/agent/src/autobots/contracts/approvals.py:70-73](../../../../services/agent/src/autobots/contracts/approvals.py#L70) (fields empty on older requests), and [services/agent/src/autobots/domain/execution.py:1-5](../../../../services/agent/src/autobots/domain/execution.py#L1) (raising a version is a review decision).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [PDOM-01](#pdom-01) | high | approach | Stored JSON records are read back with the request contracts, so a contract edit is an unversioned storage-format change | L | high |
| [PDOM-02](#pdom-02) | high | types | The routine configuration has two definitions whose trigger, budget and timezone rules differ | M | high |
| [PDOM-03](#pdom-03) | medium | types | Tool inputs accept naive `since` datetimes, which the GitHub adapter cannot compare | S | medium |
| [PDOM-04](#pdom-04) | medium | types | At least 23 response fields are typed looser than vocabularies that already exist | M | high |
| [PDOM-05](#pdom-05) | medium | types | Strictness is chosen per model and is off in 22 of 30 request bodies, so MicroUsd accepts strings and floats where requests arrive | M | high |
| [PDOM-06](#pdom-06) | medium | duplication | Contract Literals re-declare nine domain enums by hand in 10 places, with no parity check | M | medium |
| [PDOM-07](#pdom-07) | medium | types | Tool input types under-declare their constraints, so the model never sees them | M | high |
| [PDOM-08](#pdom-08) | medium | approach | Typed persistence rows exist for one entity; elsewhere DTOs are built from positional tuples | L | medium |
| [PDOM-09](#pdom-09) | medium | types | The workflow domain runs on untyped mappings and bare strings | M | medium |
| [PDOM-10](#pdom-10) | medium | size | Workflow validation and scheduling concentrate the area's complexity | M | medium |
| [PDOM-12](#pdom-12) | medium | duplication | Transform and predicate vocabularies are declared three times, with nothing tying them together | S | low |
| [PDOM-13](#pdom-13) | medium | errors | Coded refusals take four shapes, and the same constructor is written 13 times | M | medium |
| [PDOM-14](#pdom-14) | medium | standards | Layer purity is declared but not enforced, and contracts/export.py already depends on the API | S | low |
| [PDOM-15](#pdom-15) | medium | standards | pyproject.toml enforces no size or complexity rule and leaves pydantic undeclared | S | low |
| [PDOM-16](#pdom-16) | medium | tests | Cross-language contract fixtures cover 4 of 170 schemas and only one request body | M | low |
| [PDOM-11](#pdom-11) | low | size | contracts/tools.py mixes three audiences in 474 lines; run_workspace.py holds three screens | M | low |
| [PDOM-17](#pdom-17) | low | duplication | Kahn's topological sort is written three times and the foreach region walk twice | S | medium |
| [PDOM-18](#pdom-18) | low | naming | Colliding and misleading names in contracts and domain | S | low |
| [PDOM-19](#pdom-19) | low | comments | Some docstrings publish implementation notes as API documentation or describe history | S | low |
| [PDOM-20](#pdom-20) | low | approach | Grant allowlists and transition tables are mutable dicts; only models.py freezes its tables | S | low |

### <a id="pdom-01"></a>PDOM-01: Stored JSON records are read back with the request contracts, so a contract edit is an unversioned storage-format change

- **Severity** high · **Dimension** approach · **Effort** L · **Risk** high · **Occurrences** 16
- **Where:**
  - [services/agent/src/autobots/contracts/experts.py:14](../../../../services/agent/src/autobots/contracts/experts.py#L14): ExpertConfig: request body (extra=forbid, max_length bounds) and the stored config format
  - [services/agent/src/autobots/contracts/routines.py:21](../../../../services/agent/src/autobots/contracts/routines.py#L21): RoutineConfig: request body and the stored routine_versions.config
  - [services/agent/src/autobots/contracts/plans.py:40](../../../../services/agent/src/autobots/contracts/plans.py#L40): GoalSpec: TOOL_CONTRACT model stored in app_private.goal_specs
  - [services/agent/src/autobots/application/experts.py:82](../../../../services/agent/src/autobots/application/experts.py#L82): stored config read with ExpertConfig (also :213, :319)
  - [services/agent/src/autobots/application/routines.py:98](../../../../services/agent/src/autobots/application/routines.py#L98): stored config read with RoutineConfig (also :284, :434)
  - [services/agent/src/autobots/application/plans.py:104-116](../../../../services/agent/src/autobots/application/plans.py#L104): GoalSpec and PlanTask validate stored jsonb
  - [services/agent/tests/test_execution_contract.py:75](../../../../services/agent/tests/test_execution_contract.py#L75): older-record tests exist for snapshots and execution contracts, not for these records
  - [services/agent/src/autobots/domain/execution.py:62-76](../../../../services/agent/src/autobots/domain/execution.py#L62): the one stored record that is read tolerantly and explicitly
- **Evidence:** 16 read sites validate stored jsonb, or stored lines, with request or tool contract models. Counted by grep for `<Model>.model_validate(` over stored values in application/ and api/: ExpertConfig 5 (api/run_routes.py:141, application/experts.py:82, :213, :319, application/workflow_overview.py:81), RoutineConfig 3, WorkflowGraph 2, and GoalSpec, PlanTask, AssignmentResult, ApprovalScope, ApprovalReviewDetail and RestoreRecord once each. Every one refuses unknown fields (VIEW or TOOL_CONTRACT), and most carry request bounds, for example `tools: list[str] = Field(default_factory=list, max_length=20)`. Only WorkflowGraph has a version (ir_version). Older-record tests exist only for role-policy snapshots and execution contracts ([services/agent/tests/test_model_policy.py:478](../../../../services/agent/tests/test_model_policy.py#L478), [services/agent/tests/test_execution_contract.py:36](../../../../services/agent/tests/test_execution_contract.py#L36) and :75); none holds an earlier stored shape of these 16 records.
- **Why it matters:** Removing or renaming a field, or tightening a bound, in ExpertConfig, RoutineConfig, GoalSpec or PlanTask makes saved versions fail validation on read: Expert pages, routine occurrences and running goals would error. Nothing flags this, because the drift check compares OpenAPI, not stored data. It also blocks the contract tightening that other findings here recommend (PDOM-02, PDOM-04, PDOM-05).
- **Recommendation:** Give stored documents their own record types: read them leniently, give them a version, and map them explicitly to and from the DTOs. Keep request DTOs strict. Start with ExpertConfig and RoutineConfig, which have the most read sites. Add one test per record type checking that every stored shape still reads, with fixtures captured from the current release. domain/execution.py:62-76 shows the tolerant read style to follow.
- **Rule check:** DH-06 'Distinguish domain entities, persistence rows, public DTOs...' and 'Define compatibility/migration behavior for renamed/removed fields', and contracts.md 'Define compatibility and upgrade behavior'. This separates types and merges none (ground rule 2). If existing rows need normalizing, that is a new forward migration, never an edit to an applied one.
- **Verification:** revised. All 16 call sites re-opened and recounted. Corrected 'every one carries request bounds' (ApprovalScope and AssignmentResult have none) and noted the execution-contract compatibility tests, which don't cover these records.

```text
persistence/records.py
  class StoredRecord(BaseModel): model_config = ConfigDict(frozen=True, extra="ignore"); record_version: int = 1
  class ExpertConfigRecord(StoredRecord): purpose, instructions, tools, tool_groups, skills, role_bindings  # no request bounds
  class RoutineConfigRecord / GoalSpecRecord / PlanTaskRecord(StoredRecord)
  def read_expert_config(raw: Mapping[str, object]) -> ExpertConfigRecord   # upgrades older record_version
application/<aggregate>.py: to_record(dto) on write, to_view(record) on read
services/agent/tests/fixtures/stored/<record>/v1.json + test_every_stored_shape_reads
```

### <a id="pdom-02"></a>PDOM-02: The routine configuration has two definitions whose trigger, budget and timezone rules differ

- **Severity** high · **Dimension** types · **Effort** M · **Risk** high · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/contracts/routines.py:25](../../../../services/agent/src/autobots/contracts/routines.py#L25): Routines API: trigger: dict[str, Any]
  - [services/agent/src/autobots/contracts/cronjob.py:27](../../../../services/agent/src/autobots/contracts/cronjob.py#L27): cronjob tool: typed schedule, HH:MM pattern
  - [services/agent/src/autobots/domain/routines.py:33](../../../../services/agent/src/autobots/domain/routines.py#L33): API path validates the daily time with time.fromisoformat
  - [services/agent/src/autobots/contracts/routines.py:30](../../../../services/agent/src/autobots/contracts/routines.py#L30): limit ge=0, no upper bound, plain int
  - [services/agent/src/autobots/contracts/cronjob.py:51](../../../../services/agent/src/autobots/contracts/cronjob.py#L51): limit capped at 1_000_000
  - [services/agent/src/autobots/application/cronjob_tool.py:45-60](../../../../services/agent/src/autobots/application/cronjob_tool.py#L45): converts the typed schedule back into the untyped dict
  - [services/agent/src/autobots/application/routines.py:73](../../../../services/agent/src/autobots/application/routines.py#L73): Routines API validation entry
  - [services/agent/src/autobots/domain/routines.py:8](../../../../services/agent/src/autobots/domain/routines.py#L8): DEFAULT_TIMEZONE is unused; both contracts repeat the literal
- **Evidence:** RoutineConfig (Routines API) types `trigger: dict[str, Any]`, `timezone: str = "America/Costa_Rica"` and `limit_micro_usd: int = Field(default=1_000_000, ge=0)`, and domain.routines.validate_trigger checks the trigger. CronjobTask (cronjob tool) types the schedule (`time` pattern `^([01][0-9]|2[0-3]):[0-5][0-9]$`), bounds the timezone to 1-64 characters and caps the limit at 1_000_000. Re-run in memory: validate_trigger accepts "0730", "07", "07:30:45", "T07:30" and "07:30+05:00", which the tool refuses, and it accepts extra keys. occurrences() schedules "07:30+05:00" at 13:30 UTC, the same instant as "07:30", so the offset is silently ignored (datetime.combine replaces it with the routine's zone). RoutineConfig accepts limit_micro_usd=2**60. The generated client publishes `trigger: Record<string, unknown>` ([packages/api-client/src/generated.ts:8460](../../../../packages/api-client/src/generated.ts#L8460)). DEFAULT_TIMEZONE has no reader.
- **Why it matters:** Decision 0026 C5 promises the tool 'the same rules as the Routines API', including that 'the budget is capped and the trigger and timezone are checked'. Today the API is laxer: it can store triggers and budgets the tool would refuse, and the web client gets no type for the trigger. Every routine rule has to be changed in two places.
- **Recommendation:** Make the typed schedule the single trigger definition. Move CronjobSchedule into contracts/routines.py without renaming it, so the cronjob v1 input schema stays byte-identical, and use it for RoutineConfig.trigger, dumping with exclude_none so stored triggers keep today's shape. Share one IANA timezone alias with a known-zone check, and use DEFAULT_TIMEZONE. Type the API's limit as MicroUsd now. Whether the API should also take the tool's US$1 cap is for the owner to decide: today the API accepts more, and admission caps each run at the workspace's run limit (US$5 by default since migration 20261108000044). In the domain, parse the stored mapping once into typed triggers so occurrences() takes a typed value. Existing stored triggers that the stricter type refuses must still read, so land this after PDOM-01 (lenient stored records) or add a forward data migration.
- **Rule check:** Decision 0026 C5 ('Same rules as the Routines API') and DH-06 'explicit enums/unions'. The generated client is regenerated, never edited. Stored rows change only through a forward migration. A shared budget cap for the API is an owner decision, not part of this refactor.
- **Verification:** revised. Re-ran the trigger and limit checks in memory and confirmed every claim. Revised the recommendation so the moved class keeps its name (a rename would change the cronjob schema) and so the API's cap is left to the owner, because admission already honors limits up to the workspace run limit.

```text
contracts/routines.py
  class CronjobSchedule(BaseModel)   # moved unchanged from contracts/cronjob.py, so the cronjob v1 schema doesn't move
  IanaTimezone = Annotated[str, Field(min_length=1, max_length=64), AfterValidator(known_zone)]
  class RoutineConfig: trigger: CronjobSchedule; timezone: IanaTimezone = DEFAULT_TIMEZONE; limit_micro_usd: MicroUsd
contracts/cronjob.py: CronjobTask.schedule: CronjobSchedule (imported); timezone: IanaTimezone
domain/routines.py
  @dataclass(frozen=True) class IntervalTrigger: minutes: int
  @dataclass(frozen=True) class DailyTrigger: at: time
  def parse_trigger(raw: Mapping[str, object]) -> IntervalTrigger | DailyTrigger   # raises TriggerInvalid(code)
  def occurrences(trigger, zone: ZoneInfo, after, until) -> list[datetime]
```

### <a id="pdom-03"></a>PDOM-03: Tool inputs accept naive `since` datetimes, which the GitHub adapter cannot compare

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** medium · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/contracts/tools.py:86](../../../../services/agent/src/autobots/contracts/tools.py#L86): GithubListPullRequestsInput.since: datetime | None (naive allowed)
  - [services/agent/src/autobots/contracts/tools.py:115](../../../../services/agent/src/autobots/contracts/tools.py#L115): same type on the workflow-runs input, used only through .date(), so it works naive
  - [services/agent/src/autobots/adapters/github_reads.py:47-50](../../../../services/agent/src/autobots/adapters/github_reads.py#L47): _after: aware >= naive raises TypeError
  - [services/agent/src/autobots/adapters/github_reads.py:98](../../../../services/agent/src/autobots/adapters/github_reads.py#L98): comparison applied to every listed pull request
  - [services/agent/src/autobots/adapters/github_reads.py:209-211](../../../../services/agent/src/autobots/adapters/github_reads.py#L209): the GitHub reads are READ_ONLY with one retry
  - [services/agent/src/autobots/application/tool_gateway.py:410-431](../../../../services/agent/src/autobots/application/tool_gateway.py#L410): _read: an unexpected exception becomes FAILED tool_failed after the retries
- **Evidence:** `since: datetime | None = None` sits under TOOL_CONTRACT, which is not strict. In memory, GithubListPullRequestsInput.model_validate({"since": "2026-11-01"}) and "2026-11-01T00:00:00" both give tzinfo=None, and _after("2026-11-05T00:00:00Z", since) then raises `TypeError: can't compare offset-naive and offset-aware datetimes`. The GitHub read tools are READ_ONLY with retries=1, so the gateway's _read path catches the TypeError as a generic exception, repeats the GitHub call once and returns ToolOutcome.FAILED with code tool_failed. Reads keep no receipt. The published schema says only `format: date-time`. No test passes `since` (none in services/agent/tests or tests/db).
- **Why it matters:** A natural date-only filter from the model costs a second GitHub request and ends in a generic tool_failed the model can't repair, instead of a filtered list or an invalid_arguments refusal. The timezone rule belongs in the contract, not in each adapter.
- **Recommendation:** Add a UTC input primitive next to UtcTimestamp that treats a naive value as UTC, or refuses it if a repairable validation error is preferred; pick one and state it in the field description. Use it for both `since` fields, and add github_reads tests for date-only, naive and offset inputs. An AfterValidator leaves the JSON Schema unchanged, so no tool version change should follow; a reviewer should confirm that against domain/execution.py.
- **Rule check:** DH-06 'Use timezone-aware UTC dates' and 'Validate data at trust boundaries'. The schema is unchanged, so the tool-version table in domain/execution.py should not move. Nothing here weakens the URL guard or approvals.
- **Verification:** revised. Reproduced the TypeError in memory, but the cited gateway lines (542-544) belong to the effect path. These tools are READ_ONLY, so _read turns the error into FAILED tool_failed after one retry, with no receipt. Evidence corrected, and severity lowered to medium because the read fails closed and the fix is small.

```text
contracts/primitives.py
  def _assume_utc(value: datetime) -> datetime:
      return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
  UtcInput = Annotated[datetime, AfterValidator(_assume_utc)]
contracts/tools.py
  since: UtcInput | None = Field(default=None, description="ISO 8601. Without an offset, UTC.")
services/agent/tests/test_github_reads.py: since="2026-11-01" filters by updated_at; "+02:00" compares as an instant
```

### <a id="pdom-04"></a>PDOM-04: At least 23 response fields are typed looser than vocabularies that already exist

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** high · **Occurrences** 23
- **Where:**
  - [services/agent/src/autobots/contracts/approvals.py:68](../../../../services/agent/src/autobots/contracts/approvals.py#L68): status: str; SQL allows pending, approved, rejected, expired, withdrawn
  - [services/agent/src/autobots/contracts/routines.py:58](../../../../services/agent/src/autobots/contracts/routines.py#L58): occurrence_time: str; status: str at :60 (SQL: admitted, missed, skipped_overlap, blocked)
  - [services/agent/src/autobots/contracts/run_workspace.py:267](../../../../services/agent/src/autobots/contracts/run_workspace.py#L267): ToolAttemptView.status: str (SQL: started, succeeded, failed, unknown)
  - [services/agent/src/autobots/contracts/workflows.py:233](../../../../services/agent/src/autobots/contracts/workflows.py#L233): ExecutionView.run_status: str although RunStatus exists
  - [services/agent/src/autobots/contracts/operations.py:71](../../../../services/agent/src/autobots/contracts/operations.py#L71): plain datetime accepts naive values (also :81)
  - [services/agent/src/autobots/contracts/settings.py:46](../../../../services/agent/src/autobots/contracts/settings.py#L46): plain datetime (also :119)
  - [services/agent/src/autobots/application/routines.py:107](../../../../services/agent/src/autobots/application/routines.py#L107): caller formats the timestamp by hand, without UTC conversion
  - [apps/web/components/workflow-monitor.tsx:13](../../../../apps/web/components/workflow-monitor.tsx#L13): web re-declares the run terminal set over run_status: string
- **Evidence:** 14 status, kind or source fields are `str` although an SQL check constraint or a sibling contract fixes their values: ApprovalView.status, ApprovalResult.status, OccurrenceView.status (DelayedOccurrence already uses a Literal for it), ModelCallView.status, ToolAttemptView.status, InstanceView.status, WorkflowExecutionSummary.status, ExecutionView.run_status, ReplayRunView.status, CandidateView.kind and KnowledgeHead.kind (Literal["memory","skill"] exists), CandidateView.status ([supabase/migrations/20261105000022_improvements.sql:12](../../../../supabase/migrations/20261105000022_improvements.sql#L12)), EvidenceView.kind and WorkflowVersionView.source. 9 timestamps are `str` (approvals.py:69, :81; routines.py:58; workflows.py:98, :126) or plain `datetime` (operations.py:71, :81; settings.py:46, :119), while 13 fields use UtcTimestamp. Counted by reading every contract module and checking each field against the migrations' check constraints. Callers format timestamps differently: routines.py:107 `item[0].isoformat()`, workflow_overview.py:45 `.astimezone(UTC).isoformat()`.
- **Why it matters:** The generated client types these as `string`, so the web re-declares vocabularies by hand (workflow-monitor.tsx:13 `new Set(["succeeded", "failed", "cancelled"])`), and a new or misspelled value passes both sides unnoticed. Each caller decides the timestamp format.
- **Recommendation:** Type each field with the vocabulary that exists: RunStatus for run statuses, the Literal the sibling contract already uses, and new Literal aliases for the SQL-backed sets. Use UtcTimestamp for all 9 timestamps so callers pass datetimes. Keep `str` only where history can hold retired values, such as FrozenBinding.profile and ToolUseView.provider, and say so in a comment. Follow adapters.py: an unknown stored value raises instead of reaching a client. Then regenerate the client and remove the web's hand-made sets.
- **Rule check:** contracts.md: canonical states are shared, and unknown enum values need defined behavior. [contracts/adapters.py:9](../../../../services/agent/src/autobots/contracts/adapters.py#L9) already fails closed on an unknown run status. The TypeScript client is regenerated, never hand-edited.
- **Verification:** revised. Rechecked every listed field against the migrations' check constraints and sibling Literals. Added CandidateView.status, which has an SQL check constraint, so the total is 23, not 22.

### <a id="pdom-05"></a>PDOM-05: Strictness is chosen per model and is off in 22 of 30 request bodies, so MicroUsd accepts strings and floats where requests arrive

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** high · **Occurrences** 22
- **Where:**
  - [services/agent/src/autobots/contracts/primitives.py:17](../../../../services/agent/src/autobots/contracts/primitives.py#L17): 'Floats and strings are refused by strict validation'
  - [services/agent/src/autobots/contracts/run_commands.py:16](../../../../services/agent/src/autobots/contracts/run_commands.py#L16): RunRequest is lax, inline config
  - [services/agent/src/autobots/contracts/run_commands.py:24](../../../../services/agent/src/autobots/contracts/run_commands.py#L24): MicroUsd inside a lax model accepts "5000000" and 5000000.0
  - [services/agent/src/autobots/contracts/routines.py:30](../../../../services/agent/src/autobots/contracts/routines.py#L30): money as plain int, accepts 2**60
  - [services/agent/src/autobots/contracts/routines.py:52](../../../../services/agent/src/autobots/contracts/routines.py#L52): RoutineEnabled.enabled accepts "no" and "off"
  - [services/agent/src/autobots/contracts/improvements.py:133](../../../../services/agent/src/autobots/contracts/improvements.py#L133): ReplayRequest accepts "250000"
  - [services/agent/src/autobots/contracts/approvals.py:9](../../../../services/agent/src/autobots/contracts/approvals.py#L9): VIEW config, one of 9 module copies plus 9 inline
  - [services/agent/src/autobots/application/routines.py:383](../../../../services/agent/src/autobots/application/routines.py#L383): the routine's limit becomes the run's limit, which RunSummary later refuses above MAX_SAFE_INTEGER
- **Evidence:** Only 8 of the 30 request-body models use STRICT_CONTRACT; the count comes from the OpenAPI requestBody refs and each model's model_config. Observed in memory: RunRequest accepts limit_micro_usd "5000000" and 5000000.0, ReplayRequest accepts "250000", RoutineEnabled accepts enabled="no" or "off", and RoutineConfig accepts limit_micro_usd=2**60, above MAX_SAFE_INTEGER. That last one passes because 18 money fields are plain `int`; only 6 use MicroUsd. application/routines.py:383 hands that limit to admit_run, and the admitted run's RunSummary then fails strict validation (BudgetCounters refuses it, checked in memory), so that run's summary and workspace views would error. The shared fixtures refuse 'bad money: a numeric string' for RunSummary only. The configuration is also copied: `VIEW = ConfigDict(extra="forbid", frozen=True)` is defined in 9 modules and inlined 9 more times, and TOOL_CONTRACT lives in the 474-line contracts/tools.py (line 12), which 10 contract modules import for it.
- **Why it matters:** The money rule the primitive documents holds only for responses, the opposite of where it matters. An amount above 2^53 can be stored, later lose precision in the browser, and break the views of the run it funds. Each new module re-declares its config, so the three conventions drift apart.
- **Recommendation:** Put strictness on the primitives rather than the models: MicroUsd = Annotated[int, Strict(), Field(ge=0, le=MAX_SAFE_INTEGER)], plus strict bool and count aliases. Lax models still parse UUID, enum and datetime strings. Use MicroUsd for all 18 money fields. Define STRICT_CONTRACT, TOOL_CONTRACT and one lax config once in primitives.py, and name the lax one for what it is rather than VIEW, since request bodies use it too. Add money and boolean cases for RunRequest to the shared fixtures.
- **Rule check:** DH-06 'choose explicit coercion/strictness per field' and 'exact decimal or integer monetary units'; primitives.py:12 states the JavaScript bound. Strict() leaves the JSON Schema unchanged. Adding the MAX_SAFE_INTEGER bound to money fields changes OpenAPI, so the client is regenerated.
- **Verification:** revised. Recounted 30 request-body models (8 strict), 18 plain-int and 6 MicroUsd money fields, and 9 VIEW copies plus 9 inline configs, and reproduced the coercions in memory. Added the run-summary failure a 2**60 routine limit causes, and raised the change risk to high because the fix changes what public request bodies accept.

```text
contracts/primitives.py
  STRICT_CONTRACT, LAX_CONTRACT = ConfigDict(extra="forbid", frozen=True), TOOL_CONTRACT = LAX + allow_inf_nan=False
  MicroUsd = Annotated[int, Strict(), Field(ge=0, le=MAX_SAFE_INTEGER)]
  Flag = StrictBool; Count = Annotated[int, Strict(), Field(ge=0)]
```

### <a id="pdom-06"></a>PDOM-06: Contract Literals re-declare nine domain enums by hand in 10 places, with no parity check

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 10
- **Where:**
  - [services/agent/src/autobots/contracts/tools.py:263-287](../../../../services/agent/src/autobots/contracts/tools.py#L263): ToolGroupName, ToolProviderName, OperationClassName, AvailabilityName, GrantSiteName
  - [services/agent/src/autobots/contracts/tools.py:342](../../../../services/agent/src/autobots/contracts/tools.py#L342): side_effects and cost_class (:344) inline Literals
  - [services/agent/src/autobots/contracts/runs.py:108](../../../../services/agent/src/autobots/contracts/runs.py#L108): ToolUseCompleted.outcome repeats ToolOutcome (also ToolUseView.outcome at :175)
  - [services/agent/src/autobots/domain/tool_catalog.py:15-92](../../../../services/agent/src/autobots/domain/tool_catalog.py#L15): the StrEnums they mirror
  - [services/agent/src/autobots/contracts/experts.py:24](../../../../services/agent/src/autobots/contracts/experts.py#L24): max_length=12 sized to US-14.2's 12 groups; 13 since US-14.19
  - [services/agent/src/autobots/application/tool_catalog.py:217](../../../../services/agent/src/autobots/application/tool_catalog.py#L217): cast(list[GrantSiteName], ...)
  - [services/agent/src/autobots/domain/tool_catalog.py:115-126](../../../../services/agent/src/autobots/domain/tool_catalog.py#L115): grant_sites returns list[str] from enum .value
  - [services/agent/src/autobots/contracts/run_workspace.py:142-144](../../../../services/agent/src/autobots/contracts/run_workspace.py#L142): FrozenBinding.source repeats BindingSource, which contracts/models.py:25 uses directly
- **Evidence:** Five aliases and two inline Literals in contracts/tools.py mirror OperationClass and the catalog StrEnums (ToolGroup, ToolProvider, ToolAvailability, GrantSite, SideEffect, CostClass). FrozenBinding.source repeats BindingSource, and ToolUseCompleted.outcome and ToolUseView.outcome repeat domain.tools.ToolOutcome. That is nine enums in 10 places. No test compares a Literal with its enum; test_tool_catalog.py catches only a value that a registered tool actually uses, because ToolDescriptor is strict. A magic size has already gone stale: ExpertConfig.tool_groups got `max_length=12` in commit d96d488 (US-14.2), when ToolGroupName had 12 members, and kept it when ff158fb (US-14.19) added `automation`. It doesn't bind today only because planning and delegation have no Expert-grantable tools, so an Expert can name at most 11 groups. The catalog mapping needs a cast because grant_sites returns strings.
- **Why it matters:** Adding a group, provider, grant site or binding source means editing two declarations plus magic numbers. A missed Literal shows up as a validation error when the catalog or a run view is built, and only if something exercises that value, not as a type error.
- **Recommendation:** Use the domain StrEnums in the contracts, as RunStatus, ModelProfileId and BindingSource already are elsewhere. If inline enums are preferred in OpenAPI, keep the Literals and add a parity test for each pair (`set(get_args(ToolGroupName)) == set(ToolGroup)`). Replace `max_length=12` with `len(ToolGroup)`, and have grant_sites return list[GrantSite] so the cast goes away.
- **Rule check:** DH-06 'Avoid ... duplicated business rules' and the shared canonical vocabularies in contracts.md. Switching to enums renames generated schema types, so the client is regenerated, not edited; the parity-test option changes no contract.
- **Verification:** revised. Confirmed the history with git show. Corrected the count (ToolOutcome is mirrored twice in contracts/runs.py, so nine enums in 10 places, not seven) and noted that the stale max_length doesn't bind today and that catalog tests catch a value a tool actually uses.

### <a id="pdom-07"></a>PDOM-07: Tool input types under-declare their constraints, so the model never sees them

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** high · **Occurrences** 8
- **Where:**
  - [services/agent/src/autobots/contracts/market_tools.py:11](../../../../services/agent/src/autobots/contracts/market_tools.py#L11): Symbol = str; regex hidden in a model validator at :24
  - [services/agent/src/autobots/contracts/web_tools.py:14-15](../../../../services/agent/src/autobots/contracts/web_tools.py#L14): Domain = str and HttpsUrl = str constrain nothing
  - [services/agent/src/autobots/contracts/web_tools.py:57](../../../../services/agent/src/autobots/contracts/web_tools.py#L57): urls items unbounded; a 100,000-character item passes
  - [services/agent/src/autobots/contracts/browsing.py:42](../../../../services/agent/src/autobots/contracts/browsing.py#L42): DOMAIN_PATTERN checked inside a model validator
  - [services/agent/src/autobots/contracts/assignments.py:11](../../../../services/agent/src/autobots/contracts/assignments.py#L11): UUID as a 36-character string (also improvements.py:17, memory.py:60)
  - [services/agent/src/autobots/application/assignments.py:94-96](../../../../services/agent/src/autobots/application/assignments.py#L94): re-parses the UUID and maps ValueError to a ToolFailed code
  - [services/agent/src/autobots/contracts/tools.py:212](../../../../services/agent/src/autobots/contracts/tools.py#L212): second copy of the repository path validator (first at :181)
- **Evidence:** Eight tool-input fields show a bare string in the published schema while their real rule lives in a validator, in the adapter, or nowhere: MarketHistoryInput.symbols (regex in a model validator), TavilySearchInput.include_domains and exclude_domains (Domain = str, checked nowhere), TavilyExtractInput.urls and the Map, Crawl and ExtractWebsite `url` fields (HttpsUrl = str; https is enforced only by the adapter's URL guard), and BrowseGoalInput.allowed_domains (DOMAIN_PATTERN in a model validator). TavilyExtractInput accepted a 100,000-character URL item in memory, although web_tools.py:3 says 'Ceilings are in the schema'. Three ID fields are 36-character strings, while the newer cronjob.py:44 uses Identifier, so application/memory.py:167-169 and application/assignments.py:94-96 parse them again. Constraints are also copied: `path: str = Field(min_length=1, max_length=500, ...)` is written 11 times in three modules (6 plain, 3 with ^outputs/, 2 with the repository pattern), and the GitHub title and body bounds 3 times (tools.py:49-50, :68-69, :223-224).
- **Why it matters:** The model and the Tools page see input schemas without their real limits, so a valid call depends on a retry. The same concept is validated at different layers, and changing a limit means finding every copy.
- **Recommendation:** Declare tool field types once, as Annotated aliases with the constraint in the schema: Symbol, DomainName (move DOMAIN_PATTERN out of browsing.py), HttpsUrl (length plus a ^https:// pattern), RunFilePath, OutputPath, RepoPath (with the climb-out validator), IssueTitle and IssueBody. Use Identifier for IDs. Keep the URL guard and the cross-field validators. Handle any schema change under the tool-version policy in domain/execution.py.
- **Rule check:** DH-06 'Validate data at trust boundaries'. The adapter's URL guard stays: schema constraints are added alongside it, not instead of it. domain/execution.py's version table and compatible-change list decide whether a tool version moves.
- **Verification:** revised. Recounted the fields, the 11 path copies and the 3 ID strings, and reproduced the 100,000-character URL. Clarified that the domain lists are checked nowhere, and raised the change risk to high because tool schemas are versioned against saved runs.

### <a id="pdom-08"></a>PDOM-08: Typed persistence rows exist for one entity; elsewhere DTOs are built from positional tuples

- **Severity** medium · **Dimension** approach · **Effort** L · **Risk** medium · **Occurrences** 353
- **Where:**
  - [services/agent/src/autobots/persistence/rows.py:8](../../../../services/agent/src/autobots/persistence/rows.py#L8): RunRow, the only row type
  - [services/agent/src/autobots/contracts/adapters.py:8](../../../../services/agent/src/autobots/contracts/adapters.py#L8): row to domain to DTO mapping, for runs only
  - [services/agent/src/autobots/application/run_projection.py:120](../../../../services/agent/src/autobots/application/run_projection.py#L120): the one typed use needs type: ignore[arg-type]
  - [services/agent/src/autobots/application/workflow_overview.py:42](../../../../services/agent/src/autobots/application/workflow_overview.py#L42): charged_micro_usd=int(row[7]); row[0]..row[9] in one function
  - [services/agent/src/autobots/application/routines.py:107](../../../../services/agent/src/autobots/application/routines.py#L107): item[0]..item[4] mapped inline into OccurrenceView
  - [services/agent/src/autobots/adapters/checkpoints.py:70](../../../../services/agent/src/autobots/adapters/checkpoints.py#L70): the only psycopg row_factory in the service
- **Evidence:** persistence/ defines one TypedDict. Its only production use builds it from `dict(zip(_NAMES, row[:-1], strict=True))` and needs a type ignore. Everywhere else, DTOs are constructed inline from positional tuples. grep -rEo '\b(row|item|found|record)\[[0-9]+\]' counts 353 positional reads in 41 modules of application/, api/ and operations/. The count is approximate, since other variable names are missed.
- **Why it matters:** Adding or reordering a SELECT column silently shifts every positional read after it, and mypy cannot help because rows are Any. That the one typed path needs a type ignore suggests the pattern was never made easy to follow.
- **Recommendation:** Use psycopg's class_row (or dict_row with TypedDicts) per query. Keep one typed row type per table or read model, and map rows to DTOs in named functions, as contracts/adapters.py does for runs. Start with modules that index past row[5], and track the remaining positional reads as a ratchet count.
- **Rule check:** DH-06 'Distinguish ... persistence rows, public DTOs'. Rows stay distinct from DTOs and are not merged; this only makes the mapping explicit. DH-03 lists no persistence/ package, so where rows live is for the sweep-boundaries lens to settle.
- **Verification:** confirmed. Re-ran the grep (353 reads in 41 modules) and confirmed RunRow's single, type-ignored use. PRUN-12 reports the same pattern inside the run modules.

### <a id="pdom-09"></a>PDOM-09: The workflow domain runs on untyped mappings and bare strings

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** medium · **Occurrences** 29
- **Where:**
  - [services/agent/src/autobots/domain/workflow_execution.py:12](../../../../services/agent/src/autobots/domain/workflow_execution.py#L12): TERMINAL instance statuses as strings
  - [services/agent/src/autobots/domain/workflow_execution.py:72](../../../../services/agent/src/autobots/domain/workflow_execution.py#L72): Step.decision: str (run, skipped, blocked)
  - [services/agent/src/autobots/domain/workflow_execution.py:78](../../../../services/agent/src/autobots/domain/workflow_execution.py#L78): GraphShape.nodes: Mapping[str, Mapping[str, Any]]
  - [services/agent/src/autobots/domain/workflows.py:105](../../../../services/agent/src/autobots/domain/workflows.py#L105): block, config, name read by string subscripts
  - [services/agent/src/autobots/domain/workflows.py:214](../../../../services/agent/src/autobots/domain/workflows.py#L214): validate_graph(graph: Mapping[str, Any])
  - [services/agent/src/autobots/application/workflow_runner.py:261-263](../../../../services/agent/src/autobots/application/workflow_runner.py#L261): the runner writes the same status strings
  - [supabase/migrations/20261105000019_workflow_execution.sql:9](../../../../supabase/migrations/20261105000019_workflow_execution.sql#L9): the only closed list of instance statuses
- **Evidence:** The two workflow modules use `Any` 29 times in annotations (31 occurrences with the two imports) and 56 string-key subscripts on nodes and links (52 on `node[...]` or `link[...]`, 4 on `nodes[...]["block"]`). Block names ("foreach", "join", "input", ...), instance statuses, source states ("waiting", "ready") and step decisions are string literals compared across both modules and the runner. Counted with grep over domain/workflows.py and domain/workflow_execution.py.
- **Why it matters:** A misspelled block name or status takes a wrong branch silently instead of failing a type check, and adding a block means touching string comparisons in both modules and the runner. domain/runs.py, where RunStatus makes the same kind of logic checkable, is the contrast.
- **Recommendation:** Parse the canonical graph once into frozen domain types (Node, Link, Graph), with Block and InstanceStatus StrEnums and a Decision Literal. Keep ir_normalized, canonical and graph_hash working on the normalized dict, so stored hashes do not change. validate_graph and next_steps then read attributes.
- **Rule check:** DH-06 'explicit enums/unions'. graph_hash stability and IR versioning must hold. The domain types stay separate from the WorkflowGraph DTO and are mapped explicitly, not merged.
- **Verification:** revised. Recounted with grep: 29 Any annotations rather than 31 (two were imports) and 56 subscripts rather than 55. The finding stands.

```text
domain/workflows.py
  class Block(StrEnum): INPUT, OUTPUT, TRANSFORM, CONDITION, FOREACH, JOIN, READ, ARTIFACT, APPROVAL, AGENT
  @dataclass(frozen=True) class Node: id; block: Block; version: int; config: Mapping[str, object]; label: str | None
  @dataclass(frozen=True) class Link: source; source_port; target; target_port
  def parse_graph(normalized: Mapping[str, object]) -> Graph   # hashing stays on the normalized dict
domain/workflow_execution.py: class InstanceStatus(StrEnum); Decision = Literal["run", "skipped", "blocked"]
```

### <a id="pdom-10"></a>PDOM-10: Workflow validation and scheduling concentrate the area's complexity

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/domain/workflows.py:214-289](../../../../services/agent/src/autobots/domain/workflows.py#L214): validate_graph: 76 lines, C901 21, 20 branches
  - [services/agent/src/autobots/domain/workflows.py:104-125](../../../../services/agent/src/autobots/domain/workflows.py#L104): _config_errors: C901 11, 9 returns
  - [services/agent/src/autobots/domain/workflows.py:145-196](../../../../services/agent/src/autobots/domain/workflows.py#L145): _iteration_errors: C901 11
  - [services/agent/src/autobots/domain/workflows.py:76-93](../../../../services/agent/src/autobots/domain/workflows.py#L76): _resolved_type: 6 positional parameters
  - [services/agent/src/autobots/domain/workflow_execution.py:199-234](../../../../services/agent/src/autobots/domain/workflow_execution.py#L199): next_steps: C901 14, 13 branches
  - [services/agent/src/autobots/domain/workflow_execution.py:227](../../../../services/agent/src/autobots/domain/workflow_execution.py#L227): item count repeated from _decide_join at :185
  - [services/agent/tests/test_workflows.py:152](../../../../services/agent/tests/test_workflows.py#L152): first of nine exact error-list assertions
- **Evidence:** Measured by ruff with max-complexity 10 (metrics.md), confirmed by reading. validate_graph runs seven phases inline: version, labels, node index, block specs and config, links, arity and presence, then cycle and iteration. _config_errors is an if-chain over block names. next_steps handles joins, top-level nodes and foreach bodies in one loop, and repeats `sum(1 for (key, port, _) in emissions if key == foreach and port == "item")`.
- **Why it matters:** Every new block or rule lands in the longest function in the domain. Nine assertions in test_workflows.py compare exact error-code lists (one of them parametrized), so the phase order is observable behavior and has to survive any change.
- **Recommendation:** Split validate_graph by phase, keeping the early returns and the error order. Drive per-block config checks from a table keyed by block. Pass a parameter object to _resolved_type. Split next_steps by node kind, with a shared _item_count.
- **Rule check:** DH-06 'small cohesive modules'. No complexity rule is configured yet (PDOM-15). Error order is asserted by tests and must not change.
- **Verification:** revised. Line ranges and complexity figures match metrics.md. The test count is nine exact-list assertions, not eight; nothing else changed.

```text
def validate_graph(graph):
    if refused := _version_error(graph): return [refused]
    nodes, index_errors = _index_nodes(graph)
    specs, spec_errors = _resolve_specs(nodes)          # _CONFIG_CHECKS[block](node) -> GraphError | None
    if errors := _label_errors(graph) + index_errors + spec_errors: return errors
    wiring = _check_links(graph, TypeContext(nodes, specs, feeds))   # errors, linked, successors
    if errors := wiring.errors + _arity_errors(wiring.linked, specs) + _presence_errors(nodes): return errors
    return [GraphError("cycle_not_supported")] if _has_cycle(...) else _iteration_errors(nodes, wiring.successors)
def next_steps(shape, statuses, emissions): flat map over shape.order of _join_steps / _top_level_steps / _foreach_body_steps
```

### <a id="pdom-12"></a>PDOM-12: Transform and predicate vocabularies are declared three times, with nothing tying them together

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/domain/workflows.py:19](../../../../services/agent/src/autobots/domain/workflows.py#L19): TRANSFORMS decides what validates
  - [services/agent/src/autobots/domain/workflows.py:20](../../../../services/agent/src/autobots/domain/workflows.py#L20): PREDICATES
  - [services/agent/src/autobots/domain/workflows.py:65-71](../../../../services/agent/src/autobots/domain/workflows.py#L65): TRANSFORM_OUTPUTS decides output types
  - [services/agent/src/autobots/domain/workflow_execution.py:23-39](../../../../services/agent/src/autobots/domain/workflow_execution.py#L23): run_transform if-chain over the same names
  - [services/agent/src/autobots/domain/workflow_execution.py:48-62](../../../../services/agent/src/autobots/domain/workflow_execution.py#L48): run_predicate if-chain
  - [services/agent/tests/test_workflow_execution.py:181](../../../../services/agent/tests/test_workflow_execution.py#L181): parametrized over 4 of 6 transforms
- **Evidence:** Three declarations hold one vocabulary across two modules. Tests run upper, lower, length and sum directly (test_workflow_execution.py:181-186). identity runs only inside the golden-graph helper, to_string never executes in a test, and of the five predicates only greater_than does. No test checks that every validated name executes.
- **Why it matters:** Adding a name to TRANSFORMS without an execution branch lets a graph publish and then fail at run time with transform_operation_unknown. The reverse leaves dead branches.
- **Recommendation:** Keep one table per vocabulary in the domain: TRANSFORMS: Mapping[str, Transform(output_type, apply)] and PREDICATES: Mapping[str, Callable[[Any, Any], bool]]. Validation reads the keys, _resolved_type reads output_type, and execution dispatches through the table. One parametrized test covers every key.
- **Rule check:** DH-06 'Avoid ... duplicated business rules'.
- **Verification:** revised. Confirmed the three declarations. Corrected the coverage claim: identity is exercised through the golden-graph helper, so only to_string and four of the five predicates never execute in a test.

### <a id="pdom-13"></a>PDOM-13: Coded refusals take four shapes, and the same constructor is written 13 times

- **Severity** medium · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 13
- **Where:**
  - [services/agent/src/autobots/domain/budgets.py:11](../../../../services/agent/src/autobots/domain/budgets.py#L11): __init__(self, code) sets self.code
  - [services/agent/src/autobots/domain/workflow_execution.py:15](../../../../services/agent/src/autobots/domain/workflow_execution.py#L15): the same constructor again
  - [services/agent/src/autobots/domain/routines.py:13](../../../../services/agent/src/autobots/domain/routines.py#L13): TriggerInvalid: the code is the message
  - [services/agent/src/autobots/application/routines.py:75](../../../../services/agent/src/autobots/application/routines.py#L75): RoutineRefused(str(invalid))
  - [services/agent/src/autobots/domain/models.py:83](../../../../services/agent/src/autobots/domain/models.py#L83): ProfileNotOffered: code on the class, a sentence in the message
  - [services/agent/src/autobots/domain/models.py:116-120](../../../../services/agent/src/autobots/domain/models.py#L116): UnknownModelProfile, which has no code, is also raised for an unknown role
  - [services/agent/src/autobots/domain/runs.py:76](../../../../services/agent/src/autobots/domain/runs.py#L76): CommandRefused: free text only
  - [services/agent/src/autobots/api/run_routes.py:86-89](../../../../services/agent/src/autobots/api/run_routes.py#L86): the API substitutes the constant transition_refused
- **Evidence:** grep 'def __init__(self, code: str' finds 13 classes in domain/, application/ and adapters/ that each set self.code by hand, with no shared base. Domain refusals carry their code as an instance attribute, as the message, as a class attribute, or not at all. api/settings_routes.py:323 maps UnknownModelProfile to unknown_model.
- **Why it matters:** Each route maps each exception by hand, and that is where codes and messages drift. A new refusal has no obvious shape to follow.
- **Recommendation:** Add domain/errors.py with `class Refused(Exception)` that holds a code and an optional internal detail. Make the domain refusals subclass it, and let application refusals reuse it, so the API can map the base class once. Keep every existing code and HTTP status.
- **Rule check:** DH-06 'centralize error handling ... expose safe typed errors'. Codes and statuses stay identical. The route-side mapping belongs to the api area.
- **Verification:** confirmed. Re-ran the grep (13 classes with the same constructor) and opened each cited refusal shape and both route mappings.

### <a id="pdom-14"></a>PDOM-14: Layer purity is declared but not enforced, and contracts/export.py already depends on the API

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/domain/__init__.py:1](../../../../services/agent/src/autobots/domain/__init__.py#L1): 'No framework, persistence or public DTO imports'
  - [services/agent/src/autobots/persistence/__init__.py:1](../../../../services/agent/src/autobots/persistence/__init__.py#L1): rule stated, not checked
  - [services/agent/src/autobots/contracts/export.py:9](../../../../services/agent/src/autobots/contracts/export.py#L9): contracts imports autobots.api.app.create_app
  - [scripts/generate_contracts.py:98](../../../../scripts/generate_contracts.py#L98): runs -m autobots.contracts.export
  - [services/agent/tests/test_model_policy.py:355-374](../../../../services/agent/tests/test_model_policy.py#L355): an existing AST import check to reuse
- **Evidence:** The domain complies today: every import is from the standard library or autobots.domain. Nothing checks it, though. export.py makes the contracts package, otherwise a leaf over domain and persistence, depend on the whole app factory. Only [scripts/generate_contracts.py:98](../../../../scripts/generate_contracts.py#L98) and [services/agent/tests/test_contracts.py:13](../../../../services/agent/tests/test_contracts.py#L13) reference the module. The repository already uses an AST walk to keep OpenRouter imports inside factory.py.
- **Why it matters:** One convenience import, such as a Pydantic model or a psycopg type in domain/, would pass review unnoticed. The inverted export module invites import cycles as the API grows.
- **Recommendation:** Move export.py into the API package (for example autobots.api.openapi_export) and update the script and test that call it. Then reuse the AST-walk pattern for a layering test: domain imports only the standard library and autobots.domain, persistence only the standard library, and contracts only the standard library, pydantic, autobots.contracts, autobots.domain and autobots.persistence.
- **Rule check:** DH-06 'Keep domain decisions independent of HTTP, Supabase clients and LangGraph internals'. Generation stays offline (contracts.md), still built from the pure app factory, just from the API package.
- **Verification:** confirmed. Confirmed the import at export.py:9 and that only two files reference the module, so the move is small.

### <a id="pdom-15"></a>PDOM-15: pyproject.toml enforces no size or complexity rule and leaves pydantic undeclared

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/pyproject.toml:47](../../../../services/agent/pyproject.toml#L47): select = E, F, W, I, B, UP, ASYNC, RUF
  - [services/agent/pyproject.toml:6-21](../../../../services/agent/pyproject.toml#L6): dependencies without pydantic
  - [services/agent/src/autobots/domain/workflows.py:214](../../../../services/agent/src/autobots/domain/workflows.py#L214): C901 21 passes the project check
- **Evidence:** The project ruff check exits 0, while ruff with C901 at 10 and the PLR size rules finds 9 violations in this area (metrics.md: 4 C901, 1 PLR0911, 2 PLR0912, 1 PLR0913, 1 PLR0917). 42 source modules import pydantic, and the contracts are built on it, but uv.lock resolves pydantic 2.12.5 only transitively, through fastapi, langchain-core, langgraph, openrouter and other packages.
- **Why it matters:** Complexity can only grow, and a lock refresh can move the contract engine without any visible pyproject change. DH-06 names Pydantic in the dependency set to qualify.
- **Recommendation:** Pin pydantic directly, and add the complexity rules with a baseline that ratchets down: `"pydantic==2.12.5"` in dependencies; select += ["C90", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]; [tool.ruff.lint.mccabe] max-complexity = 10; per-file-ignores listing today's offenders, each removed as its refactor lands.
- **Rule check:** DH-06 'Use Ruff for lint/format' and 'Qualify the combined LangGraph/Deep Agents/OpenRouter/Pydantic dependency set'. Updating the lock is an explicit dependency operation, never part of a check.
- **Verification:** confirmed. Checked pyproject.toml, the packages in uv.lock that depend on pydantic, the 42 importing modules and the 9 in-area violations listed in metrics.md.

### <a id="pdom-16"></a>PDOM-16: Cross-language contract fixtures cover 4 of 170 schemas and only one request body

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 29
- **Where:**
  - [contracts/fixtures/boundary-cases.json:1](../../../../contracts/fixtures/boundary-cases.json#L1): 29 cases: RunSummary 19, RunEvent 4, WorkflowGraph 4, ErrorResponse 2
  - [services/agent/tests/test_contracts.py:30-35](../../../../services/agent/tests/test_contracts.py#L30): the four models the fixtures exercise
  - [services/agent/src/autobots/contracts/run_commands.py:13](../../../../services/agent/src/autobots/contracts/run_commands.py#L13): RunRequest accepts the 'numeric string' money case that RunSummary refuses
  - [services/agent/src/autobots/contracts/operations.py:34](../../../../services/agent/src/autobots/contracts/operations.py#L34): RetentionSettings returned without schema_version
  - [services/agent/src/autobots/contracts/tools.py:377](../../../../services/agent/src/autobots/contracts/tools.py#L377): ToolVersions and ToolDescriptor returned without schema_version
- **Evidence:** The OpenAPI document has 170 schemas and 30 request-body models. WorkflowGraph is the only request body with shared cases, so 29 are uncovered. The money, timestamp, unknown-enum and private-field cases exist for RunSummary and RunEvent only. 3 of 51 route response models lack schema_version (RetentionSettings, ToolDescriptor, ToolVersions), and no test notices.
- **Why it matters:** Cross-language validation parity is proven for the responses, where coercion matters least. Request bodies, where it matters most, have no shared cases on either side.
- **Recommendation:** Extend the fixtures to request bodies first: RunRequest, RoutineCreate, ModelPolicyUpdate, ExecutionCreate and ApprovalDecision, with money, boolean, timestamp and unknown-enum cases. Add a contract test that every route response model carries schema_version.
- **Rule check:** contracts.md: 'Shared validation fixtures cover both languages, unknown enums and private-field leakage'.
- **Verification:** confirmed. Recomputed from contracts/generated/openapi.json (170 schemas, 30 request-body models, 51 response models) and from the fixture file (29 cases over four models).

### <a id="pdom-11"></a>PDOM-11: contracts/tools.py mixes three audiences in 474 lines; run_workspace.py holds three screens

- **Severity** low · **Dimension** size · **Effort** M · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/contracts/tools.py:16-260](../../../../services/agent/src/autobots/contracts/tools.py#L16): model-facing tool I/O: calculate, run file v1, GitHub issue v1/v2, GitHub reads and pull request, save artifact
  - [services/agent/src/autobots/contracts/tools.py:262-382](../../../../services/agent/src/autobots/contracts/tools.py#L262): web-facing catalog API
  - [services/agent/src/autobots/contracts/tools.py:384-454](../../../../services/agent/src/autobots/contracts/tools.py#L384): more tool I/O: run file v2, CSV, remote file
  - [services/agent/src/autobots/contracts/tools.py:456-474](../../../../services/agent/src/autobots/contracts/tools.py#L456): grants API
  - [services/agent/src/autobots/contracts/run_workspace.py:15-171](../../../../services/agent/src/autobots/contracts/run_workspace.py#L15): run workspace view
  - [services/agent/src/autobots/contracts/run_workspace.py:173-225](../../../../services/agent/src/autobots/contracts/run_workspace.py#L173): run list
  - [services/agent/src/autobots/contracts/run_workspace.py:227-305](../../../../services/agent/src/autobots/contracts/run_workspace.py#L227): run inspector
- **Evidence:** tools.py also exports TOOL_CONTRACT and MAX_FILE_CHARACTERS, which 10 contract modules import. Other tool families already have their own modules (web_tools, market_tools, code_tools, browsing, cronjob). run_workspace.py is declarative and cohesive around runs, but it holds three independent responses for three routes.
- **Why it matters:** A catalog change and a GitHub tool change edit the same file, and a new tool model has no obvious home. The run screens evolve independently but share one module.
- **Recommendation:** Split tools.py by audience and tool family; the run_workspace.py split is optional. Class names stay the same, so OpenAPI schema names and the generated client do not change; the drift check should show no difference.
- **Rule check:** DH-06 'small cohesive modules'. Schema names are class names, so the generated artifacts should not change; any change is regenerated, never edited.
- **Verification:** revised. Line ranges and importers confirmed. Lowered to low: the module is declarative, nothing breaks, and the friction is only where new tool models go; run_workspace.py's three screens are cohesive, so its split is marked optional.

```text
contracts/primitives.py     TOOL_CONTRACT, MAX_FILE_CHARACTERS (moved)
contracts/tool_catalog.py   vocabularies, FieldDescriptor ... ToolVersions, GrantedTo, ToolGrants
contracts/github_tools.py   CreateGithubIssue v1/v2, Github* inputs and outputs, MAX_PULL_REQUEST_BYTES
contracts/file_tools.py     ReadRunFile v1/v2, ReadCsv, CsvColumn, SaveArtifact, StoreRemoteFile, TextMediaType
contracts/tools.py          Calculate only
contracts/run_list.py       RunListGroup, RunListItem, RunGroupCounts, RunList   (optional)
contracts/run_inspector.py  ModelCallView, ToolAttemptView, CheckpointView, EvidenceView, RunInspector   (optional)
```

### <a id="pdom-17"></a>PDOM-17: Kahn's topological sort is written three times and the foreach region walk twice

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/domain/workflows.py:128-142](../../../../services/agent/src/autobots/domain/workflows.py#L128): _has_cycle
  - [services/agent/src/autobots/domain/workflows.py:292-311](../../../../services/agent/src/autobots/domain/workflows.py#L292): step_order
  - [services/agent/src/autobots/domain/workflow_execution.py:84-101](../../../../services/agent/src/autobots/domain/workflow_execution.py#L84): shape_of order
  - [services/agent/src/autobots/domain/workflows.py:153-179](../../../../services/agent/src/autobots/domain/workflows.py#L153): foreach region walk during validation
  - [services/agent/src/autobots/domain/workflow_execution.py:102-112](../../../../services/agent/src/autobots/domain/workflow_execution.py#L102): foreach owner walk during execution
- **Evidence:** Each sort builds in-degree counts and drains a deque. The copies differ slightly: set versus list successors, and different handling of leftover nodes. Both region walks follow a foreach's successors until a join.
- **Why it matters:** A fix to ordering, or to what counts as inside a foreach, must be repeated in each copy, and the small differences are undocumented.
- **Recommendation:** Write one topological_order(names, edges) -> (ordered, unordered) helper for all three uses, and share the common part of the region walk. Add a comment wherever validation and execution intentionally differ.
- **Rule check:** DH-06 'Avoid ... duplicated business rules'.
- **Verification:** confirmed. Opened all five walks; the differences in successor types and leftover handling are as stated.

### <a id="pdom-18"></a>PDOM-18: Colliding and misleading names in contracts and domain

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 6
- **Where:**
  - [services/agent/src/autobots/contracts/search.py:11](../../../../services/agent/src/autobots/contracts/search.py#L11): SearchResult (API)
  - [services/agent/src/autobots/contracts/web_tools.py:40](../../../../services/agent/src/autobots/contracts/web_tools.py#L40): SearchResult (tool)
  - [services/agent/src/autobots/contracts/search.py:23](../../../../services/agent/src/autobots/contracts/search.py#L23): SearchResults (API)
  - [services/agent/src/autobots/contracts/memory.py:28](../../../../services/agent/src/autobots/contracts/memory.py#L28): SearchResults (tool)
  - [services/agent/src/autobots/domain/runs.py:22](../../../../services/agent/src/autobots/domain/runs.py#L22): TERMINAL: set of RunStatus
  - [services/agent/src/autobots/domain/workflow_execution.py:12](../../../../services/agent/src/autobots/domain/workflow_execution.py#L12): TERMINAL: set of instance-status strings
  - [services/agent/src/autobots/contracts/primitives.py:19](../../../../services/agent/src/autobots/contracts/primitives.py#L19): Sequence shadows collections.abc.Sequence
  - [services/agent/src/autobots/domain/models.py:116](../../../../services/agent/src/autobots/domain/models.py#L116): UnknownModelProfile raised for an unknown role
- **Evidence:** Two pairs of public classes share names across modules, two domain constants named TERMINAL hold different element types, the event sequence primitive is called Sequence, and contracts/adapters.py (row-to-DTO mappers) shares its name with the autobots.adapters package of external clients.
- **Why it matters:** Readers and autocomplete pick the wrong import. If both SearchResults classes reached the OpenAPI document, FastAPI would rename them and change the generated client types.
- **Recommendation:** Rename the tool-side models (WebSearchHit, MemorySearchResults), the workflow constant (INSTANCE_TERMINAL), the primitive (EventSequence) and the mapper module (contracts/mapping.py), and raise a separate UnknownModelRole for roles. None of the renamed tool models appears in the OpenAPI document today.
- **Rule check:** none
- **Verification:** confirmed. Confirmed each collision and that OpenAPI holds only the API-side SearchResult and SearchResults today.

### <a id="pdom-19"></a>PDOM-19: Some docstrings publish implementation notes as API documentation or describe history

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 10
- **Where:**
  - [services/agent/src/autobots/contracts/artifacts.py:30](../../../../services/agent/src/autobots/contracts/artifacts.py#L30): 'Not strict, since it is built from database values.'
  - [services/agent/src/autobots/contracts/run_commands.py:14](../../../../services/agent/src/autobots/contracts/run_commands.py#L14): also :42; published as the OpenAPI description
  - [services/agent/src/autobots/contracts/settings.py:124](../../../../services/agent/src/autobots/contracts/settings.py#L124): also experts.py:15
  - [services/agent/src/autobots/contracts/runs.py:1](../../../../services/agent/src/autobots/contracts/runs.py#L1): 'The initial public slice.'
  - [services/agent/src/autobots/contracts/service.py:1](../../../../services/agent/src/autobots/contracts/service.py#L1): 'Contracts for the first routes.'
  - [services/agent/pyproject.toml:4](../../../../services/agent/pyproject.toml#L4): 'minimal non-feature scaffold.'
  - [services/agent/src/autobots/domain/tools.py:26](../../../../services/agent/src/autobots/domain/tools.py#L26): describes propose_improvement but sits above PROVIDER_TOOLS
  - [services/agent/src/autobots/domain/workflow_execution.py:84](../../../../services/agent/src/autobots/domain/workflow_execution.py#L84): shape_of and GraphShape.owner undocumented
- **Evidence:** Pydantic publishes class docstrings as schema descriptions. contracts/generated/openapi.json carries 'Not strict...' as the description of ArtifactSummary, RunAccepted, RunRequest, ExpertConfig and ModelPolicyUpdate. Three docstrings describe the module's history rather than its contents. git blame shows the comment at domain/tools.py:26 dates from 2026-11-05, and PROVIDER_TOOLS was inserted under it on 2026-11-07. shape_of computes run order and foreach ownership with no docstring.
- **Why it matters:** API consumers read Pydantic configuration notes as API documentation, and readers have to reverse-engineer what `owner` means.
- **Recommendation:** Move strictness notes into `#` comments beside model_config, and keep consumer-facing facts in docstrings. Rewrite the three history docstrings to say what each module holds. Move the orphaned comment down to EXPERT_TOOLS' propose_improvement entry (line 40), and document shape_of's outputs.
- **Rule check:** DH-06 'Explain nonobvious invariants in code; avoid comments that restate syntax'. Decision and story citations stay (ground rule 2).
- **Verification:** confirmed. Confirmed the five published 'Not strict' descriptions in openapi.json and the blame dates for domain/tools.py:26-28.

### <a id="pdom-20"></a>PDOM-20: Grant allowlists and transition tables are mutable dicts; only models.py freezes its tables

- **Severity** low · **Dimension** approach · **Effort** S · **Risk** low · **Occurrences** 14
- **Where:**
  - [services/agent/src/autobots/domain/tools.py:16-63](../../../../services/agent/src/autobots/domain/tools.py#L16): PLAN, GENERAL, PROVIDER, EXPERT and LOOP grant maps, untyped dicts
  - [services/agent/src/autobots/domain/runs.py:24](../../../../services/agent/src/autobots/domain/runs.py#L24): NORMAL_EXITS dict
  - [services/agent/src/autobots/domain/runs.py:81](../../../../services/agent/src/autobots/domain/runs.py#L81): COMMANDS and COMMAND_SOURCES dicts
  - [services/agent/src/autobots/domain/tool_guides.py:16](../../../../services/agent/src/autobots/domain/tool_guides.py#L16): TOOL_GUIDES dict
  - [services/agent/src/autobots/domain/workflows.py:31](../../../../services/agent/src/autobots/domain/workflows.py#L31): BLOCKS typed Mapping, built as dict
  - [services/agent/src/autobots/domain/execution.py:15](../../../../services/agent/src/autobots/domain/execution.py#L15): TOOL_VERSIONS typed Mapping, built as dict
  - [services/agent/src/autobots/domain/models.py:39](../../../../services/agent/src/autobots/domain/models.py#L39): the contrast: MappingProxyType
- **Evidence:** 14 module-level dict tables in domain/ are mutable (5 grant maps, 3 run tables, TOOL_GUIDES, BLOCKS, TRANSFORM_OUTPUTS, TOOL_VERSIONS, GROUP_TITLES and SIDE_EFFECTS). models.py wraps PROFILES, NOT_OFFERED_MESSAGES and the RolePolicy maps in MappingProxyType (5 uses). grep finds no code that mutates the others today.
- **Why it matters:** The grant sets decide what a run may call. One accidental `EXPERT_TOOLS[name] = 1` in any importer would widen grants process-wide without a type error.
- **Recommendation:** Annotate these tables as Final Mapping types and wrap them in MappingProxyType, as models.py does. The tests that monkeypatch TOOL_GUIDES replace the attribute, so they keep working.
- **Rule check:** none. This matches domain/models.py's own immutability choice.
- **Verification:** confirmed. Counted 14 module-level dict tables and found no mutation in src or tests; the TOOL_GUIDES test replaces the attribute, as stated.

## Rejected during verification

None. Every finding held up at its cited lines and was kept; where counts, evidence, severity or risk changed, the finding is marked revised and its verification line says what changed.

## Not covered

The review is static reading plus read-only checks: python3.12 -I -B snippets that validated contract models in memory against the service's installed pydantic and wrote no files, and ruff in check mode with --no-cache. mypy, pytest and scripts/verify.py were not run, per the ground rules. Files in application/, api/ and adapters/ were read only at the call sites cited as evidence; their own quality belongs to other areas. docs/engineering/option-b-contract.md was not compared field by field with domain/runs.py. On the TypeScript side, only the generated client's trigger type and apps/web/components/workflow-monitor.tsx were checked. The counts of positional row reads (353) and stored-record read sites (16) come from grep patterns and may miss differently named variables. metrics.md and PRD-Development-Harness.md were read only in their relevant sections (DH-03, DH-06, and the Python measurements).
