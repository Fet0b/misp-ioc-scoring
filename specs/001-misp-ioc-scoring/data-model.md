# Modelo de dados: Plataforma de Scoring e Compartilhamento de IOCs

Este é o modelo conceitual do domínio. Colunas de credencial ou referência a segredo recebem o comentário PostgreSQL `secret`
(convenção que a exportação respeita). A exportação de observabilidade (FR-028) lê todas
as tabelas abaixo por reflexão e
não faz parte de nenhum módulo. Cada entidade pertence a um módulo (`collection`,
`scoring` ou `sharing`), único escritor de suas tabelas; ver "Arquitetura Modular" em
`plan.md`. Identificadores locais são internos; UUIDs MISP
identificam objetos na origem e não substituem a identidade de um IOC lógico.

## Entidades

### IOC

Indicador lógico consolidado pelas observações equivalentes.

- `id`: identificador interno estável.
- `type`: tipo canônico do atributo MISP.
- `normalized_value`: valor normalizado, sem descartar a forma original.
- `input_revision`: contador incrementado apenas quando muda um campo de entrada do algoritmo.
- `created_at`, `updated_at`: timestamps do registro local.
- **Módulo dono**: `collection`.
- **Identidade**: unicidade de `(type, normalized_value)`.
- **Validação**: tipo e forma normalizada devem pertencer ao conjunto suportado;
  conteúdo inválido não pode ser transformado silenciosamente em IOC válido.
- Um IOC pode reunir múltiplas Observações de origem.

### Observação de origem

Ocorrência observada em uma instância/evento/atributo MISP.

- `id`: identificador interno.
- `ioc_id`: referência ao IOC lógico.
- `source_instance_id`: identidade configurada da instância MISP consultada.
- `event_uuid`, `attribute_uuid`: UUIDs de origem portáveis; `attribute_uuid` é
  único dentro de uma instância de origem.
- `raw_value`, `misp_type`, `category`: dados originais necessários para auditoria,
  mapeamento e reconstrução.
- `event_threat_level`, `event_analysis`: valores de contexto MISP usados pelo
  CARIOCA, preservando também o valor recebido quando não reconhecido.
- `orgc_uuid`: organização criadora do evento; proxy da fonte no FeedRank (FR-025).
- `to_ids`, distribuição, tags e campos relevantes ao algoritmo/política.
- `removed_at`: marca atributo que deixou de existir ou de atender ao filtro da coleta
  (FR-026); a observação é preservada, mas inativa para o scoring.
- `source_created_at`, `source_modified_at`, `collected_at`: tempos de origem e coleta.
- **Regra de atualização**: upsert por origem + UUID do atributo; revisão de campos
  relevantes incrementa a revisão de entrada do IOC e pode criar candidato.
- UUIDs e timestamps de origem são preservados; IDs numéricos locais não são usados
  como identidade compartilhada.

### Endpoint de coleta

Configuração e estado operacional de cada fonte MISP.

- `id`, `base_url`, versão/compatibilidade detectada e credencial referenciada de
  forma segura.
- `interval`, filtros/paginação e estado habilitado.
- `to_ids_only` (padrão verdadeiro) e limite de remoção em massa na reconciliação
  (FR-026); exceder o limite recusa a reconciliação e sinaliza erro.
- `last_successful_checkpoint`, janela sobreposta consultada, `last_run_at`,
  `last_success_at`, status/erro resumido.
- **Estado de execução**: agendada → executando → concluída ou falha. Checkpoint só
  avança depois que a janela completa e suas alterações são persistidas.
- Cada endpoint mantém cadência e checkpoint independentes.

### Configuração CARIOCA

Snapshot versionado de regras e parâmetros para reprodução de scores.

- `id`, `version`, `created_at`, aprovador/referência, hash do conteúdo.
- pesos `alpha` do score de evento e `beta` de categorias; soma dos pesos por conjunto
  deve ser 1 e valores não podem ser negativos.
