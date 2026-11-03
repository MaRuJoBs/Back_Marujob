# FEAT-37 — API de oportunidades, pesquisa, filtros e paginação

## A. Diagnóstico inicial

Auditoria e validação realizadas em 03/11/2026 exclusivamente no repositório Git
Back_Marujob. A raiz foi confirmada com `pwd` e `git rev-parse --show-toplevel`.
O status inicial já continha alterações em `.pdm-python`, `.vscode/settings.json`
e `db.sqlite3`; esses arquivos foram preservados e não fazem parte da implementação.
Nenhum AGENTS.md foi encontrado dentro do repositório.

| Requisito | Estado inicial e decisão |
| --- | --- |
| CRUD, empresa proprietária e JWT (FEAT-34) | Implementados; preservados |
| Listagem e detalhes por ID | Implementados; serializer compartilhado já retorna os 15 campos atuais |
| Pesquisa por título | Implementada com SearchFilter do DRF; preservados parser e limites de segurança |
| Categoria | Modelo possui `tag` como texto livre; filtro existente por `tag` preservado |
| Preço mínimo/máximo | Implementados, inclusivos e validados; preservados |
| Tipo de contratação e nível | Campos com escolhas existentes, filtros ausentes; acrescentados |
| Paginação | PageNumberPagination global, 10 itens, `id` crescente; preservada |
| Candidaturas e notificações (FEAT-41/44) | Presentes, com isolamento por usuário/propriedade e decisões de aprovação/recusa; preservadas |
| Documentação | Exemplos omitiam os campos complementares; referências de testes/ambiente estavam antigas; atualizadas |
| Modalidade, localização da oportunidade e status de publicação | Não são campos do modelo; não criados nem inferidos da descrição ou da empresa |

`data_publicacao` é uma data opcional gravável, sem regra existente de agendamento
ou visibilidade. Datas nulas/futuras não ocultam oportunidades. Não existem rascunho,
flag de disponibilidade ou vagas privadas no modelo. Todos os usuários autenticados
podem consultar os registros, inclusive oportunidades legadas sem empresa.

`jornada_trabalho` e `tempo` são textos livres sem valores padronizados. Não foram
criados novos filtros para esses textos, requisitos, benefícios ou data; os filtros
adicionais usam as escolhas já definidas pelo modelo. O filtro monetário existente
continua aplicado exclusivamente a `preco`, sem reinterpretar a faixa salarial.

Não foi encontrado defeito nas funcionalidades anteriores: os 174 testes da suíte
preexistente passaram antes das alterações. A consulta de oportunidades não serializa
candidaturas, notificações nem dados privados da conta empresarial.

## B. Arquivos modificados

| Arquivo | Finalidade |
| --- | --- |
| `core/views/freelance.py` | Dois filtros validados pelas escolhas do modelo; documentação OpenAPI dos filtros de listagem; nomes para os limites de pesquisa existentes, preservando seus valores |
| `core/tests/test_opportunity_queries.py` | 13 testes adicionais de integração, totalizando 29 neste módulo |
| `docs/FEAT-37-oportunidades.md` | Contrato atual, exemplos completos, diagnóstico e evidências desta execução |

Não foram alterados models, serializers de respostas, rotas, permissões, grupos,
configuração global, dependências, lockfile, infraestrutura ou produção. Nenhuma
migration foi criada ou aplicada ao banco da aplicação.

## C. Endpoints disponíveis

Todas as operações de oportunidades exigem `Authorization: Bearer <access>`.

| Método | URL | Autorização e resultado esperado |
| --- | --- | --- |
| GET | `/api/freelances/` | Autenticados; 200 com coleção paginada |
| GET | `/api/freelances/{id}/` | Autenticados; 200 ou 404 |
| POST | `/api/freelances/` | Grupo Empresa; 201; proprietário definido pelo servidor |
| PUT | `/api/freelances/{id}/` | Empresa proprietária; 200; exige campos obrigatórios |
| PATCH | `/api/freelances/{id}/` | Empresa proprietária; 200; atualização parcial |
| DELETE | `/api/freelances/{id}/` | Empresa proprietária; 204 |

