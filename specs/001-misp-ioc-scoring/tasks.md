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

The implementation plan defines one Python package at `src/misp_ioc_scoring/`,
database migrations under `migrations/`, and tests under `tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the Python project and three-container development environment.

- [ ] T001 Create `pyproject.toml` for Python 3.12 with runtime dependencies PyMISP, SQLAlchemy 2.x, Alembic, Pydantic, APScheduler 3.x and development dependency pytest.
- [ ] T002 [P] Create `Dockerfile` using a non-root runtime user and separate collector/scoring worker commands.
- [ ] T003 [P] Create `compose.yaml` with PostgreSQL, collector/normalizer and scoring/sharing services, persistent database volume, health check, and service dependency conditions.
- [ ] T004 [P] Create `.dockerignore` and `.env.example` with configuration keys but no credentials or secret values.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared configuration, persistence, migration, error, and domain-language foundations required by every story.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [ ] T005 Implement validated environment/configuration loading in `src/misp_ioc_scoring/infrastructure/configuration.py`, keeping credentials as secret references and rejecting missing required settings.
- [ ] T006 Implement SQLAlchemy engine, session lifecycle, declarative base, and transaction helpers in `src/misp_ioc_scoring/infrastructure/persistence/database.py`.
- [ ] T007 Initialize Alembic configuration and migration environment in `alembic.ini` and `migrations/env.py`, wiring database URL from validated configuration.
- [ ] T008 [P] Implement structured logging and shared operational error types in `src/misp_ioc_scoring/infrastructure/logging.py` and `src/misp_ioc_scoring/domain/errors.py`; ensure secrets and raw sensitive payloads are not emitted.
- [ ] T009 [P] Create the canonical domain glossary in `docs/domain-glossary.md` using the spec terms IOC, Observação de origem, Resultado de score, Candidato a re-scoring, Endpoint de coleta, Peer MISP and Política de compartilhamento.
- [ ] T010 Add foundational unit tests for required-setting validation, secret redaction, and domain error behavior in `tests/unit/test_configuration.py` and `tests/unit/test_errors.py`.

**Checkpoint**: Project environment, shared database access, migrations, safe logging, and canonical vocabulary are ready.

---

## Phase 3: User Story 1 - Coletar e normalizar IOCs do MISP (Priority: P1) 🎯 MVP

**Goal**: Collect MISP data synchronously per endpoint, normalize supported indicators, and persist idempotent observations with provenance.

**Independent Test**: Process fixture MISP events and verify original/normalized values, source UUID provenance, a single IOC for equal type and normalized value, independent endpoint checkpoints, and safe retry after failure.

### Tests for User Story 1

- [ ] T011 [P] [US1] Add normalization unit tests for supported, invalid, and unsupported indicator types in `tests/unit/test_normalization.py`.
- [ ] T012 [P] [US1] Add collection contract tests for paginated MISP payloads, response variants, UUIDs, modifications and failures in `tests/contract/test_misp_collection.py`.
- [ ] T013 [P] [US1] Add PostgreSQL integration tests for IOC uniqueness, observation upsert, provenance retention, transaction rollback, and checkpoint behavior in `tests/integration/test_collection_persistence.py`.

### Implementation for User Story 1

- [ ] T014 [P] [US1] Implement the IOC domain entity in `src/misp_ioc_scoring/domain/indicators.py` with identity uniqueness on `(type, normalized_value)` and validation that invalid content is never silently converted into a valid IOC.
- [ ] T015 [P] [US1] Implement the Observação de origem domain entity in `src/misp_ioc_scoring/domain/observations.py`, preserving raw value, source instance, event UUID, attribute UUID, category, timestamps, distribution and relevant event context.
- [ ] T016 [US1] Add SQLAlchemy mappings and Alembic migration in `src/misp_ioc_scoring/infrastructure/persistence/models.py` and `migrations/versions/0001_ioc_observations.py`; enforce IOC uniqueness on `(type, normalized_value)` and observation uniqueness on source instance + attribute UUID.
- [ ] T017 [P] [US1] Define validated external MISP event/attribute payload schemas in `src/misp_ioc_scoring/adapters/misp/schemas.py`, preserving unrecognized raw enum values for explicit handling.
- [ ] T018 [US1] Implement type/value normalization as domain rules in `src/misp_ioc_scoring/domain/normalization.py`, keeping source-specific parsing out of scoring and persistence.
- [ ] T019 [US1] Implement the PyMISP client adapter and paginated source queries in `src/misp_ioc_scoring/adapters/misp/client.py` and `src/misp_ioc_scoring/adapters/misp/collection.py`, using the configured instance version/OpenAPI compatibility.
- [ ] T020 [US1] Implement IOC and Observação de origem upsert/reconciliation repositories in `src/misp_ioc_scoring/infrastructure/persistence/repositories/observations.py`; reconcile by source UUID and modification time, never by local numeric MISP IDs.
- [ ] T021 [US1] Implement synchronous collection use case, transactional batch persistence, overlap windows, bounded retry/backoff, and checkpoint advancement only after complete successful processing in `src/misp_ioc_scoring/application/collect.py`.
- [ ] T022 [US1] Implement per-endpoint cadence, last-run/last-success state, and non-overlapping collection jobs in `src/misp_ioc_scoring/infrastructure/scheduling/collector_scheduler.py` and `src/misp_ioc_scoring/workers/collector.py`.
- [ ] T023 [US1] Implement collection run status and safe actionable error reporting in `src/misp_ioc_scoring/application/collection_status.py`, without logging credentials or raw sensitive payloads.

**Checkpoint**: Story 1 is independently testable against MISP fixtures and PostgreSQL; repeated windows do not duplicate IOCs or observations.

---

## Phase 4: User Story 2 - Calcular e explicar o score Carioca (Priority: P2)

**Goal**: Calculate deterministic CARIOCA priority scores and explain the contributing inputs, while refusing incomplete parameter configuration.

**Independent Test**: Run published-formula reference cases and verify component scores, deterministic 0–100 priority, explanations, missing-input handling, and refusal to score with incomplete approved configuration.

### Tests for User Story 2

- [ ] T024 [P] [US2] Add unit tests for published threat-level and analysis mappings, CADE category score, weighted EventScore, attribute freshness, and final SPOTIS priority in `tests/unit/test_carioca_scoring.py`.
- [ ] T025 [P] [US2] Add tests that reject incomplete/unapproved configuration and missing required inputs, and assert deterministic results for identical input/configuration snapshots in `tests/unit/test_carioca_configuration.py`.
- [ ] T026 [P] [US2] Add PostgreSQL integration tests for persisted score provenance, configuration version, and scoring-run state in `tests/integration/test_scoring_persistence.py`.

### Implementation for User Story 2

- [ ] T027 [P] [US2] Implement the versioned CARIOCA configuration domain model in `src/misp_ioc_scoring/domain/carioca_configuration.py`; validate nonnegative alpha/beta weights summing to 1, explicit FeedRank method/version, category distributions, MinMax/SPOTIS parameters, freshness mappings, approval, and configuration hash.
- [ ] T028 [US2] Implement CARIOCA input completeness validation and published threat-level/analysis mappings in `src/misp_ioc_scoring/domain/carioca_inputs.py`; missing or unknown required values must yield an explicit invalid result rather than an invented score.
- [ ] T029 [US2] Implement CADE, weighted EventScore and attribute freshness formulas in `src/misp_ioc_scoring/domain/carioca_components.py`, applying only approved category distributions and the published HASH/IP/Domain freshness parameters.
- [ ] T030 [US2] Implement the FeedRank integration boundary in `src/misp_ioc_scoring/domain/feed_rank.py`; compute only from an explicitly approved method/version and parameters, and return a configuration error when no approved method exists.
- [ ] T031 [US2] Implement MinMax normalization and SPOTIS final priority calculation in `src/misp_ioc_scoring/domain/priority.py`, using the published equal criterion weights and returning a score in the 0–100 range where higher means more relevant.
- [ ] T032 [P] [US2] Add Resultado de score and scoring-run persistence mappings plus Alembic migration in `src/misp_ioc_scoring/infrastructure/persistence/scoring_models.py` and `migrations/versions/0002_scores_and_runs.py`; record exact IOC input revision, CARIOCA configuration ID/version, component values and calculation time.
- [ ] T033 [US2] Implement scoring application service in `src/misp_ioc_scoring/application/score_ioc.py` to load a stable input snapshot, call domain scoring, persist explanations/results, and avoid returning a valid score for incomplete config or data.
- [ ] T034 [US2] Implement the synchronous daily scoring worker and non-overlapping job in `src/misp_ioc_scoring/application/score_candidates.py`, `src/misp_ioc_scoring/infrastructure/scheduling/scoring_scheduler.py`, and `src/misp_ioc_scoring/workers/scoring.py`.
- [ ] T035 [US2] Implement operator-facing score explanation/status rendering in `src/misp_ioc_scoring/application/score_explanation.py` using canonical domain terms and no infrastructure-specific identifiers.

**Checkpoint**: Story 2 produces reproducible, traceable scores for complete approved configurations and explicit invalid outcomes otherwise.

---

## Phase 5: User Story 3 - Reavaliar IOCs após mudanças nos dados (Priority: P2)

**Goal**: Mark logical IOCs for daily re-scoring only when algorithm inputs change, and safely clear candidacy only for a successful current revision.

**Independent Test**: Change an algorithm input on one source observation and a non-input on another; verify only related logical IOC candidates are marked, scoring clears successful current candidates, and failures/concurrent changes remain pending.

### Tests for User Story 3

- [ ] T036 [P] [US3] Add unit tests for relevant-field change detection, irrelevant-field exclusion, and coalescing multiple source changes into one IOC candidate in `tests/unit/test_rescoring_candidates.py`.
- [ ] T037 [P] [US3] Add PostgreSQL integration tests for candidate upsert, input revision races, scoring failures, and score writes not re-marking candidates in `tests/integration/test_rescoring_candidates.py`.

### Implementation for User Story 3

- [ ] T038 [US3] Add Candidato a re-scoring persistence mapping and Alembic migration in `src/misp_ioc_scoring/infrastructure/persistence/candidate_models.py` and `migrations/versions/0003_rescoring_candidates.py`; enforce one candidate per logical IOC with pending state and input revision.
- [ ] T039 [US3] Implement relevant-input change classification and candidate marking in `src/misp_ioc_scoring/domain/rescoring.py`, resolving changed source observations to IOC logical identity and excluding unrelated fields and score-result writes.
- [ ] T040 [US3] Integrate candidate marking and IOC input revision increments with source-observation upserts in `src/misp_ioc_scoring/infrastructure/persistence/repositories/observations.py`.
- [ ] T041 [US3] Implement candidate snapshot, claim, and success/failure completion in `src/misp_ioc_scoring/application/score_candidates.py`; clear pending only if calculation succeeded and the input revision still matches.
- [ ] T042 [US3] Extend daily worker run status and retry visibility for candidates in `src/misp_ioc_scoring/workers/scoring.py`, preserving pending status on failures and concurrent input changes.

**Checkpoint**: Story 3 can mark, process, and retain candidates correctly without score-write loops.

---

## Phase 6: User Story 4 - Compartilhar IOCs com peers MISP (Priority: P3)

**Goal**: Share only IOCs with a current valid score at or above the configured peer minimum, while leaving MISP distribution and authorization as final controls.

**Independent Test**: Run eligible/ineligible IOCs through a test peer; confirm only eligible and MISP-authorized IOCs are synchronized, ambiguous sends are reconciled, and delivery is not reported confirmed without evidence.

### Tests for User Story 4

- [ ] T043 [P] [US4] Add unit tests for per-peer score threshold boundaries and stale/invalid score rejection in `tests/unit/test_sharing_eligibility.py`.
- [ ] T044 [P] [US4] Add MISP sync contract tests for authorized/restricted distribution, publication status, asynchronous job status, ambiguous timeout reconciliation and retry in `tests/contract/test_misp_sharing.py`.
- [ ] T045 [P] [US4] Add PostgreSQL integration tests for peer policy, sharing attempt states, retry idempotency, and eligibility changes before retry in `tests/integration/test_sharing_persistence.py`.

### Implementation for User Story 4

- [ ] T046 [P] [US4] Implement per-peer Política de compartilhamento domain rules and threshold validation in `src/misp_ioc_scoring/domain/sharing.py`, requiring a current valid score meeting the configured 0–100 minimum.
- [ ] T047 [US4] Add Peer MISP, sharing policy, and sharing-attempt persistence mappings with Alembic migration in `src/misp_ioc_scoring/infrastructure/persistence/sharing_models.py` and `migrations/versions/0004_misp_sharing.py`.
- [ ] T048 [US4] Implement eligibility evaluation in `src/misp_ioc_scoring/application/share_eligible.py`, applying the peer minimum and preserving native MISP publication, distribution, sharing-group and authorization controls.
- [ ] T049 [US4] Implement native MISP push synchronization adapter in `src/misp_ioc_scoring/adapters/misp/synchronization.py`, tracking asynchronous jobs separately from confirmed peer receipt.
- [ ] T050 [US4] Implement sharing-attempt state transitions, UUID reconciliation after ambiguous timeout, bounded retries, and re-evaluation of score/policy before retry in `src/misp_ioc_scoring/application/share_eligible.py` and `src/misp_ioc_scoring/infrastructure/persistence/repositories/sharing.py`.
- [ ] T051 [US4] Integrate eligible IOC sharing with the scoring worker and expose operator-visible pending, failed, and confirmed states in `src/misp_ioc_scoring/workers/scoring.py` and `src/misp_ioc_scoring/application/sharing_status.py`.

**Checkpoint**: Story 4 shares eligible IOCs idempotently and never treats a requested push as confirmed delivery.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify the integrated system, security posture, and runbook across all stories.

- [ ] T052 [P] Add end-to-end Compose test fixtures and isolated MISP test configuration in `tests/e2e/conftest.py` and `tests/e2e/config/`.
- [ ] T053 [P] Add migration-upgrade and clean-install verification for the complete PostgreSQL schema in `tests/integration/test_migrations.py`.
- [ ] T054 Update `specs/001-misp-ioc-scoring/quickstart.md` with final runnable Compose, pytest, collection, scoring and isolated sync-peer commands.
- [ ] T055 Run `docker compose up --build` and `python -m pytest` following `specs/001-misp-ioc-scoring/quickstart.md`; fix failures in the relevant source/test files and record any unavailable MISP integration prerequisite.
- [ ] T056 Review secrets handling, MISP distribution enforcement, dependency pins, and domain vocabulary across `src/misp_ioc_scoring/`, `compose.yaml`, `.env.example`, and `docs/domain-glossary.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependency; creates the Python project and container baseline.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational; delivers collection/normalization MVP.
- **US2 (Phase 4)**: Depends on US1's observations and context for end-to-end scoring; pure formula tests can use fixtures.
- **US3 (Phase 5)**: Depends on US1 persistence and US2's scoring lifecycle.
- **US4 (Phase 6)**: Depends on US1 source/provenance and US2 valid scores; integrates with US3 candidate freshness before sharing.
- **Polish (Phase 7)**: Depends on all stories selected for release.

