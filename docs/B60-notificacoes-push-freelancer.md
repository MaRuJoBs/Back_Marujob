# B60 · Notificações de decisão para freelancers

A aprovação ou recusa feita pela empresa registra um evento no histórico do freelancer. Uma aprovação indica o resultado da candidatura. A conclusão do trabalho segue seu fluxo próprio.

## API para o frontend

Use `Authorization: Bearer <access_token>` nas rotas marcadas como freelancer. O histórico segue a paginação DRF de 10 itens, do mais recente para o mais antigo, com desempate pelo ID. O `count` da consulta com `lida=false` é o total para o badge, mesmo quando há várias páginas.

| Método | Rota | Acesso | Sucesso |
| --- | --- | --- | --- |
| GET | `/api/notificacoes-freelancer/` | Freelancer | 200 com página |
| GET | `/api/notificacoes-freelancer/?lida=false` | Freelancer | 200 com página de não lidas |
| GET | `/api/notificacoes-freelancer/{id}/` | Freelancer | 200 com objeto |
| PATCH | `/api/notificacoes-freelancer/{id}/marcar-lida/` | Freelancer | 200 com objeto atualizado, sem corpo de entrada |
| POST | `/api/notificacoes-freelancer/marcar-todas-lidas/` | Freelancer | 200 com `{"atualizadas": 2}`, sem corpo de entrada |
| GET | `/api/push/vapid-public-key/` | Público | 200 com `{"publicKey": "<base64url>"}` |
| POST | `/api/push/subscriptions/` | Freelancer | 204 sem corpo |
| DELETE | `/api/push/subscriptions/` | Freelancer | 204 sem corpo |

