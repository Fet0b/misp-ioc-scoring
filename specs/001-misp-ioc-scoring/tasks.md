# Tasks: Plataforma de Scoring e Compartilhamento de IOCs

**Input**: Design documents from `specs/001-misp-ioc-scoring/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/`, and `quickstart.md`

**Organization**: Tasks are grouped by user story to enable independently verifiable
increments. Automated tests are included because the project constitution requires
tests for affected behavior.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other marked tasks in the same ready phase because
  they modify different files and have no unresolved dependencies.
- **[Story]**: User-story label linked to `spec.md`.
- Every task names concrete file paths.

## Path Conventions

One Python package (modular monolith) at `src/misp_ioc_scoring/` with modules
`shared/`, `collection/`, `scoring/`, `sharing/` and container composition roots in
`entrypoints/`; migrations under `migrations/`; tests under `tests/`. In this file
`<pkg>` means `src/misp_ioc_scoring`. Module boundaries and table ownership are defined
in `plan.md` ("Arquitetura Modular"); each module writes only its own PostgreSQL schema
(`collection`, `scoring`, `sharing`) and reads other modules only through `api.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the Python project and three-container development environment.

- [ ] T001 Create `pyproject.toml` for Python 3.12 with runtime dependencies PyMISP, SQLAlchemy 2.x, Alembic, Pydantic, APScheduler 3.x, openpyxl (Excel export, FR-028) and development dependencies pytest and import-linter.
- [ ] T002 [P] Create `Dockerfile` using a non-root runtime user and separate commands for `<pkg>/entrypoints/collector.py` and `<pkg>/entrypoints/scoring_sharing.py`.
- [ ] T003 [P] Create `compose.yaml` with PostgreSQL, collector/normalizer and scoring/sharing services using distinct database roles (see T008), persistent database volume, health check, service dependency conditions, and per-service `env_file`/environment (peer settings only for the scoring/sharing service), plus a one-off `tools` service (compose profile `tools`) that runs `tools/export_observability.py` with the read-only `observer` role and a mounted output directory; there is no CLI, API or UI. Later tasks (T008, T005, T080) extend this file.
- [ ] T004 [P] Create `.dockerignore` and `.env.example` with configuration keys (including `MISP_TO_IDS_ONLY`, `RECONCILE_MAX_REMOVAL_RATIO`, `CARIOCA_TOP_N`, all time/frequency settings (per-endpoint collection cadence, daily scoring schedule, overlap windows, retry/backoff, `SCORE_MAX_AGE_HOURS` with default 48), the observability export settings (`EXPORT_OUTPUT_DIR`, `EXPORT_MAX_ROWS_PER_SHEET`), and the peer settings: peers, per-peer minimum score, secret references); `EXPORT_MAX_ROWS_PER_SHEET` defaults to 1000000 with a ceiling of 1048575. Later tasks (T008, T005, T080) extend this file. but no credentials, secret values, or implicit defaults for unapproved CARIOCA parameters.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared configuration, persistence, migration, error, module-boundary, and domain-language foundations required by every story.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [ ] T005 Implement validated environment/configuration loading in `<pkg>/shared/configuration.py`, keeping credentials as secret references, loading every operational time and frequency (per-endpoint collection cadence, daily scoring schedule, overlap windows, retry/backoff, `SCORE_MAX_AGE_HOURS` default 48, sharing run frequency and retries, `EXPORT_MAX_ROWS_PER_SHEET` default 1000000 and rejected above 1048575) from environment variables validated at startup, and rejecting missing or invalid required settings with an explicit error; changes apply only after restart (FR-029).
- [ ] T006 Implement SQLAlchemy engine, session lifecycle, declarative base, and transaction helpers in `<pkg>/shared/database.py`, with a per-module schema naming helper for `collection`, `scoring` and `sharing`.
- [ ] T007 Initialize Alembic in `alembic.ini` and `migrations/env.py`, wiring the database URL from validated configuration, and add `migrations/versions/0000_schemas.py` creating the `collection`, `scoring` and `sharing` schemas.
- [ ] T008 Add `migrations/versions/0001_module_roles.py` creating the collector and scoring/sharing database roles with schema-level grants and `ALTER DEFAULT PRIVILEGES` so later tables inherit them (collector: write `collection` only; scoring/sharing: write `scoring` and `sharing`, read-only `collection`; `observer`: read-only on all three schemas, used only by `tools/export_observability.py`), and wire the roles into `compose.yaml` and `.env.example`; role passwords are never in migration files: the migration reads them from secret references resolved by `<pkg>/shared/configuration.py` at run time.
- [ ] T009 [P] Implement structured logging and shared operational error types in `<pkg>/shared/logging.py` and `<pkg>/shared/errors.py`; ensure secrets and raw sensitive payloads are not emitted.
- [ ] T010 [P] Create the canonical domain glossary in `docs/domain-glossary.md` using the spec terms IOC, Observação de origem, Resultado de score, Candidato a re-scoring (rastreabilidade), Endpoint de coleta, Peer MISP, Política de compartilhamento, plus Configuração CARIOCA, População válida, Exclusão de score, Estatísticas de população, Execução vigente, Rejeição de indicador, `as_of` and Warninglist, and list avoided synonyms for each term.
- [ ] T011 [P] Implement the shared PyMISP client wrapper in `<pkg>/shared/misp/client.py` (authentication from secret references, timeouts, version detection, no credential logging), used by `collection` and `sharing`.
- [ ] T012 Create the module skeleton under `<pkg>/` (`shared/`, `collection/`, `scoring/`, `sharing/`, `entrypoints/` with `__init__.py`, and empty `api.py` in `collection/` and `scoring/`).
- [ ] T013 Configure import-linter in `pyproject.toml` with the contracts from `plan.md` (layers inside each module, `collection` ← `scoring` ← `sharing` independence, cross-module imports only through `api.py`, `entrypoints.collector` and `entrypoints.scoring_sharing` independent, and `tools` forbidden from importing `collection`, `scoring` or `sharing`) and add `tests/architecture/test_module_boundaries.py` that runs it.
- [ ] T014 [P] Add `tests/architecture/test_table_ownership.py` asserting every mapped table lives in the schema of the module that maps it (`collection`, `scoring`, `sharing`), and failing if a column whose name contains `credential`, `secret`, `token` or `password` lacks the PostgreSQL column comment `secret`.
- [ ] T015 Add foundational unit tests for required-setting validation, secret redaction, and domain error behavior in `tests/unit/test_configuration.py` and `tests/unit/test_errors.py`.

**Checkpoint**: Project environment, shared database access, migrations, database roles, safe logging, canonical vocabulary, and enforced module boundaries are ready.

---

## Phase 3: User Story 1 - Coletar e normalizar IOCs do MISP (Priority: P1) 🎯 MVP

**Goal**: Collect actionable (`to_ids=true`) MISP data synchronously per endpoint, normalize supported indicators, and persist idempotent observations with provenance, `orgc_uuid` and warninglist entries (FR-001 to FR-006, FR-026, FR-027 data).

**Independent Test**: Process fixture MISP events and verify original/normalized values, source UUID provenance, `orgc_uuid`, a single IOC for equal type and normalized value, independent endpoint checkpoints, `to_ids` filtering with `removed_at` reconciliation, warninglist matching, and safe retry after failure.

### Tests for User Story 1

- [ ] T016 [P] [US1] Add normalization unit tests for supported, invalid, and unsupported indicator types in `tests/unit/test_normalization.py`.
- [ ] T017 [P] [US1] Add collection contract tests for paginated MISP payloads, response variants, UUIDs, modifications, failures, `to_ids` filtering, `orgc_uuid` capture and warninglist download (including unsupported regex/substring entries) in `tests/contract/test_misp_collection.py`.
- [ ] T018 [P] [US1] Add PostgreSQL integration tests for IOC uniqueness, observation upsert, provenance retention, transaction rollback, checkpoint behavior, and `removed_at` reconciliation including refusal above `RECONCILE_MAX_REMOVAL_RATIO` without advancing the checkpoint in `tests/integration/test_collection_persistence.py`.
- [ ] T019 [P] [US1] Add unit tests for per-event, per-category attribute counts (`n_i` over the 16 MISP categories, active attributes only) in `tests/unit/test_event_aggregates.py`.
- [ ] T020 [P] [US1] Add PostgreSQL integration tests for Rejeição de indicador in `tests/integration/test_rejections.py`: invalid and unsupported indicators create no IOC; exactly one record per `(source_instance_id, attribute_uuid, reason)` after recollecting; a rejected attribute that later becomes valid has its record removed in the same transaction as IOC creation; count and listing by reason and source work; the raw value never appears in logs or error messages.
- [ ] T021 [P] [US1] Add unit tests for the observability export in `tests/unit/test_observability_export.py`: one sheet per table of every schema, read-only behavior, no column commented `secret` in any sheet, raw values such as `=1+1`, `+x`, `-x` and `@x` written as text, truncation above `EXPORT_MAX_ROWS_PER_SHEET` marked on the sheet with the true total shown in the Métricas sheet, and an explicit error without a partial file when the connection or settings are invalid.
- [ ] T022 [P] [US1] Add a PostgreSQL integration test in `tests/integration/test_observability_export_db.py` that runs `tools/export_observability.py` against the test database with the read-only `observer` role and checks every table appears as a sheet, the Métricas sheet matches known fixtures, and no write is possible (SC-012).
- [ ] T023 [P] [US1] Add unit tests for warninglist membership (exact normalized value, CIDR containment for IPs, hostname/subdomain for domains) and for regex/substring entries being stored with `supported = false` and never evaluated, in `tests/unit/test_warninglist_matching.py`.

### Implementation for User Story 1

- [ ] T024 [P] [US1] Implement the IOC domain entity in `<pkg>/collection/domain/indicators.py` with identity uniqueness on `(type, normalized_value)` and validation that invalid content is never silently converted into a valid IOC.
- [ ] T025 [P] [US1] Implement the Observação de origem domain entity in `<pkg>/collection/domain/observations.py`, preserving raw value, source instance, event UUID, attribute UUID, category, `to_ids`, `orgc_uuid`, timestamps, distribution, relevant event context (`threat_level_id`, `analysis`) and `removed_at`.
- [ ] T026 [P] [US1] Define validated external MISP event/attribute/warninglist payload schemas in `<pkg>/collection/adapters/schemas.py`, preserving unrecognized raw enum values for explicit handling.
- [ ] T027 [P] [US1] Implement the Rejeição de indicador domain type in `<pkg>/collection/domain/rejections.py`: source instance, event UUID, attribute UUID, MISP type, raw value (untrusted data, never interpreted), `reason` in (`invalid`, `unsupported`), short non-sensitive `detail`, `rejected_at`; uniqueness on `(source_instance_id, attribute_uuid, reason)`.
- [ ] T028 [P] [US1] Implement the Entrada de warninglist domain type and matching in `<pkg>/collection/domain/warninglists.py`: list, list type, normalized value, source instance, `collected_at`, `supported`; membership by exact normalized value, CIDR for IPs and hostname/subdomain for domains; regex and substring entries marked `supported = false`, never evaluated, and listed for the operator.
- [ ] T029 [US1] Implement type/value normalization as domain rules in `<pkg>/collection/domain/normalization.py`, keeping source-specific parsing out of scoring and persistence; invalid or unsupported indicators produce a Rejeição de indicador (T027) and never an IOC.
- [ ] T030 [US1] Implement per-event category counts in `<pkg>/collection/domain/event_aggregates.py`, excluding observations with `removed_at` set.
- [ ] T031 [US1] Add SQLAlchemy mappings and Alembic migration in `<pkg>/collection/infrastructure/persistence/models.py` and `migrations/versions/0002_collection.py` creating, in schema `collection` (any credential or secret-reference column carries the PostgreSQL column comment `secret`), `ioc` (with `input_revision`), `observacao_origem` (with `orgc_uuid`, `to_ids`, `removed_at`), `endpoint_coleta` (with `to_ids_only` default true and removal-ratio limit) `rejeicao_indicador` (unique on `(source_instance_id, attribute_uuid, reason)`; `reason` restricted to `invalid` or `unsupported`) and `entrada_warninglist` (with `supported`); enforce IOC uniqueness on `(type, normalized_value)` and observation uniqueness on source instance + attribute UUID.
- [ ] T032 [US1] Implement paginated source queries in `<pkg>/collection/adapters/collection.py` using `<pkg>/shared/misp/client.py`: configured instance version/OpenAPI compatibility, `to_ids` filter per endpoint, overlapped time windows, event `orgc_uuid`, and enabled warninglist entries.
- [ ] T033 [US1] Implement IOC, Observação de origem, Endpoint de coleta, Rejeição de indicador (upsert per origin and reason; delete when the attribute becomes valid, in the IOC-creation transaction) and warninglist repositories in `<pkg>/collection/infrastructure/persistence/repositories/observations.py`; reconcile by source UUID and modification time, never by local numeric MISP IDs.
- [ ] T034 [US1] Implement reconciliation of removed, expired or filtered-out attributes (set `removed_at`, preserve provenance) with the mass-removal guard in `<pkg>/collection/application/reconcile.py`; above the configured ratio, refuse to apply and raise an operator-visible error.
- [ ] T035 [US1] Implement the synchronous collection use case, transactional batch persistence, overlap windows, bounded retry/backoff, and checkpoint advancement only after complete successful processing in `<pkg>/collection/application/collect.py`.
- [ ] T036 [US1] Implement per-endpoint cadence (from environment, T005), last-run/last-success state, non-overlapping collection jobs in `<pkg>/collection/infrastructure/scheduling/scheduler.py`, and the collector composition root in `<pkg>/entrypoints/collector.py`.
- [ ] T037 [US1] Implement collection run status and safe actionable error reporting in `<pkg>/collection/application/status.py`, including rejection counts by reason and by source, without logging credentials, raw indicator values or raw sensitive payloads.
- [ ] T038 [US1] Implement `tools/export_observability.py` per `contracts/observability-export.md`: connect with the read-only `observer` role, reflect all tables of the `collection`, `scoring` and `sharing` schemas (no imports from the modules), write one `.xlsx` sheet per table with openpyxl, neutralize untrusted text values, use openpyxl write-only mode, write the file with permission 0600 into a restricted output directory, skip every column commented `secret`, apply the row cap (default 1000000, ceiling 1048575) without silent truncation, and build the Métricas sheet through pluggable metric functions; include the collection metrics: rows per table, rejections by reason and source, last collection run per endpoint, and unsupported warninglist entries. There is no CLI: configuration comes only from environment variables (T005).
- [ ] T039 [US1] Implement the read-only public surface in `<pkg>/collection/api.py`: iterate active IOCs with observations, per-event category counts, event threat level/analysis, per-pair first-publication facts by `orgc_uuid` (for FeedRank), warninglist membership by `(type, normalized_value)`, unsupported warninglist entries, listing and counting of Rejeições de indicador by reason and source, and current `input_revision`.

**Checkpoint**: Story 1 is independently testable against MISP fixtures and PostgreSQL; repeated windows do not duplicate IOCs or observations; filtered-out attributes are reconciled safely; warninglist matching follows the supported types only.

---

## Phase 4: User Story 2 - Calcular e explicar o score Carioca (Priority: P2)

**Goal**: Recalculate daily, for the whole valid population with a single `as_of` and without reusing earlier results, deterministic CARIOCA v3 priority scores and explanations within 1 hour, refusing to score with incomplete or unapproved configuration (FR-010, FR-012 to FR-014, FR-022 to FR-025, SC-011).

**Independent Test**: Run published-formula reference cases and verify component scores (Source, Event with normalized CADE, Attribute), deterministic 0–100 priority for a fixed `as_of`, rank and top-N membership, explanations, exclusion reasons, empty-population and all-equal MinMax behavior, missing-input handling, and refusal to score with incomplete approved configuration.

### Tests for User Story 2

- [ ] T040 [P] [US2] Add unit tests for TL/SA mappings (`threat_level_id` 1/2/3/4 → 100/66/33/0; `analysis` 0/1/2 → 0/50/100), Event score `0,4·TL + 0,2·SA + 0,4·CADE'`, and Attribute freshness (hash 2/60, ip 1,5/7, domain 0,7/365; `t ≥ T_a` → 0; unsupported types → 0) against `as_of`, using the real reference cases from the Notion page "CARIOCA — fórmulas e exemplos reais" (e.g. `hotels-stays55501.com`: CADE 6,5218, E 25,8087, P 69,486) in `tests/unit/test_carioca_components.py`.
- [ ] T041 [P] [US2] Add unit tests for the CADE `CS_i = (1 − e^(−n²/(2σ²)))·100`, β = 1/16, robust σ estimator, explicit σ = 0 rule, and MinMax between events in `tests/unit/test_cade.py`.
- [ ] T042 [P] [US2] Add unit tests for the `orgc-proxy` FeedRank (first publisher per pair, directed graph, PageRank 0,85, `V_o = 50·c·100 + 50·MinMax(PR)`, `Source = MinMax(V_o)`) in `tests/unit/test_feed_rank.py`.
- [ ] T043 [P] [US2] Add unit tests for population eligibility and exclusion reasons (type without decay group, expired), MinMax where maximum = minimum (normalized value 50, recorded in the explanation), empty population (run completes without scores and with an operator warning), and SPOTIS equivalence to `(S'+E'+A')/3` in `tests/unit/test_population_priority.py`.
- [ ] T044 [P] [US2] Add unit tests for rank assignment and top-N selection boundaries, ties, and `top_n` larger than the valid population in `tests/unit/test_selection.py`.
- [ ] T045 [P] [US2] Add tests that reject incomplete/unapproved configuration (including missing σ estimator, CADE normalization, FeedRank method, `top_n`) and missing required inputs, and assert identical results for identical input/configuration/`as_of` snapshots in `tests/unit/test_carioca_configuration.py`.
- [ ] T046 [P] [US2] Add unit tests in `tests/unit/test_scoring_metrics.py` for the scoring metrics of the export (last successful run with `as_of` and duration, valid population and exclusions by reason, empty-population and equal-value warnings, rank cut) computed from fixture tables.
- [ ] T047 [P] [US2] Add PostgreSQL integration tests for persisted score provenance, configuration version, `as_of`, rank/top-N, population statistics, exclusions and scoring-run state in `tests/integration/test_scoring_persistence.py`.

