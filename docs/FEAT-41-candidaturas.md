# FEAT-41 — Sistema de candidaturas

Implementação exclusiva de `Back_Marujob`, na branch `FEAT-41`, criada antes de
qualquer edição a partir da `origin/DEV` atualizada (`4549d85`). A base contém as
FEATs 34, 38, 39 e 40. A alteração preexistente em `db.sqlite3` foi preservada.
Commit, push e abertura de PR foram autorizados pelo usuário após a validação.
Merge Git e deploy seguem fora do escopo. Não houve alteração de `.env` ou frontend.

## Diagnóstico e escopo

`Freelance` já representa a oportunidade e tem `empresa` opcional como proprietário.
Não existiam modelo/rota de candidatura. A FEAT-34 preservou a ausência de campo de
disponibilidade/encerramento. Grupos `Usuário` e `Empresa` e a política restritiva
de grupos ausentes/conflitantes vêm da FEAT-39. A folha atual era
`0016_merge_20261030_1516`; nenhuma união anterior foi recriada.

Foi adicionado um recurso de candidatura para criar e consultar, sem reimplementar
usuários, oportunidades ou autenticação e sem alterar contratos existentes.

| Arquivo | Finalidade |
| --- | --- |
| `core/models/candidatura.py` | Modelo, estados, relacionamentos, datas, ordenação e unicidade |
| `core/models/__init__.py` | Exportação do modelo |
| `core/serializers/candidatura.py` | Criação, consulta, filtro e apresentação profissional restrita |
| `core/serializers/__init__.py` | Exportações dos serializers |
| `core/permissions.py` | Permissão nova, sem alterar as regras dos recursos anteriores |
| `core/views/candidatura.py` | Create/List/Retrieve, querysets por papel, transação e erros seguros |
| `core/views/__init__.py` | Exportação do ViewSet |
| `app/urls.py` | Registro de `/api/candidaturas/` no router existente |
| `core/migrations/0017_candidatura.py` | Criação da tabela e restrição no banco |
| `core/tests/test_candidaturas.py` | Cenários funcionais, privacidade, integridade, consultas e concorrência |
| `docs/FEAT-41-candidaturas.md` | Contratos, permissões, operação e limites |

## Modelo e exclusão

`Candidatura` contém somente:

- `id`: BigAutoField.
- `freelancer`: ForeignKey para `settings.AUTH_USER_MODEL`.
- `oportunidade`: ForeignKey para `core.Freelance`.
- `status`: TextChoices `pendente`, `aprovada`, `recusada`; padrão `pendente`.
- `criado_em`: auto_now_add.
- `atualizado_em`: auto_now.

Constraint `candidatura_freelancer_oportunidade_unica` impede duplicidade do par
freelancer/oportunidade inclusive fora da API. ForeignKeys mantêm integridade e
índices próprios. Ordenação: `-criado_em`, `-id`.

Os dois vínculos usam CASCADE, após avaliar as convenções de `Favorito` e os
contratos de exclusão da FEAT-34. Candidatura nesta etapa é dependente da conta e
da vaga, sem contratação ou obrigação de retenção histórica definida. Apagar a
conta candidata remove suas candidaturas; apagar a oportunidade remove as
candidaturas correspondentes. Não apaga a conta ou oportunidade no sentido inverso.
Isso preserva DELETE de vagas, sem introduzir PROTECT ou uma nova resposta de erro
incompatível. Nenhuma exclusão nova foi executada em dados reais.

Excluir a empresa continua com o comportamento existente de `Freelance.empresa`:
SET_NULL. A oportunidade e candidaturas permanecem, o freelancer continua vendo
a própria candidatura e nenhuma outra empresa ganha acesso. Antes de introduzir
contratações/auditoria na FEAT-44, revisar a política de retenção; esta etapa não
promete histórico após excluir conta candidata ou vaga.

## Endpoints e contratos

