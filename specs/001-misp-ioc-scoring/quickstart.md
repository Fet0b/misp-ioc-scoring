# Quickstart de validação

Este roteiro valida o comportamento da feature depois que os serviços de aplicação
forem implementados. Os comandos assumem Docker Compose e ambiente Python do projeto;
arquivos de execução ainda serão entregues pelas tarefas de implementação.

## Pré-requisitos

- Docker Engine e Docker Compose disponíveis.
- Instância MISP de teste com conta de automação e pelo menos um evento/atributo de
  teste, além de um peer de sync isolado.
- Configuração CARIOCA versionada, contendo explicitamente todos os parâmetros ainda
  não definidos na publicação e casos de resultado de referência aprovados.
- Política por peer com score mínimo definido.
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
   Esperado: scores/componentes reproduzíveis; configuração incompleta impede cálculo;
   falha ou revisão concorrente deixa o candidato pendente; gravação do score não o
   remarca.
5. **Validar compartilhamento**: testar score abaixo/acima do limite e distribuição
   autorizada/restrita, incluindo timeout após envio.
   Esperado: somente score elegível e autorizado é sincronizado; timeout não é
   registrado como entrega confirmada; retentativa reconcilia antes de repetir.
6. **Validar recuperação**: interromper a coleta e reiniciar um worker durante um
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