Exemplo de listagem:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [{
    "id": 123,
    "candidatura": 42,
    "oportunidade": 17,
    "evento": "candidatura_aprovada",
    "titulo": "Candidatura aprovada!",
    "mensagem": "Parabéns! Sua candidatura para a oportunidade 'Design' foi aprovada.",
    "lida": false,
    "criado_em": "2026-11-21T20:15:00Z"
  }]
}
```

Os IDs de candidatura e oportunidade servem para navegação. Ambos podem ser `null` se a candidatura foi excluída. A mensagem e a data do evento permanecem no histórico. `lida=true` filtra as lidas. As ações de leitura são idempotentes. Exiba o título e a mensagem como texto. `/api/notificacoes/` continua atendendo ao fluxo da empresa.

### Cadastrar e remover o dispositivo

1. Após uma ação explícita do freelancer e a permissão concedida, aguarde `navigator.serviceWorker.ready`. Obtenha `publicKey` da API, decodifique de base64url para `Uint8Array` e passe como `applicationServerKey` a `pushManager.subscribe({ userVisibleOnly: true, applicationServerKey })`. Reutilize a subscription atual quando vinculada à mesma chave pública.
2. Envie `subscription.toJSON()` em JSON no POST. O formato é `{"endpoint":"<url do Push Service>","keys":{"p256dh":"<chave pública P-256>","auth":"<segredo>"},"expirationTime":null}`. `expirationTime` é opcional e, quando presente, usa milissegundos desde a época Unix. O frontend deve cadastrar a subscription novamente ao renová-la ou ao trocar de conta.
3. Antes de descartar o JWT no logout, envie no DELETE o JSON `{"endpoint":"<url do Push Service>"}`. Chame também `subscription.unsubscribe()` no navegador. Exclua o endpoint do estado local. Se o logout ocorrer offline, o cancelamento no navegador ou a sincronização posterior é necessário para encerrar a entrega.
4. Uma conta pode cadastrar até cinco endpoints. Um endpoint pertence a uma única conta. Outra conta só pode assumir um endpoint existente se apresentar as duas chaves da subscription atual. O DELETE é restrito ao proprietário e retorna o mesmo 204 para um endpoint ausente ou de terceiro. Nenhuma resposta devolve as chaves ou o endpoint cadastrado.

A lista de destinos aceita Firebase/FCM (`fcm.googleapis.com/fcm/send/` ou `/wp/`), Mozilla (`updates.push.services.mozilla.com/wpush/v1/`, `/wpush/v2/` ou `/push/v1/`) e Apple (`web.push.apple.com/`). São exigidos HTTPS e um token no caminho, sem query. Navegadores que emitirem outros endpoints podem usar o histórico.

### Payload do Service Worker

```json
{
  "event": "candidatura_aprovada",
  "notification_id": 123,
  "title": "Candidatura aprovada!",
  "body": "Sua candidatura foi aprovada.",
  "url": "/notificacoes"
}
```

O outro evento é `candidatura_recusada`, com título e corpo correspondentes. No handler `push`, use `event.waitUntil(registration.showNotification(title, …))`. Em `notificationclick`, abra ou foque a SPA e resolva `url` na origem do frontend, com fallback para a rota do histórico se necessário. Ao abrir ou retomar a SPA, atualize a lista e o badge pela API. Cada dispositivo do freelancer pode receber a decisão, pois a mutação foi iniciada pela empresa.

### Erros esperados

| Status | Situação |
| --- | --- |
| 400 | Filtro inválido, endpoint/chaves inválidos, subscription informada como expirada ou cadastro acima do limite |
| 401 | JWT ausente, inválido ou expirado nas rotas privadas |
| 403 | Conta autenticada sem o papel de freelancer nas rotas privadas |
| 404 | Notificação ausente ou de outro usuário |
| 405 | Método não oferecido pela rota |
| 429 | Throttle excedido. Respeite `Retry-After` |
| 503 | Web Push sem configuração válida no GET da chave e no POST de subscriptions, ou contenção temporária do banco no gerenciamento de subscriptions |

## Ambiente e deploy

- Instale as dependências travadas e aplique `python manage.py migrate` antes de servir tráfego com o código novo. A migration `0025_notificacoes_freelancer_push` adiciona duas tabelas após `0024_empresaperfil_bairro`. O trabalho local B62 tem outra migration 0025 e outro contrato de Web Push. Ao integrar B60 e B62, coordene uma única tabela e API de subscriptions e reconcilie o grafo de migrations.
- Gere um par VAPID por ambiente conforme a seção de VAPID da Unidade 8. Configure `VAPID_PUBLIC_KEY` como o ponto P-256 não comprimido (65 bytes) e `VAPID_PRIVATE_KEY` como o escalar privado de 32 bytes, ambos em base64url sem padding. Configure `VAPID_SUBJECT` com o contato operacional em formato `mailto:...`. Use a mesma configuração em todos os processos. Guarde a chave privada no ambiente seguro do servidor e mantenha o par estável. Rotação da chave exige renovar as subscriptions no navegador. [Unidade 8 · VAPID](https://eduardo-da-silva.github.io/desenvolvimento-mobile/unidade8/vapid/)
- Com VAPID ausente ou inconsistente, o histórico continua disponível. Produção precisa de origem segura para o Service Worker, saída HTTPS aos provedores permitidos e política de logs que omita corpos, URLs de subscriptions e cabeçalhos de envio. Os limites são 60 GET/min por IP e 20 escritas/min por conta, usando o cache configurado pelo Django. Sem cache compartilhado, cada processo mantém seus próprios contadores.
- A entrega ocorre no processo da requisição, após o commit, com uma tentativa por dispositivo, timeout de conexão/leitura de 2 segundos e TTL de 300 segundos no provedor. Esse custo pode aumentar a latência da aprovação. Falhas transitórias ficam no histórico e o dispositivo segue cadastrado para eventos futuros. Respostas 404/410 removem a inscrição correspondente, e inscrições conhecidas como expiradas são limpas no cadastro ou antes de enviar. Eventos podem perder a tentativa se o processo cair após o commit. Um push em trânsito pode aparecer após logout ou troca de conta. O payload usa texto genérico e o acesso ao detalhe exige o JWT do destinatário. Uma fila durável com outbox resolveria a perda entre commit e envio, se a operação exigir essa garantia.
- O histórico começa nas decisões feitas após a migration. O banco anterior não guarda um evento imutável de decisão e o título atual da vaga pode diferir do título na ocasião. A migration não cria notificações nem envia pushes retroativos.

## Verificação automatizada

```shell
python manage.py check --settings=core.tests.settings
python manage.py makemigrations --check --dry-run --settings=core.tests.settings
python manage.py test --settings=core.tests.settings
```

A suíte B60 cobre o upgrade a partir da migration 0024, a concorrência de decisões, o isolamento entre contas e a assinatura e cifragem com o transporte HTTP simulado.

## Teste em dois navegadores ou dispositivos

1. Configure chaves próprias em homologação, integre o Service Worker ao frontend e use HTTPS. Para dois navegadores locais, `localhost` também permite Service Worker. Um IP local em HTTP comum não oferece o contexto seguro necessário.
2. Faça login com a mesma conta freelancer em Chrome e Firefox em perfis independentes. Autorize push e confirme os dois cadastros com 204. Deixe uma aba em segundo plano ou fechada, com o navegador apto a receber push.
3. Crie duas candidaturas de teste. Com a empresa proprietária, aprove uma e recuse outra. Confirme as notificações nos dois dispositivos e os dois registros no histórico. Confira o badge com `lida=false`, repita a decisão e confirme que a contagem continua igual.
4. Saia em um dispositivo e confirme que uma nova decisão só dispara no dispositivo ainda inscrito. Entre com outro freelancer e confirme que a URL de detalhe da conta anterior responde 404.

O fluxo adapta os cinco passos da Unidade 8 ao backend MaRuJoB’s. O servidor publica VAPID, mantém as subscriptions vinculadas ao JWT, cifra e envia pelo Push Service, enquanto o Service Worker e a interface de permissão ficam a cargo do frontend. [Unidade 8 · Web Push, tutorial e atividades](https://eduardo-da-silva.github.io/desenvolvimento-mobile/unidade8/)
