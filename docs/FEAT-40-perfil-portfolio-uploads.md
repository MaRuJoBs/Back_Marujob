# FEAT-40 — Perfil, portfólio e uploads

Implementação exclusiva de `Back_Marujob`, na branch `FEAT-40`, criada a partir da
`origin/DEV` atualizada (`6a09cde`), incluindo FEAT-38 e FEAT-39. Commit, push e PR
autorizados pelo usuário após a validação; merge Git e deploy seguem fora do escopo.
Nenhum frontend, segredo, `.env`, dependência
ou registro do banco de desenvolvimento foi alterado. `db.sqlite3` já estava
modificado antes do trabalho e foi preservado.

## Diagnóstico e arquivos

O DRF já decodificava JSON textual de campos JSONField em multipart. O problema
era a ausência de validação estrutural: objetos, números e strings podiam ocupar
campos que o frontend espera como listas. Parsers já existiam no perfil; o portfólio
dependia dos parsers globais. Também faltavam limite de arquivo, formatos explícitos,
tratamento de falhas de armazenamento e validação dos metadados GPS. O serializer
de `/usuarios/me/` não recebia contexto da requisição para construir URLs locais.

A DEV integrada ainda tinha `core/tests.py` e `core/tests/`, causando ImportError
na descoberta de testes, e duas migrations 0014 com o mesmo ancestral.

| Arquivo | Alteração |
| --- | --- |
| `app/settings.py` | `MAX_IMAGE_UPLOAD_BYTES`, padrão 5 MiB, configurável por ambiente e validado como inteiro positivo |
| `core/serializers/fields.py` | Listas de strings, validação de imagem e tratamento genérico de erros de armazenamento |
| `core/serializers/user.py` | Habilidades, foto, precisão/timestamp GPS, limpeza de metadados e persistência transacional |
| `core/serializers/portfolio.py` | Tags, imagens e persistência transacional sem mudar campos de resposta |
| `core/views/user.py` | Contexto da requisição no serializer do perfil para URLs de imagem |
| `core/views/portfolio.py` | Parsers JSON/form/multipart explícitos e ordenação por ID para paginação consistente |
| `core/tests.py` → `core/tests/test_authentication.py` | Preserva testes FEAT-39; ajusta apenas o caminho relativo de settings e acrescenta teste da configuração de upload |
| `core/tests/test_profiles_portfolios.py` | Testes de perfil, portfólio, listas, permissões, arquivos e storage simulado |
| `core/migrations/0015_merge_favorito_freelance.py` | União das folhas 0014, com operations vazio |
| `docs/FEAT-40-perfil-portfolio-uploads.md` | Contratos, validações, limitações e operação |

Não foi necessário alterar models, permissões, URLs ou autenticação. Não foi
adicionado campo `cidade`: `localizacao` continua representando cidade/estado.

## Endpoints, respostas e permissões

Todos exigem Bearer access JWT. Não foram criadas rotas públicas novas.

| Endpoint | Método | Resultado |
| --- | --- | --- |
| `/api/usuarios/me/` | GET | 200, perfil completo somente da conta autenticada |
| `/api/usuarios/me/` | PATCH | 200, dados atualizados; campos omitidos preservados |
| `/api/portfolios/` | GET | 200, paginação dos projetos próprios |
| `/api/portfolios/` | POST | 201, criação por freelancer e proprietário automático |
| `/api/portfolios/{id}/` | GET | 200, detalhe próprio |
| `/api/portfolios/{id}/` | PUT | 200, edição com campos obrigatórios completos |
| `/api/portfolios/{id}/` | PATCH | 200, edição parcial |
| `/api/portfolios/{id}/` | DELETE | 204, exclusão de registro próprio |

Dados inválidos retornam 400 com erros por campo. Ausência/invalidade de JWT retorna
401. Escrita de empresa ou conta sem tipo inequívoco em portfólio retorna 403.
Recurso inexistente ou portfólio de terceiro retorna 404 quando a permissão da
ação permite a consulta. Falhas conhecidas de storage retornam 503 com mensagem
genérica, sem caminhos, credenciais ou detalhes do provedor.

| Ação | Freelancer proprietário | Freelancer não proprietário | Empresa | Anônimo |
| --- | --- | --- | --- | --- |
| Consultar/editar seu perfil | Sim | Somente o próprio perfil | Somente o próprio perfil | Não, 401 |
| Criar portfólio | Sim | Cria somente para si | Não, 403 | Não, 401 |
| Listar/consultar portfólio | Próprios | Terceiro ocultado, 404 | Apenas próprios, se já existirem | Não, 401 |
| Editar/excluir portfólio | Sim | Não, 404 | Não, 403 | Não, 401 |
| Alterar proprietário/grupos/privilégios | Não | Não | Não | Não |

