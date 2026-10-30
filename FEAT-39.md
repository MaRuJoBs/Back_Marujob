# FEAT-39 — Autenticação e controle de acesso

Implementação exclusiva do backend `Back_Marujob`, na branch `FEAT-39`, criada a partir
da `DEV` por solicitação do usuário. Commit e envio para PR autorizados posteriormente;
merge e deploy permanecem fora do escopo.
`db.sqlite3` já estava modificado antes do trabalho; não foi migrado nem restaurado.
Nenhum arquivo de frontend, dependência ou credencial foi alterado.

## Diagnóstico e alterações

Antes da implementação, oportunidades admitiam escrita anônima e não tinham
proprietário; portfólios eram privados por usuário, mas não restringiam empresas;
`/usuarios/` expunha outras contas autenticadas; `/usuarios/me/` não identificava
grupos; definição de senha substituía senhas existentes; Google vinculava contas
locais automaticamente por e-mail. Não havia testes descobertos pelo Django.

Os grupos `Usuário` e `Empresa` são criados pela migration existente `0009`.
Cadastros locais e Google atribuem exatamente o grupo escolhido em `tipo`, dentro
de transação. Grupos ausentes são criados com `get_or_create` no cadastro.

| Arquivo | Finalidade |
| --- | --- |
| `app/settings.py` | Autenticação JWT mantida; autenticação obrigatória por padrão; hosts/CORS explícitos em produção; validação de configuração; remoção da impressão do banco |
| `core/permissions.py` | Identificação inequívoca de tipo e permissões reutilizáveis por ação e objeto |
| `core/models/freelance.py` | Vínculo opcional com empresa proprietária |
| `core/migrations/0014_freelance_empresa.py` | Coluna e índice da FK; preservação dos registros antigos |
| `core/serializers/freelance.py` | Proprietário somente para leitura |
| `core/serializers/user.py` | Validadores Django, duplicidade de e-mail sem distinção de caixa, cadastro transacional, grupos e tipo de leitura no perfil |
| `core/views/freelance.py` | Permissões de empresa/proprietário e atribuição automática de empresa |
| `core/views/portfolio.py` | Escrita exclusiva de freelancer, preservando consulta privada por proprietário |
| `core/views/user.py` | Perfil próprio, suporte JSON além de formulários, Google seguro, tratamento de integridade e fluxos de senha |
| `core/tests.py` | Testes DRF/Django, Google offline com assinatura real e configuração de produção |
| `FEAT-39.md` | Contratos, matriz de acesso, validações e operação dos dados legados |

## Endpoints revisados

| Endpoint | Método | Autenticação e comportamento |
| --- | --- | --- |
| `/api/registro/` | POST | Público; `email`, `password`, `tipo` obrigatórios; `tipo=usuario` ou `empresa`; sucesso 201; validação 400 |
| `/api/token/` | POST | Público; e-mail/senha; access e refresh em 200; credenciais inválidas/inativas em 401 |
| `/api/token/refresh/` | POST | Público; exige refresh válido; 200 com access; token inválido, expirado ou do tipo access em 401 |
| `/api/token/verify/` | POST | Público; `token` válido retorna 200 e `{}`; inválido/expirado retorna 401 |
| `/api/auth/google/` | POST | Público; token validado pelo servidor; cadastro e login existentes preservam 200; inválido 400, inativo 401, conta não cadastrada 404, configuração/transporte indisponível 503 |
| `/api/auth/definir-senha/` | POST | JWT; somente conta Google com senha inutilizável; senha Django válida; 200 ou 400 |
| `/api/auth/trocar-senha/` | POST | JWT; exige `senha_atual` correta e `nova_senha` Django válida; 200 ou 400 |
| `/api/usuarios/me/` | GET, PATCH | JWT; consulta/edita apenas o próprio perfil; 200; validação 400; PUT não suportado (405) |
| `/api/usuarios/`, `/api/usuarios/{id}/` | GET | JWT; somente a própria conta; outra conta retorna 404; escrita permanece não suportada |
| `/api/freelances/`, `/api/freelances/{id}/` | GET, POST, PUT, PATCH, DELETE | JWT; leitura autenticada; criação só empresa; alteração/exclusão só empresa proprietária |
| `/api/portfolios/`, `/api/portfolios/{id}/` | GET, POST, PUT, PATCH, DELETE | JWT; leitura continua restrita ao próprio usuário; escrita só freelancer proprietário |

