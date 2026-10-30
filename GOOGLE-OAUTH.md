# FEAT-39 — Revisão Google Identity Services

Revisão exclusiva do backend `Back_Marujob`, branch `FEAT-39`. Não foi acessado o
frontend nem alterado `.env`, banco de dados, dependências ou infraestrutura.
A implementação e validação foram feitas antes de qualquer publicação. O usuário
autorizou posteriormente commit e push na mesma branch/PR; merge e deploy seguem
fora do escopo.

## Fluxo e contrato preservados

O fluxo considerado é GIS no navegador, com callback recebendo um **ID token** em
`credential` e enviando JSON para `POST /api/auth/google/`. Não existe nesta API
troca de authorization code, uso de client secret ou callback OAuth de redirecionamento.

O servidor usa `verify_oauth2_token` com o `GOOGLE_CLIENT_ID` do ambiente, verificando
assinatura, emissor Google, audiência e expiração. Também exige `sub`, audiência
correspondente e `email_verified=true`. E-mail, identidade e grupos enviados
separadamente pelo frontend não definem a identidade da conta.

Cadastro exige `tipo=usuario` ou `empresa`, atribuindo `Usuário` ou `Empresa`.
Login de conta vinculada preserva todos os grupos, inclusive administrativos.
Conta inativa é rejeitada. Conta local sem vínculo não é associada por coincidência
de e-mail: retorna erro e deve entrar com senha. O formato de sucesso continua
`access`, `refresh`, `user` e `precisa_definir_senha`, conforme `FEAT-39.md`.

Somente o endpoint público Google deixa de processar JWT da API: um header Bearer
antigo não bloqueia a nova autenticação Google. A credencial Google continua
obrigatória e verificada. Rotas privadas mantêm a autenticação JWT anterior.

## Problemas encontrados e correções

| Problema | Correção |
| --- | --- |
| CORS aberto em desenvolvimento escondia divergências de origem | Lista explícita padrão para localhost e 127.0.0.1 na porta 5173; nenhuma liberação global em qualquer modo |
| Origens CSRF fixas nas portas antigas | `CSRF_TRUSTED_ORIGINS` configurável por ambiente, com Vite nos padrões de desenvolvimento |
| CORS posicionado depois do WhiteNoise | Middleware movido antes de WhiteNoise para também cobrir respostas antecipadas desse middleware |
| Ausência de reconhecimento configurável de HTTPS por proxy | `TRUST_X_FORWARDED_PROTO`, opt-in, configura o header seguro do Django |
| Espaços no Client ID podiam causar audiência incompatível | Remoção de espaços externos; valor vazio retorna 503 sem desabilitar a verificação de audiência |
| MODE sem normalização e DEBUG com leitura sensível a maiúsculas | MODE normalizado e validado; DEBUG aceita `true` e produção continua rejeitando debug ativo |
| JWT antigo no header bloqueava a rota pública antes de validar Google | Identidade da rota passa a depender exclusivamente da credencial Google |
| `tipo` como lista causava erro interno em cadastro | Entrada inválida retorna 400; `cadastro` textual aceita somente true/false |
| Ausência de testes de indisponibilidade e de configuração de navegador/proxy | Cobertura adicional de 503, preservação de grupos, CORS, CSRF e HTTPS percebido pelo Django |

Não foi constatada falha criptográfica na validação existente. Os testes anteriores
de assinatura, emissor, audiência, expiração e grupos foram preservados.

## Quais URLs configurar manualmente

Os domínios reais da Vercel e do Fabroku/Dokku não estão identificados nos arquivos
de configuração e documentação inspecionados. Os marcadores abaixo **não são URLs
reais** e devem ser substituídos pelo responsável:

| Informação necessária | Quem deve informar |
| --- | --- |
| Origem HTTPS canônica do frontend Vercel, incluindo domínio próprio se utilizado | Responsável pela Vercel |
| Origens HTTPS fixas de homologação/preview que precisam de login | Responsável pela Vercel |
| Host público e URL base HTTPS da API Fabroku/Dokku | Responsável pelo backend |
| Domínios HTTPS de desenvolvimento no celular, caso use túnel | Responsável pelo ambiente de desenvolvimento |
| Qual Client ID web pertence a cada ambiente | Responsável pelo projeto Google Cloud |
| Se o proxy remove/substitui X-Forwarded-Proto e restringe acesso direto à aplicação | Responsável pelo Fabroku/Dokku |

No cliente OAuth do tipo **Web application**, em **Origens JavaScript autorizadas**:

```text
http://localhost
http://localhost:5173
http://127.0.0.1:5173
https://<HOST_REAL_DO_FRONTEND_VERCEL>
https://<HOST_FIXO_DE_HOMOLOGACAO_SE_USADO>
https://<HOST_DE_DESENVOLVIMENTO_HTTPS_SE_USADO>
```

