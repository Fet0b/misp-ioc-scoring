# Modelo de dados: Plataforma de Scoring e Compartilhamento de IOCs

Este é o modelo conceitual do domínio. Identificadores locais são internos; UUIDs MISP
identificam objetos na origem e não substituem a identidade de um IOC lógico.

## Entidades

### IOC

Indicador lógico consolidado pelas observações equivalentes.

- `id`: identificador interno estável.
- `type`: tipo canônico do atributo MISP.
- `normalized_value`: valor normalizado, sem descartar a forma original.
- `created_at`, `updated_at`: timestamps do registro local.
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
- `to_ids`, distribuição, tags e campos relevantes ao algoritmo/política.
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
- método/versão de FeedRank e parâmetros necessários para sua reprodução.
- parâmetros de normalização MinMax e combinação SPOTIS.
- parâmetros não especificados no artigo precisam de valor explícito, justificativa e
  aprovação antes de ativar a configuração.
- Configuração ausente ou inválida impede cálculo, em vez de usar default implícito.

### Candidato a re-scoring

Indica um IOC lógico cujos dados relevantes mudaram e cujo score precisa ser recalculado.

- `ioc_id`: chave primária e relação um-para-um com IOC.
- `pending`: booleano que indica trabalho ainda não concluído.
- `input_revision`: revisão atual dos dados de entrada usados no cálculo.
- `reason`, `marked_at`, `last_attempt_at`, `last_error`: rastreabilidade do ciclo.
- Uma alteração numa Observação de origem percorre sua relação até o IOC e marca o
  IOC lógico; múltiplas observações não criam candidatos duplicados.
- Apenas campos de entrada usados pelo algoritmo marcam candidato; gravações de score
  não o fazem.
- A execução lê uma revisão; conclui e limpa `pending` somente se o cálculo tiver
  sucesso e a revisão não tiver mudado durante a execução. Falha ou revisão concorrente
  mantém o candidato pendente.

### Resultado de score

Resultado reproduzível da avaliação de um IOC.

- `id`, `ioc_id`, `scoring_run_id`, `configuration_id`, revisão de entrada avaliada.
- `priority_score` no intervalo 0–100; valores maiores indicam maior prioridade.
- componentes FeedRank, EventScore, AttributeScore e contribuição final, com fatores
  explicativos e status de validade.
- `calculated_at`; referência ao snapshot/fonte que permite auditoria.
- Score não válido quando há entrada necessária ausente ou configuração incompleta;
  nesse caso registrar a insuficiência em vez de inventar resultado.

### Execução de scoring

- `id`, configuração CARIOCA, início/fim, status, quantidade processada/falha,
  resumo de erros.
- Estados: iniciada → concluída; iniciada → falha. Execução interrompida não deve
  limpar candidatos não calculados com sucesso.
- Job diário único; execuções simultâneas do mesmo job são impedidas.

### Política de compartilhamento

- `id`, `peer_id`, `minimum_priority_score`, habilitada, versão e timestamps.
- O limite deve estar no intervalo de score definido pelo algoritmo (0–100).
- Elegibilidade exige score válido que atinja o mínimo; distribuição, autorização,
  publicação e sharing group continuam sujeitos às regras nativas do MISP.

### Peer MISP e tentativa de compartilhamento

**Peer MISP**:

- `id`, identidade/URL, versão detectada, credencial referenciada com segurança e
  configuração de sync push/distribution.

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
Peer MISP 1 ─── * Política de compartilhamento
Peer MISP 1 ─── * Tentativa de compartilhamento * ─── 1 IOC
```

## Invariantes de domínio

1. Um único IOC lógico por tipo e valor normalizado.
2. Observações de origem distintas são preservadas, ainda que consolidadas no mesmo IOC.
3. Alterações relevantes em qualquer observação relacionada atualizam a revisão do IOC
   e o marcam para re-scoring.
4. Um score referencia a revisão exata do IOC e a configuração CARIOCA usada.
5. Resultado de score não é entrada do algoritmo e não pode disparar seu próprio
   re-scoring.
6. Só score válido que cumpra o mínimo por peer pode solicitar compartilhamento;
   MISP mantém autoridade final sobre distribuição e autorização.
