# Contrato de consulta para sender

A identidade canônica é `(source_instance_id, attribute_uuid)`; ID numérico local é opcional e sempre acompanhado da origem. Os dois identificadores não são intercambiáveis. O sender deve usar uma superfície somente leitura disponibilizada pelo módulo scoring (consulta SQL/view ou API Python documentada na implementação), jamais ler o booleano bruto sem checar validade.

Para cada atributo conhecido retornar origem, UUID, ID local quando disponível, decisão efetiva (`true`/`false`), motivo, `as_of`, vencimento e versão da regra. Resultado ausente, erro de leitura, dados incompletos ou avaliação indeterminada nunca autoriza bloqueio; a interface distingue esses estados de `false` calculado. Um `true` exige execução concluída, geração da origem ainda correspondente, snapshot de coleta confiável e dentro de `SCORE_MAX_AGE_HOURS`, e atributo não expirado. Se qualquer condição falhar, entregar `false` efetivo e motivo de invalidação.

Consulta por ID local deve incluir origem e retornar ausência ou erro se não for inequívoca. Este contrato cobre a consulta de decisões; o envio ao Pi-hole é definido em `pihole.md`. O transporte de envio a peers MISP permanece fora desta entrega. O contrato não promete decisões para atributos não coletados (por exemplo, quando `MISP_TO_IDS_ONLY=true`).
