# Contrato do destino Pi-hole

- **Configuração:** `SHARING_PIHOLE_ENABLED`, `PIHOLE_SCORE_MODEL=default|carioca`, endpoint, referência de segredo e intervalo; `PIHOLE_CARIOCA_MIN_SCORE` é obrigatório e está entre 0 e 100 quando `carioca` estiver ativo. `SHARING_MISP_ENABLED` é independente. Defaults de ambos os destinos: desativado.
- **Disponibilidade:** a seleção `carioca` exige `SCORING_CARIOCA_ENABLED=true` com configuração aprovada; sem isso a inicialização falha explicitamente (`PIHOLE_REQUIRES_SCORING_CARIOCA_ENABLED` ou `CARIOCA_CONFIGURATION_NOT_APPROVED`). Sem execução vigente, ou com ela mais antiga que `SCORE_MAX_AGE_HOURS`, nada é enviado e as entradas existentes são preservadas. O modo `carioca` envia só `domain` e `hostname`; URLs ficam com o modo `default`. A seleção `default` usa decisão simples válida e atual. Configuração Pi-hole não é exigida quando desativado.
- **Entrada:** atributo MISP `domain` ou `url` elegível, com origem e UUID. URL é convertida para hostname exato e validado; esquema, porta, caminho, query e fragmento não são enviados. IP literal ou host inválido é rejeitado com motivo. O host inteiro será afetado pelo bloqueio DNS, sem incluir automaticamente subdomínios.
- **Política:** preservar warninglists, frescor e confiabilidade de dados. CARIOCA exige score >= corte; nenhuma regra top-N implícita. Deduplicar por hostname e guardar todas as evidências.
- **Transporte:** API Pi-hole v6, autenticação via segredo e sessão com expiração, confirmação do estado remoto e reautenticação controlada. TLS verificado por padrão, HTTP somente com opção explícita. Contrato efetivo e versão são verificados pela documentação da instância. Nenhuma senha ou sessão em logs.
- **Reconciliação:** adicionar idempotentemente; confirmar sucesso; em timeout consultar o estado antes de repetir. Remover apenas entradas criadas e comprovadamente gerenciadas pelo projeto, quando não houver evidência elegível e o snapshot completo for confiável. Nunca adotar ou remover entrada manual, alterar grupos ou limpar a lista inteira. Comprovar propriedade por identidade remota e marca verificável; se uma resposta de criação se perder ou uma alteração remota impedir a comprovação, manter a entrada e sinalizar intervenção. Para origem com snapshot incompleto ou vencido, manter entradas que tenham vínculo com essa origem; reconciliar normalmente entradas sem esse vínculo e reavaliar os vínculos após recuperação.
- **Falhas:** preservar estado observado, registrar motivo seguro e retry limitado; snapshot incompleto suspende operação destrutiva. A desativação do destino impede novos envios e remoções, sem alterar entradas existentes.

A marca de propriedade é gravada em `comment` como `misp-ioc-scoring:<UUID>`
e persistida localmente antes do POST. Depois de confirmação por leitura,
o ID remoto também é persistido. Uma tentativa ambígua só pode ser vinculada
se o comentário remoto casar com a marca pendente e a API fornecer um ID.

As entradas novas usam o grupo padrão (ID 0). Se um operador trocar o grupo,
desativar a entrada ou alterar sua marca ou ID, a próxima reconciliação
preserva a entrada e registra que a propriedade precisa ser verificada.
