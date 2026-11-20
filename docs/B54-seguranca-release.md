# B54 — Segurança, privacidade e preparação para produção

Revisão de 2026-11-20, exclusivamente em `MaRuJoBs/Back_Marujob`, branch `B54`.
Base: `c359787ac244ee624af4f1fbefa3276dd5c8c56d`, igual à DEV local e à `origin/DEV` após fetch.

**Resultado: alterações prontas para revisão em PR na DEV, com ressalvas operacionais. Produção não está homologada.**

## Histórico e escopo

A B54 anterior já foi integrada à DEV pelo [PR #22](https://github.com/MaRuJoBs/Back_Marujob/pull/22),
merge `2ebacc9`, confirmado pelo histórico Git e pelos metadados do GitHub. Foram preservadas a revogação de
access/refresh após alteração de senha, a validação de fotos Google e as proteções existentes de permissões.
Esta revisão cobre também os módulos de avaliações e chat integrados posteriormente; não repete as FEATs.

Na abertura, a branch era `FEAT-54`, no mesmo commit da DEV. As edições começaram somente depois da criação de
`B54`. Alterações preexistentes em `.pdm-python`, `.vscode/settings.json`, `core.png`, `db.sqlite3` e mídia local
foram preservadas. Nenhum frontend, endpoint, modelo de dados ou arquivo de migration foi acrescentado ou removido.
O arquivo de modelo do chat mudou somente a implementação da função que seleciona o storage.
A validação ocorreu localmente, sem merge, deploy ou alteração de dados em serviços externos.
O commit e o PR publicam somente o código, os testes e este relatório.

## Problemas comprovados e correções

| Problema | Evidência | Correção e arquivos |
| --- | --- | --- |
| WebSocket mantinha acesso após revogação ou expiração do JWT | Testes de conexão já aberta continuavam recebendo/enviando eventos após troca de senha, desativação ou expiração. | `chat/consumers.py` revalida JWT e estado atual do usuário antes de ações e eventos privados. Fecha com 4401 e limpa presença/grupo. |
| Entrada malformada derrubava o WebSocket e conteúdo arbitrário era copiado para logs | `action` como lista/dicionário causava exceção; um marcador sintético enviado como ação desconhecida aparecia no log. | `chat/consumers.py` valida tipos e não registra o texto desconhecido. `chat/middleware.py` trata query inválida e usa mensagem genérica. `chat/services.py` não imprime exceção de storage na exclusão. |
| Servidor de mídia local contornava a autorização dos anexos | A rota genérica de mídia utilizava `django.views.static.serve` sobre o mesmo diretório dos anexos. O nome aleatório não constitui autorização. | `core/media.py` e `app/urls.py` bloqueiam `chat_files`, inclusive caminhos normalizados e separadores Windows. Mídia pública existente continua disponível. |
| Novos anexos Cloudinary usavam entrega pública por padrão | O storage raw anterior fazia upload sem `type` restrito. A autorização na API não protegia o URL direto do serviço. | `chat/storage.py` usa `type=authenticated`, download assinado interno, timeout, streaming limitado e sem redirects. `chat/models/message.py` seleciona esse storage. A API de download usa `private, no-store` em `chat/views/message.py`. |
| Endpoints sensíveis não tinham orçamento de requisições na aplicação | Novos testes conseguiam ultrapassar o orçamento pretendido; antes da correção não havia resposta 429. | `core/throttles.py`, `core/views/tokens.py`, `core/views/user.py` e `app/urls.py`: limite compartilhado por IP em login, refresh, verify, Google e registro; limite por usuário nas operações de senha. |
| Configuração de produção aceitava fallback implícito de banco, segredo repetitivo e origens inseguras | Testes demonstraram aceitação dessas configurações. HTTPS redirect/HSTS também não eram ativados pelo Django. Isso não demonstra como uma borda externa estava configurada. | `app/settings.py` exige banco explícito fora de desenvolvimento, rejeita segredos triviais e origens inválidas/HTTP em produção, ativa redirect HTTPS e HSTS de uma hora. Cookies Secure anteriores foram preservados. |
| Runner de auditoria não iniciava no Windows com o chat integrado | Bloqueio de sockets interrompia a inicialização do asyncio e do waker do Twisted antes dos testes. | `scripts/audit_b54.py` inicializa o runtime ASGI antes do bloqueio e permite somente a criação interna de socketpair no thread correspondente. Conexões diretas continuam bloqueadas nos testes. |

Os testes novos de configuração/limites falharam antes das correções (18 falhas/subcenários em 10 testes).
Os cinco testes iniciais de WebSocket também reproduziram os problemas (quatro falhas e um erro).
Nenhum teste anterior foi removido ou enfraquecido.

## Configuração e compatibilidade

- `MODE=PRODUCTION`: `AUTH_THROTTLE_RATE=20/min` por IP entre os cinco endpoints públicos de autenticação;
  `PASSWORD_THROTTLE_RATE=5/min` por usuário entre definir/trocar senha. Excesso retorna 429 e `Retry-After`.
  Contagens incluem tentativas válidas e inválidas. Ambos os limites são configuráveis e validados na inicialização.
- Desenvolvimento permanece com HTTP local, fallback SQLite e sem throttling desses endpoints.
- O orçamento por IP usa `REMOTE_ADDR`, sem confiar diretamente em `X-Forwarded-For`. O servidor/proxy deve
  fornecer o IP real apenas a partir de proxies confiáveis; caso contrário, usuários atrás do proxy compartilham orçamento.
- Em produção, `REDIS_URL` também configura o cache Redis para compartilhar contadores. Sem Redis, o cache padrão
  fica por processo. Throttles DRF não oferecem contagem atômica nem substituem proteção de borda contra abuso.
- `DATABASE_URL` passa a ser obrigatória em PRODUCTION e MIGRATE. SQLite explicitamente configurado continua aceito.
  Não houve troca do banco atual.
- Produção exige origens HTTPS sem caminho, credenciais, query, fragmento ou wildcard. `ALLOWED_HOSTS`, `DEBUG=False`
  e a exigência de chave com 50 caracteres continuam obrigatórios. A verificação adicional rejeita chaves com menos
  de cinco caracteres distintos; isso não mede aleatoriedade nem substitui geração segura do segredo.
- `SECURE_SSL_REDIRECT=True` e HSTS de 3600 segundos em produção. `TRUST_X_FORWARDED_PROTO` continua false por padrão:
  habilitar somente atrás de proxy controlado que remova/substitua o cabeçalho. Validar esse caminho antes da publicação
  para evitar loop de redirect. HSTS de subdomínios e preload permanecem desabilitados.
- WebSockets validam novamente a credencial no próximo evento recebido ou enviado, com consulta adicional ao usuário.
  Uma conexão ociosa pode permanecer aberta até o próximo evento; não recebe dados nem executa novas ações sem validação.
- Novos anexos Cloudinary usam entrega autenticada. O backend mantém leitura de anexos legados pelo download autorizado,
  mas isso **não revoga URLs públicos antigos**. Exclusão considera os dois tipos de entrega. Os contratos de resposta
  e a aceitação de arquivos como download no chat foram preservados; HTML/SVG não são exibidos inline.
- `.env.exemplo` registra as variáveis e condições. `.gitignore` evita inclusão de novos arquivos de ambiente, banco,
  dump e mídia local. Arquivos já rastreados continuam no índice/histórico e não foram apagados.

## Testes executados

Ambiente: Windows, Python 3.13, dependências locais do PDM, Django 5.2.12 e DRF 3.16.1. Testes usam SQLite em memória,
contas fictícias e storage temporário; `.env` desabilitado e conexões externas bloqueadas no processo da auditoria.
Redis é desabilitado explicitamente no runner para não usar uma instância configurada no ambiente local.
O diretório `staticfiles` ausente gera um aviso preexistente; a coleta de estáticos pertence à publicação.

| Verificação | Resultado |
| --- | --- |
| Baseline, após corrigir a portabilidade do runner | 378 testes aprovados. |
| Suíte completa final, um processo | **402 testes aprovados, zero falhas, erros ou skips; exit 0; 17,872 s.** |
| `pdm run python scripts/audit_b54.py check` | Exit 0, nenhuma questão. |
| `pdm run python scripts/audit_b54.py --production check --deploy` | Exit 0 com 12 avisos: sete W001 e três W002 do schema; W005 e W021 de HSTS subdomínios/preload. Nenhum aviso foi silenciado. |
| `pdm run python scripts/audit_b54.py makemigrations --check --dry-run` | Exit 0, nenhuma alteração detectada. |
| `pdm run python scripts/audit_b54.py showmigrations --plan` | Exit 0, grafo inclui `core.0023_avaliacoes_reputacao` e `chat.0001_initial`. O banco dessa execução é descartável, sem migrations aplicadas. |
| Inspeção adicional do SQLite local | Conexão SQLite `mode=ro`: nenhuma migration core/chat pendente, dependência inconsistente ou coluna esperada ausente; grafo sem conflitos. Nenhum registro pessoal foi impresso. |
| Ruff check e format check | Aprovados nos 15 arquivos Python alterados/adicionados. |
| `git diff --check` | Aprovado. |

O runner despacha esses comandos para o management do Django como `manage.py`, usando configuração sintética
em vez de carregar o banco/credenciais da aplicação. A inspeção local consulta somente migrations e metadados de colunas.

Cobertura dos oito cenários obrigatórios, reaproveitada e reexecutada:

| Cenário | Evidência automatizada |
| --- | --- |
| Freelancer A não altera dados privados de B | `test_authentication`, `test_profiles_portfolios` e matriz de autorização `test_integration_b43`. |
| Empresa A não edita/exclui vagas de B | `test_authentication`, `test_freelances` e matriz B43; dono não pode ser falsificado. |
| Empresa não gerencia candidaturas alheias | `test_candidaturas`, `test_notificacoes` e matriz B43. |
| Freelancer não acessa operações exclusivas de empresa | Testes anteriores e diretório B45, incluindo contas com grupos ambíguos. |
| Anônimo é recusado nos recursos privados | `test_security_b54`, testes de cada módulo e testes REST/WebSocket do chat. |
| Projeções públicas não expõem campos sensíveis | `test_freelancer_publico` verifica allowlists, dados privados ausentes e revogação da publicação; avaliações têm projeção própria. |
| Tokens inválidos/expirados/revogados são rejeitados | `test_authentication`, `test_security_b54` e novos testes de conexões de chat já abertas. |
| Uploads inválidos são bloqueados | Validação de conteúdo, formatos, tamanho e dimensões de imagens; limites de anexos, arquivo vazio, autorização de download, bloqueio do acesso direto e download seguro de outros tipos. |

As jornadas com dois freelancers e duas empresas, cadastro, JWT, perfil, portfólio, vagas, candidaturas,
notificações e decisões continuam aprovadas. Os 24 testes novos concentram-se nas lacunas desta revisão.

## Pendências para publicação

1. **Dados já versionados:** o inventário sanitizado `scripts/audit_b54_artifacts.py` confirmou 11 contas no banco
   versionado, duas no dump e 17 arquivos de mídia. Há e-mails e hashes de senha; a origem real ou sintética permanece
   não verificada. Não houve remoção, reescrita de histórico ou teste de credenciais. Responsáveis devem decidir
   retirada do versionamento, retenção e eventual remediação. A regra de ignore não resolve o histórico existente.
2. **Mídia legada:** inventariar e restringir/remover anexos já publicados no Cloudinary e invalidar caches. Fotos
   e imagens com URLs públicos antigos também exigem política de acesso/retirada; ocultar o JSON de um perfil não
   revoga esses URLs. Homologar upload, download e exclusão autenticados no serviço real.
3. **Infraestrutura:** validar HTTPS/proxy, IP real, origens publicadas, Redis compartilhado, limites de borda,
   logs de acesso sem JWT na query do WebSocket e banco/backup do ambiente publicado. Nenhum serviço real foi acessado.
4. **Limites restantes:** não houve teste de carga/ataque, scanner atualizado de dependências, varredura antimalware,
   validação de PostgreSQL real ou homologação de Google OAuth/Cloudinary. Download de fotos Google mantém as proteções
   anteriores, sem prova nova de SSRF controlável por atacante; política de destinos/egress continua pendente.
5. **Avisos:** corrigir a documentação OpenAPI em tarefa própria. HSTS com subdomínios/preload depende de controlar
   todos os domínios envolvidos; não deve ser ativado somente para eliminar os avisos.

## Referências técnicas

- [Checklist de publicação Django 5.2](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
- [Limites e restrições do throttling DRF](https://www.django-rest-framework.org/api-guide/throttling/).
- [Controle de acesso e downloads assinados Cloudinary](https://cloudinary.com/documentation/control_access_to_media).

O PR pode revisar estas correções e as evidências locais. Sua aprovação não substitui o tratamento das pendências
de dados nem a homologação operacional necessária à publicação.