Contas sem grupo ou com ambos os grupos mantêm leitura própria e perfil próprio,
mas não executam escrita exclusiva de freelancer. A FEAT-39 permanece intacta.

## Perfil e localização

GET `/api/usuarios/me/`, exemplo ilustrativo completo:

```json
{
  "id":42,
  "name":"Pessoa",
  "email":"pessoa@example.com",
  "profile_image":null,
  "profissao":"Desenvolvimento Web",
  "localizacao":"Joinville, SC",
  "latitude":null,
  "longitude":null,
  "geolocation_accuracy":null,
  "geolocation_timestamp":null,
  "sobre":"Desenvolvo aplicações web.",
  "telefone":"+55 (47) 99999-0000",
  "habilidades":["Django","Python"],
  "perfil_configurado":true,
  "aviso_perfil_dispensado":false,
  "groups":[{"id":2,"name":"Usuário","permissions":[]}],
  "tipo":"usuario"
}
```

PATCH JSON pode enviar somente:

```json
{"name":"Novo nome","habilidades":["Django","API"]}
```

Os demais valores permanecem. O retorno tem os mesmos campos do GET, com as
alterações persistidas. `name`, `profissao` e `localizacao` mantêm max_length 255;
`telefone`, 30. Não foram impostas máscaras de telefone ou novos campos obrigatórios.
`sobre` mantém a definição TextField atual. `perfil_configurado` mantém exatamente
o significado anterior: nome, profissão, localização, sobre e telefone preenchidos
com conteúdo não vazio. Foto, GPS e habilidades não são requisitos novos.

Campos protegidos seguem somente leitura ou fora do serializer: `id`, `email`,
`groups`, `tipo`, `is_staff`, `is_superuser`, `is_active`, `user_permissions`,
`google_id`, `password` e `perfil_configurado`. Tentativas de alterá-los são
ignoradas com segurança. `aviso_perfil_dispensado` continua editável.

Latitude/longitude mantêm os limites [-90,90]/[-180,180] e consistência do par.
PATCH pode atualizar uma coordenada se a outra já existe; não cria pares incompletos.
Precisão enviada deve ser finita e não negativa, em metros. Timestamp deve ser
datetime ISO 8601 válido; aceita histórico e até 5 minutos futuros de tolerância
de relógio. Metadados GPS enviados sem coordenadas são rejeitados. Um PATCH textual
não modifica nem revalida automaticamente metadados legados omitidos.

Seleção manual de localização com limpeza explícita:

```json
{"localizacao":"Florianópolis, SC","latitude":null,"longitude":null}
```

Isso também limpa `geolocation_accuracy` e `geolocation_timestamp`. Em multipart,
enviar `latitude` e `longitude` como campos vazios tem o mesmo efeito. Alterar
somente o texto de `localizacao` preserva coordenadas; o frontend deve enviar a
limpeza explicitamente quando trocar GPS por cidade manual. Nenhuma consulta de
geolocalização foi introduzida e nenhum centro de cidade substitui coordenadas.

## Listas: habilidades e tags

JSON exige listas reais; multipart exige um único campo textual contendo JSON:

```text
habilidades: ["Django","Python"]
tags: ["Django","Python","API"]
```

Limites para listas enviadas: até 50 itens e até 100 caracteres por item. Aceita
somente strings não vazias. Remove espaços externos e duplicatas exatas mantendo
ordem; maiúsculas/minúsculas permanecem distintas. A resposta sempre é uma lista
JSON real. Não há conversão de objetos, números, booleanos ou strings JSON duplamente
serializadas em listas. JSON malformado é rejeitado com 400.

Campo omitido em PATCH preserva a lista existente. Para limpar, enviar `[]` no JSON
ou o texto `[]` no multipart; `null` e string vazia não significam lista vazia.
Não foi introduzido suporte a campos repetidos, CSV, `tags[]` ou `habilidades[]`,
pois esses não eram contratos implementados pelo JSONField do backend. O formato
multipart JSON textual já aceito foi preservado. Dados legados omitidos não são
reescritos nem submetidos automaticamente aos novos limites.

Auditoria local somente de leitura: 0 registros com `habilidades` fora de lista de
strings e 0 registros com `tags` fora desse formato. Nenhum valor pessoal foi
exibido e nenhuma correção de dados foi executada.

## Portfólio e multipart

POST JSON, mantendo os campos existentes:

```json
{
  "titulo":"Meu projeto",
  "categoria":"Desenvolvimento Web",
  "descricao":"Projeto desenvolvido com Django.",
  "tags":["Django","Python","API"],
  "link":"https://example.com"
}
```

Resposta 201 ilustrativa:

```json
{
  "id":12,"imagem":null,"titulo":"Meu projeto",
  "categoria":"Desenvolvimento Web","descricao":"Projeto desenvolvido com Django.",
  "tags":["Django","Python","API"],"link":"https://example.com"
}
```

