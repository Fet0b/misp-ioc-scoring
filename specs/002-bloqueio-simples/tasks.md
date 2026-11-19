---
description: "Tarefas para bloqueio simples e compartilhamento Pi-hole"
---

# Tasks: Bloqueio simples e Pi-hole

**Input**: `specs/002-bloqueio-simples/` — especificação, plano, pesquisa, modelo e contratos.

**Formato**: `- [ ] TNNN [P?] [USn?] descrição e caminho`; `[P]` indica arquivos distintos e ausência de dependência entre tarefas marcadas no mesmo bloco. Os testes são exigidos pelos critérios da especificação e pela constituição.

## Fase 1: Preparação

- [X] T001 Atualizar `docs/domain-glossary.md` com Decisão de bloqueio, Destino Pi-hole e Entrada gerenciada; distinguir UUID de atributo e ID numérico local e explicar a transformação de URL para hostname.
- [X] T002 [P] Documentar em `specs/002-bloqueio-simples/quickstart.md` os pré-requisitos PostgreSQL/MISP/Pi-hole de teste e os comandos existentes de migração e teste, identificando a funcionalidade como ainda não implementada.

## Fase 2: Fundação — dados confiáveis de coleta

**Objetivo**: disponibilizar identidades e snapshots consistentes por origem sem violar a propriedade dos módulos. Os testes T003–T004 antecedem a implementação.

- [ ] T003 [P] Criar testes em `tests/contract/test_misp_collection.py` para ID numérico opcional, UUID, timestamp do atributo, atributos em objetos, categorias originais, listas habilitadas, falha e lista vazia após coleta completa; impedir exposição de valores sensíveis.
- [ ] T004 [P] Criar `tests/integration/test_blocking_collection_snapshot.py` para geração por origem, snapshot legado não confiável, alteração/remoção, falha, concorrência e isolamento dos papéis de banco.
- [X] T005 Ampliar `src/misp_ioc_scoring/collection/adapters/schemas.py` e `src/misp_ioc_scoring/collection/domain/observations.py` para preservar o ID numérico local opcional distinto do UUID, categoria original e `source_modified_at` como timestamp do atributo.
- [X] T006 Acrescentar campos e migração em `src/misp_ioc_scoring/collection/infrastructure/persistence/models.py` e `migrations/versions/0003_blocking_collection.py`: identidade `(source_instance_id, attribute_uuid)`, `attribute_id` numérico local opcional, geração monotônica, instante de snapshot completo e confiança por origem; snapshots legados começam não confiáveis.
- [X] T007 Atualizar `src/misp_ioc_scoring/collection/infrastructure/persistence/repositories/observations.py` e `src/misp_ioc_scoring/collection/application/collect.py` para publicar geração, observações e warninglists atomicamente, invalidar confiança em falhas e coordenar locks de origem com scoring, preservando remoções/rejeições.
- [X] T008 Estender `src/misp_ioc_scoring/collection/api.py` com leitura transacional coerente por origem de observações ativas e removidas, rejeições, warninglists, geração, status e instante de snapshot; scoring e sharing não podem escrever em collection.

## Fase 3: User Story 1 — consultar decisões de bloqueio (P1, MVP)

**Objetivo**: calcular e publicar decisão rastreável por atributo e expor somente resultados efetivos confiáveis.

**Teste independente**: com snapshot controlado, consultar atributos que satisfazem ou violam cada condição; alterar coleta, warninglist ou tempo e confirmar que nenhum `true` obsoleto é exposto.

### Testes

- [X] T009 [P] [US1] Criar `tests/unit/test_simple_blocking_rules.py` para combinações de `to_ids`, `url`/`domain`, `analysis=2`, remoção e dados ausentes; testar frescor antes, exatamente e após 365 dias, timestamp futuro e `as_of` fixo.
- [X] T010 [P] [US1] Criar `tests/unit/test_blocking_warninglists.py` para igualdade de URL completa, hostname normalizado e subdomínios, isolamento por origem, lista vazia confiável e tipos não suportados sem falso positivo.
- [ ] T011 [P] [US1] Criar `tests/contract/test_blocking_sender.py` para origem mais UUID, ID local opcional, ausência/indeterminação, motivo, `as_of`, expiração e invalidação por geração, idade ou falha, conforme `specs/002-bloqueio-simples/contracts/sender.md`.
- [ ] T012 [P] [US1] Criar `tests/integration/test_simple_blocking.py` para migração, persistência, remoção/rejeição, publicação atômica, corrida com coleta, falha, expiração entre execuções e papel observer somente leitura.