Os três primeiros são endereços de desenvolvimento; os demais são marcadores.
Cadastre cada origem efetivamente utilizada no cliente daquele ambiente. Origem
inclui esquema, host e porta quando aplicável; não inclui caminho, query ou `/api/`.
`localhost` e `127.0.0.1` são origens distintas. O Google recomenda também o registro
de `http://localhost` junto da variante com porta para testes locais.

A URL da API Django não é origem JavaScript só porque recebe o POST. O código GIS
é executado na página Vue, portanto a origem autorizada é a do **frontend**.
Previews variáveis não são automaticamente autorizados: prefira um domínio fixo
de homologação e cadastre a origem exata, sem liberar todos os projetos Vercel.

**URIs de redirecionamento autorizados:** nenhum novo URI é necessário para o fluxo
de callback JavaScript + POST JSON descrito. Não cadastre `/api/auth/google/` como
redirect URI apenas porque é a rota de validação. Se o frontend efetivamente usar
`ux_mode=redirect` ou `data-login_uri`, isso exige revisão adicional: registrar o
destino exato com caminho e validar o fluxo de POST direto/CSRF do GIS. O backend
atual foi testado para callback com POST JSON; não foi homologado como receptor
de redirecionamento direto do Google.

Verifique também branding/consentimento, domínios autorizados e usuários de teste
do projeto Google quando o aplicativo estiver em modo de teste.

## Ambiente Django no Fabroku/Dokku

| Variável | Formato/finalidade |
| --- | --- |
| `MODE` | `PRODUCTION` no serviço publicado; `DEVELOPMENT` local; `MIGRATE` continua suportado |
| `DEBUG` | `False` em produção |
| `SECRET_KEY` | Segredo forte já exigido na FEAT-39; nunca enviado ao frontend |
| `GOOGLE_CLIENT_ID` | Um único Client ID **web** do ambiente, sem lista; deve ser o mesmo usado pelo GIS correspondente |
| `ALLOWED_HOSTS` | Hosts da API separados por vírgula, sem esquema, porta ou caminho; sem `*` em produção |
| `CORS_ALLOWED_ORIGINS` | Origens completas e exatas do frontend, separadas por vírgula, sem caminho nem barra final |
| `CSRF_TRUSTED_ORIGINS` | Origens completas extras que realmente enviam formulários com sessão/CSRF; lista por vírgula; vazio é válido quando só há formulários same-origin |
| `TRUST_X_FORWARDED_PROTO` | `False` por padrão; `True` somente após confirmar proxy controlado e header sanitizado |

`CORS_ALLOW_ALL_ORIGINS` é sempre `False` e não tem override por variável. Em
desenvolvimento, se `CORS_ALLOWED_ORIGINS` estiver ausente, são permitidos
`http://localhost:5173` e `http://127.0.0.1:5173`. Variável definida vazia significa
lista vazia; uma lista explícita substitui os padrões. Outros ambientes não
herdam localhost nem portas antigas nas origens CORS/CSRF.

Exemplo **simbólico**, não copiar os marcadores literalmente:

```text
MODE=PRODUCTION
DEBUG=False
ALLOWED_HOSTS=<HOST_REAL_DA_API>
CORS_ALLOWED_ORIGINS=https://<HOST_REAL_DO_FRONTEND_VERCEL>
GOOGLE_CLIENT_ID=<CLIENT_ID_WEB_DO_AMBIENTE>
```

No fluxo de API atual usa-se Bearer JWT, não sessão nem cookie de autenticação.
O POST JSON Google não exige token CSRF de sessão; adicionar uma origem a
`CSRF_TRUSTED_ORIGINS` não corrige CORS, origem Google ou audiência inválida.
O admin Django continua exigindo sessão/CSRF. Não foram desativadas proteções CSRF,
habilitados cookies cross-site ou introduzida autenticação por sessão na API.

Se TLS termina no proxy, `TRUST_X_FORWARDED_PROTO=True` faz Django reconhecer
`X-Forwarded-Proto: https`. Não habilite sem confirmar que o proxy remove valores
enviados pelo cliente, reescreve o header e protege acesso direto ao servidor.
A opção não instala certificado, não habilita HTTPS e não força redirect HTTPS.
Não foi alterada a infraestrutura de publicação nem adicionado redirect que possa
gerar loop quando o proxy estiver incorreto.

## Vercel e frontend — somente orientações

Sem acesso ao repositório frontend, não é possível confirmar os nomes atuais das
variáveis. Se o projeto ainda não possui convenção, os nomes sugeridos são:

| Variável sugerida no Vite/Vercel | Valor esperado |
| --- | --- |
| `VITE_GOOGLE_CLIENT_ID` | Mesmo Client ID web de `GOOGLE_CLIENT_ID` no backend daquele ambiente |
| `VITE_API_BASE_URL` | URL pública HTTPS real da API; observar se o cliente já acrescenta `/api/` para não duplicar o caminho |