- parâmetros de distribuição/PDF de categorias, mapeamentos necessários de tipo para
  grupo de frescor e parâmetros `D_a`/`T_a`.
- método/versão de FeedRank (`orgc-proxy`: amortecimento 0,85, iterações, pesos 50/50) e
  parâmetros necessários para sua reprodução.
- estimador de σ por categoria (método, versão, limite de percentil ou escala log) e
  regra para σ = 0 (FR-023); normalização MinMax do CADE entre eventos; em qualquer
  MinMax com máximo = mínimo o valor normalizado é 50 (FR-024, regra fixa, não configurável).
- parâmetros de normalização MinMax e combinação SPOTIS (pesos 1/3, ponto ideal 100).
- `top_n` (sem padrão implícito) e identificadores de modelo (`carioca-orgc-proxy-v3`,
  `cade-seminormal-v2`).
- parâmetros não especificados no artigo precisam de valor explícito, justificativa e
  aprovação antes de ativar a configuração.
- Configuração ausente ou inválida impede cálculo, em vez de usar default implícito.

### Candidato a re-scoring

Rastreabilidade de que os dados de entrada de um IOC lógico mudaram desde o último score
bem-sucedido. Como o scoring diário recalcula toda a população (FR-010), o candidato não
restringe quais IOCs recebem score, não otimiza o cálculo e não é consultado por ele;
apenas permanece pendente até um recálculo bem-sucedido sobre a revisão vigente.

- **Módulo dono**: `scoring`. É derivado: a coleta só incrementa `ioc.input_revision`.
- `ioc_id`: chave primária e relação um-para-um com IOC.
- `pending`: booleano que indica trabalho ainda não concluído.
- `input_revision`: revisão de entrada do IOC (lida via `collection.api`) que originou o candidato.
- `reason`, `marked_at`, `last_attempt_at`, `last_error`: rastreabilidade do ciclo.
- Uma alteração numa Observação de origem percorre sua relação até o IOC e marca o
  IOC lógico; múltiplas observações não criam candidatos duplicados.
- Apenas campos de entrada usados pelo algoritmo marcam candidato; gravações de score
  não o fazem.
- A execução lê uma revisão; conclui e limpa `pending` somente se o cálculo tiver
  sucesso e a revisão não tiver mudado durante a execução. Falha ou revisão concorrente
  mantém o candidato pendente.

### Estatísticas de população

Valores calculados por execução sobre a população válida; módulo dono: `scoring`.

- `scoring_run_id`, `as_of`, configuração CARIOCA.
- σ por categoria (16), mínimo e máximo de CADE, Event, Attribute e Source.
- Por organização: pares em que foi a primeira, contribuição, PageRank, valor da fonte.
- Garante que um score possa ser reproduzido a partir de seus insumos (FR-013).

### Exclusão de score

Motivo de um IOC ativo não ter score válido (FR-022); módulo dono: `scoring`.

- `scoring_run_id`, `ioc_id`, motivo (tipo sem grupo de decaimento, expirado,
  dado ausente, configuração incompleta).

### Rejeição de indicador

Registro de um indicador inválido ou não suportado recebido do MISP (FR-003); módulo
dono: `collection`. Não é um IOC e nunca alimenta o scoring.

- `id`, `source_instance_id`, `event_uuid`, `attribute_uuid`: origem da rejeição.
- `misp_type`, `raw_value`: tipo e valor como recebidos (dado não confiável; nunca
  interpretado nem copiado para logs ou mensagens de erro).
- `reason`: `invalid` ou `unsupported`; `detail` curto e não sensível; `rejected_at`.
- **Unicidade**: `(source_instance_id, attribute_uuid, reason)`; recoletar o mesmo
  atributo atualiza o registro em vez de duplicá-lo (FR-005, SC-004).
- Se um atributo antes rejeitado passa a ser válido ou suportado, o registro é removido
  (ou marcado resolvido) na mesma transação em que o IOC é criado.