### User Story Dependencies

- **US1 (P1)**: Independent after Foundational; first deployable MVP.
- **US2 (P2)**: Formula/domain work can proceed after Foundational with fixtures, but production integration depends on US1 collection and persistence.
- **US3 (P2)**: Depends on US1 observation updates and US2's candidate scoring lifecycle.
- **US4 (P3)**: Depends on current US2 scores and US1 MISP provenance; re-evaluates pending/stale state from US3 before retry.

### Within Each User Story

- Tests are included because the constitution requires automated coverage; write them before implementation and verify failure against the missing behavior.
- Domain rules precede persistence/application integration where possible.
- MISP external payloads remain in adapter schemas; domain logic uses canonical domain terms.
- Do not clear checkpoints or candidates on partial/failed processing.

### Parallel Opportunities

- Setup tasks T002–T004 touch separate files and can proceed in parallel after T001 project conventions are agreed.
- Foundational T008–T009 can proceed in parallel with T005–T007 because they touch independent modules/docs.
- In US1, T011–T013 can be authored in parallel; T014, T015 and T017 are independent domain/schema files.
- In US2, T024–T026 are independent tests; T027 and T032 modify separate domain/persistence files.
- In US3, T036–T037 are separate tests; implementation can split domain detection from candidate persistence after US1/US2.
- In US4, T043–T045 are independent tests; policy rules and sync adapter are separate modules.
- Cross-story parallelism is limited: US2 formula work can begin with fixtures alongside US1, but integration phases must respect the dependency graph.

