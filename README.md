# MISP IOC Scoring

Python 3.12 modular workers with PostgreSQL. The collection MVP is implemented:
MISP pagination, IOC normalization, provenance, indicator rejections, warninglists,
transactional checkpoints and a read-only Excel export.

**Scoring and outbound sharing are not implemented yet.** Their Compose profile
`scoring` is disabled by default. CARIOCA parameters still require evaluation and
explicit approval; collection does not publish or modify MISP data.

## Development

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
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