### Implementation for User Story 2

- [ ] T048 [P] [US2] Evaluate σ estimators (percentile-95 cap and log scale) on the study MISP data described in the Caderno de Projetos (Notion), handling categories where the cap yields σ = 0, and record the evidence and a proposed approved configuration in `docs/sigma-estimator-evaluation.md`; this blocks approving the configuration (T058), not the formula code.
- [ ] T049 [P] [US2] Implement the versioned CARIOCA configuration domain model in `<pkg>/scoring/domain/carioca_configuration.py`; validate nonnegative weights summing to 1 (α: 0,4/0,2/0,4; β: 1/16), model ids (`carioca-orgc-proxy-v3`, `cade-seminormal-v2`), σ estimator method/version/σ = 0 rule, CADE MinMax, FeedRank `orgc-proxy` parameters, SPOTIS weights 1/3, freshness mappings, `top_n` (no implicit default), approval, and configuration hash. MinMax with maximum = minimum is fixed at 50 and is not configurable.
- [ ] T050 [US2] Implement CARIOCA input completeness validation and published mappings (TL, SA, type → decay group including composite types such as `filename|hash`) in `<pkg>/scoring/domain/carioca_inputs.py`; missing or unknown required values must yield an explicit invalid result rather than an invented score.
- [ ] T051 [US2] Implement the CADE calculation (category scores, robust σ, per-event MinMax) in `<pkg>/scoring/domain/cade.py`, applying only approved configuration.
- [ ] T052 [US2] Implement Event score and Attribute freshness computed against `as_of` (never the system clock) in `<pkg>/scoring/domain/carioca_components.py`.
- [ ] T053 [US2] Implement the `orgc-proxy` FeedRank in `<pkg>/scoring/domain/feed_rank.py` (in pure Python unless T048 or the benchmark T063 shows a need; record any new dependency in `research.md`), returning a configuration error when the approved method/version is absent and exposing the proxy limitation for explanations.
- [ ] T054 [US2] Implement population eligibility and exclusion reasons (type without decay group, expired, missing data, incomplete configuration) in `<pkg>/scoring/domain/population.py`.
- [ ] T055 [US2] Implement MinMax (maximum = minimum → 50, flagged for the explanation) and SPOTIS final priority in `<pkg>/scoring/domain/priority.py`, with equal criterion weights and a 0–100 result where higher means more relevant.
- [ ] T056 [US2] Implement rank assignment and top-N selection over the valid scores of a scoring run in `<pkg>/scoring/domain/selection.py`, using the `top_n` from the approved configuration.
- [ ] T057 [US2] Add persistence mappings and Alembic migration in `<pkg>/scoring/infrastructure/persistence/models.py` and `migrations/versions/0003_scoring.py` creating, in schema `scoring` (any credential or secret-reference column carries the column comment `secret`), `configuracao_carioca`, `estatisticas_populacao`, `resultado_score` (with `as_of`, raw and normalized components, input revision, `rank`, `in_top_n`), `exclusao_score` and `execucao_scoring` (with `as_of` and `warnings` for conditions such as an empty population or equal-value MinMax).
- [ ] T058 [US2] Create the explicit CARIOCA v3 configuration file `config/carioca-orgc-proxy-v3.yaml` with every parameter from T049 and `approved: false` until the σ evaluation in `docs/sigma-estimator-evaluation.md` is approved.
- [ ] T059 [US2] Implement the daily population scoring use case in `<pkg>/scoring/application/score_population.py`: fix `as_of`, load a stable snapshot through `collection.api`, compute population statistics (σ, min/max, FeedRank), score every valid IOC without reusing earlier results, assign rank/top-N, persist results, exclusions and statistics, finish without scores on an empty population, recording the warning as a structured WARNING log event and in `execucao_scoring.warnings`, and never emit a valid score for incomplete configuration or data.
- [ ] T060 [US2] Implement the non-overlapping daily scoring job, with its frequency read from the environment (T005), in `<pkg>/scoring/infrastructure/scheduling/scheduler.py` and wire it into the composition root `<pkg>/entrypoints/scoring_sharing.py`.
- [ ] T061 [US2] Implement operator-facing score explanation/status rendering in `<pkg>/scoring/application/score_explanation.py` using canonical domain terms, the `as_of`, rank/top-N, the exclusion reason, MinMax-equal-values notes, and the FeedRank proxy limitation.
- [ ] T062 [US2] Add the scoring metric functions to the observability export in `tools/metrics/scoring.py` (last successful run, `as_of`, duration, valid population, exclusions by reason, empty-population and equal-value warnings), reading only the exported tables.
- [ ] T063 [US2] Add a benchmark in `tests/benchmark/test_scoring_performance.py` that runs T059 over representative data (order of 270 mil valid IOCs) generated by `tests/benchmark/dataset.py` (synthetic, with a realistic category/organization/age distribution) or, when `BENCHMARK_DATABASE_URL` is set, loaded from a copy of the study MISP database, and asserts the full recalculation completes within 1 hour (SC-011); record the memory-versus-SQL processing decision in `research.md`.

