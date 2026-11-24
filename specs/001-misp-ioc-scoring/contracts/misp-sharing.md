# Contrato de integração: compartilhamento MISP

## Propósito

Compartilhar IOCs elegíveis com peers MISP autorizados sem criar um segundo protocolo
de replicação nem substituir os controles de distribuição do MISP.

## Elegibilidade

0. Peers, mínimos e credenciais vêm das variáveis de ambiente do container, lidas na
   inicialização; configuração ausente ou inválida impede o compartilhamento e mudanças
   exigem reiniciar o container. A política efetiva carregada é registrada e referenciada
   pelas tentativas.
1. Deve existir Resultado de score válido para a revisão de entrada atual, vindo da
   execução vigente: a última concluída com sucesso, com no máximo 48 horas. Acima disso
   o compartilhamento é suspenso, o operador é avisado e os envios só retomam após nova
   execução bem-sucedida.
2. O score deve atingir o mínimo configurado para o peer.
3. O IOC deve estar entre os N maiores scores válidos da execução vigente (`top_n` da
   Configuração CARIOCA).
4. O IOC não pode constar em warninglist habilitada (igualdade exata, CIDR ou
   hostname/subdomínio); o motivo é registrado e o score
   mantido (FR-027).
5. O evento/atributo deve obedecer publicação, distribuição, sharing group e permissões
   de conta definidos no MISP.
6. IOC inelegível ou sem score/configuração CARIOCA válida não é enviado.

## Operação

- Usar sync nativo MISP push para peer configurado, com regras explícitas de evento,
  distribuição e credenciais de uma conta de sync dedicada.
- Publicação/envio inicia processamento no MISP, mas não equivale a confirmação de
  recebimento; verificar job/estado ou evidência do peer antes de marcar como confirmado.
- Registrar peer, IOC, score/configuração avaliados, referência MISP enviada,
  timestamps e estado de entrega.
- Em timeout ambíguo, reconciliar pela identidade/UUID no peer antes de repetir uma
  operação de criação ou publicação.
- Falhas transitórias permanecem pendentes para retentativa controlada; falhas
  permanentes ficam visíveis para intervenção.
- Reavaliar score, posição no top-N, warninglist e elegibilidade antes de uma nova
  tentativa; não compartilhar IOC que deixou de atender a qualquer critério. Um score
  de uma execução anterior ao `as_of` vigente não é válido para novo envio.

## Garantias

- Nenhum envio pode ignorar as permissões e distribuição nativas do MISP.
- Repetição não cria duplicação lógica no peer.
- Falha de comunicação não é apresentada como sucesso.
- Segredos, dados de peers restritos e conteúdos não autorizados não são expostos.
- Resultado compartilhado mantém referência à configuração e entradas que justificam
  seu score.

## Referências

- [MISP sharing guide](https://www.circl.lu/doc/misp/sharing/)
- [MISP automation guide](https://www.circl.lu/doc/misp/automation/)

## Revisão 2026-11-24

- **Ativação**: `SHARING_MISP_ENABLED=true` (padrão `false`, independente do Pi-hole).
  Exige `SCORING_CARIOCA_ENABLED=true`, configuração CARIOCA aprovada e peers válidos.
  Sem isso, a inicialização falha com erro explícito.
- **Leitura de scores**: somente por [scoring-api.md](./scoring-api.md)
  (`current_carioca_run` e `carioca_scores` com `top_n_only=True` e o mínimo do peer).
- **Evento de saída por peer**: o push nativo sincroniza eventos publicados. O adaptador
  mantém, na instância MISP local de saída, um evento por peer (`outbound_event_uuid`),
  com a distribuição máxima da política do peer. Cada IOC elegível vira um atributo
  com UUID determinístico (UUID v5 de `peer_id` + `ioc_id`), tipo e valor normalizado
  do IOC, `to_ids=true` e a **distribuição da observação que tornou o envio
  permitido** (e o sharing group dela, se for `4`). Como o MISP aplica o menor valor
  entre evento e atributo, o atributo nunca sai mais amplo que a origem. IOCs que deixam de ser elegíveis têm o atributo
  removido (soft delete) antes da próxima publicação.
- **Confirmação**: publicar o evento só registra `requested`. `confirmed` exige ler o
  atributo no peer pelo UUID. Em timeout, o estado vira `ambiguous` e a próxima rodada
  consulta o peer antes de repetir.
- **Regra de distribuição** (FR-016, clarificação 2026-11-24): basta uma observação
  ativa, de evento publicado, cuja distribuição efetiva seja `1`, `2` ou `3`, ou `4`
  com o servidor do peer no sharing group. Entre as que alcançam, vale a mais
  restritiva. Sem nenhuma, o IOC fica inelegível com motivo `distribution_not_allowed`.
  A regra é reavaliada antes de cada nova tentativa; se a distribuição permitida
  diminuir, o atributo de saída é atualizado ou removido antes da publicação.
- **Retentativas**: quantidade e backoff vêm de variáveis de ambiente
  (`SHARING_RETRY_ATTEMPTS`, `SHARING_RETRY_BACKOFF_SECONDS`) e são reavaliados contra a
  elegibilidade atual a cada tentativa.
- **Pendente de validação**: o desenho precisa de teste contra um MISP isolado com peer
  de sync antes de produção. A conta de sync e as regras de push ficam no MISP.
