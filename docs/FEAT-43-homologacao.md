# FEAT-43 — Integração, testes finais e prontidão do backend

Data da execução: 2026-11-11. Base efetivamente testada: `2ebacc933af424a378a2a1ec679e17735625ac04` mais os três testes locais B43. Não houve alteração de código de produção.

**PR B43: PRONTO COM RESSALVAS para revisão dos testes e deste relatório; nenhum PR criado.**

**Backend para homologação/produção: NÃO APTO à liberação final nesta execução.** O funcionamento automatizado local passou; homologação operacional não foi executada e permanecem decisões de privacidade/segurança sem aceite formal identificado. Não se declara conformidade integral LGPD nem segurança absoluta.

## A. Estado Git, autorização e anti-duplicação

Raiz confirmada: `C:/Users/Ricardo/Documents/Back_Marujob`. Remote: `https://github.com/MaRuJoBs/Back_Marujob.git`. Branch inicial FEAT-54 em 7a88534. Foram executados rev-parse, status --short, branch atual, remote -v, worktree list, branch -a, log -8 e fetch origin --prune.

FEAT-43 não existia localmente nem remotamente. Após autorização expressa, foi criada com `git switch -c FEAT-43 origin/DEV`, em `2ebacc9`. Nenhuma outra worktree utiliza FEAT-43. As worktrees auxiliares preexistentes estão detached em a54ee49, e8cb0da e b832120 e não foram utilizadas nesta B43. A DEV local não foi alterada; o ponto de partida foi origin/DEV atualizada.

Preexistentes, integralmente preservados e fora da entrega: core.png e db.sqlite3 modificados, imagem não rastreada em media/portfolios e diretórios `.audit-b54/` e `.audit-b45-review/`. Na troca de branch, hashes dos três arquivos foram comparados internamente antes/depois, confirmando preservação byte a byte, sem imprimir valores. HEAD e origin/DEV tinham árvores idênticas antes da criação, pois o único commit novo era o merge da B54.

