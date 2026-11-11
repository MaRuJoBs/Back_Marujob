# B54 — Validação antes de merge

## Atualização após integração efetiva do FIX-B45 — 2026-11-11

**Situação atual: PRONTO COM RESSALVAS para revisão técnica do PR de auditoria, na base local validada. Sistema não liberado para produção.** O registro anterior abaixo permanece como evidência histórica do bloqueio, que agora foi resolvido.

- PR #23 confirmado integrado: merged_at `2026-11-11T18:48:52Z`, commit da DEV `34a58b5076ef96f7088b02911242155e8764c576`. A integração remota já havia sido concluída quando esta etapa começou; não foi repetida. Seu diff continua restrito a `core/tests/test_freelancer_publico.py`, sem migrations de produção.
- FEAT-54 inicial `651dfb2bc1d4c3153b6f8f72f2be643d86811151`; merge normal local de origin/DEV concluído sem conflitos em `1c64c9751c1d1c52ac5e8bcca047a776e479f0aa`. O único arquivo alterado pelo merge em relação ao primeiro pai é o teste B45 (três linhas adicionadas, duas removidas).
- Confirmados como ancestrais preservados: b832120, 69e2bdf, b9cf1d7 e 651dfb2, além de 34a58b5. Os três testes recentes e seus documentos continuam intactos.
- Antes/depois do merge, comparação SHA256 confirmou preservação byte a byte de core.png, db.sqlite3, imagem local não rastreada, test_security_b54.py, FEAT-54-revisao-final.md e deste documento. Este acréscimo documental ocorreu somente depois da conferência. Nenhum valor de hash ou dado pessoal foi impresso.
- A worktree manteve as alterações preexistentes e os dois diretórios de inspeção não rastreados. Sem stash, rebase, reset, exclusão ou sobrescrita.

### Resultados sobre a base integrada 1c64c97

Os comandos do runner listados neste documento foram novamente executados: test --noinput, check, makemigrations --check --dry-run, showmigrations --plan e --production check --deploy.

| Verificação | Resultado real após integração |
|---|---|
| Suíte completa em um único processo | **270 testes, zero falhas, zero erros, sem skips, exit 0**; `Ran 270 tests in 11.733s`, `OK` |
| Django check | exit 0, nenhuma questão |
| Migration dry-run | exit 0, No changes detected |
| Plano de migrations | exit 0, grafo resolvido até core.0022_empresa_perfil em banco descartável |
| Deploy check sintético | exit 0, os mesmos 12 avisos: W004/W008 e dez de schema |
| Ruff check / format --check | exit 0 em nove arquivos Python da B54 e do teste B45 integrado |

Os 270 testes incluem regressões de JWT após troca/definição de senha, refresh, login normal/Google, conta inativa/excluída, tokens legados, uploads e erros Google, origem da URL/logs, permissões entre contas, candidaturas/notificações, portfólios, B45 e B46. Nenhum teste foi removido, alterado ou ignorado para obter aprovação nesta integração.

Persistem B54-03 com origem não verificada, restrição de destino/egress das fotos pendente de decisão, risco de órfãos banco/storage, timeout sem prazo total, PostgreSQL e configuração real de TLS/proxy/CORS/CSRF/Cloudinary sem homologação, avisos de schema e validações operacionais B43. As recomendações de tratamento dos dados e proteção de destinos descritas abaixo continuam válidas. Não se declara conformidade jurídica LGPD nem segurança absoluta.

O PR #22 remoto ainda aponta para 651dfb2 e permanece draft: **o merge local e este resultado ainda não foram enviados**. Próximas operações dependentes de autorização: commit somente desta atualização documental; push normal da FEAT-54 com o merge autorizado e a documentação; atualização do PR/estado de revisão; eventual merge do #22 após aprovação separada. Nenhum push, merge do #22, deploy ou migration em banco real ocorreu nesta etapa. O commit 1c64c97 é exclusivamente o merge local expressamente autorizado, sem commit adicional de implementação.

## Registro anterior à integração (histórico)

Data: 2026-11-11. **Veredito: NÃO PRONTO.** O critério de aceite da suíte integral (exit 0) não foi atendido. Esta validação complementa a [revisão das correções](FEAT-54-revisao-final.md), sem refazer a auditoria.

## Estado Git e PRs

Repositório confirmado: MaRuJoBs/Back_Marujob; branch FEAT-54 na pasta principal, HEAD/remoto `b9cf1d7219494421ae9d3f337ad5c9da7e2b71d8`. Após fetch --prune, DEV segue em `0226c2e0adbb17546dfe74e91df14dd03d4cd419`. Não houve avanço da DEV nem necessidade de integração. As outras duas worktrees estão detached; não se trabalhou nelas.

Alterações preexistentes em core.png, db.sqlite3, mídia não rastreada e diretório `.audit-b54` foram preservadas e não integram esta entrega. Não foi carregado .env nem utilizado o banco local nos testes.

