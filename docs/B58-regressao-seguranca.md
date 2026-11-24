# B58 — Regressão e segurança do backend

**Veredito — PARCIAL.** A revisão final confirmou 446 testes aprovados em SQLite e em PostgreSQL 18 com locale `C.utf8`. Os critérios de B55 e B56 e a homologação de produção continuam pendentes. A execução em PostgreSQL com locale `C` encontrou duas falhas no diretório.

## Base Git e dependências

O remoto `origin` aponta para `MaRuJoBs/Back_Marujob`. A worktree original estava em `DEV`, no commit `a9a2554cff70dda3b404d589fa669681711e064f`, com alterações em `.pdm-python`, `.vscode/settings.json` e `db.sqlite3`. Após `git fetch origin --prune`, a divergência `DEV...origin/DEV` era de 0 commits exclusivos da DEV local e 6 exclusivos da referência remota. As buscas por B58 em branches, histórico e PRs em todos os estados retornaram nenhum trabalho equivalente identificado.

A branch `B58` foi criada na worktree isolada `/tmp/marujob-B58`, cujo HEAD coincide com o commit buscado de `origin/DEV`, `2b59bd0f13d7d523d4490ffa5aca28c4c0b8e6ac`. O Git confirma B60 e B62 integradas pelos PRs #29 e #30. As alterações da B58 estão na worktree, pendentes de commit. A DEV original permaneceu no mesmo commit e com as mesmas três alterações locais.

Na revisão final, um novo `git fetch origin --prune` confirmou a mesma ponta e divergência `0/0` entre B58 e `origin/DEV`. As buscas por B55/B56 foram repetidas em issues e PRs de todos os estados na organização, branches do backend e do frontend e histórico e documentação locais. O chat oferece implementação de conversas, mensagens, anexos, REST e WebSocket. A atribuição a B55/B56 depende dos critérios de aceite ou de uma referência que vincule esses identificadores ao trabalho integrado.

| Dependência | Classificação | Evidência |
| --- | --- | --- |
| B55 | DEPENDÊNCIA SEM ESCOPO DOCUMENTADO | Buscas pelo identificador em issues, PRs abertos e fechados, branches e mensagens de commits não encontraram critérios de aceite. |
| B56 | DEPENDÊNCIA SEM ESCOPO DOCUMENTADO | As buscas pelo identificador também não encontraram critérios de aceite. |
| B59 | IMPLEMENTADA E TESTADA | PR #28 integrado, endpoints em `core/views/empresa_perfil.py`, migration `0024_empresaperfil_bairro` e suíte `core/tests/test_empresa_localizacao_b59.py` aprovada. |

