# Feature Specification: Plataforma de Scoring e Compartilhamento de IOCs

**Feature Branch**: `001-misp-ioc-scoring`

**Created**: 2026-11-09

**Status**: Draft

**Input**: User description: "Coletar e normalizar dados do MISP, persistir os dados necessários ao scoring Carioca, calcular e compartilhar IOCs com peers MISP, com coleta síncrona em cadências próprias por endpoint e recálculo diário dos scores de toda a população de IOCs válidos, com rastreabilidade dos IOCs cujos dados de entrada mudaram."

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
- Q: Como o scoring diário deve recalcular os scores: só os IOCs candidatos ou toda a
  população de IOCs válidos? → A: Recalcular diariamente toda a população de IOCs
  válidos com uma data de referência (`as_of`) registrada.
- Q: Qual conjunto de IOCs deve entrar na população ranqueada e na normalização do
  score? → A: Somente IOCs de tipo suportado (com grupo de decaimento) e não expirados
  (score de frescor maior que 0); os demais não recebem score válido nem entram nos
  mínimos e máximos da normalização.
- Q: Como escolher quais IOCs são aprovados para compartilhamento: limiar absoluto,
  top-N ou ambos? → A: Ambos: o IOC deve estar entre os N maiores scores (N
  configurável, valor explícito e aprovado) e atingir o score mínimo configurado do
  peer.
- Q: Como estimar o desvio-padrão (σ) de cada categoria do CADE, que o artigo não
  especifica? → A: Usar um estimador robusto a eventos extremos (limitar a contagem ao
  percentil 95 ou usar escala logarítmica), com método, versão e tratamento do caso
  σ = 0 registrados na configuração CARIOCA e aprovados antes da ativação.
- Q: O CADE deve ser normalizado por MinMax entre os eventos? → A: Sim; o CADE bruto
  de cada evento é normalizado por MinMax entre todos os eventos (0 a 100) antes de
  entrar no Event score, e essa normalização é registrada na configuração CARIOCA.
- Q: O Source score deve usar a organização criadora do evento (`orgc`) como proxy do
  feed, com FeedRank sobre essas organizações? → A: Sim; a organização que primeiro
  publicou cada par (tipo, valor) recebe a contribuição, um grafo dirigido
  (quem publicou depois aponta para quem publicou antes) recebe PageRank com
  amortecimento 0,85, e o valor da fonte combina 50% de contribuição e 50% de
  PageRank, ambos normalizados por MinMax. É uma limitação conhecida, versionada na
  configuração CARIOCA, a ser substituída quando o feed de origem estiver disponível.
- Q: A coleta deve trazer só atributos acionáveis (`to_ids=true`) ou todos? → A: Só
  `to_ids=true` por padrão, configurável por endpoint; atributos que deixam de atender
  ao filtro são marcados como removidos na reconciliação, com trava contra remoção em
  massa.
- Q: IOCs em warninglist habilitada do MISP devem ser excluídos do compartilhamento?
  → A: Sim; o IOC mantém seu score, mas é inelegível para compartilhamento, com o
  motivo registrado.
- Q: Qual o papel do estado de candidato a re-scoring, dado o recálculo diário da
  população completa? → A: Apenas rastreabilidade: o candidato indica que os dados de
  entrada do IOC mudaram desde o último score bem-sucedido e permanece pendente até um
  recálculo bem-sucedido; o recálculo diário não depende dele e não reaproveita
  resultados de IOCs não afetados.
- Q: Como decidir que um IOC consta em uma warninglist? → A: Por igualdade exata do
  valor normalizado, por CIDR para IPs e por hostname/subdomínio para domínios;
  entradas de tipo regex ou substring não são avaliadas e ficam registradas como não
  suportadas.
- Q: Como o operador configura os peers MISP e o score mínimo de cada um? → A: Pelas
  variáveis de ambiente do container de scoring/compartilhamento (peers, score mínimo
  por peer e credenciais como referências a segredos), lidas na inicialização; qualquer
  alteração exige editar o ambiente e reiniciar esse container.
- Q: Qual o tempo máximo aceitável para o scoring diário recalcular toda a população
  de IOCs válidos? → A: Até 1 hora, medido em benchmark com dados representativos
  (ordem de 270 mil IOCs válidos).
- Q: O que o scoring diário faz com população vazia ou com valores todos iguais na
  normalização? → A: População vazia: a execução conclui sem scores e com aviso ao
  operador. Valores todos iguais (máximo = mínimo): o componente normalizado vale 50,
  com a ocorrência registrada na explicação do score.