O modelo mantém `usuario`, atribuído exclusivamente a `request.user`. Como antes,
o serializer não retorna esse campo. Enviá-lo no payload não altera o proprietário.
`titulo` mantém 255 caracteres; `categoria`, 100; descrição continua obrigatória e
link continua opcional com a validação URLField existente. Imagem é opcional.

POST multipart com imagem:

```text
titulo: Meu projeto
categoria: Desenvolvimento Web
descricao: Projeto desenvolvido com Django.
tags: ["Django","Python","API"]
link: https://example.com
imagem: <arquivo binário PNG/JPEG/WebP>
```

PATCH `/api/portfolios/12/` aceita, por exemplo:

```json
{"titulo":"Projeto revisado","tags":[]}
```

Para atualizar somente a imagem, usar PATCH multipart com `imagem: <arquivo>`.
Campos omitidos, inclusive tags e imagem, permanecem. PUT continua exigindo título,
categoria e descrição; campos opcionais omitidos preservam o comportamento atual
do ModelSerializer. Listagens mantêm `count`, `next`, `previous` e `results`, com
10 itens por página e ordenação estável por ID.

Upload de perfil também usa multipart na rota existente:

```text
name: Pessoa
profissao: Designer
habilidades: ["Design","Web"]
profile_image: <arquivo binário PNG/JPEG/WebP>
```

## Imagens e armazenamento

- Limite padrão: 5 MiB por imagem (`5242880` bytes). Variável
  `MAX_IMAGE_UPLOAD_BYTES` aceita inteiro positivo em bytes; não altera `.env`.
- Formatos permitidos em novos uploads: JPEG, PNG e WebP, verificados pelo Pillow
  através do ImageField. Extensão/MIME declarados pelo cliente não substituem a
  validação real. Arquivos corrompidos, formatos não permitidos e imagens que
  excedem os limites de descompressão do Pillow são rejeitados com 400.
- O mesmo campo de foto no cadastro aplica essas validações, sem alterar o fluxo
  de autenticação. Registros/imagens existentes não são apagados ou revalidados
  só por serem consultados ou por um PATCH que não envia imagem.
- Desenvolvimento mantém FileSystemStorage/MEDIA_ROOT. Para servir mídia pelo
  runserver, usar o modo de desenvolvimento com DEBUG apropriado; a configuração
  de URLs de mídia existente do Django depende de DEBUG. Não foi criado servidor
  público de mídia para produção.
- Produção mantém `cloudinary_storage.storage.MediaCloudinaryStorage`. Não foi
  trocado por armazenamento local, nem alterado o destino dos arquivos existentes.
- A URL vem do storage. Em `/me/`, contexto da requisição agora transforma URLs
  locais relativas em URLs absolutas; no portfólio o DRF já fornece esse contexto.
  URL absoluta do Cloudinary permanece absoluta e não recebe outro domínio/media.
  O frontend deve consumir o valor retornado diretamente.
- Omitir o campo mantém a imagem; enviar arquivo substitui a referência; enviar
  JSON `null` ou campo multipart vazio remove a referência. A resposta passa a
  retornar `null` quando não há imagem.
- Substituição, remoção da referência e exclusão do registro não apagam arquivos
  antigos automaticamente. Isso evita apagar arquivos compartilhados ou ainda
  referenciados. Uma futura limpeza exige inventário/revisão separados.
- Falhas de I/O, SDK Cloudinary e requisições ao storage são convertidas em 503
  genérico. Falha durante `serializer.save()` reverte a transação do banco. Não há
  transação distribuída entre Django e storage: arquivos já gravados antes de uma
  falha posterior de banco/resposta podem exigir conciliação, sem deleção automática.

URLs de mídia local podem mudar de relativas para absolutas em `/me/`; o formato
JSON permanece string/null. HTTPS percebido em produção depende do proxy já
documentado na FEAT-39. O SDK deve estar configurado para retornar URLs HTTPS no
ambiente publicado; esta revisão não usa credenciais reais para homologar isso.

## Consulta pública segura: decisão pendente

Não foi criado endpoint público nem tornados públicos os registros atuais. Eles
foram criados sob leitura privada e não há flag de publicação, consentimento ou
regra de visibilidade no modelo.

Proposta para decisão de produto: publicação explícita por projeto, com padrão
privado para todos os registros legados, seguida de endpoint GET separado com
serializer profissional dedicado. Permitir somente ID, título, categoria,
descrição, tags, link e imagem que o dono decidiu publicar. Se houver perfil
profissional público, limitar a projeção aprovada a nome profissional, profissão,
habilidades, foto publicada e cidade/estado. Não expor e-mail, telefone, grupos,
flags administrativos, latitude/longitude exatas, precisão ou timestamp GPS.