**Checkpoint**: Story 2 produces reproducible, traceable scores with rank for the whole valid population under a complete approved configuration, within the time target, and explicit invalid outcomes otherwise.

---

## Phase 5: User Story 3 - Rastrear IOCs com dados de entrada alterados (Priority: P2)

**Goal**: Advance `input_revision` only when algorithm inputs change and track, as traceability only, which IOCs have changed data since their last successful score; pending is cleared only after a successful calculation on the current revision (FR-007 to FR-011). The daily recalculation of the whole population does not depend on candidates.

**Independent Test**: Change an algorithm input on one source observation and a non-input on another; verify only the related IOC's `input_revision` advances and only it becomes a candidate, a successful daily run on the current revision clears it, and failures/concurrent changes remain pending.

### Tests for User Story 3

- [ ] T064 [P] [US3] Add unit tests for relevant-field classification (fields feeding Source, Event, CADE and Attribute) and exclusion of irrelevant fields in `tests/unit/test_input_revision.py`.
- [ ] T065 [P] [US3] Add unit tests for candidate derivation (`input_revision` differs from the last successfully scored revision), coalescing multiple observations into one IOC candidate, and that candidacy never changes which IOCs are scored in `tests/unit/test_rescoring_candidates.py`.
- [ ] T066 [P] [US3] Add PostgreSQL integration tests for candidate upsert, input revision races, scoring failures, and score writes not re-marking candidates in `tests/integration/test_rescoring_candidates.py`.

