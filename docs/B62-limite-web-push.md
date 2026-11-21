# B62 — Limite de profissionais por oportunidade e Web Push

## Limite de profissionais

`max_profissionais` é um campo opcional de `Freelance`. `null` mantém o comportamento sem limite; `0` impede aprovações. O teto conta somente candidaturas com status `aprovada`, não candidaturas pendentes. A empresa continua recebendo candidaturas e pode recusar candidaturas mesmo depois de atingir o teto.

O campo é retornado e aceito pelo contrato existente de `/api/freelances/`. Uma tentativa de aprovar candidatura que exceda o teto retorna HTTP 409 com código `oportunidade_limite_atingido`. As aprovações são serializadas pelo bloqueio da oportunidade.

## Web Push

- `GET /api/webpush/public-key/` retorna `{ "public_key": "..." }` para configurar o cliente Web Push.
- `POST /api/webpush/subscriptions/` registra a inscrição do navegador autenticado. O corpo segue o formato do navegador: `{ "endpoint": "https://...", "keys": { "p256dh": "...", "auth": "..." } }`.
- `DELETE /api/webpush/subscriptions/{id}/` remove somente inscrição pertencente à conta autenticada.

O endpoint HTTPS é único globalmente; registrar o mesmo endpoint novamente atualiza as chaves e o proprietário. O backend envia push para a empresa ao chegar candidatura e para o profissional quando sua candidatura muda de pendente para aprovada/recusada. Inscrições expiradas (HTTP 404/410) são removidas. Falhas de entrega não desfazem a operação principal.

Configure `WEBPUSH_VAPID_PUBLIC_KEY`, `WEBPUSH_VAPID_PRIVATE_KEY` e `WEBPUSH_VAPID_SUBJECT` no ambiente. O subject deve ser um identificador de contato VAPID, como `mailto:suporte@dominio`. Sem as três configurações, o backend mantém as inscrições, mas não envia push. A chave privada nunca é exposta pela API.

## Banco e dependências

A migration `0026_b62_limite_webpush` adiciona o limite e a tabela de inscrições, com exclusão em cascata pela conta. A dependência `pywebpush` implementa a entrega compatível com Web Push.
