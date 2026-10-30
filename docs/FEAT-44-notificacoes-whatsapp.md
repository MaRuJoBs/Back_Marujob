# FEAT-44 — Notificações, decisões e WhatsApp

Implementação exclusiva do `Back_Marujob`, na branch existente `FEAT-44`.
O remoto conferido foi `https://github.com/MaRuJoBs/Back_Marujob.git`.
As implementações das FEAT-34 e FEAT-41 já estavam disponíveis e foram estendidas.
Não houve acesso ao repositório de frontend, alteração de Vue, commit, push, merge
ou deploy. O `db.sqlite3` já estava modificado antes do trabalho e foi preservado.

## Estrutura e integridade

Fluxo: candidatura criada pela API → notificação da empresa → consulta profissional
→ aprovação/recusa → contato manual disponível se aprovada e telefone válido.

`Candidatura`, `Freelance`, `User`, autenticação JWT e os grupos existentes são
reutilizados. Não foram criadas tabelas paralelas de oportunidades ou candidatos.

O novo modelo `Notificacao` contém:

| Campo | Definição |
| --- | --- |
| `id` | BigAutoField |
| `empresa` | FK para `AUTH_USER_MODEL`, destinatário identificado pela oportunidade |
| `candidatura` | OneToOneField para `Candidatura`, unicidade garantida no banco |
| `lida` | Boolean, padrão `false` |
| `criado_em` | Data de criação automática |

Freelancer, profissão, imagem, oportunidade e status são consultados pelos
relacionamentos; não são copiados para a tabela. Ordenação por `-criado_em, -id`.
Índice composto por empresa, leitura e data. Relacionamentos usam CASCADE:
excluir uma candidatura ou sua conta candidata/oportunidade remove a notificação;
excluir a conta destinatária também remove as notificações. A exclusão da empresa
continua preservando a oportunidade, com `empresa=NULL`, como na FEAT-34.
Não se promete retenção histórica após essas exclusões existentes.

No `perform_create` existente, candidatura e notificação são gravadas na mesma
`transaction.atomic()`. Uma falha de notificação desfaz a candidatura. O
`get_or_create` e o OneToOne impedem duplicações. Não há sinal ou efeito de escrita
nos endpoints GET. Criações por ORM/bulk fora da API não disparam notificações:
ferramentas administrativas futuras devem preservar a mesma transação e unicidade.

Oportunidades legadas sem empresa continuam aceitando candidatura, preservando
a FEAT-41; não se inventa um destinatário e nenhuma empresa pode analisar esses
registros. Não há novo conceito de encerramento/disponibilidade de vagas.

## Autenticação e permissões

Todas as rotas abaixo exigem `Authorization: Bearer <access JWT>`.
Ausência de credencial ou JWT inválido/expirado retorna `401`.
Somente a conta com grupo de negócio inequívoco `Empresa` pode acessar notificações
ou decidir. Freelancer com grupo `Usuário`, contas sem grupo e contas com ambos
recebem `403` nesses recursos. Privilégios administrativos não substituem o papel.

Notificações exigem que tanto o destinatário quanto o proprietário atual da
oportunidade sejam a empresa autenticada. IDs de terceiros e inexistentes retornam
`404`. Filtros e payloads não permitem trocar destinatário, candidato ou proprietário.
Se a propriedade for alterada administrativamente, a notificação antiga fica oculta;
o novo dono consulta a candidatura pela API existente, sem transferência automática
de notificações. A API de oportunidades não permite transferir a propriedade.

## Endpoints

| Método e caminho | Resultado |
| --- | --- |
| GET `/api/notificacoes/` | Lista paginada exclusiva da empresa |
| GET `/api/notificacoes/{id}/` | Detalhe exclusivo da empresa |
| PATCH `/api/notificacoes/{id}/marcar-lida/` | Marca leitura, idempotente |
| POST `/api/candidaturas/{id}/aprovar/` | Aprova pendente, somente empresa proprietária |
| POST `/api/candidaturas/{id}/recusar/` | Recusa pendente, somente empresa proprietária |