### Implementation for User Story 3

- [ ] T067 [US3] Implement relevant-input change classification in `<pkg>/collection/domain/input_revision.py`: only changes to fields used by the algorithm (type/normalized value, category, `to_ids`, `removed_at`, `orgc_uuid`, attribute timestamp, event threat level and analysis) increment `ioc.input_revision`.
- [ ] T068 [US3] Integrate `input_revision` increments with source-observation upserts in `<pkg>/collection/infrastructure/persistence/repositories/observations.py`; the collection module never writes scoring tables.
- [ ] T069 [US3] Add the Candidato a re-scoring mapping and Alembic migration in `<pkg>/scoring/infrastructure/persistence/candidate_models.py` and `migrations/versions/0004_rescoring_candidates.py` (schema `scoring`); enforce one candidate per logical IOC with pending state and the last successfully scored input revision.
- [ ] T070 [US3] Add the pending-candidates metric to the observability export in `tools/metrics/candidates.py` (pending count, oldest pending age, last attempt error), plus its unit test in `tests/unit/test_candidate_metrics.py`.
- [ ] T071 [US3] Implement candidate derivation in `<pkg>/scoring/domain/rescoring.py`: an IOC is a candidate when its `input_revision` (read via `collection.api`) differs from the revision of its last valid score; score writes never alter `input_revision`.
- [ ] T072 [US3] Implement candidate snapshot and completion in `<pkg>/scoring/application/score_candidates.py` and edit `<pkg>/scoring/application/score_population.py` (T059) to call it after each IOC calculation: record the revision used by each calculation and clear pending only if the IOC's calculation succeeded and its input revision still matches; it must not select which IOCs are scored nor reuse earlier results.
- [ ] T073 [US3] Extend daily run status and retry visibility for candidates in `<pkg>/entrypoints/scoring_sharing.py`, preserving pending status on failures and concurrent input changes.

