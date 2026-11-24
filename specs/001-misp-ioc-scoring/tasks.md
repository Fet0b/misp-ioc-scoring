# Tasks: Plataforma de Scoring e Compartilhamento de IOCs (retomada US2–US4 e ajuste de DDD)

**Input**: Design documents from `specs/001-misp-ioc-scoring/` (revisão 2026-11-24)

**Prerequisites**: `plan.md` (seções "Revisão 2026-11-24" e "Ajuste de DDD"), `spec.md`,
`research.md`, `data-model.md`, `contracts/` e `quickstart.md`

**Organization**: tarefas agrupadas por história de usuário. Os testes estão
incluídos porque a Constituição exige testes para todo comportamento afetado.

**Regenerado em 2026-11-24.** Esta lista substitui a de 95 tarefas (versão anterior no
commit `082f3b2`). O que já estava pronto não é repetido aqui:

- **Setup, fundação e US1 (coleta)**: pacote, Docker/Compose, configuração, banco,
  migrations `0000`–`0003`, papéis, logging, glossário, cliente MISP, import-linter,
  normalização, observações, rejeições, warninglists, reconciliação, coleta,
  scheduler por endpoint, `collection/api.py` e exportação de observabilidade.
- **Feature 002**: bloqueio simples, Pi-hole, flags e migrations `0004`–`0007`.

Pendências de US1 que ficaram incompletas foram absorvidas aqui: T037 antiga →
T061; ajuste de `input_revision` → T005.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente).
- **[Story]**: história de `spec.md` (US2 score, US3 candidatos, US4 peers MISP).
- `<pkg>` = `src/misp_ioc_scoring`.
- **Regra das etapas D1–D10 (ajuste de DDD)**: refatoração sem mudança de
  comportamento. Os testes existentes continuam passando sem mudar nenhum **valor
  esperado**; só muda a forma de acesso quando o tipo devolvido muda (por exemplo
  `row["block"]` → `row.block` em T020). O teste de caracterização (T003) continua
  idêntico. Os casos de uso são chamados pelos entrypoints; a infraestrutura só
  implementa portas e nunca importa `application`. Um commit por etapa, com a suíte completa
  em PostgreSQL (`TEST_DATABASE_URL`) rodada antes.

---

## Phase 1: Setup

**Purpose**: corrigir a execução dos testes e preparar a verificação automática.

- [X] T001 Adicionar `[tool.pytest.ini_options]` com `pythonpath = ["."]` e `testpaths = ["tests"]` em `pyproject.toml`, para `tests/unit/test_observability_export.py` importar `tools` sem `PYTHONPATH=.`; confirmar com `uv run --extra dev pytest -q tests/unit tests/contract tests/architecture` (77 testes passando).
- [X] T002 [P] Adicionar em `pyproject.toml` contratos import-linter do tipo `forbidden` que proíbem `misp_ioc_scoring.collection.domain`, `misp_ioc_scoring.scoring.domain` e `misp_ioc_scoring.sharing.domain` de importar `sqlalchemy`, `pymisp` e `pydantic`; rodar `uv run --extra dev lint-imports` (o domínio já cumpre, então o contrato só impede regressão).

---

## Phase 2: Foundational (pré-requisitos e DDD de base D1–D6)

**Purpose**: rede de segurança da refatoração, ajuste de `input_revision` e as peças
de domínio que o CARIOCA reutiliza.

**⚠️ CRITICAL**: US2 não começa antes do fim desta fase.

### Rede de segurança e pré-requisitos

- [X] T003 Criar o teste de caracterização `tests/integration/test_blocking_characterization.py`. Monta uma fixture fixa com 2 endpoints (um confiável e um com coleta `failed`), observações `domain` e `url` cobrindo todos os motivos (`eligible`, `removed`, `type`, `to_ids`, `analysis`, `warninglist`, `expired`, `indeterminate`, `rejected`), warninglists (`string`, `hostname`, `cidr` e uma `regex`) e rejeições. Congela o relógio com `monkeypatch` do atributo `datetime` em `<pkg>/scoring/infrastructure/persistence/simple_blocking.py` e em `<pkg>/sharing/infrastructure/scheduling/scheduler.py` para um `as_of` fixo. Executa `simple_blocking.run` e o cálculo do conjunto desejado do Pi-hole (com um `PiHole` falso que registra os hosts). Compara decisões `(source_instance_id, attribute_uuid, block, reason, expires_at)` e hosts desejados com o golden `tests/integration/fixtures/blocking_characterization.json`, gerado na primeira execução com a opção `--update-golden` (registrada via `pytest_addoption` em `tests/integration/conftest.py`) e versionado. Deve passar antes de T009.
- [X] T004 [P] Acrescentar casos em `tests/unit/test_input_revision.py`: mudar `published` incrementa a revisão; mudar `tags`, `collected_at`, `distribution` ou `raw_value` com o mesmo valor normalizado não incrementa.
- [X] T005 Incluir `'published'` em `RELEVANT_FIELDS` em `<pkg>/collection/domain/input_revision.py`, porque `first_publications` só considera observações publicadas (FeedRank), e atualizar a docstring para listar o motivo de cada campo (`event_uuid` agrupa o CADE; `source_created_at` ordena o FeedRank; `source_modified_at` é o tempo do frescor).

### D1–D2: tipos de domínio na API da coleta e confiança da origem

- [X] T006 [P] Criar testes unitários em `tests/unit/test_source_snapshot.py` para `SourceSnapshot.trusted(now, max_age)`: falso com `generation == 0`, com `status != "completed"`, com `last_success_at` nulo e com `last_success_at <= now - max_age`; verdadeiro caso contrário. As fronteiras devem bater com o SQL atual de `unavailable_blocking_sources` em `<pkg>/collection/api.py`.
- [X] T007 Criar `<pkg>/collection/domain/snapshots.py` com as dataclasses congeladas de `data-model.md` ("Tipos de domínio do ajuste de DDD"):
  - `SourceSnapshot(source_instance_id, generation, status, last_success_at)` com `trusted(now, max_age)`;
  - `ObservationSnapshot` (campos de `Observation` mais `ioc_id`, `normalized_value`, `input_revision`);
  - `CollectionSnapshot(sources, observations, warninglists, rejections)`.

  `IndicatorRejection` em `<pkg>/collection/domain/rejections.py` ganha `attribute_id: int | None = None`, que `scoring` já lê.
- [X] T008 Em `<pkg>/collection/api.py`:
  - implementar `collection_snapshot(session) -> CollectionSnapshot`, convertendo os modelos ORM em tipos de domínio dentro da própria função (observações ativas e removidas, como `blocking_snapshot` faz hoje);
  - implementar `untrusted_sources(session, now, max_age)` usando `SourceSnapshot.trusted`;
  - implementar `source_generations(session)`;
  - manter `blocking_snapshot`, `unavailable_blocking_sources` e `blocking_generations` como aliases finos até T011 ([contracts/collection-api.md](./contracts/collection-api.md), "Transição").