Usar os nomes efetivamente lidos pelo frontend; cadastrar uma variável com nome
diferente do código não tem efeito. Variáveis `VITE_*` são públicas no bundle;
nunca colocar `SECRET_KEY`, client secret, credenciais de banco ou JWT nelas.
O fluxo GIS atual não necessita client secret. Configurar separadamente ambientes
Development/Preview/Production da Vercel e reconstruir a aplicação após mudar
valores usados no build. Não misturar Client ID de desenvolvimento com API que
aceita apenas o Client ID de produção; este backend não aceita audiências arbitrárias.

Conferir no frontend, sem alterações nesta revisão:

- Callback GIS envia `credential` como ID token, não access token Google ou código.
- Requisição usa a URL HTTPS correta, com `/api/auth/google/` e barra final,
  evitando redirects desnecessários em POST/preflight.
- Origem usada no navegador corresponde à origem cadastrada no Google e no CORS.
- Tratar 400 (credencial/dados), 401 (conta inativa), 404 (conta ausente) e 503
  (Google/configuração indisponível) sem registrar tokens no console.
- Examinar CSP, COOP, popups e FedCM no host que serve o frontend caso o botão
  falhe antes de enviar POST. Headers do Django não corrigem a página na Vercel.

## Celular e rede local

Não foi reproduzida a falha em um aparelho; as causas abaixo são hipóteses de
configuração, e não uma declaração de resolução:

1. `localhost`/`127.0.0.1` no celular apontam para o próprio aparelho, não para o PC.
2. Google exige origens seguras, com exceções de loopback para desenvolvimento.
   IP privado HTTP do PC não é equivalente a localhost e não é uma alternativa
   suportada ao requisito de origem do GIS. One Tap tem exigência própria de HTTPS.
3. Frontend HTTPS chamando API HTTP pode ser bloqueado por mixed content antes de
   CORS. Certificados inválidos, DNS e restrições de rede também impedem o acesso.
4. IP/host da API ausente em `ALLOWED_HOSTS` pode causar 400; origem de frontend
   ausente no CORS bloqueia a leitura da resposta pelo navegador.
5. Client IDs diferentes geram erro de audiência mesmo com CORS correto.

Alternativa segura: usar homologação HTTPS ou um túnel HTTPS confiável com hostname
estável e certificado válido para o frontend e API (ou proxy same-origin HTTPS).
Registrar a origem HTTPS exata no cliente Google, configurar CORS para ela e hosts
da API no Django, mantendo o mesmo Client ID por ambiente. Abrir essa URL no celular.
Não publicar IP HTTP, desativar verificações de token ou liberar CORS globalmente
para tentar contornar o Google. Bind da rede, túnel, firewall e certificados não
foram configurados por esta revisão.

## Validação e pendências

A suíte original passou com 13 testes antes das alterações. Os testes desta revisão
cobrem cadastro dos dois tipos, login vinculado, preservação de grupos e contrato,
token inválido/expirado, audiência, assinatura e emissor, e-mail não verificado,
inatividade, conta local não vinculada, Client ID ausente, indisponibilidade de
transporte/chaves públicas, JWT antigo no header, preflight CORS e proxy opt-in.
Não são feitas chamadas reais ao Google.

Resultado: **20 testes passaram em 36,210 s**. `manage.py check` não identificou
problemas. O aviso preexistente de diretório `staticfiles` ausente não impediu os
testes. Nenhum dado real foi usado para gerar tokens de teste.

Comandos pelo ambiente PDM:

```text
pdm run python manage.py test
pdm run python manage.py check
pdm run python manage.py makemigrations --check --dry-run
pdm run ruff check app/settings.py core/views/user.py core/tests.py
pdm run ruff format --check app/settings.py core/views/user.py core/tests.py
git diff --check
```

Não há migration nova nesta revisão. A aplicação da migration `0014` continua
pendente conforme a entrega principal. Faltam os domínios reais, conferência do
console Google, ambiente Vercel e proxy Fabroku/Dokku, além de homologação real no
celular. Testes locais de headers não substituem essa validação no navegador.

Referências oficiais consultadas:

- [GIS: configuração, origens e redirect opcional](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid)
- [GIS: callback, credential e modo redirect](https://developers.google.com/identity/gsi/web/reference/js-reference)
- [Google: validação de origens JavaScript](https://developers.google.com/identity/protocols/oauth2/javascript-implicit-flow#origin-validation)
- [Django: proxy HTTPS confiável](https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header)
- [Django: origens CSRF confiáveis](https://docs.djangoproject.com/en/5.2/ref/settings/#csrf-trusted-origins)