Nas rotas privadas, ausência de JWT ou access inválido/expirado retorna 401.
Criação retorna 201, edição 200 e exclusão 204. Acesso proibido por papel retorna
403; portfólio de terceiro é ocultado pelo queryset e retorna 404 para freelancer.
Empresa recebe 403 ao tentar escrita em portfólios. Objeto inexistente retorna 404
quando a requisição passou pela permissão de ação.
Admin Django continua com a autenticação de sessão e controles administrativos
existentes. Schema/documentação DRF seguem a nova permissão padrão autenticada.

## Contratos JSON

Cadastros continuam aceitando multipart/form e passam a aceitar JSON:

```json
{"email":"pessoa@example.com","name":"Pessoa","password":"<senha válida>","tipo":"usuario"}
```

Resposta 201 de cadastro (IDs ilustrativos):

```json
{"id":42,"email":"pessoa@example.com","name":"Pessoa","profile_image":null}
```

`tipo=empresa` no cadastro público continua permitido. `password` e `tipo` são
campos de entrada do cadastro e não aparecem nessa resposta.

GET/PATCH `/api/usuarios/me/`, exemplo completo de empresa:

```json
{
  "id":42,
  "email":"empresa@example.com",
  "name":"Empresa",
  "profile_image":null,
  "profissao":"",
  "localizacao":"",
  "latitude":null,
  "longitude":null,
  "geolocation_accuracy":null,
  "geolocation_timestamp":null,
  "sobre":"",
  "telefone":"",
  "habilidades":[],
  "perfil_configurado":false,
  "aviso_perfil_dispensado":false,
  "groups":[{"id":1,"name":"Empresa","permissions":[]}],
  "tipo":"empresa"
}
```

O formato de `groups` preserva a representação aninhada já usada por
`UserSerializer`: `id`, `name` e `permissions`. IDs e permissões variam por banco.
Freelancer tem `tipo: "usuario"` e grupo `Usuário`; não existe novo valor
`"freelancer"` no contrato. Conta sem grupo de negócio, ou com ambos, retorna
`tipo: null`. Grupos administrativos são preservados e não definem o tipo.

PATCH aceita dados de perfil. `id`, `email`, `perfil_configurado`, `tipo`, `groups`,
`is_staff`, `is_superuser`, `is_active`, `user_permissions`, `google_id` e `password`
não podem ser alterados pelo perfil: campos somente de leitura ou fora do serializer
são ignorados com segurança. PUT em `/me/` permanece 405.

POST `/api/token/` com `email` e `password` mantém:

```json
{"refresh":"<refresh JWT>","access":"<access JWT>"}
```

POST `/api/token/refresh/` com `{"refresh":"<refresh JWT>"}` retorna:

```json
{"access":"<novo access JWT>"}
```

Verify aceita access ou refresh válidos e retorna `{}`. Isso verifica validade do
token; não autoriza operações nem transforma refresh em credencial Bearer de API.
Access expira em 180 minutos e refresh em 1 dia, conforme configuração anterior.
Não havia rotação ou blacklist habilitada; nenhuma foi introduzida. Não há novo
logout/revogação: tokens já emitidos seguem as regras existentes até expirar.

POST Google aceita `credential`, `cadastro` (boolean ou string `true`/`false`) e
`tipo` obrigatório no cadastro. Login ignora `tipo` para autorização e não muda grupos.
Resposta 200 preserva:

```json
{
  "access":"<access JWT>",
  "refresh":"<refresh JWT>",
  "user":{
    "id":42,"email":"empresa@example.com","name":"Empresa",
    "is_active":true,"is_staff":false,"is_superuser":false,
    "last_login":null,"groups":[{"id":1,"name":"Empresa","permissions":[]}],
    "profile_image":null,"tipo":"empresa"
  },
  "precisa_definir_senha":true
}
```

