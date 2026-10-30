# FEAT-37 — Consulta de oportunidades

## Contrato disponível

Todas as requisições exigem `Authorization: Bearer <access>` (JWT).
Empresas e freelancers autenticados podem consultar todas as oportunidades.
As regras da FEAT-34 continuam: criação somente por empresa; edição e exclusão
somente pela empresa proprietária. Favoritos e serializer compartilhado não mudaram.

- `GET /api/freelances/`: listagem paginada, 10 itens, ordenação crescente por `id`.
- `GET /api/freelances/{id}/`: objeto de detalhes, sem envelope de paginação.
- POST na coleção, PUT/PATCH/DELETE no detalhe: CRUD existente, sem mudanças.

| Parâmetro da listagem | Comportamento |
|---|---|
| `search` | SearchFilter do DRF sobre `titulo`: pesquisa parcial, sem distinção de caixa conforme suporte do banco. Termos separados por espaço/vírgula são combinados com AND; aspas agrupam uma expressão |
| `tag` | Igualdade do texto completo, sem distinção de caixa conforme suporte do banco; espaços externos removidos |
| `preco_min` | Limite inferior inclusivo |
| `preco_max` | Limite superior inclusivo |
| `page` | Número da página; padrão 1, DRF também aceita `last` |

Os preços seguem o campo existente: até 10 dígitos totais, 2 casas decimais,
mínimo zero e máximo 99999999.99. Vazio, texto não numérico, valores não finitos,
negativos, precisão excessiva e mínimo maior que máximo retornam 400.
Ausência de limites não restringe preço. `search` e `tag` vazios não restringem.
Parâmetros desconhecidos são ignorados. Use um valor por parâmetro.
Os parâmetros de consulta restringem somente a listagem, sem afetar o CRUD/detalhe.
Filtros e pesquisa são aplicados no banco antes da paginação.

`search` aceita no máximo **200 caracteres** no valor recebido (incluindo espaços
e aspas) e **20 termos**, contados pelo próprio parser do SearchFilter instalado.
Expressões entre aspas são contadas conforme esse parser, sem separar manualmente
as palavras internas. O filtro usa os mesmos termos retornados pela validação.
Esses limites mantêm consultas usuais e restringem a quantidade de condições SQL,
evitando a expressão excessiva reproduzida no SQLite com 1.100 termos.
Valores vazios ou somente com espaços, dentro do limite, não restringem resultados.
Exceder qualquer limite retorna HTTP 400 antes das consultas de contagem/paginação:

```json
{"search":["A pesquisa deve ter no máximo 200 caracteres."]}
```

Ou, quando o comprimento é válido mas há mais de 20 termos:

```json
{"search":["A pesquisa deve ter no máximo 20 termos."]}
```

Exemplo:

```http
GET /api/freelances/?search=designer&tag=design&preco_min=100&preco_max=500&page=2
Authorization: Bearer <access>
```

## Formatos JSON

