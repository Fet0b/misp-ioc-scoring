# Feature Specification: Plataforma de Scoring e Compartilhamento de IOCs

**Feature Branch**: `001-misp-ioc-scoring`

**Created**: 2026-11-09

**Status**: Draft

**Input**: User description: "Coletar e normalizar dados do MISP, persistir os dados necessários ao scoring Carioca, calcular e compartilhar IOCs com peers MISP, com coleta síncrona em cadências próprias por endpoint e recálculo diário dos indicadores afetados por mudanças nos parâmetros do algoritmo."

## Clarifications

### Session 2026-11-09

- Q: Como o sistema deve decidir que dois registros do MISP representam o mesmo
  IOC para evitar duplicações? → A: Um IOC é identificado pela combinação de tipo
  e valor normalizado; observações de cada evento ou atributo MISP são preservadas
  separadamente, e o UUID do atributo identifica a proveniência, não o IOC.
- Q: Quais IOCs devem ser enviados automaticamente aos peers MISP? → A: Somente IOCs
  que atendam a critérios de uma política configurada são compartilhados
  automaticamente; os demais permanecem locais.

### Session 2026-11-10

- Q: Como devemos tratar os parâmetros do CARIOCA que a publicação não especifica
  por completo, como pesos padrão e calibração das distribuições? → A: Usar as
  fórmulas publicadas e exigir configuração explícita para cada parâmetro ausente;
  não calcular score enquanto a configuração estiver incompleta.
- Q: Quais critérios devem tornar um IOC elegível para compartilhamento automático
  com um peer MISP? → A: Exigir um score CARIOCA mínimo configurável por peer,
  respeitando também as permissões e regras de distribuição nativas do MISP.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coletar e normalizar IOCs do MISP (Priority: P1)

Como responsável pela operação, quero coletar indicadores e seus dados de contexto do
MISP e obter registros normalizados, para que dados de diferentes eventos possam ser
comparados e usados de forma consistente.

**Why this priority**: A coleta e a normalização disponibilizam a base necessária para
persistência, cálculo e compartilhamento.

**Independent Test**: Processar um conjunto representativo de eventos MISP e verificar
que cada indicador suportado mantém seu valor original, possui uma representação
normalizada e informa sua origem.

**Acceptance Scenarios**:

1. **Given** eventos MISP contendo indicadores suportados, **When** a coleta é
   executada, **Then** os indicadores e os dados de contexto necessários são
   disponibilizados como registros estruturados com origem identificável.
2. **Given** um indicador com formato inválido ou não suportado, **When** os dados são
   normalizados, **Then** o indicador não é convertido silenciosamente em um valor
   válido e o problema fica identificável para análise.
3. **Given** um evento já coletado, **When** o mesmo evento é coletado novamente,
   **Then** a repetição não cria observações duplicadas nem apaga a proveniência
   existente.
4. **Given** o mesmo indicador normalizado aparece em eventos ou atributos MISP
   diferentes, **When** os dados são coletados, **Then** existe um único IOC lógico
   com observações de origem separadas para cada evento ou atributo.
5. **Given** endpoints MISP com frequências de atualização diferentes, **When** o
   coletor executa suas consultas síncronas, **Then** cada endpoint é consultado
   conforme sua própria cadência, com endpoints mais frequentemente atualizados
   consultados mais vezes.

---

### User Story 2 - Calcular e explicar o score Carioca (Priority: P2)

Como analista, quero calcular um score Carioca para cada IOC usando os dados coletados
que sejam relevantes, para que eu possa priorizar indicadores e entender os fatores que
influenciaram cada resultado.

**Why this priority**: O cálculo transforma os dados normalizados em uma avaliação útil
para triagem e compartilhamento.

**Independent Test**: Fornecer IOCs e observações com valores conhecidos e comparar
score e fatores explicativos com os resultados esperados segundo a definição aprovada
do algoritmo.

**Acceptance Scenarios**:

1. **Given** um IOC com os dados requeridos pelo algoritmo, **When** o score é
   calculado, **Then** o resultado segue os critérios documentados e identifica os
   dados que contribuíram para ele.
2. **Given** um IOC sem um ou mais dados necessários, **When** o cálculo é solicitado,
   **Then** o sistema informa quais dados faltam e não apresenta um score fabricado.
3. **Given** os mesmos dados, critérios e versão do algoritmo, **When** o cálculo é
   repetido, **Then** o score e seus fatores explicativos são os mesmos.
