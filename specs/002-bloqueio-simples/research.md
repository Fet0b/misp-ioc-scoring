# Pesquisa e decisões

## Decaimento

**Decisão:** aplicar a URL e domínio a fórmula CARIOCA `(1 - (t/365) ** (1/0.7)) * 100`, com `t` em dias desde o timestamp de modificação do atributo e `as_of` UTC fixo. Frescor positivo implica `0 <= t < 365`; em `t >= 365` é zero. Timestamp ausente, inválido ou futuro é indeterminado e não bloqueia. A escolha de usar `source_modified_at` é explícita: é o timestamp do atributo preservado pela coleta, enquanto `source_created_at` hoje representa a data do evento. Uma alteração do atributo reinicia a idade; registrar isso na explicação.

**Justificativa:** fórmula existente em `specs/001-misp-ioc-scoring/plan.md`; usuário autorizou mesma regra para URLs. **Alternativa:** usar data do evento ou inventar idade de criação do atributo; descartada porque a primeira não é timestamp do atributo e a segunda não está disponível.

## Identidade e cobertura

**Decisão:** chave estável `(source_instance_id, attribute_uuid)`; preservar adicionalmente ID numérico local do atributo quando presente e expor ambos, com origem obrigatória. Não interpretar UUID como ID numérico. **Justificativa:** ID local pode colidir entre instâncias; modelo atual só armazena UUID. **Alternativa:** ID numérico isolado, rejeitado por colisões. Coleta com `MISP_TO_IDS_ONLY=true` não fornece atributos `false`; usar `false` para cobertura integral, sem fabricar decisões para dados não coletados.

## Warninglists

**Decisão:** usar snapshot completo das listas habilitadas da mesma origem; comparar URL completa por string e o host normalizado por listas hostname, com subdomínios. Aceitar ausência de entradas somente após coleta completa confirmada. Caso existam entradas de tipos que não podem ser avaliados ou falhe a coleta, não produzir positivos dessa origem e registrar motivo. **Justificativa:** função atual não compara hostname ao host de URL e ignora regex/substring; ignorá-las não prova ausência da warninglist. **Alternativa:** tratar entrada não suportada como não correspondente, rejeitada por falso positivo de bloqueio.

## Consistência e validade

**Decisão:** snapshot transacional e geração por origem, atualização de geração na mesma transação da coleta, publicação atômica com verificação/lock, e consulta que invalida positivos quando geração mudou, coleta falhou, snapshot ficou velho ou tempo expirou. Usar `SCORE_MAX_AGE_HOURS` (padrão existente 48) como limite explícito do snapshot e da avaliação; consulta ausente/indeterminada nunca equivale a `true`. **Justificativa:** coleta e scoring são processos distintos e remoção ou alteração de lista pode ocorrer entre execuções. **Alternativa:** guardar somente booleano e confiar no último job; rejeitada porque pode servir `true` obsoleto.

## Configuração e implantação

**Decisão:** flags independentes, validação e recursos condicionais, sem CARIOCA/peer obrigatórios para scoring simples; implementação futura ainda indisponível falha se ativada. Preservar perfil Compose `scoring`, documentando como ativá-lo. **Alternativa:** ligar sharing automaticamente ou exigir credenciais não usadas, rejeitada pelo escopo de pausa.

## Pi-hole e URLs

**Decisão:** suportar Pi-hole v6 por API e enviar hostnames exatos, extraindo host DNS validado de URLs, sem wildcard. O bloqueio se aplica ao host inteiro e não distingue caminhos, portas ou parâmetros; um domínio compartilhado pode hospedar conteúdo legítimo. Conservar URL e contexto originais na coleta e registrar a transformação e o alcance. IP literal não é hostname DNS e não será enviado. O operador deve avaliar esse alcance antes de ativar o destino.

**Justificativa:** Pi-hole opera no DNS; a [documentação oficial da API](https://docs.pi-hole.net/api/) e a [especificação dos domínios](https://github.com/pi-hole/FTL/blob/master/src/api/docs/content/specs/domains.yaml) descrevem seu contrato. Autenticação v6 usa sessão temporária conforme [documentação oficial](https://docs.pi-hole.net/api/auth/). A documentação servida em `/api/docs` pela instância é a referência para a versão efetiva. **Alternativa:** enviar caminho de URL como se fosse regra DNS; rejeitada porque a semântica é incorreta.

## Modelo de score para Pi-hole

**Decisão:** `PIHOLE_SCORE_MODEL=default` usa decisão simples; `carioca` requer score numérico válido, corte explícito 0–100 e execução CARIOCA aprovada e vigente. Não impor top-N adicional ao Pi-hole. CARIOCA não está implementado: seleção não pode produzir scores fabricados nem ativação aparentemente bem-sucedida. **Alternativa:** oferecer CARIOCA como se estivesse funcional ou atribuir corte padrão; rejeitada por falta de implementação e aprovação.

## Categorias dos peers MISP

**Evidência pública:** o [modelo de dados MISP](https://www.misp-project.org/datamodels/) distingue tipo e categoria e a [definição de tipos do MISP](https://github.com/MISP/MISP/blob/2.5/describeTypes.json) indica `Network activity` como categoria padrão de `url`. Isso não determina categorias efetivamente usadas pelos peers. A [API MISP](https://github.com/MISP/MISP/blob/2.5/docs/API_Doc.md) descreve buscas por tipo e categoria. O código local já preserva `category` e processa atributos dentro de objetos.

**Decisão:** produzir levantamento agregado por origem, tipo e categoria no período disponível, sem registrar valores de indicadores. Nenhuma conexão com peers específicos está disponível neste planejamento; o levantamento empírico permanece pendente. Não filtrar categoria por padrão e não presumir que `link`, `text` ou outros tipos sejam equivalentes a `url`. **Alternativa:** restringir a `Network activity` de antemão, rejeitada por risco de perder URLs reais.

## Reconciliação de propriedade

**Decisão:** controlar apenas entradas criadas e comprovadamente gerenciadas pelo projeto, com evidências múltiplas por hostname e publicação confirmada. Uma entrada existente manualmente não é adotada ou removida. Retirar uma entrada gerenciada somente quando não restar nenhuma evidência elegível e o snapshot completo for confiável; falha ou ausência de confiança suspende remoções. **Alternativa:** substituir a lista inteira ou apagar qualquer domínio inelegível, rejeitada por afetar configurações de terceiros.

Para levantar as categorias, configure `DATABASE_URL` com a URL do papel
`observer` e execute `python -m tools.misp_category_inventory` na raiz.
O relatório agrega observações ativas por origem, tipo e categoria, incluindo
atributos de objetos. Os campos `earliest` e `latest` delimitam os instantes
de coleta das observações em cada grupo. A seção `sources` sinaliza origens
sem snapshot completo ou cuja última coleta falhou. Contagens existentes
dessas origens refletem os dados disponíveis da última coleta bem-sucedida.
