# Implementation Plan: Bloqueio simples de indicadores

**Branch**: `main` (feature `002-bloqueio-simples`; nenhum branch foi criado) | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

## Summary

Adicionar ao módulo scoring uma avaliação booleana por observação de origem, com critérios verificáveis, expiração CARIOCA e consulta segura para o sender. Os dados vêm de collection; decisões são persistidas em scoring. Sharing MISP e Pi-hole possuem flags independentes e ficam desativados por padrão. O destino Pi-hole seleciona decisão simples ou score CARIOCA; configurações de componentes desativados não serão exigidas.

## Technical Context

**Language/Version**: Python 3.12\
**Primary Dependencies**: SQLAlchemy 2, Alembic, APScheduler 3, Pydantic, PyMISP existentes; sem novas dependências.\
**Storage**: PostgreSQL 16; schemas e papéis já existentes.\
**Testing**: pytest (unitário, contrato e integração PostgreSQL), import-linter; validação Compose.\
**Target Platform**: Linux / Docker Compose.\
**Project Type**: serviços assíncronos de coleta e processamento; sem API HTTP adicional.\
**Performance Goals**: processamento em lotes; execução não sobreposta; instrumentar duração e falhas, sem inventar SLA.\
**Constraints**: dados MISP não confiáveis; snapshot coerente, publicação atômica, nenhum resultado positivo obsoleto exposto; sem envio aos destinos desativados.\
**Scale/Scope**: múltiplas origens e atributos; avaliações individuais, incluindo removidos e rejeições conhecidas.

## Constitution Check

*Pré-pesquisa e pós-design: aprovado, sujeito à implementação e testes.*

- I: regra, versão, origem, dados decisivos, motivo, `as_of` e expiração registrados para reproduzir a decisão.
- II: manter valores originais e normalização da coleta; dados inválidos ou ausentes geram resultado negativo explícito.
- III: função de domínio pura recebe `as_of`; testes de critérios, fronteiras e reprocessamento.
- IV: validar entradas e timestamps; nenhuma credencial ou payload em logs; consulta com privilégios mínimos.
- V: aproveitar serviços, PostgreSQL e bibliotecas atuais; UUID e ID local explicitados no contrato; sem dependência nova.
- VI: domínio separado de infraestrutura; documentar “Decisão de bloqueio” no glossário e preservar interfaces públicas de módulos.
- Arquitetura: manter database, collector e scoring/sharing; pausa de sharing não elimina seu lugar na arquitetura nem o modelo CARIOCA futuro. Scoring lê collection e escreve apenas scoring; observer lê sem escrever. Testes e revisão de segurança são parte da entrega.

## Project Structure

### Documentation

```text
specs/002-bloqueio-simples/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/sender.md
└── quickstart.md
```

### Source Code

```text
src/misp_ioc_scoring/
├── collection/               # snapshot público e evidência de warninglists
├── scoring/domain/           # regra pura de decisão e frescor
├── scoring/application/      # avaliação e reconciliação
├── scoring/infrastructure/   # persistência e agendamento
├── scoring/api.py            # consulta segura das decisões
├── sharing/                 # política e adaptador Pi-hole
├── shared/configuration.py   # flags e validação condicional
└── entrypoints/              # composição dos serviços
migrations/versions/          # nova revisão após 0002
compose.yaml, .env.example, docs/domain-glossary.md
tests/unit/, tests/integration/, tests/contract/, tests/architecture/
```

**Structure Decision**: estender módulos atuais; collection fornece snapshots coerentes por sua API pública; scoring contém a regra e suas tabelas; entrypoints compõem adapters sem imports proibidos entre módulos.

## Design e sequência

1. Ampliar coleta para preservar ID numérico de atributo quando fornecido, além de `(source_instance_id, attribute_uuid)`, e estado versionado do snapshot completo de cada endpoint, incluindo warninglists e sucesso. Implementar leitura consistente de observações (ativas e removidas), rejeições, warninglists e gerações; manter histórico de origem. Desativar filtro `to_ids` quando se quiser decisões falsas para todos atributos disponíveis; documentar que registros não coletados não geram decisão.
2. Implementar regra pura e matching de warninglist: igualdade de URL inteira e correspondência de hostname para host normalizado de URL e domínio; comparar listas habilitadas da própria origem. Entradas de tipos não suportados ou snapshot ausente/vencido tornam a avaliação indeterminada, sem positivo. `source_modified_at` é timestamp do atributo; valores futuros ou inválidos são indeterminados. Expiração ocorre aos 365 dias; domínio e URL usam `D=0,7`, conforme [research.md](research.md).
3. Criar migração de decisão e metadados de execução, com unicidade por origem e UUID; processar snapshot integral e reconciliar removidos, substituindo decisão positiva por falsa. Uma transação publica execução concluída e decisões juntas; falhas preservam execução anterior mas não dão validade ilimitada.
4. Proteger consumidor de corridas e dados antigos: consulta efetiva verifica no banco geração do snapshot por origem, estado de sucesso da coleta, prazo do snapshot e prazo do próprio atributo; alteração ou expiração invalida positivos imediatamente, mesmo entre execuções. A publicação rejeita resultado se a geração mudou durante cálculo; coordenação transacional impede corrida entre verificação e publicação. Expor somente leitura e sem resultados positivos em caso de erro.
5. Adicionar flags de coleção, scoring simples, CARIOCA e sharing em `.env.example`, configuração validada e Compose; simples ativo por configuração explícita, CARIOCA, sharing MISP e sharing Pi-hole desativados por padrão, sem declarar que estão implementados. Ativação de módulo ainda não implementado deve falhar explicitamente. Não exigir credenciais de peers, CARIOCA ou segredos de Compose enquanto inativos. Execução agendada em UTC com `max_instances=1`, `coalesce`, uma execução inicial e sem sobreposição entre processos (lock de banco).
6. Acrescentar testes de domínio, contrato do sender, migração, papéis, concorrência e falhas, integração e configuração; atualizar guia e glossário. Implementar sender Pi-hole; manter transporte de sharing MISP futuro desativado.

