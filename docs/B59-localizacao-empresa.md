# B59 — Localização empresarial com privacidade

Implementação local na branch `B59`, a partir de `origin/DEV`
`46c03137f0ecfb88ec8c83b0e82eca5ea9b64dee`, conferida após fetch em 2026-11-20.
Entrega autorizada pelo usuário para commit, push e abertura de PR para revisão na DEV; sem merge ou deploy.

## 1. Diagnóstico inicial

O [PR backend #21](https://github.com/MaRuJoBs/Back_Marujob/pull/21) já estava integrado à DEV e fornecia
`EmpresaPerfil`, seus campos `cidade`/`uf` e GET/PATCH `/api/empresas/me/`, com autenticação, isolamento
pela empresa do JWT e atualização transacional. UF já usava as 27 escolhas brasileiras de `Freelance`.
Faltavam validação conjunta de cidade/UF, rejeição de tipos malformados, bairro opcional e uma projeção pública limitada.
Não foi localizada implementação B59 nas branches/histórico/PRs pesquisados.

A [F58, PR frontend #102](https://github.com/MaRuJoBs/Front_marujob/pull/102), está integrada e foi consultada
somente para leitura. Sua implementação atual usa GPS com geocodificação reversa no frontend e envia **somente
cidade/UF** ao perfil empresarial. Não oferece busca textual manual nem envia coordenadas à API empresarial.
O payload é parcial e pode ser JSON ou multipart junto do logotipo.

Na abertura, `FEAT-59` estava no mesmo commit da DEV atualizada; foi criada `B59` sem tracking da DEV antes
das edições. Alterações preexistentes em `.pdm-python`, `.vscode/settings.json`, `core.png` e `db.sqlite3`
foram preservadas, inclusive seu estado no índice. Seus hashes foram conferidos após os testes.
Nenhum arquivo Vue, JavaScript, CSS ou do repositório frontend foi alterado.

## 2. Arquivos da entrega

| Arquivo | Finalidade |
| --- | --- |
| `core/models/empresa_perfil.py` | Bairro opcional privado e propriedade `pais`, derivada das UFs brasileiras. |
| `core/migrations/0024_empresaperfil_bairro.py` | Adicionar somente o campo bairro, sem modificar migrations antigas. |
| `core/serializers/empresa_perfil.py` | Validar localização, aceitar país/bairro opcionais e definir serializer público com cidade/UF. |
| `core/views/empresa_perfil.py` | Reutilizar a edição privada e acrescentar a consulta pública somente para leitura. |
| `app/urls.py` | Registrar a única rota pública nova de localização. |
| `core/tests/test_empresa_localizacao_b59.py` | Persistência, novo login, validação, permissões, privacidade, schema e preservação de registros na migration. |
| `core/tests/test_empresa_perfil.py` | Atualizar somente as expectativas dos dois campos adicionais na resposta/schema privados. |
| `docs/B59-localizacao-empresa.md` | Contrato, decisões de privacidade, validação e pendências. |

## 3. Banco e integridade

- `EmpresaPerfil.cidade` e `EmpresaPerfil.uf` são reutilizados, sem cópia para `User` ou outro modelo.
- O único campo de banco novo é `EmpresaPerfil.bairro`: texto opcional, até 100 caracteres, default vazio.
  É necessário para receber bairro quando explicitamente informado e fica restrito ao perfil privado.
- `pais` não é coluna: retorna `BR` quando cidade e uma UF brasileira estão presentes; retorna vazio sem localização
  completa. O contrato aceita somente Brasil, conforme o domínio já adotado pela F58 e pelas UFs existentes.
  Aceitar `pais=BR` confirma esse formato; não comprova a origem física da empresa.
- Não foram criados endereço completo, complemento ou coordenadas. Os campos GPS preexistentes de `User` não
  são copiados, preenchidos nem alterados pelo contrato B59.
- `0024_empresaperfil_bairro` depende da folha `0023_avaliacoes_reputacao` e contém somente `AddField`.
  O teste histórico preserva os campos e a quantidade de perfis/usuários anteriores, preenchendo bairro com vazio.
- A atualização reutiliza a transação e o bloqueio do usuário da B46. A consistência é verificada novamente contra
  o perfil atual após obter esse bloqueio, para não validar um PATCH parcial somente contra uma leitura antiga.

A migration foi testada nos bancos descartáveis e, posteriormente, **aplicada ao SQLite local a pedido explícito
do usuário**, com resultado OK. Foi criado backup consistente em `.cache/b59/` (ignorado pelo Git).
A comparação com o backup confirmou que os dados anteriores de usuários e perfis empresariais foram preservados.
`showmigrations` confirmou a 0024 aplicada e a coluna `bairro` foi conferida no banco. Nenhum banco remoto foi migrado.

## 4. API e exemplos

| Método e endpoint | Acesso e resposta |
| --- | --- |
| GET `/api/empresas/me/` | JWT de empresa ativa e de papel inequívoco; 200 com perfil privado. |
| PATCH `/api/empresas/me/` | Mesma autenticação; 200 com perfil atualizado; cria a linha opcional no primeiro PATCH válido. |
| GET `/api/empresas/{empresa_id}/localizacao/` | Consulta pública sem JWT obrigatório; 200 com somente cidade e UF. |

Os endpoints privados existentes são mantidos. A rota pública é nova porque a B46 não disponibilizava
consulta a outra empresa. Não há novo endpoint de escrita ou de busca/geocodificação.
GET de uma empresa antiga sem perfil não cria linhas; localização ausente retorna strings vazias.

Payload mínimo da F58, com `Authorization: Bearer <access>`:

```http
PATCH /api/empresas/me/
Content-Type: application/json

{"cidade":"Joinville","uf":"SC"}
```

Campos de localização na resposta privada 200, além dos demais campos anteriores do perfil:

```json
{"cidade":"Joinville","uf":"SC","pais":"BR","bairro":""}
```

Para informar bairro privado, opcionalmente:

```json
{"cidade":"Joinville","uf":"SC","pais":"BR","bairro":"Centro"}
```

Consulta pública correspondente:

```http
GET /api/empresas/123/localizacao/
```

```json
{"cidade":"Joinville","uf":"SC"}
```

PATCH parcial preserva campos omitidos. Pode atualizar só a cidade se uma UF válida já estiver salva,
ou só o bairro se a localização básica estiver completa. Ao mudar cidade/UF sem informar bairro, o bairro
antigo é limpo para não vincular um detalhe da localização anterior ao novo local.
Para remover a localização, enviar `{"cidade":"","uf":""}`: bairro é limpo e país passa a vazio.
Também é aceito enviar os quatro campos vazios. Nome ou logotipo podem ser atualizados sem revalidar/reescrever
uma localização legada incompleta que não foi objeto do PATCH.

### Validações e erros

- Cidade: string até 100 caracteres; aceita nomes Unicode, remove espaços nas extremidades e exige ao menos
  uma letra quando preenchida. Números JSON, booleanos, listas, objetos, null, marcação e caracteres de controle
  são rejeitados. Não há confirmação externa da existência da cidade.
- UF: uma das 27 siglas brasileiras existentes, em maiúsculas, sem espaços. Cidade e UF precisam estar
  preenchidas juntas; ambas vazias são uma remoção explícita, compatível com a F58.
- País opcional: `BR`, ou vazio quando a localização completa está ausente. Outros códigos, nomes e null são rejeitados.
- Bairro opcional: string até 100 caracteres ou vazio. Não aceita tipos malformados, null, marcação ou controles;
  bairro preenchido exige cidade/UF. Não há obrigação de informá-lo na F58.
- Um erro não grava parcialmente o nome ou a localização nem cria perfil vazio como efeito colateral.
- Propriedade e campos protegidos continuam determinados pelo servidor. Conforme o contrato anterior, IDs e campos
  desconhecidos/protegidos são ignorados, inclusive GPS; enviar um ID alheio não muda a empresa alvo do JWT.
  Esses campos não integram o payload de localização e não devem ser enviados pela F58.

Exemplo de 400 para cidade sem UF:

```json
{"uf":["Informe a UF junto com a cidade."]}
```

Recurso privado sem JWT válido: 401. Freelancer, conta sem papel ou com papéis ambíguos: 403.
A rota pública retorna 404 para ID ausente, fora do intervalo, freelancer, empresa inativa ou conta administrativa/ambígua.
POST/PUT/PATCH/DELETE na rota pública e POST/PUT/DELETE no perfil privado retornam 405 para o acesso permitido à rota.

## 5. Privacidade

O endpoint público seleciona somente as colunas institucionais cidade/UF e usa serializer dedicado com esses
dois campos. Não consulta nem retorna bairro, país, contato comercial, e-mail, telefone, endereço pessoal,
GPS, senha, tokens ou privilégios. Não copia informações do perfil pessoal para a localização empresarial.

Bairro fica disponível apenas no perfil privado da própria empresa. O JWT determina a proprietária no servidor;
uma empresa não consulta o perfil privado de outra, e freelancers/anônimos não o editam. Nenhum log de endereço
ou coordenadas foi acrescentado. Toda localização é **declarada**, validada apenas quanto a formato e consistência.

## 6. Testes e verificações executados

PDM existente, Django/DRF locais, contas fictícias de empresas A/B e freelancer. O runner da B54 desabilita
`.env`, fixa SQLite em memória e bloqueia conexões externas. Migrações de teste nunca atingem o banco local.

```text
pdm run python scripts/audit_b54.py test core.tests.test_empresa_perfil --noinput
pdm run python scripts/audit_b54.py test core.tests.test_empresa_localizacao_b59 core.tests.test_empresa_perfil --noinput
pdm run python scripts/audit_b54.py test --noinput
pdm run python scripts/audit_b54.py check
pdm run python scripts/audit_b54.py makemigrations --check --dry-run
pdm run python scripts/audit_b54.py showmigrations --plan
```

- Baseline do perfil empresarial: oito testes aprovados antes da implementação.
- B59 e regressões de perfil: **30 testes aprovados**, incluindo 22 novos da B59.
- Suíte completa final: **424 testes aprovados em um único processo, zero falhas, erros ou skips; exit 0;
  47,035 segundos**. Autenticação, perfis, vagas, candidaturas, notificações, avaliações e chat continuam cobertos.
- Django `check`: nenhuma questão; `makemigrations --check --dry-run`: nenhuma alteração detectada.
- `showmigrations --plan`: grafo inclui `0024_empresaperfil_bairro`, sem conflito detectado. A listagem é de banco
  descartável vazio; não representa o estado aplicado do banco local.
- Ruff check e format check: aprovados nos sete arquivos Python da entrega; revisão de whitespace sem erros.

A cobertura inclui os dez cenários pedidos: criação/atualização, leitura persistida em novo login, tipos/formatos
inválidos, isolamento por empresa, freelancer/anônimo recusados, projeção pública sem dados privados e regressões
de endpoints. Coordenadas não são utilizadas pela B59, portanto não há nova validação ou persistência de GPS.
O teste de campos protegidos confirma que coordenadas enviadas ao perfil empresarial não alteram `User`.
Há também teste de PATCH com leitura antiga, migration preservando registros, multipart e allowlist OpenAPI.

## 7. Integração F58

Nenhum ajuste é necessário para a F58 atual: continuar enviando apenas cidade/UF selecionadas em
PATCH `empresas/me/`, com JWT, e reler GET após novo login. A resposta confirma os mesmos campos normalizados;
`pais`/`bairro` são adições opcionais e não alteram os campos que a F58 já compara.
O envio multipart com logotipo continua aceito. Erros 400 devem ser exibidos por campo; 401 exige novo login.

Se houver uma tela futura de país/bairro, enviar `pais=BR` e o bairro somente após informação explícita da empresa.
Uma tela pública deve usar a rota de localização pública e nunca o serializer completo do perfil privado.
Não implementar no frontend desta branch. Busca textual manual ou suporte internacional exigem contrato próprio;
não foram presumidos a partir do título da F58.

## 8. Pendências e limites

- A migration local já foi aplicada e conferida. Aplicar nos demais ambientes somente pelo fluxo autorizado de publicação.
- Homologar o fluxo no backend publicado e, se aplicável, no PostgreSQL real. Os testes HTTP usam o cliente
  em processo do Django; não comprovam infraestrutura ou persistência num servidor externo.
- A existência física do endereço não foi verificada. O backend não chama geocodificador; disponibilidade,
  consentimento do GPS e envio de coordenadas ao geocodificador usado pela F58 pertencem ao frontend/serviço externo.
- Países diferentes de Brasil, endereço completo e coordenadas empresariais não fazem parte deste contrato.
- Avisos preexistentes de schema OpenAPI em outros módulos e `staticfiles` ausente permanecem fora do escopo.
  Não houve refatoração dessas FEATs nem repetição da auditoria de produção B54.

As alterações da B59 são publicadas para revisão em PR pelo fluxo autorizado; não há merge na DEV.