- Consultável por contagem e listagem por motivo e por origem, via `collection.api`.

### Entrada de warninglist

Valores presentes em warninglists habilitadas do MISP; módulo dono: `collection`.

- lista, tipo da lista, valor normalizado, instância de origem, `collected_at`.
- Pertinência avaliada por igualdade exata, CIDR (IPs) e hostname/subdomínio
  (domínios); entradas de tipo regex ou substring são guardadas com `supported = false`
  e nunca avaliadas, e ficam visíveis ao operador (FR-027).
- Exposta a `sharing` por `collection.api` (FR-027); ausência de entrada não prova
  segurança do IOC.

### Resultado de score

Resultado reproduzível da avaliação de um IOC.

- `id`, `ioc_id`, `scoring_run_id`, `configuration_id`, revisão de entrada avaliada.
- `as_of`: data de referência usada no frescor e na normalização.
- `rank` e `in_top_n`: posição entre os scores válidos da execução e pertinência ao
  top-N da Configuração CARIOCA, persistidos para consulta por `scoring.api`.
- `priority_score` no intervalo 0–100; valores maiores indicam maior prioridade.
- componentes Source (FeedRank por `orgc`), EventScore (com CADE bruto e normalizado),
  AttributeScore (com idade `t` e grupo) e contribuição final, brutos e normalizados,
  com fatores explicativos, status de validade e a limitação do proxy de fonte.
- `calculated_at`; referência ao snapshot/fonte que permite auditoria.
- Score não válido quando há entrada necessária ausente ou configuração incompleta;
  nesse caso registrar a insuficiência em vez de inventar resultado.

### Execução de scoring

- `id`, configuração CARIOCA, `as_of`, início/fim, status, quantidade
  processada/excluída/falha, resumo de erros e `warnings` (por exemplo, população vazia,
  MinMax com valores iguais), persistidos para a exportação de observabilidade.
- Estados: iniciada → concluída; iniciada → falha. Execução interrompida não deve
  limpar candidatos não calculados com sucesso.
- Job diário único; execuções simultâneas do mesmo job são impedidas.
- **Execução vigente** (FR-016): a última execução concluída com sucesso; seu
  `finished_at` define a idade dos scores. Se a idade exceder 48 horas, o módulo
  `sharing` suspende novos envios e emite aviso ao operador até nova execução
  bem-sucedida; falhas de execução não substituem a vigente.

### Política de compartilhamento

- `id`, `peer_id`, `minimum_priority_score`, habilitada, versão e timestamps.
- O limite deve estar no intervalo de score definido pelo algoritmo (0–100). O `top_n`
  vem da Configuração CARIOCA e vale para todos os peers.
- Elegibilidade exige score válido que atinja o mínimo, posição no top-N da execução
  vigente e ausência em warninglist habilitada (FR-016, FR-027); distribuição, autorização,
  publicação e sharing group continuam sujeitos às regras nativas do MISP.

### Peer MISP e tentativa de compartilhamento

**Peer MISP**:

- `id`, identidade/URL, versão detectada, credencial referenciada com segurança e
  configuração de sync push/distribution.
- Origem: variáveis de ambiente do container de scoring/sharing, lidas na inicialização
  (FR-015). Configuração ausente ou inválida (por exemplo, mínimo fora de 0–100) impede
  o início do compartilhamento com erro explícito.
- **Política efetiva carregada**: a cada inicialização o conjunto de peers e mínimos é
  gravado com hash e timestamp (módulo `sharing`); cada tentativa referencia essa
  política. Alterações só valem após reiniciar o container.

**Tentativa de compartilhamento**:

- `id`, `peer_id`, `ioc_id`, resultado de score e política avaliados, referência do
  evento/atributo compartilhado, timestamps e estado.
- Estados: elegível → aguardando sync → confirmado; falha/resultado desconhecido →
  reconciliação ou nova tentativa; inelegível → não enviado.
