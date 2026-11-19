# Guia de validação

Este guia descreve o comportamento a validar após a implementação; não afirma que a funcionalidade já está disponível.

1. Preparar PostgreSQL e MISP de teste isolados conforme `specs/001-misp-ioc-scoring/quickstart.md`; fornecer os segredos de coleta e banco. Executar as migrações até `head`.
2. Em ambiente de teste configurar `MISP_TO_IDS_ONLY=false` para observar decisões positivas e negativas, habilitar coleta e scoring simples pelas flags documentadas na implementação, e manter CARIOCA e sharing desabilitados. Iniciar Compose com o perfil `scoring`; confirmar que não são exigidos segredos de peers nem configuração CARIOCA.
3. Criar atributos URL e domain com `to_ids=1`, evento `analysis=2` e timestamp recente. Após coleta e avaliação, consultar pelo contrato em [sender.md](contracts/sender.md): decisão efetiva verdadeira. Repetir invertendo cada condição e adicionando correspondências em warninglists; esperar falsa e motivo.
4. Validar idade imediatamente antes, exatamente aos 365 dias e depois; também timestamps futuros, observações removidas, coleta falha, lista não suportada e mudança de lista após avaliação. Nenhuma decisão positiva obsoleta deve ser consultável.
5. Executar `.venv/bin/python -m pytest` e os testes de integração PostgreSQL com a configuração descrita no repositório; rodar também verificações arquiteturais e `docker compose config`. Registrar separadamente testes que não puderem rodar por falta de serviços externos.

## Validação adicional do Pi-hole

Após implementação, usar uma instância Pi-hole v6 isolada, consultar `/api/docs` da versão e configurar endpoint, credencial por referência de segredo e `SHARING_PIHOLE_ENABLED=true`, mantendo `SHARING_MISP_ENABLED=false`. Com `PIHOLE_SCORE_MODEL=default`, avaliar um domínio e uma URL e verificar que apenas hostnames exatos elegíveis aparecem na lista gerenciada, com vínculo ao atributo de origem. Confirmar que uma URL com caminho bloqueia o hostname inteiro e que subdomínios não são incluídos automaticamente.

Repetir envio e simular timeout; não devem surgir duplicatas. Criar entrada manual preexistente, retirar elegibilidade das evidências e verificar que apenas entradas comprovadamente criadas pelo projeto são removidas. Simular coleta incompleta e garantir suspensão de remoções. Testar flags desativadas e ausência de segredos de destinos não usados. Para `carioca`, fornecer corte explícito e configuração aprovada quando o motor existir; até lá verificar erro claro ao habilitar. Efetuar levantamento agregado de tipo/categoria por origem com instâncias autorizadas ou dados já coletados; documentar indisponibilidade quando não houver dados.

Com configuração de banco e segredos da coleta pronta, habilite o perfil com
`docker compose --profile scoring up --build`. Configure
`SCORING_SIMPLE_ENABLED=true` e `SCORING_DAILY_CRON=0 3 * * *`.
Monte a senha de aplicativo como `password` no diretório indicado em
`PIHOLE_CREDENTIALS_DIR` e configure `PIHOLE_URL` e `PIHOLE_INTERVAL_SECONDS`
antes de habilitar `SHARING_PIHOLE_ENABLED`.

Consulta com o papel observer:

```sql
SELECT *
FROM scoring.decisao_bloqueio_efetiva
WHERE source_instance_id = 'origem-de-teste' AND attribute_id = 42;
```

Para levantar categorias dos atributos ativos já coletados, execute
`python -m tools.misp_category_inventory` com `DATABASE_URL` do observer.
O resultado agrega tipo e categoria por origem. Ele representa o conjunto
visível pela coleta, sujeito aos filtros dos endpoints.

A suíte local usa um adaptador simulado nos casos de timeout e propriedade.
A migração e as consultas PostgreSQL exigem `TEST_DATABASE_URL` apontando
para um banco descartável com sufixo `_test`. A confirmação no DNS e a
validação do Compose exigem Docker e uma instância Pi-hole v6 de teste.
