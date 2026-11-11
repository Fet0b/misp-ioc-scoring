# Implementation Plan: Plataforma de Scoring e Compartilhamento de IOCs

**Branch**: `001-misp-ioc-scoring` | **Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-misp-ioc-scoring/spec.md`

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
- Cenários de validação: [quickstart.md](./quickstart.md).

**Gate pós-design**: PASS. O modelo mantém uma linguagem do domínio independente do
protocolo MISP, conserva proveniência, explicita estado e falhas, e mantém integrações
externas atrás de adaptadores. Reavaliar a configuração versionada quando casos de
referência e mapeamentos concretos do artigo forem aprovados.
