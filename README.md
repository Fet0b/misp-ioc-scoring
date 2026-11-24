# MISP IOC Scoring

Python 3.12 modular workers with PostgreSQL: MISP collection, simple blocking with
Pi-hole, CARIOCA scoring, re-scoring candidates and sharing with MISP peers, plus a
read-only Excel export.

The Compose profile `scoring` is disabled by default. **CARIOCA needs an approved
configuration** (`config/carioca-orgc-proxy-v3.yaml`, `approved: false` until the σ
evaluation in `docs/sigma-estimator-evaluation.md` is approved). Sharing with MISP peers
must be validated against an isolated MISP before production. Collection never
publishes or modifies MISP data.

## Development

```bash
uv run --extra dev pytest -q
uv run --extra dev lint-imports
```

PostgreSQL integration tests use `TEST_DATABASE_URL`. Supply a fresh disposable
database whose name ends in `_test`, and an administrator role able to create roles.
Tests create and remove module schemas and runtime roles. Use a separate PostgreSQL
instance: never point this setting at the production cluster.

```bash
TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55439/misp_ioc_scoring_test \
  .venv/bin/python -m pytest
```

## Run collection

Copy `.env.example` to `.env`, configure the database URLs and secret-file paths,
and provide the operational intervals explicitly. The Compose services receive only
their own environment settings. Runtime UID is `10001`; application secret files must
be readable by this UID, and the mounted output directory must be writable by it.
Keep MISP credentials in a dedicated directory containing only MISP credential files.
Database admin secrets must never be mounted in the collector.

The endpoints file is a JSON array, for example:

```json
[{"id":"misp-local","base_url":"https://misp.example/","credential_secret_ref":"file:/run/misp-credentials/key"}]
```

The cadence file maps endpoint IDs to positive intervals in seconds:

```json
{"misp-local":300}
```

HTTPS is the default. A deployment explicitly using HTTP must set `"allow_http":true`
on that endpoint. Credentials are read from `file:/absolute/path` or `env:NAME`
references and do not belong in source files. Configuration is a startup snapshot;
restart the collector after changing it.

```bash
docker compose up -d --build database migrate collector
docker compose ps -a
docker compose logs --tail=30 collector
docker compose exec database psql -U postgres -d misp_ioc_scoring
```

The collector runs immediately, then follows each endpoint's cadence. PostgreSQL and
the collector restart automatically unless explicitly stopped. A named volume retains
the database across container replacement. A complete identity snapshot is collected
alongside incremental windows so absence in an incremental response never becomes a
false removal. This favors correctness over query volume in the MVP.

```sql
SELECT id, status, last_successful_checkpoint, last_success_at, error
FROM collection.endpoint_coleta;
SELECT count(*) FROM collection.ioc;
SELECT count(*) FROM collection.observacao_origem;
SELECT reason, count(*) FROM collection.rejeicao_indicador GROUP BY reason;
```

Export an Excel workbook using the read-only `observer` database role:

```bash
docker compose --profile tools run --rm tools
```

Output is restricted to UID `10001` (directory `0700`, files `0600`). Columns commented
`secret` are excluded. All cells are written as text. Sheet truncation is explicit,
and table totals remain visible in the metrics sheet.

## Bloqueio simples e Pi-hole

No perfil Compose `scoring`, habilite `SCORING_SIMPLE_ENABLED=true` e configure
`SCORING_DAILY_CRON` em UTC. O worker grava uma decisão por origem e UUID do
atributo. A elegibilidade exige `to_ids=1`, tipo `url` ou `domain`, evento com
`analysis=2`, ausência em warninglist e menos de 365 dias desde o timestamp
de modificação do atributo. Para coletar também atributos com `to_ids=false`,
desative o filtro `MISP_TO_IDS_ONLY` e confira a configuração de cada endpoint.

Consulte `scoring.decisao_bloqueio_efetiva` com um papel somente leitura.
A decisão é revalidada na consulta. Ambas as flags de compartilhamento começam
desativadas. Ative o Pi-hole v6 com `SHARING_PIHOLE_ENABLED=true`,
`PIHOLE_SCORE_MODEL=default`, `PIHOLE_URL`, `PIHOLE_INTERVAL_SECONDS` e
uma referência de senha. Uma URL vira uma regra DNS exata para seu hostname.
Isso afeta todos os caminhos daquele hostname. O ID remoto e o comentário
identificam entradas do projeto. Quando a propriedade é incerta, a entrada
permanece.

