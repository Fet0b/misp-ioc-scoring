# Quickstart de validação

Este roteiro valida o comportamento da feature depois que os serviços de aplicação
forem implementados. Os comandos assumem Docker Compose e ambiente Python do projeto;
arquivos de execução ainda serão entregues pelas tarefas de implementação.

## Pré-requisitos

- Docker Engine e Docker Compose disponíveis.
- Instância MISP de teste com conta de automação e pelo menos um evento/atributo de
  teste, além de um peer de sync isolado.
- Configuração CARIOCA versionada, contendo explicitamente todos os parâmetros ainda
  não definidos na publicação (estimador de σ, normalização do CADE, FeedRank
  `orgc-proxy`, `top_n`, regra de empate) e casos de resultado de referência aprovados.
- Peers e score mínimo por peer definidos nas variáveis de ambiente do container de
  scoring/sharing (mudança exige reiniciar o container).
- Endpoint de teste com `to_ids_only` habilitado e ao menos uma warninglist habilitada.
- Credenciais fornecidas por mecanismo seguro de configuração, não commitadas.

## Verificações

1. **Subir o ambiente**: iniciar PostgreSQL e os dois workers pelo Compose.
   Esperado: os três serviços ficam saudáveis; workers reportam versão/configuração
   sem imprimir segredos.
2. **Coletar**: executar uma coleta manual de cada endpoint de teste.
   Esperado: resposta paginada validada, checkpoint avançado apenas após persistência,
   IOCs deduplicados por tipo/valor normalizado e observações mantidas por UUID.
3. **Repetir coleta**: repetir a mesma janela e depois alterar um campo relevante e
   outro não relevante.
   Esperado: nenhuma duplicação; mudança relevante marca o IOC lógico uma vez;
   mudança irrelevante não marca.
4. **Validar scoring**: rodar testes de unidade com casos CARIOCA de referência e uma
   execução diária de candidatos.
   Esperado: scores/componentes reproduzíveis para o mesmo `as_of`; configuração
   incompleta (inclusive sem estimador de σ aprovado) impede cálculo; toda a população
   válida é recalculada; IOCs expirados ou de tipo sem decaimento ficam com exclusão
   registrada; falha ou revisão concorrente deixa o candidato pendente; gravação do
   score não o remarca.
5. **Validar compartilhamento**: testar score abaixo/acima do limite e distribuição
   autorizada/restrita, incluindo timeout após envio.
   Esperado: somente IOC no top-N, com score mínimo, fora de warninglist e autorizado é
   sincronizado; timeout não é
   registrado como entrega confirmada; retentativa reconcilia antes de repetir.
6. **Validar filtro de coleta**: coletar com `to_ids_only` e depois desabilitá-lo/habilitá-lo
   num banco de teste.
   Esperado: atributos fora do filtro recebem `removed_at`; reconciliação acima do limite
   de remoção é recusada e não avança o checkpoint.
7. **Validar rejeições**: coletar fixtures com indicadores inválidos e de tipo não
   suportado, e repetir a coleta.
   Esperado: nenhum IOC é criado para eles; cada rejeição aparece uma vez por origem e
   motivo, com valor bruto, tipo MISP e momento; contagem e listagem por motivo e origem
   funcionam; logs não repetem o valor.
8. **Validar desempenho**: rodar o scoring diário sobre dados representativos (ordem de
   270 mil IOCs válidos).
   Esperado: recálculo da população completa em até 1 hora (SC-011); população vazia
   conclui sem scores e com aviso; valores iguais na normalização dão 50.
9. **Validar configuração de peers**: iniciar o container com mínimo fora de 0–100 e
   depois com valores válidos, alterando e reiniciando.
   Esperado: configuração inválida impede o compartilhamento com erro explícito;
   alteração só vale após o reinício e a política efetiva fica registrada.
10. **Validar validade do score**: com a última execução de scoring bem-sucedida com mais
    de 48 horas (simulada), executar o compartilhamento.
    Esperado: nenhum envio, aviso ao operador; após uma nova execução bem-sucedida os
    envios retomam.
11. **Validar observabilidade**: rodar o script de exportação sobre o banco de teste.
    Esperado: uma aba por tabela de todos os schemas, mais a aba de métricas (contagens,
    rejeições por motivo e origem, última execução de coleta e scoring, população válida e
    excluída, candidatos pendentes, tentativas por estado, avisos e suspensão do
    compartilhamento); valores como `=1+1` ou `@x` em `raw_value` aparecem como texto;
    nenhum segredo na planilha; abas acima do limite indicam o truncamento e a aba de
    métricas traz o total.