O chat REST e WebSocket está implementado e foi integrado por `featchat` (PR #26). O código e os testes confirmam seus contratos atuais. Sem critérios de B55 e B56, a equivalência com qualquer uma dessas duas dependências permanece indeterminada. [Chat #26](https://github.com/MaRuJoBs/Back_Marujob/pull/26) · [B59 #28](https://github.com/MaRuJoBs/Back_Marujob/pull/28) · [B60 #29](https://github.com/MaRuJoBs/Back_Marujob/pull/29) · [B62 #30](https://github.com/MaRuJoBs/Back_Marujob/pull/30)

## Áreas e evidência reaproveitada

Foram consultados `scripts/audit_b54.py`, `app/settings.py`, `app/asgi.py`, `app/urls.py`, `core/tests/settings.py`, `core/tests/`, `chat/tests/` e os relatórios B54, B59, B60, B62 e FEAT-43 de `docs/`. A revisão de código incluiu decisões e candidaturas, notificações, subscriptions, avaliações, autenticação e o caminho de mensagens do chat entre services, actions, consumer e difusão.

| Área | Evidência da suíte executada |
| --- | --- |
| B39 e B54 · Autenticação e configuração | Cadastro e login por papéis, Google simulado, JWT ausente/inválido/expirado, refresh, revogação por senha, inativação, ambiguidade de grupos, limites de autenticação, HTTPS, cookies e origens em configuração sintética. |
| B40 e B45 · Perfis, portfólio e diretório | Projeções públicas e privadas, papéis, campos protegidos, uploads válidos e malformados, limite e falha de armazenamento simulada. |
| B34, B37, B38 e B47 · Vagas e favoritos | CRUD, proprietário, status, filtros, busca, paginação, detalhes, favoritos por conta e campos opcionais, incluindo o limite B62 publicado pela API. |
| B41, B44 e B62 · Candidaturas e decisões | Autoria e status do servidor, duplicatas e constraint, visibilidade por propriedade, decisão idempotente, recusa, limite, notificação e rollback. O contrato de criação em vagas existentes é caracterizado pela suíte B41. |
| B43 · Jornadas e matriz | Cadastro e login JWT, diretório, publicação, candidatura, decisão, exclusão e snapshots contra mutações indevidas. A B58 acrescenta localização pública B59, histórico B60, leitura e remoção local da credencial. |
| Chat e B54 · REST, WebSocket e anexos | Participantes e autores, histórico e paginação, leitura, edição/exclusão, revogação, expiração, desativação, frames inválidos, origens, autorização de mídia, entrega Cloudinary simulada, reconexão e falha de publicação por Redis simulado. |
| B57 · Avaliações | Conclusão bilateral, participantes, duplicatas, restrições no banco, concorrência e projeções de reputação. |
| B59 · Localização empresarial | PATCH parcial e remoção, rollback de payload inválido, identidade do JWT, rejeição de edição por terceiros e projeção pública limitada a cidade e UF. |
| B60 · Histórico e Web Push | Destinatário, leitura individual e em lote, limite, chaves, expiração, falha pós-commit, transporte cifrado simulado e destinos/redirecionamentos rejeitados. Mudança de conta no dispositivo exige endpoint e as duas chaves já registradas pelo contrato atual. |

## Matriz com contas fictícias

A matriz JWT original compara snapshots do banco nas negativas. A jornada adicionada também confirma que cada negativa de leitura da notificação preserva seu estado.

| Operação em recurso de A | Freelancer A | Freelancer B | Empresa A | Empresa B | Anônimo |
| --- | ---: | ---: | ---: | ---: | ---: |
| PATCH vaga da empresa A | 403 | 403 | 200 | 403 | 401 |
| PATCH projeto do freelancer A | 200 | 404 | 403 | 403 | 401 |
| GET candidatura do freelancer A à vaga da empresa A | 200 | 404 | 200 | 404 | 401 |
| POST aprovar candidatura A | 403 | 403 | 200 | 404 | 401 |
| PATCH marcar notificação empresarial A lida | 403 | 403 | 200 | 404 | 401 |
| GET perfil profissional publicado A | 403 | 403 | 200 | 200 | 401 |
| PATCH marcar notificação do freelancer A lida | 200 | 404 | 403 | 403 | 401 |

A matriz B43 também cobre contas inativa e ambígua, com 401 e 403, respectivamente. As suítes de recursos privados cobrem exclusão indevida, uso de IDs alheios e injeção de campos de propriedade em payload. O teste público da B59 exige o conjunto exato `cidade` e `uf`, preservando a privacidade do bairro e das coordenadas.

## Achados e correções

| Severidade | Reprodução | Resultado |
| --- | --- | --- |
| P1 | Simular `RedisConnectionError` em `group_send` ao enviar mensagem por REST. O destinatário via a mensagem persistida, mas o POST retornava 500. | `chat/realtime.py` preserva o resultado da operação quando o Redis falha na expedição de eventos por erro de conexão ou timeout. O POST retorna 201 com o identificador persistido. O aviso omite exceção, payload, conta e endereço do Redis. A entrega instantânea pode se perder durante a falha. |
| P2 | Seis assertions de esquema de vagas falhavam pela presença do campo documentado `max_profissionais`. | O contrato segue validado por igualdade exata de campos, com verificações de valor configurado, persistência e valor nulo por padrão. |
| P2 | Um teste B44 interceptava todos os `select_for_update`. Com B62, a aprovação aguardava uma segunda vez na barreira ao bloquear a vaga e falhava com `BrokenBarrierError`. | A sincronização intercepta somente a consulta da candidatura. Permanecem as verificações de vencedor único, idempotência e preservação do registro. |
| P2 | Os testes existentes cobriam o limite de profissionais em série e o limite de dispositivos em série. | Novos testes exercitam duas aprovações para a última vaga e dois cadastros para a última posição de dispositivo em SQLite. |
| P3 | O check de produção sintético registrou dez avisos de geração OpenAPI e dois de HSTS (`W005`, `W021`). A suíte também emitiu aviso de `staticfiles` ausente na worktree. | Pendências registradas. A configuração e os endpoints do projeto foram preservados. |

## Execução e ambiente

O runner foi inspecionado antes dos testes. Ele força configuração sintética, desativa leitura de dotenv, bloqueia conexões de saída e usa SQLite em memória. As chaves e contas de teste são fictícias. Web Push, Google, Cloudinary e a indisponibilidade do Redis foram simulados nos respectivos testes. Nenhuma operação de teste usou o banco ou serviços publicados.

A primeira execução com o virtualenv existente foi interrompida na importação de dependências B60 (`py_vapid` e depois `aiohttp`). As dependências do lockfile exportado pelo PDM foram instaladas em `/tmp/marujob-B58-locked`, com Python 3.12.12. O sandbox produziu falhas em sockets locais e cancelamentos por tempo em WebSocket. O mesmo teste de handshake passou com a execução autorizada fora do sandbox, com ambiente vazio, a proteção de rede do runner e SQLite em memória.

As invocações finais usaram este prefixo na worktree B58:

```sh
env -i PATH=/usr/bin:/bin HOME=/tmp PYTHONDONTWRITEBYTECODE=1 \
  /tmp/marujob-B58-locked/bin/python scripts/audit_b54.py
```

| Invocação do runner | Resultado |
| --- | --- |
| `test --noinput` original | 441 executados, 434 aprovados, 6 falhas, 1 erro, 0 skips. |
| `test --noinput chat.tests.test_api.MessageTests.test_message_remains_available_in_history_when_redis_is_unavailable` antes da correção | 1 falha. A verificação do histórico passou e a do status obteve 500. |
| `test --noinput` após a correção | 446 aprovados, 0 falhas, 0 erros, 0 skips. Cinco testes novos. |
| `test --noinput` com seleção de suítes de vagas, decisões, B43, B59, B60, B62 e `chat.tests` | 205 aprovados, 0 falhas, 0 erros, 0 skips. |
| `test --noinput core.tests.test_limite_profissionais.LimiteProfissionaisConcurrencyTests core.tests.test_notificacoes_freelancer.PushSubscriptionConcurrencyTests` | 2 aprovados por execução em 5 execuções consecutivas. |
| `check` | Exit 0, zero problemas. |
| `--production check --deploy` | Exit 0, 12 avisos. |
| `makemigrations --check --dry-run` | Exit 0, nenhuma alteração detectada. |
| `showmigrations --plan` | Exit 0, 48 entradas em banco vazio, incluindo a sequência 0024, 0025 e 0026. |

`git diff --check` passou. Ruff passou nos nove arquivos Python alterados com `--extend-ignore PT009,PT018,PT027` para o estilo unittest existente, e `ruff format --check` passou nos mesmos arquivos.

Logs da execução em `/tmp`: `marujob-B58-verified-baseline.log`, `marujob-B58-redis-before.log`, `marujob-B58-final.log`, `marujob-B58-verified-targeted.log`, `marujob-B58-concurrency.log` e `marujob-B58-locked-{check,deploy,migrations,plan}.log`.

## Banco e concorrência

A criação do banco da suíte aplicou o grafo de migrations do zero. Testes com `MigrationExecutor` percorreram os upgrades B59, B60 e B62 em SQLite descartável, com verificações de preservação dos registros. A B58 não requer migration própria.

As suítes exercitaram duplicata de candidatura, decisões opostas, duplicata de avaliação, confirmação bilateral e os dois últimos limites adicionados nesta entrega. O teste B62 usa duas conexões e uma barreira antes do bloqueio da oportunidade. Após eventual 503 de contenção SQLite, espera um 200 e um 409, uma candidatura aprovada, a outra pendente e um único histórico e callback. Em B60, testes concorrentes com um espaço disponível terminam com um 204, um 400 e o total de dispositivos dentro do limite.

O modelo impõe unicidade de candidatura por freelancer e vaga, de avaliação por candidatura e autor e de endpoint de subscription. A revisão encontrou bloqueio de oportunidade nas aprovações e bloqueio de usuário no cadastro de dispositivos. A disputa concorrente de edição de perfil entre requisições reais e a transferência concorrente de subscriptions entre contas seguem sem validação.

## Revisão final

Todos os nove arquivos Python e este relatório foram revisados. Os ajustes desta etapa foram nos testes de transporte do chat, limite de aprovações e cadastro de dispositivos. A implementação de `chat/realtime.py` mantém tratamento restrito a conexão e timeout do Redis, sem capturar erros arbitrários de aplicação. O teste usa um mock na fronteira `group_send` e confirma HTTP 201, um único registro por envio para cada falha simulada e aviso sanitizado. Erro de conexão do Redis também abrange alguns erros de configuração, como falha de autenticação. Esses casos continuam sinalizados pelo aviso e exigem diagnóstico operacional.

Quando a publicação falha, o WebSocket pode ficar sem o evento em tempo real que a interface usa para atualizar a conversa. O histórico REST contém o resultado persistido. O teste de reconexão cobre rede local de teste e entrega de mensagem nova após reconectar. Falhas de inscrição em grupos, recuperação automática do histórico, configuração de credenciais Redis e reenvios manuais do mesmo POST seguem para homologação. A API não oferece uma chave de idempotência para reenvio de mensagem.

**P2 · Evidência dos testes de concorrência.** O teste Web Push sincronizava a entrada HTTP, permitindo que os cadastros alcançassem o trecho crítico em sequência. Os dois testes agora verificam que a barreira foi efetivamente atingida pelas duas requisições imediatamente antes do `select_for_update` relevante. O teste de Push também exige que o HTTP 400 venha especificamente do limite de dispositivos. As consultas, transações e constraints são reais em ambos os bancos. O teste de Push substitui somente a disponibilidade de VAPID e o teste B62 substitui o envio externo.

**P2 · Diretório sob locale `C`.** PostgreSQL 18.6 inicializado com locale `C` e encoding UTF-8 executou 446 testes e falhou em dois casos de busca por letras acentuadas de `FreelancerPublicoTests`. O filtro B45 depende do tratamento de maiúsculas e minúsculas da collation do banco. O resultado foi confirmado pela suíte em um segundo cluster com locale `C.utf8`, em que os mesmos testes passaram. O código de busca e a configuração de produção foram preservados. A homologação deve confirmar a collation real ou tratar a portabilidade caso o locale `C` seja exigido.

Os clusters descartáveis foram criados a partir de pacotes PostgreSQL extraídos em `/tmp`, sem instalação no sistema. O servidor ficou sem TCP e aceitou apenas o socket Unix em diretório de modo 0700. Um adaptador temporário do runner B54 substituiu apenas `DATABASES` por esse socket antes da inicialização do Django. O ambiente sintético e as demais proteções do runner continuaram ativos. O Django criou e removeu seu banco temporário, e o processo do servidor foi encerrado após cada rodada.

| Execução da revisão | Resultado |
| --- | --- |
| SQLite, suíte integral antes dos ajustes | 446 aprovados, 0 falhas, 0 erros, 0 skips. |
| PostgreSQL 18.6 `C`, seleção B62 e concorrência de Push | 4 aprovados. |
| PostgreSQL 18.6 `C`, suíte integral antes dos ajustes | 444 aprovados, 2 falhas do diretório, 0 erros, 0 skips. |
| SQLite, suíte integral após os ajustes | 446 aprovados, 0 falhas, 0 erros, 0 skips. |
| PostgreSQL 18.6 `C.utf8`, suíte integral após os ajustes | 446 aprovados, 0 falhas, 0 erros, 0 skips. Inclui concorrência B62 e Push e aplicação das migrations. |
| `check` e `makemigrations --check --dry-run` | Exit 0. Sem problemas ou alterações de schema. |
| `--production check --deploy` | Exit 0. Os mesmos 12 avisos foram reproduzidos. |

**Produção sintética.** Dos dez avisos OpenAPI, três indicam que Google Login, definir senha e trocar senha são omitidos pelo gerador de schema. Isso afeta clientes gerados e documentação, embora os testes HTTP das rotas passem. Os outros sete indicam quatro problemas de nomes ou tipos em componentes e três tipos de parâmetro de rota inferidos como string. São limitações reais do contrato OpenAPI, sem falha HTTP reproduzida. Os dois avisos HSTS correspondem a subdomínios e preload. A configuração ativa HSTS por 3600 segundos no host e redireciona para HTTPS em produção. Estender a política depende do controle dos subdomínios e do comportamento de HTTPS no ambiente publicado. O aviso de `staticfiles` é separado do `check --deploy` e vem da worktree de teste sem os arquivos coletados.

Os resultados da revisão estão em `/tmp/marujob-B58-review-{baseline,final,pg-baseline,pg-full,pg-utf8,production,check,migrations}.log`. A worktree está em tmpfs e depende da duração da sessão. A revisão preserva a worktree canônica e usa cópia recuperável do diff e deste relatório em armazenamento persistente.

## Arquivos da entrega

| Arquivo | Alteração |
| --- | --- |
| `chat/realtime.py` | Tratamento de falhas de conexão e timeout do Redis ao publicar eventos. |
| `chat/tests/test_api.py` | Regressão de envio persistido e aviso sanitizado durante falha simulada do Redis. |
| `chat/tests/test_consumer.py` | Reconexão de participante, presença e entrega de mensagem nova. |
| `core/tests/test_freelance_complementos.py` | Validação de nulabilidade, valor configurado, persistência e contrato B62. |
| `core/tests/test_opportunity_queries.py` | Projeção exata de vaga e limite padrão nulo. |
| `core/tests/test_integration_b43.py` | Jornada JWT B59/B60 com leitura negada a outras contas. |
| `core/tests/test_limite_profissionais.py` | Disputa concorrente pela última aprovação. |
| `core/tests/test_notificacoes.py` | Barreira restrita ao bloqueio da candidatura na corrida de decisões. |
| `core/tests/test_notificacoes_freelancer.py` | Disputa concorrente pela última posição de dispositivo. |
| `docs/B58-regressao-seguranca.md` | Evidências, achados e pendências da auditoria. |

## Pendências de homologação e F43

- Confirmar os critérios de aceite de B55 e B56 e cotejá-los com as funcionalidades já integradas.
- Confirmar a collation do PostgreSQL de homologação e produção. Homologar Redis compartilhado, incluindo queda durante handshake, assinaturas de grupos, reconexão e recuperação do histórico. A simulação desta entrega cobre a falha de publicação `group_send`.
- Confirmar políticas de sessão. O backend revoga JWT por troca de senha e inativação. A inspeção não localizou endpoint de logout ou blacklist. O teste de saída remove a credencial do cliente e confirma 401 nas requisições seguintes. A F43 deve fechar os sockets e remover a subscription ao sair, conforme o fluxo B60.
- Em homologação com contas fictícias, conferir origens, HTTPS, proxy, logs de acesso sem JWT, Google, mídia privada, reconsulta do histórico após desconexão e integração Web Push em dois navegadores. Produção não foi homologada.
- A B54 registrou banco, dump e mídia versionados e URLs legadas de mídia. Esta revisão confirmou por metadados Git que há arquivos nessas categorias. A autenticidade dos dados, a exposição das URLs legadas e a remediação dos artefatos continuam pendentes. Nenhum conteúdo desses artefatos foi inspecionado nesta entrega.

## PR sugerido

**Título** — B58 · Regressão de permissões, concorrência e resiliência do chat

**Descrição** — Corrige o retorno HTTP 500 após persistência de mensagens quando a publicação em Redis falha. Atualiza verificações estritas do contrato B62 e amplia as suítes existentes para aprovações e dispositivos concorrentes, reconexão WebSocket e isolamento do histórico B60 via JWT. A suíte passou com 446 testes em SQLite e PostgreSQL 18 com `C.utf8`. A auditoria segue parcial até confirmar B55, B56, a collation do ambiente publicado e a homologação operacional. Recomenda-se PR em rascunho para revisão técnica enquanto essas pendências estiverem abertas.

## Homologação B58 · 24/11/2026

A branch `B58-homologacao` foi criada em worktree isolada no commit
`9ba765195e38eec2d1e6740796ab2f4ee5e64705`. O `git fetch origin --prune`
falhou na resolução DNS de GitHub. A comparação ao vivo pelo conector do GitHub
confirmou que a DEV estava na mesma ponta, com divergência 0/0. O PR #31 foi
integrado à DEV nesse commit. Ele já está na base da worktree, sem commits
posteriores da DEV a incorporar. A worktree original preservou as alterações
locais em `.pdm-python`, `.vscode/settings.json` e `db.sqlite3`.
[PR #31](https://github.com/MaRuJoBs/Back_Marujob/pull/31)

### Código, banco e migrações

- O OpenAPI passou a documentar os corpos de entrada e de sucesso do login
  Google e das operações de definir e trocar senha. Os handlers HTTP e as
  permissões dessas rotas seguem com o comportamento anterior.
- A inspeção do schema gerado confirmou as três operações, os componentes de
  entrada e resposta e a exigência de JWT nas operações de senha. O
  `check --deploy` sintético passou com dez avisos, oito de OpenAPI e dois de
  HSTS. Os três avisos de rotas omitidas foram resolvidos. O aviso de tipo
  de `get_tipo` também aparece na rota Google agora documentada. Permanecem
  avisos sobre tipos de campos e parâmetros e sobre componentes aninhados.
- `check` passou sem questões. `makemigrations --check --dry-run` passou
  sem mudanças e `showmigrations --plan` listou 48 entradas no banco
  descartável. A alteração de documentação da API dispensa migration.
- O diretório usa regex com correspondência sem distinção de caixa para nome,
  profissão e cidade. PostgreSQL com locale `C` faz classificação de caixa de
  letras ASCII. A B58 anterior reproduziu duas falhas em `C` e aprovou a suíte
  em `C.utf8`. Esta sessão dispõe apenas do cliente PostgreSQL, sem servidor
  descartável disponível. A versão, o encoding, o provedor de collation e o
  `LC_CTYPE` do banco hospedado seguem por confirmar. A consulta do diretório
  foi preservada até ser possível testar uma correção no ambiente compatível.
  [Collations do PostgreSQL](https://www.postgresql.org/docs/18/collation.html)

### Simulações e inspeção de infraestrutura

- A suíte usa SQLite em memória, contas fictícias e o runner B54 com dotenv
  desabilitado e bloqueio de conexões externas. As verificações de Redis,
  Google, Cloudinary e Web Push previstas na suíte usam simulações na fronteira
  do serviço. O WebSocket usa o consumidor ASGI em processo.
- A configuração sintética exige hosts explícitos, segredo forte e DEBUG
  desativado, restringe CORS/CSRF a origens HTTPS explícitas e habilita cookies
  seguros, redirecionamento HTTPS e HSTS de 3600 segundos. Subdomínios e
  preload exigem confirmação operacional. Há limites de upload e de rotas
  sensíveis. O Redis é compartilhado para canais e contadores quando
  configurado. O fallback é por processo. Um GET anônimo via HTTPS ao admin
  na configuração sintética redirecionou para a página de login.
- O login Google, o processamento de imagens, o download autorizado do chat e
  o histórico de notificações têm contratos e testes existentes. Em particular,
  o teste de publicação interrompida cobre persistência e recuperação pelo
  histórico REST. A recuperação automática pelo cliente e o Redis real durante
  inscrição/reconexão ficaram pendentes.
- A expiração, inativação e troca de senha fazem a conexão perder acesso no
  próximo evento. Sair removendo a credencial local só encerra a sessão desse
  cliente. O backend atual carece de logout com revogação de JWT já emitido.
  A política de logout e fechamento do socket precisa ser confirmada em
  homologação. A transferência de Web Push entre contas usa o endpoint e as
  chaves do dispositivo. A entrega real e a troca de conta no navegador
  permanecem pendentes.
- O README menciona Render e PostgreSQL como opções do template. Isso só
  identifica a infraestrutura sugerida pelo repositório. Sem identificação e
  acesso autorizado ao serviço real, ficaram pendentes versão e collation do
  banco, migrations aplicadas, backup restaurável, Redis compartilhado, proxy,
  HTTPS, origens, IP real e limites de borda, logs sem JWT na query,
  configuração de segredos, Google OAuth, Cloudinary e Web Push em navegadores.
  A revisão foi local. `build.sh` e `Procfile` contêm execução de migrations, então
  iniciar o fluxo de publicação pode alterar o banco.
- B55 e B56 seguem **sem escopo documentado**. A busca nos metadados do GitHub,
  histórico, branches e documentação disponíveis não encontrou critérios de
  aceite. Chat REST/WebSocket, B59, B60 e B62 já constam na DEV. Atribuir
  qualquer dessas funcionalidades a B55/B56 exige a referência de escopo.

### Resultado dos testes desta revisão

| Execução | Resultado |
| --- | --- |
| SQLite em memória, seleção dos 422 casos síncronos após reinício da sessão | 421 aprovados, zero falhas de asserção e um erro. O teste do runner recebeu `EPERM` na escrita em um socketpair local. |
| SQLite em memória, suíte integral de 446 casos | A sessão foi interrompida após registrar dois erros em testes WebSocket. Um desses erros, na conexão anônima, foi reproduzido isoladamente como timeout no handshake do comunicador ASGI. Restaram 22 dos 24 casos assíncronos sem veredito confirmado. |
| PostgreSQL e Redis reais | Sem servidor descartável disponível nesta sessão. |
| Hospedagem | Verificações operacionais pendentes de identificação e acesso autorizado. |

O resultado consolidado por caso foi de 421 aprovados, zero falhas de
asserção, três erros e 22 sem resultado confirmado. A seleção síncrona
incluiu permissões, candidaturas, avaliações, concorrência, migrações, chat
REST, notificações e Web Push simulado. O erro do socketpair confirma uma
restrição do ambiente do runner. Os erros WebSocket continuam sem causa
confirmada nesta execução e bloqueiam o aceite do chat. A referência de 446
aprovações da revisão anterior permanece histórica.

### Dados versionados · bloqueador de homologação

O inventário agregado de HEAD confirmou 11 registros de conta em
`db.sqlite3`, dois em `dump.json` e 17 arquivos em `media/`. Cada registro de
conta contado tem e-mail e hash de senha preenchidos. Os totais por artefato
podem se sobrepor. Quatro imagens possuem EXIF. Nenhuma tinha a tag GPS
inspecionada. As referências Git disponíveis contêm 23 commits que tocaram o
banco, três que tocaram o dump e seis que tocaram mídia. O inventário não
determinou a origem dos registros. Também não confirma ausência de segredos
em revisões antigas. Nenhum valor de registro foi publicado no relatório.

Antes de liberar o ambiente para homologação, os responsáveis devem confirmar
origem e público exposto, restringir acesso aos artefatos e avaliar eventual
troca de credenciais ou revogação de sessões se os dados forem reais ou
reutilizados. Retirada do índice, tratamento do histórico e cópias, e
revogação de URLs legadas de mídia exigem uma intervenção autorizada e
coordenada. A regra de ignore existente cobre novos arquivos dessas
categorias e não elimina cópias já versionadas.

### B63 · viabilidade do povoamento demonstrativo

Os modelos existentes suportam os quantitativos solicitados. Criar 20 contas
ativas com papel exclusivo Empresa e até um `EmpresaPerfil` por conta, 40
contas ativas com papel exclusivo Usuário, 60 `Freelance` vinculadas às
empresas, 50 `Portfolio` vinculados aos freelancers e 30 `Candidatura` com
pares distintos de freelancer e vaga. Respeitar unicidade de e-mail,
`google_id` quando preenchido e par freelancer/vaga. Usar os validadores
existentes e as regras de status, localização e limite de profissionais das
vagas. A publicação no diretório exige `perfil_publico` no freelancer ativo e
elegível. Cada projeto exibido exige também `publico`. Ambos os flags
começam desativados.

A criação de candidatura pelo fluxo da API gera notificação para a empresa.
Decisões podem registrar histórico e disparar Web Push após commit.
A execução futura precisa isolar as contas e o transporte externo e cuidar
dos side effects de uploads. Usar identificação de lote, IDs registrados
fora dos dados públicos, e-mails fictícios únicos, execução idempotente e
plano de remoção pelo manifesto. Validar backup com restauração em ambiente
separado antes da execução hospedada. A B63 depende de autorização própria.
Nenhum dado demonstrativo foi criado.

## Revalidação direcionada para a entrega · 24/11/2026

### Exposição dos artefatos

O metadado `visibility` do GitHub retornou `public` para
`MaRuJoBs/Back_Marujob`. O commit da DEV auditado contém o banco, o dump e
os 17 arquivos de mídia já inventariados. Os 11 registros do banco e os
dois do dump usam endereços em domínios não reservados para exemplos.
Dois registros do banco têm identificador externo preenchido no campo de
Google. Esses sinais, junto com os hashes e a mídia com EXIF, justificam
tratar o conteúdo como potencialmente real. A inspeção agregada não verificou
titularidade, origem, validade das credenciais ou publicação de cada URL
legada. Não houve contato com as contas ou divulgação de valores.
[Repositório no GitHub](https://github.com/MaRuJoBs/Back_Marujob)

Os responsáveis devem avaliar contenção imediata do acesso ao repositório,
inventariar revisões e cópias públicas e identificar a origem dos registros.
Se os dados forem reais, tratar a exposição com os responsáveis por
privacidade e avaliar redefinição de senhas, revogação de sessões e
rotação de credenciais possivelmente expostas. Uma mudança de visibilidade
não recolhe clones já feitos. A retirada dos arquivos do versionamento,
o tratamento do histórico, forks e caches e a revogação de URLs legadas
precisam ser coordenados e autorizados. Preparar fixtures sintéticas sem
dados pessoais para substituir esses artefatos. Nenhum arquivo foi
removido e nenhuma referência Git foi alterada nesta revisão.

### Autenticação e demonstração

A execução dirigida a autenticação, segurança B54 e jornadas B43 aprovou
49 testes em SQLite em memória. A verificação do OpenAPI anterior confirmou
os três contratos e foi feita sobre a mesma versão de `core/views/user.py`.
Essas evidências sustentam demonstração local das jornadas REST aprovadas
com contas fictícias e banco descartável. Google e serviços externos
foram simulados. A disponibilidade do ambiente publicado, dos serviços
integrados e do banco hospedado continua sem validação autorizada.

### Diagnóstico dos três erros

O teste B54 do runner voltou a acusar erro. Um controle sob o runner
reproduziu `EPERM` na escrita de um socketpair local, sem passar pelo
backend. A abertura de socket IPv4 também recebeu `EPERM`.

Os dois testes WebSocket originais foram reexecutados com observação
temporária da escrita em sockets. Em ambos, `asyncio` recebeu `EPERM`
em `_write_to_self` ao tentar acordar o loop, seguido do timeout no
comunicador ASGI. Um controle sem Django e sem código do MaRuJoB's
confirmou o padrão: o comunicador devolveu o fechamento 4401 em execução
direta, mas expirou quando a chamada cruzou `async_to_sync` e
`sync_to_async`. Isso explica os dois erros observados e o erro do runner.
A restrição impede usar esses resultados como aceite funcional do chat.

A rodada por processo reexecutou os 24 casos WebSocket. Entre os 22
anteriormente inconclusivos, 14 terminaram com timeout no comunicador ASGI
e oito atingiram o limite de 22 segundos do processo. Os dois casos
originais também tiveram timeout na reexecução instrumentada. Nenhum dos
24 recebeu confirmação de aprovação nesta sessão. A execução completa
desses casos em um ambiente que permita a comunicação local do loop
permanece necessária para o aceite do chat.

**Veredito para a entrega.** Demonstração local das jornadas REST aprovadas
com dados fictícios está apta pelo teste funcional dirigido. Chat em tempo
real e serviços hospedados permanecem sem homologação. A branch segue
bloqueada para PR de homologação pelo aceite do WebSocket e pela exposição
dos artefatos no repositório público.

## Validação final para apresentação · 24/11/2026

A worktree `B58-homologacao` continua em `9ba7651`. O fetch voltou a
falhar por resolução DNS. A comparação atual do GitHub confirmou identidade
com a DEV, com zero commits de diferença. O PR #31 continua na base.
A worktree original da DEV manteve suas três alterações locais.

| Verificação dirigida | Resultado |
| --- | --- |
| Cadastro e login por papel, JWT, jornadas B43, vagas, pesquisa, filtros, candidaturas, decisão, B62, perfil, portfólio, permissões, notificações e chat REST | 239 aprovados, zero falhas ou erros. SQLite descartável com contas fictícias e migrações aplicadas pelo runner. |
| Chat REST com Redis indisponível simulado | O teste incluído nas 239 aprovações confirma HTTP 201, uma mensagem persistida por envio e recuperação pelo histórico autorizado após erro de conexão ou timeout de publicação. Um novo POST do cliente constitui outro envio e pode criar outra mensagem. |
| WebSocket, reconexão e isolamento de conversa | A reexecução selecionada registrou erro no caso de reconexão. A execução atingiu o limite antes de concluir o teste de isolamento. A rodada anterior dos 24 casos e o controle com EPERM permanecem a evidência de limitação do ambiente. Não havia ambiente local seguro fora dessa restrição disponível para homologar WebSocket. |
| Contrato OpenAPI e estilo | A versão da view é idêntica à verificada no schema. Google público, operações de senha com JWT e componentes de entrada e resposta presentes. Ruff check e format check aprovados. |
| Configuração e migrations | `makemigrations --check --dry-run` passou sem mudanças. `check --deploy` sintético passou com oito avisos OpenAPI e dois HSTS, já descritos acima. |
| Hospedagem | Sem acesso autorizado para confirmar PostgreSQL, Redis, HTTPS, CORS, autenticação, rotas, logs ou disponibilidade do serviço publicado. |

A remoção do JWT no cliente foi coberta pela jornada. O backend não revoga
um JWT já emitido apenas por logout local. Troca de senha, inativação e
expiração têm testes próprios. Google, Cloudinary, Redis e Web Push usaram
simulações nos testes aplicáveis.

### Prioridade de segurança

**Gravidade alta, com tratamento imediato pelos responsáveis.** O GitHub
reconfirmou o repositório público. Os 19 caminhos em HEAD são o banco,
o dump e 17 arquivos em `media/`. As referências locais registram 23
commits que tocaram o banco, três que tocaram o dump e seis que tocaram
mídia. Os indícios de dados reais descritos na revalidação anterior
continuam aplicáveis à mesma revisão. O alcance potencial inclui acesso
anônimo a versões públicas, clones, forks e cópias já obtidas. O número
de terceiros que acessaram o conteúdo é desconhecido.

O `.gitignore` agora cobre bancos SQLite com outros nomes, arquivos
auxiliares, exports `.dump` e a pasta `backups/`, além de `dump.json`
e `media/`. As regras foram verificadas com nomes sintéticos. Arquivos
já rastreados continuam no índice e no histórico. Após autorização, os
responsáveis devem preservar evidências sob acesso restrito, conter
acesso público, avaliar a origem e as credenciais, retirar os artefatos
do índice e decidir sobre tratamento do histórico e das cópias. Para
evitar recorrência, um check obrigatório no PR pode rejeitar alterações
em caminhos sensíveis já rastreados e a entrada de novos bancos, dumps e
mídias privadas. Até esse controle existir, a revisão do diff continua
necessária. Nenhum artefato foi excluído e a visibilidade foi preservada.

**Classificação: APTO COM RESSALVAS.** O backend está apto para demonstração
local dos fluxos REST aprovados com dados fictícios. A apresentação
hospedada e o chat em tempo real não têm aceite nesta sessão. A indicação
é aguardar o tratamento da exposição pública e um teste válido de
WebSocket antes de abrir um PR de homologação. A collation PostgreSQL,
a mídia legada, B55/B56 e as integrações externas seguem como pendências.

## Fechamento e responsáveis pela entrega

A comparação ao vivo reconfirmou a DEV em `9ba7651`. A branch de
homologação está nessa base e tem somente três arquivos modificados na
worktree: `.gitignore`, `core/views/user.py` e este relatório. O fetch
voltou a falhar por DNS. O índice está limpo e o diff não inclui
artefatos de dados, mídia ou segredos.

Uma cópia temporária contendo somente código e configurações de teste,
sem banco, dump ou mídia versionados, repetiu a seleção com **239
aprovações**. Ela demonstrou que esses artefatos podem ser separados
do código para os fluxos REST validados. Imagens para a apresentação
devem ser fictícias. A geração do schema confirmou os três contratos
OpenAPI, Ruff e o check de migrations passaram, e as regras de ignore
foram verificadas por caminho. A reexecução de controle voltou a obter
dois erros: EPERM no socket local e timeout no handshake anônimo
WebSocket. Não há outra execução autorizada disponível nesta sessão
para confirmar o WebSocket.

| Responsável | Próxima ação |
| --- | --- |
| Proprietário do repositório e responsáveis por segurança e privacidade | Autorizar e coordenar a contenção do acesso público, preservar evidências em armazenamento restrito, determinar a origem dos dados e a extensão da exposição, e decidir revogação, redefinição de senhas ou rotação conforme a avaliação. |
| Proprietário e mantenedores do Git | Autorizar a retirada dos 19 caminhos do índice mantendo cópias locais que precisem ser preservadas, substituir o material de demonstração por fixtures sintéticas e aprovar eventual intervenção coordenada no histórico, referências, forks e caches. O histórico pode continuar acessível por cópias já feitas. |
| Equipe do backend | Reexecutar os 24 casos assíncronos em ambiente autorizado com comunicação local funcional antes do aceite do chat em tempo real. |
| Responsável pela hospedagem | Identificar o serviço e conceder acesso de leitura para confirmação de HTTPS, disponibilidade, PostgreSQL, Redis, WebSocket, rotas e logs sanitizados. |

O risco de exposição é bloqueador de publicação até avaliação e
contenção pelos responsáveis. A apresentação local permanece apta para
os fluxos REST validados. A hospedagem segue sem homologação e a
recomendação é aguardar antes do PR e do merge de homologação.
