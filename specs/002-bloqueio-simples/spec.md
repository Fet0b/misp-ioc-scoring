# Feature Specification: Bloqueio simples de indicadores

**Created**: 2026-11-19
**Status**: Draft
**Input**: Critérios rastreáveis de bloqueio, decaimento CARIOCA, flags independentes para compartilhamento MISP e Pi-hole e seleção de score para Pi-hole.

## User Scenarios & Testing

### User Story 1 - Consultar decisões de bloqueio (P1)

O operador consulta, para cada atributo de origem, se deve ser bloqueado. Um atributo ativo é elegível quando to_ids é verdadeiro, seu tipo é URL ou domínio, o evento tem analysis igual a 2, o valor não pertence a warninglist habilitada e o frescor não expirou.

**Independent Test**: avaliar atributos que satisfazem e que violam cada condição e consultar suas decisões.

**Acceptance Scenarios**:

1. **Given** um atributo elegível e não expirado, **When** a avaliação termina, **Then** sua decisão é verdadeira.
2. **Given** uma condição não satisfeita ou atributo removido, **When** a avaliação termina, **Then** sua decisão é falsa.
3. **Given** mudança de atributo, evento, warninglist ou passagem do tempo, **When** ocorre nova avaliação, **Then** a decisão reflete o estado atual.

### User Story 2 - Controlar módulos (P2)

O operador ativa e desativa módulos por configuração de ambiente e controla separadamente os envios para MISP e Pi-hole.

**Independent Test**: iniciar com combinações de flags e verificar quais trabalhos são executados.

**Acceptance Scenarios**:

1. **Given** um destino de compartilhamento desativado, **When** o serviço inicia, **Then** nenhum envio é realizado para esse destino.

### Edge Cases

- Identificadores locais de atributos podem colidir entre instâncias MISP; preservar origem e UUID.
- A ausência de dados necessários ou de warninglists confiáveis não deve gerar bloqueio positivo.
- Um atributo pode deixar de ser elegível por expiração sem sofrer alteração na origem.
- URLs usam o mesmo decaimento de domínios: D = 0,7 e prazo de 365 dias.

## Requirements

### Functional Requirements

- **FR-001**: Avaliar individualmente atributos ativos com to_ids verdadeiro, tipo url ou domain e analysis do evento igual a 2.
- **FR-002**: Excluir valores presentes em warninglists habilitadas e atributos expirados pelo decaimento CARIOCA.
- **FR-003**: Persistir uma decisão booleana consultável por atributo e origem para uso pelo sender, incluindo decisões falsas.
- **FR-004**: Recalcular decisões para refletir alterações, remoções, warninglists e passagem do tempo.
- **FR-005**: Permitir ativação dos módulos por variáveis de ambiente e manter ambos os destinos de compartilhamento desativados por padrão.
- **FR-006**: Registrar motivo da decisão e referência temporal para auditoria, sem expor segredos.

### Key Entities

- **Atributo de origem**: identificador, origem, tipo, valor e contexto do evento.
- **Decisão de bloqueio**: atributo, booleano, motivo e instante de avaliação.

## Success Criteria

- **SC-001**: Todos os casos de teste das condições e suas negações produzem a decisão esperada.
- **SC-002**: O operador consegue identificar a origem e consultar a decisão de cada atributo avaliado.
- **SC-003**: Nenhum envio ocorre para um destino cujo compartilhamento está desativado.

## Assumptions

- A decisão é por atributo, não uma agregação por valor de IOC.
- O bloqueio é aplicado pelo Pi-hole quando seu envio estiver habilitado; o envio para peers MISP permanece independente e desativado por padrão.
- Valores com dados incompletos não recebem decisão positiva.

## Ampliação: compartilhamento Pi-hole

### User Story 3 - Enviar indicadores elegíveis ao Pi-hole (P1)

Como operador, quero habilitar o envio ao Pi-hole separadamente do envio a peers MISP e selecionar pela configuração se os indicadores serão elegíveis pela decisão simples ou por CARIOCA. Assim o Pi-hole recebe hostnames rastreáveis sem depender do compartilhamento MISP.

**Teste independente**: com um Pi-hole de teste e indicadores de origem conhecidos, ativar apenas Pi-hole, selecionar cada modelo disponível e verificar elegibilidade, envio, confirmação, repetição e retirada de entradas gerenciadas quando deixarem de ser elegíveis.