- Q: Onde registrar indicadores inválidos ou de tipo não suportado? → A: Em um registro
  persistente de rejeições na coleta, com origem (instância, evento, atributo), valor
  bruto, tipo MISP, motivo (inválido ou não suportado) e momento; a rejeição não cria
  IOC e o registro é consultável por contagem e listagem.
- Q: Qual execução de scoring os envios aos peers usam e por quanto tempo ela vale? →
  A: A última execução concluída com sucesso, válida por até 48 horas; acima disso o
  compartilhamento é suspenso e o operador é avisado.
- Q: Como o operador observa o sistema, e quais interfaces existem? → A: Não há CLI, API
  nem interface de usuário. Tempos e frequências vêm de variáveis de ambiente dos
  containers (aplicadas ao reiniciar). A observabilidade é um script que exporta o banco
  para uma planilha Excel, uma aba por tabela, com uma aba de métricas calculadas; os
  avisos ao operador são eventos de log estruturado de nível WARNING com registro
  persistido, visíveis nessa exportação.

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
5. **Given** um IOC de tipo sem grupo de decaimento ou já expirado (score de frescor
   igual a 0), **When** o scoring diário é executado, **Then** ele não entra na
   população válida, não influencia a normalização e não recebe score válido, mas o
   motivo da exclusão fica identificável.
6. **Given** a execução diária de scoring, **When** ela é iniciada, **Then** os scores
   de toda a população de IOCs válidos são recalculados com uma data de referência
   (`as_of`) única e registrada, mesmo para IOCs sem alteração nos dados de entrada.

---

### User Story 3 - Rastrear IOCs com dados de entrada alterados (Priority: P2)

Como analista, quero que um IOC seja marcado para novo scoring quando um dado usado
pelo algoritmo Carioca mudar, para que o score armazenado não fique desatualizado e
possa ser reavaliado na próxima execução diária.

**Why this priority**: A relação explícita entre mudanças nos dados de entrada e
o último score bem-sucedido torna visível qualquer IOC cujo score ainda não reflete
seus dados atuais; o recálculo diário da população completa continua sendo o que
atualiza os scores.

**Independent Test**: Alterar um campo usado pelo algoritmo e confirmar que somente
os IOCs relacionados ficam pendentes; executar o scoring diário e confirmar que todos
os scores são recalculados e que os candidatos cujo cálculo foi bem-sucedido sobre a
revisão vigente deixam de estar pendentes.

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
4. **Given** um IOC cujo score está abaixo do mínimo configurado para o peer, fora
   do top-N da execução vigente, presente em warninglist habilitada ou cuja
   distribuição não é autorizada pelo MISP, **When** o compartilhamento é executado,
   **Then** o IOC não é enviado a esse peer.
5. **Given** que a última execução de scoring concluída com sucesso é mais antiga que
   a validade configurada (48 horas por padrão), **When** o compartilhamento é executado, **Then** nenhum IOC é enviado, o
   operador é avisado e os envios retomam após uma nova execução bem-sucedida.

### Edge Cases

- Um evento não contém os atributos opcionais esperados ou contém campos conflitantes.
- A população válida está vazia ou todos os valores de um componente são iguais na
  normalização.
- Uma reconciliação marcaria atributos como removidos acima do limite configurado.
- Uma warninglist contém entradas de tipo não suportado para avaliação.
- O top-N configurado é maior que o número de IOCs válidos.
- O scoring diário falha e os scores disponíveis ficam mais antigos que a validade
  configurada (48 horas por padrão).
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
  convertê-los silenciosamente em indicadores válidos, e MUST registrar cada rejeição de
  forma persistente com origem (instância, evento, atributo), valor bruto, tipo MISP,
  motivo (inválido ou não suportado) e momento, sem criar IOC; o operador MUST conseguir
  listar e contar as rejeições por motivo e por origem por meio da exportação de
  observabilidade (FR-028).
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
  síncrona diária dos scores de toda a população de IOCs válidos, usando os dados mais
  recentes disponíveis e uma única data de referência (`as_of`) registrada em cada
  execução e em cada score, porque a normalização entre IOCs e o frescor dependem da
  população e da data. O recálculo MUST NOT reaproveitar resultados de execuções
  anteriores nem depender do estado de candidato a re-scoring.
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
  MISP autorizado para determinar elegibilidade de compartilhamento automático. Peers e
  mínimos MUST vir das variáveis de ambiente do container de scoring/compartilhamento,
  lidas na inicialização, com credenciais apenas como referências a segredos; uma
  alteração só passa a valer após reiniciar esse container. A configuração ausente ou
  inválida (por exemplo, mínimo fora de 0–100) MUST impedir o início do
  compartilhamento com erro explícito, e a política efetiva carregada MUST ser
  registrada a cada inicialização para que cada tentativa de compartilhamento remeta à
  política avaliada.
