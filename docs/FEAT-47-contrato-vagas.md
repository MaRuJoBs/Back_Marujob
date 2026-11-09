# FEAT-47 — Contrato estruturado das oportunidades

## Estado da entrega

**Implementada e validada localmente**, na branch exclusiva `FEAT-47`, em
09/11/2026. Base: `origin/DEV`, commit
`db8f5b2ff7da80fa724de3bd75c671ba4f44a5af`, confirmado após novo fetch.
Não houve desenvolvimento na DEV, commit, push, abertura de PR, merge ou deploy.
A integração à DEV e a aplicação da migration em ambiente persistente continuam
dependentes de autorização; não são operações realizadas por este relatório.

Foram acrescentados somente `modalidade`, `cidade`, `uf` e `status`, com migration
nova, validação, testes e documentação. Os quinze campos anteriores, endpoints,
permissões, pesquisa, filtros, paginação e relacionamentos foram reaproveitados.

## Preparação e histórico verificado

Raiz confirmada: `C:/Users/Ricardo/Documents/Back_Marujob`. Branch inicial e
final desta implementação: `FEAT-47`. HEAD e origin/DEV tinham zero commits de
diferença antes das alterações. `git worktree list` mostrou uma única worktree
registrada; não foi encontrada outra implementação B47 ou branch remota B47.
Não foram encontrados AGENTS.md aplicáveis nas verificações do repositório e
ancestrais. O fetch precisou ser repetido com permissão fora do sandbox porque
o primeiro acesso a `.git/FETCH_HEAD` foi bloqueado.

Alterações locais preexistentes, preservadas e excluídas da entrega:

```text
 M core.png
 M db.sqlite3
?? media/portfolios/WhatsApp_Image_2026-10-29_at_14.58.02.jpeg
```

O histórico Git e todos os 19 PRs retornados pela busca backend foram consultados,
incluindo títulos alternativos. As integrações relevantes, com metadados de merge
conferidos durante esta sessão, são:

| PR | Conteúdo | merged_at UTC | Merge / implementação |
|---|---|---|---|
| [#10](https://github.com/MaRuJoBs/Back_Marujob/pull/10) | B34, CRUD e propriedade | 2026-10-30 18:20:15 | `4549d85` / `241f7bc` |
| [#15](https://github.com/MaRuJoBs/Back_Marujob/pull/15) | B37, busca/filtros/paginação | 2026-10-30 18:48:19 | `9d04124` / `a95b079` |
| [#17](https://github.com/MaRuJoBs/Back_Marujob/pull/17) | Oito complementos da vaga, pela branch FEAT-41 | 2026-10-30 20:57:50 | `d7e692c` / `23b2b1b` |
| [#18](https://github.com/MaRuJoBs/Back_Marujob/pull/18) | Filtros contratação/experiência | 2026-11-03 17:13:41 | `db8f5b2` / `1311f01` |
| [#14](https://github.com/MaRuJoBs/Back_Marujob/pull/14) | B41, candidaturas | 2026-10-30 18:47:46 | `473640e` |
| [#16](https://github.com/MaRuJoBs/Back_Marujob/pull/16) | B44, notificações/decisões | 2026-10-30 20:28:47 | `ff54267` |

Os PRs #2, #3, #4, #7 e #13 estavam fechados sem merge; os demais até #18
estavam integrados. Na nova consulta apareceu o [PR #19](https://github.com/MaRuJoBs/Back_Marujob/pull/19),
aberto e draft, `merged_at=null`, branch FEAT-45, commit `62fc99b`, para diretório
de profissionais. Ele não altera vagas, models ou migrations e não foi integrado
a esta branch. Sua rota `/api/freelancers/` não é a rota `/api/freelances/` de vagas.
Não há implementação duplicada de B34/B37 nem dependência funcional da B45.

## Auditoria e matriz do contrato

Foram inspecionados model, serializer, view, permissões, rotas, settings DRF,
migrations, testes de vagas/complementos/consultas e os documentos FEAT-34,
FEAT-36 e FEAT-37. Também foram conferidos os consumidores de oportunidade em
favoritos/candidaturas e os vínculos de notificações, sem alterar sua implementação.

Frontend DEV consultado exclusivamente em leitura pelo GitHub: `vagaForm.js`,
`CriarVagaComponent.vue`, `OportunidadeDetalheComponent.vue` e
`freelanceService.js`. Blobs respectivamente:
`e16a39057fedc5210706652937c8e970f0d9dec2`,
`5b57ae6d339fbf65b6b19bc9cb5860dd4a97e6c5`,
`91da2f7d798a594d3fce2a2ee73a399a5230699d` e
`53d31b687f26617ae9eb494fd7bc6b5c56dfafd8`.
O detalhe empresarial e a Home também haviam sido consultados nesta sessão.

Figma não verificado: nenhum link foi fornecido e as buscas nos documentos
backend e no código indexado dos dois repositórios não retornaram referência
utilizável. A implementação usa os requisitos deste prompt e os contratos reais,
sem inventar requisitos visuais.

| Campo | Antes no backend | Frontend consultado | Resultado B47 | Figma |
|---|---|---|---|---|
| Título | Persistido e exposto | Criação/edição/detalhe | Preservado | Não verificado |
| Descrição | Persistida, até 200 | Inclui prefixo de modalidade | Preservada, sem conversão | Não verificado |
| Categoria | `tag` livre | Formulário usa categoria e envia tag | Preservada | Não verificado |
| Preço | `preco` obrigatório | Pagamento em reais | Preservado, separado da faixa | Não verificado |
| Tempo | Texto livre obrigatório | Criação usa horas positivas | Preservado sem restringir legado | Não verificado |
| Modalidade | Somente dentro da descrição | Remoto/Híbrido/Presencial via prefixo | Campo estruturado opcional novo | Não verificado |
| Cidade/UF da vaga | Ausentes | Sem envio estruturado identificado | Dois campos opcionais novos | Não verificado |
| Requisitos | Persistidos e expostos | Formulário/edição; não exibidos no detalhe profissional consultado | Preservados | Não verificado |
| Benefícios | Persistidos e expostos | Formulário/edição; apresentação desigual entre telas | Preservados | Não verificado |
| Contratação | Persistida, escolhas e filtro | Formulário/edição | Preservada | Não verificado |
| Experiência | Persistida, escolhas e filtro | Formulário/edição | Preservada | Não verificado |
| Jornada | Persistida e exposta | Formulário/edição | Preservada | Não verificado |
| Data de publicação | Data gravável opcional | Formulário; Home ainda tem mensagem antiga | Preservada, não é status | Não verificado |
| Faixa salarial | Dois decimais opcionais | Formulário/edição | Preservada | Não verificado |
| Status | Ausente | Sem campo persistido identificado | Campo estruturado novo | Não verificado |

Os quatro campos novos são persistidos e serializados, não calculados. O prefixo
de modalidade é apenas texto persistido em descrição e interpretado pelo frontend.
A etiqueta de rascunho na prévia não é um status da API. A aproximação de última
publicação por maior ID na Home não é timestamp de publicação.

## Campos finais e validações

Todas as representações de oportunidade passam de 15 para **19 campos**.

| Campo | Tipo e regras |
|---|---|
| `id` | Inteiro automático, somente leitura |
| `empresa` | ID inteiro ou null, somente leitura; servidor atribui na criação |
| `titulo` | String obrigatória POST/PUT, não vazia, máximo 100 |
| `descricao` | String opcional, máximo 200, aceita vazio/null |
| `tag` | String livre opcional, máximo 50, aceita vazio/null |
| `preco` | Decimal obrigatório, não negativo, até 8 inteiros e 2 decimais |
| `tempo` | String obrigatória não vazia, máximo 50; API mantém unidade livre |
| `modalidade` | String opcional: Remoto, Híbrido, Presencial ou `""`; padrão `""` |
| `cidade` | String opcional, máximo 100, padrão `""`; trim externo e normalização Unicode NFC |
| `uf` | Sigla brasileira exata em maiúsculas ou `""`; padrão `""` |
| `status` | publicada, encerrada ou cancelada; padrão publicada no POST/legado |
| `requisitos`, `beneficios` | Strings opcionais, máximo 1000, padrão `""` |
| `tipo_contratacao` | CLT, PJ, Autônomo, Temporário, Estágio, Outros ou `""` |
| `nivel_experiencia` | Iniciante, Júnior, Pleno, Sênior, Especialista ou `""` |
| `jornada_trabalho` | String opcional, máximo 100, padrão `""` |
| `data_publicacao` | Data válida estrita YYYY-MM-DD ou null; sem geração automática |
| `salario_minimo`, `salario_maximo` | Decimais não negativos ou ambos null; máximo >= mínimo |

Modalidade, cidade e UF aceitam ausência e string vazia; não aceitam null.
Cidade e UF são independentes: informar uma não torna a outra obrigatória.
Cidade aceita letras Unicode, espaços, hífen, ponto e apóstrofos reto/tipográfico;
se não vazia, deve conter letra. Números, controles internos e outros símbolos
são rejeitados. Isso valida formato, não existência do município ou correspondência
geográfica com a UF. Nenhum serviço externo de geocodificação foi introduzido.

UFs: AC, AL, AP, AM, BA, CE, DF, ES, GO, MA, MT, MS, MG, PA, PB, PR, PE, PI,
RJ, RN, RS, RO, RR, SC, SP, SE, TO. Não há conversão silenciosa de caixa nas
escolhas. Opções desconhecidas, caixa/acentos diferentes ou espaços adicionais
em modalidade/UF/status retornam 400. Status não aceita vazio/null.

Textos complementares anteriores não aceitam null. Requisitos, benefícios e
jornada mantêm seus espaços no serializer. Valores monetários retornam strings
com duas casas; excesso de precisão é rejeitado, não arredondado silenciosamente.
Faixa incompleta/invertida é rejeitada considerando o estado final armazenado.
Preço não substitui faixa, e tempo não substitui jornada.

## Status e transições

Não existia regra de ciclo de vida de vaga na DEV. A B47 torna o estado explícito
sem inventar efeitos sobre outras FEATs: qualquer empresa proprietária pode
alterar entre os três estados, inclusive reabrir. Repetir o estado é idempotente.
As nove combinações de estado anterior/novo estão testadas. Estados inválidos
são rejeitados por ChoiceField; permissões continuam validadas pela view existente.
Também é possível criar diretamente em qualquer um dos três estados válidos.

**O status é informativo nesta entrega:** encerrada/cancelada continuam legíveis
e presentes na pesquisa e paginação. Não há bloqueio novo de candidatura,
cancelamento de candidatura existente, decisão automática ou notificação de mudança
de status. Favoritos permanecem válidos. Data nula/futura não muda status ou
visibilidade. O frontend não deve anunciar bloqueio de candidaturas inexistente.

Essas escolhas preservam o comportamento anterior. Ocultar vagas ou bloquear
candidaturas exigirá integração explícita futura com B37/B41/B44, com critérios
de reabertura, retenção e concorrência próprios. Não se deve substituir encerramento
por DELETE: a exclusão continua com os CASCADE existentes.

## Endpoints, permissões, PUT e PATCH

Todas as operações exigem JWT Bearer. Papéis vêm dos grupos existentes.

| Método | Endpoint | Regra / sucesso |
|---|---|---|
| GET | `/api/freelances/` | Autenticados; 200, coleção paginada |
| POST | `/api/freelances/` | Empresa; 201, empresa=request.user |
| GET | `/api/freelances/{id}/` | Autenticados; 200 |
| PUT | `/api/freelances/{id}/` | Empresa proprietária; 200; titulo/preco/tempo obrigatórios |
| PATCH | `/api/freelances/{id}/` | Empresa proprietária; 200; somente campos enviados |
| DELETE | `/api/freelances/{id}/` | Empresa proprietária; 204 |

PUT e PATCH preservam os campos opcionais omitidos, incluindo status existente;
o padrão publicada não sobrescreve encerrada/cancelada em edição. PATCH também
permite omitir os obrigatórios da criação. `""` limpa modalidade/cidade/UF/textos;
null limpa data. Para limpar faixa, enviar ambos os extremos null.
`id`/`empresa` enviados não transferem propriedade. Vagas legadas sem empresa
continuam legíveis e não editáveis pela API. Não há exceção de superusuário.

Sem autenticação: 401; escrita sem papel/propriedade: 403; ID inexistente: 404;
validação: 400 por campo. Erros gerais usam `{"detail":"..."}` conforme DRF.
Textos padrão seguem a localização do ambiente.

Filtros B37 preservados: search (título, até 200 caracteres/20 termos), tag
(texto completo, comparação conforme banco), preco_min/preco_max inclusivos,
tipo_contratacao, nivel_experiencia e page. São combinados antes da paginação,
10 itens, ID crescente. Filtros inválidos retornam 400; páginas inválidas 404;
page=last permanece aceito. A coleção vazia tem count=0/results=[].
O filtro monetário consulta preco, não salários. Parâmetros desconhecidos são
ignorados, inclusive modalidade/cidade/uf/status: **a B47 não acrescenta filtros**.
Filtros de coleção não restringem detalhe nem escrita.

## JSON real validado

Captura via APIClient, com dados sintéticos exclusivamente em SQLite em memória.
POST sem id/empresa gerou 201 e GET de detalhe retornou o mesmo objeto:

```json
{
  "id": 1,
  "empresa": 1,
  "titulo": "Projeto B47",
  "descricao": "Modalidade: Remoto\n\nTexto original.",
  "tag": "Web",
  "preco": "1500.00",
  "tempo": "40",
  "modalidade": "Híbrido",
  "cidade": "São Paulo",
  "uf": "SP",
  "status": "publicada",
  "requisitos": "Vue",
  "beneficios": "Horario flexivel",
  "tipo_contratacao": "PJ",
  "nivel_experiencia": "Pleno",
  "jornada_trabalho": "40h",
  "data_publicacao": "2026-11-09",
  "salario_minimo": "2000.50",
  "salario_maximo": "3500.00"
}
```

A divergência intencional entre modalidade estruturada e prefixo comprova que o
backend não altera descrição nem infere modalidade. O novo campo é a fonte
estruturada; descrições permanecem texto livre. Não há validação de equivalência
entre ambos para não rejeitar clientes e textos antigos.

GET da coleção retornou count=1, next=null, previous=null e results contendo
integralmente o objeto acima. PATCH `{"status":"encerrada"}` retornou 200 com
somente essa mudança. PUT `{"titulo":"Projeto atualizado","preco":"1500.00","tempo":"40"}`
retornou 200 preservando status encerrada, modalidade, cidade, UF e complementos.

PATCH inválido `{"status":"rascunho","uf":"XX","modalidade":"Outro"}` retornou 400:

```json
{
  "status": ["\"rascunho\" não é um escolha válida."],
  "modalidade": ["\"Outro\" não é um escolha válida."],
  "uf": ["\"XX\" não é um escolha válida."]
}
```

As mensagens acima reproduzem a tradução efetiva do DRF na captura.

## Frontend e integração F47

O frontend atual continua enviando modalidade dentro de descricao; esses POSTs
permanecem válidos e o campo novo fica vazio. A allowlist atual do PATCH ainda
não inclui os quatro campos novos. Nenhum arquivo frontend foi alterado.

F47 deve enviar os nomes exatos, incluir os campos na allowlist e preferir
modalidade estruturada quando não vazia, usando o prefixo antigo somente como
fallback visual. Se editar modalidade, deve atualizar o campo estruturado de forma
explícita; editar só descrição não muda modalidade. Não duplicar/reescrever texto
legado automaticamente. Campos novos vazios significam informação não fornecida.

Não usar localização do perfil da empresa como fallback persistido da vaga.
Não expor coordenadas privadas. Status da oportunidade é distinto do status
pendente/aprovada/recusada de uma candidatura. Não usar data como status.
O detalhe profissional consultado ainda não mostra todos os complementos;
a apresentação desses campos é responsabilidade da F47. A Home também precisa
revisar sua mensagem antiga sobre ausência de data na API, considerando que a
data existente é opcional/gravável e não um timestamp automático de criação.

## Migration e preservação dos dados

Nova `0021_freelance_contrato_b47`, dependente de `0020_freelance_complementos`,
contém somente quatro AddField. Migrations anteriores não foram modificadas.
Registros antigos recebem modalidade/cidade/UF vazias. Status publicada preserva
a disponibilidade anterior de todas as vagas; não afirma uma data ou evento
histórico novo. Não há RunPython inferindo conteúdo, dados fictícios de localização,
cópia de GPS, mudança de propriedade ou exclusão de registros.

Plano e SQL foram inspecionados com settings em memória. No SQLite, AddField
com default faz reconstrução interna da tabela (cópia, troca de tabela e recriação
de índice). O teste histórico aplica a migration em banco isolado e compara todos
os valores anteriores, dono e vínculos de candidatura aprovada, favorito e
notificação lida, inclusive vaga sem dono. Nenhum SQL foi aplicado ao banco da equipe.

Aplicar a migration em ambiente persistente somente após revisão e autorização.
Evitar o atalho `pdm run migrate`, que tem hooks de makemigrations e geração de
diagrama no projeto. Coordenar a migration antes de executar o código novo contra
um banco sem as colunas. Não usar settings de testes para migrar o banco real.
Rollback de schema removeria os campos novos e perderia seus valores; não foi
executado em dados persistentes e exige planejamento específico.

## Testes e verificações executados

Ambiente PDM existente, Python 3.13.2, Django 5.2.12; configuração
`core.tests.settings` inspecionada, SQLite exclusivamente em memória. Não houve
instalação de dependências, alteração de lockfile ou uso de credenciais reais.

```powershell
git rev-parse --show-toplevel
git branch --show-current
git status --short
git fetch origin
git rev-list --left-right --count HEAD...origin/DEV
git worktree list
git branch -a
git log --all --oneline --regexp-ignore-case --grep='47\|contrato'
pdm run python -B manage.py makemigrations core --name freelance_contrato_b47 --settings=core.tests.settings
pdm run python -B manage.py test core.tests.test_freelance_contrato_b47 core.tests.test_freelances core.tests.test_freelance_complementos core.tests.test_opportunity_queries --settings=core.tests.settings -v 1
pdm run python -B manage.py test --settings=core.tests.settings -v 1
pdm run python -B manage.py check --settings=core.tests.settings
pdm run python -B manage.py makemigrations --check --dry-run --settings=core.tests.settings
pdm run python -B manage.py migrate --plan --settings=core.tests.settings
pdm run python -B manage.py sqlmigrate core 0021 --settings=core.tests.settings
pdm run python -B manage.py spectacular --validate --settings=core.tests.settings --file "$env:TEMP/b47-schema-final.yaml"
pdm run ruff check core/models/freelance.py core/serializers/freelance.py core/tests/test_freelance_contrato_b47.py core/tests/test_freelance_complementos.py core/tests/test_opportunity_queries.py
pdm run ruff format --check core/models/freelance.py core/serializers/freelance.py core/tests/test_freelance_contrato_b47.py core/tests/test_freelance_complementos.py core/tests/test_opportunity_queries.py
git diff --check
```

Foi aplicado `ruff format` somente nos dois arquivos B47 apontados pelo primeiro
check. A captura JSON final foi um script não interativo enviado a
`pdm run python -B -`: definiu DJANGO_SETTINGS_MODULE=core.tests.settings, conferiu
NAME=:memory:, migrou apenas nessa memória e executou as chamadas APIClient.

| Verificação | Resultado |
|---|---|
| Linha de base anterior desta sessão | 187 testes aprovados, sem alterações B47 |
| Módulos de oportunidades + B47 | 74 aprovados, 3,972 s |
| Suíte completa após implementação | 201 aprovados, 8,357 s |
| Suíte completa após ajuste OpenAPI | 201 aprovados, 8,653 s, zero falhas |
| Django check | Sem problemas |
| Model/migration dry-run | No changes detected |
| Plano e SQL 0021 | Revisados; apenas novos campos, sem aplicação ao banco local |
| Ruff check e format finais | Aprovados; cinco arquivos formatados |
| Captura APIClient | POST 201, GET/lista, PATCH 200, PUT 200 e opções inválidas 400 |
| OpenAPI global final | Código 0, 12 erros (3 únicos) e 12 avisos (7 únicos), preexistentes |

São 14 testes novos: 13 de API/contrato e um de migration. Cobrem POST, PUT,
PATCH, persistência e omissões, limites e formatos inválidos em todos os métodos,
opcionais, todas as modalidades/UFs, todas as transições de status, propriedade,
exclusão, coleção paginada com filtros antigos, schema e efeitos nos consumidores.
As duas asserções anteriores de chaves exatas foram ampliadas para exigir os
quatro campos novos; nenhuma cobertura anterior foi removida ou desabilitada.

Ocorrências e limites reais:

- Os primeiros checks de estilo apontaram formatação/linha longa, corrigidas;
  a verificação final passou.
- A primeira captura manual de JSON teve acentos convertidos pelo pipeline
  PowerShell e falhou na validação. Foi repetida em Python não interativo com
  escapes Unicode e asserts de respostas, com sucesso e código 0.
- O novo enum inicialmente causou colisão de nome com status de candidatura
  no OpenAPI. O campo OpportunityStatusField resolve somente o novo componente,
  sem alterar configurações ou serializers de outras FEATs. O schema isolado
  de oportunidades é testado e a colisão não aparece no schema global final.
- Os diagnósticos globais preexistentes são serializers ausentes para documentação
  de autenticação e inferências de parâmetros/métodos/componentes de outros endpoints.
  Não foram corrigidos fora do escopo; código 0 não significa schema global limpo.
- Aviso staticfiles ausente não impediu testes. Mensagens negativas Google são
  esperadas pela suíte existente.
- Não executados: PostgreSQL, frontend, navegação Swagger, integração publicada
  ou Figma. Não foi conferido o estado de migrations de produção.

## Impactos, diff e arquivos da entrega

| Arquivo | Alteração |
|---|---|
| `core/models/freelance.py` | Quatro campos, escolhas e defaults |
| `core/serializers/freelance.py` | Validação de cidade e status tipado no OpenAPI; exposição via serializer existente |
| `core/migrations/0021_freelance_contrato_b47.py` | Quatro AddField compatíveis com legado |
| `core/tests/test_freelance_contrato_b47.py` | 14 testes novos de integração e migration |
| `core/tests/test_freelance_complementos.py` | Atualiza conjunto exato de chaves esperado |
| `core/tests/test_opportunity_queries.py` | Atualiza conjunto exato de chaves esperado |
| `docs/FEAT-47-contrato-vagas.md` | Diagnóstico, contrato e evidências |

O diff funcional é aditivo. Não houve alteração de views, filtros, endpoints,
permissões, autenticação, configuração global, favoritos, candidaturas, notificações
ou frontend. Os consumidores que compartilham FreelanceSerializer recebem os
quatro campos adicionais em oportunidade_detalhes, sem remover/renomear os anteriores.

- B34: CRUD, empresa proprietária e bloqueio de terceiros preservados e testados.
- B37: pesquisa, filtros, ordenação e paginação preservados e testados.
- F47: contrato pronto para os quatro campos; integração Vue permanece fora do escopo.
- B41/B44: implementação intacta; testes confirmam estados e vínculos preservados.
  Encerramento/cancelamento não bloqueiam novas candidaturas nesta entrega.
- B43: evidências fornecidas; homologação final conjunta e PostgreSQL ainda necessários.
- B45/PR #19: não integrado, sem conflito direto identificado nos arquivos alterados.

Riscos: executar o código sem migration aplicada resulta em colunas ausentes;
consumidores que exigem exatamente 15 chaves precisarão aceitar a evolução aditiva;
clientes antigos podem editar o prefixo sem editar modalidade estruturada, e F47
deve tratar explicitamente essa diferença. Status informativo não pode ser anunciado
como bloqueio de inscrições. Nenhuma dessas integrações foi simulada como publicada.

Pendências operacionais: revisão, autorização de commit/push/PR, integração à DEV
e aplicação coordenada da migration no ambiente adequado. Nenhum teste essencial
está falhando. As alterações preexistentes de core.png, db.sqlite3 e mídia não fazem
parte da B47 e não devem ser incluídas em commit. O schema global e a integração
frontend/produção mantêm as limitações registradas acima.
