# Implementation Plan: Plataforma de Scoring e Compartilhamento de IOCs

**Branch**: `main` (feature `001-misp-ioc-scoring`) | **Date**: 2026-11-10, revisado em 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-misp-ioc-scoring/spec.md`

> **Revisão 2026-11-24.** A coleta (US1) e a feature 002 (bloqueio simples e Pi-hole)
> já estão implementadas. Esta revisão retoma o que falta: score CARIOCA (US2),
> candidatos a re-scoring (US3) e compartilhamento com peers MISP (US4). Ela também
> alinha o plano ao código e às decisões da 002. As mudanças estão em
> [Revisão 2026-11-24](#revisão-2026-11-24-retomada-de-us2-us4); o restante do
> documento continua valendo.

## Summary

Coletar e normalizar IOCs acionáveis (`to_ids=true`) e contexto de endpoints MISP em
cadências próprias, persistir observações com proveniência, recalcular e explicar
diariamente as prioridades CARIOCA de toda a população de IOCs válidos (com data de
referência `as_of`) e compartilhar somente IOCs que estejam no top-N, atinjam um score
mínimo configurado por peer e não constem em warninglist, respeitando a distribuição
nativa do MISP. A solução será composta por três
containers: PostgreSQL, worker de coleta/normalização e worker de scoring/compartilhamento.
A aplicação é um **monolito modular**: um único pacote Python, dividido em três módulos
de negócio (`collection`, `scoring`, `sharing`) mais um núcleo compartilhado mínimo
(`shared`), com fronteiras verificadas automaticamente. As regras de domínio ficam
isoladas dos adaptadores MISP e de persistência dentro de cada módulo.

## Technical Context

**Language/Version**: Python 3.12 como baseline de implementação

**Primary Dependencies**: PyMISP para integração MISP; SQLAlchemy 2.x para
persistência; Alembic para migrações; Pydantic para validação nas fronteiras externas;
APScheduler 3.x com uma instância por worker; openpyxl para a exportação de
observabilidade para Excel (FR-028); pytest para testes. Não adicionar pandas
até que uma necessidade concreta do algoritmo justifique o custo.

**Storage**: PostgreSQL em container dedicado; volume persistente; schema relacional
com migrações versionadas.

**Testing**: pytest; unitários para regras de domínio; integração com PostgreSQL para
transações, constraints, migrações e idempotência; testes de contrato com respostas
MISP simuladas; cenários end-to-end em ambiente de teste com MISP disponível.

**Target Platform**: Linux em containers Docker; execução local ou em host compatível
com Docker Compose.

**Project Type**: Aplicação de workers internos com três containers, sem CLI, API nem
interface de usuário; operação por variáveis de ambiente e observação por um script de
exportação do banco para Excel (FR-028, FR-029).

**Performance Goals**: O recálculo diário da população completa deve concluir em até
1 hora com dados representativos (ordem de 270 mil IOCs válidos; SC-011), medido por
benchmark. Os jobs de coleta processam lotes paginados e respeitam a cadência por
endpoint; demais SLOs só após benchmarks com dados reais.

**Constraints**: Coleta e jobs de scoring são síncronos dentro de cada execução.
Execuções do mesmo job não podem se sobrepor. Uma falha parcial não avança checkpoint
nem limpa candidatos pendentes. Parâmetros CARIOCA não publicados exigem configuração
explícita versionada; scoring não ocorre com configuração incompleta. O scoring diário
recalcula toda a população válida com um único `as_of` (FR-010), porque MinMax e
frescor dependem da população e da data. A coleta traz só `to_ids=true` por padrão
(FR-026). Compartilhamento exige top-N, score mínimo por peer, ausência em warninglist
e autorização/distribuição nativa do MISP (FR-016, FR-027). Peers, mínimo por peer e
credenciais (referências a segredos) vêm das variáveis de ambiente do container de
scoring/sharing, lidas na inicialização; mudar exige reiniciar o container (FR-015).

**Scale/Scope**: Uma instância de coletor e uma de scoring no primeiro deployment;
uma instância MISP por endpoint configurado e um conjunto explícito de peers MISP.
Volume total e número de endpoints permanecem dependentes da implantação.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio/regra | Avaliação | Evidência do plano |
|---|---|---|
| Scoring explicável e baseado em evidência | PASS | Persistir score, critérios, snapshot de entradas e versão da configuração. |
| Preservar dados de origem | PASS | Manter valor original, valor normalizado e observação MISP separadamente. |
| Determinismo e testes | PASS | Configuração versionada, casos de referência e testes em PostgreSQL. |
| Dados de ameaça não confiáveis | PASS | Validar payloads nas fronteiras; não registrar credenciais; aplicar permissões MISP. |
| Simplicidade e interoperabilidade | PASS | Três containers e um único pacote modular, sem broker ou pandas sem necessidade demonstrada. |
| DDD e linguagem ubíqua | PASS | IOC, Observação de origem, Resultado de score, Candidato a re-scoring e Política de compartilhamento são os termos canônicos. Domínio separado dos adaptadores. |
| Observabilidade sem superfície de ataque | PASS | Sem CLI/API/UI; exportação somente leitura, sem segredos, com valores neutralizados contra interpretação como fórmula (princípio IV). |
| Monolito modular | PASS | Três módulos com API pública, propriedade única de tabelas e fronteiras impostas por import-linter e permissões de banco. |
| Arquitetura requerida | PASS | Python/Docker, database, collector/normalizer e scoring/sharing. |
| Governança de parâmetros CARIOCA | PASS | Configuração explícita/versionada para lacunas da publicação (σ robusto, normalização do CADE, FeedRank `orgc-proxy`, top-N, desempate MinMax); sem score quando incompleta. |
| Determinismo com dependência temporal | PASS | `as_of` único por execução, registrado em execução e score; frescor calculado contra `as_of`, não contra o relógio. |

**Gate pré-pesquisa**: PASS. A spec fornece escopo e decisões funcionais; detalhes
não especificados na publicação foram transformados em configurações explícitas, sem
defaults implícitos. Nenhuma violação constitucional requer exceção.

## Project Structure

### Documentation (this feature)

```text
specs/001-misp-ioc-scoring/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── misp-collection.md
│   ├── misp-sharing.md
│   └── observability-export.md
└── tasks.md
```

### Source Code (repository root)

```text
src/misp_ioc_scoring/
├── shared/                       # núcleo compartilhado: sem regra de negócio
│   ├── configuration.py
│   ├── database.py               # engine, sessão, transação
│   ├── logging.py
│   ├── errors.py
│   └── misp/client.py            # cliente PyMISP reutilizado por collection e sharing
├── collection/                   # módulo 1: coletar e normalizar
│   ├── api.py                    # única superfície importável por outros módulos (somente leitura)
│   ├── domain/                   # indicators, observations, normalization, input_revision,
│   │                             # event_aggregates (n_i por categoria), warninglists
│   ├── application/              # collect, reconcile, status
│   ├── adapters/                 # schemas e consulta paginada MISP
│   └── infrastructure/           # persistence/ (models, repositories), scheduling/
├── scoring/                      # módulo 2: calcular e explicar o score CARIOCA
│   ├── api.py                    # consulta de scores válidos por IOC
│   ├── domain/                   # carioca_configuration, carioca_inputs, carioca_components,
│   │                             # cade (σ robusto + MinMax), feed_rank (orgc-proxy),
│   │                             # population (elegibilidade/exclusão), priority, selection (top-N),
│   │                             # rescoring (derivação de candidatos)
│   ├── application/              # score_population, score_candidates (rastreabilidade),
│   │                             # score_explanation
│   └── infrastructure/           # persistence/, scheduling/
├── sharing/                      # módulo 3: compartilhar com peers MISP
│   ├── domain/                   # sharing
│   ├── application/              # share_eligible, sharing_status
│   ├── adapters/                 # synchronization (push nativo)
│   └── infrastructure/           # persistence/
└── entrypoints/                  # raízes de composição, um por container
    ├── collector.py              # monta collection
    └── scoring_sharing.py        # monta scoring + sharing