**Checkpoint**: Story 3 tracks pending data changes correctly without score-write loops and without affecting which IOCs are scored.

---

## Phase 6: User Story 4 - Compartilhar IOCs com peers MISP (Priority: P3)

**Goal**: Share only IOCs that are in the top-N, meet the peer minimum, are not in an enabled warninglist, and are authorized by native MISP controls, with peers and minimums read from the container environment at startup (FR-015 to FR-017, FR-027).

**Independent Test**: Run eligible/ineligible IOCs through a test peer; confirm only eligible and MISP-authorized IOCs are synchronized, ambiguous sends are reconciled, delivery is not reported confirmed without evidence, invalid peer settings prevent sharing, and changes apply only after a restart.

### Tests for User Story 4

- [ ] T074 [P] [US4] Add unit tests for per-peer threshold boundaries, top-N, warninglist ineligibility with recorded reason, stale scores (older `as_of`) or invalid scores, and the 48-hour validity of the latest successfully completed scoring run (older than `SCORE_MAX_AGE_HOURS`, default 48 → sharing suspended with a WARNING log event and persisted warning; a failed newer run does not replace it; sharing resumes after a new successful run) in `tests/unit/test_sharing_eligibility.py`.
- [ ] T075 [P] [US4] Add MISP sync contract tests for authorized/restricted distribution, publication status, asynchronous job status, ambiguous timeout reconciliation, partial acceptance by the peer (accepted items confirmed, rest kept pending) and retry in `tests/contract/test_misp_sharing.py`.
- [ ] T076 [P] [US4] Add PostgreSQL integration tests for peer policy, effective-policy registration, sharing attempt states, retry idempotency, and eligibility changes before retry in `tests/integration/test_sharing_persistence.py`.
- [ ] T077 [P] [US4] Add unit tests for peer environment parsing: minimum outside 0–100 or missing peer fields prevents sharing with an explicit error, secrets stay references, and the effective policy hash changes when settings change in `tests/unit/test_peer_configuration.py`.

