# Contrato: superfície de leitura dos scores CARIOCA

Revisão 2026-11-24. É a única forma de `sharing` (peers MISP e Pi-hole `carioca`) ler
scores. Fica em `misp_ioc_scoring/scoring/api.py`, ao lado das funções de bloqueio
simples já existentes (`blocking_decision`, `effective_blocks`). Pelo ajuste de DDD
(D5), essas duas passam a devolver `BlockingDecision` em vez de `RowMapping`, com os
mesmos campos e a mesma semântica.

## Execução vigente

`current_carioca_run(session) -> CariocaRun | None`

- Devolve a última `execucao_scoring` com estado `completed`: `id`, `as_of`,
  `finished_at`, `configuration_version`, `configuration_hash`, `top_n` e `warnings`.
- Devolve `None` se nunca houve execução bem-sucedida. Execuções falhas ou em andamento
  nunca são devolvidas.
- Quem chama compara `finished_at` com `SCORE_MAX_AGE_HOURS`; acima do limite, não envia
  nada e registra a suspensão. A API não decide a política.

## Scores da execução vigente

`carioca_scores(session, run_id, *, min_score=None, top_n_only=False) -> Iterator[CariocaScore]`

- Cada item tem `ioc_id`, `type`, `normalized_value`, `priority_score` (0–100),
  `rank`, `in_top_n`, `input_revision`, `as_of` e a observação vencedora
  (`source_instance_id`, `attribute_uuid`). A distribuição não vem daqui: `sharing`
  lê as observações do IOC por `collection.api` para aplicar a regra de distribuição.
- `min_score` filtra `priority_score >= min_score`; `top_n_only` filtra `in_top_n`.
- A ordem é por `rank` crescente; a iteração é paginada para não carregar a população
  inteira em memória.
- Só devolve scores válidos. IOCs excluídos não aparecem; os motivos ficam em
  `exclusions(session, run_id)`.

## Explicação

`explain(session, run_id, ioc_id) -> ScoreExplanation | None`

- Componentes brutos e normalizados da observação vencedora, σ das categorias do evento,
  componentes em que o MinMax foi degenerado, número de observações avaliadas, versão da
  configuração e a limitação do proxy `orgc` no lugar do feed. Usa os termos do
  glossário de domínio.

## Garantias

- Somente leitura; nenhuma função grava.
- Os tipos devolvidos são dataclasses imutáveis do próprio `scoring`; nunca modelos
  SQLAlchemy.
- Valores de indicador são dados não confiáveis: quem chama não os interpola em logs.
- O teste de arquitetura impede `sharing` de importar qualquer coisa de `scoring` além
  de `scoring.api`.
