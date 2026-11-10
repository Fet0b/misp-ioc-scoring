# Contrato de integração: coleta MISP

## Propósito

Definir o comportamento observável do adaptador de coleta entre uma instância MISP e o
domínio IOC, sem acoplar regras de scoring ao formato de resposta externo.

## Entrada

- Endpoint MISP configurado e habilitado, credencial autorizada e versão/API detectada.
- Cadência, filtros, tamanho de página e checkpoint da última janela concluída.
- O worker executa a janela de forma síncrona; cada endpoint tem estado e frequência
  independentes.

## Operação

1. Consultar eventos/atributos suportados usando pesquisa paginada e janela temporal
   com sobreposição conforme os filtros aprovados.
2. Validar o payload na fronteira externa; mapear campos MISP para Observação de
   origem sem expor regras de negócio ao cliente PyMISP.
3. Preservar UUID da instância/evento/atributo, valores originais, timestamps, tags,
   distribuição e campos relevantes à avaliação.
4. Normalizar tipo/valor e associar por identidade do IOC lógico (tipo + valor
   normalizado); atualizar a Observação de origem pelo UUID em vez de criar duplicata.
5. Persistir o lote com transação e atualizar o checkpoint somente após todas as
   páginas/alterações da janela terem sido aplicadas.

## Saída e falhas

- Sucesso: lote persistido, contadores e checkpoint integralmente processado.
- Payload inválido/não suportado: erro identificável, valor não convertido em IOC
  válido; os demais registros podem continuar se a execução registrar falhas parciais
  sem avançar checkpoint além do que foi concluído com segurança.
- Indisponibilidade, rate limit ou falha de página: registrar status, aplicar backoff
  limitado e preservar checkpoint para repetição segura.
- Mudança concorrente no conjunto de resultados: reconciliação por UUID e timestamp;
  a próxima janela sobreposta deve poder recuperar alterações perdidas.
- Mudanças e remoções/expiração/alterações de `to_ids` devem ser reconciliadas para
  evitar conservar dados ativos que a origem já revogou.
- Credenciais não aparecem no log; erros contêm endpoint e contexto não sensível.

## Compatibilidade e segurança

- Consultar a versão da instância e usar o OpenAPI da instância como referência final.
- Nunca assumir que IDs numéricos são portáveis entre instâncias.
- Não tratar ausência em warninglist como prova de segurança.
- Revalidar filtros e permissões antes de ativar uma nova versão do adaptador.

## Verificação do contrato

- Respostas de endpoint têm paginação e formas alternativas cobertas por testes.
- Repetir uma janela não duplica IOC ou Observação de origem.
- Falhas não avançam checkpoint incorretamente.
- Eventos/atributos atualizados, expirados ou removidos são reconciliados.
- Instância incompatível ou credencial inválida é exposta como falha operacional clara.

## Referências

- [MISP automation guide](https://www.circl.lu/doc/misp/automation/)
- [PyMISP documentation](https://pymisp.readthedocs.io/en/latest/README.html)
