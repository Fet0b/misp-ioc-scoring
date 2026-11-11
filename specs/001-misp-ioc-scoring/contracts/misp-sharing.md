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