- **FR-016**: O sistema MUST compartilhar somente IOCs cujo score atinja o mínimo
  configurado, que estejam entre os N maiores scores válidos da execução vigente (N
  configurável explicitamente, sem valor padrão implícito) e cuja distribuição seja
  permitida pelas regras de acesso e distribuição nativas do MISP; os demais MUST NOT
  ser enviados a esse peer. A "execução vigente" MUST ser a última execução de scoring
  concluída com sucesso; se ela tiver mais do que a validade configurada (48 horas por
  padrão, FR-029), o compartilhamento MUST ser suspenso com aviso ao operador, e novos
  envios só ocorrem após uma execução bem-sucedida.
- **FR-017**: O sistema MUST registrar o estado de cada tentativa de compartilhamento,
  expor falhas e permitir novas tentativas sem duplicar lógica ou silenciosamente
  descartar dados.
- **FR-018**: O sistema MUST proteger credenciais de MISP e MUST NOT expor segredos em
  saídas ou mensagens de erro.
- **FR-019**: Operadores MUST conseguir identificar o estado de coleta, normalização,
  scoring e compartilhamento, incluindo erros que exijam ação, por meio dos logs
  estruturados e da exportação de observabilidade (FR-028).
- **FR-020**: O sistema MUST documentar os termos canônicos do domínio definidos em
  Key Entities e MUST usar seus significados consistentemente nas especificações,
  documentação e mensagens destinadas aos operadores.
- **FR-021**: O significado das regras de scoring, candidatura a re-scoring e
  elegibilidade para compartilhamento MUST ser definido independentemente da forma
  como MISP representa ou transporta os dados; fontes MISP distintas com os mesmos
  dados de domínio MUST produzir as mesmas decisões de domínio.
- **FR-022**: A população válida, ranqueada e usada na normalização MinMax, MUST conter somente
  IOCs de tipo suportado pelo algoritmo e não expirados (score de frescor maior que 0);
  IOCs fora dessa população MUST NOT receber score válido e MUST ter o motivo da
  exclusão registrado.
- **FR-023**: O CADE MUST usar uma estimativa de σ por categoria robusta a eventos
  extremos, cujo método, versão e tratamento do caso σ = 0 (comum em categorias raras)
  sejam parte da configuração CARIOCA aprovada; o desvio-padrão populacional bruto
  MUST NOT ser usado como padrão implícito.
- **FR-024**: O CADE de cada evento MUST ser normalizado por MinMax entre todos os
  eventos da execução (0 a 100) antes de compor o Event score; a normalização MUST
  constar da configuração CARIOCA versionada e do score explicado. Em qualquer
  normalização MinMax, se todos os valores forem iguais (máximo = mínimo), o valor
  normalizado MUST ser 50 e a ocorrência MUST constar da explicação do score; se a
  população válida estiver vazia, a execução MUST concluir sem scores e emitir aviso ao
  operador.
- **FR-025**: Enquanto a origem do feed não estiver disponível, o Source score MUST
  usar a organização criadora do evento como proxy da fonte: a primeira organização
  a publicar cada par (tipo, valor normalizado) recebe a contribuição; um grafo
  dirigido (quem publicou depois aponta para quem publicou antes, peso igual ao número
  de pares em comum) recebe PageRank com amortecimento 0,85; o valor da fonte MUST
  combinar 50% da fração de contribuição e 50% do PageRank normalizado por MinMax, e o
  Source score MUST ser o MinMax desse valor entre as organizações. O método e sua
  versão MUST constar da configuração CARIOCA, e a limitação (proxy no lugar do feed)
  MUST ser exposta na explicação do score.
- **FR-026**: A coleta MUST trazer por padrão apenas atributos marcados como acionáveis
  (`to_ids=true`), com esse filtro configurável por endpoint. Atributos que deixarem de
  atender ao filtro (inclusive por mudança de configuração) MUST ser marcados como
  removidos na reconciliação, preservando a proveniência, e a reconciliação MUST
  recusar uma remoção em massa acima de um limite configurado, sinalizando o erro ao
  operador.
