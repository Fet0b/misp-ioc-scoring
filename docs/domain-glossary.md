# Glossário de domínio

| Termo canônico | Definição | Sinônimos a evitar |
|---|---|---|
| IOC | Indicador normalizado e identificado por tipo e valor. | indicador genérico, artefato |
| Observação de origem | Registro de um atributo recebido de uma instância, evento e atributo MISP. | ocorrência, cópia |
| Resultado de score | Resultado calculado para um IOC em uma execução e configuração. | pontuação, nota |
| Candidato a re-scoring (rastreabilidade) | IOC cuja revisão de entradas difere da última revisão pontuada com sucesso. | fila de recálculo, IOC a recalcular |
| Endpoint de coleta | Instância MISP configurada como fonte de observações. | servidor, feed |
| Peer MISP | Instância MISP configurada como destino de compartilhamento. | consumidor, réplica |
| Política de compartilhamento | Regras efetivas que determinam a elegibilidade de envio a um peer. | filtro, regra de envio |
| Configuração CARIOCA | Parâmetros versionados e aprovados para o cálculo CARIOCA. | configuração de score |
| População válida | IOCs elegíveis para cálculo na execução vigente. | universo, conjunto ativo |
| Exclusão de score | Motivo registrado para um IOC não receber resultado válido. | descarte, ignorado |
| Estatísticas de população | Estatísticas calculadas sobre a população válida de uma execução. | métricas gerais |
| Execução vigente | Última execução de scoring concluída com sucesso. | score atual, última tentativa |
| Rejeição de indicador | Registro de entrada inválida ou não suportada que não originou IOC. | erro de IOC |
| `as_of` | Instante único de referência temporal de uma execução de scoring. | data atual |
| Warninglist | Lista MISP de valores que afetam a elegibilidade de compartilhamento. | blacklist |
| Decisão de bloqueio | Avaliação booleana de uma Observação de origem, identificada pelo UUID de atributo e pela origem. O ID numérico é local à origem. | score numérico |
| Destino Pi-hole | Instância DNS que recebe hostnames exatos. Uma URL contribui com seu hostname inteiro. | filtro de caminho |
| Entrada gerenciada | Regra DNS cuja propriedade o projeto confirma pelo ID remoto e pela marca no comentário. | entrada manual |