4. **Given** um IOC candidato a novo cálculo, **When** a execução diária de scoring
   é iniciada, **Then** seu score é atualizado com os dados de entrada mais recentes e
   o candidato deixa de estar pendente somente após um cálculo concluído com sucesso.

---

### User Story 3 - Reavaliar IOCs após mudanças nos dados (Priority: P2)

Como analista, quero que um IOC seja marcado para novo scoring quando um dado usado
pelo algoritmo Carioca mudar, para que o score armazenado não fique desatualizado e
possa ser reavaliado na próxima execução diária.

**Why this priority**: A relação explícita entre mudanças nos dados de entrada e
reavaliação evita que scores baseados em dados antigos permaneçam como atuais.

**Independent Test**: Alterar um campo usado pelo algoritmo e confirmar que somente
os IOCs relacionados ficam pendentes; executar o scoring diário e confirmar que os
scores são atualizados e os candidatos concluídos deixam de estar pendentes.

**Acceptance Scenarios**:

1. **Given** uma observação associada ao ID de atributo de um IOC, **When** um campo
   usado pelo algoritmo Carioca é alterado, **Then** o IOC relacionado é marcado uma
   única vez como candidato a re-scoring.
2. **Given** uma linha alterada apenas em campos que não participam do cálculo,
   **When** a atualização é persistida, **Then** o IOC não é marcado para re-scoring.
3. **Given** que o próprio resultado do score foi atualizado, **When** essa gravação
   ocorre, **Then** ela não volta a marcar o mesmo IOC como candidato.
4. **Given** um candidato cujo cálculo falha ou cujos dados relevantes mudam durante
   a execução, **When** a execução diária termina, **Then** o candidato permanece
   pendente para uma execução posterior.

---

### User Story 4 - Compartilhar IOCs com peers MISP (Priority: P3)

Como responsável pela operação, quero compartilhar automaticamente com peers MISP
configurados os IOCs que atendam à política de compartilhamento, para que outras
instâncias possam usar os indicadores avaliados sem divulgar os que não são elegíveis.

**Why this priority**: O compartilhamento distribui os resultados para além da
instância que coleta e calcula os scores.

**Independent Test**: Executar o compartilhamento com IOCs que atendem e não atendem à
política e verificar que somente os elegíveis são enviados a um peer de teste, sem
duplicações em uma repetição segura.

**Acceptance Scenarios**:

1. **Given** um IOC calculado, seu score atende ao mínimo configurado para o peer e
   o MISP autoriza sua distribuição, **When** o compartilhamento é executado,
   **Then** o IOC é enviado
   preservando seus dados e score de acordo com as convenções MISP acordadas.
2. **Given** um peer temporariamente indisponível, **When** o envio falha, **Then** a
   falha fica visível e o IOC permanece identificável como pendente para nova tentativa.
3. **Given** um envio já concluído, **When** o mesmo IOC é compartilhado novamente,
   **Then** a operação não cria uma duplicação lógica no peer.
4. **Given** um IOC cujo score está abaixo do mínimo configurado para o peer ou cuja
   distribuição não é autorizada pelo MISP, **When** o compartilhamento é executado,
   **Then** o IOC não é enviado a esse peer.

### Edge Cases

- Um evento não contém os atributos opcionais esperados ou contém campos conflitantes.
- Um indicador é atualizado na origem depois de ter sido coletado e normalizado.
- Uma coleta termina parcialmente por indisponibilidade da origem.
- Um endpoint demora ou falha durante uma execução síncrona de coleta, enquanto os
  demais endpoints têm cadências próprias.
- Há dados insuficientes para o algoritmo, ou os dados disponíveis não têm origem
  verificável.
- Uma alteração de dado relevante ocorre durante o cálculo diário de um IOC candidato.
- O score é gravado e a atualização do resultado não pode provocar um novo ciclo de
  marcação do mesmo candidato.
- O peer MISP rejeita um IOC, fica indisponível ou aceita apenas parte do envio.
- Um IOC deixa de atender à política de compartilhamento antes de uma nova tentativa.
- Uma nova tentativa ocorre após uma falha sem duplicar IOCs já aceitos pelo peer.
- Credenciais ou conteúdo externo aparecem em mensagens de erro ou registros de
  operação.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST coletar indicadores e os dados de contexto relevantes de
  fontes MISP configuradas.