- **FR-027**: Um IOC presente em warninglist habilitada do MISP MUST manter seu score
  e MUST ser inelegível para compartilhamento com qualquer peer, com o motivo da
  inelegibilidade registrado e visível ao operador. A pertinência MUST ser avaliada
  por igualdade exata do valor normalizado, por CIDR para IPs e por hostname/subdomínio
  para domínios; entradas de warninglist de tipo regex ou substring MUST NOT ser
  avaliadas, e cada entrada ignorada MUST ficar registrada como não suportada e visível
  ao operador.
- **FR-028**: O sistema MUST oferecer um script de observabilidade que exporta o banco
  para uma planilha Excel, com uma aba por tabela de todos os módulos e uma aba de
  métricas calculadas pelo próprio script (contagens por tabela, rejeições por motivo e
  por origem, última execução de coleta e de scoring, população válida e excluída por
  motivo, candidatos pendentes, tentativas de compartilhamento por estado, avisos ativos
  e se o compartilhamento está suspenso). O script MUST ser somente leitura, MUST NOT
  incluir segredos (colunas de credencial ou referência a segredo são identificadas por
  convenção no esquema e nunca exportadas), MUST gravar o arquivo com permissão restrita
  ao usuário que o gerou, MUST neutralizar valores não confiáveis para que não sejam
  interpretados como fórmula, MUST NOT truncar silenciosamente abas acima do limite de
  linhas configurado (a aba indica o truncamento e a aba de métricas traz o total), e
  não há CLI, API nem interface de usuário além dele. Cada "aviso ao operador" neste
  documento é um evento de log estruturado de nível WARNING com registro persistido,
  visível nessa exportação.
- **FR-029**: Todos os tempos e frequências operacionais (cadência de coleta por
  endpoint, frequência do scoring diário, janelas de sobreposição, tentativas e
  esperas, validade do score para compartilhamento, limite de linhas por aba da
  exportação) MUST vir de variáveis de ambiente dos containers, validadas na
  inicialização; valores ausentes ou inválidos MUST impedir o início do serviço com erro
  explícito, e mudanças só valem após reiniciar o container. A validade do score tem
  padrão de 48 horas. O limite de linhas por aba da exportação tem padrão de 1.000.000 e
  teto de 1.048.575 (limite do formato menos o cabeçalho); valores acima do teto MUST
  ser recusados.

### Key Entities *(include if feature involves data)*

- **Vocabulário do domínio**: Os nomes e definições das entidades abaixo são os
  termos canônicos usados neste projeto em requisitos, documentação e mensagens aos
  operadores.
- **IOC**: Indicador identificado pela combinação de tipo e valor normalizado,
  preservando o valor original e as observações de origem relacionadas.
- **Rejeição de indicador**: Registro de um indicador inválido ou não suportado recebido
  do MISP, com origem, valor bruto, tipo MISP, motivo e momento; não é um IOC.
- **Observação de origem**: Registro do indicador no contexto de origem, incluindo
  referência ao evento e UUID do atributo MISP, além dos dados necessários à avaliação.
- **Configuração CARIOCA**: Conjunto versionado e aprovado de parâmetros (pesos, σ,
  normalização, FeedRank, top-N e mapeamentos) que cada score referencia.
- **População válida**: IOCs de tipo suportado e não expirados que entram na
  normalização e no ranking de uma execução.
- **Execução de scoring**: Recálculo diário com data de referência (`as_of`), estado e
  avisos; a **execução vigente** é a última concluída com sucesso.
- **Estatísticas de população**: Valores calculados por execução (σ por categoria,
  mínimos e máximos, valor por organização).
- **Exclusão de score**: Motivo pelo qual um IOC ativo não está na população válida.
- **Entrada de warninglist**: Valor de uma warninglist habilitada, com tipo e indicação
  de suporte para avaliação.
- **Resultado de score**: Score calculado para um IOC, com os dados e critérios que
  explicam o resultado.
- **Candidato a re-scoring**: Registro de rastreabilidade associado ao IOC lógico que
  indica que seus dados de entrada mudaram desde o último score bem-sucedido; permanece
  pendente até um recálculo bem-sucedido sobre a revisão vigente. Não determina quais
  IOCs são pontuados.
- **Endpoint de coleta**: Fonte MISP consultada com uma cadência própria e um estado
  observável da última execução.
- **Peer MISP**: Destino autorizado de compartilhamento para o qual IOCs podem ser
  enviados.
