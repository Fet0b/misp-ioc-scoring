# Implementation Plan: Plataforma de Scoring e Compartilhamento de IOCs

**Branch**: `001-misp-ioc-scoring` | **Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-misp-ioc-scoring/spec.md`

## Summary

Coletar e normalizar IOCs e contexto de endpoints MISP em cadências próprias,
persistir observações com proveniência, calcular e explicar prioridades CARIOCA
diariamente e compartilhar somente IOCs que atinjam um score mínimo configurado por
peer, respeitando a distribuição nativa do MISP. A solução será composta por três
containers: PostgreSQL, worker de coleta/normalização e worker de scoring/compartilhamento.
As regras de domínio ficarão isoladas dos adaptadores MISP e de persistência.

## Technical Context

**Language/Version**: Python 3.12 como baseline de implementação

**Primary Dependencies**: PyMISP para integração MISP; SQLAlchemy 2.x para
persistência; Alembic para migrações; Pydantic para validação nas fronteiras externas;
APScheduler 3.x com uma instância por worker; pytest para testes. Não adicionar pandas
até que uma necessidade concreta do algoritmo justifique o custo.

**Storage**: PostgreSQL em container dedicado; volume persistente; schema relacional
com migrações versionadas.

**Testing**: pytest; unitários para regras de domínio; integração com PostgreSQL para
transações, constraints, migrações e idempotência; testes de contrato com respostas
MISP simuladas; cenários end-to-end em ambiente de teste com MISP disponível.

**Target Platform**: Linux em containers Docker; execução local ou em host compatível
com Docker Compose.

**Project Type**: Aplicação de workers internos com três containers, sem API de usuário
adicional definida nesta feature.

**Performance Goals**: A especificação não determina volume ou metas de latência. Os
jobs devem processar lotes paginados e respeitar a cadência por endpoint; estabelecer
benchmarks operacionais com dados reais antes de fixar SLOs.

**Constraints**: Coleta e jobs de scoring são síncronos dentro de cada execução.
Execuções do mesmo job não podem se sobrepor. Uma falha parcial não avança checkpoint
nem limpa candidatos pendentes. Parâmetros CARIOCA não publicados exigem configuração
explícita versionada; scoring não ocorre com configuração incompleta. Compartilhamento
exige score mínimo por peer e autorização/distribuição nativa do MISP.

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
| Simplicidade e interoperabilidade | PASS | Três containers, sem broker ou pandas sem necessidade demonstrada. |
| DDD e linguagem ubíqua | PASS | IOC, Observação de origem, Resultado de score, Candidato a re-scoring e Política de compartilhamento são os termos canônicos. Domínio separado dos adaptadores. |
| Arquitetura requerida | PASS | Python/Docker, database, collector/normalizer e scoring/sharing. |
| Governança de parâmetros CARIOCA | PASS | Configuração explícita/versionada para lacunas da publicação; sem score quando incompleta. |

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
│   └── misp-sharing.md
└── tasks.md
```

### Source Code (repository root)

```text
src/misp_ioc_scoring/
├── domain/
│   ├── indicators.py
│   ├── observations.py
│   ├── scoring.py
│   └── sharing.py
├── application/
│   ├── collect.py
│   ├── score_candidates.py
│   └── share_eligible.py
├── adapters/
│   └── misp/
│       ├── client.py
│       ├── collection.py
│       └── synchronization.py
├── infrastructure/
│   ├── persistence/
│   ├── scheduling/
│   └── configuration.py
└── workers/
    ├── collector.py
    └── scoring.py

migrations/
tests/
├── unit/
├── integration/
├── contract/
└── e2e/
```

**Structure Decision**: O repositório não contém aplicação ou testes preexistentes.
Esta é uma proposta inicial para um único pacote Python organizado por domínio,
casos de uso e adaptadores. Os workers são entrypoints separados do mesmo pacote;
PostgreSQL é o terceiro container. Não se cria serviço HTTP público nem broker nesta
feature sem requisito adicional.

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