- **FR-002**: O sistema MUST preservar o valor original do indicador, a representação
  normalizada e a proveniência disponível de cada observação; a proveniência MUST
  identificar o atributo MISP de origem.
- **FR-003**: O sistema MUST identificar indicadores inválidos ou não suportados sem
  convertê-los silenciosamente em indicadores válidos.
- **FR-004**: O sistema MUST persistir os dados estruturados necessários para calcular
  o score Carioca e explicar seus resultados.
- **FR-005**: A coleta repetida do mesmo dado MUST ser idempotente e MUST preservar
  proveniência e atualizações detectadas na origem. Registros com o mesmo tipo e valor
  normalizado MUST representar um único IOC lógico, mantendo observações de origem
  distintas.
- **FR-006**: O coletor MUST executar as consultas de forma síncrona e MUST manter
  uma cadência de coleta por endpoint MISP, consultando com maior frequência os
  endpoints cujos dados mudam mais frequentemente.
- **FR-007**: O sistema MUST manter um estado persistente de candidato a re-scoring
  associado ao IOC lógico, distinguindo candidatos pendentes dos concluídos. Uma
  mudança recebida por um atributo MISP MUST ser relacionada ao IOC lógico pelo seu
  registro de observação de origem.
- **FR-008**: Quando um campo de entrada usado pelo algoritmo Carioca for alterado, o
  sistema MUST marcar para re-scoring os IOCs relacionados a esse dado.
- **FR-009**: Alterações em campos não usados pelo cálculo e gravações do próprio
  resultado do score MUST NOT marcar um IOC novamente para re-scoring.
- **FR-010**: O componente responsável pelo scoring MUST executar uma atualização
  síncrona diária dos scores pendentes, usando os dados mais recentes disponíveis.
- **FR-011**: O sistema MUST manter um candidato pendente se o cálculo falhar ou se
  um dado relevante mudar durante o cálculo, e MUST remover a pendência somente após
  concluir o cálculo com sucesso sobre os dados vigentes.