### Implementação

- [X] T013 [P] [US1] Implementar em `src/misp_ioc_scoring/scoring/domain/simple_blocking.py` regra pura com motivos, cálculo `(1 - (t/365) ** (1/0.7)) * 100`, `as_of` UTC e `source_modified_at`; timestamps futuros ou inválidos são indeterminados e nunca positivos.
- [X] T014 [P] [US1] Estender `src/misp_ioc_scoring/collection/domain/warninglists.py` e `src/misp_ioc_scoring/collection/api.py` para URL completa e hostname normalizado de URL/domínio, incluindo subdomínios, e expor entradas não avaliáveis por origem.
- [ ] T015 [US1] Criar modelos em `src/misp_ioc_scoring/scoring/infrastructure/persistence/models.py` e migração `migrations/versions/0004_simple_blocking.py`: `block` boolean não nulo, unicidade `(source_instance_id, attribute_uuid)`, `attribute_id` numérico local opcional, motivo, execução, geração, `as_of`, vencimento e entradas decisivas; manter grants e não armazenar credenciais.
- [X] T016 [US1] Implementar `src/misp_ioc_scoring/scoring/application/simple_blocking.py` com portas, avaliação integral, reconciliação de remoções/rejeições e registro de evidências; não fabricar decisões para atributos nunca coletados.
- [X] T017 [US1] Implementar `src/misp_ioc_scoring/scoring/infrastructure/persistence/simple_blocking.py` com lock entre workers, verificação de geração coordenada com T007 e publicação transacional; rejeitar snapshot modificado e registrar falhas seguras.
- [X] T018 [US1] Implementar leitura efetiva em `src/misp_ioc_scoring/scoring/api.py` e, se necessário, view em `migrations/versions/0005_blocking_sender_view.py`: verificar execução, geração, confiança, idade do snapshot e avaliação e vencimento; distinguir falso calculado de ausente/indeterminado.
- [X] T019 [US1] Implementar agendamento UTC em `src/misp_ioc_scoring/scoring/infrastructure/scheduling/scheduler.py` e composição em `src/misp_ioc_scoring/entrypoints/scoring_sharing.py`, com execução inicial, `max_instances=1`, `coalesce` e lock de banco; permitir execução controlada independente das flags.

**Checkpoint**: decisões consultáveis e verificadas por origem/UUID, sem enviar nem bloquear diretamente.

## Fase 4: User Story 3 — compartilhar indicadores no Pi-hole (P1)

**Objetivo**: sincronizar hostnames elegíveis com Pi-hole v6, com rastreabilidade, propriedade e seleção de score; MISP sharing continua independente.

**Teste independente**: usar Pi-hole isolado e indicadores controlados; verificar inserção, conversão URL/hostname, confirmação, repetição, invalidação e remoção apenas de entradas próprias, com score simples; para CARIOCA usar score simulado e verificar erro explícito quando o motor real estiver ausente.

### Testes

- [X] T020 [P] [US3] Criar `tests/unit/test_pihole_policy.py` para `default` e CARIOCA simulado, corte inclusivo 0–100, score ausente/vencido, warninglist, frescor, múltiplas origens, deduplicação e suspensão com snapshot incompleto.
- [X] T021 [P] [US3] Criar `tests/unit/test_pihole_hostname.py` para domain e URLs com caminho, porta, query, IDNA e subdomínio, rejeição de IP literal, host inválido e tipos `link`/`text`; verificar hostname exato e não wildcard.
- [ ] T022 [P] [US3] Criar `tests/contract/test_pihole_api.py` com servidor simulado para autenticação v6, expiração de sessão, validação de versão, TLS/HTTP explícito, confirmação, erro, timeout ambíguo e ausência de segredos nos logs.
- [ ] T023 [P] [US3] Criar `tests/integration/test_pihole_sharing.py` para entradas próprias e manuais, múltiplas evidências por host, repetição idempotente, concorrência, remoção segura, falha de coleta/endpoint, origem indisponível com outra disponível, timeout de criação, alteração remota da marca, tentativas e preservação de grupos; conferir grants de `sharing`.
- [ ] T024 [P] [US3] Criar `tests/integration/test_misp_category_inventory.py` para contagens agregadas por origem/tipo/categoria, inclusive atributos de objetos e fonte indisponível, sem imprimir valores de indicadores nem credenciais.