Continuam disponíveis POST/GET `/api/candidaturas/` e GET
`/api/candidaturas/{id}/`. POST é exclusivo do freelancer. GET lista/consulta
candidaturas próprias do freelancer ou candidaturas de oportunidades da empresa.
PUT, PATCH e DELETE genéricos de candidatura permanecem indisponíveis (`405`).
Notificações não admitem criação, exclusão nem edição genérica pela API (`405`).
HEAD/OPTIONS técnicos seguem o DRF e as permissões do recurso.

## GET /api/notificacoes/

Parâmetros opcionais, combinados por AND:

| Parâmetro | Valores |
| --- | --- |
| `lida` | `true`, `false` |
| `status` | `pendente`, `aprovada`, `recusada` |
| `page` | Número da página, iniciando em 1 |

Paginação padrão existente do DRF: 10 itens, envelope
`count`, `next`, `previous`, `results`. Não foi adotado outro envelope nem criado
um tamanho de página específico. Filtro inválido retorna `400`; página fora do
intervalo retorna `404`. Os filtros restringem a lista; não afetam detalhe/leitura.

Requisição:

```http
GET /api/notificacoes/?lida=false&status=pendente&page=1
Authorization: Bearer <access JWT da empresa>
```

Resposta `200` (IDs, host e datas ilustrativos):

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 9,
      "candidatura": 25,
      "freelancer": 7,
      "freelancer_detalhes": {
        "id": 7,
        "name": "Ana",
        "profissao": "Designer",
        "habilidades": ["Design", "UX"],
        "profile_image": "http://localhost:8000/media/users/ana.jpg"
      },
      "oportunidade": 12,
      "oportunidade_titulo": "Design de aplicativo",
      "status": "pendente",
      "candidatura_criado_em": "2026-10-30T15:00:00-03:00",
      "criado_em": "2026-10-30T15:00:00-03:00",
      "lida": false
    }
  ]
}
```

`profile_image` pode ser `null`; quando preenchido, consumir a URL retornada.
`criado_em` é a data da notificação; `candidatura_criado_em` é a data original da
candidatura. Em registros retroativos as datas podem ser diferentes.

## GET /api/notificacoes/{id}/

```http
GET /api/notificacoes/9/
Authorization: Bearer <access JWT da empresa>
```

Resposta `200`, sem envelope de paginação:

```json
{
  "id": 9,
  "candidatura": 25,
  "freelancer": 7,
  "freelancer_detalhes": {
    "id": 7,
    "name": "Ana",
    "profissao": "Designer",
    "habilidades": ["Design", "UX"],
    "profile_image": null
  },
  "oportunidade": 12,
  "oportunidade_titulo": "Design de aplicativo",
  "status": "pendente",
  "candidatura_criado_em": "2026-10-30T15:00:00-03:00",
  "criado_em": "2026-10-30T15:00:00-03:00",
  "lida": false
}
```

Consultar não marca leitura e não muda o status da candidatura.

## PATCH /api/notificacoes/{id}/marcar-lida/

```http
PATCH /api/notificacoes/9/marcar-lida/
Authorization: Bearer <access JWT da empresa>
Content-Type: application/json