## Complexity Tracking

Nenhuma exceção à constituição é proposta. Snapshot e validação de geração são necessários para evitar decisões positivas depois de remoção, alteração de warninglist ou corrida com a coleta.

## Design adicional: Pi-hole e seleção de score

- Introduzir `SHARING_MISP_ENABLED=false`, `SHARING_PIHOLE_ENABLED=false` e `PIHOLE_SCORE_MODEL=default` (`default` ou `carioca`). Exigir endpoint, referência de segredo e periodicidade somente se Pi-hole estiver habilitado. Para `carioca`, exigir `PIHOLE_CARIOCA_MIN_SCORE` numérico finito entre 0 e 100, configuração CARIOCA aprovada e execução válida atual; sem implementação de CARIOCA, recusar ativação com mensagem clara. Não inferir top-N para Pi-hole: o corte é o mínimo configurado. Sharing MISP continua reservado e falha explicitamente se ativado antes de sua implementação.
- Pi-hole v6 API por HTTPS com autenticação por referência de segredo, sessão expirada renovável e acesso mínimo; admitir HTTP somente por opção explícita para rede local. Descobrir versão e validar contrato `/api/docs` da instância. Não registrar senha, SID, payload sensível ou URL de indicador.
- Para domínio, validar hostname normalizado; para URL, extrair somente host DNS validado. Rejeitar IPs literais, hosts ausentes ou inválidos, sem converter tipos genéricos `link`/`text` em URLs. Configurar regra exata, sem wildcard nem suposição de cobertura de subdomínios. Um bloqueio afeta todo o host para clientes DNS e pode ser mais amplo que URL original; registrar explicitamente essa transformação.
- Avaliar elegibilidade e warninglist sobre todos os vínculos de origem do host. Um host é desejado enquanto existir pelo menos uma evidência elegível e atual; não remover entrada enquanto houver vínculo elegível. Se uma origem tiver snapshot incompleto ou expirado, manter cada entrada com vínculo a essa origem; entradas sem vínculo a essa origem podem ser reconciliadas normalmente. Após recuperação, reavaliar os vínculos e remover somente quando nenhuma evidência elegível restar. Revalidar antes de envio e novas tentativas; persistir justificativa, score, versão, geração, `as_of`, associação com observação e status.
- Operar exclusivamente em entradas criadas e comprovadamente gerenciadas pelo projeto, com identidade remota e marca verificável. Se uma resposta de criação se perder ou uma alteração remota impedir comprovação, manter a entrada e avisar o operador; entradas preexistentes não são adotadas nem removidas, e permissões/grupos existentes são preservados. Registrar confirmação real, timeouts ambíguos, reconciliação por leitura, retries limitados e falhas; a indisponibilidade do Pi-hole não bloqueia a coleta.
- Investigar as categorias de URL e domínio realmente existentes por origem e categoria, usando somente dados autorizados já coletados ou consulta de leitura às instâncias configuradas, incluindo atributos em objetos. Registrar contagens e período sem valores, credenciais ou dados brutos. Não limitar por categoria até existirem evidências e decisão explícita; tipos `url` e `domain` continuam filtrados pela semântica da regra. Se fontes não estiverem disponíveis, marcar levantamento pendente sem bloquear o planejamento.
- Testar regras de corte e ausência de CARIOCA, autenticação, compatibilidade de versão, casos de URL, deduplicação, múltiplas origens, invalidação, retirada segura, falha de rede, resposta ambígua e preservação de entradas manuais. Documentar grupos e resultado efetivo no DNS em Pi-hole de teste.

**Constituição pós-ampliação:** mantém três serviços e separação de domínios, registra transformação de URL e critério, minimiza privilégios e segredos, preserva fontes e exige testes. URL para host altera o alcance do bloqueio e deve ser documentado como transformação explícita, não como alteração do IOC original.
