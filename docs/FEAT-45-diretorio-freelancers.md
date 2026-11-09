# B45 — Diretório de freelancers: entrega parcial

## A. Diagnóstico inicial

Repositório confirmado por `pwd` e `git rev-parse --show-toplevel`:
`Back_Marujob`, branch `FEAT-45`. O backend usa Django, DRF, SimpleJWT,
DRF Spectacular e módulos `core/models`, `core/views`, `core/serializers`,
`core/tests`. Não foi encontrada implementação anterior de `/api/freelancers/`.

Alterações locais preexistentes preservadas: `.pdm-python`, `.vscode/settings.json`,
`core.png`, `db.sqlite3`, `media/portfolios/image.png`, `media/users/image.png`.

B39 disponível: `core.User`, JWT, grupos `Usuário`/`Empresa` e helper
`core.permissions.account_type`. Grupos são ManyToMany: ambos podem coexistir,
mas o helper retorna `None` para essa combinação. A B45 reutiliza essa decisão.
Grupos adicionais não alteram o tipo quando há apenas um dos dois grupos de conta.

B40 disponível: perfil próprio e portfólios privados do proprietário.
`User` persiste `name` e `profile_image` opcionais, `profissao`, `localizacao`,
`sobre`, `telefone` com padrão vazio, `habilidades` em JSONField (lista validada
nas escritas do perfil), flags de configuração e dados GPS opcionais.
`Portfolio.usuario` aponta para `User`, related_name `portfolios`; projetos têm
título, categoria, descrição, tags JSON, link e imagem opcional.

**Impedimento de privacidade:** não existe campo ou mecanismo de consentimento
para publicação de perfis ou portfólios. A documentação B40, seção de publicação,
registra expressamente essa pendência. `perfil_configurado` indica preenchimento,
não consentimento. `localizacao` é texto livre e pode conter endereço residencial;
não existe campo público de cidade. Autenticação e persistência estão disponíveis,
mas a dependência de divulgação pública não está resolvida.

## B. Implementação realizada

| Arquivo | Alteração |
| --- | --- |
| `core/views/freelancer_publico.py` | ViewSet somente leitura, permissão empresarial, queryset restritivo, paginação e OpenAPI |
| `core/serializers/freelancer_publico.py` | Serializers independentes e validação explícita dos parâmetros |
| `core/tests/test_freelancer_publico.py` | 18 testes de API, segurança, contrato e schema |
| `app/urls.py` | Um import e um registro no router |
| `docs/FEAT-45-diretorio-freelancers.md` | Auditoria, contrato real, validação e pendências |

Sem models, migrations, dependências ou alterações de autenticação.
`/api/freelances/` e as demais rotas existentes foram preservadas.

`FreelancerPublicoListSerializer` permite apenas `id`;
`FreelancerPublicoDetailSerializer` permite `id` e `portfolio` vazio.
Esses contratos mínimos **não tornam nenhum perfil elegível**. Nome, profissão,
habilidades, foto e descrição aguardam política de publicação; localização livre
não pode ser promovida automaticamente a cidade pública.

## C. Contrato efetivamente implementado

Todas as requisições exigem `Authorization: Bearer <access JWT>` e tipo inequívoco
`empresa`, determinado no banco pelo helper B39. Um superusuário sem tipo Empresa
não recebe exceção de acesso. Tokens usam a autenticação global existente.

### GET /api/freelancers/

Empresa autenticada: HTTP 200, inclusive havendo perfis completos no banco:

```json
{"count":0,"next":null,"previous":null,"results":[]}
```

Utiliza `PageNumberPagination`, padrão global de 10 registros por página,
sem `page_size` configurável. Ordenação por ID. Queryset vazio deliberado:
nenhum perfil possui autorização comprovada; não carrega perfis/portfólios.

| Parâmetro | Validação e comportamento atual |
| --- | --- |
| `search` | Até 255 caracteres, reservado; não vazio retorna 400 |
| `profissao` | Até 255 caracteres, reservado; não vazio retorna 400 |
| `habilidade` | Até 100 caracteres, reservado; não vazio retorna 400 |
| `cidade` | Até 255 caracteres, reservado; não vazio retorna 400 |
| `page` | Inteiro entre 1 e 1000000; padrão 1; página inexistente retorna 404 |

Espaços externos e consecutivos são normalizados nos filtros; filtros vazios são
aceitos. Filtros repetidos, parâmetros desconhecidos, `ordering`, `page_size` e
`page` vazio ou inválido retornam 400. Filtros combinados não vazios também retornam
400, com erro por campo. Não há busca operacional ou filtragem profissional
implementada: rejeitar explicitamente evita aparentar suporte ou pesquisar dados
que ainda não têm autorização de divulgação. Não há SQL manual.

GET `/api/freelancers/?habilidade=Python` retorna HTTP 400:

```json
{"habilidade":["Filtro indisponível até a definição e implementação da divulgação autorizada."]}
```

### GET /api/freelancers/{id}/

Empresa autenticada recebe HTTP 404 para qualquer ID, existente ou não.
O `get_object()` do DRF consulta exclusivamente o queryset restritivo:
não procura no conjunto completo de usuários antes de ocultar o resultado.
O corpo contém apenas `detail`, com mensagem padrão traduzida do DRF.
Não existe exemplo honesto de resposta 200 deste endpoint nesta entrega.

Contrato unitário do serializer de detalhe, **não uma resposta HTTP disponível**:

