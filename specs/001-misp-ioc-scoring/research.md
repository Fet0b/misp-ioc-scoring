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
