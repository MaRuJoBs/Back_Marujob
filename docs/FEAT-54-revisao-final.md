# B54 — Revisão final e correções autorizadas

Data: 2026-11-11. Base efetiva: FEAT-54 em `69e2bdf21dd49fe038a43f8b05d7e3c07b0a8eec` mais alterações locais desta revisão, ainda sem commit/push. Este documento atualiza o [relatório inicial](FEAT-54-auditoria-seguranca.md); não reinicia a auditoria.

**Veredito: AUDITORIA INCOMPLETA — VALIDAÇÕES PENDENTES.** B54-01 e B54-02 estão corrigidos e validados localmente no escopo descrito abaixo. B54-03 continua não verificada, a suíte integral permanece vermelha pela dependência B45 e não houve homologação operacional.

## A. Estado Git e dependências

- Repositório confirmado: MaRuJoBs/Back_Marujob, remoto HTTPS correto, branch FEAT-54 na pasta principal.
- HEAD local/remoto FEAT-54 na abertura: `69e2bdf`; DEV após fetch: `0226c2e0adbb17546dfe74e91df14dd03d4cd419`, sem avanço desde a auditoria anterior. FEAT-54 tem dois commits exclusivos e nenhum commit pendente da DEV; não foi necessário integrar outra base.
- Worktrees: pasta principal FEAT-54; `.audit-b54` detached em `b832120`; worktree temporária B46 detached em `a54ee49`. Nenhuma outra worktree mantém FEAT-54. Somente a pasta principal foi utilizada nesta revisão.
- Alterações preexistentes preservadas: core.png, db.sqlite3 e uma imagem não rastreada. Não foram incluídas nem modificadas pela auditoria. O diretório `.audit-b54` preexistente permanece fora da entrega.
- Executados antes das edições: rev-parse, status, branch atual, remote, worktree list, fetch --prune, branch -a, logs DEV/HEAD, comparação DEV...HEAD e inspeção do PR.
- Nova busca de PRs com estado all retornou os mesmos #1–#23. Reconsultados individualmente #8, #12, #19, #20, #21, #22 e #23, com merged_at e diff relevante. O [histórico completo anterior](FEAT-54-historico.md) permanece válido.
- #8, #12, #19, #20 e #21 continuam integrados à DEV; #22 e #23 seguem abertos e sem merged_at. Nenhum código do #23 foi copiado, e nenhum merge/rebase foi executado.

## B. PR #22 e autorização complementar

