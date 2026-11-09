# FEAT-45 — Diretório de freelancers e perfis públicos

## Diagnóstico e solução

Branch `FEAT-45`, repositório `MaRuJoBs/Back_Marujob`, PR existente #19 para `DEV`.
A implementação anterior retornava queryset vazio e rejeitava filtros preenchidos,
pois B39/B40 não possuíam autorização de publicação. Esta revisão implementa essa
autorização explicitamente e mantém usuários/projetos existentes privados.

Reutiliza JWT/SimpleJWT e `account_type` da B39, edição do perfil próprio e CRUD de
portfólio da B40, paginação DRF de 10 itens e as duas rotas já registradas.
Não cria endpoints duplicados nem modifica `/api/freelances/`.

## Autorizar e revogar o perfil

Bearer access JWT obrigatório. O próprio freelancer de tipo inequívoco `Usuário`,
sem privilégios administrativos, pode usar o endpoint existente:

```http
PATCH /api/usuarios/me/
Content-Type: application/json
Authorization: Bearer <access>
```

```json
{"perfil_publico":true,"cidade_publica":"Joinville"}
```

O GET e o PATCH de `/api/usuarios/me/` retornam os campos antigos e os dois novos.
`cidade_publica` aceita até 120 caracteres, pode ficar vazia e normaliza espaços.
Nunca é preenchida a partir de `localizacao` ou coordenadas. A cidade é declarada
pelo proprietário: não há consulta a cadastro de municípios ou geolocalização.
Tentativas de editar esses campos por empresa, conta ambígua/sem grupo ou
administrativa retornam 400 por campo. As demais edições privadas continuam
seguindo B39/B40. A rota `/me/` sempre edita apenas a conta autenticada.

`perfil_publico=true` autoriza divulgar nome (`name`), profissão, cidade pública,
habilidades, descrição (`sobre`), foto de perfil e projetos marcados públicos.
Esses campos refletem as futuras edições do perfil enquanto publicado.
`perfil_configurado` mantém a semântica antiga e não concede publicação.
Campos opcionais vazios não impedem a publicação; foto e nome podem ser null.

Revogação imediata nas próximas consultas do diretório:

```json
{"perfil_publico":false}
```

Não há cache de perfis públicos. Revogar o perfil também impede a consulta dos
seus projetos pelo diretório, mesmo quando os projetos continuam marcados públicos.
A revogação não apaga dados e não desfaz cópias já recebidas por uma empresa.

## Publicar projetos

Use os endpoints privados existentes, com JWT do proprietário freelancer:

- POST `/api/portfolios/`: novo campo opcional `publico`, padrão false.
- PATCH/PUT `/api/portfolios/{id}/`: `publico: true` publica; false revoga.
- GET e listagem privados retornam os campos antigos e `publico`.
- DELETE mantém o comportamento B40.

Exemplo de PATCH:

```json
{"publico":true}
```

B40 já restringe escrita a freelancer e queryset ao proprietário: outro freelancer
recebe 404, empresa recebe 403 em escrita. Informar `usuario` de terceiros não
altera o proprietário. Publicar projeto não publica automaticamente o perfil.
JSON e multipart continuam suportados, incluindo flags true/false textuais.

## Diretório empresarial

Ambas as rotas exigem JWT válido e tipo inequívoco Empresa conforme `account_type`.
Contas com ambos os grupos `Usuário`/`Empresa` não têm tipo inequívoco. Grupos
adicionais sem esses nomes não impedem a classificação já estabelecida na B39.

```http
GET /api/freelancers/?search=ana&cidade=Joinville&habilidade=Python
GET /api/freelancers/{id}/
```

Somente usuários com `perfil_publico=true`, ativos, pertencentes a `Usuário`,
sem grupo `Empresa`, `is_staff=false` e `is_superuser=false` são consultados.
A elegibilidade é aplicada no queryset antes da busca por ID e dos filtros.

### Busca, filtros e paginação

