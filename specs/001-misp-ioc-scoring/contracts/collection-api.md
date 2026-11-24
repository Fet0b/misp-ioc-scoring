# Contrato: superfície de leitura da coleta

Revisão 2026-11-24 (ajuste de DDD, etapas D1–D4). `misp_ioc_scoring/collection/api.py`
é a única porta de leitura de `collection` para `scoring` e `sharing`.

## Regras gerais

- Toda função devolve tipos de domínio imutáveis de `collection.domain`
  (ver [data-model.md](../data-model.md#tipos-de-domínio-do-ajuste-de-ddd)); nunca
  modelos SQLAlchemy, `Row` ou `RowMapping`.
- Somente leitura. Quem chama controla a transação e o lock; funções que exigem
  snapshot estável recebem a `session` e documentam o nível de isolamento esperado.
- Valores de indicador são dados não confiáveis; a API não os registra em log.

## Funções

| Função | Devolve | Substitui |
|---|---|---|
| `collection_snapshot(session)` | `CollectionSnapshot` (fontes, observações ativas e removidas, warninglists, rejeições) | `blocking_snapshot`, `active_iocs`, `event_category_counts`, `first_publications` (as duas últimas passam a ser calculadas pelo `scoring` sobre o snapshot) |
| `untrusted_sources(session, now, max_age)` | `set[str]` calculado por `SourceSnapshot.trusted` | `unavailable_blocking_sources` |
| `source_generations(session)` | `dict[str, int]` | `blocking_generations` |
| `warninglist_index(entries, mode)` | `WarninglistIndex` | `blocking_warninglist_membership`, `warninglist_membership` |
| `dns_hostname(kind, value)` | `str | None` | `sharing/domain/pihole_hostname.hostname` e `normalization._domain` |
| `rejections(...)`, `rejection_counts()`, `unsupported_warninglist_entries()` | sem mudança | — |

## Transição

As funções antigas ficam como aliases finos que chamam as novas até o fim da etapa
D2 e são removidas na mesma entrega; nenhum chamador externo ao projeto depende delas.

## Verificação

- `tests/architecture/test_public_api_types.py` chama cada função pública sobre a
  fixture de integração e falha se algum valor devolvido for instância de `Base`.
- O teste de caracterização da 002 continua igual depois da troca.
