# Modelo de dados

## Observação de origem e snapshot

Identidade `(source_instance_id, attribute_uuid)`; `attribute_id` numérico local opcional, `event_uuid`, tipo, valor normalizado, `to_ids`, `analysis`, `source_modified_at` e `removed_at`. Coleta mantém uma geração monotônica por origem e o instante do último snapshot completo e confiável de observações e warninglists; coleta falha ou incompleta é identificável. A geração muda transacionalmente quando dados relevantes ou warninglists mudam, incluindo remoção e falhas que invalidem confiança. Migração preserva dados anteriores e trata snapshots legados como não confiáveis até nova coleta.

## Execução de bloqueio

ID, `as_of` UTC, versão da regra, início, fim, estado e erro seguro. Apenas execução concluída publica resultados. Falhas não apagam histórico nem autorizam resultados antigos além da validade. Exclusão mútua em banco protege múltiplos workers.

## Decisão de bloqueio

Tabela `scoring.decisao_bloqueio`, uma linha corrente por `(source_instance_id, attribute_uuid)`, com `attribute_id` opcional, `block` boolean não nulo, motivo, ID da execução, geração da coleta utilizada, `as_of`, vencimento, timestamp de atributo, tipo, `to_ids`, `analysis` e resultado da verificação de warninglist. Sem credenciais ou necessidade de repetir valor bruto. Chave de origem + UUID garante unicidade; ID local só é único por origem quando presente. Razões incluem elegível, removido, tipo, to_ids, analysis, warninglist, expirado e dados/avaliação indeterminados.

**Transições:** cada snapshot completo gera nova decisão; remoção ou rejeição conhecida invalida decisão anterior. Leitura efetiva nunca retorna positivo se geração diverge, coleta está indisponível/não confiável, prazo do snapshot ou decisão expirou, ou execução não terminou. Publicação e verificação de geração são coordenadas com transação da coleta. Leitura distingue `false` de inexistente/indeterminado.

## Política de compartilhamento Pi-hole

Configuração efetiva: destino, flag, modelo `default` ou `carioca`, corte opcional somente para CARIOCA (obrigatório e finito, de 0 a 100 quando selecionado), frequência e referência de segredo. Gravar versão/hash sem armazenar senha nem SID. Flag MISP é independente e desativada por padrão.

## Hostname gerenciado e evidências

Hostname DNS normalizado, destino, identidade remota e marca verificável de propriedade, propriedade comprovada, estado desejado e confirmado, última sincronização e justificativa de transformação de URL para hostname. Cada vínculo relaciona origem, UUID, tipo, categoria preservada, decisão ou resultado CARIOCA, versão, `as_of` e geração. Podem existir múltiplas observações por hostname; uma só evidência elegível e atual mantém o host desejado. IPs literais e hosts inválidos não geram entrada.

## Tentativa de sincronização

Identidade, hostname, operação, estado pendente/confirmado/falhou/ambíguo, número de tentativas, instantes e erro seguro; timeout ambíguo exige consulta de estado antes de nova tentativa. Exclusões se restringem a registros comprovadamente gerenciados. Entradas vinculadas a uma origem com snapshot incompleto ou vencido são mantidas até a recuperação; entradas sem vínculo com ela podem ser reconciliadas. Se a propriedade não for comprovada após timeout ou alteração remota, manter a entrada e avisar o operador.