Senha, hash e `google_id` não são retornados. Emissão de JWT é intencional e
exclusiva dos endpoints de autenticação. Definição usa `{"senha":"<senha válida>"}`;
troca usa `{"senha_atual":"<atual>","nova_senha":"<nova>"}`. Respostas de sucesso:
`{"detail":"Senha definida com sucesso."}` e
`{"detail":"Senha alterada com sucesso."}`. Erros de senha retornam 400 com
mensagem ou lista de validação no campo `senha`/`nova_senha`.

Oportunidade retorna os campos anteriores e `empresa` somente de leitura:

```json
{"id":12,"titulo":"Projeto","descricao":"Descrição","tag":"Dev","preco":"100.00","tempo":"1 dia","empresa":42}
```

O backend atribui `empresa=request.user`. Enviar outro proprietário em POST/PUT/PATCH
não altera essa atribuição. Portfólios preservam os campos anteriores (`id`,
`imagem`, `titulo`, `categoria`, `descricao`, `tags`, `link`); `usuario` é atribuído
pelo backend e sua presença no payload é ignorada.

## Matriz de permissões

| Ação | Freelancer | Empresa | Sem grupo/com ambos | Anônimo |
| --- | --- | --- | --- | --- |
| Ler oportunidades | Sim | Sim | Sim | Não |
| Criar oportunidade | Não | Sim | Não | Não |
| Editar/excluir oportunidade própria | Não | Sim | Não | Não |
| Editar/excluir oportunidade alheia ou sem dono | Não | Não | Não | Não |
| Ler portfólios | Próprios | Próprios, se já existirem | Próprios, se já existirem | Não |
| Criar/editar/excluir portfólio próprio | Sim | Não | Não | Não |
| Editar/excluir portfólio alheio | Não | Não | Não | Não |
| Consultar/editar próprio perfil | Sim | Sim | Sim | Não |
| Consultar perfil privado de terceiro | Não | Não | Não | Não |
| Alterar grupos/privilégios pelo perfil | Não | Não | Não | Não |

## Migração e dados legados

`0014_freelance_empresa` adiciona FK opcional para `AUTH_USER_MODEL`, com índice,
`related_name='oportunidades'` e `SET_NULL` na exclusão da conta. Registros existentes
ficam com `empresa=NULL`; não há exclusão de dados nem atribuição aleatória.
Permanecem consultáveis por autenticados, mas ninguém os edita/exclui pela API.

Não foi executado `migrate` no banco de trabalho. Foram inspecionados o plano e o
SQL; a migration é aplicada apenas ao banco temporário dos testes. O operador deve
revisar e aplicar a migration antes de executar o novo backend contra dados reais.
Para atribuir oportunidades antigas, identificar a empresa por evidência verificável,
revisar o mapeamento e atualizar somente registros aprovados por ferramenta
administrativa. Não inferir proprietário pelo título ou pela primeira empresa.

Auditoria local somente de leitura em 2026-10-30: 11 contas, 6 sem grupo de negócio,
0 com os dois grupos. Isso inclui possíveis contas administrativas. Não houve
reclassificação automática. Revisar cada conta com base no cadastro original;
atribuir somente o grupo de negócio comprovado, mantendo grupos administrativos.
Se houver conflito, resolver com confirmação do responsável e registrar a decisão.
Sem evidência, manter `tipo=null` e escrita por papel bloqueada. Não é necessária
migration de dados que invente a classificação de contas antigas.

## Configuração e frontend

Produção/MIGRATE exigem `DEBUG=False`, `SECRET_KEY` com pelo menos 50 caracteres,
sem prefixo `django-insecure`, e `ALLOWED_HOSTS` explícitos separados por vírgula,
sem `*`. `CORS_ALLOWED_ORIGINS` contém origens completas separadas por vírgula.
CORS permanece restrito também em desenvolvimento: os padrões são as origens Vite
`http://localhost:5173` e `http://127.0.0.1:5173`. Outros endereços exigem configuração
explícita. Hosts locais são o padrão de desenvolvimento. Acesso via IP de rede exige
configurar esse host explicitamente e não garante compatibilidade com Google.
Nenhum `.env` foi modificado nem segredo exibido. A revisão OAuth adicionou
`CSRF_TRUSTED_ORIGINS` por ambiente e `TRUST_X_FORWARDED_PROTO`, desativado por padrão.
HTTPS, proxy, cookies de sessão, HSTS e infraestrutura dependem do ambiente de
publicação. Consulte [GOOGLE-OAUTH.md](GOOGLE-OAUTH.md) para a configuração atual.

