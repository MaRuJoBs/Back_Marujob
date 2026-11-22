# B62 · Limite de profissionais por oportunidade

`max_profissionais` é opcional em `/api/freelances/`. O valor `null` mantém aprovações sem limite e zero bloqueia novas aprovações. O limite conta apenas candidaturas aprovadas. Novas candidaturas, recusas e repetições de decisões já registradas mantêm seu comportamento.

A empresa recebe HTTP 409 ao tentar aprovar além do limite. A API serializa aprovações pelo bloqueio da oportunidade em bancos com bloqueio de linha.

A migration `0026_limite_profissionais` depende de `0025_notificacoes_freelancer_push`. As oportunidades existentes começam com `max_profissionais=null`, e os dados anteriores são preservados.