- Timeout ambíguo exige reconciliação por UUID/estado do peer antes de repetir criação.
- Uma tentativa não pode sobrepor ou enfraquecer regras de distribuição nativas.

## Relações principais

```text
IOC 1 ─── * Observação de origem * ─── 1 Endpoint de coleta
IOC 1 ─── 0..1 Candidato a re-scoring
IOC 1 ─── * Resultado de score * ─── 1 Execução de scoring
Execução de scoring * ─── 1 Configuração CARIOCA
Execução de scoring 1 ─── * Estatísticas de população
Execução de scoring 1 ─── * Exclusão de score * ─── 1 IOC
Endpoint de coleta 1 ─── * Rejeição de indicador (por origem; não relacionada a IOC)
IOC 0..* ─── * Entrada de warninglist (por tipo + valor normalizado)
Peer MISP 1 ─── * Política de compartilhamento
Peer MISP 1 ─── * Tentativa de compartilhamento * ─── 1 IOC
```

## Invariantes de domínio

1. Um único IOC lógico por tipo e valor normalizado.
2. Observações de origem distintas são preservadas, ainda que consolidadas no mesmo IOC.
3. Alterações relevantes em qualquer observação relacionada atualizam a revisão do IOC
   e o marcam para re-scoring; o scoring diário recalcula toda a população válida com
   um único `as_of`.
4. Um score referencia a revisão exata do IOC e a configuração CARIOCA usada.
5. Resultado de score não é entrada do algoritmo e não pode disparar seu próprio
   re-scoring.
6. Só score válido que cumpra o mínimo por peer, esteja no top-N da execução vigente e
   não conste em warninglist habilitada pode solicitar compartilhamento; MISP mantém
   autoridade final sobre distribuição e autorização.
7. Só IOCs de tipo suportado e não expirados (frescor > 0) entram na população e na
   normalização; os demais ficam com exclusão registrada.
8. Nenhum cálculo usa o relógio do sistema: todo o tempo vem do `as_of` da execução.
9. Um indicador inválido ou não suportado nunca vira IOC; fica em Rejeição de indicador,
   uma por origem e motivo.
10. Só scores da execução vigente (concluída com sucesso há no máximo 48 horas) podem
    originar novos envios; acima disso o compartilhamento é suspenso.

## Revisão 2026-11-24

Alinha o modelo às decisões da revisão do plano e ao que já existe no banco. Os
detalhes e a justificativa estão em `research.md`, seção "Revisão 2026-11-24".

### Já existente (não recriar)

- `collection`: `ioc`, `endpoint_coleta` (com `generation` da 002), `observacao_origem`
  (com `attribute_id` e `published`), `rejeicao_indicador`, `entrada_warninglist`.
- `scoring`: `execucao_bloqueio`, `decisao_bloqueio` (feature 002).
- `sharing`: `pihole_policy`, `pihole_entry`, `pihole_attempt` (feature 002).

### Configuração CARIOCA (acréscimos)

- `type_groups`: mapeamento fechado tipo MISP → grupo (`hash`, `ip`, `domain`), com os
  tipos da tabela do Notion §2.1. `url` não pertence a nenhum grupo. Tipos compostos
  `filename|<hash>` entram em hash.
- `scoring_to_ids_only: true`: só observações `to_ids=true` entram em qualquer
  componente.
- `aggregation: max-observation` com desempate `source_created_at` e depois
  `(source_instance_id, attribute_uuid)`.
- `normalization_scopes`: `cade` = eventos com observação `to_ids` ativa; `event` =
  eventos com observação válida; `attribute` e `source` = observações válidas.
- `feed_rank`: `damping 0,85`, `iterations 50`, `dangling: uniform`, pesos 50/50.
- `approved`, `approved_by`, `approved_at`, `evidence_ref` (avaliação de σ) e
  `content_hash` (SHA-256 do YAML canônico). Ativar o scoring exige `approved: true`.