12. **Validar parâmetros de ambiente**: iniciar cada container com uma frequência ou
    validade inválida e depois válida.
    Esperado: valor inválido impede o início com erro explícito; mudança só vale após
    reiniciar.
13. **Validar recuperação**: interromper a coleta e reiniciar um worker durante um
   lote.
   Esperado: checkpoint e pendências permitem retomar sem lacunas ou duplicação.

## Comandos previstos

```bash
docker compose up --build
python -m pytest
```

Para cenários de integração, usar o perfil de teste e instância MISP isolada a serem
definidos na implementação. Não executar testes de publicação contra peers de produção.

## Referências

- [Modelo de dados](./data-model.md)
- [Contrato de coleta](./contracts/misp-collection.md)
- [Contrato de compartilhamento](./contracts/misp-sharing.md)


## MVP de coleta implementado (2026-11-11)

A coleta e a exportação estão implementadas; scoring e compartilhamento seguem
pendentes. O perfil `scoring` fica desativado por padrão. Preparação de segredos,
formatos JSON de endpoints/cadências e comandos de consulta estão em
[README.md](../../README.md).

```bash
docker compose up -d --build database migrate collector
docker compose ps -a
docker compose logs --tail=30 collector
docker compose --profile tools run --rm tools
.venv/bin/python -m pytest
```

A primeira coleta começa na inicialização. Banco e coletor têm reinício automático;
o volume `postgres-data` preserva os dados. Para a integração automatizada, definir
`TEST_DATABASE_URL` para uma instância PostgreSQL separada e descartável, com nome de
banco terminado em `_test`; os testes criam e removem schemas e papéis nesse ambiente.
Não usar o cluster de produção para os testes.


## Retomada de US2–US4 (revisão 2026-11-24)