- [X] T009 Adaptar `<pkg>/scoring/application/simple_blocking.py::evaluate` e `<pkg>/scoring/infrastructure/persistence/simple_blocking.py` para consumir `CollectionSnapshot`. Usar `source.trusted(as_of, max_age)` no lugar da checagem manual de `generation`, `status` e `last_success_at` (D2). Nenhum atributo de modelo ORM pode ser lido fora de `collection`. T003 e `tests/integration/test_simple_blocking.py` devem continuar idênticos.
- [X] T010 Adaptar `<pkg>/sharing/infrastructure/scheduling/scheduler.py` para `untrusted_sources` e `source_generations`; rodar T003 e `tests/integration/test_pihole_sharing.py`.
- [X] T011 Remover os aliases `blocking_snapshot`, `unavailable_blocking_sources` e `blocking_generations` de `<pkg>/collection/api.py` e atualizar os testes que os chamam (`tests/integration/test_blocking_collection_snapshot.py`).

### D3: índice de warninglist

- [X] T012 [P] Criar testes em `tests/unit/test_warninglist_index.py` para `WarninglistIndex`:
  - modo `strict`: igualdade, hostname e subdomínio, host de URL casando com lista `hostname`, URL com IP casando com `cidr`; entrada não suportada na origem dá `None`;
  - modo `fr027`: as mesmas igualdades, e entrada não suportada é ignorada (`False`).

  Reaproveitar os casos de `tests/unit/test_blocking_warninglists.py` e `tests/unit/test_warninglist_matching.py` para garantir equivalência com `blocking_warninglist_membership` e `WarninglistEntry.matches`.
- [X] T013 Implementar `WarninglistIndex` em `<pkg>/collection/domain/warninglists.py`:
  - construído uma vez por lista de entradas de uma origem;
  - estruturas: conjunto de valores exatos, conjunto de sufixos de hostname consultado por rótulos (do host completo ao domínio de segundo nível) e lista de redes `ip_network` por versão;
  - `match(kind, value, mode) -> bool | None`, com `mode` em (`"strict"`, `"fr027"`).

  `WarninglistEntry.matches` continua existindo e passa a ser usado só pelos testes de equivalência.
- [X] T014 Expor `warninglist_index(entries, mode)` em `<pkg>/collection/api.py`. Trocar o uso de `blocking_warninglist_membership` em `<pkg>/scoring/infrastructure/persistence/simple_blocking.py` por um índice por origem com `mode="strict"`. Remover `blocking_warninglist_membership` e `warninglist_membership`. T003 continua idêntico.

### D4: decaimento, hostname e tipos

- [X] T015 [P] Criar testes em `tests/unit/test_decay.py` para `DecayGroup(name, D, T).freshness(t_days)`:
  - `t` negativo dá `None` e `t >= T` dá `0`;
  - valores do Notion: domain `t=158,2835` dá `69,687`; ip `t=3` dá `43,16`; hash `t=30` dá `29,29`;
  - igualdade com `scoring/domain/simple_blocking.freshness` atual para `t` em 0, 1, 364,9 e 365.
- [X] T016 Criar `<pkg>/scoring/domain/decay.py` com `DecayGroup` e as constantes `DOMAIN = DecayGroup("domain", 0.7, 365)`, `IP = DecayGroup("ip", 1.5, 7)` e `HASH = DecayGroup("hash", 2, 60)`. Reescrever `freshness` em `<pkg>/scoring/domain/simple_blocking.py` para usar `DOMAIN` (URL usa o mesmo grupo no bloqueio simples, conforme a 002).
- [X] T017 Mover a validação de hostname DNS para uma função única `dns_hostname(kind, value) -> str | None` em `<pkg>/collection/domain/normalization.py`, reaproveitando `_domain`:
  - `domain` valida o próprio valor; `url` extrai o host com os esquemas `http`, `https` e `ftp`, sem `userinfo`;
  - IP literal, TLD numérico e host de um rótulo só dão `None`.

  Expor a função em `<pkg>/collection/api.py`. Apagar `<pkg>/sharing/domain/pihole_hostname.py`, trocar o import em `<pkg>/sharing/infrastructure/scheduling/scheduler.py` e mover `test_dns_hostname` de `tests/unit/test_pihole_policy.py` para `tests/unit/test_normalization.py`, mantendo os mesmos parâmetros.
- [X] T018 [P] Criar constantes nomeadas de tipos em `<pkg>/collection/domain/indicators.py`: `DOMAIN_TYPES = frozenset({"domain", "hostname"})`, `IP_TYPES = frozenset({"ip-src", "ip-dst"})`, `HASH_TYPES` e `URL_TYPES = frozenset({"url"})`. Usá-las em `normalization.py` e `warninglists.py`. Em `<pkg>/scoring/domain/simple_blocking.py`, criar `BLOCKABLE_TYPES = frozenset({"domain", "url"})`. Fazer `active_blocking_values` em `<pkg>/collection/api.py` receber os tipos como parâmetro em vez de fixá-los.

### D5: enums e Decisão de bloqueio

- [X] T019 Criar `<pkg>/scoring/domain/blocking.py` com:
  - `BlockingReason(StrEnum)` com exatamente `eligible`, `removed`, `type`, `to_ids`, `analysis`, `warninglist`, `expired`, `indeterminate`, `rejected`, `stale`;
  - `ScoreModel(StrEnum)` com `default` e `carioca`;
  - a dataclass congelada `BlockingDecision(source_instance_id, attribute_uuid, attribute_id, block, reason, as_of, expires_at, generation, evidence)`.

  `simple_blocking.decision` passa a devolver `BlockingReason`, e `evaluate` passa a devolver `BlockingDecision`. A persistência grava `reason.value`, então as colunas não mudam.
- [X] T020 Fazer `blocking_decision` e `effective_blocks` em `<pkg>/scoring/api.py` devolverem `BlockingDecision` em vez de `RowMapping`, com os mesmos campos e `rule_version`, e reexportar `ScoreModel`. Atualizar `<pkg>/sharing/domain/pihole_policy.py` para receber `ScoreModel`, e `<pkg>/sharing/infrastructure/scheduling/scheduler.py` para usar atributos em vez de chaves de dicionário. Em `tests/integration/test_simple_blocking.py` e `tests/integration/test_pihole_sharing.py`, trocar só a forma de acesso (`row["block"]` → `row.block`), sem mudar nenhum valor esperado. T003 continua idêntico.

### D6: caso de uso do bloqueio simples

- [X] T021 Mover a orquestração de `<pkg>/scoring/infrastructure/persistence/simple_blocking.py::run` para `run_blocking(as_of, snapshot, max_age, store)` em `<pkg>/scoring/application/simple_blocking.py`. A porta `BlockingStore(Protocol)` tem `start(run_id, as_of)`, `upsert(decisions)` e `finish(run_id)`. Em `<pkg>/scoring/infrastructure/persistence/simple_blocking.py`, `run` dá lugar a `BlockingRunner`, um gerenciador de contexto que obtém os locks consultivos (`874202` sem espera, depois `874201`), abre a transação, lê o `CollectionSnapshot` e entrega um `BlockingStore`; se o lock não estiver livre, entrega `None`. Uma falha registra a execução `failed`. O job em `<pkg>/entrypoints/scoring_sharing.py` abre o runner, lê o `as_of` **uma vez**, dentro do contexto, e chama `run_blocking`. A infraestrutura não importa `scoring.application`.
- [X] T022 Criar `tests/architecture/test_public_api_types.py`. Sobre a fixture de integração, ele chama cada função pública de `<pkg>/collection/api.py` e `<pkg>/scoring/api.py`, percorre o valor devolvido (inclusive iteráveis e campos de dataclass) e falha se encontrar instância de `misp_ioc_scoring.shared.database.Base`, `Row` ou `RowMapping`.

