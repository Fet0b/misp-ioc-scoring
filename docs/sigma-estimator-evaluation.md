# Avaliação do estimador de σ do CADE (FR-023)

**Estado**: proposta, **não aprovada**. A `config/carioca-orgc-proxy-v3.yaml` fica com
`approved: false` até o dono aprovar este documento. Sem essa aprovação,
`SCORING_CARIOCA_ENABLED=true` faz o serviço falhar na inicialização com
`CARIOCA_CONFIGURATION_NOT_APPROVED`.

## Por que σ precisa de decisão

O CADE usa `CS_i = (1 − e^(−n_i²/(2σ_i²)))·100`. Com o desvio-padrão populacional
bruto, σ(network activity) = 917,29 no MISP de estudos, por causa dos eventos Maltrail
com até 17.093 atributos de rede. Com esse σ, eventos pequenos ficam com CADE perto de
zero e qualquer categoria com milhares de atributos satura (página do Notion
"CADE — fórmulas e exemplos reais", §3 e §6).

## Estimadores implementados

Todos estão em `scoring/domain/cade.py` e são escolhidos pela configuração
(`sigma.method`, `sigma.version` e `sigma.zero_rule`):

| `method` | σ da categoria | Observação |
|---|---|---|
| `population_std` | desvio-padrão populacional de `n_i` entre os eventos do escopo `cade` (zeros contam) | Reproduz o Notion; é o estimador que a FR-023 rejeita como padrão |
| `p95_winsorized` | desvio-padrão populacional depois de limitar `n_i` ao percentil 95 (interpolação linear) | Dá σ = 0 nas 9 categorias raras do MISP de estudos |
| `log_std` | desvio-padrão populacional de `ln(1 + n_i)`; o `CS_i` usa `ln(1 + n_i)` | Comprime os eventos gigantes sem zerar categorias raras |

Regra para σ = 0 (`zero_rule`), sempre explícita:

- `indicator`: `CS_i = 0` com `n_i = 0` e 100 com `n_i > 0`;
- `half`: 0 ou 50 (regra do protótipo anterior, citada no Notion);
- `zero`: sempre 0.

## Casos de referência com os dados disponíveis

Com o σ do percentil 95 publicado na tabela §3.1 do Notion ("σ alt"), sem acesso ao
banco, dá para recalcular o CADE bruto dos dois casos de referência:

| Caso | `n_i` | CADE bruto (`population_std`) | `p95_winsorized` + `indicator` | `p95_winsorized` + `half` |
|---|---|---|---|---|
| `hotels-stays55501.com` | network activity 60, other 48, person 10 | 6,5218 | 12,6084 | 9,4834 |
| Evento 19 | payload installation 792, external analysis 508, network activity 48, antivirus detection 35, payload delivery 33, other 9 | 18,7994 | 22,9719 | 19,8469 |

CADE', E e P dependem do mínimo e do máximo do CADE em **todos** os eventos, e o
`log_std` depende da distribuição inteira de `n_i`. Esses valores só podem ser
calculados sobre o MISP de estudos.

## O que falta (depende do dono)

1. Rodar os três estimadores sobre o MISP de estudos (515.151 atributos, 1.613
   eventos), com `as_of` fixo em 2026-11-10T18:11:00Z, e comparar a distribuição do
   CADE, do CADE' e do top-N de cada um.
2. Escolher o estimador e a regra para σ = 0, com a justificativa.
3. Gravar os valores recalculados de σ, CADE, CADE', E e P dos dois casos em
   `tests/unit/fixtures/carioca_reference_approved.json`. Esse é o nível 2 da SC-015,
   conferido por `tests/unit/test_carioca_reference_approved.py`.
4. Atualizar `sigma` na configuração e preencher `approval` (`approved: true`,
   `approved_by`, `approved_at` e `evidence_ref` apontando para este documento).

A proposta inicial na configuração é `log_std` com `indicator`, porque é o único
estimador implementado que não zera as categorias raras. Ela continua sujeita à
avaliação acima.
