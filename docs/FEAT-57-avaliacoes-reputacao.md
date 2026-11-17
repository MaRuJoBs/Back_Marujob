# B57 — Avaliações e reputação

## Implementação

Implementação exclusiva do backend na branch `FEAT-57`, baseada na DEV remota
`4001659a1bc8ac5aeb00b6d4ae3f847100c1aaf9`. Reutiliza usuários, JWT, grupos,
oportunidades B34/B47 e candidaturas/aprovação B41/B44. Não altera o frontend.

A conclusão é comprovada por confirmação independente dos dois participantes
via JWT. Aprovação da candidatura, encerramento/cancelamento da vaga, tempo
transcorrido e contato WhatsApp nunca liberam avaliações automaticamente.
A regra implementa a transição mínima segura prevista no item 3 do pedido B57.
Não há aprovação unilateral nem backfill de trabalhos supostamente concluídos.

## Investigação e isolamento

Antes das modificações foram executados `git rev-parse --show-toplevel`,
`git status --short`, `git branch --show-current` e `git log -5 --oneline`.
O repositório confirmado foi `MaRuJoBs/Back_Marujob`; a FEAT-57 já existia com
HEAD igual à DEV local e origin/DEV. `git ls-remote --heads origin` confirmou
esse mesmo hash para a DEV remota. Não foi necessário trocar ou atualizar a base.