### Implementação

- [X] T025 [P] [US3] Implementar extração e validação de hostname em `src/misp_ioc_scoring/sharing/domain/pihole_hostname.py`: para `domain` ou `url` preservar evidência original, rejeitar IP literal e host inválido, enviar somente hostname DNS normalizado exato; documentar alcance ao host inteiro.
- [X] T026 [P] [US3] Implementar política pura em `src/misp_ioc_scoring/sharing/domain/pihole_policy.py` com `default` por decisão efetiva e `carioca` por score válido `>=` corte finito de 0 a 100, sem top-N implícito; verificar warninglist e frescor e manter um host desejado enquanto houver evidência elegível.
- [ ] T027 [US3] Criar modelos em `src/misp_ioc_scoring/sharing/infrastructure/persistence/models.py` e migração `migrations/versions/0006_pihole_sharing.py` após as migrações anteriores, incluindo política efetiva com modelo `default` ou `carioca`, corte obrigatório e finito de 0 a 100 para CARIOCA, referência de segredo comentada `secret`, host/destino/identidade remota/marca verificável de propriedade, evidências por origem/UUID, tentativa com estado pendente/confirmado/falhou/ambíguo e nenhum SID ou senha persistido.
- [ ] T028 [US3] Implementar adaptador v6 em `src/misp_ioc_scoring/sharing/adapters/pihole.py`: validar versão/contrato da instância, autenticar por referência de segredo, renovar SID expirado, usar TLS verificado por padrão e permitir HTTP apenas com opção explícita; consultar estado após timeout e não registrar segredos ou URLs de indicadores.
- [X] T029 [US3] Implementar `src/misp_ioc_scoring/sharing/infrastructure/persistence/pihole.py` para vínculo de evidências, propriedade comprovada, estados/tentativas idempotentes, auditoria de score/geração e lock de execução; não adotar entradas remotas preexistentes; registrar identidade remota e marca verificável, mantendo e sinalizando entradas cuja propriedade não possa ser comprovada após timeout ou alteração remota.
- [X] T030 [US3] Implementar `src/misp_ioc_scoring/sharing/application/sync_pihole.py` usando APIs públicas de collection/scoring e portas do adaptador: revalidar antes de envio/retry, confirmar estado remoto, limitar tentativas, manter entradas vinculadas a origem com snapshot incompleto ou vencido, reconciliar normalmente entradas sem esse vínculo e reavaliar após recuperação; remover somente entradas comprovadamente próprias sem evidência elegível.
- [ ] T031 [US3] Implementar levantamento somente leitura em `tools/misp_category_inventory.py` e instruções em `specs/002-bloqueio-simples/research.md` para contagens por origem/tipo/categoria e período, incluindo atributos em objetos; usar dados autorizados existentes, registrar indisponibilidade sem inventar categorias e nunca filtrar categoria automaticamente.
- [X] T032 [US3] Compor job Pi-hole em `src/misp_ioc_scoring/entrypoints/scoring_sharing.py` e `src/misp_ioc_scoring/sharing/infrastructure/scheduling/scheduler.py`, com execução e reconciliação não sobrepostas; indisponibilidade Pi-hole não interrompe a coleta, e o destino desativado não envia nem remove.

**Checkpoint**: testar com cliente Pi-hole simulado e, quando disponível, instância isolada; `carioca` sem motor implementado deve falhar claramente e nunca fabricar score.

## Fase 5: User Story 2 — controlar módulos (P2)

**Objetivo**: controlar independentemente coleta, scoring e destinos MISP/Pi-hole por ambiente, sem exigir configuração de componentes inativos.

**Teste independente**: iniciar combinações de flags com jobs simulados; verificar defaults, isolamento dos destinos e erros de configuração/implementação indisponível.

### Testes

- [X] T033 [P] [US2] Ampliar `tests/unit/test_configuration.py` para flags booleanas, `SHARING_MISP_ENABLED=false`, `SHARING_PIHOLE_ENABLED=false`, `PIHOLE_SCORE_MODEL=default|carioca`, corte ausente/inválido/0/100, dependências condicionais, segredos ausentes para destinos inativos e erro de CARIOCA/MISP não implementados.
- [ ] T034 [P] [US2] Criar `tests/integration/test_module_activation.py` para combinações de flags com jobs simulados, incluindo Pi-hole ativo e MISP desativado, ausência de envios a destinos inativos e Compose sem segredos de módulos inativos.