- [PR #22](https://github.com/MaRuJoBs/Back_Marujob/pull/22): aberto, draft, base DEV, head FEAT-54 em b9cf1d7, merged_at=null. Contém as correções anteriores, mas ainda não estes três testes adicionais e este relatório.
- [PR #23](https://github.com/MaRuJoBs/Back_Marujob/pull/23): aberto, draft, head e8cb0daf, merged_at=null. Diff novamente conferido: somente o teste histórico B45, três linhas adicionadas e duas removidas; restaura todas as folhas do grafo no finally. Nenhum arquivo de migration de produção é modificado pelo FIX.

**A aprovação integral está bloqueada pela dependência B45.** Não se copiou o código do #23 nem se fez merge/rebase. Quando estiver integrado à DEV, a estratégia proposta é conferir o novo histórico e os diffs, verificar a worktree e planejar um merge normal da origin/DEV na FEAT-54, preservando seus commits. Essa operação exige autorização explícita prévia e nova avaliação dos arquivos locais; não foi executada. Depois é obrigatória nova execução integral sobre a base efetivamente integrada.

## Confirmação JWT e foto Google

As correções de b9cf1d7 foram preservadas sem alteração de runtime nesta etapa. Os testes executados confirmam:

- Access e refresh anteriores à troca/primeira definição de senha recebem 401; novo login por senha ou Google emite tokens funcionais.
- Refresh atual mantém o formato de resposta existente. Contas inativas/excluídas e tokens legados sem claim são negados.
- Foto aceita apenas conteúdo real JPEG/PNG/WebP, com limite cumulativo de bytes e proteção de dimensões. GIF/texto/imagens excessivas não são armazenados.
- Timeout de obtenção/leitura e erro de armazenamento local/Cloudinary simulado não impedem autenticação verificada. Foto é opcional; foto existente é preservada.
- Não segue redirects, rejeita URL não HTTPS/com credenciais, fecha a resposta e interrompe o streaming ao exceder limite.
- Novo teste confirma que `picture` no payload não sobrepõe `picture` das claims verificadas.
- Novo teste captura o log de timeout: somente `Optional Google photo unavailable`, sem URL, e-mail ou texto da exceção. Não representa auditoria de todos os logs publicados.

Tokens legados exigirão reautenticação na implantação. Nenhum endpoint, JSON público, duração de token ou regra de permissão foi alterado nesta validação.

## Destino das URLs: evidência condicional e proposta

Novo teste `test_characterization_verified_picture_has_no_destination_allowlist` simula o retorno do verificador Google com URL HTTPS de loopback e substitui requests.get por mock. O downloader recebe esse destino. Nenhuma conexão de loopback ou rede real é feita.

Isso comprova ausência de restrição de host/IP no helper **depois** da verificação de claims. Não comprova que um cliente possa obter token Google válido contendo esse endereço; a obtenção de claims foi deliberadamente simulada. Portanto, não se declara SSRF explorável comprovado. O teste é caracterização desse limite de confiança, não evidência de remediação. O fluxo não foi modificado.

Risco residual: se o provedor emitir picture para destino não confiável, ou se esse destino resolver para rede privada, o servidor tenta obter a imagem. HTTPS e ausência de redirects não equivalem a restrição de destino. URLs HTTPS também podem indicar portas diferentes da padrão, atualmente sem restrição específica. Cabe confirmar contrato de URLs Google e política de egress; não se presumiu qual host o provedor sempre utiliza.

**Proposta mínima, dependente de aprovação antes de implementar:** identificar os hosts de foto legitimamente necessários a partir do contrato/documentação e de evidência sintética autorizada, adotar allowlist explícita com comparação segura de hostname e porta 443 (opcional omitida), negar IPs literais e sufixos enganosos, manter redirects desabilitados e falha opcional. Não bloquear domínios por adivinhação, pois isso pode remover fotos legítimas. Restrição de egress para redes privadas/link-local/loopback na infraestrutura complementa o controle da aplicação; validação DNS isolada não elimina rebinding.

Testes propostos para a mudança: hosts exatos/subdomínios permitidos conforme política, domínio com sufixo enganoso, userinfo, porta alternativa, IPv4/IPv6 literal/loopback, destino desconhecido e redirect. Todos com mocks; rejeitados não podem chegar ao downloader, e login deve continuar funcionando. Se forem adotadas verificações DNS, cobrir resolução privada e mudança de resolução, sem prometer proteção apenas por checagem prévia.

## B54-03: inventário reconfirmado e decisões

`pdm run python scripts/audit_b54_artifacts.py` executado novamente, exit 0, sobre blobs de HEAD em memória:

| Artefato | Evidência sanitizada |
|---|---|
| SQLite versionado | 11 registros User com e-mail e hash pbkdf2_sha256 |
| dump.json | 2 registros User com e-mail e hash pbkdf2_sha256 |
| Mídia versionada | 17 arquivos; quatro com EXIF; nenhuma tag GPS EXIF detectada |
| Histórico nas refs locais disponíveis | 23 entradas para banco, três para dump, seis para mídia; zero para .env |
| Heurísticas dos artefatos atuais | Nenhum JWT-like, marcador de chave privada ou token GitHub-like detectado; não é scanner completo de segredos |

Banco/dump contêm dados identificadores e hashes; serem reais ou sintéticos permanece **não verificado**. O conteúdo visual das imagens não foi classificado; EXIF pode conter informações pessoais, e ausência de tag GPS não prova ausência de localização. Nenhum valor foi impresso e nenhum artefato foi alterado ou copiado para disco. `.env` está ignorado; banco/dump/novo arquivo de mídia não estão protegidos por política de ignore suficiente, e ignore não remove arquivos já rastreados.

Antes da homologação, responsáveis precisam confirmar origem, necessidade de retenção e acesso ao repositório/artefatos/backups. Se dados reais ou credenciais utilizáveis forem confirmados, decidir resposta apropriada e rotação/revogação dos itens afetados. Aprovar fixtures sintéticas e política de versionamento; inventariar histórico e cópias distribuídas em ambiente controlado. Exclusão de arquivos, remoção do índice, reescrita de histórico e qualquer force push exigem autorização específica; nada disso foi executado.

## Comandos e resultados desta etapa

Todos foram executados via PDM instalado, runner revisado em leitura, SQLite descartável e sockets Python bloqueados:

```powershell
pdm run python scripts/audit_b54.py check
pdm run python scripts/audit_b54.py makemigrations --check --dry-run
pdm run python scripts/audit_b54.py showmigrations --plan
pdm run python scripts/audit_b54.py --production check --deploy
pdm run python scripts/audit_b54.py test --noinput
pdm run python scripts/audit_b54.py test core.tests.test_security_b54 core.tests.test_authentication core.test_google_auth core.tests.test_profiles_portfolios core.tests.test_empresa_perfil core.tests.test_notificacoes --noinput
pdm run python scripts/audit_b54_artifacts.py
pdm run ruff check core/tests/test_security_b54.py
pdm run ruff format --check core/tests/test_security_b54.py
git diff --check
git diff --stat
git status --short
```

| Verificação | Resultado |
|---|---|
| Suíte integral, processo único | **270 testes, 268 sem erro, dois erros conhecidos B45, exit 1** |
| Regressão selecionada | **120/120 aprovados**, incluindo 22 testes B54 e os módulos existentes selecionados |
| check | exit 0, nenhuma questão |
| makemigrations --check --dry-run | exit 0, nenhuma alteração detectada |
| showmigrations --plan | exit 0, grafo até core.0022_empresa_perfil em banco novo |
| check --deploy sintético | exit 0 com 12 avisos: W004/W008 de segurança e dez de schema |
| Ruff check e format check | exit 0 |

A execução integral foi repetida somente para obter o resumo final que havia sido truncado pelo limite de saída; manteve os dois erros e nenhuma aprovação foi inferida da execução parcial. Erros: decisões concorrentes e criação simultânea de candidatura/notificação em `test_notificacoes`, ambos na preparação por ausência de `core_freelance.modalidade` após o teste histórico B45. A execução isolada desses cenários permanece aprovada dentro dos 120 testes. Não foram pulados testes.

Os 12 avisos seguem separados: W004/HSTS e W008/redirect dependem da borda TLS/proxy; sete W001 e três W002 são diagnósticos de schema. Cookies Secure em PRODUCTION continuam presentes. Não houve habilitação de HSTS/redirect nem carregamento da configuração real. Staticfiles ausente no ambiente de teste segue como aviso preexistente.

## Arquivos e veredito

Alterações desta etapa: somente `core/tests/test_security_b54.py` (três testes), este documento novo e link de atualização em `docs/FEAT-54-revisao-final.md`. Nenhum arquivo de runtime, migration, teste B45 ou artefato de dados foi alterado. Os arquivos novos precisam ser revisados além do diff comum enquanto não rastreados. Nenhum staging, commit, push, merge, rebase ou deploy realizado.

**PR #22: NÃO PRONTO para aprovação de merge pelo critério solicitado**, pois a suíte não atinge exit 0 e depende do #23. Ausência de conflito Git não altera esse resultado.

**Sistema: não liberado para produção/homologação final.** B43 deve repetir a suíte após integração autorizada da dependência, validar reautenticação no cliente, decidir restrição de destino/egress das fotos e tratamento de dados versionados, além de PostgreSQL, TLS/proxy/origens, storage privado/URLs conhecidas, rate limits, logs e scan atualizado de dependências. Permanecem riscos de objetos órfãos entre banco/storage e timeout sem prazo total de download; não foram apresentados como resolvidos.
