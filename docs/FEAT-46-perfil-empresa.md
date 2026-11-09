# FEAT-46 — Perfil institucional da empresa

Implementada localmente na branch `FEAT-46`, baseada em `origin/DEV`
`a54ee498ae33508129d9cee5064aeb21a8bbb590`, com B39/B40 e B45 integradas.
O PR #19 foi confirmado como merged em 09/11/2026, 17:49:51 UTC.
Histórico de PRs, branches e commits pesquisado: não havia implementação B46.

Implementação e testes realizados inicialmente na worktree isolada
`C:/Users/Ricardo/AppData/Local/Temp/Back_Marujob-FEAT-46`.
A pedido do usuário, a branch FEAT-46 e os oito arquivos da entrega foram depois
trazidos para `C:/Users/Ricardo/Documents/Back_Marujob`, com cópias conferidas por
hash. A worktree temporária foi mantida em detached HEAD com uma cópia dos arquivos.
As alterações preexistentes em core.png, db.sqlite3 e mídia continuam preservadas
na pasta principal e não fazem parte desta entrega.

## Estrutura e privacidade

Novo modelo `EmpresaPerfil`, OneToOne com User, usando empresa como chave primária.
Nome e imagem reutilizam `User.name` e `User.profile_image`; não há cópias dessas
informações. A atualização reutiliza a rotina B40 para manter o cálculo existente
de `perfil_configurado` consistente. Uploads usam ValidatedImageField e
SafeImageStorageMixin existentes, sem novas dependências.

Os seis campos institucionais ficam separados do usuário. Descrição comercial
não é inferida de `sobre`, segmento não é copiado de `profissao`, cidade/UF não
são extraídas de localização/GPS e contato comercial não recebe telefone/e-mail
pessoal. O contato separado é necessário para a empresa informar explicitamente
o canal comercial desejado. Nenhum endpoint público foi criado.

## API para F46

`Authorization: Bearer <access>` obrigatório. Somente contas ativas de tipo
Empresa inequívoco, conforme os grupos existentes, podem consultar e editar.
Usuário anônimo recebe 401; freelancer, conta sem papel ou com ambos os papéis
recebe 403. Não há exceção automática de superusuário.

| Método | Endpoint | Resultado |
|---|---|---|
| GET | `/api/empresas/me/` | 200, perfil da empresa autenticada |
| PATCH | `/api/empresas/me/` | 200, atualização parcial persistida |

HEAD/OPTIONS são suportados; POST/PUT/DELETE retornam 405. Não há seletor de
empresa por ID no endpoint. O JWT determina a proprietária e `empresa` é somente
leitura. Campos desconhecidos/protegidos enviados não são persistidos nem usados
para transferir propriedade. Uma empresa sempre altera exclusivamente sua própria
conta, mesmo se enviar outro ID. Rotas `/api/empresas/{id}/` não foram criadas.

| Campo | Edição e regra |
|---|---|
| `empresa` | ID do User, somente leitura |
| `name` | Nome existente do User; opcional, até 255, aceita vazio/null |
| `profile_image` | Imagem existente do User; opcional; retorna URL ou null |
| `descricao_institucional` | Texto opcional até 2000 |
| `area_atuacao` | Texto opcional até 120 |
| `cidade` | Texto opcional até 100, sem inferência geográfica |
| `uf` | Sigla brasileira exata em maiúsculas ou vazio |
| `website` | URL HTTP/HTTPS válida, até 200, ou vazio; FTP rejeitado |
| `contato_comercial` | Texto comercial explícito até 255; pode conter e-mail, telefone ou outro canal |

Os seis campos institucionais aceitam ausência e `""`, não null. Campos omitidos
no PATCH preservam os valores atuais. `""` limpa texto. UF reutiliza as 27 escolhas
já integradas no projeto; não normaliza caixa silenciosamente. Não há validação
externa de existência da cidade, website ou titularidade de contato.

GET de empresa antiga sem EmpresaPerfil retorna os defaults vazios e os dados
existentes de nome/imagem, sem criar registros. O primeiro PATCH válido cria o
perfil. PATCH inválido não cria linha nem salva parcialmente o nome. A atualização
de User e EmpresaPerfil é transacional, com bloqueio do User existente para
serializar a criação/edição no PostgreSQL.

Exemplo real de GET em teste isolado, antes do primeiro PATCH:

```json
{
  "empresa": 1,
  "name": "Empresa Exemplo",
  "profile_image": null,
  "descricao_institucional": "",
  "area_atuacao": "",
  "cidade": "",
  "uf": "",
  "website": "",
  "contato_comercial": ""
}
```

Payload PATCH validado, sem empresa/profile_image:

```json
{
  "name": "Empresa Digital",
  "descricao_institucional": "Desenvolvimento de software.",
  "area_atuacao": "Tecnologia",
  "cidade": "Joinville",
  "uf": "SC",
  "website": "https://example.com",
  "contato_comercial": "comercial@example.com"
}
```

A resposta 200 contém esses valores, mais `empresa: 1` e `profile_image: null`.
GET posterior retornou exatamente a representação persistida. Não são incluídos
e-mail pessoal, telefone pessoal, senha, tokens, privilégios, grupos ou GPS.

Erros de validação retornam 400 por campo. Captura real de UF/website inválidos:

```json
{"uf":["\"XX\" não é um escolha válida."],"website":["Insira um URL válido."]}
```