| Parâmetro | Regra |
| --- | --- |
| `search` | Nome, correspondência parcial literal, até 255 caracteres |
| `profissao` | Profissão, correspondência parcial literal, até 255 caracteres |
| `habilidade` | Elemento inteiro da lista JSON, até 100 caracteres |
| `cidade` | Igualdade com `cidade_publica`, até 120 caracteres |
| `page` | Inteiro entre 1 e 1000000, padrão 1; 10 resultados por página |

Comparações não distinguem caixa. Espaços externos e consecutivos dos filtros são
normalizados; filtros vazios não restringem resultados. Todos os filtros são
cumulativos e aplicados no banco antes da contagem e paginação. Ordem estável por
ID, sem repetições de contas, inclusive com grupos extras ou habilidades repetidas.
Sem resultados: 200 com count 0. Página inexistente: 404. Parâmetros desconhecidos,
repetidos, maiores que os limites e página inválida/vazia: 400. Não há `ordering`
ou `page_size` arbitrários. Os filtros são documentados para a listagem.

Busca textual usa ORM `iregex` com valores escapados; expressões fornecidas pelo
cliente são literais. Habilidades usam expressão ORM própria com SQL fixo por
backend e valores vinculados: SQLite `json_each` e PostgreSQL `jsonb_array_elements`.
A expressão exige array e elemento string; objetos, arrays aninhados, números e
strings JSON isoladas não são tratados como listas de habilidades. `Python` não
corresponde a `Pythonista`; símbolos como `C++` e `Vue.js` são literais. As funções
seguem as referências oficiais de [SQLite](https://www.sqlite.org/json1.html) e
[PostgreSQL](https://www.postgresql.org/docs/17/functions-json.html).
Não há filtragem de usuários em memória ou interpolação de valores do cliente no SQL.
Backends cobertos: SQLite e PostgreSQL, conforme dependências existentes. A comparação
Unicode no PostgreSQL segue a collation configurada no banco; testes executáveis
locais cobrem SQLite e a compilação SQL PostgreSQL, sem homologação em servidor PostgreSQL.

### Resposta de listagem

Exemplo ilustrativo compatível com o contrato implementado:

```json
{
  "count":1,
  "next":null,
  "previous":null,
  "results":[{
    "id":12,
    "nome":"Ana Silva",
    "profissao":"Designer",
    "cidade":"Joinville",
    "habilidades":["Python","Figma"],
    "foto_perfil":null
  }]
}
```

### Resposta de detalhe

```json
{
  "id":12,
  "nome":"Ana Silva",
  "profissao":"Designer",
  "cidade":"Joinville",
  "habilidades":["Python","Figma"],
  "foto_perfil":null,
  "descricao":"Design e desenvolvimento de interfaces.",
  "portfolio":[{
    "id":3,
    "titulo":"Sistema de gerenciamento",
    "categoria":"Design",
    "descricao":"Projeto autorizado pelo proprietário.",
    "tags":["Figma"],
    "link":"https://example.com",
    "imagem":null
  }]
}
```

Os IDs e textos dos exemplos não são dados reais. Imagens usam o storage/contexto
da requisição como na B40; imagem ausente retorna null e URLs locais podem ser
absolutas. Portfólio sem projetos publicados retorna `[]`.

### HTTP e privacidade

- 200: empresa autorizada, listagem ou detalhe elegível.
- 400: query params inválidos ou edição inválida nos endpoints privados.
- 401: JWT ausente, inválido, expirado ou conta autenticada inativa.
- 403: acesso ao diretório por freelancer ou conta sem tipo empresarial inequívoco.
- 404: perfil privado, inexistente ou inelegível; página inexistente.
- 405: tentativa de escrita nos endpoints do diretório.

Serializers públicos são independentes dos privados, com allowlist explícita:
`FreelancerPublicoListSerializer`, `FreelancerPublicoDetailSerializer` e
`PortfolioPublicoSerializer`. Não incluem e-mail, telefone, senha, Google ID,
localização privada, GPS, grupos, permissões, dados administrativos ou tokens.
Projetos públicos nunca incluem dados internos do proprietário ou flag de publicação.
Detalhe faz prefetch somente de projetos autorizados, ordenados por ID; listagem
não consulta projetos. Testes verificam quatro queries por listagem/detalhe com JWT.

O diretório restringe a divulgação de links de imagens; a proteção direta de URLs
já conhecidas continua dependendo do storage da B40. Despublicação não invalida
links de mídia anteriormente compartilhados. Nenhuma alteração de storage está
incluída nesta revisão.

Schema/Swagger existentes em `/api/schema/` e `/api/doc/` refletem o contrato final,
os campos adicionados aos serializers privados e as regras de acesso.

## Migration e compatibilidade

Migration gerada pelo Django: `0021_publicacao_perfil_portfolio`, dependente de
`0020_freelance_complementos`, sem alteração de migrations antigas:

- `User.perfil_publico`: boolean, default false.
- `User.cidade_publica`: texto de até 120 caracteres, default vazio.
- `Portfolio.publico`: boolean, default false.

Nenhum dado privado é copiado ou publicado automaticamente. Migration testada em
banco exclusivamente em memória: registros anteriores mantêm dados e permanecem
privados. Nenhuma migration foi executada no banco de desenvolvimento/produção.
É necessário aplicar a migration em ambiente autorizado antes de utilizar a versão
nova; o código novo depende dessas colunas. Frontend pode integrar os campos novos
nos endpoints existentes, sem nova API de edição.

Arquivos alterados: models de usuário/portfólio, serializers privados correspondentes,
serializers/view/testes B45 e esta documentação. Novos: `core/freelancer_filters.py`
e `core/migrations/0021_publicacao_perfil_portfolio.py`. Autenticação, router, vagas,
favoritos, candidaturas e notificações não foram alterados nesta revisão.

## Validação

Bibliotecas locais já instaladas, sem novas dependências:

```powershell
$env:PYTHONPATH = "$PWD\__pypackages__\3.13\lib"
python manage.py check
python manage.py makemigrations --check --dry-run --settings=core.tests.settings
python manage.py test core.tests.test_freelancer_publico --settings=core.tests.settings --noinput
python manage.py test --settings=core.tests.settings --noinput
& ./__pypackages__/3.13/Scripts/ruff.exe check core/freelancer_filters.py core/models/user.py core/models/portfolio.py core/serializers/user.py core/serializers/portfolio.py core/serializers/freelancer_publico.py core/views/freelancer_publico.py core/tests/test_freelancer_publico.py
git diff --check
git status --short
git diff --stat
```

37 testes B45 aprovados, cobrindo JWT, classificação por grupos, exclusões,
publicação/revogação, privacidade em listagem/detalhe, filtros isolados/combinados,
Unicode e metacaracteres literais, formatos JSON legados, páginas consecutivas,
contagem, queries, projetos privados/públicos, CRUD, multipart, imagens, OpenAPI,
compilação PostgreSQL e migration com registros legados. Suíte completa final:
**224 testes aprovados**, incluindo os 37 da B45. Checks Django e migration dry-run
aprovados, sem alterações de model pendentes.

PostgreSQL não foi executado: não há postgres/psql disponíveis e o Docker local
não tem daemon ativo. A consulta PostgreSQL foi compilada e a vinculação de
parâmetros testada, mas isso não substitui homologação em servidor desse banco.
Avisos preexistentes de `staticfiles` ausente e inferência de schema de outros
módulos permanecem; não indicam falhas dos testes.

## Estado da entrega

Implementação funcional pronta para revisão na PR #19, com uso dependente da
aplicação da migration em ambiente autorizado. Após a validação, o usuário
autorizou commit, envio da branch e atualização da PR #19 existente para DEV.
Sem nova PR, merge, rebase ou deploy. Frontend intocado. Alterações locais
preexistentes preservadas: `.pdm-python`, `.vscode/settings.json`, `core.png`,
`db.sqlite3`, `media/portfolios/image.png` e `media/users/image.png`.