Foram pesquisados todos os PRs abertos/fechados com state=all e lidos individualmente os 23 resultados (#1–#23), verificando merged_at, destino e commit de merge. Não apareceu PR dedicado à B43, nem implementação equivalente sob título alternativo. Os requisitos já cobertos foram reutilizados; não se recriaram os testes B39/B40/B41/B44/B45/B46/B47/B54. Os commits de merge das dependências da tabela foram conferidos como ancestrais da base.

| Dependência | PR(s) | Commit de merge na DEV | merged_at UTC |
|---|---|---|---|
| B34 | #10 | 4549d85 | 2026-10-30T18:20:15Z |
| B38 | #9 | f2933bc | 2026-10-30T17:38:04Z |
| B39 | #8 | 6a09cde | 2026-10-30T17:41:41Z |
| Correção Google | #12 | b800fb3 | 2026-10-30T19:25:25Z |
| B40 | #11 | 56d0530 | 2026-10-30T18:13:26Z |
| B41 | #14 | 473640e | 2026-10-30T18:47:46Z |
| Complementos B41/B36 | #17 | d7e692c | 2026-10-30T20:57:50Z |
| B44 | #16 | ff54267 | 2026-10-30T20:28:47Z |
| B37 | #15 / #18 | 9d04124 / db8f5b2 | 2026-10-30T18:48:19Z / 2026-11-03T17:13:41Z |
| B45 | #19 | a54ee49 | 2026-11-09T17:49:51Z |
| B47 | #20 | 49fab85 | 2026-11-09T17:48:17Z |
| B46 | #21 | 0226c2e | 2026-11-09T18:30:55Z |
| FIX-B45 | #23 | 34a58b5 | 2026-11-11T18:48:52Z |
| B54 | #22 | 2ebacc9 | 2026-11-11T18:59:22Z |

Os PRs #2, #3, #4, #7 e #13 estão fechados sem merged_at; não foram tratados como integrados. #6 foi integrado em main, o que isoladamente não prova presença na DEV. O [histórico B54](FEAT-54-historico.md) preserva a consulta anterior, quando #22/#23 ainda estavam abertos; as confirmações acima prevalecem nesta execução.

## B. Matriz das funcionalidades e cobertura reaproveitada

As classificações desta tabela se referem aos testes locais SQLite, não ao ambiente publicado. Toda linha operacional real tem classificação separada no checklist.

| Módulo/requisito | Classificação | Evidência executada e limites |
|---|---|---|
| Cadastro, JWT, refresh, verify, contas inativas | JÁ IMPLEMENTADA E VALIDADA | test_authentication, test_security_b54; novo fluxo usa cadastro e login HTTP, sem force_authenticate. Senha errada, token ausente/inválido/expirado, refresh no header e conta inativa cobertos pela suíte existente. |
| Troca e primeira definição de senha | JÁ IMPLEMENTADA E VALIDADA | B54 exige rejeição de access/refresh antigos e sucesso de novo login; Google elegível mantém fluxo. Tokens sem claim precisam reautenticar. |
| Google | JÁ IMPLEMENTADA E VALIDADA | test_google_auth e autenticação: RSA/verificador real offline, assinatura/audience/expiração, email_verified, vínculo, conta inativa e indisponibilidade; sem Google real. |
| Oportunidades CRUD/contrato B47 | JÁ IMPLEMENTADA E VALIDADA | test_freelances, test_freelance_contrato_b47, complementos e queries; jornada B43 percorre criação, busca combinada, atualização/status, exclusão e efeito nas relações. |
| Filtros de oportunidades implementados | JÁ IMPLEMENTADA E VALIDADA | search, tag, preco_min/preco_max, tipo_contratacao, nivel_experiencia e page; filtros reais executam consultas e verificam IDs/paginação em test_opportunity_queries. |
| Filtros tempo_min/tempo_max, categoria, modalidade/status como query | NÃO IMPLEMENTADA | Não constam no contrato do filtro atual; tempo é texto. Modalidade/cidade/UF/status são campos graváveis/legíveis B47, não filtros adicionados por B43. Não é regressão nem convite a implementar. |
| Perfil do usuário | JÁ IMPLEMENTADA E VALIDADA | test_profiles_portfolios e autenticação: titular, limites, listas, GPS, read-only, privilégios e isolamento; jornada publica/revoga perfil com JWT. |
| Portfólios e publicação | JÁ IMPLEMENTADA E VALIDADA | CRUD/ownership/uploads nos testes existentes; B43 cria projeto publicado e privado, checa projeção e persistência própria após revogação. |
| Diretório autorizado | JÁ IMPLEMENTADA E VALIDADA | test_freelancer_publico: consentimento, elegibilidade, privacidade, filtros e revogação. Exige empresa/JWT; não é diretório anônimo. |
| Perfil empresarial | JÁ IMPLEMENTADA E VALIDADA | test_empresa_perfil e jornada B43: GET não cria linha, PATCH próprio persiste, identidade não é transferida; logo/validação em testes existentes. |
| Favoritos | JÁ IMPLEMENTADA E VALIDADA | test_favoritos e jornada B43: banco, idempotência, listas privadas, remoção e cascata. Sem armazenamento de frontend. |
| Candidaturas/decisões | JÁ IMPLEMENTADA E VALIDADA | test_candidaturas/test_notificacoes: criação, estados/datas, duplicidade, decisão, conflito e concorrência; fluxo B43 atravessa recursos com contas criadas na API. |
| Notificações | JÁ IMPLEMENTADA E VALIDADA | Associação transacional, leitura/filtros/paginação/duplicação, permissões e concorrência; B43 verifica notificação desde a criação da candidatura até aprovação. |
| WhatsApp link | JÁ IMPLEMENTADA E VALIDADA | Testes de normalização/contato existentes e jornada B43 validam wa.me, número e parâmetros percent-encoded; mensagem_enviada=false. Não existe envio automático nem endpoint WhatsApp separado. |
| Uploads comuns e foto Google | JÁ IMPLEMENTADA E VALIDADA | B40/B46/B54: JPEG/PNG/WebP, tamanho/conteúdo/dimensões, substituição, storage/timeout e rollback conforme cada caminho. Apenas mídia temporária/mocks. |
| Imagem de oportunidade | NÃO IMPLEMENTADA | Freelance não tem ImageField nem serializer de upload de imagem; o requisito condicional não foi marcado como teste aprovado. |
| Rotas de documentação/schema | IMPLEMENTADA, MAS COM COBERTURA PARCIAL | B43 confirma HTTP 200/HTML e recursos presentes no schema; persistem erros de geração/anotação conhecidos. HTTP 200 não comprova schema completo. |
| Migrations, constraints e restauração B45 | JÁ IMPLEMENTADA E VALIDADA | check/dry-run/plano e suíte integral em banco novo, incluindo testes históricos e concorrência posteriores; SQLite não equivale a PostgreSQL. |
| Destinos de foto, mídia privada/retirada de URLs | IMPLEMENTADA, MAS COM COBERTURA PARCIAL | HTTPS e ausência de redirects testados; sem allowlist/egress validado e sem revogação física garantida de URLs. Pendências B54 mantidas. |
| PostgreSQL/TLS/CORS/CSRF/storage publicados | NÃO VERIFICADA NO AMBIENTE REAL | Nível C NÃO EXECUTADO; ambiente e autorização próprios necessários. |
| Tratamento de dados versionados | BLOQUEADA POR DEPENDÊNCIA | Origem, responsável e decisão formal da equipe não confirmados. Não se presume aceite pelo merge B54. |

## C. Contratos reais de API

Fontes: app/urls.py, views/serializers/permissions reais e testes executados. HEAD/OPTIONS são auxiliares do DRF conforme autenticação; a tabela destaca métodos de negócio.

| Caminho | Métodos e permissão | Respostas/efeitos relevantes |
|---|---|---|
| /api/registro/ | POST sem exigir sessão | 201; tipo usuario/empresa; senha write-only e validada; payload não concede privilégios |
| /api/token/ | POST email/password | 200 access+refresh; 401 credencial/conta inválida |
| /api/token/refresh/ | POST refresh válido | 200 access; 401 expirado, senha anterior, conta inativa/excluída ou legado sem claim |
| /api/token/verify/ | POST token | Verifica criptografia/expiração; não substitui autorização ao recurso nem prova de sessão ainda válida após troca de senha |
| /api/auth/google/ | POST credential; opcional cadastro/tipo | 200 tokens para conta verificada; 400 inválido/vínculo; 401 inativa; 404 não cadastrada; 503 provedor/configuração indisponível |
| /api/auth/definir-senha/ | POST JWT, Google sem senha utilizável | 200 elegível; 400 inelegível/senha inválida; invalida tokens anteriores |
| /api/auth/trocar-senha/ | POST JWT + senha atual/nova | 200; 400 senha atual/nova inválida; invalida tokens anteriores |
| /api/usuarios/ e /{id}/ | GET JWT, queryset do titular | Outra conta oculta com 404; não oferece CRUD arbitrário de usuário |
| /api/usuarios/me/ | GET/PATCH JWT | 200; email/id/privilégios/grupos não transferíveis pelo payload; PUT 405 |
| /api/freelances/ e /{id}/ | GET JWT; POST empresa; PUT/PATCH/DELETE empresa dona | 201/200/204; outro dono ou freelancer na escrita 403; inexistente 404; dados inválidos 400 |
| /api/freelancers/ e /{id}/ | GET empresa autenticada | Só freelancers ativos/não administrativos/elegíveis/com consentimento; perfil privado 404; freelancer 403; filtros estritos inválidos 400 |
| /api/portfolios/ e /{id}/ | GET próprios; POST/PUT/PATCH/DELETE freelancer dono | Projeto alheio 404 pelo queryset; empresa escreve 403; uploads inválidos 400/storage 503 |
| /api/favoritos/ | GET/POST JWT | 201 novo ou 200 existente; listas privadas; /{id}/ apenas DELETE (204); alheio/inexistente 404 |
| /api/candidaturas/ e /{id}/ | GET freelancer próprio ou empresa dona da vaga; POST só freelancer | 201 pendente/datas automáticas, duplicidade 400, empresa candidata-se 403, acesso cruzado 404 |
| /api/candidaturas/{id}/aprovar/ e /recusar/ | POST empresa dona | 200 mesma decisão idempotente; oposta posterior 409; freelancer 403; outra empresa 404; contenção de banco simulada 503 |
| /api/notificacoes/ e /{id}/ | GET empresa destinatária e dona atual da vaga | Outros dados ocultos com 404; freelancer 403; filtros lida/status e paginação |
| /api/notificacoes/{id}/marcar-lida/ | PATCH mesma empresa | Idempotente; somente lida passa a true, independentemente do payload; não transfere destinatária |
| /api/empresas/me/ | GET/PATCH própria empresa | GET de perfil inexistente não grava; PATCH cria linha opcional; freelancer/ambígua 403; PUT 405 |
| /api/schema/, /api/doc/, /api/redoc/ | GET da documentação | B43 observou 200 sem JWT; schema com diagnósticos; sem validação de navegador/servidor publicado |

Todas as rotas privadas rejeitam ausência/invalidade do JWT com 401 conforme testes. Métodos genéricos não oferecidos em candidaturas/notificações recebem 405, preservando ações específicas. Códigos não foram uniformizados.

Filtros /freelances/: search procura título; tag igualdade sem distinção de caixa conforme o banco; limites de preco não filtram salario_minimo/maximo; escolhas tipo_contratacao/nivel_experiencia e paginação. Categoria não é catálogo: usa-se tag. Query params não suportados nesse endpoint mantêm o comportamento existente (podem ser ignorados), diferentemente do diretório B45, que rejeita desconhecidos/repetidos. Não enviar filtros ausentes esperando implementação implícita.

## D. Execução e evidências por nível

Ambiente instalado verificado: Python 3.13.2, Django 5.2.12, DRF 3.16.1, SimpleJWT 5.5.1, google-auth 2.57.1, Pillow 12.1.1, python-dotenv 1.2.2. PDM existente, sem instalação de pacotes. Pip-audit/Bandit/Safety não estão instalados; não houve scan atualizado de CVEs.

core/tests/settings.py e scripts/audit_b54.py foram relidos antes do uso. O runner força settings sintéticos, .env desabilitado, SQLite :memory:, Cloudinary/Google fictícios e bloqueia connect/connect_ex. Os testes de upload usam storage temporário/mocks existentes. O hash MD5 é exclusivo dos settings de testes, não configuração de senha de produção. Não se executaram scripts PDM migrate/build/release. O runner não é sandbox de filesystem/subprocessos nem deve receber argumentos de importação não revisados; foram utilizadas apenas as invocações abaixo.

### Nível A — Suíte automatizada existente

Baseline na FEAT-43, antes de qualquer novo teste: **270 descobertos/executados, 270 aprovados, zero falhas, zero erros, zero skips, exit 0**, em 9.442s. São testes unitários e de integração existentes, não 270 testes E2E publicados.

### Nível B — Fluxo completo da API em processo isolado

O arquivo novo `core/tests/test_integration_b43.py` cobre uma lacuna de composição: os testes anteriores exercitavam os módulos e algumas sequências, mas não todo o percurso abaixo com contas criadas pelo endpoint de cadastro e JWT obtido pelo login, até revogação e exclusão. Não duplica todos os edge cases já cobertos.

1. `test_registered_accounts_complete_publication_application_and_decision_journey`: cadastra empresas A/B e freelancers A/B via HTTP; autentica por /token; GET/PATCH B46; perfil e dois portfólios (público/privado); diretório e filtro; criação/busca combinada de vaga; favoritos idempotentes/isolados; candidatura com tentativa de alterar candidato/status; notificação correta; duplicação 400 sem novas linhas; contato indisponível antes da decisão; marcação de leitura sem transferência; aprovação/timestamp; link wa.me normalizado/codificado sem envio; aprovação repetida; recusa posterior 409; estado consultável pelo freelancer/notificação; revogação do perfil; portfólio próprio ainda acessível; remoção de favorito, encerramento/exclusão de vaga e cascata confirmada no banco.
2. `test_http_role_matrix_denied_operations_leave_business_database_unchanged`: sete identidades, seis operações, 42 subcenários; JWT real inclusive token de conta desativada depois da emissão. As operações negadas comparam snapshots dos seis modelos de negócio antes/depois, sem incluir senha/e-mail/tokens em diagnósticos. Fixtures extras de conta inativa/grupo ambíguo são criadas no banco descartável.
3. `test_documentation_routes_return_responses_and_schema_has_real_resources`: GET doc/redoc/schema com respostas reais do roteador em processo, verifica HTML/paths e mantém diagnósticos visíveis. Não valida completude do schema nem carrega assets externos no navegador.

Estes testes usam APIClient do DRF; não abrem servidor TCP nem validam TLS, proxy ou serviços reais. Serviços externos não são necessários ao percurso; mocks de Google/Cloudinary permanecem nos testes existentes de nível A.

### Matriz B43 executada (42 combinações)

| Operação em recursos de A | Empresa A | Empresa B | Freelancer A | Freelancer B | Anônimo | Inativa | Ambígua |
|---|---|---|---|---|---|---|---|
| PATCH vaga A | 200 | 403 | 403 | 403 | 401 | 401 | 403 |
| PATCH portfólio A | 403 | 403 | 200 | 404 | 401 | 401 | 403 |
| GET candidatura A | 200 | 404 | 200 | 404 | 401 | 401 | 403 |
| POST aprovar candidatura A | 200 | 404 | 403 | 403 | 401 | 401 | 403 |
| PATCH marcar notificação A lida | 200 | 404 | 403 | 403 | 401 | 401 | 403 |
| GET diretório/perfil publicado A | 200 | 200 | 403 | 403 | 401 | 401 | 403 |

A matriz não força 403 onde o queryset produz 404; empresas B podem consultar perfil profissional publicado, mas não seu CRUD privado. Os demais papéis/recursos e códigos 400/405/409/503 são cobertos pela suíte existente e pelo fluxo. Snapshot sem alterações não transforma operação de leitura em requisito de escrita.

### Nível C — Homologação operacional publicada

**NÃO EXECUTADO.** Nenhum servidor publicado, PostgreSQL, proxy TLS, origem CORS/CSRF ou storage real foi acessado. Não se utilizou credencial real, conta real, WhatsApp ou upload Cloudinary. A inexistência de autorização/ambiente isolado impede equiparar A/B a C.

### Comandos e resultados reais

```powershell
pdm run python scripts/audit_b54.py test --noinput
pdm run python scripts/audit_b54.py test core.tests.test_integration_b43 --noinput
pdm run python scripts/audit_b54.py check
pdm run python scripts/audit_b54.py makemigrations --check --dry-run
pdm run python scripts/audit_b54.py showmigrations --plan
pdm run python scripts/audit_b54.py --production check --deploy
pdm run python scripts/audit_b54_artifacts.py
pdm run ruff check core/tests/test_integration_b43.py scripts/audit_b54.py
pdm run ruff format --check core/tests/test_integration_b43.py scripts/audit_b54.py
pdm run ruff check core/tests scripts/audit_b54.py scripts/audit_b54_artifacts.py
pdm run ruff check core/tests scripts/audit_b54.py scripts/audit_b54_artifacts.py --statistics
pdm run ruff format --check core/tests scripts/audit_b54.py scripts/audit_b54_artifacts.py
git diff --check
git diff --stat
git status --short
```

| Verificação | Resultado |
|---|---|
| Baseline original na base B43 | 270/270; zero falhas/erros/skips; exit 0 |
| Três testes B43 isolados | 3/3; zero falhas/erros/skips; exit 0; 1.031s |
| Suíte integral final após adições | **273 descobertos, 273 executados/aprovados; zero falhas, zero erros, zero skips, exit 0; 14.322s**, um único processo |
| Django check | exit 0, nenhuma questão |
| Migration dry-run | exit 0, No changes detected |
| showmigrations --plan | exit 0, grafo até core.0022_empresa_perfil; itens desmarcados são esperados no banco vazio |
| Deploy check sintético | exit 0 com 12 avisos, não aprovação de produção |
| Inventário sanitizado B54 na base B43 | exit 0, resultados agregados na seção F |
| Ruff no arquivo novo e runner | exit 0 em check e format --check |
| Ruff ampliado aos testes existentes/scripts | **check exit 1: 93 PT009 e 1 PT027; format check exit 1: dois arquivos existentes**, 14 já formatados |

A primeira verificação do arquivo novo indicou complexidade natural do fluxo e literal de status: foi usado status.HTTP_400_BAD_REQUEST e exceção local PLR0914/PLR0915 para manter o percurso completo em um teste. Nenhuma regra global do Ruff foi alterada. Nenhum teste falhou durante a construção B43. As execuções não foram somadas como se fossem testes únicos; a contagem final única é 273.

## E. Erros, bugs e comportamentos esperados

| Item | Classificação | Evidência/encaminhamento |
|---|---|---|
| Restauração B45 causava dois erros seguintes | Bug histórico corrigido, NÃO REPRODUZIDO na base B43 | #23 restaurando todas as folhas; teste histórico e concorrências posteriores passam na mesma suíte integral |
| Schema com métodos sem serializer/anotação | Limitação comprovada, preexistente; PARCIAL | check --deploy e GET schema registram três W002 e sete W001. Propor FIX-DOCS-schema-autenticacao, com anotações/serializers de documentação e teste do schema; sem autorização para mudar views nesta B43 |
| Lint dos testes favoritos/vagas | Dívida de qualidade comprovada, preexistente | Arquivos test_favoritos.py/test_freelances.py idênticos ao HEAD; 94 diagnósticos PT009/PT027 e formatação pendente. Propor tarefa de qualidade separada, sem reescrever asserts para ocultar falhas |
| 403 versus 404 nos recursos alheios | Comportamento esperado | Matriz e querysets privados; não uniformizar códigos |
| Proprietário enviado no payload ignorado | Comportamento esperado | Identidade deriva do JWT; B43 confirma vaga/candidato/projeto e notificação no banco |
| Vaga encerrada continua legível/candidatura segue contrato anterior | Comportamento esperado aprovado B47 | Não inventar indisponibilidade; test_status_keeps_applications_favorites_and_notifications_contract e test_existing_opportunities_have_no_invented_availability_rules |
| Foto aceita destino HTTPS de claims sem allowlist | Risco residual já documentado, não novo SSRF comprovado | Teste B54 usa claims/download simulados; não prova que atacante obtenha token Google válido com destino arbitrário |
| Suposto envio automático de WhatsApp | NÃO REPRODUZIDO; não faz parte da implementação | Apenas construção da URL e mensagem_enviada=false; nenhuma chamada ao WhatsApp |
| Filtros de tempo e imagem de oportunidade | Não implementados no contrato atual, não bug da B43 | Ausentes de model/view/serializer; não classificados como funcionalidades testadas |
| Falhas operacionais reais | TESTE NÃO EXECUTADO | Sem ambiente/credenciais/autorização; não foi criado bug fictício nem aprovação presumida |

Nenhuma regressão funcional nova foi demonstrada pelos testes executados. Isso não demonstra ausência de bugs em caminhos não exercitados ou em PostgreSQL/produção. Correções em módulos de produção precisam de diagnóstico e aprovação de FIX própria.

## F. Segurança, privacidade e decisões pendentes

Reutilizados controles B54: senha forte e hashing de produção separados dos testes; validação Google offline com assinatura; negação de conta inativa, tokens inválidos/expirados e revogação por estado da senha; dono imposto pelo servidor; papéis inequívocos; allowlists de projeção do diretório/candidatos; controle de uploads e erros genéricos. A matriz B43 acrescenta a prova de ausência de mutação em tentativas negadas no fluxo integrado.

Inventário sanitizado reexecutado na base 2ebacc9 pelo script existente, com blobs Git em memória e sem abrir o SQLite da worktree: **11 contas/e-mails/hashes pbkdf2_sha256 no banco versionado; duas no dump; 17 mídias, quatro com EXIF, nenhuma tag GPS detectada**. Valores não foram impressos nem usados como dados de teste. Zero indicadores heurísticos de JWT-like/chave privada/token GitHub-like não equivale a scan completo de segredos. .env está ignorado; banco/dump e novos arquivos de mídia não têm política suficiente de exclusão do versionamento. Ignore não elimina arquivos já rastreados ou histórico.

Foram consultados documentos B54, descrição do PR #22 e seus comentários/revisões: comentários e revisões retornaram vazios, e o relatório ainda mantém origem **não verificada**. Não foi localizada decisão formal de tratamento ou responsável designado nessas fontes. Foi solicitada confirmação à equipe/usuário; não se inferiu aceite por silêncio ou pelo merge do PR. Situação: **B54-03 PENDENTE; responsável pela decisão A DESIGNAR PELA EQUIPE**. A existência de decisão fora dessas fontes não é descartada.

Plano: responsáveis confirmarem origem/finalidade e quem teve acesso a Git/CI/backups; se reais ou segredos utilizáveis, avaliar resposta e rotação/revogação específica; aprovar fixtures sintéticas e política de versionamento; inventariar histórico/clones; só então avaliar remoção controlada com autorização própria. Nada foi excluído, rotacionado ou reescrito.

Persistem riscos B54: URL Google sem allowlist/egress, portas/destinos não restritos apenas por HTTPS, objetos órfãos entre banco e storage, timeout por leitura sem prazo total, retenção/EXIF e URLs de imagens previamente conhecidas. Retirar publicação da API não garante invalidar URL no storage. Essas políticas não foram implementadas na B43 e não foram formalmente aceitas. Não se faz declaração jurídica LGPD.

## G. Migrations e infraestrutura

O grafo core converge em 0022_empresa_perfil, dependente das duas folhas 0021; uniões 0015 vazias convergem em 0016. Migrations normais são aplicadas somente pelo test runner em banco descartável. Os testes históricos e constraints verificam preservação de dados sintéticos, unicidade de candidatura, relação one-to-one notificação, FKs/CASCADE/SET_NULL e restauração posterior de todas as folhas. Não há migration nova ou inesperada.

Concorrências passaram em SQLite, que não reproduz todos os locks/isolation levels PostgreSQL. Plano necessário para PostgreSQL de homologação: provisionamento e credencial restrita próprios, schema/banco descartável, contas fictícias, aplicação normal das migrations nesse ambiente autorizado, barreiras de concorrência/decisões/rollback e limpeza aprovada apenas dos recursos criados. Nenhuma conexão ou limpeza real executada; exige aprovação antes de iniciar.

Os mesmos 12 avisos de deploy check persistem: **W004 HSTS, W008 SSL redirect, sete drf_spectacular.W001 e três W002**. Os sete W001 abrangem três parâmetros ID sem tipo, três métodos de serializer sem tipo e colisão de componentes Nested. Os três W002 são GoogleLoginView, DefinirSenhaView e TrocarSenhaView sem serializer de schema. Aviso de staticfiles ausente aparece nos testes, sem simulação de collectstatic/deploy.

Configuração sintética valida rejeição de DEBUG inseguro/chave curta/hosts curingas fora de desenvolvimento e cookies Secure em PRODUCTION. Ela não comprova ambiente publicado. Não foram ativados HSTS, SSL redirect ou trust de proxy. Permanecem NÃO EXECUTADOS: TLS/redirect/header sanitizado, hosts/origens reais, cookies no navegador, CORS/CSRF do frontend publicado, PostgreSQL, Cloudinary real, logs/retention/rate limiting e scan atualizado de dependências. Scanner não instalado; não foi solicitada instalação nem feito teste externo de vulnerabilidades.

## H. Arquivos alterados e diff

| Caminho | Objetivo e conteúdo | Impacto/risco | Validação |
|---|---|---|---|
| core/tests/test_integration_b43.py (novo) | Três testes: jornada API integrada, matriz com snapshots, rotas de documentação | Apenas testes; risco baixo para produção; usa banco de testes e nenhuma rede real. O fluxo longo tem exceção Ruff local justificada, sem refatoração de módulos. | 3/3 isolados e 273/273 na suíte, Ruff do arquivo aprovado |
| docs/FEAT-43-homologacao.md (novo) | Relatório A–J, contratos, resultados, riscos e checklist | Apenas documentação; não afirma que ambiente real foi aprovado nem que aceite ocorreu. | Revisão cruzada com código, PRs e comandos executados |

Não foram alterados app/settings.py, views, serializers, permissões, models, migrations, scripts existentes, frontend, banco, dump ou mídias. O diff comum não inclui os dois arquivos ainda não rastreados; revisar seu conteúdo completo e `git diff --no-index -- NUL <arquivo>` no Windows. `git diff --stat` da worktree mostra os dois binários preexistentes, que não devem entrar em staging. Nenhum git add/commit/push/merge/rebase, PR novo ou deploy foi feito nesta B43.

## I. Checklist B43

| Requisito | Resultado |
|---|---|
| Branch exclusiva e base DEV atualizada | PASSOU |
| Anti-duplicação e merged_at das dependências | PASSOU |
| Suíte integral sem falhas/erros/skips | PASSOU — 273/273, exit 0 |
| Fluxo API isolado com cadastro/JWT até decisão/notificação | PASSOU — nível B, sem equivalência com deploy |
| Autenticação, Google e revogação por senha | PASSOU no ambiente isolado |
| Oportunidades, filtros implementados e B47 | PASSOU |
| Perfis, portfólios, consentimento e diretório | PASSOU |
| B46, favoritos, candidaturas/notificações/WhatsApp | PASSOU |
| Matriz entre usuários e ausência de mutação negada | PASSOU |
| Uploads, storage/timeout simulados | PASSOU no contrato atual; política de destino/mídia PARCIAL |
| Correção B45/migrations/constraints e concorrência SQLite | PASSOU |
| Rotas de documentação servidas | PASSOU; schema completo PARCIAL |
| Ruff novo arquivo/runner | PASSOU |
| Ruff global no conjunto de testes reutilizados | FALHOU por dívida preexistente; nenhuma alteração cosmética aplicada |
| Check --deploy | PARCIAL — exit 0 com 12 avisos, não atesta produção |
| Origem/tratamento/responsável B54-03 | BLOQUEADO por decisão da equipe não confirmada |
| Aceite formal de riscos de mídia/destinos/retention | BLOQUEADO por decisão não confirmada |
| Nível C: servidor/PostgreSQL/TLS/CORS/Cloudinary reais | NÃO EXECUTADO |
| Scan atualizado de dependências/segredos e logs reais | NÃO EXECUTADO |
| Aceite do relatório e conclusão administrativa B43 | BLOQUEADO até revisão/aceite dos responsáveis |

## J. Vereditos e próximas autorizações

**PR B43: PRONTO COM RESSALVAS.** Os novos testes e o relatório têm evidência suficiente para revisão técnica, com 273 testes passando e sem alteração de runtime. Ressalvas: lint global preexistente, schema parcial, decisões de privacidade/segurança e homologação real pendentes. Nenhum PR existe ainda; prontidão para revisão não é autorização de publicação ou merge.

**Backend para homologação/produção: NÃO APTO à liberação final com estas evidências.** Níveis A/B passaram. Nível C está NÃO EXECUTADO; os riscos relevantes ainda não foram avaliados/aceitos formalmente pelos responsáveis. Isso não significa falha de todo o backend local nem atribui bug fictício às áreas não testadas.

Próximos passos: revisar os dois arquivos B43; autorizar commit específico, depois push e criação de PR com base DEV em etapas separadas; atribuir responsáveis/decisões B54-03 e mídia; aprovar plano/ambiente operacional C. Merge da B43 e deploy permanecem dependentes de autorização posterior própria. A conclusão administrativa exige integração aprovada ou aceite formal do relatório, e não foi presumida.