**Checkpoint**: D1–D6 concluídas. Os 77 testes antigos, a integração e T003 passam
sem mudança de valor esperado, e `lint-imports` passa.

---

## Phase 3: User Story 2 - Calcular e explicar o score Carioca (Priority: P2)

**Goal**: recálculo diário completo da População válida com `as_of` único, calculado
por observação e agregado no IOC pela observação de maior prioridade, com
explicação, persistência, top-N e Pi-hole no modo `carioca` (FR-010, FR-012 a FR-014,
FR-022 a FR-025; 002 FR-008).

**Independent Test**: com uma configuração de teste aprovada e fixtures montadas com
os insumos do Notion, a execução reproduz `hotels-stays55501.com` (CADE 6,5218; CADE'
19,544; E 31,017; A 69,687; P 75,838 no cenário v3). Exclui `url` e observações
`to_ids=false` com motivo, dá 50 em MinMax degenerado e conclui sem scores em
população vazia. Com `approved: false`, o serviço não inicia.

### Tests for User Story 2

- [X] T023 [P] [US2] Criar `tests/unit/test_carioca_components.py`:
  - mapeamentos TL (`threat_level_id` 1/2/3/4 → 100/66/33/0) e SA (`analysis` 0/1/2 → 0/50/100);
  - Event `0,4·TL + 0,2·SA + 0,4·CADE'` (`hotels-stays55501.com`: TL 33, SA 50, CADE' 19,544 → E 31,017; evento 19: TL 100, SA 100, CADE 18,7994 → 67,5198 no cálculo v2);
  - frescor contra `as_of` pelos três `DecayGroup` (T016), sem usar o relógio do sistema.
- [X] T024 [P] [US2] Criar `tests/unit/test_cade.py`:
  - `CS_i = (1 − e^(−n²/(2σ²)))·100` com β = 1/16;
  - `hotels-stays55501.com`: n = 60/48/10 e σ = 917,29/165,15/0,45 → CS 0,2137/4,1359/100,0000 e CADE 6,5218;
  - evento 19 → CADE 18,7994;
  - regra explícita de σ = 0 lida da configuração;
  - MinMax entre eventos (6,5218 com mínimo 0,0000037 e máximo 33,3707 → 19,544).

  É o **nível 1** da SC-015: σ entra como dado do teste, com os valores do Notion (σ populacional bruto). Não usa o estimador da configuração.
- [X] T025 [P] [US2] Criar `tests/unit/test_feed_rank.py`:
  - primeiro publicador por par `(tipo, valor)` com desempate por `source_created_at` e depois `orgc_uuid`;
  - grafo dirigido "quem publicou depois aponta para quem publicou antes", com peso = pares em comum;
  - PageRank 0,85 com 50 iterações e nós sem saída redistribuídos uniformemente (`dangling: uniform`);
  - `V_o = 50·c_o·100 + 50·MinMax(PR)_o` e `Source = MinMax(V_o)`;
  - grafo de 3 organizações com valores calculados à mão e documentados no teste;
  - só observações publicadas e `to_ids=true` contam.
- [X] T026 [P] [US2] Criar `tests/unit/test_population_priority.py`:
  - elegibilidade e motivos de exclusão `type_without_decay_group` (inclui `url` e tipos fora da lista fechada), `expired`, `not_to_ids`, `unpublished` (evento não publicado), `missing_data` (TL, SA, timestamp, categoria ou `orgc` ausente ou desconhecido) e `incomplete_configuration`;
  - motivo do IOC pela precedência `incomplete_configuration` > `missing_data` > `unpublished` > `not_to_ids` > `type_without_decay_group` > `expired`; IOC com uma observação válida e outra sem `orgc` não é excluído;
  - MinMax com máximo = mínimo dá 50 e registra o componente em `minmax_degenerate`;
  - população vazia conclui sem scores e com aviso;
  - SPOTIS (ideal 100, pesos 1/3) igual a `(S'+E'+A')/3` em 1.000 triplas aleatórias com semente fixa;
  - escopos de normalização: `CADE'` entre eventos com observação `to_ids` ativa, `E'` entre eventos com observação válida, `A'` e `S'` entre observações válidas.
- [X] T027 [P] [US2] Criar `tests/unit/test_aggregation_selection.py`:
  - o IOC recebe a observação de maior `priority`;
  - em empate vence o menor `source_created_at` e depois o menor `(source_instance_id, attribute_uuid)`;
  - `observations_evaluated` correto;
  - `rank` denso por prioridade decrescente; `in_top_n` marca exatamente os `top_n` primeiros, inclusive com empate na fronteira e com `top_n` maior que a população.
- [X] T028 [P] [US2] Criar `tests/unit/test_carioca_configuration.py`:
  - rejeitar YAML com peso negativo, pesos que não somam 1, `top_n` ausente, estimador de σ ausente, regra σ = 0 ausente, `type_groups` ausente ou com `url`, ou `aggregation` diferente de `max-observation`;
  - `content_hash` estável para o mesmo conteúdo canônico;
  - `approved: false` impede o cálculo com erro explícito;
  - resultados idênticos para entrada, configuração e `as_of` idênticos.
- [X] T029 [P] [US2] Criar `tests/unit/test_scoring_metrics.py` para as métricas da exportação a partir de tabelas fixture: última execução bem-sucedida (`as_of`, duração), população válida, exclusões por motivo, avisos de população vazia e MinMax degenerado, e corte do top-N.
- [X] T030 [P] [US2] Criar `tests/integration/test_scoring_persistence.py` em PostgreSQL:
  - persistência de execução, estatísticas, `avaliacao_observacao` (única por `(scoring_run_id, source_instance_id, attribute_uuid)`), `resultado_score` (único por `(scoring_run_id, ioc_id)`) e exclusões;
  - execução falha não substitui a vigente;
  - o lock consultivo impede duas execuções simultâneas;
  - o papel do coletor não escreve em `scoring`.
- [X] T031 [P] [US2] Criar `tests/integration/test_scoring_api.py` para [contracts/scoring-api.md](./contracts/scoring-api.md):
  - `current_carioca_run` ignora execuções falhas e em andamento;
  - `carioca_scores` filtra `min_score` e `top_n_only`, ordena por `rank` e pagina;
  - `explain` traz a observação vencedora, σ, componentes degenerados e a limitação do proxy `orgc`.
- [X] T032 [P] [US2] Criar `tests/integration/test_carioca_to_ids_independence.py`: coletar a mesma fixture com `MISP_TO_IDS_ONLY=true` e depois `false`, executar o scoring com o mesmo `as_of` e verificar scores, ranks e exclusões idênticos para os IOCs `to_ids=true`.

### Implementation for User Story 2

- [ ] T033 [P] [US2] Avaliar os estimadores de σ (limite no percentil 95 e escala log) sobre os dados do MISP de estudos descritos no Caderno de Projetos (Notion), tratando categorias com σ = 0. Registrar evidência e configuração proposta em `docs/sigma-estimator-evaluation.md`, com os valores recalculados (σ, CADE, CADE', E e P) de `hotels-stays55501.com` e do evento 19 também em `tests/unit/fixtures/carioca_reference_approved.json`. **Depende do dono**: exige acesso aos dados do MISP de estudos, que não estão no repositório. Isso bloqueia a aprovação (T043) e o nível 2 da SC-015 (T034), não o código.
- [ ] T034 [US2] Criar `tests/unit/test_carioca_reference_approved.py` (**nível 2** da SC-015): carrega a configuração de `config/carioca-orgc-proxy-v3.yaml` e os valores de `tests/unit/fixtures/carioca_reference_approved.json` (T033) e confere σ, CADE, CADE', E e P dos casos de referência. Fica com `pytest.skip` explícito enquanto o arquivo de valores não existir ou `approved` for `false`; com `approved: true`, a ausência do arquivo faz o teste falhar.
- [X] T035 [P] [US2] Implementar `<pkg>/scoring/domain/carioca_configuration.py`, com a dataclass congelada `CariocaConfiguration` e o carregamento e validação do YAML:
  - α 0,4/0,2/0,4 e β 1/16 (não negativos, somando 1); `model_id` `carioca-orgc-proxy-v3` e `cade_id` `cade-seminormal-v2`;
  - σ: `method`, `version` e `zero_rule`;
  - `type_groups` fechado (hash: md5, sha1, sha256, sha512, ssdeep, imphash, tlsh, filename, malware-sample e `filename|<hash>`; ip: ip-src, ip-dst, ip-src|port, ip-dst|port; domain: domain, hostname, domain|ip; sem `url`);
  - `scoring_to_ids_only: true`, `aggregation: max-observation` e `normalization_scopes`;
  - `feed_rank` (damping 0,85, iterations 50, dangling uniform, pesos 50/50) e SPOTIS (pesos 1/3, ideal 100);
  - `top_n` sem default; `approved`, `approved_by`, `approved_at`, `evidence_ref`;
  - `content_hash` SHA-256 do YAML canônico. O MinMax com máximo = mínimo é fixo em 50 e não configurável.
- [X] T036 [US2] Implementar `<pkg>/scoring/domain/carioca_inputs.py`: mapear TL e SA, e mapear tipo → `DecayGroup` pela configuração. Valores ausentes ou desconhecidos (TL, SA, timestamp, categoria ou `orgc_uuid`) dão resultado inválido explícito com motivo `missing_data`, e observação de evento não publicado dá `unpublished`; nunca um score inventado.
- [X] T037 [US2] Implementar `<pkg>/scoring/domain/cade.py`: contagem `n_i` por evento sobre observações `to_ids=true` ativas (reaproveitando `collection/domain/event_aggregates.CATEGORIES` via `collection.api`); σ por categoria com o estimador aprovado e a regra σ = 0; `CS_i`; CADE bruto; `CADE'` por MinMax no escopo `cade`.
- [X] T038 [US2] Implementar `<pkg>/scoring/domain/carioca_components.py`: `A` via `DecayGroup.freshness` com `t` = dias entre `source_modified_at` e `as_of`; Event `0,4·TL + 0,2·SA + 0,4·CADE'`; tudo contra `as_of`, nunca contra o relógio.
- [X] T039 [US2] Implementar `<pkg>/scoring/domain/feed_rank.py` em Python puro, conforme T025, devolvendo, por organização, `first_pairs`, `contribution`, `pagerank`, `pagerank_norm`, `value` e `source_norm`. Gera erro de configuração quando `feed_rank` está ausente e expõe o texto da limitação do proxy para a explicação.
- [X] T040 [US2] Implementar `<pkg>/scoring/domain/population.py` (elegibilidade por observação e motivos de exclusão por IOC, conforme `data-model.md`; um IOC com ao menos uma observação válida não é excluído) e `<pkg>/scoring/domain/priority.py` (MinMax com o 50 fixo e registro em `minmax_degenerate`; SPOTIS com pesos iguais, resultado de 0 a 100).
- [X] T041 [US2] Implementar `<pkg>/scoring/domain/aggregation.py` (observação vencedora com o desempate do plano e `observations_evaluated`) e `<pkg>/scoring/domain/selection.py` (`rank` denso e `in_top_n` com o `top_n` da configuração).
- [X] T042 [US2] Criar os mapeamentos em `<pkg>/scoring/infrastructure/persistence/carioca.py` e a migration `migrations/versions/0008_carioca_scoring.py` (`down_revision` = `0007_pihole_policy`), no schema `scoring`:
  - `configuracao_carioca` (versão, hash, conteúdo, aprovação);
  - `execucao_scoring` (`as_of`, início, fim, estado `running`/`completed`/`failed`, como `execucao_bloqueio`, contadores, `warnings`);
  - `estatisticas_populacao`;
  - `avaliacao_observacao` (campos de `data-model.md`, única por `(scoring_run_id, source_instance_id, attribute_uuid)`);
  - `resultado_score` (com `as_of`, componentes brutos e normalizados, `input_revision`, `rank`, `in_top_n`, `winning_source_instance_id`, `winning_attribute_uuid`, `observations_evaluated`; único por `(scoring_run_id, ioc_id)`);
  - `exclusao_score`.

  Grants seguem `0001_module_roles`: escrita para o papel do scoring e leitura para o `observer`.
- [X] T043 [US2] Criar `config/carioca-orgc-proxy-v3.yaml` com todos os parâmetros de T035 e `approved: false` até `docs/sigma-estimator-evaluation.md` (T033) ser aprovado pelo dono; montar o diretório no serviço `scoring-sharing` de `compose.yaml` em modo somente leitura e adicionar `CARIOCA_CONFIG_PATH` a `.env.example`. Remover `CARIOCA_TOP_N` de `.env.example` (linha 29): o `top_n` vem só do YAML.
- [X] T044 [US2] Implementar o caso de uso `run_carioca(as_of, snapshot, configuration, store)` em `<pkg>/scoring/application/score_population.py`, seguindo o molde de D6:
  - recebe o `CollectionSnapshot` (T008) e filtra `to_ids=true`;
  - calcula estatísticas (σ, mínimos e máximos por escopo, FeedRank);
  - avalia toda observação válida sem reaproveitar execuções anteriores, agrega por IOC e atribui rank e top-N;
  - persiste avaliações, resultados, exclusões e estatísticas pela porta `CariocaStore`;
  - com população vazia, conclui sem scores, registra um WARNING estruturado e grava o aviso em `execucao_scoring.warnings`;
  - nunca emite score válido com configuração ou dados incompletos.
- [X] T045 [US2] Implementar `CariocaRunner` em `<pkg>/scoring/infrastructure/persistence/carioca.py`, no molde do `BlockingRunner` (T021): gerenciador de contexto com lock consultivo próprio, mais o lock da coleta `874201` enquanto lê o snapshot em `REPEATABLE READ`, e entrega da porta `CariocaStore` com gravação em lotes de 1.000. A execução falha é registrada sem substituir a vigente. A infraestrutura não importa `scoring.application`.
- [X] T046 [US2] Ligar o job em `<pkg>/entrypoints/scoring_sharing.py` (abre o `CariocaRunner`, lê o `as_of` uma vez e chama `run_carioca`) e agendá-lo por `<pkg>/scoring/infrastructure/scheduling/scheduler.py` com `SCORING_DAILY_CRON`, `max_instances=1` e `coalesce`. Em `<pkg>/shared/configuration.py`, retirar `SCORING_CARIOCA_ENABLED` da lista `NOT_IMPLEMENTED`: com `true`, a inicialização exige `CARIOCA_CONFIG_PATH` legível, configuração válida e `approved: true`, ou falha com `CARIOCA_CONFIGURATION_NOT_APPROVED`. Atualizar `tests/integration/test_module_activation.py` e `tests/unit/test_configuration.py`.
- [X] T047 [US2] Implementar em `<pkg>/scoring/api.py` `current_carioca_run`, `carioca_scores` (paginado) e `exclusions`, conforme [contracts/scoring-api.md](./contracts/scoring-api.md), com dataclasses congeladas `CariocaRun` e `CariocaScore` definidas em `<pkg>/scoring/domain/carioca_results.py`.
- [X] T048 [US2] Implementar `explain` em `<pkg>/scoring/application/score_explanation.py` e expô-lo em `<pkg>/scoring/api.py`. A explicação usa os termos canônicos do glossário e inclui: `as_of`, rank e top-N, observação vencedora, `observations_evaluated`, componentes brutos e normalizados, σ das categorias, componentes com MinMax degenerado, motivo de exclusão e a limitação do proxy `orgc`.
- [X] T049 [P] [US2] Adicionar as funções de métrica em `tools/metrics/scoring.py` (última execução bem-sucedida, `as_of`, duração, população válida, exclusões por motivo, avisos de população vazia e MinMax degenerado, corte do top-N), lendo só tabelas exportadas, e registrá-las em `tools/export_observability.py`.
- [X] T050 [US2] Implementar o modo `carioca` do Pi-hole em `<pkg>/sharing/infrastructure/scheduling/scheduler.py` e `<pkg>/sharing/domain/pihole_policy.py`:
  - ler `current_carioca_run` e `carioca_scores(min_score=PIHOLE_CARIOCA_MIN_SCORE)`, sem top-N;
  - se a execução vigente for mais antiga que `SCORE_MAX_AGE_HOURS`, não enviar, preservar as entradas e registrar WARNING;
  - aplicar `warninglist_index(..., mode="strict")` e `untrusted_sources`;
  - só `domain` e `hostname` (URL fica fora do CARIOCA);
  - evidência com `model: "carioca"`, `as_of`, `priority_score` e `scoring_run_id`.

  Retirar `PIHOLE_CARIOCA_NOT_IMPLEMENTED` de `<pkg>/shared/configuration.py`. O modo `carioca` exige `SCORING_CARIOCA_ENABLED=true`.
- [X] T051 [P] [US2] Acrescentar casos do modo `carioca` em `tests/integration/test_pihole_sharing.py`: acima e abaixo do corte, execução vigente vencida (nada enviado e entradas preservadas), sem execução, origem não confiável e URL ignorada.
- [ ] T052 [US2] Criar o benchmark `tests/benchmark/test_scoring_performance.py` com o gerador `tests/benchmark/dataset.py`: cerca de 270 mil IOCs válidos sintéticos, com distribuição realista de categorias, organizações (27, duas com cerca de 92% dos pares) e idades. Quando `BENCHMARK_DATABASE_URL` estiver definido, usar uma cópia do MISP de estudos e conferir também a tabela de fontes do Notion §4 (CIRCL S' 100; CthulhuSPRL.be 59,92; Krawczyk 47,05; PageRank do CIRCL 0,40966). O recálculo completo deve terminar em até 1 hora (SC-011). Registrar a decisão entre memória e SQL em `research.md`.
- [ ] T053 [P] [US2] Acrescentar ao `docs/domain-glossary.md` os termos "Avaliação de observação" e "Observação vencedora", com sinônimos a evitar.

**Checkpoint**: US2 pode ser testada sozinha; com configuração de teste aprovada o
job diário produz scores explicáveis, e o Pi-hole `carioca` funciona.

---

## Phase 4: User Story 3 - Rastrear IOCs com dados de entrada alterados (Priority: P2)

**Goal**: o candidato a re-scoring rastreia IOCs cuja revisão de entrada mudou desde o
último score bem-sucedido, sem influir em quais IOCs são calculados (FR-007 a
FR-011). Inclui as etapas D7–D8 do ajuste de DDD, que tiram do repositório a regra
que gera essas revisões.

**Independent Test**: alterar um campo relevante de uma observação marca o IOC uma
vez; alterar um campo irrelevante não marca. Um recálculo bem-sucedido limpa a
pendência; falha ou revisão concorrente a mantém.

### Tests for User Story 3

- [ ] T054 [P] [US3] Criar `tests/unit/test_reconcile_snapshot.py` para `reconcile_snapshot(existing, received, collected_at, removal_ratio)`:
  - atualização com `source_modified_at` mais antigo é ignorada;
  - valor inválido ou não suportado vira rejeição e marca a observação ativa como removida;
  - valor válido cria o IOC pela identidade `(type, normalized_value)` com a entidade `IOC`;
  - rejeição anterior é resolvida;
  - observação ausente do snapshot vira remoção;
  - IOC com campo relevante alterado entra no conjunto de revisões, e campo irrelevante não entra;
  - troca de IOC marca o antigo e o novo;
  - remoção acima de `removal_ratio` recusa a reconciliação.
- [ ] T055 [P] [US3] Criar `tests/unit/test_rescoring_candidates.py`: derivação de candidatos por `input_revision` diferente da revisão do último score válido; várias observações viram um só candidato; candidatura não muda o conjunto pontuado; gravar score não altera `input_revision`.
- [ ] T056 [P] [US3] Criar `tests/integration/test_rescoring_candidates.py` em PostgreSQL: upsert de candidato, revisão que muda durante o cálculo mantém a pendência, falha de scoring mantém a pendência, e gravar score não remarca.

### Implementation for User Story 3

- [ ] T057 [US3] (D7) Criar `<pkg>/collection/domain/reconciliation.py` com a dataclass `Changeset` (inserções, atualizações, IOCs novos, rejeições a gravar e a resolver, remoções e `ioc_ids` cuja revisão sobe) e a função pura `reconcile_snapshot`. Ela usa `normalize`, `inputs_changed` e a entidade `IOC` de `<pkg>/collection/domain/indicators.py`, e leva para o domínio a trava de remoção hoje em `<pkg>/collection/application/reconcile.py`.
- [ ] T058 [US3] (D7) Reescrever `<pkg>/collection/infrastructure/persistence/repositories/observations.py::apply` para:
  - carregar as observações, IOCs e rejeições da origem em lote, eliminando o `SELECT` por observação;
  - chamar `reconcile_snapshot` e gravar o `Changeset` na mesma transação, mantendo os locks e a checagem `collection_checkpoint_superseded`;
  - devolver as contagens (aplicadas, rejeitadas por motivo, removidas).

  `tests/integration/test_collection_persistence.py`, `tests/integration/test_rejections.py` e T003 continuam iguais.
- [ ] T059 [US3] (D8) Apagar `<pkg>/collection/application/reconcile.py` (a regra está agora em T057) e retirar do repositório os imports de `collection.application`. Mover `report_status` para dentro do caso de uso `<pkg>/collection/application/collect.py`, que o chama depois de `repository.apply` ou `repository.failed`.
- [ ] T060 [US3] (D8) Adicionar em `pyproject.toml` contratos import-linter `forbidden` de `misp_ioc_scoring.<módulo>.infrastructure` para `misp_ioc_scoring.<módulo>.application` em `collection`, `scoring` e `sharing`. Depois de T021 e T045, `scoring` já cumpre o contrato. Se `sharing.infrastructure.scheduling` ainda importar `sharing.application.sync_pihole` (resolvido em T070), registrar a exceção temporária com `ignore_imports` e removê-la em T070.
- [ ] T061 [US3] Completar o status da coleta em `<pkg>/collection/application/status.py` (resto da T037 antiga): o log estruturado de cada execução inclui contagem de rejeições por motivo e por origem, vinda de T058, sem credenciais, valores brutos ou payloads; acrescentar o caso em `tests/unit/test_collection_use_case.py`.
- [ ] T062 [US3] Criar o mapeamento em `<pkg>/scoring/infrastructure/persistence/candidates.py` e a migration `migrations/versions/0009_rescoring_candidates.py` (schema `scoring`), com `candidato_rescoring`: `ioc_id` como chave primária, `pending`, `input_revision`, `reason`, `marked_at`, `last_attempt_at` e `last_error`, com um candidato por IOC lógico.
- [ ] T063 [US3] Implementar `<pkg>/scoring/domain/rescoring.py`: um IOC é candidato quando o `input_revision` lido no snapshot difere da revisão do seu último `resultado_score` válido. A derivação nunca altera `input_revision`.
- [ ] T064 [US3] Implementar `<pkg>/scoring/application/score_candidates.py` e chamá-lo de `run_carioca` (T044) depois do cálculo:
  - registrar a revisão usada por IOC;
  - limpar `pending` só se o cálculo do IOC teve sucesso e `collection.api.current_input_revision` ainda for igual;
  - não selecionar quais IOCs são pontuados nem reaproveitar resultados.
- [ ] T065 [US3] Preservar as pendências em falhas e em mudanças concorrentes de entrada, registrando `last_attempt_at` e `last_error` seguro, em `<pkg>/entrypoints/scoring_sharing.py` e `<pkg>/scoring/infrastructure/persistence/candidates.py`.
- [ ] T066 [P] [US3] Adicionar a métrica de candidatos em `tools/metrics/candidates.py` (pendentes, idade do mais antigo, último erro) com teste em `tests/unit/test_candidate_metrics.py`.

**Checkpoint**: US3 rastreia mudanças relevantes, e a coleta não tem mais regra de
negócio no repositório.

---

## Phase 5: User Story 4 - Compartilhar IOCs com peers MISP (Priority: P3)

**Goal**: enviar a peers MISP só IOCs da execução vigente que estejam no top-N,
atinjam o mínimo do peer e não constem em warninglist, preservando a distribuição
nativa do MISP (FR-015 a FR-017, FR-027). Começa pela etapa D9, que dá ao Pi-hole o
molde de caso de uso que os peers vão seguir.

**Independent Test**: com um MISP isolado e um peer de sync, IOCs abaixo do mínimo,
fora do top-N ou em warninglist não são enviados; timeout não vira confirmação; a
repetição reconcilia pelo UUID; com score mais antigo que 48 horas, nada é enviado e
o operador é avisado.

### D9: caso de uso do Pi-hole

- [ ] T067 [P] [US4] Criar `tests/unit/test_managed_entry.py` para `ManagedEntry.is_owned_by(remote: RemoteEntry)`, com os mesmos casos de `owned()` em `<pkg>/sharing/application/sync_pihole.py`: comentário igual à marca, `id` inteiro, `remote_id` igual quando conhecido, `groups == (0,)` e `enabled`.
- [ ] T068 [US4] Criar `<pkg>/sharing/domain/pihole_entries.py` com `RemoteEntry(id, comment, groups, enabled)` e `ManagedEntry(hostname, marker, remote_id, status, evidence)`, com `is_owned_by`. Fazer `<pkg>/sharing/adapters/pihole.py` traduzir o JSON remoto para `RemoteEntry` em `lookup` e `<pkg>/sharing/infrastructure/persistence/pihole.py::entries` devolver `ManagedEntry`.
- [ ] T069 [US4] Criar `plan_and_reconcile(as_of, decisions, sources, pihole, store, policy)` em `<pkg>/sharing/application/sync_pihole.py`, com as portas `DecisionsPort`, `SourcesPort`, `PiHolePort` e `PiHoleStore`. Movem para lá a montagem do conjunto desejado e a função `revalidate`, hoje em `<pkg>/sharing/infrastructure/scheduling/scheduler.py`. `reconcile` passa a usar `ManagedEntry.is_owned_by`, e `owned()` é removido.
- [ ] T070 [US4] Reduzir `<pkg>/sharing/infrastructure/scheduling/scheduler.py` a um `PiHoleRunner` (lock consultivo `874203`, registro da política, transações `REPEATABLE READ` e implementação das portas sobre `collection.api` e `scoring.api`), sem importar `sharing.application`. O job em `<pkg>/entrypoints/scoring_sharing.py` abre o runner e chama `plan_and_reconcile`. T003, T051 e `tests/integration/test_pihole_sharing.py` continuam iguais. Remover o `ignore_imports` temporário de T060.

### Tests for User Story 4

- [ ] T071 [P] [US4] Criar `tests/unit/test_sharing_eligibility.py`:
  - limite do mínimo por peer (igual passa, abaixo não);
  - top-N;
  - warninglist em modo `fr027` torna inelegível e registra o motivo;
  - score de execução anterior à vigente é inválido;
  - execução vigente mais antiga que `SCORE_MAX_AGE_HOURS` (padrão 48) suspende o envio com WARNING e aviso persistido;
  - execução falha mais nova não substitui a vigente;
  - o envio retoma depois de nova execução bem-sucedida;
  - distribuição (FR-016): IOC com observações `0` e `3` é elegível e sai com `3`; com `1` e `3`, sai com `1`; com `4` e o peer no sharing group, sai com `4` e o mesmo grupo; com `4` e o peer fora do grupo, ou só `0`, ou só eventos não publicados, fica inelegível com `distribution_not_allowed`; atributo com `5` herda a distribuição e o sharing group do evento; sem `event_sharing_group_id` em dado legado, `5` sobre evento `4` conta como `0`;
  - em empate de distribuição entre observações que alcançam o peer, vale o desempate da agregação (`source_created_at`, depois `(source_instance_id, attribute_uuid)`).
- [ ] T072 [P] [US4] Criar `tests/unit/test_peer_configuration.py`: mínimo fora de 0–100 ou campo de peer ausente impede o compartilhamento com erro explícito; segredos continuam como referências; o hash da política efetiva muda quando a configuração muda.
- [ ] T073 [P] [US4] Criar `tests/contract/test_misp_sharing.py` com respostas MISP simuladas:
  - criação idempotente do evento de saída por peer (`outbound_event_uuid`) e dos atributos com UUID v5 de `peer_id` + `ioc_id`;
  - o evento de saída leva a distribuição máxima da política do peer, e cada atributo leva a distribuição (e o sharing group, se `4`) da observação que o tornou elegível, nunca mais ampla;
  - quando a distribuição permitida diminui antes de uma nova tentativa, o atributo é atualizado ou removido antes da publicação;
  - publicação registra `requested`, e `confirmed` só depois de ler o atributo no peer;
  - timeout vira `ambiguous` e é reconciliado pela leitura antes de repetir;
  - aceitação parcial confirma só os itens aceitos;
  - IOC que deixou de ser elegível tem o atributo removido (soft delete) antes da publicação.
- [ ] T074 [P] [US4] Criar `tests/integration/test_sharing_persistence.py` em PostgreSQL: registro da política efetiva, estados das tentativas, idempotência da repetição (uma tentativa corrente por `(peer_id, ioc_id)`), elegibilidade reavaliada antes de nova tentativa e papel do coletor sem escrita em `sharing`.
- [ ] T075 [P] [US4] Criar `tests/unit/test_sharing_metrics.py` para as métricas da exportação: tentativas por estado, política efetiva e indicador de suspensão calculado pela idade da última execução bem-sucedida contra `SCORE_MAX_AGE_HOURS`.

### Implementation for User Story 4


- [ ] T076 [P] [US4] Implementar `<pkg>/sharing/domain/sharing.py`: Política de compartilhamento por peer e a função de elegibilidade (score válido da execução vigente, maior ou igual ao mínimo de 0 a 100, `in_top_n` e ausência em warninglist `fr027`), com a regra de distribuição `DistributionDecision` de `data-model.md` ("Elegibilidade de distribuição": basta uma observação ativa, de evento publicado, com distribuição efetiva `1`, `2` ou `3`, ou `4` com o servidor do peer no sharing group; vale a mais restritiva, com `4` mais restritiva que `1`; `0` nunca alcança), e com motivos de inelegibilidade em `StrEnum` (`below_minimum`, `outside_top_n`, `warninglist`, `stale_score`, `no_valid_score`, `distribution_not_allowed`) e estados de tentativa em `StrEnum` (`eligible`, `requested`, `confirmed`, `failed`, `ambiguous`, `ineligible`, `suspended`).
- [ ] T077 [P] [US4] Implementar `<pkg>/sharing/infrastructure/peer_configuration.py`, que lê do ambiente do container `scoring-sharing` (`MISP_PEERS_SECRET_REF` apontando para JSON com `peer_id`, `base_url`, `credential_secret_ref`, `minimum_priority_score`, `distribution` e `sharing_group_uuid` opcional), mais `SHARING_INTERVAL_SECONDS`, `SHARING_RETRY_ATTEMPTS` e `SHARING_RETRY_BACKOFF_SECONDS`. Valida na inicialização (configuração inválida ou ausente impede o compartilhamento com erro explícito) e registra a política efetiva com hash e timestamp a cada início; mudanças só valem após reiniciar.
- [ ] T078 [US4] Criar os mapeamentos em `<pkg>/sharing/infrastructure/persistence/models.py` e a migration `migrations/versions/0010_misp_sharing.py` (schema `sharing`):
  - `peer_misp`, com `credential_secret_ref` marcado com o comentário `secret`;
  - `politica_compartilhamento`, com `policy_hash`, `loaded_at` e `peers` sem segredos;
  - `tentativa_compartilhamento`, com `peer_id`, `ioc_id`, `scoring_run_id`, `policy_hash`, `outbound_attribute_uuid`, `permitting_source_instance_id`, `permitting_attribute_uuid`, `outbound_distribution` (0–4), `outbound_sharing_group_uuid` opcional, estado, `attempts`, `next_attempt_at`, `last_error` seguro, timestamps e uma tentativa corrente por `(peer_id, ioc_id)`.
- [ ] T079 [P] [US4] Acrescentar em `tests/contract/test_misp_collection.py` o caso em que o evento tem `distribution=4` com `SharingGroup` e o atributo tem `distribution=5`, verificando que a observação guarda `event_sharing_group_id`, e em `tests/unit/test_input_revision.py` que mudar `event_sharing_group_id` não incrementa a revisão (não é entrada do CARIOCA).
- [ ] T080 [US4] Guardar o sharing group do evento: campo `event_sharing_group_id: str | None` em `<pkg>/collection/adapters/schemas.py` (lido do `sharing_group_id` do evento) e em `<pkg>/collection/domain/observations.py`; coluna em `<pkg>/collection/infrastructure/persistence/models.py` e migration `migrations/versions/0011_event_sharing_group.py` (`down_revision` = `0010_misp_sharing`), nula para dados legados até a recoleta. Implementar `ObservationSnapshot.effective_distribution()` em `<pkg>/collection/domain/snapshots.py`: o menor entre `distribution` e `event_distribution`, com `5` herdando do evento, e o sharing group correspondente.
- [ ] T081 [US4] Implementar o adaptador `<pkg>/sharing/adapters/synchronization.py` sobre `<pkg>/shared/misp/client.py`, conforme [contracts/misp-sharing.md](./contracts/misp-sharing.md) ("Revisão 2026-11-24"):
  - garantir o evento de saída por peer, com a distribuição máxima da política;
  - ler da instância local os sharing groups e seus servidores no início de cada rodada, para decidir se o peer pertence a um grupo;
  - gravar em cada atributo a `outbound_distribution` e o `outbound_sharing_group_uuid` da decisão;
  - fazer upsert e soft delete de atributos por UUID v5, com `to_ids=true`;
  - publicar o evento e ler o atributo no peer pelo UUID;
  - acompanhar jobs assíncronos separadamente da confirmação de recebimento;
  - não registrar credenciais nem valores de indicador.
- [ ] T082 [US4] Implementar o caso de uso `share_eligible(as_of, run, scores, warninglists, policy, peers, store)` em `<pkg>/sharing/application/share_eligible.py`, no molde de T069:
  - lê `current_carioca_run` e `carioca_scores(top_n_only=True, min_score=<mínimo do peer>)`;
  - suspende todos os envios novos, com WARNING e aviso persistido, se a execução vigente for mais antiga que `SCORE_MAX_AGE_HOURS`;
  - registra os motivos de inelegibilidade;
  - lê as observações do IOC por `collection.api` (`ObservationSnapshot.effective_distribution()`) e aplica `DistributionDecision` por peer;
  - preserva os controles nativos de publicação, distribuição e sharing group.
- [ ] T083 [US4] Implementar as transições de estado das tentativas, a reconciliação por UUID depois de timeout ambíguo, as retentativas limitadas com backoff, a aceitação parcial e a reavaliação de score, top-N, warninglist, distribuição, idade do score e política antes de cada nova tentativa, em `<pkg>/sharing/application/share_eligible.py` e `<pkg>/sharing/infrastructure/persistence/misp.py`.
- [ ] T084 [US4] Ligar o job de peers em `<pkg>/entrypoints/scoring_sharing.py` (intervalo `SHARING_INTERVAL_SECONDS`, `max_instances=1`, lock consultivo próprio) e registrar os estados lidos pela exportação em `<pkg>/sharing/application/sharing_status.py`. Em `<pkg>/shared/configuration.py`, retirar `SHARING_MISP_ENABLED` de `NOT_IMPLEMENTED`: com `true`, exigir `SCORING_CARIOCA_ENABLED=true` e peers válidos. Atualizar `compose.yaml`, `.env.example` e `tests/integration/test_module_activation.py`.
- [ ] T085 [P] [US4] Adicionar as métricas de compartilhamento em `tools/metrics/sharing.py` (tentativas por estado, pendentes e falhas, hash da política efetiva, suspenso ou não), lendo só tabelas exportadas, e registrá-las em `tools/export_observability.py`.

**Checkpoint**: US4 envia somente IOCs elegíveis, com estados auditáveis, e Pi-hole e
peers MISP seguem o mesmo molde de caso de uso.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T086 [P] (D10) Acrescentar a coluna "Nome no código" em `docs/domain-glossary.md` para cada termo, por exemplo: Observação de origem → `Observation` / `collection.observacao_origem`; Decisão de bloqueio → `BlockingDecision` / `scoring.decisao_bloqueio`; Entrada gerenciada → `ManagedEntry` / `sharing.pihole_entry`. Registrar que as tabelas `pihole_*` mantêm o nome em inglês por decisão do plano.
- [ ] T087 [P] Criar `tests/architecture/test_domain_vocabulary.py`, que varre mensagens para operador e docstrings em `<pkg>/` em busca dos sinônimos a evitar de `docs/domain-glossary.md` (SC-009).
- [ ] T088 [P] Criar `tests/integration/test_migrations.py`: instalação limpa de `0000` a `0010` e upgrade a partir de um banco em `0007` com dados, verificando que as decisões de bloqueio e as entradas do Pi-hole são preservadas.
- [ ] T089 [P] Criar `tests/integration/test_source_equivalence.py`: dados de domínio equivalentes vindos de dois endpoints MISP distintos produzem as mesmas decisões de scoring, candidatos e elegibilidade (FR-021, SC-010).
- [ ] T090 [P] Criar os fixtures end-to-end com Compose e a configuração de MISP isolado (com peer de sync e Pi-hole de teste) em `tests/e2e/conftest.py` e `tests/e2e/config/`.
- [ ] T091 Atualizar `specs/001-misp-ioc-scoring/quickstart.md` e `README.md` com os comandos finais: Compose, pytest, benchmark, coleta, scoring CARIOCA, aprovação da configuração, Pi-hole `carioca`, variáveis dos peers e peer de sync isolado. Atualizar também `specs/002-bloqueio-simples/contracts/pihole.md`, `specs/002-bloqueio-simples/spec.md` (cenário 2 da US3 e FR-008) e `specs/002-bloqueio-simples/quickstart.md`: o modo `carioca` agora funciona e só envia domínios e hostnames, sem URL.
- [ ] T092 Rodar `docker compose config`, `docker compose up --build`, `uv run --extra dev lint-imports` e `uv run --extra dev pytest -q` com `TEST_DATABASE_URL`, seguindo `quickstart.md`. Registrar em `specs/001-misp-ioc-scoring/quickstart.md` e `specs/002-bloqueio-simples/quickstart.md` os serviços ou verificações indisponíveis (inclui a T040 pendente da 002).
- [ ] T093 Fazer a revisão de segurança com o agente `x9`: tratamento de segredos (peers, Pi-hole, banco), fronteiras de módulo, distribuição MISP, dependências fixadas em `uv.lock` e `pyproject.toml`, e ausência de valores de indicador em logs, em `<pkg>/`, `compose.yaml` e `.env.example`; registrar os achados em `docs/security-review.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001–T002)**: sem dependências.
- **Foundational (T003–T022)**: depende do Setup. T003 vem **antes** de qualquer
  etapa D. Dentro da fase: T006–T011 (D1–D2) → T012–T014 (D3) → T015–T018 (D4) →
  T019–T020 (D5) → T021 (D6) → T022. T004–T005 são independentes das etapas D.
- **US2 (T023–T053)**: depende da Foundational. T033 (σ) pode começar já no Setup,
  porque só bloqueia T043 (`approved: true`) e o nível 2 da SC-015 (T034); T034 fica
  com skip explícito até lá.
- **US3 (T054–T066)**: T054–T061 (D7–D8 e status) dependem só da Foundational;
  T062–T065 dependem de T044 (job CARIOCA).
- **US4 (T067–T085)**: T067–T070 (D9) dependem de T050 (Pi-hole `carioca`), para não
  mexer duas vezes no mesmo scheduler; T071–T085 dependem de T047 (scoring.api); T080
  depende de T007 (snapshots) e de T078 (migration `0010`, que vem antes da `0011`).
- **Polish (T086–T093)**: depois das histórias desejadas.

### User Story Dependencies

- **US2**: fundação concluída. É o núcleo das demais.
- **US3**: a refatoração da coleta (D7–D8) é independente; os candidatos precisam do
  job da US2.
- **US4**: precisa de `scoring.api` (T047) e do Pi-hole refatorado (D9).

### Within Each User Story

- Testes antes da implementação correspondente; nas etapas D, o teste de
  caracterização T003 é a referência.
- Domínio → persistência e migration → caso de uso → infraestrutura do job →
  entrypoint → métricas.
- Mesmo arquivo nunca em paralelo: `<pkg>/collection/api.py` (T008, T011, T014, T017,
  T018), `<pkg>/scoring/api.py` (T020, T047, T048), `<pkg>/shared/configuration.py`
  (T046, T050, T084), `<pkg>/entrypoints/scoring_sharing.py` (T046, T065, T084) e
  `<pkg>/sharing/infrastructure/scheduling/scheduler.py` (T010, T017, T020, T050, T070).

### Parallel Opportunities

- Setup: T002 com T001.
- Foundational: T004, T006, T012, T015 e T018 (arquivos de teste e de domínio
  distintos) assim que T003 estiver verde.
- US2: todos os testes T023–T032; T033, T035, T049 e T053.
- US3: T054–T056 e T066.
- US4: T067 e T071–T075; T076, T077 e T085.
- Polish: T086–T090.
- US4: T079 junto com os demais testes da história.

---

## Parallel Example: User Story 2

```bash
# Testes de domínio do CARIOCA, todos em arquivos distintos:
Task: "T023 [US2] tests/unit/test_carioca_components.py"
Task: "T024 [US2] tests/unit/test_cade.py"
Task: "T025 [US2] tests/unit/test_feed_rank.py"
Task: "T026 [US2] tests/unit/test_population_priority.py"
Task: "T027 [US2] tests/unit/test_aggregation_selection.py"
Task: "T028 [US2] tests/unit/test_carioca_configuration.py"

# Em paralelo, fora do caminho crítico:
Task: "T033 [US2] docs/sigma-estimator-evaluation.md"
Task: "T035 [US2] <pkg>/scoring/domain/carioca_configuration.py"
```

## Parallel Example: Foundational (depois de T003)

```bash
Task: "T004 tests/unit/test_input_revision.py"
Task: "T006 tests/unit/test_source_snapshot.py"
Task: "T012 tests/unit/test_warninglist_index.py"
Task: "T015 tests/unit/test_decay.py"
```

---

## Implementation Strategy

### MVP: Foundational + US2

1. Setup (T001–T002) e o teste de caracterização (T003).
2. DDD de base D1–D6 (T006–T022), um commit por etapa, sempre com T003 verde.
3. US2 (T023–T053). Validar os casos do Notion e o benchmark.
4. **Parar e validar**: com uma configuração de teste aprovada, o job diário gera
   scores explicáveis e o Pi-hole `carioca` envia só domínios acima do corte. A
   ativação em produção espera a aprovação de σ (T033 → T043).

### Incremental Delivery

1. Foundational → código atual mais limpo, mesmo comportamento (T003 verde).
2. US2 → scores CARIOCA e Pi-hole `carioca`.
3. US3 → coleta sem regra no repositório, e rastreabilidade de candidatos.
4. US4 → Pi-hole no molde de caso de uso e peers MISP.
5. Polish → glossário, e2e, migrations, segurança e quickstart.

### Agentes

- `bigode` implementa; `banza` aprova o desenho de US4 (evento de saída por peer)
  antes de T081; `x9` faz T093; `escritor` revisa T086 e T091.

---

## Notes

- `[P]` = arquivos diferentes, sem dependência pendente.
- Cada etapa D é um commit próprio (Conventional Commits, por exemplo
  `refactor(collection): devolve tipos de domínio na api`).
- Não ativar `SCORING_CARIOCA_ENABLED` nem `SHARING_MISP_ENABLED` em produção antes de
  T043 aprovado e da validação de US4 contra um MISP isolado.