## Parallel Example: User Story 1

```text
After T001/T005–T007 are ready:
T011 tests/unit/test_normalization.py
T012 tests/contract/test_misp_collection.py
T013 tests/integration/test_collection_persistence.py
T014 src/misp_ioc_scoring/domain/indicators.py
T015 src/misp_ioc_scoring/domain/observations.py
T017 src/misp_ioc_scoring/adapters/misp/schemas.py
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational phases.
2. Complete US1 collection, normalization, provenance, checkpointing and tests.
3. Validate against PostgreSQL and MISP fixtures, then stop for an MVP review.

### Incremental Delivery

1. Add US2 CARIOCA configuration and deterministic explanation; block scoring until all
   required explicit parameters are approved and complete.
2. Add US3 change-driven candidate marking and safe daily re-scoring.
3. Add US4 threshold-based sharing subject to native MISP controls.
4. Complete isolated end-to-end and security checks.

### Parallel Team Strategy

1. Complete Setup/Foundational together.
2. US1 owns collection/persistence; a separate contributor may prepare US2 formula tests
   and pure scoring functions against fixtures after shared foundations are ready.
3. Start US3 only after observation persistence and scoring lifecycle interfaces exist.
4. Start US4 policy tests/adapters after score and provenance contracts are stable.

## Notes

- `[P]` tasks modify separate files and have no dependency on unfinished work.
- Every user-story task uses its story label; setup, foundational and polish tasks do not.
- Score publication parameters absent from the CARIOCA article must be approved and
  explicitly configured; tasks must not introduce silent defaults.
- MISP push completion is asynchronous; a queued job is not proof of peer receipt.
- `tasks.md` is an implementation checklist; do not mark a task complete until its
  acceptance behavior is verified.