### Implementation for User Story 4

- [ ] T078 [P] [US4] Implement the read-only public surface in `<pkg>/scoring/api.py`: current valid score per IOC with configuration version, `as_of`, input revision, `rank` and `in_top_n` for the latest successfully completed run, plus that run's `finished_at` (the execução vigente) so `sharing` can enforce the 48-hour validity.
- [ ] T079 [P] [US4] Implement per-peer Política de compartilhamento domain rules and threshold validation in `<pkg>/sharing/domain/sharing.py`, requiring a current valid score meeting the configured 0–100 minimum, top-N membership and absence from enabled warninglists.
- [ ] T080 [P] [US4] Implement peer configuration loading from the scoring/sharing container environment in `<pkg>/sharing/infrastructure/peer_configuration.py`: peers, per-peer minimum (0–100) and secret references, validated at startup (invalid or missing settings stop sharing with an explicit error), and registration of the effective policy with hash and timestamp at each start; changes apply only after restart.
- [ ] T081 [US4] Add Peer MISP, effective sharing policy, and sharing-attempt persistence mappings with Alembic migration in `<pkg>/sharing/infrastructure/persistence/models.py` and `migrations/versions/0005_sharing.py` (schema `sharing`; credential and secret-reference columns carry the PostgreSQL column comment `secret`); attempts reference the effective policy and the evaluated score.
- [ ] T082 [US4] Implement eligibility evaluation in `<pkg>/sharing/application/share_eligible.py` using `scoring.api` and `collection.api` (warninglist), applying the peer minimum and top-N while preserving native MISP publication, distribution, sharing-group and authorization controls; record ineligibility reasons; suspend all new sends and record a WARNING log event plus a persisted warning when the latest successful scoring run is older than `SCORE_MAX_AGE_HOURS` (default 48, from environment, FR-016/FR-029); the sharing run frequency also comes from the environment, resuming only after a new successful run.
- [ ] T083 [P] [US4] Implement the native MISP push synchronization adapter in `<pkg>/sharing/adapters/synchronization.py`, tracking asynchronous jobs separately from confirmed peer receipt; retry count and backoff come from the environment (T005).
- [ ] T084 [US4] Implement sharing-attempt state transitions, UUID reconciliation after ambiguous timeout, bounded retries, handling of partial acceptance by the peer (confirm only accepted items, keep the rest pending), and re-evaluation of score, top-N, warninglist, score age and policy before retry in `<pkg>/sharing/application/share_eligible.py` and `<pkg>/sharing/infrastructure/persistence/repositories/sharing.py`.
- [ ] T085 [P] [US4] Add unit tests in `tests/unit/test_sharing_metrics.py` for the sharing metrics of the export (attempts by state, effective policy, suspension flag computed from the age of the last successful scoring run versus `SCORE_MAX_AGE_HOURS`).
- [ ] T086 [US4] Add the sharing metric functions to the observability export in `tools/metrics/sharing.py` (attempts by state, pending and failed counts, effective policy hash, suspended or not), reading only the exported tables.
- [ ] T087 [US4] Compose eligible IOC sharing with the scoring job in `<pkg>/entrypoints/scoring_sharing.py` and record pending, failed, confirmed, ineligible and suspended (stale scores) states in the tables read by the export, in `<pkg>/sharing/application/sharing_status.py`.