```json
{"id":42,"portfolio":[]}
```

Ambas as rotas: sem JWT, inválido, expirado ou conta inativa: 401;
freelancer, conta sem tipo ou com ambos os grupos: 403. Escrita por empresa:
405. A definição OpenAPI identifica a entrega parcial, os parâmetros, os códigos
e o bloqueio atual; aparece no schema/documentação existentes.

## D. Segurança

Nenhum perfil é exposto, incluindo empresas, contas administrativas, inativas,
sem grupo, com ambos os grupos ou freelancers com perfil configurado.
Nenhum campo pessoal/profissional é publicado enquanto faltar autorização.
Serializers públicos não herdam dos serializers privados e usam lista explícita.
Não retornam e-mail, telefone, senha, privilégios, grupos, permissões, tokens,
Google ID, login, coordenadas, precisão, timestamps GPS ou endereço residencial.

Portfólios são sempre omitidos da API: não há consultas nem acesso ao storage.
O contrato de detalhe mantém `portfolio: []`, mesmo quando aplicado isoladamente
a um usuário com projetos. Não foi inventado serializer de projeto público sem
campos autorizados. A privacidade das URLs de mídia preexistentes é assunto
pendente da B40; esta entrega não altera storage nem divulga URLs.

## E. Testes e verificações

Ambiente usa bibliotecas locais, sem instalar dependências:

```powershell
$env:PYTHONPATH = "$PWD\__pypackages__\3.13\lib"
python manage.py check
python manage.py check --settings=core.tests.settings
python manage.py test core.tests.test_freelancer_publico --settings=core.tests.settings --noinput
python manage.py test --settings=core.tests.settings --noinput
& ./__pypackages__/3.13/Scripts/ruff.exe check app/urls.py core/views/freelancer_publico.py core/serializers/freelancer_publico.py core/tests/test_freelancer_publico.py
git diff --check
git status --short
git diff --stat
```

Banco de testes SQLite exclusivamente em memória via settings já existentes.
Nenhuma migration foi aplicada ao banco da aplicação.

A primeira execução B45 encontrou uma falha real em `page=` vazio (tratamento
HTML do QueryDict pelo DRF); validação explícita corrigida. A suíte completa
posterior passou: **205 testes**, incluindo **18 B45** e regressões de autenticação,
usuários, portfólios e demais módulos. Checks Django sem problemas.

Avisos existentes: pasta `staticfiles` ausente e inferência OpenAPI de tipos,
querysets e componentes em outros módulos. Não são falhas dos testes.
`python -m ruff` não encontrou o binário; foi utilizado o executável já instalado
em `__pypackages__/3.13/Scripts/ruff.exe`, sem instalação.

Cobertura B45: JWT real válido/inválido/expirado, inativação após emissão,
grupos ambíguos, listagem paginada vazia, detalhes ocultos, campos opcionais,
privacidade, portfólio não divulgado, filtros indisponíveis, parâmetros repetidos,
desconhecidos, vazios e limites, read-only, rotas antigas e schema.
A listagem executa duas consultas (JWT e grupos), sem consultas de perfis/projetos.

Não há testes de sucesso de detalhes, busca, filtros com resultados, projetos
publicados ou segunda página com registros: esses comportamentos não foram
implementados por falta de autorização/modelagem. Não foram simulados como
funcionalidades concluídas.

## F. Pendências e critérios de aceite

- [x] Isolamento do backend e preservação dos contratos B39/B40.
- [x] JWT e bloqueio de acesso não empresarial, incluindo contas ambíguas.
- [x] Serializers dedicados e não divulgação de dados e portfólios privados.
- [x] Estrutura de paginação, documentação, testes e regressão.
- [ ] Definir campos públicos aprovados e autorização revogável de perfil.
- [ ] Implementar mecanismo de elegibilidade aprovado; substituir o queryset vazio.
- [ ] Definir cidade pública separada de endereço livre/GPS.
- [ ] Implementar busca e filtros sobre dados autorizados (habilidades são JSON).
- [ ] Listar freelancers reais e consultar seus detalhes autorizados.
- [ ] Validar primeira/segunda páginas com registros, ordem e filtros cumulativos.
- [ ] Aprovar publicação explícita por projeto e regras de mídia da B40.
- [ ] Implementar e testar retorno de projetos autorizados e exclusão de privados.

Frontend: não apresentar filtros reservados como funcionais nem interpretar lista
vazia como inexistência de freelancers cadastrados. A liberação exige novo acordo
de contrato; não consumir os serializers privados para preencher lacunas.
Possível conflito de integração restrito ao registro em `app/urls.py`; arquivos
de usuário, permissões compartilhadas, models e portfólios permanecem intactos.

## G. Estado final do Git

Branch `FEAT-45`. Escopo B45: quatro arquivos novos (view, serializers, testes,
documentação) e somente duas linhas adicionadas em `app/urls.py`.
O `git diff --stat` padrão não inclui arquivos novos não rastreados; inclui
alterações locais preexistentes que não pertencem à B45.
Na entrega inicial, sem commit, push, merge, rebase, PR ou deploy.
Posteriormente o usuário autorizou commit, envio da branch e abertura de PR para
`DEV`, mantendo a identificação de entrega parcial. Merge, rebase e deploy
continuam fora do escopo. Nenhum arquivo de frontend alterado.

**Entrega parcial para revisão: o diretório operacional permanece bloqueado pela
ausência de autorização de publicação. Não considerar a B45 concluída.**