Exemplos com IDs e conteúdo ilustrativos, usando os campos reais do contrato.
Uma coleção com apenas uma oportunidade:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "titulo": "Designer",
      "descricao": null,
      "tag": "design",
      "preco": "100.00",
      "tempo": "1 dia",
      "empresa": 2
    }
  ]
}
```

Em uma coleção com 11 itens, a primeira página contém 10 objetos e:
`count: 11`, `previous: null`,
`next: "http://testserver/api/freelances/?page=2"` no host de testes.
A segunda contém um objeto, `next: null` e
`previous: "http://testserver/api/freelances/"`.
Em produção os links usam o host da requisição e preservam pesquisa/filtros.

Detalhe (200):

```json
{"id":1,"titulo":"Designer","descricao":null,"tag":"design","preco":"100.00","tempo":"1 dia","empresa":2}
```

`empresa` é apenas o ID, aceita null para registros legados; dados privados da
conta não são incluídos. `descricao` e `tag` também aceitam null. Preço é string decimal.
Sem resultados (200):

```json
{"count":0,"next":null,"previous":null,"results":[]}
```

Intervalo invertido (400):

```json
{"preco_max":["Deve ser maior ou igual a preco_min."]}
```

Outros erros de filtros usam listas de mensagens por parâmetro, por exemplo
`{"preco_min":["..."]}`. A redação padrão do DRF depende da localização.
401 indica JWT ausente/inválido; 403 indica escrita sem permissão;
404 indica ID inexistente ou página inválida. Esses erros usam `{"detail":"..."}`.
Páginas zero, negativas, não numéricas e fora do intervalo retornam 404.

## Limitações e compatibilidade

`tag` é texto livre, não uma categoria controlada. O frontend pode filtrar por
esse campo imediatamente, mas sua equivalência a categoria exige definição da
equipe. Não existem modalidade, experiência, jornada ou tipo de contratação.
`tempo` não tem semântica de jornada confirmada. Nenhum filtro para esses conceitos
foi criado. Moeda e periodicidade de preço também não estão definidas no model.

Listagem, detalhe, busca, tag, intervalo de preço e paginação combinados estão
disponíveis sem mudanças no frontend ou nas respostas usadas pela FEAT-38.
Não foram alterados models, serializers, permissões, rotas ou migrations.
Nenhuma migration foi necessária para implementar pesquisa, filtros e paginação.

## Validação isolada

Configuração `core.tests.settings`: SQLite em memória, sem banco da aplicação.
PDM disponível, mas o interpretador salvo estava indisponível e o `.venv` local
não contém Django. O apontamento `.pdm-python` foi preservado no estado original.
Usado `/tmp/feat38-venv/bin/python`, sem instalar dependências ou mudar lockfile.
O ambiente não reproduz integralmente o lockfile. Cloudinary recebe credenciais
fictícias no processo para permitir a importação dos testes existentes de perfil;
as chamadas de armazenamento desses testes são simuladas.

```bash
/tmp/feat38-venv/bin/python -B manage.py check --settings=core.tests.settings
/tmp/feat38-venv/bin/python -B manage.py makemigrations --check --dry-run --settings=core.tests.settings
CLOUDINARY_CLOUD_NAME=test CLOUDINARY_API_KEY=test CLOUDINARY_API_SECRET=test /tmp/feat38-venv/bin/python -B manage.py test --settings=core.tests.settings -v 1
```

A validação não comprova comportamento em PostgreSQL; em particular, comparação
sem distinção de caixa depende da collation e do banco. Não houve migrations
no banco da aplicação, alteração de dados reais ou operações de integração Git.
No SQLite usado nos testes, `árvore` não encontra `Árvore`, e `área` não encontra
a tag `ÁREA`: a comparação sem distinção de caixa tem limitações para Unicode.
Esta correção não implementa normalização Unicode ou remoção de acentos.

Resultado anterior à correção de robustez: 81 testes preexistentes e 10 novos, total de 91 executados e
aprovados, sem falhas. A primeira tentativa encontrou erro de importação por
configuração Cloudinary ausente; a execução seguinte identificou dois subcasos
de preço vazio, corrigidos antes da execução final. Aviso não impeditivo:
diretório `staticfiles/` ausente. System check sem problemas; nenhuma mudança
de model pendente; grafo sem conflitos, com folha core
`0016_merge_20261030_1516` já existente. `git diff --check` aprovado.

Após a correção de robustez: seis testes de regressão adicionais; 16 testes do
módulo de consultas aprovados na execução direcionada e 97 testes aprovados na
suíte completa (incluindo FEAT-34 e FEAT-38), sem falhas. Os casos excessivos,
incluindo 1.100 termos, verificam HTTP 400 e zero consultas SQL com autenticação
forçada no teste. System check, consistência models/migrations e grafo de
migrations continuam aprovados. Nenhuma migration criada ou aplicada no banco
da aplicação.
