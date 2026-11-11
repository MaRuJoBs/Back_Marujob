# B54 — Auditoria de segurança, privacidade e produção

Data: 2026-11-11. Veredito: **INCOMPLETA — VALIDAÇÕES PENDENTES**.

A análise de código e os testes locais foram realizados. Há achados médios comprovados, pendência de classificação dos artefatos versionados, dois erros preexistentes na suíte integral e validações operacionais não executadas. Isto não libera B43 nem atesta segurança absoluta ou conformidade jurídica com LGPD.

## A. Estado inicial, histórico e escopo

- Repositório confirmado: `https://github.com/MaRuJoBs/Back_Marujob.git`.
- Raiz: `C:/Users/Ricardo/Documents/Back_Marujob`; branch inicial FEAT-46, commit `0c1cf9f`.
- Alterações preexistentes preservadas: `core.png`, `db.sqlite3` e uma imagem não rastreada em `media/portfolios/`. Nenhum desses arquivos compõe esta entrega.
- Worktree já existente em diretório temporário, detached em `a54ee49`, não foi utilizada.
- `git fetch origin --prune` executado com sucesso após permissão para escrever FETCH_HEAD.
- DEV remota atualizada: `0226c2e0adbb17546dfe74e91df14dd03d4cd419`.
- FEAT-54 remota já existia: `b832120cd7454d9a0b2b45878e47d087638f7f01`, exatamente um commit à frente da DEV e nenhum commit exclusivo da DEV. Nenhum rebase/reset foi feito.
- Trabalho começou na worktree exclusiva `.audit-b54`, na FEAT-54. A pedido do usuário para visualizar a branch na pasta principal, essa worktree foi destacada em detached HEAD e a pasta principal passou à FEAT-54. Os dois arquivos novos foram transferidos para a pasta principal sem sobrescrita. `.audit-b54` permanece como diretório de inspeção, fora da entrega.
- PR existente [#22](https://github.com/MaRuJoBs/Back_Marujob/pull/22): aberto, draft, `merged_at=null`; altera settings e dois testes de cookies. Essa mudança anterior foi preservada, não reimplementada.
- Classificação inicial: **PARCIAL**, conforme escopo efetivo do #22 e cobertura existente; nenhum relatório completo B54 estava versionado.
- Todos os PRs #1–#23 foram pesquisados e lidos individualmente. Estados, datas de merge e hashes estão em [FEAT-54-historico.md](FEAT-54-historico.md). Inclui fechados sem merge e trabalhos com títulos alternativos.

| Dependência | Evidência de integração na DEV |
|---|---|
| B34 | PR #10, merge `4549d85` |
| B39 | PR #8 `6a09cde`; correção Google #12 `b800fb3`; #13 fechado sem merge |
| B40 | PR #11 `56d0530` |
| B41 | PR #14 `473640e`; complementos #17 `d7e692c` |
| B44 | PR #16 `ff54267` |
| B45 | PR #19 `a54ee49` |
| B46 | PR #21 `0226c2e` |
| B47 | PR #20 `49fab85` |
| B54 | PR #22 aberto, não integrado |
| B43 | Nenhum PR identificado; homologação final pendente |

O [PR #23](https://github.com/MaRuJoBs/Back_Marujob/pull/23), FIX-B45-restauracao-migrations, está aberto e sem merge. Sua correção não foi incorporada. Ter uma branch ou um PR não comprova funcionamento: as evidências abaixo são de execução local desta base.

## B. Matriz de segurança e contratos reais

Os testes existentes criam empresas A/B, freelancers A/B e cliente anônimo em SQLite descartável. Foram reutilizados em vez de duplicados. `core.tests.settings` força banco em memória e hash rápido exclusivamente para testes; isso não representa o algoritmo de produção. Os cinco testes novos complementam lacunas específicas e usam apenas identidades fictícias.

| Área | Implementação, evidência e resultado |
|---|---|
| Autenticação | `/api/token/` usa TokenObtainPairView com `USERNAME_FIELD=email`; access 180 minutos, refresh 1 dia. `/api/token/refresh/` e `/api/token/verify/` existem. Testes em `test_authentication.py`, `test_google_auth.py` e `test_security_b54.py`: credencial inválida/expirada ou refresh no header é rejeitada; conta inativa não recebe access/refresh utilizável. Não há endpoint de revogação/logout nem recuperação por e-mail nas rotas inspecionadas. Definição de senha exige Google sem senha utilizável; troca exige senha atual e validadores Django. B54-01 registra ausência de revogação após troca. |
| Autorização | `core/permissions.py` exige grupo empresarial/profissional inequívoco. Grupos vazios ou ambíguos não ganham ações de negócio. Os testes de autenticação, B47, perfil/portfólio e B46 cobrem payload de proprietário e privilégios, mantendo identidade atribuída pelo servidor. |
| Oportunidades | `/api/freelances/`: leitura autenticada; escrita só empresa, e no objeto só proprietária. B pode ler a vaga de A conforme contrato, mas PATCH/PUT/DELETE recebem 403. `empresa` é somente leitura, inclusive em criação. Legadas sem empresa não podem ser assumidas. `test_freelances.py`, `test_freelance_contrato_b47.py` e complementos validam persistência e limites. |
| Portfólios | `/api/portfolios/`: queryset do próprio usuário e escrita exclusiva de freelancer. Outro freelancer recebe 404 no objeto; empresa recebe 403 na escrita; leitura própria não concede acesso a projetos alheios. `usuario` é somente leitura. `test_profiles_portfolios.py` cobre matriz, imagens e campos protegidos. |
| Candidaturas | `/api/candidaturas/`: POST exclusivo de freelancer, proprietário/status/datas fixados no backend; duplicação 400 com constraint no banco. Listagem e detalhe restringem freelancer ou empresa proprietária. Ações POST `aprovar`/`recusar` só da empresa dona. Outro dono recebe 404, freelancer 403; repetição da mesma decisão 200 e oposta 409. `test_candidaturas.py` e `test_notificacoes.py`. |
| Notificações | `/api/notificacoes/`: só empresas, filtro duplo por destinatária e dona atual da vaga. PATCH `marcar-lida` só altera booleano; outro dono recebe 404. Projeção não contém telefone/GPS/e-mail. Testes cobrem IDs, tentativa de alterar destinatária, perda de propriedade e rollback. 25 testes desse módulo passam em processo independente. |
| Perfil empresarial | `/api/empresas/me/` só GET/PATCH da própria empresa. GET não cria linha; PATCH cria perfil opcional. Empresa enviada no payload não transfere identidade; freelancer recebe 403. Não existe rota pública B46 nem rota por ID empresarial. `test_empresa_perfil.py`. |
| Diretório B45 | `/api/freelancers/` e detalhe exigem empresa autenticada; não são acesso anônimo público. Só perfis com consentimento `perfil_publico`, ativos, não administrativos e exclusivamente freelancers. Só projetos `publico` aparecem. Filtros são cumulativos e parâmetros repetidos/desconhecidos são rejeitados. Testes B45 cobrem ausência de dados privados, revogação, filtros, grupos e projeções explícitas. |
| Privacidade | `usuarios/` e `usuarios/{id}/` filtram pelo próprio usuário; `me` retorna dados privados apenas do titular. Candidaturas/notificações usam projeção profissional mínima. Diretório usa allowlists próprias. A API não revoga automaticamente arquivos já conhecidos no storage. Ver inventário abaixo. |
| Uploads | Cadastro comum, perfil, portfólio e logo B46 usam `ValidatedImageField`: tamanho padrão 5 MiB, conteúdo JPEG/PNG/WebP, proteção de dimensões Pillow; `SafeImageStorageMixin` trata erros com 503 e transação. Testes usam mídia temporária e Cloudinary simulado. Caminho de foto Google possui exceção comprovada, B54-02. |
| Settings | Fora de DEVELOPMENT rejeita DEBUG verdadeiro, chave curta/insegura e hosts vazios/curinga. CORS não permite todas as origens; origens CORS/CSRF vêm do ambiente. Cookies Secure em PRODUCTION já presentes na FEAT-54, ainda não na DEV. Proxy opt-in; HSTS/redirect não configurados no app. `check --deploy` sintético: 12 avisos; não equivale ao deploy real. |
| Integrações | Google usa `verify_oauth2_token` com audience explícita e tolerância de 5s, checa sub/email_verified, conta ativa e vínculo google_id; conta com senha não é vinculada automaticamente por e-mail. Testes Google offline validam assinatura RSA, audiência, expiração e indisponibilidade. Foto Google: B54-02. Cloudinary recebe credenciais sintéticas nos checks e é simulado nos testes. WhatsApp só constrói link codificado, sem enviar mensagens. |
| Migrations | Grafo atual termina em `0022_empresa_perfil`, unindo as duas folhas 0021. As duas uniões 0015 são vazias e convergem em 0016. `makemigrations --check --dry-run`: nenhuma alteração. Aplicação inicial em bancos novos dos testes funciona; testes históricos validam preservação. Falha de restauração do teste B45 afeta a suíte, não prova corrupção em produção. PostgreSQL não executado. |

### Códigos negativos observados

| Operação | Resultado real |
|---|---|
| GET das nove coleções/rotas protegidas sem JWT, JWT inválido/expirado ou refresh no header | 401; teste novo executa 36 subcenários |
| Login com senha incorreta / conta inativa | 401 |
| Refresh expirado ou access enviado como refresh | 401 |
| Conta empresarial candidata-se / freelancer decide candidatura | 403 |
| Empresa B edita/exclui vaga A; freelancer escreve vaga | 403 |
| Freelancer B lê/edita portfólio A | 404 |
| Empresa B acessa candidatura/notificação A, inclusive ação | 404 |
| ID inexistente, para papel autorizado a consultar recurso | 404 |
| Payload de proprietário ou campo somente leitura | Ignorado conforme serializer; não transfere propriedade; resposta pode ser 200/201 |
| PATCH genérico de candidatura / PUT de perfil empresarial | 405 |
| Candidatura duplicada | 400, mensagem sem SQL |
| Decisão oposta após decisão persistida | 409 |
| Falha simulada de storage nos uploads comuns | 503 genérico, sem persistência parcial |
| Falha simulada de storage no cadastro Google com foto | 500 genérico com DEBUG=False, conta permanece criada; B54-02 |

Não foram uniformizados 403/404. Os 404 de querysets privados evitam revelar existência; oportunidades são legíveis por contas autenticadas por contrato. Ausência de stack trace foi confirmada nos novos cenários de JWT e erro Google; não é prova de que todos os possíveis erros operacionais sejam sanitizados.

### Inventário dos dados e minimização

| Dados armazenados | Modelo/campo | Acesso pela API e avaliação |
|---|---|---|
| E-mail, senha hash, google_id, privilégios | User | E-mail e privilégios próprios em UserSerializer/me; hash e google_id não aparecem nessas respostas. JWT contém identificação técnica, não senha. `depth=1` expõe grupos/permissões do próprio titular; avaliar necessidade, sem evidência de vazamento entre contas. |
| Telefone | User.telefone | Titular em me. Empresa proprietária só recebe telefone indiretamente no link wa.me após aprovação e normalização; sem contato para candidaturas pendentes/recusadas ou terceiros. Exige finalidade e informação ao titular. |
| Localização livre, latitude/longitude, precisão e timestamp | User.localizacao/latitude/longitude/geolocation_accuracy/geolocation_timestamp | Me do titular; ausentes nas projeções do diretório, candidatos e notificações. Diretório usa cidade_publica separada. Validação de par e faixa de coordenadas, precisão finita e timestamp futuro em testes B40. Decidir necessidade/retenção do GPS; acesso restrito não justifica por si só a coleta. |
| Nome, profissão, habilidades, cidade pública, sobre e foto | User | Diretório exige publicação; candidato expõe apenas id/nome/profissão/habilidades/foto às partes autorizadas. Texto livre e imagem podem conter dados que o titular inseriu; validação estrutural não detecta toda informação pessoal. |
| Perfil institucional, site, contato comercial, cidade/UF | EmpresaPerfil e nome/logo em User | Só própria empresa em B46. Vagas expõem FK empresa, não perfil B46 aninhado. Não há publicação institucional pública implementada. |
| Projetos, tags, descrição, links e imagem | Portfolio | CRUD próprio; projeção do diretório só projetos publicados com perfil publicado. URLs de imagem podem sobreviver à revogação na API. |
| Relações, decisões e datas de candidatura/notificação | Candidatura e Notificacao | Freelancer próprio ou empresa dona da vaga; notificações apenas destinatária válida. Índice por empresa/leitura/data e unicidade evitam duplicações. |
| Artefatos de banco/mídia no Git | dump.json, db.sqlite3, media | B54-03: hash/e-mail presentes no dump; origem sintética não confirmada. O banco real não foi aberto nem utilizado. |

Avaliação LGPD pendente da equipe/jurídico: base legal e transparência para GPS, publicação e contato após aprovação; finalidade, retenção, exclusão e direitos do titular; backups e histórico Git; operadores Cloudinary/Google; remoção de imagens, cache e EXIF. Não foi realizado laudo jurídico. Cadastro público exige foto validada, mas não há prova de remoção de metadados EXIF nem rotina de eliminação de arquivos antigos.

## C. Achados classificados

Nenhuma falha crítica/alta de autorização entre contas foi demonstrada pelos cenários executados. Isso não elimina riscos fora do escopo nem reduz a urgência de confirmar a origem dos dados versionados.

### B54-01 — MÉDIA — Tokens sobrevivem à troca de senha (comprovado)

- Arquivos/endpoints: `app/settings.py` SIMPLE_JWT; `core/views/user.py` TrocarSenhaView; `/api/auth/trocar-senha/`, `/api/token/refresh/`.
- Condição: terceiro já possui access ou refresh válido antes da troca de senha.
- Impacto: troca não encerra o acesso anterior; access pode durar até 3h, refresh emitido até 1 dia. Um access renovado perto do fim do refresh pode continuar válido além desse prazo. Não há endpoint de revogação nem blacklist configurada.
- Evidência: `TokenBoundaryAuditTests.test_finding_01_password_change_keeps_preexisting_tokens_usable`: troca 200, access antigo GET me 200, refresh antigo 200, novo access GET me 200. Não demonstra roubo inicial de token.
- Correção mínima proposta: FIX-B39-revogacao-jwt, avaliar `CHECK_REVOKE_TOKEN` da versão instalada e política de revogação de access/refresh; cobrir também definição inicial de senha, logout e contas inativas. Rotação/blacklist exigem desenho e possivelmente migrations separados.
- Regressão: sessões em outros dispositivos poderão expirar; compatibilidade do frontend e fluxos Google precisam ser testados. Requer autorização antes de alterar settings/autenticação.

### B54-02 — MÉDIA — Foto Google contorna validação e tratamento de storage (comprovado)

- Arquivo/endpoint: `core/views/user.py`, dois blocos de `requests.get`/`profile_image.save` no GoogleLoginView, `/api/auth/google/`.
- Condição: credencial Google válida com picture; resposta do download inválida/grande ou falha de armazenamento. O teste simula claims após verificação e download, não falsifica assinatura Google.
- Impacto: bytes sem formato de imagem e acima do limite são persistidos; download inteiro em memória, redirects padrão e sem limite de tamanho nesse caminho; OSError do storage não é capturado, devolve 500 e deixa conta criada. Pode consumir recursos e produzir cadastro parcial. Não foi comprovada execução de código, takeover ou SSRF controlável pelo cliente.
- Evidência: `GooglePhotoAuditTests.test_finding_02_google_photo_bypasses_content_and_size_validation`: texto inofensivo maior que o limite sintético de 8 bytes é salvo e resposta 200. `test_finding_02_google_storage_error_returns_500_and_leaves_account`: erro de storage simulado, 500 genérico sem mensagem interna, conta permanece. Arquivos reais temporários; nenhuma chamada externa.
- Correção mínima proposta: FIX-B39-foto-google, reutilizar validação de conteúdo/tamanho, leitura com limite, política de URL/redirect e captura das exceções de storage; decidir se foto opcional deve falhar sem impedir login ou se cadastro deve ser transacional.
- Regressão: latência/login, fotos atuais, tratamento de falhas e identidade de contas. Requer autorização; não alterar vínculo Google ou fluxo de cadastro informalmente.

### B54-03 — MÉDIA — Dados e hashes versionados; autenticidade pendente

- Arquivos: `dump.json`, `db.sqlite3`, `media/`; `.gitignore` mantém db.sqlite3 versionável e não exclui mídia.
- Condição: acesso ao repositório/artefatos. A presença é comprovada; serem dados reais, senhas ainda válidas ou vazamento público NÃO foi confirmado.
- Impacto: distribuição desnecessária de dados e possibilidade de ataque offline a hashes caso pertençam a contas reais. Severidade deve subir para ALTA se confirmado material de contas reais/reutilizáveis. Visibilidade e permissões efetivas do repositório não foram auditadas.
- Evidência sanitizada: `git ls-files` identifica banco, dump e mídia; leitura estrutural do dump: 2 registros User, 2 e-mails preenchidos e 2 hashes `pbkdf2_sha256`, sem imprimir nenhum valor. Não se abriu o SQLite nem se carregou o dump em testes.
- Proposta: FIX-PRIV-dados-versionados, confirmar origem com responsáveis; substituir por fixtures sintéticas e excluir novos artefatos da distribuição. Se reais, avaliar resposta a incidente, troca de credenciais e tratamento de histórico/backups. Remover do HEAD não remove histórico.
- Regressão: fixtures e onboarding podem depender desses arquivos. Não remover arquivos ou reescrever histórico sem autorização específica.

### B54-04 — BAIXA — Endurecimento HTTPS depende do proxy (comprovado no app, operação pendente)

- Arquivo: `app/settings.py`; `check --deploy --production` sintético aponta W004/W008.
- Condição: publicação acessível em HTTP sem redirecionamento externo; configuração efetiva do proxy não verificada.
- Impacto: risco de transporte inseguro se a borda não garantir TLS. Não se conclui que produção atualmente transmite credenciais em HTTP.
- Proposta: equipe de infraestrutura/B54 documentar e testar TLS/redirect, sanitização de X-Forwarded-Proto, hosts e cookies; só depois avaliar HSTS e redirect no app. Risco de indisponibilidade/loops se habilitados sem validar proxy. Settings exigem autorização.
- Cookies Secure: mitigação já existente em `b832120`, validada nos testes, ainda pendente de integração do PR #22. Não foi editada novamente.

### B54-05 — INFORMATIVA — Controle de abuso não demonstrado na aplicação

- Arquivos/endpoints: REST_FRAMEWORK sem throttles explícitos; login, refresh, cadastro e Google não têm limites locais configurados no código inspecionado.
- Condição/impacto: sem proteção na borda, tentativas repetidas podem facilitar brute force/enumeração e custos de cadastro/upload. Teste de carga ou ataque não foi executado; não se afirma ausência de controle no proxy.
- Proposta: B39/infra confirmar rate limits e monitoração; se inexistentes, projetar limites com testes de 429 e prevenção de bloqueio indevido. Risco: NATs e usuários legítimos podem ser afetados. Autorização necessária para mudar comportamento.

### B54-F01 — Pendência funcional de validação, não vulnerabilidade comprovada

`FreelancerPublicoMigrationTests.test_existing_profiles_and_projects_remain_private` restaura apenas sua folha 0021, deixando fora campos B47 e a folha B46. Na suíte integral, dois testes de concorrência seguintes falham durante preparação por ausência de `core_freelance.modalidade`. Mesmo erro antes e depois dos cinco testes novos. O PR #23 propõe restauração de todas as folhas e ainda não está integrado. Não se propõe nova migration nem se atribui esse erro à produção. Responsável: FIX-B45 existente/B43. Risco da correção: isolamento dos testes históricos; revisão e merge exigem fluxo próprio.

## D. Correções e decisões propostas

Indispensáveis antes de aprovar homologação: resolver a origem dos artefatos B54-03; revisar/integrar a FIX #23 e reexecutar suíte integral; decidir e corrigir/aceitar formalmente B54-01 e B54-02; validar TLS/proxy/origens/storage no ambiente de homologação com dados sintéticos; verificar dependências vulneráveis em fonte atualizada; avaliar integração do PR #22. Nenhum aceite de risco foi presumido.

Recomendadas: confirmar limites de abuso e de corpo no proxy, retenção de imagens antigas, remoção de metadados, política de acesso a mídia, logging sanitizado e monitoramento. Futuras: estratégia de revogação/dispositivos e recuperação de conta, conforme requisitos de produto. Campos `__all__` em FreelanceSerializer exigem revisão quando novos campos forem adicionados; os campos atuais foram inspecionados e não há vazamento adicional comprovado por isso.

Todas as mudanças de produção acima dependem de autorização específica. Esta entrega adiciona testes, runner seguro e documentação, sem alterar contratos, regras de negócio, models, serializers, views, settings ou migrations.

## E. Arquivos da entrega atual

| Arquivo | Alteração e motivo | Impacto/risco |
|---|---|---|
| `core/tests/test_security_b54.py` | Cinco testes de lacunas e caracterização dos achados | Só testes; os testes `finding_*` documentam falhas existentes, não afirmam segurança. Devem mudar para comportamento seguro junto à correção autorizada. |
| `scripts/audit_b54.py` | Runner de checks/testes com ambiente sintético, banco em memória e bloqueio de sockets Python | Só invocação explícita; muda diretório para o projeto e evita descoberta na worktree errada. Não é sandbox para programas externos nem atestado do ambiente real. |
| `docs/FEAT-54-auditoria-seguranca.md` | Relatório, evidências, riscos e checklist | Documentação; sem credenciais/dados reais. |
| `docs/FEAT-54-historico.md` | 23 PRs e merged_at conferidos | Documentação verificável. |

Separadamente, a branch já contém o commit `b832120` em `app/settings.py` e `core/tests/test_authentication.py`; seu diff anterior não deve ser confundido com alterações desta execução.

## F. Comandos e resultados reais

Ambiente instalado: PDM 2.26.6, Python 3.13, Django 5.2.12, DRF 3.16.1, SimpleJWT 5.5.1, google-auth 2.57.1, Pillow 12.1.1, python-dotenv 1.2.2. Nenhuma ferramenta/dependência instalada. Pip-audit, Bandit e Safety não estão disponíveis; não foi executada consulta de CVEs. Versões instaladas não significam ausência de vulnerabilidades.

O PDM está instalado fora da raiz permitida e exigiu aprovação de execução do launcher. O runner fixa DATABASE_URL em memória, desabilita .env, usa Cloudinary/Google fictícios e bloqueia conexões socket Python. Não executa o script PDM `migrate`, `build.sh` ou release do Procfile, que aplicariam migrations. Migrations são aplicadas apenas pelo runner de testes em bancos descartáveis.

Na raiz, com as dependências existentes:

```powershell
pdm run python scripts/audit_b54.py test --noinput
pdm run python scripts/audit_b54.py test core.tests.test_security_b54 --noinput
pdm run python scripts/audit_b54.py test core.tests.test_notificacoes --noinput
pdm run python scripts/audit_b54.py check
pdm run python scripts/audit_b54.py makemigrations --check --dry-run
pdm run python scripts/audit_b54.py showmigrations --plan
pdm run python scripts/audit_b54.py --production check --deploy
pdm run ruff check scripts/audit_b54.py core/tests/test_security_b54.py
pdm run ruff format --check scripts/audit_b54.py core/tests/test_security_b54.py
```

| Verificação | Resultado |
|---|---|
| Baseline FEAT-54 antes das adições | 248 testes, 246 sem erro e 2 erros preexistentes, exit 1 |
| Suíte com os cinco novos | 253 testes, 251 sem erro e os mesmos 2 erros, exit 1; suíte NÃO aprovada |
| Novos testes isolados | 5/5 aprovados |
| Notificações em processo/banco novo | 25/25 aprovados, inclusive concorrência que falha após teste B45 na suíte integral |
| Django check com settings de testes | exit 0, nenhuma questão |
| makemigrations check/dry-run | exit 0, No changes detected |
| showmigrations plan | exit 0, grafo resolvido até core.0022; itens desmarcados são esperados em banco novo |
| check deploy com app.settings PRODUCTION sintético | exit 0 com 12 avisos: W004 e W008 de segurança, 7 W001 e 3 W002 de schema |
| Ruff check / format check finais dos dois arquivos Python novos | exit 0 em ambos; dois arquivos formatados |
| git diff --check | exit 0; arquivos novos também inspecionados com diff --no-index --check |

Aviso preexistente de staticfiles ausente aparece em testes. Diagnósticos de schema incluem três views de autenticação sem serializer de schema, tipos não anotados e componentes Nested com mesmo nome. São limitações de documentação, não evidência de bypass de autenticação.

Duas tentativas iniciais de descoberta a partir da raiz com manage.py da subpasta falharam antes de executar testes por conflito de importação entre worktrees. Execução com cwd/import path ajustados funcionou; o runner versionado fixa esse diretório. Não se contaram essas tentativas como testes aprovados. Ruff format inicialmente detectou formatação do arquivo novo; foi aplicada somente nos arquivos novos.

Não executados: PostgreSQL e concorrência real nesse banco; Cloudinary/Google/WhatsApp reais; endpoints publicados; deploy, migrations reais e configurações efetivas do proxy; scan de CVEs/segredos em todo histórico binário; teste de carga; validação jurídica. Motivos: evitar dados/serviços reais, ausência de ambiente autorizado de homologação e ferramentas de scan instaladas. Não há demonstração de que os domínios/origens sintéticos correspondam ao frontend publicado.

## G. Diff e revisão

Revisão sem staging/commit:

```powershell
git diff --check
git diff --stat
git status --short
git diff origin/DEV...FEAT-54 -- app/settings.py core/tests/test_authentication.py
git diff --no-index -- /dev/null core/tests/test_security_b54.py
```

Em Windows, usar `git diff --no-index -- NUL <arquivo-novo>` para visualizar cada arquivo novo; exit 1 significa diferença encontrada. O diff comum não inclui arquivos ainda não rastreados. Os quatro arquivos listados na seção E são a referência completa das adições desta execução; o diff entre DEV e FEAT-54 mostra as 28 linhas do commit anterior. `core.png`, banco, mídia preexistente e `.audit-b54/` devem ficar fora de qualquer staging posterior.

Revisão final: `git diff --stat` mostra somente os dois binários preexistentes (core.png e db.sqlite3); os quatro arquivos B54 continuam não rastreados. `git status --short` confirma também a imagem preexistente e o diretório da worktree detached. O Git avisa sobre conversão futura LF/CRLF nos arquivos novos; não foram alteradas configurações Git de fim de linha. Um branco extra no fim do histórico foi removido após a inspeção.

Risco de regressão em produção desta adição: baixo, pois o código de runtime permanece intacto. Risco de interpretação: testes de caracterização passam mesmo com falhas de segurança existentes; a matriz e o veredito registram isso explicitamente. Um futuro merge deve incluir somente os arquivos aprovados.

## H. Riscos residuais

Segurança: B54-01/02 permanecem sem correção; B54-03 requer confirmação; TLS/headers/abuso/credenciais de integração e dependências precisam de homologação. Arquivos no storage não são protegidos apenas por queryset: retirar consentimento oculta a API, mas não garante invalidação de URL já compartilhada. Logs publicados, backups, EXIF, acesso administrativo e permissões reais do repositório não foram homologados.

Funcionalidade/validação: suíte integral vermelha pela restauração de migrations B45; PostgreSQL e produção não exercitados; schema com diagnósticos e estáticos ausentes no ambiente de teste. Não confundir esses itens com acesso indevido comprovado a dados de terceiros.

## I. Checklist de encaminhamento B43

- [ ] Revisar/integrar FIX #23 e executar suíte inteira em um único processo, sem erros e sem ignorar testes.
- [ ] Após FIX B39, reexecutar senha/access/refresh antigos, definição inicial, Google e conta inativa; converter testes de caracterização para negar os comportamentos inseguros.
- [ ] Após correção da foto Google, testar conteúdo real, limite em bytes/dimensões, redirects permitidos, timeout, storage indisponível e atomicidade/continuidade do login, sem rede real em testes unitários.
- [ ] Executar empresas A/B, freelancers A/B e anônimo em todos os contratos da matriz, incluindo payload de proprietário, campos read-only, IDs inexistentes/sequenciais, duplicação e decisão concorrente.
- [ ] Revalidar B45 após publicação/revogação: lista, detalhe, filtros, projetos privados, GPS/e-mail/telefone ausentes e política de mídia já compartilhada.
- [ ] Revalidar B46: GET sem escrita, PATCH próprio, logo, freelancer negado e nenhuma exposição institucional pública informal.
- [ ] Confirmar origem sintética do banco/dump/mídia ou executar plano autorizado de remediação; verificar histórico/backups sem imprimir dados.
- [ ] Aplicar plano em PostgreSQL de homologação descartável, verificar unicidade, FKs, índices e concorrência de candidaturas/decisões; preservar registros sintéticos legados.
- [ ] Confirmar DEBUG=False, chave forte, hosts e origens reais, CORS sem wildcard/credenciais indevidas, cookies Secure e TLS na borda; testar sanitização de headers antes de confiar no proxy.
- [ ] Decidir HSTS/redirect e controle de abuso com infraestrutura; reexecutar check --deploy no ambiente representativo e resolver ou justificar cada aviso.
- [ ] Validar storage/Google com contas sintéticas em homologação somente após autorização; verificar URLs, remoção, retenção, EXIF e falhas seguras. Nenhuma mensagem real deve ser enviada.
- [ ] Executar scanner atualizado de dependências/segredos em ambiente autorizado, revisar logs sanitizados e decisões de privacidade/LGPD com responsáveis.

## J. Veredito e aprovação

**INCOMPLETA — VALIDAÇÕES PENDENTES.** A auditoria local produziu evidências e cenários reproduzíveis, mas não permite homologação final: faltam decisões/remediações dos achados, confirmação dos artefatos, suíte integral aprovada e validação operacional. Nenhuma vulnerabilidade crítica/alta foi comprovada nos testes de autorização executados; não se declara o sistema seguro por terem passado testes isolados.

Nenhum git add/commit/push/merge, novo PR ou deploy foi executado nesta auditoria. O PR #22 já existia. Commit depende de autorização; push e atualização/abertura de PR precisam de autorizações posteriores separadas. Não há necessidade de criar PR duplicado para a mesma branch.