migrations/
config/                           # carioca-orgc-proxy-v3.yaml (aprovação explícita)
tools/                            # export_observability.py: relê o banco por reflexão, sem importar módulos
docs/                             # glossário de domínio, avaliação do estimador de σ
tests/
├── unit/
├── integration/
├── contract/
├── architecture/                 # fronteiras de módulo e propriedade de tabelas
├── benchmark/                    # SC-011: recálculo diário em até 1 hora
└── e2e/
```

**Structure Decision**: O repositório não contém aplicação ou testes preexistentes.
Um único pacote Python (monolito modular) com três módulos de negócio e um núcleo
`shared` sem regras de negócio. Cada container executa um `entrypoint`, que é a única
camada autorizada a conhecer vários módulos. PostgreSQL é o terceiro container. Não se
cria serviço HTTP público nem broker nesta feature sem requisito adicional.

## Arquitetura Modular

### Módulos e dependências permitidas

| Módulo | Responsabilidade | Pode importar | Não pode importar |
|---|---|---|---|
| `shared` | configuração, banco, logging, erros, cliente MISP | biblioteca padrão e terceiros | qualquer módulo de negócio |
| `collection` | coleta, normalização, IOC, Observação de origem, checkpoints | `shared` | `scoring`, `sharing`, `entrypoints` |
| `scoring` | configuração CARIOCA, componentes, score, execuções, candidatos | `shared`, `collection.api` | `sharing`, `entrypoints`, internos de `collection` |
| `sharing` | peers, política, tentativas, push MISP | `shared`, `collection.api`, `scoring.api` | `entrypoints`, internos de `collection` e `scoring` |
| `entrypoints` | composição e processo de cada container | todos os módulos | — (e `collector` e `scoring_sharing` não se importam) |

Dentro de cada módulo vale a regra de camadas: `domain` não importa `application`,
`adapters` nem `infrastructure`; `application` não importa `adapters`/`infrastructure`
diretamente, apenas portas definidas no domínio ou na própria aplicação. A comunicação
entre módulos ocorre só por `api.py` (funções/tipos somente leitura), nunca pelos
modelos SQLAlchemy ou repositórios do outro módulo.

### Propriedade de tabelas (escritor único)

| Módulo dono (único escritor) | Tabelas |
|---|---|
| `collection` | `ioc` (inclui `input_revision`), `rejeicao_indicador`, `observacao_origem` (inclui `orgc_uuid`, `removed_at`), `endpoint_coleta` (inclui filtro `to_ids`), `entrada_warninglist` |
| `scoring` | `configuracao_carioca`, `estatisticas_populacao`, `resultado_score`, `exclusao_score`, `execucao_scoring`, `candidato_rescoring` |
| `sharing` | `peer_misp`, `politica_compartilhamento`, `tentativa_compartilhamento` |

- Cada módulo usa um **schema PostgreSQL próprio** (`collection`, `scoring`, `sharing`).
  Outros módulos leem apenas via `api.py`; consultas diretas às tabelas alheias são
  proibidas.
- **Candidato a re-scoring é derivado, não escrito pela coleta.** A coleta incrementa
  `ioc.input_revision` somente quando muda um campo de entrada do algoritmo; o módulo
  `scoring` marca o IOC como candidato quando `input_revision` difere da revisão do
  último score. Gravar score não altera `input_revision`, evitando laços.
- **Recálculo diário completo (FR-010).** Todo dia o módulo `scoring` fixa um `as_of`,
  recalcula `estatisticas_populacao` (σ por categoria, mínimos/máximos, FeedRank por
  organização) e os scores de toda a população válida. O recálculo não reaproveita
  resultados anteriores nem depende do candidato a re-scoring, que é apenas
  rastreabilidade (FR-007, FR-011): indica que os dados de entrada de um IOC mudaram
  desde o último score bem-sucedido e permanece pendente até um recálculo bem-sucedido
  sobre a revisão vigente. O processamento em memória ou em SQL é escolhido pelo
  benchmark de SC-011.
- A exportação de observabilidade (`tools/`) é uma ferramenta de relatório fora dos
  módulos: usa o papel de banco `observer`, somente leitura em todos os schemas, e lê as
  tabelas por reflexão, sem importar código de módulo (o contrato do import-linter
  proíbe `tools` de importar `collection`, `scoring` ou `sharing`). É a única exceção à
  regra "só via `api.py`", justificada por ser leitura sem regra de negócio.
- Os dois containers de aplicação usam papéis de banco distintos: o do coletor escreve
  só no schema `collection`; o de scoring/sharing escreve em `scoring` e `sharing` e
  tem somente leitura em `collection`.

### Verificação automática

- **import-linter** (em `pyproject.toml`): contratos de camadas por módulo, de
  independência (`collection` ← `scoring` ← `sharing`, sem ciclos), de `api.py` como
  única porta entre módulos, e de `entrypoints.collector` independente de
  `entrypoints.scoring_sharing`.
- `tests/architecture/`: roda import-linter e confere, nos metadados do SQLAlchemy,
  que cada tabela pertence ao schema do módulo que a mapeia.
- Integração em PostgreSQL confere que o papel do coletor não consegue escrever em
  `scoring` ou `sharing`.

## Decisões de Design do Algoritmo (CARIOCA v3)

Modelo `carioca-orgc-proxy-v3` / CADE `cade-seminormal-v2` (versões gravadas na
Configuração CARIOCA). Fórmulas e casos reais: páginas do Notion "CARIOCA — fórmulas e
exemplos reais" e "CADE — fórmulas e exemplos reais"; detalhes em
[research.md](./research.md).

| Tema | Decisão | Requisito |
|---|---|---|
| População | Só tipo com grupo de decaimento (hash, ip, domain) e frescor > 0; demais excluídos com motivo | FR-022 |
| Recálculo | Diário, população completa, `as_of` único | FR-010 |
| CADE | `CS_i = (1 − e^(−n²/2σ²))·100`, β = 1/16, depois MinMax entre eventos | FR-024 |
| σ por categoria | Estimador robusto (limite no percentil 95 ou escala log); método, versão e caso σ = 0 na configuração, **a aprovar antes de ativar** | FR-023 |
| Source | FeedRank com `orgc` como proxy: primeiro a publicar + PageRank 0,85, 50/50, MinMax | FR-025 |
| Event | `0,4·TL + 0,2·SA + 0,4·CADE'` (TL 100/66/33/0; SA 0/50/100) | FR-012 |
| Attribute | `(1 − (t/Ta)^(1/Da))·100`, `t` contra `as_of`; hash 2/60, ip 1,5/7, domain 0,7/365 | FR-012 |
| Priority | MinMax e SPOTIS com pesos 1/3 (equivale a `(S'+E'+A')/3`) | FR-012 |
| Seleção | Top-N configurável (sem padrão implícito) e mínimo por peer | FR-016 |
| Warninglist | Mantém score; inelegível para compartilhar, com motivo. Pertinência: igualdade exata, CIDR (IP) e hostname/subdomínio (domínio); regex e substring ignorados e registrados como não suportados | FR-027 |
| MinMax degenerado | Máximo = mínimo → componente normalizado 50, registrado na explicação; população vazia → execução concluída sem scores e com aviso | FR-024 |
| Candidato a re-scoring | Só rastreabilidade; recálculo diário independe dele | FR-007, FR-010, FR-011 |
| Observabilidade | Script `tools/export_observability.py`: exporta cada tabela de todos os schemas para uma aba Excel e calcula uma aba de métricas; somente leitura (papel `observer`), sem segredos, valores neutralizados contra fórmulas, limite de linhas por aba sem truncamento silencioso; avisos = log WARNING + registro persistido | FR-028 |
| Colunas secretas | Comentário PostgreSQL `secret` nos modelos; exportação as ignora; teste de arquitetura valida colunas de nome sensível | FR-028 |
| Tempos e frequências | Todos por variáveis de ambiente validadas na inicialização (cadências, scoring diário, janelas, backoff, validade do score com padrão 48 h, limite de linhas da exportação); mudança só após reinício | FR-029 |
| Peers e política | Variáveis de ambiente do container scoring/sharing, aplicadas no reinício; política efetiva registrada a cada inicialização e referenciada por cada tentativa | FR-015 |
| Indicadores rejeitados | Registro persistente (`rejeicao_indicador`, módulo `collection`): origem, valor bruto, tipo MISP, motivo, momento; uma por origem e motivo; não cria IOC; valor bruto nunca vai a logs | FR-003 |
| Validade do score | Compartilhamento usa a última execução de scoring bem-sucedida; acima de 48 h, suspende e avisa o operador | FR-016 |
| Desempenho | Recálculo completo em até 1 h (~270 mil IOCs); benchmark decide processamento em memória ou SQL | SC-011 |
| Coleta | `to_ids=true` por padrão, por endpoint; reconciliação marca `removed_at` com trava de remoção em massa | FR-026 |