Todos exigem `Authorization: Bearer <access JWT>`. Anônimo ou JWT inválido recebe
401. Não há autenticação alternativa nem rota pública de candidatos.

| Método e rota | Comportamento |
| --- | --- |
| POST `/api/candidaturas/` | Somente freelancer; criação válida 201 |
| GET `/api/candidaturas/` | Freelancer lista suas candidaturas; empresa lista candidaturas de vagas próprias; 200 |
| GET `/api/candidaturas/{id}/` | Detalhe dentro do mesmo escopo; 200 ou 404 |
| PUT/PATCH/DELETE | Indisponíveis; contas com papel válido recebem 405 |

HEAD/OPTIONS técnicos continuam disponíveis para contas autorizadas.
Contas sem grupo de negócio ou com os dois grupos recebem 403. Não existe exceção
automática para is_staff/is_superuser. Grupos administrativos adicionais não mudam
um papel de negócio inequívoco.

Criação, exemplo:

```http
POST /api/candidaturas/
Content-Type: application/json

{"oportunidade":12}
```

Resposta 201 (IDs e datas ilustrativos, formato ISO 8601 do DRF):

```json
{
  "id":25,
  "freelancer":7,
  "oportunidade":12,
  "status":"pendente",
  "criado_em":"2026-10-30T15:00:00-03:00",
  "atualizado_em":"2026-10-30T15:00:00-03:00"
}
```

Somente `oportunidade` é campo de entrada. `id`, `freelancer`, `status`,
`criado_em` e `atualizado_em` são somente leitura: se enviados, são ignorados com
segurança. O backend atribui `request.user`, força `pendente` e gera as datas.
O ID de oportunidade deve ser inteiro positivo válido e corresponder a uma vaga.
Oportunidade ausente, inválida ou inexistente retorna 400 por campo, conforme a
validação DRF de relacionamento; não é 404 nesse POST.

GET lista paginada:

```json
{
  "count":1,
  "next":null,
  "previous":null,
  "results":[
    {
      "id":25,"freelancer":7,"oportunidade":12,"status":"pendente",
      "criado_em":"2026-10-30T15:00:00-03:00",
      "atualizado_em":"2026-10-30T15:00:00-03:00",
      "oportunidade_detalhes":{
        "id":12,"empresa":3,"titulo":"Projeto","descricao":"Descrição",
        "tag":"Web","preco":"100.00","tempo":"1 dia"
      },
      "freelancer_detalhes":{
        "id":7,"name":"Pessoa","profissao":"Designer",
        "habilidades":["Design","Python"],"profile_image":null
      }
    }
  ]
}
```

GET detalhe retorna um único objeto no formato de um item de `results`.
`oportunidade_detalhes` reutiliza o serializer existente sem mudar seu contrato.
A apresentação profissional restrita é a mesma na consulta própria e na consulta
autorizada da empresa. O POST retorna o contrato básico acima, sem os dois detalhes.

Paginação padrão: 10 itens por página, parâmetro `page`, mais recentes primeiro.
Há select_related para candidato/oportunidade, evitando consultas por item.

Filtro opcional:

```text
GET /api/candidaturas/?oportunidade=12
```

O filtro é aplicado depois do escopo obrigatório de usuário/propriedade. Para
empresa, uma vaga alheia ou inexistente retorna lista vazia; não revela candidatos
nem permite descobrir o proprietário. Para freelancer, retorna apenas suas
candidaturas daquela vaga. Parâmetro inválido/vazio retorna 400. Parâmetros
`empresa` e `freelancer` enviados pelo cliente não alteram o escopo e são ignorados.
Detalhe alheio/inexistente retorna 404. A empresa não se candidata nem à própria
vaga nem a vagas alheias (403).

## Duplicidade, concorrência e erros

Uma transação envolve a criação. A unicidade é arbitrada no banco, sem depender
de uma checagem vulnerável a corrida no serializer. O IntegrityError é tratado
depois do rollback do savepoint, mantendo a conexão utilizável.