### Avaliação de observação (nova, `scoring.avaliacao_observacao`)

Componentes de cada observação válida numa execução; é o que permite explicar e
reproduzir o score do IOC.

- `scoring_run_id`, `ioc_id`, `source_instance_id`, `attribute_uuid`, `event_uuid`,
  `orgc_uuid`.
- `age_days`, `attribute_raw`, `attribute_norm`; `threat_level`, `analysis`,
  `cade_raw`, `cade_norm`, `event_raw`, `event_norm`; `source_value`, `source_norm`;
  `priority`.
- `minmax_degenerate`: lista dos componentes em que máximo = mínimo (valor 50).
- **Unicidade**: `(scoring_run_id, source_instance_id, attribute_uuid)`.

### Resultado de score (ajustes)

- Ganha `winning_source_instance_id`, `winning_attribute_uuid` e
  `observations_evaluated`. Os componentes são os da observação vencedora.
- `priority_score`, `rank` e `in_top_n` são por IOC lógico. O `rank` é denso pela
  prioridade decrescente, com o mesmo desempate da agregação aplicado à observação
  vencedora. `in_top_n` marca exatamente os `top_n` primeiros.
- **Unicidade**: `(scoring_run_id, ioc_id)`.

### Estatísticas de população (ajustes)

- `sigma_by_category` (16 categorias, com o método e a regra σ = 0 aplicados),
  `n_by_category_stats` (insumos do estimador), mínimos e máximos de cada escopo de
  normalização e, por organização, `first_pairs`, `contribution`, `pagerank`,
  `pagerank_norm`, `value`, `source_norm`.

### Exclusão de score (motivos)

`type_without_decay_group` (inclui `url`), `expired`, `not_to_ids`, `unpublished`,
`missing_data` (TL, SA, timestamp, categoria ou `orgc` ausente ou desconhecido) e
`incomplete_configuration`. Os motivos são avaliados por observação; o IOC recebe o
motivo da sua observação ativa de maior precedência (`incomplete_configuration` >
`missing_data` > `unpublished` > `not_to_ids` > `type_without_decay_group` > `expired`).
A exclusão é registrada por IOC; um IOC com pelo menos uma observação válida não é
excluído.

### Peer MISP, política e tentativa (ajustes)

- `sharing.peer_misp`: `peer_id`, `base_url`, `credential_secret_ref` (comentário
  `secret`), `minimum_priority_score`, `distribution`, `sharing_group_uuid` opcional e
  `outbound_event_uuid` (evento de saída local deste peer).
- `sharing.politica_compartilhamento`: snapshot da política efetiva por inicialização
  (`policy_hash`, `loaded_at`, `peers` sem segredos).
- `sharing.tentativa_compartilhamento`: `peer_id`, `ioc_id`, `scoring_run_id`,
  `policy_hash`, `outbound_attribute_uuid` (UUID v5 de `peer_id` + `ioc_id`),
  `permitting_source_instance_id` e `permitting_attribute_uuid` (observação que tornou
  o envio permitido), `outbound_distribution` (0–4) e `outbound_sharing_group_uuid`
  opcional, estado
  (`eligible`, `requested`, `confirmed`, `failed`, `ambiguous`, `ineligible`,
  `suspended`), `attempts`, `next_attempt_at`, `last_error` seguro e timestamps.
- **Unicidade**: uma tentativa corrente por `(peer_id, ioc_id)`.

### Migrations

| Revisão | Conteúdo |
|---|---|
| `0008_carioca_scoring` | `configuracao_carioca`, `execucao_scoring`, `estatisticas_populacao`, `avaliacao_observacao`, `resultado_score`, `exclusao_score` (schema `scoring`) |
| `0009_rescoring_candidates` | `candidato_rescoring` (schema `scoring`) |
| `0011_event_sharing_group` | `event_sharing_group_id` em `collection.observacao_origem` (nulo para dados legados até a recoleta) |
| `0010_misp_sharing` | `peer_misp`, `politica_compartilhamento`, `tentativa_compartilhamento` (schema `sharing`) |