- **Política de compartilhamento**: Score CARIOCA mínimo configurado por peer, aplicado
  junto com o limite top-N e com as permissões e regras de distribuição nativas do MISP
  para determinar se um IOC pode ser enviado automaticamente.
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
- **SC-005**: Em testes com mudanças em campos de entrada do algoritmo, 100% dos IOCs
  afetados ficam pendentes como candidatos a re-scoring e os não afetados permanecem
  fora dessa lista.
- **SC-006**: Após a execução diária, 100% dos IOCs válidos têm score calculado com a
  mesma data de referência (`as_of`) e 100% dos candidatos com dados estáveis e cálculo
  bem-sucedido deixam de estar pendentes; candidatos com falha ou mudança concorrente
  continuam identificáveis como pendentes.
- **SC-007**: Em testes com indisponibilidade e recuperação de um peer, 100% dos
  envios pendentes permanecem identificáveis e podem ser retomados sem perda silenciosa.
- **SC-008**: Em testes de compartilhamento, 100% dos IOCs abaixo do mínimo de score,
  fora do top-N, presentes em warninglist habilitada ou não autorizados pelas regras do
  MISP não são enviados ao peer.
- **SC-009**: Em 100% dos fluxos cobertos por testes, as mensagens e documentação
  relacionadas ao domínio usam os termos canônicos com os significados registrados em
  Key Entities.
- **SC-010**: Para dados de domínio equivalentes recebidos de fontes MISP distintas,
  100% das decisões de scoring, re-scoring e elegibilidade para compartilhamento são
  iguais.
- **SC-011**: Em um benchmark com dados representativos (ordem de 270 mil IOCs
  válidos), a execução diária de scoring conclui o recálculo da população completa em
  até 1 hora.
- **SC-012**: Executando o script de observabilidade sobre um banco de teste, 100% das
  tabelas aparecem como abas, a aba de métricas traz os valores esperados dos cenários
  de teste, nenhum valor não confiável é interpretado como fórmula e nenhum segredo
  aparece na planilha.
- **SC-013**: Em um conjunto de teste, 100% dos indicadores inválidos ou não suportados
  geram exatamente uma rejeição por origem e motivo, nenhum vira IOC, e recoletar o mesmo
  conjunto não duplica rejeições.
- **SC-014**: Com o último scoring bem-sucedido mais antigo que a validade configurada,
  0 IOCs são enviados e o aviso fica registrado; após uma nova execução bem-sucedida, os
  envios retomam.
- **SC-015**: Com o estimador de σ aprovado, o CADE dos eventos de referência coincide
  com os valores esperados; sem estimador aprovado, nenhum score é gerado.
- **SC-016**: O Source score das organizações de referência coincide com os valores
  esperados (primeiro a publicar, PageRank e MinMax).
- **SC-017**: Com o filtro de acionabilidade ativo, 100% dos atributos sem `to_ids`
  ficam fora da coleta, e uma reconciliação acima do limite configurado é recusada sem
  avançar o checkpoint.

## Assumptions

- Não há CLI, API nem interface de usuário nesta feature; a operação é feita por
  variáveis de ambiente e a observação pela exportação de observabilidade (FR-028).
- Os peers de compartilhamento são instâncias MISP autorizadas e configuradas pelos
  responsáveis pela operação.
- O score mínimo de compartilhamento é configurado explicitamente por peer, via
  ambiente do container de scoring/compartilhamento e aplicado após reinício; os
  controles nativos de autorização e distribuição do MISP continuam sendo aplicados.
- O compartilhamento descrito é de saída da instância local para peers; sincronização
  bidirecional não foi solicitada.
- As cadências dos endpoints são parâmetros operacionais configuráveis; valores e
  limites específicos serão definidos no planejamento ou implantação.
- O scoring é executado em uma rotina diária que recalcula toda a população de IOCs
  válidos; não é necessário recalcular o score de forma síncrona durante a coleta.
- O estado de re-scoring é rastreabilidade de dados de entrada alterados desde o último
  score bem-sucedido, não uma alteração do score em si nem uma otimização do cálculo;
  gravar o resultado não deve reiniciar o ciclo.
- A publicação CARIOCA indicada em FR-012 é a referência para as fórmulas definidas;
  parâmetros ausentes devem ser explicitamente configurados antes do scoring, e os
  casos de referência para verificação serão aprovados pelo projeto.
- A arquitetura e as tecnologias já estabelecidas pela Constituição do projeto serão
  detalhadas no planejamento sem alterar os resultados funcionais desta especificação.
