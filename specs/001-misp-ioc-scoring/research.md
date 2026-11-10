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

- **Decisão**: Implementar as fórmulas e mapeamentos publicados; armazenar configuração
  explícita e versionada para os parâmetros ausentes. Não calcular score se a
  configuração necessária estiver incompleta.
- **Racional**: O artigo não especifica parâmetros suficientes para reprodução
  independente, incluindo a fórmula/parametrização do FeedRank, o método de ajuste das
  distribuições por categoria, pesos padrão de categorias/eventos e alguns casos de
  valores ausentes. Não definir defaults silenciosos protege a reprodutibilidade.
- **Alternativas consideradas**: Valores provisórios do projeto poderiam ser usados
  apenas após aprovação explícita e registro de versão; não são adotados por esta
  decisão.
- **Fonte**: Delvecchio et al., “CARIOCA: prioritizing the use of IoC by threats
  assessment shared on the MISP platform”, *International Journal of Information
  Security* 24(2), 2025, [DOI](https://doi.org/10.1007/s10207-025-01006-2).

#### Fórmulas e critérios identificados na publicação

- `threat_level_id`: Undefined=0, Low=33, Medium=66, High=100.
- `analysis`: Initial=0, Ongoing=50, Complete=100.
- Para categoria de evento `i`, `CategoryScore_i = (1 - PDF_i(N)) * 100`;
  `CADE = Σ β_i * CategoryScore_i`, com pesos configuráveis que somam 1.
- `EventScore = α₁ * ThreatLevel + α₂ * StatusAnalysis + α₃ * CADE`, com pesos não
  negativos que somam 1.
- Frescor do atributo: para `t < T_a`,
  `AttributeScore(t) = (1 - (t/T_a)^(1/D_a)) * 100`, e score 0 em `t >= T_a`.
  A tabela do artigo fornece HASH (`D_a=2`, `T_a=60` dias), IP (`D_a=1.5`,
  `T_a=7` dias) e Domain (`D_a=0.7`, `T_a=365` dias).
- A prioridade final combina FeedRank, EventScore e AttributeScore via normalização
  MinMax e SPOTIS, com pesos iguais no artigo; transforma a distância em score
  `PriorityScore = (1 - SPOTIS(eval(IoC))) * 100`, em que maior é mais relevante.
- CADE usa categorias de atributos MISP e distribuições de frequência por categoria.
  A distribuição deve ser recalculada/atualizada quando a base MISP usada na calibração
  mudar, conforme estratégia explícita e versionada.
- O artigo não especifica a regra de publicação do score de volta ao MISP. A política
  deste projeto exige score mínimo configurável por peer e continua sujeita às
  permissões e regras nativas de distribuição do MISP.
- A publicação trata o cálculo local como síncrono, mas a sincronização push de MISP é
  baseada em jobs: uma solicitação de publicação não confirma entrega ao peer. O
  estado de compartilhamento precisa distinguir envio solicitado, confirmado e
  desconhecido/falho.

## Síntese de implantação

O baseline recomendado é um container PostgreSQL, um worker de coleta/normalização e
um worker de scoring/compartilhamento, todos ligados pela mesma base persistente.
Parâmetros operacionais (cadências, endpoint, peers, limites de score e parâmetros
CARIOCA) são configuração versionada/identificável, não valores ocultos no código.
