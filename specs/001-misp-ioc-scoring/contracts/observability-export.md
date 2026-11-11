# Contrato: exportação de observabilidade

## Propósito

Único meio de o operador observar o sistema além dos logs: um script que exporta o banco
para uma planilha Excel. Não há CLI, API nem interface de usuário (FR-028).

## Entrada

- Papel de banco somente leitura (`observer`) com acesso aos schemas `collection`,
  `scoring` e `sharing`.
- Variáveis de ambiente: destino do arquivo e limite de linhas por aba (FR-029; padrão
  1.000.000, teto 1.048.575); valores ausentes ou inválidos impedem a execução.

## Saída

- Um arquivo `.xlsx` com:
  - **Uma aba por tabela** de todos os módulos (nome da aba = schema e tabela).
  - **Aba "Métricas"**, calculada pelo script a partir das tabelas:
    - contagem de linhas por tabela;
    - rejeições de indicador por motivo e por origem;
    - última execução de coleta por endpoint e última execução de scoring (status,
      `as_of`, duração, avisos);
    - população válida e exclusões por motivo; execução vazia ou com MinMax degenerado;
    - candidatos a re-scoring pendentes;
    - entradas de warninglist não suportadas;
    - tentativas de compartilhamento por estado;
    - idade do último scoring bem-sucedido e se o compartilhamento está suspenso;
    - avisos ativos.

## Segurança e robustez

- Somente leitura; nenhuma escrita no banco.
- Sem segredos: colunas com o comentário PostgreSQL `secret` não são exportadas; um teste
  de arquitetura garante que toda coluna com nome sensível (`credential`, `secret`,
  `token`, `password`) tenha esse comentário.
- O arquivo é gravado com permissão restrita ao usuário que o gerou (0600) em diretório
  também restrito; a planilha contém IOCs e dados de peers.
- Valores de origem externa (por exemplo `raw_value`) são escritos como texto e
  neutralizados contra interpretação como fórmula (valores que começam com `=`, `+`, `-`
  ou `@`).
- Escrita em modo somente-escrita (write-only) para suportar abas grandes sem estourar a
  memória. Limite de linhas por aba: padrão 1.000.000, teto 1.048.575 (valores maiores são
  recusados na inicialização); ao exceder, a aba indica o truncamento e a aba "Métricas"
  traz o total real; nunca truncar em silêncio.
- Falha de conexão ou configuração inválida termina com erro explícito, sem arquivo
  parcial.

## Verificação do contrato

- Todas as tabelas de todos os schemas aparecem como abas.
- A aba "Métricas" traz os valores esperados em cenários de teste (rejeições, população,
  suspensão por score antigo, candidatos pendentes).
- Valores como `=1+1` e `@x` aparecem como texto.
- Nenhum segredo na planilha; abas truncadas são identificadas.
- Um teste de integração roda a exportação sobre o banco de teste com o papel `observer`
  (SC-012).