**Risco aberto**: o método de σ ainda não está definido (o limite no percentil 95 dá
σ = 0 em categorias raras). É uma tarefa de pesquisa que bloqueia a ativação da
Configuração CARIOCA, não a implementação das fórmulas.

## Revisão 2026-11-24: retomada de US2–US4

### Estado de partida

| Parte | Estado no código | O que falta |
|---|---|---|
| US1 coleta | Implementada: `collection/` completo, migrations `0000`–`0003`, scheduler por endpoint, `collection/api.py` | Contagem de rejeições por motivo e origem no status (`collection/application/status.py`); revisar os campos de `input_revision` (abaixo) |
| 002 bloqueio simples e Pi-hole | Implementada: `scoring.decisao_bloqueio`, `sharing.pihole_*`, migrations `0004`–`0007`, flags | T040 da 002: rodar a suíte com PostgreSQL e Pi-hole isolado |
| US2 CARIOCA | Nada implementado; `SCORING_CARIOCA_ENABLED` falha com `NOT_IMPLEMENTED` | Tudo: domínio, configuração, persistência, job, explicação, benchmark |
| US3 candidatos | Só o incremento de `ioc.input_revision` na coleta | Tabela, derivação e conclusão de candidatos, métricas |
| US4 peers MISP | Nada; `SHARING_MISP_ENABLED` falha com `NOT_IMPLEMENTED` | Política, peers, tentativas, adaptador de sync, métricas |