- **FR-012**: O sistema MUST calcular scores de acordo com a definição aprovada do
  algoritmo Carioca publicada em [CARIOCA: prioritizing the use of IoC by threats
  assessment shared on the MISP platform](https://doi.org/10.1007/s10207-025-01006-2)
  e com casos de referência aprovados pelo projeto. Parâmetros necessários que a
  publicação não especificar MUST ter configuração explícita aprovada pelo projeto;
  o sistema MUST NOT calcular ou apresentar um score quando essa configuração estiver
  incompleta.
- **FR-013**: Cada score MUST identificar os dados de entrada e critérios que
  contribuíram para o resultado, e MUST ser reprodutível para entradas e critérios
  idênticos.
- **FR-014**: Quando os dados necessários ao cálculo estiverem ausentes ou inválidos,
  o sistema MUST indicar a insuficiência e MUST NOT inventar ou apresentar um score
  válido.
- **FR-015**: Operadores MUST conseguir configurar um score CARIOCA mínimo por peer
  MISP autorizado para determinar elegibilidade de compartilhamento automático.
- **FR-016**: O sistema MUST compartilhar somente IOCs cujo score atinja o mínimo
  configurado e cuja distribuição seja permitida pelas regras de acesso e distribuição
  nativas do MISP; os demais MUST NOT ser enviados a esse peer.
- **FR-017**: O sistema MUST registrar o estado de cada tentativa de compartilhamento,
  expor falhas e permitir novas tentativas sem duplicar lógica ou silenciosamente
  descartar dados.
- **FR-018**: O sistema MUST proteger credenciais de MISP e MUST NOT expor segredos em
  saídas ou mensagens de erro.
- **FR-019**: Operadores MUST conseguir identificar o estado de coleta, normalização,
  scoring e compartilhamento, incluindo erros que exijam ação.
- **FR-020**: O sistema MUST documentar os termos canônicos do domínio definidos em
  Key Entities e MUST usar seus significados consistentemente nas especificações,
  documentação e mensagens destinadas aos operadores.
- **FR-021**: O significado das regras de scoring, candidatura a re-scoring e
  elegibilidade para compartilhamento MUST ser definido independentemente da forma
  como MISP representa ou transporta os dados; fontes MISP distintas com os mesmos
  dados de domínio MUST produzir as mesmas decisões de domínio.

### Key Entities *(include if feature involves data)*

- **Vocabulário do domínio**: Os nomes e definições das entidades abaixo são os
  termos canônicos usados neste projeto em requisitos, documentação e mensagens aos
  operadores.
- **IOC**: Indicador identificado pela combinação de tipo e valor normalizado,
  preservando o valor original e as observações de origem relacionadas.
- **Observação de origem**: Registro do indicador no contexto de origem, incluindo
  referência ao evento e UUID do atributo MISP, além dos dados necessários à avaliação.
- **Resultado de score**: Score calculado para um IOC, com os dados e critérios que
  explicam o resultado.
- **Candidato a re-scoring**: Estado persistente associado ao IOC lógico que indica
  se mudanças em dados de entrada usados pelo algoritmo exigem novo cálculo; uma
  alteração na observação de origem identifica os IOCs afetados por meio dessa relação.
- **Endpoint de coleta**: Fonte MISP consultada com uma cadência própria e um estado
  observável da última execução.
- **Peer MISP**: Destino autorizado de compartilhamento para o qual IOCs podem ser
  enviados.
- **Política de compartilhamento**: Score CARIOCA mínimo configurado por peer,
  aplicado em conjunto com as permissões e regras de distribuição nativas do MISP para
  determinar se um IOC pode ser enviado automaticamente.
- **Tentativa de compartilhamento**: Registro do envio, seu destino, estado e
  resultado, relacionado aos IOCs compartilhados.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em um conjunto de aceitação com indicadores suportados e casos de
  normalização definidos, 100% dos registros processados preservam o valor original,
  a representação normalizada e a referência de origem disponível.
- **SC-002**: Para 100% dos casos de referência aprovados do algoritmo, o resultado e
  os fatores explicativos correspondem aos valores esperados.
- **SC-003**: Para 100% dos resultados calculados, um analista consegue identificar
  os dados e critérios que contribuíram para o score.
- **SC-004**: Reprocessar a mesma entrada e repetir um compartilhamento concluído não
  cria duplicações lógicas.
- **SC-005**: Em testes com mudanças em parâmetros de scoring, 100% dos IOCs afetados
  ficam pendentes para re-scoring e os não afetados permanecem fora da fila.
- **SC-006**: Após a execução diária, 100% dos candidatos com dados estáveis e cálculo
  bem-sucedido têm score atualizado; candidatos com falha ou mudança concorrente
  continuam identificáveis como pendentes.
- **SC-007**: Em testes com indisponibilidade e recuperação de um peer, 100% dos
  envios pendentes permanecem identificáveis e podem ser retomados sem perda silenciosa.
- **SC-008**: Em testes de compartilhamento, 100% dos IOCs abaixo do mínimo de score
  ou não autorizados pelas regras do MISP não são enviados ao peer.
- **SC-009**: Em 100% dos fluxos cobertos por testes, as mensagens e documentação
  relacionadas ao domínio usam os termos canônicos com os significados registrados em
  Key Entities.
- **SC-010**: Para dados de domínio equivalentes recebidos de fontes MISP distintas,
  100% das decisões de scoring, re-scoring e elegibilidade para compartilhamento são
  iguais.

## Assumptions

- Os peers de compartilhamento são instâncias MISP autorizadas e configuradas pelos
  responsáveis pela operação.
- O score mínimo de compartilhamento é configurado explicitamente por peer; os
  controles nativos de autorização e distribuição do MISP continuam sendo aplicados.
- O compartilhamento descrito é de saída da instância local para peers; sincronização
  bidirecional não foi solicitada.
- As cadências dos endpoints são parâmetros operacionais configuráveis; valores e
  limites específicos serão definidos no planejamento ou implantação.
- O scoring é executado em uma rotina diária; não é necessário recalcular o score de
  forma síncrona durante a coleta.
- O estado de re-scoring representa dados de entrada pendentes, não uma alteração do
  score em si; gravar o resultado não deve reiniciar o ciclo de cálculo.
- A publicação CARIOCA indicada em FR-012 é a referência para as fórmulas definidas;
  parâmetros ausentes devem ser explicitamente configurados antes do scoring, e os
  casos de referência para verificação serão aprovados pelo projeto.
- A arquitetura e as tecnologias já estabelecidas pela Constituição do projeto serão
  detalhadas no planejamento sem alterar os resultados funcionais desta especificação.