{}
```

Resposta `200`: objeto completo da notificação, no mesmo formato do detalhe,
com `"lida": true`. Exemplo:

```json
{
  "id": 9,
  "candidatura": 25,
  "freelancer": 7,
  "freelancer_detalhes": {
    "id": 7,
    "name": "Ana",
    "profissao": "Designer",
    "habilidades": ["Design", "UX"],
    "profile_image": null
  },
  "oportunidade": 12,
  "oportunidade_titulo": "Design de aplicativo",
  "status": "pendente",
  "candidatura_criado_em": "2026-10-30T15:00:00-03:00",
  "criado_em": "2026-10-30T15:00:00-03:00",
  "lida": true
}
```

Corpo vazio também funciona. Campos enviados são ignorados: esta ação só permite
fixar `lida=true`, nunca trocar relações ou desfazer leitura. Repetir não muda a
data, não cria registros e não decide a candidatura. Falha de bloqueio retorna `503`.

## Aprovação e recusa

| Estado atual | Ação | Resultado |
| --- | --- | --- |
| `pendente` | aprovar | `200`, passa a `aprovada` |
| `pendente` | recusar | `200`, passa a `recusada` |
| `aprovada` | aprovar | `200`, mantém status e `atualizado_em` |
| `recusada` | recusar | `200`, mantém status e `atualizado_em` |
| `aprovada` | recusar | `409`, sem alteração |
| `recusada` | aprovar | `409`, sem alteração |

A decisão usa transação e `select_for_update(of=('self',))` sobre a candidatura,
sem bloquear o outer join opcional com empresa. A atualização também exige
`status=pendente` e propriedade da empresa no WHERE, e grava `atualizado_em`
explicitamente. Assim não há sobrescrita de um estado terminal por leitura antiga.
No SQLite o bloqueio de linha não existe; a condição na atualização e a transação
mantêm a integridade. Contenção temporária pode produzir `503`: repetir a mesma
ação após aguardar, ou recarregar o recurso. Uma decisão oposta já persistida
produz `409`. A criação/leitura da notificação é independente da decisão: aprovar
não cria outra notificação nem marca a existente como lida.

Requisição de aprovação (payload não escolhe o status):

```http
POST /api/candidaturas/25/aprovar/
Authorization: Bearer <access JWT da empresa proprietária>
Content-Type: application/json

{}
```

Resposta `200`, incluindo o contrato anterior da candidatura:

```json
{
  "id": 25,
  "freelancer": 7,
  "oportunidade": 12,
  "status": "aprovada",
  "criado_em": "2026-10-30T15:00:00-03:00",
  "atualizado_em": "2026-10-30T15:10:00-03:00",
  "oportunidade_detalhes": {
    "id": 12,
    "titulo": "Design de aplicativo",
    "descricao": "Projeto de interface",
    "tag": "Design",
    "preco": "100.00",
    "tempo": "1 dia",
    "empresa": 42
  },
  "freelancer_detalhes": {
    "id": 7,
    "name": "Ana",
    "profissao": "Designer",
    "habilidades": ["Design", "UX"],
    "profile_image": null
  },
  "whatsapp": {
    "disponivel": true,
    "modo": "link",
    "url": "https://wa.me/5547999999999?text=Ol%C3%A1%2C+Ana%21+Sua+candidatura+para+a+vaga+Design+de+aplicativo+foi+aprovada+pela+empresa+Exemplo+atrav%C3%A9s+do+MaRuJoBs.+Gostar%C3%ADamos+de+conversar+com+voc%C3%AA+sobre+os+pr%C3%B3ximos+passos.",
    "mensagem_enviada": false
  }
}
```

Requisição de recusa para outra candidatura ainda pendente:

```http
POST /api/candidaturas/26/recusar/
Authorization: Bearer <access JWT da empresa proprietária>
Content-Type: application/json