PR existente: [#22](https://github.com/MaRuJoBs/Back_Marujob/pull/22), base DEV, head FEAT-54, aberto e draft. O remoto contém a auditoria inicial e a correção de cookies; ainda não contém as alterações locais descritas aqui. Não foi criado PR duplicado nem atualizada a descrição remota nesta revisão.

A autorização complementar permite corrigir B54-01/B54-02 na própria FEAT-54. Por isso a proposta anterior de FIXs separados para esses dois achados foi implementada localmente, sem abrir novas branches/PRs. Permanecem separados os escopos de JWT, foto Google e tratamento de dados versionados. Não há autorização para commit, push, merge ou deploy neste estágio.

As duas regras de cookies Secure em PRODUCTION continuam intactas. Não foram alterados hosts, origens, proxy, HSTS, SSL redirect, duração de tokens, modelos, migrations, permissões de negócio ou endpoints.

## C. Dependência PR #23 e suíte integral

O #23 continua aberto, `merged_at=null`, head `e8cb0daf5015b0db1c69264e382e8ce3febd199d`. O diff tem somente `core/tests/test_freelancer_publico.py`, três linhas adicionadas e duas removidas: captura as folhas atuais do grafo, prepara a migration dentro do try e restaura todas as folhas no finally. Não altera arquivos de migrations de produção.

O resultado de 246 testes aprovado no texto daquele PR não foi atribuído à B54. Na base efetiva desta revisão:

- Antes da correção local: **253 testes, dois erros, exit 1**.
- Depois: **267 testes, 265 sem erro e os mesmos dois erros, exit 1**.
- Erros: `DecisaoConcurrencyTests.test_simultaneous_opposite_decisions_never_overwrite_the_winner` e `NotificacaoCreationConcurrencyTests.test_simultaneous_applications_create_exactly_one_application_and_notification`.
- Ambos ocorrem na preparação após o teste histórico B45: `core_freelance` sem coluna `modalidade`.
- Os mesmos cenários de concorrência passam no conjunto independente de regressão, em banco novo.

Não foram pulados testes nem reescrito o teste B45. Depois do merge autorizado do #23 na DEV, será necessário avaliar a integração autorizada dessa DEV na FEAT-54 e executar novamente a suíte integral, em um único processo. Até lá não se declara suíte aprovada.

## D. Matriz atual dos achados

| ID | Severidade original | Evidência e impacto | Correção/situação atual |
|---|---|---|---|
| B54-01 | Média | Access/refresh anteriores à alteração de senha mantinham acesso. A versão instalada 5.5.1 inclui claim e checagem de senha no access com CHECK_REVOKE_TOKEN, mas seu TokenRefreshSerializer não faz essa checagem. | Corrigido localmente: CHECK_REVOKE_TOKEN=True e serializer de refresh que reutiliza JWTAuthentication.get_user antes do serializer padrão. Tokens antigos ou sem claim retornam 401; login novo e Google continuam funcionais. |
| B54-02 | Média | Download remoto contornava conteúdo/tamanho; storage OSError retornava 500 depois da criação da conta. | Corrigido localmente: download em streaming limitado, sem redirects, HTTPS sem credenciais na URL, validação existente e foto opcional com falhas tratadas. Login/cadastro verificado mantém 200/tokens e nenhuma referência inválida de foto nos cenários testados. |
| B54-03 | Média; reavaliar se dados reais confirmados | SQLite e dump versionados com e-mails e hashes; mídia e histórico persistentes. | Não verificada. Inventário sanitizado aprofundado; nenhum dado removido/alterado. Plano separado abaixo. Não há prova de exposição pública nem de credenciais válidas. |
| B54-04 | Baixa | W004 (HSTS) e W008 (redirect) no app sintético. A existência/adequação da borda TLS não foi testada. | Pendente infraestrutura. Cookies Secure preservados; nada ativado automaticamente. |
| B54-05 | Informativa | Sem throttle explícito na configuração da aplicação; controles da borda não confirmados. | Pendente decisão/validação de rate limit e monitoração. Não se executou ataque ou teste de carga. |

### JWT: implementação, compatibilidade e limites

`app/settings.py` habilita CHECK_REVOKE_TOKEN e configura `core.serializers.tokens.PasswordBoundTokenRefreshSerializer`. O serializer valida assinatura/expiração/tipo refresh e reutiliza a mesma checagem de identidade, atividade e estado da senha do access. Depois delega a resposta ao serializer do SimpleJWT, preservando o formato `{access: ...}`, validade e sem habilitar rotação/blacklist. Ausência de usuário retorna 401, sem erro de banco exposto.

Nenhuma migration é necessária. Não há blacklist nova nem promessa de logout/revogação individual por dispositivo. A marca é derivada do hash de senha pelo próprio SimpleJWT, não contém a senha em texto. O custo do refresh inclui uma consulta adicional de usuário. Tokens emitidos simultaneamente a uma mudança podem produzir resposta de refresh inutilizável após a mudança; não podem autenticar com o estado antigo.

**Impacto de implantação:** tokens já emitidos sem claim serão rejeitados e todos esses usuários precisarão entrar novamente. A própria sessão usada para trocar/definir senha deixa de autenticar após sucesso; o frontend deve tratar 401 e solicitar novo login. O JSON e os endpoints de troca/definição permanecem iguais. Tokens de Google com senha inutilizável continuam válidos até mudança efetiva desse estado; definir a primeira senha invalida os anteriores. O retorno de `/api/token/verify/` continua sendo verificação criptográfica/expiração, não comprovação de sessão autorizada; o controle efetivo está no refresh e na autenticação dos recursos.

Regressões substituem os antigos testes `finding_*`: troca de senha rejeita access e refresh antigos, login com nova senha funciona; refresh atual preserva resposta; tokens sem claim exigem login; conta inativa/excluída é negada; primeiro password Google invalida tokens anteriores e novo login Google funciona. O teste antigo de senha foi ajustado para renovar suas credenciais depois de mudar deliberadamente o estado da senha no próprio teste.

### Foto Google: implementação e consistência

`core/google_photo.py` concentra a obtenção opcional; `core/views/user.py` chama o helper nos mesmos dois locais de cadastro/login, depois de validar claims, e não baixa novamente se já existe foto.

- URL continua proveniente exclusivamente de `picture` de claims verificadas; nenhum novo parâmetro de API foi criado.
- Somente HTTPS, hostname presente e sem credenciais na URL; não há whitelist de domínios nem alegação de prevenção geral de SSRF. Não foi demonstrado controle arbitrário de URL pelo usuário antes da verificação Google.
- `timeout=10`, `stream=True`, `allow_redirects=False`. Respostas diferentes de 200 são omitidas; um redirect legítimo poderá deixar o perfil sem foto, preservando login.
- Leitura interrompida ao ultrapassar MAX_IMAGE_UPLOAD_BYTES; Content-Length e MIME informados pelo servidor não são confiados. A resposta é fechada pelo context manager mesmo em falha de leitura.
- Reutiliza `ValidatedImageField`: conteúdo real JPEG/PNG/WebP e proteção de dimensões Pillow. Nome final usa a extensão do formato detectado. Não reutiliza nomes vindos da URL e não sobrescreve foto existente.
- Captura validações Django/DRF e as mesmas classes de erro do storage comum, incluindo Cloudinary/OSError/Requests. Log genérico sem URL, bytes, credencial ou texto da exceção; referência anterior é restaurada em memória.
- A conta validada é mantida intencionalmente sem foto quando a foto opcional falha. Isso segue a tolerância que já existia para erros de rede; elimina o 500 de storage comprovado, sem excluir conta nem envolver rede em transação longa.

**Limite transacional residual:** banco e storage externo não participam de transação distribuída. Falha remota que escreva bytes e depois lance exceção, ou falha de banco depois do upload bem-sucedido, pode deixar objeto sem referência. Nenhuma exclusão remota automática foi acrescentada; a reconciliação de órfãos requer política e autorização próprias. O timeout é por conexão/leitura Requests, não prazo total da operação; o streaming é limitado em bytes, mas conexões lentas exigem limite de tempo na infraestrutura. Estas limitações não são apresentadas como corrigidas.

Testes cobrem conteúdo não imagem, JPEG/PNG/WebP, GIF recusado, dimensão excessiva, limite cumulativo interrompendo o iterador, timeout antes/durante leitura, fechamento, redirect, URL não HTTPS/com credenciais, storage local/Cloudinary simulado, login existente, preservação de foto e credencial não verificada sem download. Nenhuma requisição real foi realizada.

## E. Dados versionados: evidência sanitizada e plano separado

Novo comando: `pdm run python scripts/audit_b54_artifacts.py`. Lê blobs de HEAD via Git em memória. O SQLite versionado é desserializado em conexão SQLite `:memory:` com query_only; não se abre o arquivo SQLite da worktree, não se carrega .env e não se escreve cópia em disco. Mídia é inspecionada por metadados em memória, sem renderizar pessoas ou imprimir valores EXIF. A inspeção do banco usa dados apenas para contagem de auditoria, nunca como fixtures ou contas de teste.

| Evidência no HEAD 69e2bdf | Resultado |
|---|---|
| dump.json | 2 registros User, 2 e-mails preenchidos, 2 hashes pbkdf2_sha256 |
| db.sqlite3 versionado | 11 registros User, 11 e-mails preenchidos, 11 hashes pbkdf2_sha256 |
| media | 17 arquivos; 4 com EXIF, nenhum com tag GPS EXIF detectada; zero ilegíveis |
| Histórico local em todas as refs consultadas | 23 entradas de log para banco, 3 para dump, 6 para mídia e 10 para .env.exemplo; são entradas de commits que tocam os caminhos, não contagem de versões únicas |
| .env | Não rastreado, ignorado; zero entradas de log para esse caminho nas refs disponíveis |
| Política de novos arquivos | .env.exemplo, db.sqlite3, dump.json e arquivo de mídia de prova não são ignorados |
| Indicadores heurísticos no banco/dump/.env.exemplo atuais | 0 JWT-like, 0 marcadores de chave privada, 0 tokens GitHub-like |

Nenhum e-mail, hash, token, senha ou metadado pessoal foi impresso. Nomes de algoritmos e contagens não comprovam que os registros sejam sintéticos. A origem é **não verificada**; não se tentou autenticar contas, consultar provedores nem verificar credenciais. Zero indicadores dessas três heurísticas não cobre senhas, chaves de outros provedores, valores arbitrários, conteúdo visual de mídia, esteganografia ou todos os blobs históricos. A inspeção EXIF não prova ausência de localização ou dados pessoais em texto, imagem ou outras tags.

Plano **FIX-PRIV-dados-versionados**, sem execução destrutiva:

1. Responsáveis pelo repositório/dados confirmam origem, finalidade, acesso efetivo ao Git/CI/releases/forks e se hashes correspondem a contas utilizáveis. Definir responsável e prazo antes de homologação; nenhum prazo ou aceite foi presumido.
2. Se material real/segredos for confirmado, avaliar incidente e LGPD com equipe responsável, revogar sessões e rotacionar segredos/credenciais afetados; não rotacionar por inferência sem evidência de quais segredos estão envolvidos.
3. Propor fixtures estritamente sintéticas e política .gitignore/CI para banco, dumps e mídia. Arquivos já rastreados exigem remoção do índice/HEAD mediante aprovação; acrescentar ignore não remove histórico.
4. Inventariar blobs históricos e cópias distribuídas em ambiente controlado, com scanner sanitizado aprovado, sem transmitir dados a serviços externos.
5. Somente com autorização específica avaliar remoção controlada do histórico, coordenação de clones/forks/backups e revisão de permissões. Não foi executado filter-repo, force push ou exclusão.

## F. Runner e avisos de produção

O runner existente foi lido antes de uso e não foi modificado. Na versão instalada python-dotenv 1.2.2, PYTHON_DOTENV_DISABLED impede load_dotenv. Settings normais usam core.tests.settings e SQLite em memória; --production aceita somente check e usa app.settings com valores sintéticos. Sockets connect/connect_ex são bloqueados; uploads nos testes recebem storage temporário ou mock.

O runner não é sandbox: opções genéricas de Django como --pythonpath/--testrunner e código de testes arbitrário podem mudar o que é importado/executado; subprocessos e acesso ao filesystem não são isolados por ele. Foram usadas somente as invocações auditadas abaixo. Melhoria proposta separada: rejeitar opções que substituam importação/test runner e validar novamente a configuração de banco antes da execução. Nenhuma evidência de efeito colateral nos comandos usados foi encontrada; não se autoriza usá-lo com argumentos não revisados.

`check --deploy` voltou a retornar **12 avisos, exit 0**:

- W004: HSTS ausente; depende da cobertura TLS e subdomínios. Não habilitar sem plano de borda.
- W008: SSL redirect ausente no app; pode ser responsabilidade da borda. Validar redirect, sanitização de X-Forwarded-Proto e opt-in TRUST_X_FORWARDED_PROTO antes de qualquer mudança.
- Sete W001 de schema: três parâmetros ID de viewsets, três métodos sem tipagem em serializers de usuário e colisão de componentes Nested.
- Três W002 de schema: GoogleLoginView, DefinirSenhaView e TrocarSenhaView sem serializer de documentação.

Os diagnósticos de schema não foram tratados como bypass de autenticação. W012/W016 não retornaram: as regras de cookies Secure permanecem. Isso não comprova TLS, CORS/CSRF ou storage do deploy real. Nenhuma configuração real foi carregada; origens sintéticas não atestam compatibilidade com o frontend publicado.

## G. Execuções desta revisão

Todos os comandos abaixo foram executados; não são apenas recomendações:

```powershell
pdm run python scripts/audit_b54.py check
pdm run python scripts/audit_b54.py makemigrations --check --dry-run
pdm run python scripts/audit_b54.py showmigrations --plan
pdm run python scripts/audit_b54.py test --noinput
pdm run python scripts/audit_b54.py --production check --deploy
pdm run python scripts/audit_b54.py test core.tests.test_security_b54 core.tests.test_authentication core.test_google_auth --noinput
pdm run python scripts/audit_b54.py test core.tests.test_security_b54 core.tests.test_authentication core.test_google_auth core.tests.test_profiles_portfolios core.tests.test_empresa_perfil core.tests.test_notificacoes --noinput
pdm run python scripts/audit_b54_artifacts.py
```

| Execução | Resultado real |
|---|---|
| Baseline atual, antes de editar runtime | 253 testes, 2 erros B45, exit 1 |
| Baseline B54 + notificações isolados | 30/30, exit 0 |
| Correção inicial, auth/Google/B54 | 48 testes, 1 erro introduzido: ValidationError Django da imagem não capturada; corrigido antes da entrega |
| Nova execução após ajuste | 48/48, exit 0 |
| Regressão ampliada final | 117/117, exit 0; inclui 19 testes B54 atuais e módulos existentes de autenticação, Google, perfil/portfólio, B46 e notificações |
| Suíte integral final, único processo | 267 testes, 265 sem erro, mesmos 2 erros B45, exit 1; NÃO aprovada |
| check | exit 0, nenhuma questão |
| makemigrations --check --dry-run | exit 0, No changes detected; nenhuma migration criada |
| showmigrations --plan | exit 0, grafo resolvido até core.0022_empresa_perfil em banco novo |
| check --deploy PRODUCTION sintético | exit 0, 12 avisos detalhados acima |
| Inventário sanitizado | exit 0, contagens da seção E |
| Ruff check final | exit 0, oito arquivos Python conferidos (sete novos/alterados nesta revisão e runner existente) |
| Ruff format --check final | exit 0, oito arquivos já formatados |
| git diff --check | exit 0, apenas avisos de conversão futura LF/CRLF; sem erros de whitespace |
| git diff --cached --stat | vazio, nenhum arquivo em staging |

Avisos preexistentes de staticfiles ausente e schema permanecem. Ruff foi utilizado nos arquivos alterados, corrigindo somente imports/formatação e pequenos diagnósticos dos arquivos novos. Nenhum linter novo instalado. PostgreSQL, Google/Cloudinary reais, logs e proxy publicados, scan atualizado de CVEs e avaliação jurídica não foram executados; dependem de ambiente, ferramentas e autorização adequados.

Os testes de isolamento já existentes continuam exercitados na suíte integral: empresas/freelancers A/B e anônimo, 401 JWT, 403 papel/proprietário em oportunidades, 404 em querysets privados, payloads de proprietário ignorados, privacidade de portfólios, candidaturas/notificações, B46 e diretório B45. As correções não alteraram esses contratos. Proteger a API não torna privadas as URLs do storage: revogar publicação não invalida URL previamente conhecida. Acesso ao storage real continua pendente.

## H. Arquivos locais desta revisão e risco

| Arquivo | Mudança | Risco de regressão |
|---|---|---|
| app/settings.py | Dois itens SIMPLE_JWT para senha/revalidação de refresh | Reautenticação de tokens antigos; teste e comunicação de implantação necessários |
| core/serializers/tokens.py (novo) | Refresh reutiliza a checagem do access e preserva formato padrão | Consulta adicional; expiração/usuário inválido cobertos |
| core/google_photo.py (novo) | Download e validação compartilhados dos dois caminhos Google | Foto opcional pode ser omitida em redirect/limites/falhas; login preservado |
| core/views/user.py | Substitui somente os dois blocos duplicados da foto pelo helper | Mesmas condições de chamada e mesma identidade validada |
| core/tests/test_authentication.py | Credenciais renovadas após mudança de senha no teste e novo local do mock de foto | Só teste, mantém asserções de negócio |
| core/tests/test_security_b54.py | Converte caracterização em regressão segura e amplia para 19 testes | Só teste; não conserva asserção de vulnerabilidade como aprovação |
| scripts/audit_b54_artifacts.py (novo) | Inventário em memória com saída agregada | Leitura local de blobs versionados; sem valores nos resultados |
| docs/FEAT-54-auditoria-seguranca.md | Indica explicitamente que é histórico e aponta revisão atual | Evita interpretar status antigo como situação atual |
| docs/FEAT-54-revisao-final.md (novo) | Evidências atuais, decisões, riscos e B43 | Documentação |

Nenhum arquivo de migration, frontend, artefato de dados ou teste B45 foi alterado. Diff comum não inclui os arquivos novos enquanto não rastreados; revisar também seu conteúdo integral antes de staging. Alterações preexistentes nos binários e a worktree de inspeção ficam fora da entrega.

## I. Preparação B43 e decisões de merge

Bloqueiam aprovação da homologação:

- Dependência #23 não integrada e suíte inteira sem exit 0. Reexecutar sobre a base real após integração autorizada, sem copiar o FIX.
- B54-03 sem responsável/decisão de tratamento e sem comprovação da origem dos registros.
- Correções B54-01/B54-02 ainda locais e não revisadas/integradas; confirmar reautenticação no cliente e cenários de erro em homologação sintética autorizada.
- Falta de validação representativa de PostgreSQL, TLS/proxy/origens e storage; nenhuma equivalência com produção foi presumida.

Exigem decisão de responsáveis: tratamento de dados/histórico, comunicação do encerramento de sessões, política de foto opcional e reconciliação de órfãos, proteção de arquivos privados, retenção/EXIF e limites da borda. Recomendações: corrigir schema, acrescentar monitoração sanitizada e formalizar rate limits conforme evidência de infraestrutura. Reavaliar dependências com scanner atualizado antes do aceite final.

O checklist B43 do relatório inicial continua aplicável, com estas atualizações: manter regressões JWT/foto exigindo comportamento seguro; repetir 19 testes B54 e a suíte completa após #23; conferir tokens antigos sem claim, Google após primeira senha, refresh após troca e usuários inativos/excluídos; confirmar política de mídia e origem dos artefatos.

**PR de auditoria tecnicamente apto a merge:** ainda não recomendo aprovar nesta revisão. Há correções locais não publicadas e uma suíte integral vermelha por dependência conhecida. Os 117 testes isolados aprovados dão evidência para revisão das correções, mas não substituem a execução integral após #23. Um merge apenas documental, com ressalvas explicitamente aceitas, seria decisão dos mantenedores; não equivale a liberação do sistema.

**Sistema pronto para homologação:** não. Os bloqueios e decisões acima permanecem, mesmo se o PR vier a ficar sem conflitos no GitHub.

Não houve git add, commit, push, merge, rebase, exclusão ou deploy nesta revisão. Qualquer publicação das alterações locais depende de nova autorização.