Duplicidade retorna **400**:

```json
{"oportunidade":["Você já se candidatou a esta oportunidade."]}
```

Não há retorno idempotente 200: uma segunda candidatura não é criada nem altera
o status existente. Outros conflitos de integridade recebem erro 400 genérico.
Um OperationalError na gravação, incluindo contenção de escritores SQLite,
retorna 503 sem SQL, paths ou detalhes internos:

```json
{"detail":"Serviço de candidaturas temporariamente indisponível. Tente novamente."}
```

No SQLite, duas gravações simultâneas podem produzir 201 e 503 por bloqueio
temporário, em vez de 201 e 400 imediato. Repetir a requisição perdedora após o
término da primeira retorna 400 de duplicidade; nunca persiste uma segunda linha.
A constraint também vale em PostgreSQL, mas a concorrência não foi homologada
com PostgreSQL real nesta entrega. Nenhuma exceção é devolvida diretamente ao cliente.

## Permissões e privacidade

| Ação | Freelancer | Empresa | Sem grupo/com ambos | Anônimo |
| --- | --- | --- | --- | --- |
| Criar candidatura | Própria | Não, 403 | Não, 403 | Não, 401 |
| Listar/detalhar | Próprias | Recebidas em vagas próprias | Não, 403 | Não, 401 |
| Consultar candidatura alheia | Não, 404 | Não, 404 | Não, 403 | Não, 401 |
| Modificar candidato/status/datas | Não | Não | Não | Não |
| Aprovar/recusar | Não existe nesta feature | Não existe nesta feature | Não | Não |
| Excluir candidatura pela API | Não existe nesta feature | Não existe nesta feature | Não | Não |

O queryset e a permissão por objeto verificam relações reais, nunca IDs de empresa
ou candidato fornecidos pelo cliente. Vagas sem proprietário não concedem acesso
a qualquer empresa. Candidatar-se não altera grupo, conta, portfólio ou vaga.

`CandidatoProfissionalSerializer` contém exclusivamente ID, nome, profissão,
habilidades e foto. Não reutiliza o serializer privado. Não contém e-mail,
telefone, senha/hash, google_id, permissões/grupos, flags administrativos,
coordenadas, precisão ou timestamp GPS. `localizacao` foi omitida deliberadamente:
é texto livre e não há campo separado comprovadamente limitado a cidade/estado.
Portfólios privados da FEAT-40 não são publicados nem incluídos automaticamente.
Essa projeção só existe dentro de uma candidatura que o solicitante pode consultar;
não transforma o perfil em público global.

## Disponibilidade e FEAT-44

Não existe mecanismo de vaga aberta/encerrada em `Freelance` nem na FEAT-34.
É permitido candidatar-se a qualquer oportunidade existente, inclusive legada sem
empresa. Não há inferência de expiração por tempo, preço, descrição ou data.
Bloquear vagas encerradas depende de definição futura de disponibilidade.

Os estados aprovada/recusada são apenas estrutura para a FEAT-44. Esta entrega
não contém endpoints/actions de decisão ou atualização, notificações, e-mails,
chat, WhatsApp, contratação, ponto ou pagamentos. Não foi registrado um admin
novo que forneça fluxo operacional de decisões. Uma futura transição exige
regras de autorização, concorrência, retenção e testes próprios da FEAT-44.

## Migration e validações

`0017_candidatura` depende de `0016_merge_20261030_1516`, a folha integrada atual.
Cria somente a nova tabela com relacionamentos, índices e constraint. Não altera
ou duplica as migrations de união existentes, nem converte/exclui dados antigos.
O operador deve revisar o plano e aplicar a migration após autorização própria;
ela foi aplicada exclusivamente pelo runner no banco temporário de testes.

Comandos PDM:

```text
pdm run python manage.py test
pdm run python manage.py test --settings=core.tests.settings
pdm run python manage.py test core.tests.test_candidaturas --settings=core.tests.settings
pdm run python manage.py check
pdm run python manage.py makemigrations --check --dry-run
pdm run python manage.py migrate --plan
pdm run python manage.py sqlmigrate core 0017
pdm run ruff check core/models/candidatura.py core/serializers/candidatura.py core/views/candidatura.py core/permissions.py core/tests/test_candidaturas.py app/urls.py
pdm run ruff format --check core/models/candidatura.py core/serializers/candidatura.py core/views/candidatura.py core/permissions.py core/tests/test_candidaturas.py app/urls.py
git diff --check
```

Linha de base: 81 testes passaram. Os 23 testes novos cobrem criação, JWT, campos
protegidos, datas, unicidade direta no banco, duplicidade, grupos, listagem/detalhe,
paginação, escopo empresarial, filtros, projeção profissional, vagas sem dono,
operações indisponíveis, consultas sem N+1 e exclusões dos relacionamentos.
Uma primeira execução encontrou 1 falha no filtro vazio, que era ignorado pelo
tratamento HTML do DRF; o filtro passou a ser validado como dicionário comum e
esse cenário passou sem remover a asserção. A suíte isolada completa passou com
104 testes após a correção.

Resultado final na configuração normal: **104 testes passaram em 66,905 s, zero
falhas**. Django check sem problemas; `makemigrations --check --dry-run` sem
alterações pendentes. Não houve alteração dos testes anteriores.

O teste de concorrência usa TransactionTestCase, duas threads, conexões separadas
e barreira antes da inserção real; exige exatamente um 201, uma única linha e
duplicidade 400 na tentativa posterior. Não é um mock de IntegrityError substituindo
a garantia do banco. Há também teste de erro operacional sanitizado.

Regressões FEAT-34/38/39/40 continuam executadas sem remoção/enfraquecimento.
Mídia temporária e mocks externos das features anteriores são preservados.
Não foram usados tokens/credenciais reais, Cloudinary real ou banco de produção.
O aviso preexistente de `staticfiles/` ausente não impede a suíte.

## Frontend — somente orientações

1. Enviar somente `oportunidade` em POST com access JWT; não exigir candidato,
   status ou datas no formulário.
2. Freelancer usa GET para acompanhar as próprias candidaturas. Empresa usa o
   mesmo GET, opcionalmente com `?oportunidade=ID`, para candidaturas recebidas.
3. Consumir o envelope paginado e os detalhes aninhados documentados. Não
   concatenar domínio à URL de foto se o backend já a retorna absoluta.
4. Tratar 201, 200, 400 de validação/duplicidade, 401, 403, 404 e 503. Se repetir
   um POST após falha de rede/503 e receber duplicidade, consultar a lista.
5. Não apresentar ações funcionais de aprovação/recusa, edição ou exclusão:
   a FEAT-41 não oferece esses contratos. A FEAT-44 definirá o fluxo de decisões.
6. Não tentar acessar perfil privado ou portfólio alheio para complementar a
   projeção profissional. Nenhum arquivo Vue foi acessado ou modificado.

Pendências: aplicação autorizada da migration; homologação de concorrência no
banco de produção; definição futura de disponibilidade de vagas e das decisões
da FEAT-44. Nenhuma dessas limitações foi contornada com acesso ampliado.

## Revisão Git

O diff acrescenta 6 arquivos novos e altera 5 arquivos existentes da aplicação.
`db.sqlite3` permanece como alteração local anterior, fora do escopo da entrega.
O `git diff --stat` dos arquivos rastreados registra 6 arquivos, 26 inserções e
4 remoções, incluindo o banco preexistente; os novos arquivos ainda não rastreados
não entram nesse comando. `git diff --check` passou. Esse estado foi registrado
antes do staging, commit e push autorizados posteriormente. Não houve merge Git,
deploy ou migrations no banco de desenvolvimento.