O `tasks.md` está desatualizado em relação ao código: T036, T037 e T039 aparecem
como pendentes, mas existem, com T037 incompleta. Os caminhos de migration
`0003_scoring`, `0004_rescoring_candidates` e `0005_sharing` já foram usados pela 002.
Regenerar as tarefas com `/speckit-tasks` depois desta revisão.

### Technical Context (deltas)

- **Dependências**: nenhuma nova. FeedRank (PageRank) e CADE em Python puro; ver
  [research.md](./research.md#revisão-2026-11-24). A decisão entre processamento em
  memória e em SQL fica com o benchmark (SC-011).
- **Migrations**: novas revisões a partir de `0008`: `0008_carioca_scoring`,
  `0009_rescoring_candidates`, `0010_misp_sharing`.
- **Configuração**: `config/carioca-orgc-proxy-v3.yaml` (versionado, `approved: false`
  até a avaliação de σ ser aprovada). As flags da 002 continuam: `SCORING_CARIOCA_ENABLED`
  passa a exigir configuração aprovada; `SHARING_MISP_ENABLED` passa a exigir peers
  válidos; `PIHOLE_SCORE_MODEL=carioca` passa a funcionar.
- **Testes**: corrigir `pythonpath` do pytest no `pyproject.toml` (hoje
  `tests/unit/test_observability_export.py` só roda com `PYTHONPATH=.`). Os testes de
  integração exigem `TEST_DATABASE_URL`; sem ele são pulados.

### Decisões desta revisão

| Tema | Decisão | Origem |
|---|---|---|
| Unidade de cálculo | S, E e A são calculados **por observação de origem** ativa, como na referência do Notion ("cada IoC = atributo MISP", que herda `orgc` e evento) | Notion "CARIOCA — fórmulas e exemplos reais" |
| Agregação no IOC | O Resultado de score do IOC é o da **observação de maior prioridade**; a observação vencedora e o número de observações avaliadas entram na explicação. Rank e top-N são por IOC lógico, sem duplicar valores | Dono, 2026-11-24 |
| Desempate da agregação | Em prioridade igual, vence a observação mais antiga (`source_created_at`) e depois o menor `(source_instance_id, attribute_uuid)`, para o resultado ser determinístico | Constituição III |
| URL no CARIOCA | **Fora** dos grupos de decaimento, como no artigo: `url` é excluída com motivo "tipo sem grupo de decaimento". O decaimento de URL da 002 vale só para o bloqueio simples | Dono, 2026-11-24 |
| Grupos de tipo | Lista fechada na configuração, seguindo a tabela do Notion: hash (md5, sha1, sha256, sha512, ssdeep, imphash, tlsh, filename, malware-sample, `filename\|<hash>`), ip (ip-src, ip-dst, ip-src\|port, ip-dst\|port), domain (domain, hostname, domain\|ip). Tipo fora da lista é excluído | FR-022 |
| Filtro `to_ids` no scoring | O CARIOCA usa só observações com `to_ids=true`, em todos os componentes (população, CADE, FeedRank), mesmo que a coleta rode com `MISP_TO_IDS_ONLY=false` para a 002. Assim o score não muda conforme o filtro de coleta | FR-026, research da 001 |
| Tempo do frescor | `t` = dias entre `source_modified_at` (o `attributes.timestamp` do MISP) e o `as_of` | Notion §2.1, mesma escolha da 002 |
| Normalização de E e A | `CADE'` por MinMax entre todos os eventos com observação `to_ids` ativa; `E'` por MinMax entre os eventos com ao menos uma observação válida; `A'` e `S'` por MinMax entre as observações válidas | Notion §3.1 (cenário v3) |
| Leitura da coleta | Nova função de `collection.api` que lê, numa única transação `REPEATABLE READ`, observações ativas, revisões dos IOCs e entradas de warninglist suportadas. Hoje `active_iocs()` é relida três vezes e `warninglist_membership()` varre todas as entradas a cada IOC; isso não escala a 270 mil IOCs | FR-010, SC-011 |
| Warninglist para peers MISP | Regra da 001 (FR-027): igualdade, CIDR e hostname/subdomínio; regex e substring ignorados e registrados. Reaproveitar o matcher de `collection/domain/warninglists.py` | FR-027 |
| Warninglist para Pi-hole `carioca` | Regra mais estrita da 002: entrada não suportada ou snapshot da origem vencido torna a origem indeterminada, sem envio. O Pi-hole `carioca` aplica corte `PIHOLE_CARIOCA_MIN_SCORE`, sem top-N | 002 FR-008, FR-011 |
| Campos de `input_revision` | Alinhar `RELEVANT_FIELDS` com o que o algoritmo lê: incluir `published` (usado na primeira publicação do FeedRank) e manter `event_uuid` (agrupa o CADE) e `source_created_at` (ordem do FeedRank). O `input_revision=0` dado a IOCs novos é intencional: o mesmo `apply` incrementa a revisão e o IOC termina com 1 | FR-008, FR-009 |
| Observação sem `orgc` ou não publicada | Fica fora da população, com motivo `missing_data` (sem `orgc`) ou `unpublished`; o IOC só é excluído se nenhuma outra observação for válida | Clarificação 2026-11-24 |
| Distribuição no envio a peers | Um IOC é elegível se **ao menos uma** observação ativa, de evento publicado, alcança o peer pela distribuição nativa (ver [research.md](./research.md#distribuição-no-envio-a-peers)). Entre as que alcançam, usa-se a mais restritiva, e o atributo de saída leva essa distribuição (e o sharing group, se houver), nunca uma mais ampla | FR-016, clarificação 2026-11-24 |
| Sharing group do evento | A coleta passa a guardar `event_sharing_group_id` em `observacao_origem` (hoje só guarda o do atributo); sem ele, atributo com distribuição `5` em evento `4` não tem sharing group conhecido e é tratado como `0` (não alcança) | FR-016; migration `0011_event_sharing_group` no schema `collection` |
| Valores de referência | Dois níveis: as fórmulas são testadas com σ dado como entrada contra os números do Notion; a SC-015 usa valores recalculados com o σ aprovado, registrados em `docs/sigma-estimator-evaluation.md` | SC-015, clarificação 2026-11-24 |
| Composição dos casos de uso | Os entrypoints montam os adaptadores e chamam `application`; `infrastructure` só implementa portas (SQL, locks, transações, agendamento) e nunca importa `application` | Princípio VI; ajuste D6, D8 e D9 |
| Estado de execução | `execucao_scoring` usa `running`, `completed` e `failed`, como `execucao_bloqueio` e `endpoint_coleta` | Linguagem ubíqua |
| Fonte do top-N | Só o `top_n` do YAML versionado; `CARIOCA_TOP_N` sai do `.env.example` | FR-016, FR-012 |
| Execuções concorrentes | O job CARIOCA usa lock consultivo do PostgreSQL, como o bloqueio simples, além de `max_instances=1`; os dois jobs de scoring podem rodar no mesmo cron sem disputar tabelas | FR-010 |
| Validade | `SCORE_MAX_AGE_HOURS` (48 h) vale para peers MISP e para o Pi-hole `carioca` | FR-016 |

### Estrutura acrescentada

```text
config/carioca-orgc-proxy-v3.yaml
src/misp_ioc_scoring/
├── collection/api.py                        # + leitura do snapshot de scoring
├── scoring/domain/                          # carioca_configuration, carioca_inputs, cade,
│                                            # carioca_components, feed_rank, population,
│                                            # priority, selection, aggregation, rescoring
├── scoring/application/                     # score_population, score_candidates, score_explanation
├── scoring/infrastructure/persistence/      # carioca.py, candidates.py
├── scoring/api.py                           # + scores CARIOCA vigentes (contracts/scoring-api.md)
├── sharing/domain/sharing.py                # política por peer
├── sharing/application/                     # share_eligible, sharing_status
├── sharing/adapters/synchronization.py      # push nativo MISP
├── sharing/infrastructure/                  # peer_configuration, persistence/misp.py
└── entrypoints/scoring_sharing.py           # + jobs CARIOCA e peers MISP
migrations/versions/0008_carioca_scoring.py, 0009_rescoring_candidates.py, 0010_misp_sharing.py, 0011_event_sharing_group.py
tools/metrics/scoring.py, candidates.py, sharing.py
docs/sigma-estimator-evaluation.md
tests/benchmark/, tests/e2e/
```

### Ajuste de DDD (correção do código existente)

A revisão de DDD de 2026-11-24 mostrou que as fronteiras entre módulos estão
corretas, mas que regras de negócio vivem em repositórios, schedulers e `api.py`, e
que `collection.api` entrega modelos SQLAlchemy a outros módulos. O ajuste entra
nesta mesma implementação, em etapas ligadas à frente que depende de cada parte.
**Regra comum**: é refatoração sem mudança de comportamento. Os testes atuais
(77 unitários, de contrato e de arquitetura, mais os de integração com PostgreSQL)
devem continuar passando sem mudar nenhum **valor esperado**; só pode mudar a forma de
acesso quando o tipo devolvido muda (por exemplo `row["block"]` → `row.block` em D5), e as decisões de bloqueio e as entradas do
Pi-hole devem sair idênticas antes e depois.

| Etapa | Achado | Correção | Antes de |
|---|---|---|---|
| D1 | `collection.api.blocking_snapshot` devolve `EndpointModel`, `ObservationModel`, `WarninglistModel` e `RejectionModel`; `scoring` lê atributos do ORM | `api.py` devolve só tipos de domínio imutáveis (`SourceSnapshot`, `ObservationSnapshot`, `WarninglistEntry`, `IndicatorRejection`), conforme [contracts/collection-api.md](./contracts/collection-api.md) | US2 |
| D2 | Confiança da origem escrita duas vezes: SQL em `unavailable_blocking_sources` e Python em `scoring/application/simple_blocking.py` | Regra única `SourceSnapshot.trusted(now, max_age)` no domínio de `collection`; a API filtra com ela | US2 |
| D3 | `blocking_warninglist_membership` (regra de domínio) está em `api.py`; `warninglist_membership` varre todas as entradas a cada IOC | `WarninglistIndex` em `collection/domain/warninglists.py`, construído uma vez por snapshot, com os modos `strict` (002: entrada não suportada torna indeterminado) e `fr027` (peers MISP: não suportada é ignorada e registrada) | US2 |
| D4 | Decaimento fixo em `scoring/domain/simple_blocking.py` (365; 0,7); hostname validado duas vezes (`normalization._domain` e `pihole_hostname`); conjuntos de tipos espalhados | `DecayGroup(D, T)` com `freshness(t)` em `scoring/domain/decay.py`, usado pelo bloqueio simples e pelo CARIOCA; função única `dns_hostname()` em `collection/domain/normalization.py`, exposta por `collection.api`; constantes de tipos nomeadas em `collection/domain/indicators.py` | US2 |
| D5 | Motivos, modelos de score e evidências como strings e `dict`; a Decisão de bloqueio só existe como `dict` | `StrEnum` `BlockingReason` e `ScoreModel`; dataclass `BlockingDecision` (motivo, `block`, `as_of`, `expires_at`, evidência tipada). Os valores gravados no banco não mudam (o `StrEnum` grava a mesma string) | US2 |
| D6 | `scoring/infrastructure/persistence/simple_blocking.py::run` é o caso de uso inteiro; lê o relógio duas vezes | Caso de uso `scoring/application/simple_blocking.py::run_blocking(as_of, snapshot, max_age, store)`; a infraestrutura implementa a porta `BlockingStore` (lock, SQL, transação); o job em `entrypoints/scoring_sharing.py` obtém o lock, lê o `as_of` uma vez e chama o caso de uso | US2 (molde do job CARIOCA) |
| D7 | Consolidação do IOC (ignorar atualização antiga, rejeitar ou criar IOC, identidade, `input_revision`, resolver rejeição, marcar remoção) está em `ObservationsRepository.apply` | Função pura `reconcile_snapshot(existentes, recebidas, collected_at, removal_ratio) -> Changeset` em `collection/domain/reconciliation.py`, usando a entidade `IOC` (hoje sem uso); o repositório só carrega e grava o `Changeset` | US3 |
| D8 | O repositório importa `application.reconcile.guard_removals` e `application.status.report_status` | A trava de remoção vai para o domínio (parte de D7); o status passa a ser emitido pelo caso de uso `collect`; novo contrato import-linter `infrastructure ↛ application` nos três módulos | US3 |
| D9 | `sharing/infrastructure/scheduling/scheduler.py::sync` monta a elegibilidade e a revalidação; `owned()` conhece o JSON do Pi-hole (`groups == [0]`) | Caso de uso `sharing/application/sync_pihole.py::plan_and_reconcile` com portas `DecisionsPort`, `SourcesPort` e `PiHolePort`, chamado por `entrypoints/scoring_sharing.py`; o scheduler da infraestrutura deixa de existir como orquestrador; o adaptador traduz o JSON remoto para `RemoteEntry` e a propriedade vira `ManagedEntry.is_owned_by(remote)` no domínio | US4 (molde dos peers MISP) |
| D10 | Linguagem: glossário sem nome no código; tabelas em dois idiomas | Coluna "nome no código" em `docs/domain-glossary.md`; tabelas novas em português, como as do plano. As tabelas `pihole_*` existentes **não são renomeadas** (evita migration e quebra da exportação sem ganho de domínio) | Polimento |

**Verificação automática acrescentada**:

- import-linter: `*.infrastructure ↛ *.application` em cada módulo;
  `*.domain ↛ sqlalchemy, pymisp, pydantic` (o domínio já cumpre; o contrato impede regressão); e `api.py` sem importar
  de `infrastructure` para tipos de retorno, por meio de teste de arquitetura que
  inspeciona as anotações públicas de `collection.api` e `scoring.api`.
- `tests/architecture/test_public_api_types.py`: falha se uma função pública de
  `api.py` devolver instância de `Base` do SQLAlchemy (verificação em tempo de
  execução sobre fixtures).

### Ordem de entrega

1. **Pré-requisitos curtos**: `pythonpath` do pytest, campos de `input_revision`,
   contagem de rejeições no status (T037) e `tasks.md` regenerado.
2. **DDD de base (D1–D6)**: tipos da API de coleta, confiança da origem, índice de
   warninglist, `DecayGroup`, enums e caso de uso do bloqueio simples. Sem mudança
   de comportamento; os testes da 002 são a rede de segurança.
3. **Avaliação de σ (T048)**, em paralelo com os itens 2 e 4: bloqueia só a aprovação
   da configuração, não o código.
4. **CARIOCA (US2)**: domínio puro com os casos do Notion como testes de referência,
   depois persistência, job, explicação, métricas e benchmark. Usa D1–D6 em vez de
   criar caminhos paralelos.
5. **Pi-hole `carioca`**: trocar `PIHOLE_CARIOCA_NOT_IMPLEMENTED` pela leitura de
   `scoring.api`.
6. **DDD da coleta (D7–D8)** e **Candidatos (US3)**: o `Changeset` passa a ser a
   origem dos incrementos de `input_revision`.
7. **DDD do compartilhamento (D9)** e **Peers MISP (US4)**: os peers MISP seguem o
   molde do caso de uso do Pi-hole.
8. **Polimento**: D10, e2e, migrations, equivalência entre fontes, vocabulário,
   revisão de segurança (x9) e quickstart final.

### Riscos

- **σ indefinido**: sem aprovação, `SCORING_CARIOCA_ENABLED=true` falha na
  inicialização, de propósito. Os testes de referência que dependem de σ (SC-015)
  esperam a avaliação.
- **Dados de referência dependem da data**: os valores do Notion foram tirados em
  2026-11-10 ~18:11 UTC. Os testes devem fixar `as_of` e montar as fixtures com os
  insumos publicados na página (n_i, σ_i, TL, SA, idade), não com o MISP vivo.
- **Desvio da referência pela agregação**: o Notion ranqueia atributos e o projeto
  ranqueia IOCs lógicos, então o corte do top-N não é diretamente comparável. Os casos
  de uma só observação continuam reproduzíveis.
- **Refatoração regredir a 002**: D1–D9 mexem em código em produção (coleta e
  Pi-hole). Mitigação: cada etapa é um commit separado; rodar a suíte completa com
  PostgreSQL (`TEST_DATABASE_URL`) antes de cada um; comparar decisões de bloqueio e
  o conjunto desejado do Pi-hole sobre a mesma fixture antes e depois (teste de
  caracterização escrito antes de D1).
- **Regra de distribuição permissiva**: com "basta uma observação permitir" (decisão do dono), um valor restrito por uma organização pode sair porque outra o publicou aberto. A regra nunca amplia a distribuição da observação usada; endurecer depois muda só a elegibilidade em `sharing/domain/sharing.py`.
- **Push MISP**: o sync nativo empurra eventos, não IOCs isolados. O desenho do
  adaptador (evento de saída por peer com os atributos elegíveis) está em
  [contracts/misp-sharing.md](./contracts/misp-sharing.md) e precisa de teste contra um
  MISP isolado antes de produção.

### Constitution Check (revisão)

| Princípio | Avaliação | Evidência |
|---|---|---|
| I Explicável | PASS | Explicação guarda a observação vencedora, componentes brutos e normalizados, σ, MinMax degenerado e a limitação do proxy de fonte |
| II Preservar dados | PASS | URL e tipos fora dos grupos são excluídos com motivo, sem converter tipo; valores originais ficam na coleta |
| III Determinismo | PASS | `as_of` único, desempate fixo na agregação, configuração com hash, snapshot de leitura único |
| IV Dados não confiáveis | PASS | Sem regex de warninglist; sem valores brutos em logs; segredos de peers por referência |
| V Pequeno e interoperável | PASS | Sem dependência nova; reuso de lock, flags e matcher da 002 |
| VI DDD | PASS | Termos novos (Observação vencedora) entram em `docs/domain-glossary.md`. O ajuste D1–D10 tira regras de repositórios, schedulers e `api.py` e as leva para o domínio e para casos de uso, sem criar padrão sem necessidade: só entram tipos que já existem como conceito no glossário ou que eliminam duplicação real |
| Monolito modular | PASS | `scoring` lê `collection.api`; `sharing` lê `scoring.api` e `collection.api`; novas tabelas nos schemas dos donos |

| Segurança da distribuição (pós-clarificação) | PASS | A regra de FR-016 nunca amplia a distribuição da observação usada; o achado C1 da análise fica resolvido no desenho, com teste de contrato pendente contra MISP isolado |

**Gate pós-revisão**: PASS, com a aprovação da configuração CARIOCA pendente da
avaliação de σ (risco já registrado, não é violação).

## Complexity Tracking

Nenhuma violação constitucional identificada; nenhuma exceção ou projeto adicional
necessário.

## Phase 0: Research

Concluída em [research.md](./research.md). As escolhas de banco, cliente MISP,
validação, agendamento, testes e tratamento dos parâmetros ausentes estão registradas
com fontes e alternativas.

## Phase 1: Design

- Modelo conceitual, relações, validações e estados: [data-model.md](./data-model.md).
- Contrato de coleta: [contracts/misp-collection.md](./contracts/misp-collection.md).
- Contrato de compartilhamento: [contracts/misp-sharing.md](./contracts/misp-sharing.md).
- Superfície de leitura da coleta (ajuste de DDD): [contracts/collection-api.md](./contracts/collection-api.md).
- Superfície de leitura dos scores (revisão 2026-11-24): [contracts/scoring-api.md](./contracts/scoring-api.md).
- Exportação de observabilidade: [contracts/observability-export.md](./contracts/observability-export.md).
- Cenários de validação: [quickstart.md](./quickstart.md).

**Gate pós-design**: PASS. O modelo mantém uma linguagem do domínio independente do
protocolo MISP, conserva proveniência, explicita estado e falhas, e mantém integrações
externas atrás de adaptadores. Reavaliar a configuração versionada quando casos de
referência e mapeamentos concretos do artigo forem aprovados.
