# Glossário de domínio

| Termo canônico | Definição | Nome no código | Sinônimos a evitar |
|---|---|---|---|
| IOC | Indicador normalizado e identificado por tipo e valor. | `collection.domain.indicators.IOC` / `collection.ioc` | indicador genérico, artefato |
| Observação de origem | Registro de um atributo recebido de uma instância, evento e atributo MISP. | `Observation`, `ObservationSnapshot` / `collection.observacao_origem` | ocorrência, cópia |
| Resultado de score | Resultado calculado para um IOC em uma execução e configuração. | `ScoreResult`, `CariocaScore` / `scoring.resultado_score` | pontuação, nota |
| Candidato a re-scoring (rastreabilidade) | IOC cuja revisão de entradas difere da última revisão pontuada com sucesso. | `derive_candidates` / `scoring.candidato_rescoring` | fila de recálculo, IOC a recalcular |
| Endpoint de coleta | Instância MISP configurada como fonte de observações. | `SourceSnapshot` / `collection.endpoint_coleta` | servidor, feed |
| Peer MISP | Instância MISP configurada como destino de compartilhamento. | `PeerPolicy` / `sharing.peer_misp` | consumidor, réplica |
| Política de compartilhamento | Regras efetivas que determinam a elegibilidade de envio a um peer. | `SharingPolicy` / `sharing.politica_compartilhamento` | filtro, regra de envio |
| Configuração CARIOCA | Parâmetros versionados e aprovados para o cálculo CARIOCA. | `CariocaConfiguration` / `scoring.configuracao_carioca` | configuração de score |
| População válida | IOCs elegíveis para cálculo na execução vigente. | `observation_exclusion`, `RunSummary.valid_population` | universo, conjunto ativo |
| Exclusão de score | Motivo registrado para um IOC não receber resultado válido. | `ExclusionReason`, `ScoreExclusion` / `scoring.exclusao_score` | descarte, ignorado |
| Estatísticas de população | Estatísticas calculadas sobre a população válida de uma execução. | `calculate` (statistics) / `scoring.estatisticas_populacao` | métricas gerais |
| Execução vigente | Última execução de scoring concluída com sucesso. | `CariocaRun`, `current_carioca_run` / `scoring.execucao_scoring` | score atual, última tentativa |
| Rejeição de indicador | Registro de entrada inválida ou não suportada que não originou IOC. | `IndicatorRejection` / `collection.rejeicao_indicador` | erro de IOC |
| `as_of` | Instante único de referência temporal de uma execução de scoring. | `as_of` | data atual |
| Warninglist | Lista MISP de valores que afetam a elegibilidade de compartilhamento. | `WarninglistEntry`, `WarninglistIndex` / `collection.entrada_warninglist` | blacklist |
| Decisão de bloqueio | Avaliação booleana de uma Observação de origem, identificada pelo UUID de atributo e pela origem. O ID numérico é local à origem. | `BlockingDecision` / `scoring.decisao_bloqueio` | score numérico |
| Destino Pi-hole | Instância DNS que recebe hostnames exatos. Uma URL contribui com seu hostname inteiro. | `PiHolePolicy`, `PiHole` / `sharing.pihole_policy` | filtro de caminho |
| Entrada gerenciada | Regra DNS cuja propriedade o projeto confirma pelo ID remoto e pela marca no comentário. | `ManagedEntry` / `sharing.pihole_entry` | entrada manual |
| Avaliação de observação | Componentes Source, Event e Attribute de uma Observação de origem válida numa execução, com a prioridade resultante. | `ObservationEvaluation` / `scoring.avaliacao_observacao` | score do atributo, nota parcial |
| Observação vencedora | Observação de origem de maior prioridade de um IOC numa execução; o Resultado de score do IOC usa os componentes dela. Empate: `source_created_at` mais antigo, depois origem e UUID. | `aggregation.winners`, `resultado_score.winning_*` | observação principal, melhor atributo |

As tabelas `sharing.pihole_policy`, `sharing.pihole_entry` e `sharing.pihole_attempt` mantêm o nome em inglês por decisão do plano (renomear exigiria migration e mudaria as abas da exportação sem ganho de domínio). As tabelas novas usam português.