As mensagens reproduzem a localização efetiva do DRF. Erros de autenticação e
permissão usam `{"detail":"..."}`. F46 deve manter o formulário após 400/503,
associar erros por campo e atualizar sua representação com a resposta 200.

### Logotipo

Enviar o arquivo no campo `profile_image` por PATCH multipart/form-data, junto
dos textos desejados. JPEG/PNG/WebP são validados por conteúdo e pelo limite
MAX_IMAGE_UPLOAD_BYTES já existente (5 MiB por padrão), com proteção contra
dimensões excessivas. Não enviar URL externa para simular upload.
Para remover a referência, usar JSON `{"profile_image":null}`.
Falha de armazenamento retorna 503 genérico e desfaz alterações de banco da
operação. Arquivos antigos não são apagados automaticamente, conforme B40;
transações de banco não tornam o storage de arquivos transacional.

## Migration

`0022_empresa_perfil`: somente CreateModel da nova tabela, sem backfill ou
alteração de User/Portfolio. Depende das duas folhas integradas
`0021_freelance_contrato_b47` e `0021_publicacao_perfil_portfolio`, unindo o grafo
sem editar migrations anteriores. Também declara a dependência do User configurado.
O SQL SQLite inspecionado contém somente CREATE TABLE, chave primária e FK.
Teste histórico confirmou preservação de todos os dados dos usuários e das
autorizações públicas de perfil/portfólio da B45. Nenhum perfil fictício foi criado.

Não foi aplicada ao banco local, compartilhado ou publicado. Aplicar somente
após revisão/autorização no ambiente adequado, antes de usar o endpoint. A remoção
de User remove seu EmpresaPerfil por CASCADE; não há endpoint de exclusão B46.

## Validação executada

PDM existente, sem instalação. Todos os testes usam `core.tests.settings`, SQLite
em memória e mídia temporária local. Para executar a worktree com as dependências
já instaladas na pasta original, os comandos foram chamados de lá com manage.py
absoluto. Forma reproduzível usada:

```powershell
$b46Manage = 'C:/Users/Ricardo/AppData/Local/Temp/Back_Marujob-FEAT-46/manage.py'
$env:CLOUDINARY_URL = 'cloudinary://test-key:test-secret@b46-test-only'
pdm run python -B $b46Manage test core.tests.test_empresa_perfil core.tests.test_profiles_portfolios.ProfileTests core.tests.test_freelancer_publico core.tests.test_authentication --settings=core.tests.settings -v 1
pdm run python -B $b46Manage check --settings=core.tests.settings
pdm run python -B $b46Manage makemigrations --check --dry-run --settings=core.tests.settings
pdm run python -B $b46Manage sqlmigrate core 0022 --settings=core.tests.settings
```

| Verificação | Resultado final |
|---|---|
| B46 + regressões B39/B40/B45 | 84 testes aprovados, 2,541 s, zero falhas |
| Novos testes B46 | Oito: sete API/contrato e um de migration |
| Django check | Sem problemas |
| Model/migration dry-run | No changes detected |
| SQL da migration | Revisado, apenas tabela nova |
| Ruff check e formatação | Aprovados nos cinco arquivos Python de implementação/teste/rota |
| Diff check | Sem erros de whitespace |
| APIClient adicional | GET/PATCH 200, GET sem criação, persistência e inválidos 400 |

Cobertura B46: criação para empresa antiga, PATCH preservando omitidos/limpeza,
autorização/isolamento, tentativa de alterar dados protegidos, URLs/UF/limites,
imagem inválida/removida, rollback de armazenamento, schema privado e migration.
O schema isolado expõe somente GET/PATCH e os nove campos documentados.

A primeira tentativa não iniciou os testes por falta de configuração Cloudinary
na worktree sem .env. Valores fictícios apenas no processo resolveram a importação
do teste B40; nenhum storage remoto foi utilizado. A execução seguinte encontrou
FTP aceito pelo URLField automático; o serializer recebeu validador HTTP/HTTPS
explícito, e a execução final passou. Ajustes iniciais de lint/formatação também
foram corrigidos. Avisos preexistentes de staticfiles/schema permanecem.
Não foram executados suíte completa, PostgreSQL, Cloudinary real, frontend ou
produção. Nenhum arquivo de credenciais ou configuração global foi alterado.

## Arquivos e compatibilidade

Novos: `core/models/empresa_perfil.py`, `core/serializers/empresa_perfil.py`,
`core/views/empresa_perfil.py`, `core/tests/test_empresa_perfil.py`,
`core/migrations/0022_empresa_perfil.py` e este documento.
Modificados: `core/models/__init__.py` (registro do model) e `app/urls.py` (import
e rota privada). Nenhum arquivo frontend ou implementação de outras FEATs foi editado.

B39 mantém autenticação/grupos; B40 mantém o contrato de usuário e a rotina de
completude reaproveitada; B45 mantém consentimento, campos públicos e serializers.
As regressões desses componentes passaram. Não há API pública empresarial nesta
entrega. F46 deve consumir apenas o endpoint privado e não presumir publicação.

Entrega validada e autorizada pelo usuário para commit, push e abertura de PR
da FEAT-46 para DEV. Merge, deploy e migration persistente não fazem parte dessa
autorização e não foram executados. Homologação no ambiente definitivo e integração
F46 continuam como próximos passos externos.