Google exige `GOOGLE_CLIENT_ID` real do ambiente. `verify_oauth2_token` verifica
assinatura, emissor, audiência e validade temporal; o backend também exige assunto,
audiência correspondente e `email_verified=true`. Contas inativas são recusadas.
Cadastro usa senha inutilizável e grupo explícito; login não muda grupos.
Contas locais sem `google_id` deixam de ser associadas automaticamente só por
coincidência de e-mail: devem entrar com senha. Um novo fluxo de vinculação com
confirmação da conta não foi criado, pois não existe contrato para isso no escopo.

Alterações necessárias no frontend, somente documentadas:

1. Ler `tipo`/`groups` em `/usuarios/me/`; `usuario` significa freelancer, `empresa`
   significa empresa e `null` exige revisão cadastral, sem presumir um papel.
2. Enviar Bearer access em oportunidades e demais rotas privadas; tratar 401, 403
   e 404. Mostrar edição/exclusão de oportunidade somente quando `empresa` for o
   ID da conta atual; `empresa=null` não tem edição disponível.
3. Não enviar `empresa`/`usuario` para atribuir propriedade; não tentar promover
   conta com PATCH/PUT. A lista `/usuarios/` passa a conter só a própria conta.
4. Para contas locais não vinculadas, tratar erro 400 do Google e orientar login
   com senha. Não apresentar uma vinculação automática como concluída.
5. Usar definição de senha somente quando `precisa_definir_senha=true`; contas com
   senha usam troca com senha atual. Exibir erros dos validadores Django.
6. Tratar 503 do Google sem presumir credencial inválida; verificar configuração
   e disponibilidade do provedor fora dos testes.

## Validação

Comandos usados pelo ambiente PDM:

```text
pdm run python manage.py test
pdm run python manage.py check
pdm run python manage.py makemigrations --check --dry-run
pdm run python manage.py migrate --plan
pdm run python manage.py sqlmigrate core 0014
pdm run ruff check app/settings.py core/permissions.py core/tests.py core/models/freelance.py core/serializers/freelance.py core/serializers/user.py core/views/freelance.py core/views/portfolio.py core/views/user.py
git diff --check
git diff --stat
```

Os testes usam banco temporário e mocks para serviços externos. Também exercitam
o verificador Google real com chaves RSA efêmeras locais, simulando somente a busca
das chaves públicas, para validar assinatura adulterada, emissor, audiência,
expiração e sucesso. Não há chamada real ao Google nem alteração de dependências.

Resultado final: 13 testes passaram em 45,398 s; `check` sem problemas;
`makemigrations --check --dry-run` sem alterações pendentes; plano contendo apenas
`0014_freelance_empresa`; SQL revisado sem execução no banco de trabalho. O aviso
de diretório `staticfiles` ausente é preexistente e não impede os testes.
Ruff passou nos 9 arquivos Python de implementação/testes verificados, todos já
formatados; `git diff --check` não apontou problemas. O `git diff --stat` dos
arquivos rastreados mostra 8 arquivos, 193 inserções e 135 remoções, incluindo a
alteração binária preexistente em `db.sqlite3`. Os 4 arquivos novos (documentação,
permissões, testes e migration) estão não rastreados e não entram nesse comando;
esse resultado foi registrado antes do staging e do commit autorizados posteriormente.

Pendências operacionais: aplicar migration após revisão, classificar as contas
legadas com evidência, atribuir donos antigos quando comprovados e conferir as
variáveis de produção/Google. A integração real com Google e o ambiente publicado
não foram testados; as validações locais não equivalem à homologação externa.