Foram investigados os 24 PRs existentes, com metadados e descrições consultados
individualmente: 19 mergeados e cinco fechados sem merge (#2, #3, #4, #7, #13),
nenhum aberto. Foram conferidas as 23 branches remotas, o histórico de `core` e
`app`, modelos, serializers, views, URLs, migrations, permissões e testes.
Não havia avaliações, reputação ou conclusão de serviços implementadas.

Dependências inspecionadas: [B34/#10](https://github.com/MaRuJoBs/Back_Marujob/pull/10),
[B41/#14](https://github.com/MaRuJoBs/Back_Marujob/pull/14),
[B44/#16](https://github.com/MaRuJoBs/Back_Marujob/pull/16),
[B45/#19](https://github.com/MaRuJoBs/Back_Marujob/pull/19),
[B47/#20](https://github.com/MaRuJoBs/Back_Marujob/pull/20) e
[B43/#24](https://github.com/MaRuJoBs/Back_Marujob/pull/24).
Candidaturas tinham somente `pendente`, `aprovada` e `recusada`; vagas têm status
informativo e reversível. Nenhum deles foi reinterpretado como serviço concluído.

Foram preservados os arquivos locais anteriores: `.pdm-python`,
`.vscode/settings.json`, `core.png`, `db.sqlite3`, `media/portfolios/image.png`
e `media/users/image.png`. Não há merge, deploy ou aplicação de migration no
banco local/compartilhado. Nenhuma dependência ou configuração foi alterada.

## Dados e regras

`ConclusaoTrabalho` é OneToOne com a candidatura existente; não recria trabalho,
vaga, usuário ou candidatura. Guarda a empresa e o freelancer participantes,
mais `empresa_confirmou_em` e `freelancer_confirmou_em`. Não existe booleano de
conclusão editável: `concluido` é derivado da presença das duas confirmações.

- Apenas participante ativo com papel inequívoco (`Empresa` ou `Usuário`) confirma.
- A candidatura precisa estar aprovada; os dois participantes precisam estar
  ativos, distintos e com seus papéis corretos. Vaga sem empresa não é elegível.
- A primeira confirmação registra as duas identidades reais; cada chamada grava
  somente a data da própria parte. O payload não escolhe usuário, data ou estado.
- Repetições são idempotentes e preservam a primeira data. Uma única confirmação
  mantém as avaliações bloqueadas. As partes podem confirmar em qualquer ordem.
- Troca administrativa de empresa ou freelancer invalida a relação com as
  confirmações anteriores. Elas não são transferidas ou sobrescritas pela API.
- O estado de aprovação B44 permanece inalterado. Não há cancelamento, disputa,
  revogação ou substituição livre de confirmação; discordância/ausência da outra
  parte mantém o serviço sem conclusão bilateral.

`Avaliacao` referencia candidatura, avaliador e avaliado pelo `AUTH_USER_MODEL`.
Usa `nota` inteira de 1 a 5, `comentario` opcional de até 1000 caracteres,
`criado_em` e `atualizado_em`. Há `UniqueConstraint(candidatura, avaliador)`,
checks no banco para nota e participantes distintos, além de índice de leitura
por avaliado/data/ID. Cada participante pode avaliar a outra parte uma vez por
trabalho; até duas avaliações válidas por candidatura.

A criação aceita somente os três campos documentados. IDs de avaliador/avaliado,
datas e campos desconhecidos são rejeitados com 400. Não há endpoints de edição,
exclusão, detalhe arbitrário por ID ou listagem geral de avaliações privadas.
Não foi adicionado admin de moderação ou uma nova autenticação.

## Contrato REST

Todas as rotas exigem `Authorization: Bearer <access JWT>` e papel de negócio
inequívoco. GET não grava dados. As listas usam a paginação existente: 10 itens,
`count`, `next`, `previous`, `results`, parâmetro `page` e ordem decrescente de
data/ID. Coleção vazia retorna `count: 0` e `results: []`.

| Método | Endpoint | Resultado |
| --- | --- | --- |
| GET | `/api/candidaturas/{id}/conclusao/` | Estado da conclusão, somente participantes; 200 |
| POST | `/api/candidaturas/{id}/conclusao/` | Confirma pela parte do JWT; payload `{}`; 200, inclusive repetição |
| POST | `/api/avaliacoes/` | Avalia a outra parte depois das duas confirmações; 201 |
| GET | `/api/avaliacoes/minhas/` | Avaliações válidas enviadas pelo titular; 200 paginado |
| GET | `/api/avaliacoes/recebidas/` | Avaliações válidas recebidas pelo titular; 200 paginado |
| GET | `/api/avaliacoes/usuarios/{id}/` | Avaliações divulgáveis recebidas pelo usuário; 200 paginado |
| GET | `/api/avaliacoes/usuarios/{id}/reputacao/` | Média e quantidade recebidas; 200 |

Exemplo ilustrativo de confirmação; IDs e datas abaixo não são dados gravados:

```http
POST /api/candidaturas/15/conclusao/
Authorization: Bearer <access>
Content-Type: application/json

{}
```

Após somente a empresa confirmar:

```json
{
  "candidatura_id": 15,
  "empresa_confirmou_em": "2026-11-17T12:00:00-03:00",
  "freelancer_confirmou_em": null,
  "concluido": false
}
```

O freelancer chama a mesma rota com seu próprio JWT. Somente então `concluido`
retorna `true` e ambos podem enviar, cada um com seu JWT:

```json
{
  "candidatura_id": 15,
  "nota": 5,
  "comentario": "O combinado foi cumprido."
}
```

A resposta 201 e as listas privadas contêm `id`, `candidatura`, `avaliador`,
`avaliado`, `nota`, `comentario`, `criado_em`, `atualizado_em`. O backend determina
os participantes pelos vínculos da candidatura; os nomes de login não são usados.

| Código | Significado |
| --- | --- |
| 200 | Consulta ou confirmação concluída/idempotente |
| 201 | Avaliação criada |
| 400 | Payload inválido, nota fora de 1–5, booleano/float como inteiro, comentário maior que 1000, campo proibido |
| 401 | JWT ausente/inválido/expirado ou conta inativa |
| 403 | Conta sem papel de negócio ou com ambos os papéis |
| 404 | Candidatura inexistente/de terceiro; usuário inexistente, privado ou inelegível para divulgação; página inexistente |
| 409 | Candidatura não aprovada, conclusão incompleta, relação inválida/alterada ou avaliação duplicada/inconsistente |
| 503 | Disputa de escrita/indisponibilidade do banco; cliente pode repetir a operação |

Rotas de edição/exclusão não são registradas; chamadas a elas retornam 404/405.
Erros usam os formatos padrão do DRF: `detail` ou erros por campo, sem SQL ou
mensagens internas do banco.

## Divulgação, privacidade e reputação

As rotas de divulgação também exigem JWT e retornam somente dados de avaliação.
Freelancers precisam estar ativos, sem privilégios administrativos, com papel
inequívoco e `perfil_publico=true`; revogar a publicação oculta essas consultas.
Empresas ativas, não administrativas e com papel inequívoco podem ter reputação
consultada, sem expor qualquer campo do perfil institucional privado B46.
Isso não altera o acesso ao diretório B45 ou ao perfil B46.

A projeção divulgável contém somente `id`, `nota`, `comentario`, `criado_em`.
Não revela autor, ID da candidatura, empresa da vaga, e-mail, telefone, GPS,
Google ID, senha ou grupos. O comentário enviado é conteúdo divulgável; clientes
devem apresentar essa finalidade ao autor na integração futura. Não há envio
externo de mensagens ou acesso anônimo a essas rotas.

Reputação usa `Avg` e `Count` na mesma consulta sobre avaliações recebidas
válidas, com média arredondada a duas casas. Não existe reputação persistida em
User, nota inicial ou mistura de notas enviadas e recebidas. Sem avaliações:

```json
{"usuario_id": 12, "media": null, "total_avaliacoes": 0}
```

`Avaliacao.objects.validas()` verifica aprovação, duas confirmações, identidades
preservadas e compatíveis com os vínculos atuais, direção dos participantes e
faixa de nota. Registros inconsistentes gravados fora da API não são contados
nem divulgados. Exclusão administrativa ou CASCADE remove a avaliação da média.
Mudança administrativa de vínculo/status também a exclui das consultas válidas.
Listas e agregação têm quantidade de consultas limitada, sem N+1 por avaliação.

## Concorrência, exclusão e limites

Confirmação e criação usam `transaction.atomic()` e bloqueio da candidatura com
`select_for_update(of=('self',))`. A confirmação faz atualização condicional da
data nula. OneToOne e UniqueConstraint arbitram duplicatas no banco.

No PostgreSQL, o bloqueio serializa operações da mesma candidatura. No SQLite,
que não aplica esse bloqueio, disputa de escrita pode retornar 503 com rollback;
a repetição é segura e nunca deve duplicar avaliação. Os testes exercitam duas
requisições simultâneas e repetição após a disputa, sem ocultar a resposta 503.

Os novos relacionamentos usam CASCADE, conforme candidaturas/notificações
existentes: excluir a candidatura, vaga ou conta envolvida remove os registros
relacionados. Excluir empresa também remove sua evidência/avaliações, embora a
vaga seja preservada pelo SET_NULL existente. Não há promessa de retenção após
exclusão. Uma transferência administrativa de participantes exige tratamento
próprio; a B57 bloqueia reaproveitamento das confirmações antigas.

A comprovação é a declaração autenticada e concordante dos dois participantes.
Não há verificação externa de pagamento ou entrega, arbitragem ou prevenção de
conluio entre contas; nenhuma dessas integrações existe no projeto.

## Migration e validação

Migration gerada pelo Django: `0023_avaliacoes_reputacao`, dependente de
`0022_empresa_perfil`. Cria somente duas tabelas, seus índices e constraints.
Não modifica migrations anteriores, usuários, oportunidades ou candidaturas;
não cria avaliações, confirmações ou notas retroativas. Foi aplicada somente
nos bancos descartáveis de testes, inclusive com teste de atualização de uma
base antiga contendo candidatura aprovada em vaga encerrada.

Comandos executados pelo PDM, usando o runner já existente:

```text
pdm run python scripts/audit_b54.py test core.tests.test_avaliacoes --noinput -v 1
pdm run python scripts/audit_b54.py test --noinput
pdm run python scripts/audit_b54.py check
pdm run python scripts/audit_b54.py makemigrations --check --dry-run
pdm run ruff check core/models/avaliacao.py core/serializers/avaliacao.py core/avaliacoes.py core/views/avaliacao.py core/tests/test_avaliacoes.py app/urls.py
pdm run ruff format --check core/models/avaliacao.py core/serializers/avaliacao.py core/avaliacoes.py core/views/avaliacao.py core/tests/test_avaliacoes.py app/urls.py
```

O runner executa os comandos do Django com `core.tests.settings`, SQLite em
memória, configuração sintética, `.env` desabilitado e sockets externos
bloqueados. Os testes aplicam as migrations normais. Nenhum banco local,
produção, Google ou Cloudinary real é usado.

Execução B57: **32 testes aprovados**, exit 0. Suíte completa em um único
processo: **305 testes aprovados em 36,472 segundos**, sem falhas, erros ou
skips, exit 0. Django `check`: sem problemas, exit 0.
`makemigrations --check --dry-run`: `No changes detected`, exit 0.
Ruff check e format check dos arquivos Python da B57: aprovados.
Permanecem os diagnósticos preexistentes de schema em outros módulos e o aviso
de `staticfiles/` ausente. PostgreSQL real não foi executado neste ambiente.

A cobertura B57 inclui os 17 cenários pedidos, além de duas ordens de confirmação,
idempotência/datas, status de vaga insuficiente, rejeição de falsificação de
conclusão, vínculo alterado, dados legados sem backfill, exclusões, faixa/checks
no banco, privacidade/publicação, paginação, consultas constantes e OpenAPI.
Os cenários positivos concluem e avaliam trabalhos pelo fluxo real da API no
banco de testes. Inserções inválidas por ORM são usadas apenas em testes de
rejeição, constraints e exclusão de reputação, nunca como prova de conclusão.

## Arquivos e revisão

- `core/models/avaliacao.py`: modelos e queryset de avaliações válidas.
- `core/models/__init__.py`: registro dos novos modelos.
- `core/avaliacoes.py`: operações atômicas, elegibilidade e conflitos.
- `core/serializers/avaliacao.py`: payloads e projeções privadas/divulgáveis.
- `core/views/avaliacao.py`: endpoints, permissões, agregação e OpenAPI.
- `app/urls.py`: registro das rotas B57.
- `core/migrations/0023_avaliacoes_reputacao.py`: estrutura nova sem backfill.
- `core/tests/test_avaliacoes.py`: testes de API, concorrência e migration.
- `docs/FEAT-57-avaliacoes-reputacao.md`: contrato e validação.

A branch está preparada para publicação e revisão. Commit, push e abertura de PR
da FEAT-57 para DEV foram autorizados pelo usuário após a validação acima.
Merge e deploy permanecem fora desta entrega.
A integração futura exige aplicar a migration no ambiente autorizado antes de
usar as novas rotas. Nenhum arquivo do frontend ou componente F57 foi alterado.