As permissões seguem `0001_module_roles`: o papel do scoring escreve em `scoring` e
`sharing`, e o `observer` lê tudo.

### Tipos de domínio do ajuste de DDD

Tipos sem persistência própria, que passam a carregar as regras hoje espalhadas em
infraestrutura e `api.py` (etapas D1–D9 do plano). Todos são dataclasses congeladas.

| Tipo | Módulo | Campos e comportamento |
|---|---|---|
| `SourceSnapshot` | `collection.domain` | `source_instance_id`, `generation`, `status`, `last_success_at`; `trusted(now, max_age) -> bool` (geração > 0, estado `completed`, último sucesso dentro de `max_age`). Substitui o SQL de `unavailable_blocking_sources` e a checagem em `scoring` |
| `ObservationSnapshot` | `collection.domain` | `Observation` mais `ioc_id`, `normalized_value` e `input_revision` do IOC; `effective_distribution()` = menor entre `distribution` e `event_distribution` (`5` herda do evento) |
| `CollectionSnapshot` | `collection.domain` | `sources`, `observations`, `warninglists`, `rejections`, lidos numa única transação `REPEATABLE READ` |
| `WarninglistIndex` | `collection.domain` | Montado de uma lista de `WarninglistEntry` por origem; `match(kind, value, mode) -> True/False/None`. `mode="strict"`: entrada não suportada dá `None` (indeterminado). `mode="fr027"`: ignora a não suportada. Usa conjunto exato, sufixos de hostname e redes CIDR |
| `IOC` | `collection.domain` | Já existe e passa a ser usado por `reconcile_snapshot` como identidade `(type, normalized_value)` |
| `Changeset` | `collection.domain` | Saída de `reconcile_snapshot`: observações a inserir e atualizar, IOCs a criar, rejeições a gravar e resolver, remoções e o conjunto de `ioc_id` cuja revisão sobe. Recusa a reconciliação quando passa de `removal_ratio` |
| `DecayGroup` | `scoring.domain` | `name`, `D`, `T`; `freshness(t_days) -> float | None` (tempo negativo dá `None`; `t >= T` dá 0). Usado pelo bloqueio simples (`domain`/`url`: 0,7; 365) e pelo CARIOCA |
| `BlockingReason`, `ScoreModel` | `scoring.domain` | `StrEnum` com os valores já gravados no banco |
| `BlockingDecision` | `scoring.domain` | Origem, UUID, `attribute_id` opcional, `block`, `reason`, `as_of`, `expires_at`, `generation`, evidência tipada. Gravada em `decisao_bloqueio` sem mudar colunas |
| `RemoteEntry`, `ManagedEntry` | `sharing.domain` | `RemoteEntry` é a entrada do Pi-hole traduzida pelo adaptador (`id`, `comment`, `groups`, `enabled`); `ManagedEntry.is_owned_by(remote)` contém a regra de propriedade de hoje (`owned()`) |

### Execução de scoring (estado)

Estados `running`, `completed` e `failed`, iguais aos de `execucao_bloqueio` e
`endpoint_coleta`. A Execução vigente é a última `completed`.

### Elegibilidade de distribuição (domínio de `sharing`)

`DistributionDecision(permitting_observation, distribution, sharing_group_uuid)` ou
`None`. Regra: entre as observações ativas do IOC com evento publicado, considerar as
de distribuição efetiva `1`, `2` ou `3`, ou `4` com o servidor do peer no sharing
group; `0` nunca alcança. Escolher a mais restritiva (`1` < `2` < `3`; `4` conta como
mais restritiva que `1`), com o desempate da agregação. Sem observação que alcance o
peer, o motivo de inelegibilidade é `distribution_not_allowed`.