**Checkpoint**: Story 4 shares eligible IOCs idempotently, never treats a requested push as confirmed delivery, and refuses to start sharing with invalid peer settings.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify the integrated system, security posture, and runbook across all stories.

- [ ] T088 [P] Add end-to-end Compose test fixtures and isolated MISP test configuration in `tests/e2e/conftest.py` and `tests/e2e/config/`.
- [ ] T089 [P] Add migration-upgrade and clean-install verification for the complete PostgreSQL schema in `tests/integration/test_migrations.py`.
- [ ] T090 [P] Add an integration test in `tests/integration/test_database_roles.py` that the collector role cannot write `scoring` or `sharing`, the scoring/sharing role cannot write `collection`, and the `observer` role can read all schemas but write none.
- [ ] T091 [P] Add a test in `tests/integration/test_source_equivalence.py` that equivalent domain data received from two distinct MISP sources yields identical scoring, candidate and sharing-eligibility decisions (FR-021, SC-010).
- [ ] T092 [P] Add `tests/architecture/test_domain_vocabulary.py` that scans operator-facing messages and docstrings in `<pkg>/` for the avoided synonyms listed in `docs/domain-glossary.md` (SC-009).
- [ ] T093 Update `specs/001-misp-ioc-scoring/quickstart.md` with final runnable Compose, pytest, benchmark, collection, scoring, `to_ids` filter, peer environment, and isolated sync-peer commands.
- [ ] T094 Run `docker compose up --build` and `python -m pytest` following `specs/001-misp-ioc-scoring/quickstart.md`; fix failures in the relevant source/test files and record any unavailable MISP integration prerequisite.
- [ ] T095 Review secrets handling, module boundaries, MISP distribution enforcement, dependency pins, and domain vocabulary across `<pkg>/`, `compose.yaml`, `.env.example`, and `docs/domain-glossary.md`.

---

## Dependencies & Execution Order

**Module rule**: dependencies between modules follow `collection` ← `scoring` ← `sharing`
and cross only through `api.py` (T013/T014 enforce this). Table writes follow the
ownership table in `plan.md`. The observability export in `tools/` is the only exception: it
reads every schema through the read-only `observer` role by reflection and imports no module.

### Phase Dependencies

- **Setup (Phase 1)**: No dependency; creates the Python project and container baseline.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories. The database roles (T008, including `observer`) are created here so the MVP and its integration tests run with the final roles.
- **US1 (Phase 3)**: Depends on Foundational; delivers collection/normalization MVP, Rejeições de indicador, `collection/api.py` (T039) and the observability export (T038).
- **US2 (Phase 4)**: Pure formula tasks (T040–T056) can use fixtures right after Foundational; T059–T063 need `collection.api` (T039). T062 extends the export built in T038. T048 can start anytime on the study MISP data and blocks only approving the configuration (T058) and any production scoring run.
- **US3 (Phase 5)**: Depends on US1 persistence and US2's scoring run (T059); T072 edits T059's file, so it runs after T059.
- **US4 (Phase 6)**: Depends on US1 provenance/warninglists and US2 valid scores with rank and run `finished_at`; checks pending/stale state before retry. T086 extends the export.
- **Polish (Phase 7)**: Depends on all stories selected for release.