Essa proposta exigiria modelagem/migration e política de consentimento aprovadas;
não foi implementada silenciosamente. Empresas continuam sem acesso aos projetos
privados de terceiros. Links de mídia já existentes no storage não passam a ter
controle de acesso por essa proposta: privacidade de arquivos requer revisão
específica do modo de entrega do storage antes de prometer sigilo de imagens.

## Migração e validação

`0015_merge_favorito_freelance` tem apenas dependências das duas migrations 0014,
sem operações próprias. Resolve o grafo após integração das FEAT-38/39, sem
reescrever histórico, renomear migrations aplicadas ou alterar dados. A aplicação
também executará as migrations 0014 que ainda estiverem pendentes: vínculo de
empresa da oportunidade e tabela Favorito. Não foi aplicada ao banco real.

A suíte original na branch anterior passou com 20 testes. Na DEV atualizada, a
primeira execução falhou na descoberta por conflito de módulo/pacote. Após mover
os testes e unir o grafo, os 36 testes existentes passaram. A primeira suíte com
FEAT-40 passou com 65 testes; uma execução intermediária padrão passou com 68.

**Resultado final:** `pdm run python manage.py test` executou **69 testes em
59,294 s, todos aprovados, zero falhas**. Django check sem problemas;
`makemigrations --check --dry-run` sem alterações pendentes; Ruff e verificação de
formatação dos 8 arquivos Python alterados passaram. `sqlmigrate core 0015`
confirmou `No operations found`. Os 20 testes originais FEAT-39 permanecem presentes
no arquivo movido, além da cobertura FEAT-38 e FEAT-40. `git diff --check` passou.

Revisão Git: branch `FEAT-40`, baseada em `origin/DEV` no commit `6a09cde`.
O diff rastreado mostra 7 arquivos, 48 inserções e 515 remoções, incluindo o banco
previamente alterado e a saída de `core/tests.py` do caminho antigo. Esses números
não incluem os arquivos novos ainda não rastreados: o conteúdo dos testes foi
movido para `core/tests/test_authentication.py`, não descartado. Permanecem novos
também os campos reutilizáveis, testes FEAT-40, migration vazia e esta documentação.
Esse estado foi registrado antes do staging, commit e push autorizados
posteriormente pelo usuário. Não houve merge Git nem deploy nesta entrega.

Os testes usam banco de testes e diretórios temporários `.feat40-media-*` dentro
do repositório, limpos ao finalizar. As integrações Cloudinary são simuladas nos
limites de upload/URL; nenhum arquivo é enviado ao provedor. Testes FEAT-38 e
FEAT-39 continuam sendo executados, sem remoção ou enfraquecimento de asserções.

Comandos de validação:

```text
pdm run python manage.py test
pdm run python manage.py test --settings=core.tests.settings
pdm run python manage.py check
pdm run python manage.py makemigrations --check --dry-run
pdm run python manage.py migrate --plan
pdm run ruff check app/settings.py core/serializers/fields.py core/serializers/user.py core/serializers/portfolio.py core/views/user.py core/views/portfolio.py core/tests/test_authentication.py core/tests/test_profiles_portfolios.py
pdm run ruff format --check app/settings.py core/serializers/fields.py core/serializers/user.py core/serializers/portfolio.py core/views/user.py core/views/portfolio.py core/tests/test_authentication.py core/tests/test_profiles_portfolios.py
git diff --check
```

O aviso preexistente de `staticfiles` ausente não impede os testes. Acesso real ao
Cloudinary, limites do proxy HTTP e navegação no frontend não foram homologados.
Pendências antes do PR: revisar diff, migration de união, limite de imagem no
ambiente e decisão de produto sobre publicação. Não há migrations de campos novos
de perfil/portfólio, nem mudanças nos contratos de autenticação/Google.

## Orientações ao frontend — sem alterações no Vue

1. Enviar listas reais em JSON e `JSON.stringify(lista)` no campo textual multipart.
   Não converter `FormData` inteiro em JSON ao enviar arquivos; deixar o navegador
   definir o Content-Type com boundary.
2. Usar `profile_image` no perfil e `imagem` no projeto. Omitir mantém; null em JSON
   ou campo vazio em multipart remove referência; arquivo substitui.
3. Consumir URLs completas retornadas sem concatenar domínio ou `/media/` novamente.
4. Ao escolher cidade manual e descartar GPS, enviar as duas coordenadas nulas
   (ou vazias no multipart). Timestamp GPS usa ISO 8601 e precisão usa metros.
5. Manter as regras FEAT-39 e apresentar erros por campo (400), falta de login
   (401), proibição (403), recurso privado/inexistente (404) e indisponibilidade
   de armazenamento (503). A API privada não passa a permitir navegação pública.