**Cenários de aceitação**:

1. **Given** envio Pi-hole habilitado e modelo `default`, **When** uma decisão simples válida é verdadeira, **Then** o hostname elegível é sincronizado com o Pi-hole.
2. **Given** envio Pi-hole com modelo `carioca`, **When** o CARIOCA está ativo com configuração aprovada, **Then** só domínios e hostnames com score válido da execução vigente que atinja o corte configurado são sincronizados; sem execução vigente, com score vencido ou sem corte não há envio, e a ativação sem CARIOCA ativo falha com erro claro.
3. **Given** URL elegível, **When** seu hostname é enviado, **Then** o bloqueio se aplica ao hostname inteiro, não ao caminho específico; essa ampliação e o atributo de origem ficam rastreáveis.
4. **Given** flags independentes, **When** um destino está desabilitado, **Then** nenhum envio é feito para esse destino.
5. **Given** um hostname anteriormente gerenciado que deixou de ter qualquer evidência elegível, **When** a reconciliação é executada com evidência confiável, **Then** somente a entrada gerenciada pelo projeto é retirada; entradas manuais de terceiros não são alteradas.

### Requisitos adicionais

- **FR-007**: Controlar o envio ao MISP e ao Pi-hole por flags independentes, ambas desativadas por padrão. Esta entrega implementa o destino Pi-hole; o transporte MISP permanece futuro e ativar sua flag antes da implementação falha com erro claro.
- **FR-008**: Selecionar o score do Pi-hole por ambiente: `default` usa decisão simples; `carioca` exige resultado CARIOCA válido da execução vigente e corte configurado explicitamente entre 0 e 100, e envia só `domain` e `hostname` (URL fica fora do CARIOCA). Não inventar score; sem CARIOCA ativo e aprovado, a ativação deve falhar de forma clara.
- **FR-009**: Derivar hostname normalizado de URL elegível ou usar domínio elegível; rejeitar IP literal, host inválido e formatos não suportados, preservando o valor original e explicando o alcance do bloqueio.
- **FR-010**: Enviar, acompanhar e reconciliar entradas gerenciadas de forma idempotente, com registro de origem, score, tentativa, confirmação e erro; preservar entradas manuais, outros grupos e permissões do Pi-hole.
- **FR-011**: Respeitar warninglists, frescor e dados confiáveis para ambos os modelos; falhas de coleta ou de comunicação não devem criar inclusão ou remoção em massa baseada em snapshot incompleto.
- **FR-012**: Investigar categorias e tipos realmente usados pelos peers de origem para URLs por meio de dados MISP disponíveis, registrar resultados agregados sem valores sensíveis e preservar a categoria observada; não presumir que uma categoria padrão descreve todos os peers.

### Resultados adicionais

- **SC-004**: Em testes com Pi-hole isolado, 100% dos hostnames elegíveis são confirmados e repetições não criam duplicatas.
- **SC-005**: Em testes, nenhuma entrada manual é modificada ou removida, e nenhum destino desativado recebe envio.

### Entidades e hipóteses adicionais

- **Destino Pi-hole**: configuração e estado de autenticação do destino, sem segredos em logs.
- **Entrada gerenciada**: hostname e evidências elegíveis por origem, modelo de score, estado de sincronização e propriedade da entrada.
- A configuração de score é específica do Pi-hole; a configuração de sharing MISP é independente. O critério por tipo permanece necessário para selecionar indicadores coerentes, mas não se exige uma flag adicional de tipo.
- A operação sobre URLs amplia o alcance ao hostname inteiro, limitado às consultas DNS tratadas pelo Pi-hole; o envio não inclui caminho, porta nem parâmetros.
- As categorias efetivamente usadas pelos peers dependem de acesso às suas instâncias ou aos dados já coletados; sem esses dados, registrar a investigação como pendente e não inventar resultados.

### Decisões de reconciliação

- A propriedade de uma entrada remota deve ser comprovada por identidade e marca verificável. Se uma resposta de criação se perder ou a entrada for alterada e a propriedade não puder ser comprovada, mantê-la e avisar o operador; entradas preexistentes não são adotadas.
- Uma entrada gerenciada com vínculo a origem cujo snapshot esteja incompleto ou vencido permanece até essa origem voltar a ser confiável. Outras entradas sem vínculo com essa origem podem ser reconciliadas normalmente; após recuperação, remover somente se nenhuma evidência elegível restar.