{}
```

A resposta `200` tem todos os campos da candidatura acima. Os valores relevantes
para atualizar a interface são, neste exemplo (recorte do objeto completo):

```json
{
  "id": 26,
  "status": "recusada",
  "atualizado_em": "2026-10-30T15:11:00-03:00",
  "whatsapp": {
    "disponivel": false,
    "modo": "link",
    "url": null,
    "mensagem_enviada": false,
    "motivo": "candidatura_nao_aprovada"
  }
}
```

## Consulta de candidatos e regressão da FEAT-41

```http
GET /api/candidaturas/?oportunidade=12&status=pendente&page=1
Authorization: Bearer <access JWT da empresa>
```

Retorna `200`, envelope padrão de paginação. Cada item tem o formato completo de
candidatura apresentado acima. O filtro `oportunidade` continua disponível e foi
adicionado `status` com os três valores conhecidos; valor inválido retorna `400`.
GET `/api/candidaturas/25/` retorna o objeto completo sem envelope. Para a empresa
proprietária, o campo `whatsapp` é recalculado tanto na lista quanto no detalhe e
nas respostas de decisão, inclusive após recarregar a página. Para o freelancer
esse campo não existe, mesmo em candidaturas aprovadas.

O serializer `CandidatoProfissionalSerializer` da FEAT-41 foi reutilizado. Expõe
somente `id`, `name`, `profissao`, `habilidades` e `profile_image`. Não amplia o
endpoint privado `/usuarios/`, não libera portfólios privados e não retorna e-mail,
telefone bruto, senha/hash, token, Google ID, grupos/permissões, flags administrativas,
localização ou GPS nessas projeções profissionais.

POST `/api/candidaturas/` mantém o payload `{"oportunidade":12}` e a resposta `201`
da FEAT-41, sem novos campos para o freelancer. Duplicata continua sendo `400`
com `{"oportunidade":["Você já se candidatou a esta oportunidade."]}`. Não há
exposição de link WhatsApp em oportunidades ou respostas de notificação.

## WhatsApp

Não foi encontrada implementação/configuração de WhatsApp Business Platform no
backend. Foi implementado o cenário B, com link de contato manual. Não há tokens
da Meta, automação de envio, chamada externa, alegação de entrega ou mensagem
real nos testes. `mensagem_enviada` é sempre `false`.

Texto gerado e codificado como parâmetro `text`:

> Olá, [nome]! Sua candidatura para a vaga [título] foi aprovada pela empresa [empresa] através do MaRuJoBs. Gostaríamos de conversar com você sobre os próximos passos.

Os dados vêm dos relacionamentos. Nome ausente utiliza `profissional`; nome da
empresa ausente utiliza `empresa`. Não são inferidos nomes a partir de e-mail.
`phonenumbers` valida o plano de numeração e gera E.164; o link usa somente os
dígitos internacionais, sem `+`. A biblioteca foi adicionada ao pyproject, lock e
requirements de produção, sem atualizar versões das demais dependências do lock.

São aceitos números internacionais explícitos com `+` e números brasileiros com
DDD (10/11 dígitos), ou com `55` já presente (12/13 dígitos), desde que válidos.
Só se acrescenta `55` ao formato nacional completo; não se acrescenta DDD ou nono
dígito. Números locais sem DDD, prefixos de operadora/tronco, `00`, ramais, letras,
DDI inválido e números que demandem correção silenciosa são recusados. A validação
não altera o telefone salvo no perfil.

Candidatura aprovada com telefone inválido continua aprovada e retorna:

```json
{
  "disponivel": false,
  "modo": "link",
  "url": null,
  "mensagem_enviada": false,
  "motivo": "telefone_invalido"
}
```

Antes da aprovação ou após recusa, o motivo é `candidatura_nao_aprovada`. A biblioteca
não comprova que um número pertence ao candidato, está ativo ou tem WhatsApp. Abrir
o link prepara a conversa; o usuário precisa revisar e enviar no aplicativo.
Sem integração oficial não há comprovante de envio/entrega nem controle sobre
mensagens que alguém resolva enviar novamente no WhatsApp. Uma futura integração
oficial precisará de consentimento, credenciais, templates e auditoria próprios.

Referências: [click to chat do WhatsApp](https://faq.whatsapp.com/5913398998672934),
[phonenumbers](https://github.com/daviddrysdale/python-phonenumbers) e
[bloqueio transacional no Django](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update).

## Erros

| Código | Situação |
| --- | --- |
| `200` | Consulta, leitura e decisão bem-sucedidas; decisão repetida idêntica |
| `201` | Criação de candidatura pela rota existente |
| `400` | Filtros/dados inválidos ou candidatura duplicada |
| `401` | JWT ausente, inválido ou expirado |
| `403` | Papel não autorizado |
| `404` | ID inexistente, objeto alheio ou página inexistente |
| `405` | Método não disponibilizado |
| `409` | Tentativa de inverter decisão já persistida |
| `503` | Falha operacional/bloqueio transitório durante a escrita |

Erros preservam o padrão do DRF: `detail` ou listas de erros por campo.
Exemplos de respostas reais do contrato:

```json
{"detail":"A candidatura já foi analisada e não pode receber outra decisão."}
```

```json
{"detail":"Serviço de candidaturas temporariamente indisponível. Tente novamente."}
```

Os erros não retornam SQL nem credenciais. Uma falha transacional não deixa uma
candidatura nova sem sua notificação quando existe empresa destinatária.

## Integração Vue para João

1. Autenticar com o access JWT existente e conferir `tipo=empresa` no perfil próprio.
2. Consultar `/api/notificacoes/` e seguir `next`/`previous` para outras páginas.
   Usar `lida` para distinguir novas/lidas e `status` para agrupar decisões.
   Para analisadas, consultar `aprovada` e `recusada` separadamente, ou filtrar
   a lista geral; não existe um status literal `analisada`.
3. Exibir `freelancer_detalhes`, `oportunidade_titulo` e datas. Abrir detalhes pela
   notificação ou por `/api/candidaturas/{candidatura}/`. O ID da notificação é
   diferente do ID da candidatura: decisões sempre usam o segundo.
4. Ao abrir a notificação, enviar PATCH para `marcar-lida/` e atualizar o item pela
   resposta. Aprovar/recusar não marca leitura automaticamente.
5. Somente para pendentes, oferecer POST `aprovar/` e `recusar/`. Desabilitar o botão
   enquanto a chamada estiver em curso; ao retornar, aplicar o objeto completo e
   recarregar a lista caso o filtro tenha deixado de incluir aquele status.
6. Mostrar o botão de contato somente quando `status=aprovada` e
   `whatsapp.disponivel=true`, usando exatamente `whatsapp.url`. Se indisponível,
   mostrar o motivo sem inventar número nem montar um link no cliente.
7. Usar texto como “Abrir conversa no WhatsApp”; não afirmar “Mensagem enviada”.
8. Em `409`, recarregar a candidatura para exibir a decisão atual. Em `503`, aguardar
   e repetir a mesma ação ou consultar o estado. Tratar `401` com o fluxo JWT já
   existente, `403` como falta de papel e `404` como recurso indisponível.
9. Atualizar por polling enquanto a tela estiver ativa (por exemplo, a cada 30 s,
   com pausa em aba oculta, cancelamento ao sair e espera maior após falhas).
   Manter uma requisição por vez e limpar o estado ao trocar de conta. Não há
   WebSocket, push ou contador global de não lidas separado; o `count` da consulta
   `?lida=false` informa esse total, mesmo com paginação.

Nenhum arquivo de frontend foi implementado ou alterado.

## Migrations e operação

Novas migrations, após a dependência existente `0017_candidatura`:

- `0018_notificacao`: cria exclusivamente a tabela nova, FK, OneToOne único e índice.
- `0019_notificacoes_retroativas`: utiliza modelos históricos e o alias correto do
  banco; processa lotes de 500 e cria somente notificações ausentes de candidaturas
  com proprietário conhecido, em qualquer status. Preserva as candidaturas e suas
  datas. Notificações retroativas começam não lidas e recebem a data da migração.
  Reexecutar a função não duplica nem redefine leitura; a reversão do passo de
  dados é no-op para não apagar registros de notificação existentes.

Não foram alteradas migrations antigas nem aplicadas migrations no banco de
desenvolvimento/produção. As operações de migração em testes atingem somente o
banco SQLite em memória configurado por `core.tests.settings`.

O plano do banco local real ainda contém dependências anteriores: os dois ramos
`0014_freelance_empresa` e `0014_favorito`, as duas uniões `0015`, a união `0016`,
`0017_candidatura` e as novas `0018`/`0019`. O código está integrado na branch, mas
o banco local está defasado. O operador deve revisar o plano completo e aplicar
as migrations no momento apropriado antes de usar a API nova. Não basta executar
SQL da tabela nova isoladamente. Em produção, coordenar o rollout de migrations
e código e pausar gravações da versão antiga durante o preenchimento retroativo.

Comandos de inspeção seguros já executados:

```text
pdm run python manage.py check
pdm run python manage.py makemigrations --check --dry-run
pdm run python manage.py migrate --plan
```

## Testes e verificações reais

```text
pdm run python manage.py test --settings=core.tests.settings --noinput
```

Resultado: **155 testes passaram em 2,234 s**, sem falhas ou testes ignorados.
Inclui os 130 cenários existentes das FEAT-34/37/38/39/40/41 e 25 novos cenários
da FEAT-44. O único teste antigo cujo contrato foi atualizado era o que exigia
ausência das rotas de decisão da etapa anterior; o bloqueio das edições genéricas
foi mantido e testado. A rodada específica de candidaturas/notificações também
passou: 47 testes antes da inclusão do cenário adicional de criação concorrente.

Cobertura nova: criação/rollback, unicidade no banco, duplicação, paginação,
filtros combinados, isolamento entre empresas, JWT/papéis, leitura idempotente,
aprovação/recusa, timestamp persistido, decisão repetida e oposta, telefone inválido,
normalização nacional/internacional, codificação da mensagem, bloqueio de contato
antes da aprovação, privacidade e ausência de contato em consultas do freelancer,
contagem limitada de consultas, perda de propriedade, erro de bloqueio, criação
concorrente e decisões opostas concorrentes com conexões independentes.

O teste de migração parte de `0017`, prepara dados históricos, aplica as duas
novas migrations no banco isolado, verifica todos os status e oportunidade sem
empresa, preserva uma notificação já lida e reexecuta a função de preenchimento
para confirmar idempotência. Nenhum teste envia mensagens ou acessa a Meta.

`check`: nenhum problema. `makemigrations --check --dry-run`: `No changes detected`.
`migrate --plan`: plano revisado, sem aplicação. Ruff passou nos arquivos Python
alterados; verificação de formatação e `git diff --check` também foram executadas.
Existe aviso preexistente de diretório `staticfiles` ausente durante testes; ele
não impede os testes e não foi ocultado. PostgreSQL não foi executado neste
ambiente; o bloqueio foi implementado conforme a API suportada e os testes de
concorrência foram executados no SQLite, incluindo seu comportamento de `503`.

SHA-256 do `db.sqlite3` registrado antes das alterações e confirmado na conferência final:
`0623669CB003E9F95D8E4BA3B9F328D40FEC3530A9C44624A7BD8454E74E508E`.
O conteúdo permaneceu idêntico ao início da tarefa; a alteração local anterior não
faz parte da FEAT-44. O SQL de `0018` também foi inspecionado com `sqlmigrate`, sem
execução: `candidatura_id` tem `UNIQUE` e ambas as relações possuem Foreign Keys.
`pdm lock --check` confirmou que o lock está consistente com o pyproject.

## Arquivos

| Arquivo | Alteração |
| --- | --- |
| `core/models/notificacao.py` e `core/models/__init__.py` | Modelo e exportação |
| `core/migrations/0018_notificacao.py` | Esquema novo |
| `core/migrations/0019_notificacoes_retroativas.py` | Preenchimento retroativo idempotente |
| `core/permissions.py` | Papel/propriedade para notificações e decisões |
| `core/serializers/notificacao.py` e `core/serializers/__init__.py` | Projeção segura e filtros |
| `core/serializers/candidatura.py` | Filtro de status e resposta empresarial com contato |
| `core/views/notificacao.py` e `core/views/__init__.py` | Listagem, detalhe e leitura |
| `core/views/candidatura.py` | Criação transacional conjunta e ações de decisão |
| `core/whatsapp.py` | Normalização e geração de link manual |
| `app/urls.py` | Registro no router existente |
| `core/tests/test_notificacoes.py` | Novos testes funcionais, concorrência e migração |
| `core/tests/test_candidaturas.py` | Atualização do contrato antigo de ausência de decisões |
| `pyproject.toml`, `pdm.lock`, `requirements.txt` | Dependência `phonenumbers` |
| `docs/FEAT-44-notificacoes-whatsapp.md` | Contratos e resultados |
