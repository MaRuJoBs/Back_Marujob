# FEAT-34 — Gerenciamento de oportunidades

## Implementação e contrato

O CRUD reutiliza `FreelanceViewSet`, `FreelanceSerializer` e
`CompanyOpportunityPermission`. Não foram alterados endpoints, autenticação,
model ou permissões. Todas as requisições exigem JWT válido:
`Authorization: Bearer <access>`.

| Método | Endpoint | Acesso e resultado |
|---|---|---|
| GET | `/api/freelances/` | Autenticados; 200, paginação de 10 itens, ordenação por ID |
| GET | `/api/freelances/{id}/` | Autenticados; 200 ou 404 |
| POST | `/api/freelances/` | Empresa; 201, proprietário definido por `request.user` |
| PUT | `/api/freelances/{id}/` | Empresa proprietária; 200, campos obrigatórios exigidos |
| PATCH | `/api/freelances/{id}/` | Empresa proprietária; 200, somente campos enviados |
| DELETE | `/api/freelances/{id}/` | Empresa proprietária; 204 |

Listagem retorna `count`, `next`, `previous` e `results`; aceita `page`.
Ausência de autenticação retorna 401. Escrita sem papel ou propriedade retorna
403. Dados inválidos retornam 400 no formato DRF, com erros por campo.
A consulta por ID inexistente retorna 404 para quem tem acesso ao método.

O papel empresarial vem do grupo `Empresa`; freelancer pertence ao grupo
`Usuário` e corresponde a `tipo=usuario`. Contas sem esses grupos ou com ambos
não podem escrever. Grupos administrativos adicionais não retiram um papel
empresarial exclusivo. Não há exceção automática de superusuário.

Todos os autenticados podem consultar vagas de qualquer empresa. Freelancers
não criam, editam ou excluem vagas. Empresas só editam/excluem as próprias.
`empresa` é somente leitura e é ignorado quando enviado pelo cliente; não
permite transferir propriedade em POST, PUT ou PATCH.

| Campo | Regra |
|---|---|
| `id` | Identificador automático, somente leitura |
| `empresa` | ID da conta proprietária ou null; somente leitura |
| `titulo` | Obrigatório em POST/PUT, não vazio, até 100 caracteres |
| `preco` | Obrigatório em POST/PUT, decimal de até 10 dígitos totais e 2 casas; não negativo |
| `tempo` | Obrigatório em POST/PUT, não vazio, até 50 caracteres |
| `descricao` | Opcional, aceita vazio/null, até 200 caracteres |
| `tag` | Opcional, aceita vazio/null, até 50 caracteres; texto livre |

Zero permanece válido. A validação adicional rejeita somente preços negativos;
precisão, formato e limites continuam validados pelo DRF. O formato da resposta
foi preservado. PATCH permite omitir campos obrigatórios na criação.

## Registros antigos e favoritos

O vínculo opcional com empresa já existia. Vagas com `empresa=null` continuam
consultáveis, mas não podem ser alteradas/excluídas pela API. Não há atribuição
automática de proprietário legado. Qualquer tratamento futuro exige evidência
verificável e autorização específica.

Excluir a empresa mantém a vaga e define `empresa=null` (`SET_NULL`). Excluir a
vaga remove os respectivos favoritos (`CASCADE`). A exclusão da empresa não
remove favoritos de outras contas que apontam para a vaga preservada.
O serializer compartilhado em `oportunidade_detalhes` da FEAT-38 mantém o mesmo
contrato e reflete atualizações da oportunidade.

## Migration de união

O Django gerou `0015_merge_0014_favorito_0014_freelance_empresa` com
`makemigrations core --merge --noinput --settings=core.tests.settings`.
Ela depende de `0014_favorito` e `0014_freelance_empresa` e contém zero operações.
Nenhuma migration anterior foi alterada. O grafo passou de duas folhas finais
para uma, sem conflitos. A migration não recria tabelas/campos nem transforma
registros. Foi aplicada somente pelo runner no banco de testes em memória.
Não foi consultado nem alterado o estado do banco da aplicação.

## Testes e validação

Os 20 métodos existentes de `core/tests.py` foram preservados em
`core/tests/test_authentication.py`, removendo a colisão com o pacote
`core/tests/`. O único ajuste de conteúdo foi o caminho relativo de
`app/settings.py`, devido à mudança de diretório.

Foram adicionados 12 métodos em `core/tests/test_freelances.py`, cobrindo detalhe,
ID inexistente, paginação, todos os métodos sem autenticação, preço negativo em
POST/PUT/PATCH, zero e precisão decimal, campos obrigatórios, PATCH, manipulação
de propriedade, vagas legadas, exclusão da empresa e contrato de favoritos.
Os 16 testes da FEAT-38 foram preservados integralmente.

Configuração: `core.tests.settings`, SQLite exclusivamente em memória. Nesta
validação foi utilizado `/tmp/feat38-venv/bin/python` (Python 3.14, Django 5.2.12),
pois o interpretador salvo pelo PDM apontava para um Windows indisponível neste
ambiente. Não houve alteração de dependências, lockfile ou apontamento PDM na
entrega. Esse ambiente não reproduz integralmente o lockfile.

Com esse interpretador, foram executados:

```bash
python -B manage.py check --settings=core.tests.settings
python -B manage.py makemigrations --check --dry-run --settings=core.tests.settings
python -B manage.py test core.tests.test_freelances core.tests.test_authentication core.tests.test_favoritos --settings=core.tests.settings -v 1
python -B manage.py test --settings=core.tests.settings -v 1
```

Resultados: system check sem problemas; nenhuma mudança de model pendente;
grafo inspecionado com `MigrationLoader(None)` sem conexão ao banco, sem
conflitos e com uma única folha no app core. Os 48 testes passaram tanto na
execução dos módulos explícitos quanto na descoberta da suíte completa, sem
falhas ou erros. Aviso não impeditivo: diretório `staticfiles/` ausente.
Não houve testes em PostgreSQL ou execução de migrations no banco da aplicação.

## Definições pendentes da equipe

Modalidade, tipo de contratação, experiência e jornada não foram criados.
Para cada campo, definir nome no contrato, tipo, valores permitidos, unidade
quando aplicável, obrigatoriedade, aceitação de vazio/null e estratégia para
registros antigos. Definir também se `tempo` representa prazo ou jornada e se
`tag` continuará livre ou será uma categoria controlada; não presumir equivalência.

A semântica de `preco` como remuneração ainda precisa de definição de moeda,
periodicidade e eventual faixa salarial. Zero continua permitido até existir
regra diferente. Não há necessidade de novas colunas para o CRUD atual.