Estado: coleta, bloqueio simples, Pi-hole, CARIOCA, candidatos e peers MISP
implementados. A ativação do CARIOCA espera a aprovação de σ, e os peers MISP esperam a
validação contra um MISP isolado. Decisões em [plan.md](./plan.md#revisão-2026-11-24-retomada-de-us2-us4).

### Comandos finais

```bash
# Suíte completa (integração exige PostgreSQL descartável com banco terminado em _test)
TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55432/misp_test uv run --extra dev pytest -q
uv run --extra dev lint-imports
# Benchmark SC-011 (opcional, lento)
RUN_BENCHMARK=true TEST_DATABASE_URL=... uv run --extra dev pytest -q -s tests/benchmark
# End-to-end com MISP local, MISP peer e Pi-hole isolados (exige Docker)
E2E_COMPOSE=true uv run --extra dev pytest -q tests/e2e
# Serviços
docker compose config
docker compose up -d --build database migrate collector
docker compose --profile scoring up -d --build scoring-sharing
```

- **Coleta**: como na seção "MVP de coleta".
- **Scoring CARIOCA**: `SCORING_CARIOCA_ENABLED=true`, `SCORING_DAILY_CRON` e
  `CARIOCA_CONFIG_PATH` (o Compose monta `./config` somente leitura).
- **Aprovação da configuração**: depois da avaliação de σ
  (`docs/sigma-estimator-evaluation.md`), preencher `approval` em
  `config/carioca-orgc-proxy-v3.yaml` e gravar
  `tests/unit/fixtures/carioca_reference_approved.json`. A partir daí,
  `tests/unit/test_carioca_reference_approved.py` deixa de ser pulado.
- **Pi-hole `carioca`**: `PIHOLE_SCORE_MODEL=carioca` e `PIHOLE_CARIOCA_MIN_SCORE`.
- **Peers MISP**: `SHARING_MISP_ENABLED=true`, `MISP_PEERS_SECRET_REF` (JSON com `local`
  e `peers`, ver README), `SHARING_INTERVAL_SECONDS`, `SHARING_RETRY_ATTEMPTS`,
  `SHARING_RETRY_BACKOFF_SECONDS` e `MISP_REQUEST_TIMEOUT_SECONDS`.
- **Peer de sync isolado**: `tests/e2e/config/compose.e2e.yaml`. O servidor de sync
  local → peer e as regras de push são configurados no MISP local.

### Verificação de 2026-11-24 (T092)

Ambiente sem Docker, com PostgreSQL 16.2 local descartável.

| Verificação | Resultado |
|---|---|
| `uv run --extra dev pytest -q` com `TEST_DATABASE_URL` | 265 passaram, 4 pulados: benchmark (opcional), e2e (sem Docker) e nível 2 da SC-015 (configuração ainda não aprovada) |
| `uv run --extra dev lint-imports` | 19 contratos respeitados |
| Benchmark com `RUN_BENCHMARK=true` | 269.787 IOCs: 10,3 s em memória e 42,6 s com gravação |
| `docker compose config` e `docker compose up --build` | **Não executados**: Docker indisponível no ambiente |
| e2e com MISP, peer de sync e Pi-hole isolados | **Não executado**: sem Docker e sem instâncias de teste |
| Tabela de fontes do Notion §4 | **Não conferida**: exige `BENCHMARK_DATABASE_URL` com cópia do MISP de estudos |

### Cenários de validação da US2–US4

1. **Casos de referência, nível 1 (fórmulas)**: com σ dado como entrada, os testes
   unitários reproduzem `hotels-stays55501.com` (CADE 6,5218; CADE' 19,544; E' 60,532;
   A' 66,984; P 75,838). Nível 2 (SC-015): com o σ aprovado, os mesmos casos batem com
   os valores de `docs/sigma-estimator-evaluation.md`. Também reproduzem a
   tabela de fontes do Notion (CIRCL S' 100; CthulhuSPRL.be 59,92; Krawczyk 47,05), com
   `as_of` fixo.
2. **Configuração não aprovada**: `SCORING_CARIOCA_ENABLED=true` com
   `approved: false` impede o início do serviço com erro explícito.
3. **Execução diária**: com configuração aprovada, a execução registra `as_of`, população
   válida, exclusões por motivo (incluindo `url` como tipo sem grupo e observações
   `to_ids=false`), rank e top-N por IOC lógico e a observação vencedora.
4. **Independência do filtro de coleta**: coletar com `MISP_TO_IDS_ONLY=true` e depois
   `false` sobre os mesmos dados dá os mesmos scores.
5. **Distribuição a peers (US4)**: IOC com uma observação `0` e outra `3` é enviado com
   distribuição `3`; com observações `1` e `3`, sai com `1`; só com `0` ou evento não
   publicado, fica inelegível com `distribution_not_allowed`.
6. **Pi-hole `carioca`**: com `PIHOLE_SCORE_MODEL=carioca` e corte definido, só domínios e
   hostnames com score vigente acima do corte são enviados; sem execução vigente nada é
   enviado.
7. **Benchmark**: `uv run --extra dev pytest -q tests/benchmark` conclui o recálculo de
   cerca de 270 mil IOCs em até 1 hora (SC-011).

Os cenários de candidatos (US3) e de peers MISP (US4) continuam os itens 3, 5, 9 e 10 da
lista de verificações acima.

### Validação do ajuste de DDD

Cada etapa D1–D10 do [plano](./plan.md#ajuste-de-ddd-correção-do-código-existente) é
validada antes do commit:

1. **Caracterização**: `uv run --extra dev pytest -q tests/integration/test_blocking_characterization.py`
   com `TEST_DATABASE_URL` definido. Esperado: as decisões de bloqueio e o conjunto
   desejado do Pi-hole são idênticos ao resultado gravado antes de D1.
2. **Suíte existente**: `uv run --extra dev pytest -q` (com `TEST_DATABASE_URL`).
   Esperado: todos os testes que passavam continuam passando, sem mudar asserções.
3. **Fronteiras**: `uv run --extra dev lint-imports`. Esperado: passam também os
   contratos novos (`infrastructure ↛ application` e domínio sem SQLAlchemy, PyMISP
   ou Pydantic).
4. **Tipos da API**: `uv run --extra dev pytest -q tests/architecture/test_public_api_types.py`.
   Esperado: nenhuma função pública de `collection.api` ou `scoring.api` devolve
   modelo ORM.
5. **Domínio sem banco**: os testes de `reconcile_snapshot`, `WarninglistIndex`,
   `DecayGroup` e `ManagedEntry.is_owned_by` rodam em `tests/unit` sem PostgreSQL.