### User Story Dependencies

- **US1 (P1)**: Independent after Foundational; first deployable MVP.
- **US2 (P2)**: Formula/domain work can proceed with fixtures; production integration depends on US1.
- **US3 (P2)**: Depends on US1 observation updates and US2's scoring run; it never changes which IOCs are scored.
- **US4 (P3)**: Depends on current US2 scores/rank and US1 data; re-evaluates pending/stale state before retry and suspends sharing when the latest successful scoring run is older than `SCORE_MAX_AGE_HOURS` (default 48).

### Within Each User Story

- Tests are included because the constitution requires automated coverage; write them before implementation and verify failure against the missing behavior.
- Domain rules precede persistence/application integration where possible.
- MISP external payloads remain in adapter schemas; domain logic uses canonical domain terms.
- Do not clear checkpoints or candidates on partial/failed processing.
- Never read the system clock inside scoring domain code; use the run's `as_of`.
- Never write raw indicator values to logs or error messages; they live only in Rejeição de indicador and, neutralized as text, in the export.
- There is no CLI, API or UI: operation is by environment variables and observation is by logs and the Excel export.
- A task marked `[P]` must not depend on an unfinished task in the same phase (for example T051 and T053 wait for T049).

### Parallel Opportunities

- Setup T002–T004 touch separate files and can proceed in parallel after T001; T003 and T004 are extended later by T008, T005 and T080, which therefore run after them.
- Foundational T009, T010, T011 and T014 are independent of T005–T008.
- In US1, T016–T023 can be authored in parallel; T024–T028 are independent domain/schema files.
- In US2, T040–T047 are independent tests; T048 and T049 touch separate files.
- In US3, T064–T066 are separate tests.
- In US4, T074–T077 are independent tests; T078, T079, T080 and T083 are separate modules.
- Cross-story parallelism is limited: US2 formula work can begin with fixtures alongside US1, but integration phases respect the dependency graph.

## Parallel Example: User Story 1

```text
After T001/T005–T007 are ready:
T016 tests/unit/test_normalization.py
T017 tests/contract/test_misp_collection.py
T018 tests/integration/test_collection_persistence.py
T019 tests/unit/test_event_aggregates.py
T020 tests/integration/test_rejections.py
T021 tests/unit/test_observability_export.py
T022 tests/integration/test_observability_export_db.py
T023 tests/unit/test_warninglist_matching.py
T024 src/misp_ioc_scoring/collection/domain/indicators.py
T025 src/misp_ioc_scoring/collection/domain/observations.py
T026 src/misp_ioc_scoring/collection/adapters/schemas.py
T027 src/misp_ioc_scoring/collection/domain/rejections.py
T028 src/misp_ioc_scoring/collection/domain/warninglists.py
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational phases (T001–T015).
2. Complete US1 (T016–T039): collection, normalization, rejections, provenance, `to_ids` filtering, warninglist entries, checkpointing, the observability export and tests.
3. Validate against PostgreSQL and MISP fixtures, then stop for an MVP review.

### Incremental Delivery

1. Add US2: formulas, population scoring, rank/top-N, `as_of`, explanation, scoring metrics and the 1-hour benchmark; start T048 early. Production scoring stays blocked until the σ estimator and `config/carioca-orgc-proxy-v3.yaml` are approved.
2. Add US3: `input_revision`-driven candidate tracking (traceability only) and its metric.
3. Add US4: peer settings from the environment, top-N, peer minimum, warninglist-aware sharing, the configurable score validity (default 48 h) and the sharing metrics.
4. Complete isolated end-to-end, role, equivalence and vocabulary checks, and the security review.

### Parallel Team Strategy

1. Complete Setup/Foundational together.
2. US1 owns collection/persistence and the export; a separate contributor may prepare US2 formula tests and pure scoring functions after shared foundations are ready, and own T048.
3. Start US3 only after observation persistence and the scoring run exist.
4. Start US4 policy tests/adapters after score, rank and provenance contracts are stable.

## Notes

- `[P]` tasks modify separate files and have no dependency on unfinished work.
- Every user-story task uses its story label; setup, foundational and polish tasks do not.
- CARIOCA parameters absent from the publication (σ estimator, CADE normalization, FeedRank
  proxy, `top_n`) must be approved and explicitly configured; tasks must not introduce
  silent defaults. MinMax with equal values is fixed at 50.
- The FeedRank proxy (`orgc`) is a known limitation to expose in explanations and the paper.
- Peers, per-peer minimums and all times and frequencies live in the container environment and apply only after a restart.
- A "warning to the operator" is a structured WARNING log event plus a persisted record shown by the export.
- MISP push completion is asynchronous; a queued job is not proof of peer receipt.
- `tasks.md` is an implementation checklist; do not mark a task complete until its
  acceptance behavior is verified.
