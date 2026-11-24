# Pesquisa técnica: Scoring e compartilhamento de IOCs

## Decisões

### Persistência: PostgreSQL

- **Decisão**: Usar PostgreSQL como banco relacional em um container próprio.
- **Racional**: Os serviços de coleta e scoring compartilham estado e podem persistir
  dados concorrentemente. PostgreSQL é cliente-servidor e oferece MVCC para leitores e
  escritores concorrentes. A escolha também corresponde à arquitetura declarada de
  três containers.
- **Alternativas consideradas**: SQLite simplifica uma implantação local pequena, mas
  permite apenas um escritor por vez e não é adequado para acesso concorrente por
  containers através de filesystem de rede. Pode ser reavaliado se o cenário passar a
  ser estritamente local e de baixa concorrência.
- **Fontes**: [SQLite: Appropriate Uses](https://www.sqlite.org/whentouse.html),
  [SQLite: Write-Ahead Logging](https://www.sqlite.org/wal.html#concurrency),
  [PostgreSQL: MVCC](https://www.postgresql.org/docs/current/mvcc-intro.html).

### Persistência relacional e validação de dados

- **Decisão**: SQLAlchemy 2.x para mapeamento e transações; Alembic para migrações;
  Pydantic para validar respostas/configurações nas fronteiras externas. Os modelos
  Pydantic não substituem o modelo do domínio.
- **Racional**: Esses componentes cobrem persistência, evolução do schema e validação
  de dados não confiáveis sem tornar uma biblioteca de análise tabular o modelo de
  dados primário. O núcleo do domínio permanece em regras Python independentes de
  SQLAlchemy e PyMISP.
- **Alternativas consideradas**: SQL direto é possível, mas aumenta o trabalho de
  mapeamento e migrações. pandas não será dependência inicial: seu uso só se justifica
  se a implementação do cálculo CARIOCA exigir operações tabulares vetorizadas.
- **Fontes**: [SQLAlchemy ORM Quick Start](https://docs.sqlalchemy.org/en/20/orm/quickstart.html#declare-models),
  [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/),
  [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html),
  [pandas overview](https://pandas.pydata.org/docs/getting_started/overview.html).

### Cliente MISP e integração de peers

- **Decisão**: Usar PyMISP como cliente da API REST para coleta e operações de
  integração. Para replicação a outros MISP, preferir o mecanismo nativo de sync de
  eventos publicados, com regras explícitas de push/distribution por peer.
- **Racional**: O cliente reduz duplicação de protocolo e a sincronização nativa mantém
  controles de distribuição, organização e compatibilidade próprios do MISP. O serviço
  deve confirmar jobs/estado do peer antes de registrar entrega como confirmada.
- **Alternativas consideradas**: Criar atributos diretamente no peer pode ser útil
  para fluxos não cobertos por sync, mas não será o caminho padrão de replicação.
  Chamadas de criação não devem ser repetidas às cegas após timeout ambíguo.
- **Fontes**: [PyMISP documentation](https://pymisp.readthedocs.io/en/latest/README.html),
  [MISP automation guide](https://www.circl.lu/doc/misp/automation/),
  [MISP sharing guide](https://www.circl.lu/doc/misp/sharing/).

### Coleta incremental e idempotência

- **Decisão**: Configurar cada endpoint MISP com frequência própria; buscar de forma
  síncrona em cada execução, paginar resultados e manter checkpoint da última janela
  integralmente processada. Aplicar sobreposição entre janelas, reconciliar por UUID
  e timestamp de modificação e avançar checkpoint somente após persistência completa.
- **Racional**: Um resultado de busca pode mudar enquanto é paginado. A sobreposição
  combinada com upsert/reconciliação evita lacunas e duplicações lógicas.
- **Alternativas consideradas**: Recoleta integral em toda execução é simples, mas
  aumenta custo e exposição a limites de API; depender apenas de IDs numéricos locais
  não funciona bem entre instâncias.
- **Fonte**: [MISP automation guide](https://www.circl.lu/doc/misp/automation/).

### Agendamento e execução síncrona

- **Decisão**: Um processo de coletor e um processo de scoring, cada um com scheduler
  único e jobs síncronos. Configurar intervalos por endpoint e uma execução diária de
  scoring; impedir sobreposição do mesmo job e registrar execução/checkpoint no banco.
- **Racional**: Atende às cadências declaradas sem adicionar broker ou serviço de
  agendamento independente. A persistência de execução permite recuperação e
  observabilidade após reinício.
- **Alternativas consideradas**: Um loop configurável também é possível, mas um
  scheduler com intervalos e agenda diária reduz lógica própria. Não compartilhar um
  job store do APScheduler 3.x entre réplicas; iniciar uma instância por worker.
- **Fonte**: [APScheduler 3.x user guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html),
  [APScheduler FAQ](https://apscheduler.readthedocs.io/en/3.x/faq.html#how-do-i-share-a-single-job-store-among-one-or-more-worker-processes).

### Modelo de domínio e testes

- **Decisão**: Manter regras puras de normalização, scoring, candidatura e
  elegibilidade no domínio/aplicação; isolar PyMISP e SQLAlchemy em adaptadores.
  Usar pytest; testar integrações de banco com PostgreSQL.
- **Racional**: Essa separação mantém linguagem ubíqua e decisões de domínio
  independentes do protocolo MISP, conforme FR-020/021 e a Constituição. Testes no
  mesmo banco da implantação revelam diferenças que SQLite em memória ocultaria.
- **Alternativas consideradas**: Dataframes e abstrações de DDD completas só serão
  introduzidos quando uma necessidade do algoritmo ou do domínio justificar esse custo.
- **Fontes**: [pytest good practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html),
  [pytest fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html).

### Algoritmo CARIOCA e parâmetros ausentes

- **Decisão**: Implementar as fórmulas publicadas; os parâmetros que a publicação não
  especifica ficam em configuração explícita, versionada e aprovada (FR-012). Não
  calcular score se a configuração estiver incompleta. As lacunas foram resolvidas nas
  clarificações de 2026-11-10 (ver abaixo).
- **Racional**: O artigo não especifica o suficiente para reprodução independente:
  FeedRank, estimador de σ das distribuições do CADE, escala do CADE e população
  ranqueada. Sem defaults silenciosos protege-se a reprodutibilidade.
- **Alternativas consideradas**: Valores provisórios sem aprovação foram rejeitados.
- **Fonte**: Delvecchio et al., “CARIOCA: prioritizing the use of IoC by threats
  assessment shared on the MISP platform”, *International Journal of Information
  Security* 24(2), 2025, [DOI](https://doi.org/10.1007/s10207-025-01006-2). Evidência
  empírica: experimentos do projeto sobre um MISP de estudos 2.5.51 (515.151 atributos,
  1.613 eventos, 27 organizações), registrados no Caderno de Projetos (Notion).

#### Fórmulas e critérios (publicação)

- `threat_level_id`: Undefined=0, Low=33, Medium=66, High=100.
- `analysis`: Initial=0, Ongoing=50, Complete=100.
- Categoria `i` de evento: `CategoryScore_i = (1 − PDF_i(N)) · 100`;
  `CADE = Σ β_i · CategoryScore_i` (16 categorias, β_i = 1/16 na configuração).
- `EventScore = 0,4·ThreatLevel + 0,2·StatusAnalysis + 0,4·CADE` (Tabela 4).
- Frescor: para `t < T_a`, `A(t) = (1 − (t/T_a)^(1/D_a))·100`; 0 caso contrário.
  HASH (2; 60 dias), IP (1,5; 7 dias), Domain (0,7; 365 dias). Tipos fora dos três
  grupos têm A = 0.
- Prioridade: MinMax e SPOTIS com ponto ideal 100 e pesos 1/3; com esses parâmetros
  `P = (S' + E' + A')/3`.

#### Decisões do projeto para as lacunas (clarificações 2026-11-10)

- **Densidade do CADE**: semi-normal normalizada para valer 1 em zero,
  `CS_i = (1 − e^(−n_i²/(2σ_i²)))·100`. Caso σ = 0: regra explícita na configuração.
- **σ**: estimador **robusto** a eventos extremos. Com o desvio-padrão populacional,
  σ(network activity) = 917 (a Fig. 3 do artigo sugere ≈ 1,4), o que anula eventos
  pequenos. Candidatos: limite no percentil 95 ou escala log; o limite no percentil 95
  dá σ = 0 em categorias raras, logo exige regra para esse caso. Método **ainda a
  decidir** (tarefa de pesquisa com dados reais).
- **Escala do CADE**: MinMax entre eventos (topo = 100, como a Tabela 5 do artigo). O
  valor 5,7994 da Tabela 6 não é reproduzível só com as equações publicadas.
- **FeedRank**: o MISP não registra o feed de origem; usa-se `orgc` como proxy. Cada
  par (tipo, valor em minúsculas) é creditado à organização que publicou primeiro
  (menor timestamp); o grafo dirigido "quem publicou depois aponta para quem publicou
  antes" (peso = pares em comum) recebe PageRank (0,85; 50 iterações); `V_o = 50·c_o·100
  + 50·MinMax(PR)_o`; `Source = MinMax(V_o)` entre organizações. Limitação: mede volume e
  pioneirismo, não qualidade.
- **População e seleção**: só IOCs de tipo com decaimento e não expirados (no artigo,
  510.516 IOCs válidos); top-N (20.000 no artigo, pela capacidade do IDS/IPS) combinado
  com limiar. O limiar absoluto sozinho é instável: com o mesmo MISP, 28 ou 61.757
  pares passaram de 70 conforme o filtro de coleta.
- **Coleta**: só `to_ids=true` (IOCs acionáveis, como no artigo). Atributos de contexto
  alteram Source, CADE e Event, então o resultado é sensível a essa escolha (a reportar
  como ameaça à validade).
- **Tempo**: o frescor usa `as_of`, não o relógio, para manter determinismo; sem feeds
  ativos a nota cai a cada dia.
- **Warninglists**: IOC mantém score, porém inelegível para compartilhamento. A
  pertinência usa igualdade exata, CIDR e hostname/subdomínio; regex e substring não são
  avaliados (evita custo e risco ao aplicar padrões externos a valores não confiáveis) e
  ficam registrados como não suportados.
- **Candidato a re-scoring**: só rastreabilidade. Como σ, MinMax e FeedRank dependem da
  população, reaproveitar resultados de IOCs não afetados não é seguro; o recálculo
  diário é sempre completo.
- **Configuração operacional**: peers e mínimos por variáveis de ambiente do container de
  scoring/sharing, aplicadas no reinício, com política efetiva registrada.
- **Indicadores rejeitados**: persistidos por origem e motivo (uma linha por atributo e
  motivo), sem criar IOC e sem repetir o valor bruto em logs; o operador lista e conta
  por motivo e origem.
- **Validade do score**: o compartilhamento usa a última execução bem-sucedida e suspende
  após 48 horas, evitando enviar IOCs com base em scores muito antigos sem parar tudo por
  uma falha isolada.
- **Dependência de desenvolvimento**: import-linter impõe as fronteiras entre módulos de
  forma automática no CI (necessidade: o monolito modular só é verificável com um
  verificador de imports); sem ele, as regras do plano seriam só convenção.
- **Observabilidade**: sem CLI, API nem UI. Um script exporta o banco para Excel (uma aba
  por tabela, mais uma aba de métricas calculadas) com papel de banco somente leitura. Por
  ser relatório, lê por reflexão e fica fora dos módulos. Excel limita cada aba a
  1.048.576 linhas, então há limite configurável sem truncar em silêncio. Valores de dados
  externos (por exemplo `raw_value` das rejeições) são escritos como texto e neutralizados
  contra interpretação como fórmula (princípio IV). Dependência nova: openpyxl, escolhida
  por escrever `.xlsx` sem precisar do Excel instalado.
- **Colunas secretas**: reflexão não sabe quais colunas são secretas, então a convenção é o
  comentário PostgreSQL `secret`, aplicada nos modelos e conferida por um teste de
  arquitetura que falha se uma coluna com nome sensível não tiver o comentário. O arquivo
  exportado é gravado com permissão 0600 e em modo somente-escrita do openpyxl.
- **Parâmetros temporais**: todos por variáveis de ambiente validadas na inicialização;
  mudar exige reiniciar o container.
- **Desempenho**: meta de 1 hora (SC-011) validada por benchmark; processamento em
  memória ou em SQL decidido com dados reais.
- A publicação trata o cálculo local como síncrono, mas o push de MISP é baseado em
  jobs: uma solicitação de publicação não confirma entrega ao peer. O estado de
  compartilhamento distingue envio solicitado, confirmado e desconhecido/falho.

## Síntese de implantação

O baseline recomendado é um container PostgreSQL, um worker de coleta/normalização e
um worker de scoring/compartilhamento, todos ligados pela mesma base persistente; o
código é um monolito modular (ver `plan.md`).
Parâmetros operacionais (cadências, endpoint, peers, limites de score e parâmetros
CARIOCA) são configuração versionada/identificável, não valores ocultos no código.

## Revisão 2026-11-24

Retomada de US2–US4 depois da coleta e da feature 002. Fonte principal das fórmulas e
dos casos de referência: página do Notion "CARIOCA — fórmulas e exemplos reais"
(contas executadas em 2026-11-10, ~18:11 UTC, sobre o MISP de estudos).

### Unidade de cálculo e agregação no IOC

- **Decisão**: calcular Source, Event e Attribute por observação de origem ativa com
  `to_ids=true`; o Resultado de score do IOC lógico é o da observação de maior
  prioridade (decisão do dono em 2026-11-24). Em empate, vence a observação mais antiga
  (`source_created_at`) e depois o menor `(source_instance_id, attribute_uuid)`.
- **Racional**: a referência trata "cada IoC = atributo MISP", que herda a `orgc` e o
  evento do atributo. Calcular por observação reproduz exatamente os casos de uma
  observação (por exemplo, `hotels-stays55501.com`). Agregar pelo máximo mantém o IOC
  lógico da 001 (FR-005) e evita que o mesmo valor ocupe várias posições do top-N.
- **Alternativas consideradas**: usar só a primeira publicação, coerente com o FeedRank
  mas que ignora eventos posteriores de melhor qualidade; ou ranquear por observação,
  fiel ao artigo mas que duplica valores no top-N e no envio. Ambas foram descartadas.
- **Consequência**: o corte do top-N do projeto não é diretamente comparável ao do
  Notion (top 20 mil atributos, corte 73,48 no cenário v3).

### URL e grupos de decaimento

- **Decisão**: `url` fica fora dos grupos de decaimento no CARIOCA e é excluída com
  motivo (decisão do dono em 2026-11-24). A lista de tipos por grupo é fechada e
  versionada na configuração, conforme a tabela do Notion §2.1.
- **Racional**: fidelidade ao artigo e à população de referência (271.100 válidos, todos
  `domain`). O decaimento de URL da 002 é uma regra do bloqueio simples, não do CARIOCA.
- **Consequência**: o Pi-hole no modo `carioca` só recebe domínios e hostnames; URLs
  continuam disponíveis pelo modo `default`.
- **Alternativa**: mapear `url` para o grupo domain; descartada por mudar a população e o
  MinMax sem respaldo do artigo.

### Filtro `to_ids` no scoring

- **Decisão**: o CARIOCA considera apenas observações `to_ids=true` em todos os
  componentes, independentemente de `MISP_TO_IDS_ONLY`.
- **Racional**: a 002 recomenda `MISP_TO_IDS_ONLY=false` para ter decisões de bloqueio
  sobre todos os atributos. Sem esse filtro no scoring, os atributos de contexto
  mudariam CADE, Event e Source, e o score dependeria da configuração da coleta.

### Normalizações

- **Decisão**: `CADE'` por MinMax entre todos os eventos com observação `to_ids` ativa;
  `E'` por MinMax entre os eventos com ao menos uma observação válida; `A'` e `S'` entre
  as observações válidas. Em qualquer MinMax com máximo = mínimo, o valor é 50.
- **Racional**: é o cenário "v2 + CADE MinMax + só válidos" do Notion (§3.1 e §5.2), que é
  a proposta v3 que o projeto implementa.
- **Referência para testes**: `hotels-stays55501.com` com CADE bruto 6,5218, CADE'
  19,544, E 31,017, E' 60,532, A 69,687, A' 66,984, S' 100 e P 75,838 (insumos da página,
  com `as_of` fixo).

### Leitura do snapshot da coleta

- **Decisão**: adicionar a `collection.api` uma leitura única, em transação
  `REPEATABLE READ`, que devolve observações ativas, revisões dos IOCs e entradas de
  warninglist suportadas. O casamento com warninglist é feito em memória, com índices por
  tipo (conjunto de valores exatos, árvore de sufixos de hostname e redes CIDR).
- **Racional**: hoje `active_iocs()` é chamada por `event_category_counts()` e
  `first_publications()`, o que lê a base três vezes em momentos diferentes (snapshot
  instável). Além disso, `warninglist_membership()` varre todas as entradas a cada IOC,
  o que dá O(IOCs × entradas). Com 270 mil IOCs isso compromete SC-011 e o determinismo.
- **Alternativa**: cálculo em SQL. Continua possível se o benchmark mostrar que a
  memória não basta; a decisão fica registrada no resultado do benchmark.

### PageRank sem dependência nova

- **Decisão**: PageRank por iteração de potência em Python puro (0,85; 50 iterações;
  tratamento explícito de nós sem saída distribuindo a massa uniformemente).
- **Racional**: o grafo tem a ordem de dezenas de organizações (27 no MISP de estudos),
  então não há ganho em adicionar networkx ou scipy. O tratamento de nós sem saída
  precisa ser explícito e testado, porque muda os valores. A versão da referência deve
  ser confirmada contra a tabela do Notion §4 (por exemplo, PageRank do CIRCL 0,40966).

### Pi-hole no modo `carioca`

- **Decisão**: com CARIOCA implementado, `PIHOLE_SCORE_MODEL=carioca` lê o score vigente
  por `scoring.api`, aplica `PIHOLE_CARIOCA_MIN_SCORE`, a validade de
  `SCORE_MAX_AGE_HOURS` e as regras estritas de warninglist e snapshot da 002, sem top-N.
  Sem configuração aprovada ou execução vigente, não envia nada e avisa o operador.

### Compartilhamento com peers MISP

- **Decisão**: o push nativo do MISP sincroniza eventos publicados, não atributos
  isolados. O adaptador mantém, na instância local de saída, um evento de saída por peer
  com os atributos elegíveis (UUIDs estáveis derivados do IOC e do peer). Publica esse
  evento e confia ao sync nativo a entrega, com distribuição e sharing group herdados da
  política. A confirmação vem da leitura do evento no peer pelo UUID.
- **Racional**: preserva os controles nativos (FR-016, contrato de compartilhamento) sem
  criar um segundo protocolo de replicação. UUIDs determinísticos tornam a repetição
  idempotente e permitem reconciliar timeouts ambíguos.
- **Distribuição por atributo**: o evento de saída leva a distribuição máxima da
  política do peer; cada atributo leva a distribuição efetiva da observação que o
  tornou elegível (ver "Distribuição no envio a peers"). Como o MISP aplica o menor
  valor entre evento e atributo, o atributo nunca sai mais amplo que a origem.
- **Pendência**: validar o desenho contra um MISP isolado com peer de sync (T075/T088)
  antes de ativar em produção. A conta de sync dedicada e as regras de push por peer são
  configuradas no MISP, não pelo projeto.

### Ajuste de DDD na mesma implementação

- **Decisão**: corrigir os desvios de DDD do código existente (etapas D1–D10 do plano)
  dentro desta implementação, ligando cada etapa à frente que depende dela: D1–D6 antes
  do CARIOCA, D7–D8 com os candidatos, D9 com os peers MISP e D10 no polimento.
- **Racional**: o CARIOCA, os candidatos e os peers MISP vão reutilizar exatamente as
  peças com problema: o snapshot da coleta, o matcher de warninglist, o decaimento, o
  `input_revision` e o molde de caso de uso do Pi-hole. Corrigir antes evita copiar o
  desvio para o código novo e evita duas versões da mesma regra.
- **Alternativas consideradas**: uma feature separada só de refatoração, depois da
  US2–US4, descartada porque o código novo nasceria sobre as peças erradas. Uma
  reescrita total da coleta e do Pi-hole, descartada por risco sem ganho de domínio.

### Refatoração com rede de segurança

- **Decisão**: escrever um teste de caracterização antes de D1. Sobre uma fixture fixa
  de observações, warninglists, rejeições e endpoints, com `as_of` fixo, ele grava as
  decisões de bloqueio e o conjunto desejado de hostnames do Pi-hole. Cada etapa deve
  manter esse resultado idêntico.
- **Racional**: a 002 está em produção, e a refatoração não pode mudar decisões. O
  teste compara o resultado inteiro, não só casos isolados.

### Tipos de domínio na API pública

- **Decisão**: `collection.api` e `scoring.api` devolvem dataclasses congeladas
  definidas no domínio do módulo dono; nunca modelos SQLAlchemy nem `RowMapping`. Um
  teste de arquitetura falha se uma função pública devolver instância de `Base`.
- **Racional**: o plano já proíbe a leitura entre módulos pelos modelos do outro; hoje
  `blocking_snapshot` viola isso e o import-linter não detecta, porque o import do
  modelo acontece dentro de `collection`.

### Enums e valores gravados

- **Decisão**: `StrEnum` para motivos de decisão e modelos de score, com os mesmos
  valores das strings atuais (`eligible`, `removed`, `type`, `to_ids`, `analysis`,
  `warninglist`, `expired`, `indeterminate`, `rejected`, `stale`; `default`,
  `carioca`).
- **Racional**: dá nome e checagem aos conceitos sem migration, porque o banco continua
  recebendo as mesmas strings; a view `decisao_bloqueio_efetiva` e a exportação não
  mudam.

### Nomes de tabelas

- **Decisão**: não renomear `pihole_policy`, `pihole_entry` e `pihole_attempt`.
  Tabelas novas seguem o português do plano. O glossário ganha a coluna "nome no
  código" para ligar termo, classe e tabela.
- **Racional**: renomear exige migration, muda as abas da exportação e não melhora o
  modelo; a ponte no glossário resolve a consistência de linguagem (princípio VI).

### Distribuição no envio a peers

- **Decisão** (clarificação 2026-11-24): um IOC é elegível para um peer se ao menos uma
  Observação de origem ativa vem de evento publicado e alcança o peer. A distribuição
  efetiva da observação é a menor entre a do atributo e a do evento (`5` = herda do
  evento). Ela alcança um peer de sync quando é `1` (esta comunidade), `2`
  (comunidades conectadas) ou `3` (todas as comunidades), ou quando é `4` (sharing
  group) e o servidor do peer pertence a esse sharing group. `0` (só a organização)
  nunca alcança. Entre as observações que alcançam, usa-se a de distribuição mais
  restritiva, com o mesmo desempate da agregação; o atributo de saída recebe essa
  distribuição e, se for `4`, o mesmo sharing group.
- **Racional**: atende à escolha do dono de não bloquear o envio por causa de uma
  origem restrita e, ao mesmo tempo, à FR-016, porque nenhum atributo sai com
  distribuição mais ampla que a da observação usada. Escolher a mais restritiva entre
  as permitidas é o menor alcance que ainda cumpre a regra.
- **Verificação pendente**: a semântica de push por nível (`1` e `2` rebaixados no
  destino; `4` só para servidores do sharing group) segue o guia de compartilhamento
  do MISP e deve ser confirmada no teste de contrato e no MISP isolado. A pertinência
  do peer a um sharing group é lida da instância local (sharing groups e seus
  servidores) no início de cada rodada.
- **Lacuna na coleta**: `observacao_origem` guarda só o `sharing_group_id` do atributo.
  A coleta passa a guardar também o do evento (`event_sharing_group_id`, migration
  `0011`); até a recoleta preencher o campo, a observação com distribuição herdada de
  um evento `4` é tratada como `0`, ou seja, não alcança o peer.
- **Alternativas consideradas**: exigir que todas as observações permitam (mais seguro,
  recusado pelo dono) e usar só a observação vencedora (ignora restrições das demais).

### Observação sem `orgc` ou não publicada

- **Decisão** (clarificação 2026-11-24): fica fora da população com motivo
  `missing_data` (sem `orgc`) ou `unpublished`; o IOC é excluído só se nenhuma outra
  observação for válida.
- **Racional**: o FeedRank só credita observações publicadas com `orgc`; dar Source 0
  inventaria um valor sem evidência (FR-014).

### Valores de referência em dois níveis

- **Decisão** (clarificação 2026-11-24): testes de fórmula recebem σ como entrada e
  conferem os números do Notion (σ populacional bruto, 917,29 em network activity). A
  SC-015 usa os valores recalculados com o estimador aprovado, que a avaliação de σ
  (`docs/sigma-estimator-evaluation.md`) publica com os mesmos casos
  (`hotels-stays55501.com` e evento 19) e que o dono aprova junto com o estimador.
- **Racional**: os números do Notion vêm do estimador que a FR-023 proíbe como padrão;
  sem o segundo nível, o estimador aprovado ficaria sem verificação de ponta a ponta.

### Composição nos entrypoints

- **Decisão**: os casos de uso são chamados pelos entrypoints, que montam os
  adaptadores de infraestrutura. A infraestrutura implementa portas e não importa
  `application`, e o contrato import-linter correspondente vale nos três módulos.
- **Racional**: a análise de 2026-11-24 mostrou que o plano anterior deixava
  `simple_blocking.run`, o job CARIOCA e o `scheduler.sync` chamando a aplicação a
  partir da infraestrutura, o que quebraria o próprio contrato do ajuste D8. Os
  entrypoints já são, pelo plano, a única camada autorizada a conhecer tudo.

### Benchmark do CARIOCA (SC-011)

- **Decisão**: cálculo em memória, em Python puro, sobre o `CollectionSnapshot` lido numa
  transação `REPEATABLE READ`; gravação em lotes de 1.000 linhas.
- **Evidência** (2026-11-24, `tests/benchmark/test_scoring_performance.py`, com
  `RUN_BENCHMARK=true`): população sintética de 283.500 observações e 269.787 IOCs
  válidos (27 organizações, duas com cerca de 92% dos pares, 1.600 eventos com tamanhos
  em Pareto). O `calculate` levou 10,3 s; o cálculo com a gravação no PostgreSQL 16 local
  levou 42,6 s, contra a meta de 1 hora.
- **Pendência**: a conferência da tabela de fontes do Notion §4 (CIRCL S' 100;
  CthulhuSPRL.be 59,92; Krawczyk 47,05; PageRank do CIRCL 0,40966) exige
  `BENCHMARK_DATABASE_URL` com uma cópia do MISP de estudos, que não está no repositório.
- **Alternativa**: cálculo em SQL, descartado enquanto a memória couber com folga.

### Formato da configuração CARIOCA

- **Decisão**: `config/carioca-orgc-proxy-v3.yaml` é YAML escrito no subconjunto JSON
  (todo JSON é YAML 1.2 válido), com comentários só no cabeçalho, e é lido com `json`
  da biblioteca padrão.
- **Racional**: o projeto não tem dependência de YAML, e a Constituição V pede não
  adicionar dependência sem necessidade. O `content_hash` é calculado sobre o conteúdo
  canônico (chaves ordenadas), então comentários e formatação não o mudam.
- **Alternativa**: adicionar PyYAML; fica para o dono decidir se o YAML livre for
  necessário.