## Score CARIOCA

O job diário recalcula toda a População válida com um `as_of` único e usa o mesmo
`SCORING_DAILY_CRON`. Ative com `SCORING_CARIOCA_ENABLED=true`. A inicialização exige
`CARIOCA_CONFIG_PATH` legível, configuração válida e `approved: true`. Sem isso, falha
com `CARIOCA_CONFIGURATION_NOT_APPROVED` ou com o código do parâmetro inválido.

- **Configuração**: `config/carioca-orgc-proxy-v3.yaml` é YAML no subconjunto JSON, com
  comentários só no cabeçalho. Ela tem pesos, estimador de σ e regra para σ = 0, grupos
  de tipo (sem `url`), FeedRank, SPOTIS e `top_n`, que só existe ali. O hash do conteúdo
  canônico fica gravado em cada execução.
- **Cálculo**: Source, Event e Attribute são calculados por Observação de origem com
  `to_ids=true`, qualquer que seja `MISP_TO_IDS_ONLY`. O IOC recebe o score da
  Observação vencedora (a de maior prioridade).
- **Consulta**: `scoring.api.current_carioca_run`, `carioca_scores`, `exclusions` e
  `explain`, ou as tabelas `scoring.execucao_scoring`, `resultado_score`,
  `avaliacao_observacao`, `exclusao_score` e `estatisticas_populacao`.
- **Candidatos a re-scoring**: `scoring.candidato_rescoring` mostra os IOCs cuja revisão
  de entrada mudou desde o último score. É só rastreabilidade: o recálculo é sempre
  completo.

Para o Pi-hole usar o CARIOCA, defina `PIHOLE_SCORE_MODEL=carioca` e
`PIHOLE_CARIOCA_MIN_SCORE` (0–100), com `SCORING_CARIOCA_ENABLED=true`. Só domínios e
hostnames da execução vigente com score no corte são enviados, sem top-N. Sem execução
vigente, ou com ela mais antiga que `SCORE_MAX_AGE_HOURS`, nada é enviado e as entradas
existentes ficam.

## Peers MISP

Ative com `SHARING_MISP_ENABLED=true`, que exige `SCORING_CARIOCA_ENABLED=true`, e
configure `SHARING_INTERVAL_SECONDS`, `SHARING_RETRY_ATTEMPTS`,
`SHARING_RETRY_BACKOFF_SECONDS`, `MISP_REQUEST_TIMEOUT_SECONDS` e
`MISP_PEERS_SECRET_REF`. Essa referência aponta para um JSON com a instância local de
saída e os peers:

```json
{"local": {"base_url": "https://misp-local", "credential_secret_ref": "file:/run/misp-peers/local"},
 "peers": [{"peer_id": "peer-a", "base_url": "https://peer-a", "credential_secret_ref": "file:/run/misp-peers/peer-a",
            "minimum_priority_score": 70, "distribution": "3"}]}
```

Um IOC é elegível quando:
- tem score válido da execução vigente, no top-N e no mínimo do peer;
- não está em warninglist (igualdade, CIDR e hostname; regex e substring são ignorados);
- tem ao menos uma observação ativa, de evento publicado, cuja distribuição alcança o peer.

O atributo de saída leva a distribuição mais restritiva entre as observações que alcançam
o peer, nunca uma mais ampla. Cada peer tem um evento de saída na instância local, com
atributos de UUID estável, e a entrega é feita pelo sync nativo. Publicar só registra
`requested`. `confirmed` exige ler o atributo no peer, e um timeout vira `ambiguous`
até essa leitura. Score mais antigo que `SCORE_MAX_AGE_HOURS` suspende os envios e
registra o aviso em `sharing.politica_compartilhamento`. A política efetiva é gravada,
sem segredos, a cada inicialização.

## Benchmark e end-to-end

```bash
RUN_BENCHMARK=true TEST_DATABASE_URL=... uv run --extra dev pytest -q -s tests/benchmark
E2E_COMPOSE=true uv run --extra dev pytest -q tests/e2e
```

O benchmark usa cerca de 270 mil IOCs sintéticos (SC-011: até 1 hora). O e2e sobe o
Compose do projeto com um MISP local, um MISP peer e um Pi-hole isolados
(`tests/e2e/config/`). O servidor de sync entre os dois MISP é configurado no próprio
MISP.