Sem JWT válido: 401. Escrita sem papel/propriedade: 403. Oportunidades sem empresa
continuam legíveis e não podem ser modificadas pela API. O cliente não pode transferir
a propriedade enviando `empresa` no corpo.

Autenticação existente: POST `/api/token/`, `/api/token/refresh/` e
`/api/token/verify/`. A obtenção recebe email/senha; refresh e verify recebem seus
tokens no corpo, conforme Simple JWT. OpenAPI: GET `/api/schema/`; Swagger:
GET `/api/doc/`; ReDoc: GET `/api/redoc/`. Os filtros constam na operação de listagem.

Integrações existentes, também autenticadas e sem alterações nesta entrega:

- Candidaturas: GET/POST `/api/candidaturas/`, GET `/api/candidaturas/{id}/`;
  criação por freelancer, leitura conforme candidato/empresa proprietária.
- Decisões: POST `/api/candidaturas/{id}/aprovar/` e `/recusar/`, somente empresa
  proprietária. Decisão oposta a um estado final mantém a resposta 409 existente.
- Notificações: GET `/api/notificacoes/`, GET `/api/notificacoes/{id}/` e
  PATCH `/api/notificacoes/{id}/marcar-lida/`, somente empresa autorizada.
- Favoritos: GET/POST `/api/favoritos/` e DELETE `/api/favoritos/{id}/`,
  sempre restritos ao usuário autenticado.

## D. Pesquisa e filtros

Os parâmetros abaixo restringem somente GET da coleção. Não afetam detalhes nem
operações de escrita. São combinados com AND no banco antes da paginação.

| Parâmetro | Descrição | Exemplo |
| --- | --- | --- |
| `search` | Pesquisa parcial apenas no título, usando o parser do DRF | `?search=python` |
| `tag` | Igualdade do texto completo da tag, sem distinção de caixa conforme o banco | `?tag=tecnologia` |
| `preco_min` | Limite inferior inclusivo de `preco` | `?preco_min=1000.00` |
| `preco_max` | Limite superior inclusivo de `preco` | `?preco_max=5000.00` |
| `tipo_contratacao` | Escolha exata do modelo | `?tipo_contratacao=PJ` |
| `nivel_experiencia` | Escolha exata do modelo, incluindo acentos | `?nivel_experiencia=Pleno` |
| `page` | Página, padrão 1; aceita também `last` | `?page=2` |

Escolhas aceitas:

- `tipo_contratacao`: `CLT`, `PJ`, `Autônomo`, `Temporário`, `Estágio`, `Outros`.
- `nivel_experiencia`: `Iniciante`, `Júnior`, `Pleno`, `Sênior`, `Especialista`.

Pesquisa: até 200 caracteres recebidos e 20 termos interpretados pelo SearchFilter.
Espaços/vírgulas separam termos combinados com AND; aspas agrupam expressões.
Exceder os limites retorna 400. `search` vazio/somente espaços não restringe.
Caracteres especiais de SQL são tratados como texto. Não há remoção de acentos.
Comparação sem distinção de caixa depende do banco/collation: no SQLite, diferenças
de caixa em caracteres acentuados podem impedir correspondência. Não foi adicionada
normalização Unicode, nem foi validado PostgreSQL nesta execução.

`tag` tem limite de 50 caracteres, remove espaços externos e ignora valor vazio.
Tag inexistente retorna coleção vazia com 200. Não há relação de categorias nem
parâmetro `categoria`; consumidores devem continuar usando `tag`.

Preços: de 0 a 99999999.99, até duas casas decimais. Valores vazios, não numéricos,
negativos, não finitos, com precisão excessiva ou faixa invertida retornam 400.
Limite ausente não restringe; zero é aplicado normalmente. Não são filtros de
`salario_minimo`/`salario_maximo`, que continuam campos independentes da resposta.