### Implementação

- [X] T035 [US2] Implementar flags e validação condicional em `src/misp_ioc_scoring/shared/configuration.py`: coleta, scoring simples, CARIOCA, `SHARING_MISP_ENABLED` e `SHARING_PIHOLE_ENABLED` independentes; `PIHOLE_SCORE_MODEL` é `default` ou `carioca`; corte CARIOCA obrigatório e finito de 0 a 100; rejeitar CARIOCA e sharing MISP enquanto não implementados.
- [X] T036 [US2] Aplicar flags e encerramento controlado em `src/misp_ioc_scoring/entrypoints/collector.py` e `src/misp_ioc_scoring/entrypoints/scoring_sharing.py`, integrando T019 e T032 sem iniciar jobs desabilitados ou realizar operações em destinos pausados.
- [ ] T037 [US2] Atualizar `compose.yaml` e `.env.example` com flags independentes, modelo/corte, endpoint e segredo Pi-hole condicionais, perfil scoring e `MISP_TO_IDS_ONLY=false` para cobertura de `to_ids=false`; não exigir segredos ou interpolação de MISP sharing/CARIOCA quando inativos.

**Checkpoint**: testar flags com jobs simulados independentemente; integrar scheduler real após US1 e US3.

## Fase 6: Acabamento e validação transversal

- [X] T038 [P] Atualizar `README.md` com critérios, decaimento, consulta segura, limites de coleta, flags, seleção de score e alcance do bloqueio de hostname derivado de URL; explicar pausa de sharing MISP e necessidade de CARIOCA implementado.
- [X] T039 Atualizar `specs/002-bloqueio-simples/quickstart.md` e `specs/002-bloqueio-simples/contracts/sender.md` com comportamento final, nomes de flags, consulta e passos executáveis; manter o contrato de consulta alinhado ao comportamento do Pi-hole.
- [ ] T040 Executar testes aplicáveis em `tests/unit/`, `tests/contract/`, `tests/integration/` e `tests/architecture/`, conferir `docker compose config` e cenário de Pi-hole isolado; registrar em `specs/002-bloqueio-simples/quickstart.md` serviços ou verificações indisponíveis.
- [ ] T041 Revisar `src/misp_ioc_scoring/`, `compose.yaml` e `migrations/versions/` quanto a segredos, TLS, fronteiras de módulos, acesso mínimo, dados legados, bloqueios obsoletos, propriedade e remoção de entradas; corrigir problemas e repetir os testes afetados.

## Dependências e ordem

- Preparação → fundação (T003–T008) → US1 e componentes independentes de US3/US2. T005 precede T006, T006 precede T007 e T007 precede T008.
- US1: T009–T012 antecedem implementação; T013/T014 podem ser paralelas; T015 depende de T006; T016 depende de T008/T013/T014; T017 de T007/T015/T016; T018 de T017; T019 de T016/T017.
- US3 depende da interface de decisão T018 para integração real. Testes T020–T024 e domínio T025/T026 podem avançar com fakes; T027 depende de T015 e, se T018 criar migração 0005, dela também; T028/T029 precedem T030; T030 usa T018/T025/T026/T028/T029; T032 depende de T030. T031 pode operar sobre coleta existente e registrar indisponibilidade.
- US2 pode ser testada com jobs simulados após fundação; T033/T034 antecedem T035, que precede T036/T037. A composição final T036 depende de T019/T032 e deve ser coordenada com as edições dos mesmos arquivos.
- Acabamento depende das histórias desejadas. Executar migrações em sequência única; se T018 dispensar a view 0005, ajustar `down_revision` da 0006 para 0004 sem criar revisão fantasma.

## Exemplos de trabalho paralelo

- US1: testes T009–T012 em arquivos distintos; depois T013 e T014 em arquivos distintos.
- US3: testes T020–T024 em arquivos distintos; depois T025 e T026; não editar `scoring_sharing.py` simultaneamente em T019/T032/T036.
- US2: testes T033 e T034 em arquivos distintos; T035 precede integração de entrypoints/Compose.

## Estratégia de implementação

1. Concluir fundação e US1 e validar a decisão consultável como MVP.
2. Implementar US3 com `default`, validar Pi-hole isolado e tratamento explícito de CARIOCA indisponível; integrar US2 para ativação seletiva.
3. Validar segurança, documentação e migrações. O CARIOCA completo e o transporte MISP permanecem trabalhos futuros; atributos nunca coletados não geram decisão.
