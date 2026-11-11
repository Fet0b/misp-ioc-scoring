# Quickstart de validação

Este roteiro valida o comportamento da feature depois que os serviços de aplicação
forem implementados. Os comandos assumem Docker Compose e ambiente Python do projeto;
arquivos de execução ainda serão entregues pelas tarefas de implementação.

## Pré-requisitos

- Docker Engine e Docker Compose disponíveis.
- Instância MISP de teste com conta de automação e pelo menos um evento/atributo de
  teste, além de um peer de sync isolado.
- Configuração CARIOCA versionada, contendo explicitamente todos os parâmetros ainda
  não definidos na publicação (estimador de σ, normalização do CADE, FeedRank
  `orgc-proxy`, `top_n`, regra de empate) e casos de resultado de referência aprovados.
- Peers e score mínimo por peer definidos nas variáveis de ambiente do container de
  scoring/sharing (mudança exige reiniciar o container).
- Endpoint de teste com `to_ids_only` habilitado e ao menos uma warninglist habilitada.
- Credenciais fornecidas por mecanismo seguro de configuração, não commitadas.

## Verificações

1. **Subir o ambiente**: iniciar PostgreSQL e os dois workers pelo Compose.
   Esperado: os três serviços ficam saudáveis; workers reportam versão/configuração
   sem imprimir segredos.
2. **Coletar**: executar uma coleta manual de cada endpoint de teste.
   Esperado: resposta paginada validada, checkpoint avançado apenas após persistência,
   IOCs deduplicados por tipo/valor normalizado e observações mantidas por UUID.
3. **Repetir coleta**: repetir a mesma janela e depois alterar um campo relevante e
   outro não relevante.
   Esperado: nenhuma duplicação; mudança relevante marca o IOC lógico uma vez;
   mudança irrelevante não marca.
4. **Validar scoring**: rodar testes de unidade com casos CARIOCA de referência e uma
   execução diária de candidatos.
   Esperado: scores/componentes reproduzíveis para o mesmo `as_of`; configuração
   incompleta (inclusive sem estimador de σ aprovado) impede cálculo; toda a população
   válida é recalculada; IOCs expirados ou de tipo sem decaimento ficam com exclusão
   registrada; falha ou revisão concorrente deixa o candidato pendente; gravação do
   score não o remarca.
5. **Validar compartilhamento**: testar score abaixo/acima do limite e distribuição
   autorizada/restrita, incluindo timeout após envio.
   Esperado: somente IOC no top-N, com score mínimo, fora de warninglist e autorizado é
   sincronizado; timeout não é
   registrado como entrega confirmada; retentativa reconcilia antes de repetir.
6. **Validar filtro de coleta**: coletar com `to_ids_only` e depois desabilitá-lo/habilitá-lo
   num banco de teste.
   Esperado: atributos fora do filtro recebem `removed_at`; reconciliação acima do limite
   de remoção é recusada e não avança o checkpoint.
7. **Validar rejeições**: coletar fixtures com indicadores inválidos e de tipo não
   suportado, e repetir a coleta.
   Esperado: nenhum IOC é criado para eles; cada rejeição aparece uma vez por origem e
   motivo, com valor bruto, tipo MISP e momento; contagem e listagem por motivo e origem
   funcionam; logs não repetem o valor.
8. **Validar desempenho**: rodar o scoring diário sobre dados representativos (ordem de
   270 mil IOCs válidos).
   Esperado: recálculo da população completa em até 1 hora (SC-011); população vazia
   conclui sem scores e com aviso; valores iguais na normalização dão 50.
9. **Validar configuração de peers**: iniciar o container com mínimo fora de 0–100 e
   depois com valores válidos, alterando e reiniciando.
   Esperado: configuração inválida impede o compartilhamento com erro explícito;
   alteração só vale após o reinício e a política efetiva fica registrada.
10. **Validar validade do score**: com a última execução de scoring bem-sucedida com mais
    de 48 horas (simulada), executar o compartilhamento.
    Esperado: nenhum envio, aviso ao operador; após uma nova execução bem-sucedida os
    envios retomam.
11. **Validar observabilidade**: rodar o script de exportação sobre o banco de teste.
    Esperado: uma aba por tabela de todos os schemas, mais a aba de métricas (contagens,
    rejeições por motivo e origem, última execução de coleta e scoring, população válida e
    excluída, candidatos pendentes, tentativas por estado, avisos e suspensão do
    compartilhamento); valores como `=1+1` ou `@x` em `raw_value` aparecem como texto;
    nenhum segredo na planilha; abas acima do limite indicam o truncamento e a aba de
    métricas traz o total.
12. **Validar parâmetros de ambiente**: iniciar cada container com uma frequência ou
    validade inválida e depois válida.
    Esperado: valor inválido impede o início com erro explícito; mudança só vale após
    reiniciar.
13. **Validar recuperação**: interromper a coleta e reiniciar um worker durante um
   lote.
   Esperado: checkpoint e pendências permitem retomar sem lacunas ou duplicação.

## Comandos previstos

```bash
docker compose up --build
python -m pytest
```

Para cenários de integração, usar o perfil de teste e instância MISP isolada a serem
definidos na implementação. Não executar testes de publicação contra peers de produção.

## Referências

- [Modelo de dados](./data-model.md)
- [Contrato de coleta](./contracts/misp-collection.md)
- [Contrato de compartilhamento](./contracts/misp-sharing.md)


## MVP de coleta implementado (2026-11-11)

A coleta e a exportação estão implementadas; scoring e compartilhamento seguem
pendentes. O perfil `scoring` fica desativado por padrão. Preparação de segredos,
formatos JSON de endpoints/cadências e comandos de consulta estão em
[README.md](../../README.md).

```bash
docker compose up -d --build database migrate collector
docker compose ps -a
docker compose logs --tail=30 collector
docker compose --profile tools run --rm tools
.venv/bin/python -m pytest
```

A primeira coleta começa na inicialização. Banco e coletor têm reinício automático;
o volume `postgres-data` preserva os dados. Para a integração automatizada, definir
`TEST_DATABASE_URL` para uma instância PostgreSQL separada e descartável, com nome de
banco terminado em `_test`; os testes criam e removem schemas e papéis nesse ambiente.
Não usar o cluster de produção para os testes.