Novas escolhas: vazio não restringe; opções inexistentes, com caixa/acentos diferentes
ou espaços adicionais retornam 400. Uma escolha válida sem correspondências retorna
200 com coleção vazia. Parâmetros repetidos usam o último valor, preservando o
comportamento anterior. Parâmetros desconhecidos são ignorados, inclusive
`categoria`, `modalidade`, `status` e `page_size`; não devem ser usados como filtros.

## E. Estruturas JSON

Exemplos ilustrativos dos campos reais do serializer, sem inclusão de dados artificiais
nas respostas da aplicação. O tamanho de página continua 10; uma coleção de um item:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "titulo": "Designer",
      "descricao": null,
      "tag": "design",
      "preco": "100.00",
      "tempo": "1 dia",
      "requisitos": "",
      "beneficios": "",
      "tipo_contratacao": "PJ",
      "nivel_experiencia": "Pleno",
      "jornada_trabalho": "",
      "data_publicacao": null,
      "salario_minimo": null,
      "salario_maximo": null,
      "empresa": 2
    }
  ]
}
```

Detalhe por ID (200), com os mesmos 15 campos:

```json
{
  "id": 1,
  "titulo": "Designer",
  "descricao": null,
  "tag": "design",
  "preco": "100.00",
  "tempo": "1 dia",
  "requisitos": "",
  "beneficios": "",
  "tipo_contratacao": "PJ",
  "nivel_experiencia": "Pleno",
  "jornada_trabalho": "",
  "data_publicacao": null,
  "salario_minimo": null,
  "salario_maximo": null,
  "empresa": 2
}
```

`empresa` é somente o ID e pode ser null em registros legados. `descricao` e `tag`
também aceitam null. Os textos complementares ausentes retornam `""`, datas usam
`YYYY-MM-DD` ou null, e valores monetários retornam strings com duas casas decimais
ou null quando opcionais. Dados de candidatos, telefone e credenciais não integram
a resposta. Informações públicas adicionais da empresa não têm objeto aninhado
neste contrato; o vínculo existente por ID foi preservado.

Sem resultados (200):

```json
{"count": 0, "next": null, "previous": null, "results": []}
```

Filtros inválidos, exemplo com `preco_min=2&preco_max=1` (400):

```json
{"preco_max": ["Deve ser maior ou igual a preco_min."]}
```

Escolhas inválidas e outros erros de validação também retornam listas de mensagens
por parâmetro. O texto padrão é localizado pelo DRF. JWT inválido, escrita proibida,
ID inexistente e página inválida usam `{"detail": "..."}`, com 401, 403 e 404 conforme
o caso. Páginas zero, negativas, não numéricas e fora do intervalo retornam 404.
Página 1 de uma coleção vazia retorna 200.

## F. Testes executados

Ambiente PDM existente: versão 2.24.2, Python 3.13, Django 5.2.12 e DRF 3.16.1.
Não foi necessário instalar dependências. Todos os comandos Python foram executados
com `pdm run`, usando `core.tests.settings`: SQLite exclusivamente em memória.
A configuração de produção e o banco local não foram alterados.

```powershell
pdm run python -B manage.py check --settings=core.tests.settings
pdm run python -B manage.py test core.tests.test_opportunity_queries core.tests.test_freelances core.tests.test_freelance_complementos --settings=core.tests.settings -v 1
pdm run python -B manage.py test core.tests.test_opportunity_queries --settings=core.tests.settings -v 2
pdm run python -B manage.py test --settings=core.tests.settings -v 1
pdm run python -B manage.py makemigrations --check --dry-run --settings=core.tests.settings
pdm run ruff check core/views/freelance.py core/tests/test_opportunity_queries.py
pdm run ruff format --check core/views/freelance.py core/tests/test_opportunity_queries.py
git diff --check
git diff --stat
git status --short
```

| Execução | Resultado |
| --- | --- |
| Oportunidades antes da alteração | 47 testes aprovados |
| Suíte completa antes da alteração | 174 testes aprovados |
| Consultas após os novos filtros | 29 testes aprovados, incluindo 13 novos |
| Suíte completa final | 187 testes aprovados, zero falhas |
| Django check | Sem problemas |
| Models/migrations, somente check/dry-run | Nenhuma alteração pendente |
| Ruff dos dois arquivos Python alterados | Sem erros; formatação aprovada |
| Revisão de diff | Sem erros de whitespace |

Os novos testes cobrem todas as escolhas do modelo, parâmetros vazios/inválidos,
combinação dos seis filtros com três páginas (10/10/1), links que preservam os
parâmetros, ausência de duplicatas, última página, repetição de parâmetros,
desconhecidos, tag longa, pesquisa acentuada, dados opcionais nulos, datas futuras,
JWT real de empresa/freelancer, preservação do CRUD e contrato OpenAPI.

A suíte completa inclui regressões de FEAT-34, favoritos, complementos das vagas,
FEAT-41, FEAT-44, autenticação e perfis/portfólios. Criação/edição autorizadas,
propriedade, grupos, aprovação/recusa e privacidade continuam cobertos pelos testes
existentes. Nenhum teste falhou. A primeira execução de lint apontou dois números
literais preexistentes na pesquisa; foram nomeados sem alterar os limites, e a
validação final passou.

O teste de consultas SQL confirma duas consultas na listagem (contagem e página)
e uma no detalhe, com autenticação forçada para isolar o custo da consulta de vagas.
Não existe N+1 de empresa: apenas a chave estrangeira é serializada, portanto não
foi necessário adicionar joins ou prefetch. A autenticação JWT acrescenta seu próprio
custo, fora dessa contagem isolada.

Limitações: testes em SQLite, sem comprovação de collation/desempenho no PostgreSQL.
Aviso preexistente não impeditivo de diretório `staticfiles/` ausente. Mensagens de
credenciais Google rejeitadas são esperadas nos testes negativos de autenticação.
Não há falhas de teste pendentes identificadas.

## G. Integração frontend

Enviar JWT no cabeçalho de cada consulta. Usar GET `/api/freelances/` e consumir
`results`, `count`, `next` e `previous`. Seguir diretamente os links de navegação,
que preservam filtros/pesquisa; `null` indica ausência de página seguinte/anterior.
A ordenação é sempre `id` crescente e não muda com os filtros. A paginação por número
pressupõe conjunto estável: alterações concorrentes dos registros podem deslocar
itens entre requisições, como no contrato anterior.

Exemplo de consulta combinada:

```http
GET /api/freelances/?search=designer&tag=design&preco_min=100&preco_max=500&tipo_contratacao=PJ&nivel_experiencia=Pleno&page=2
Authorization: Bearer <access>
```

Construir parâmetros com codificação de URL, especialmente espaços e acentos.
Enviar as escolhas exatamente como documentadas. Na interface de categoria, usar
`tag`, que é texto livre; não existe endpoint de catálogo de categorias. `preco` é
o pagamento existente, e a faixa salarial opcional deve ser exibida separadamente.
Renderizar detalhes via GET `/api/freelances/{id}/` e tratar strings vazias/nulls.
Não enviar filtros da coleção para restringir o detalhe. Tratar 400 como validação,
401 como autenticação, 403 como falta de permissão e 404 como ID/página inexistente.
Nenhum arquivo do frontend foi acessado ou modificado nesta execução.

## H. Resultado final

**CONCLUÍDA**, para os requisitos aplicáveis ao modelo atual: consulta, detalhes,
pesquisa, tag, preço, novos filtros e paginação combinada validados; permissões e
integrações preservadas, com 187 testes aprovados. Modelos sem modalidade/status
não receberam campos ou regras artificiais. Nenhuma regressão conhecida na suíte.

A revisão final limita a entrega aos três arquivos indicados. Alterações iniciais
do usuário em `.pdm-python`, `.vscode/settings.json` e `db.sqlite3` foram preservadas.
Não houve acesso ao Front_marujob, criação de arquivos de frontend, dependências,
migrations novas, mudanças de produção, troca de branch, merge, rebase ou deploy.

Após a validação, o usuário autorizou commit, push e abertura de PR da branch
`FEAT-37` para `DEV`, incluindo somente os três arquivos desta entrega e preservando
as alterações locais preexistentes.
