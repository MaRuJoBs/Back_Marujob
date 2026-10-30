# FEAT-38 — Favoritos por usuário

Favoritos relacionam `User` a `Freelance` no app `core`. Não copiam os dados da
oportunidade. A constraint `favorito_usuario_oportunidade_unico` impede duplicidade
no banco, inclusive sob concorrência. `get_or_create` reutiliza registros existentes.
A exclusão do usuário ou da oportunidade remove os respectivos favoritos por
`CASCADE`. Excluir um favorito não exclui a oportunidade.

## Autenticação

Todas as operações exigem o JWT já utilizado pelo backend:

```http
Authorization: Bearer <access>
Content-Type: application/json
```

O token é obtido pelo login existente (`POST /api/token/`, com `email` e `password`).
O proprietário sempre vem de `request.user`. Campos extras como `usuario` são
ignorados pelo serializer e nunca definem a propriedade. A resposta não expõe
dados do proprietário.

## Endpoints

| Método | URL | Finalidade | Sucesso |
|---|---|---|---|
| GET | `/api/favoritos/` | Listar favoritos da conta autenticada | 200 |
| POST | `/api/favoritos/` | Adicionar ou recuperar favorito existente | 201 ou 200 |
| DELETE | `/api/favoritos/{id}/` | Excluir favorito da conta autenticada | 204 |

### Adicionar

`POST /api/favoritos/`

Campo obrigatório: `oportunidade`, ID inteiro de um `Freelance` existente.

```json
{"oportunidade": 15}
```

Exemplo de resposta (IDs, valores e datas ilustrativos):

```json
{
  "id": 8,
  "oportunidade": 15,
  "oportunidade_detalhes": {
    "id": 15,
    "titulo": "Criação de identidade visual",
    "descricao": "Desenvolver identidade visual",
    "tag": "Design",
    "preco": "500.00",
    "tempo": "5 dias"
  },
  "criado_em": "2026-10-30T10:00:00-03:00"
}
```

`oportunidade_detalhes` reutiliza `FreelanceSerializer`. `id` e `criado_em` são
somente leitura. Na primeira inclusão, retorna **201**. Repetições retornam **200**
com o mesmo favorito, sem alterar a data ou criar registros adicionais.

Erros: **400** para oportunidade ausente, nula, inválida ou inexistente; **401**
para ausência de credenciais ou JWT inválido/expirado. Erros de campo usam o formato
DRF `{"oportunidade": ["mensagem de validação"]}`; o texto depende da validação.

### Listar e identificar oportunidades favoritadas

`GET /api/favoritos/` não exige corpo nem ID de usuário.

Parâmetro opcional: `page`, número da página. A paginação padrão do projeto retorna
10 itens por página, ordenados por criação mais recente, com desempate pelo ID.

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 8,
      "oportunidade": 15,
      "oportunidade_detalhes": {
        "id": 15,
        "titulo": "Criação de identidade visual",
        "descricao": "Desenvolver identidade visual",
        "tag": "Design",
        "preco": "500.00",
        "tempo": "5 dias"
      },
      "criado_em": "2026-10-30T10:00:00-03:00"
    }
  ]
}
```

Sem favoritos:

```json
{"count": 0, "next": null, "previous": null, "results": []}
```

Erros: **401** sem autenticação válida; **404** para página inexistente.

Não há endpoint extra de status nem campo novo nas oportunidades. O frontend pode
construir um mapa `oportunidade → id do favorito` com a listagem. Deve percorrer
todas as páginas seguindo `next` antes de concluir que uma oportunidade não está
favoritada. IDs de usuários em query parameters não alteram o filtro da conta.

### Remover

`DELETE /api/favoritos/8/`, sem corpo. O ID é o **ID do favorito**, não da oportunidade.

Sucesso: **204**, sem corpo. Favorito inexistente ou pertencente a outra conta:
**404**, com erro no campo `detail`. Sem JWT válido: **401**. Uma segunda exclusão
do mesmo ID retorna **404**. A oportunidade permanece no banco.

Não são implementados GET de detalhe, PUT ou PATCH; esses métodos retornam **405**
quando autenticados no caminho de detalhe.

## Integração futura

1. Após autenticar, carregar a listagem da conta e percorrer as páginas.
2. Ao favoritar, enviar o ID da oportunidade. Em 201 ou 200, guardar o favorito
   retornado e atualizar a interface.
3. Ao desfavoritar, enviar DELETE usando o ID do favorito. Em 204, removê-lo do
   estado da interface.
4. Ao trocar de conta ou sair, limpar o estado local da interface; isso não remove
   os registros persistidos. Um novo login, inclusive em outro dispositivo,
   recupera os favoritos da mesma conta.
5. Tratar falhas da API antes de confirmar a mudança visual como persistida.

O conteúdo atual de `localStorage` **não é migrado automaticamente**. Uma eventual
importação exige decisão explícita da equipe e integração posterior no frontend.

## Migration e validação isolada

Migration nova: `core/migrations/0014_favorito.py`. Cria somente o model `Favorito`,
seus relacionamentos e constraint. Não altera migrations antigas ou tabelas de
usuários/oportunidades. Sua aplicação em produção fica a cargo do fluxo autorizado
da equipe; esta entrega não executa migrations no banco da aplicação.

Com as dependências de execução do backend disponíveis:

```bash
python manage.py test core.tests.test_favoritos --settings=core.tests.settings -v 2
python manage.py makemigrations core --check --dry-run --settings=core.tests.settings
python manage.py check --settings=core.tests.settings
```

`core.tests.settings` força SQLite em memória antes de importar as configurações
da aplicação, usa chave exclusiva de testes e não utiliza o `DATABASE_URL` externo.
O test runner aplica as migrations somente no banco de testes em memória.

Os testes cobrem autenticação, criação, proprietário forjado, dados inválidos,
duplicidade via API e banco, listas independentes, paginação, exclusão e CASCADE.
Também autenticam por JWT em dois clientes, retiram as credenciais do primeiro e
confirmam a recuperação dos favoritos no segundo. O teste de constraint comprova
a proteção do banco; não é um teste de carga com requisições paralelas.

## Resultado da validação desta entrega

- 16 métodos de teste criados, executados e aprovados; nenhuma falha.
- Migration `0014_favorito` aplicada com sucesso pelo test runner em SQLite em memória.
- `makemigrations core --check --dry-run`: nenhuma alteração de model sem migration.
- `check`: nenhum problema encontrado.
- Aviso não impeditivo do WhiteNoise: diretório `staticfiles/` ausente no ambiente
  de testes. Não foi criada infraestrutura de arquivos estáticos para esta FEAT.
- Ambiente temporário: Python 3.14, Django 5.2.12, DRF 3.16.1 e SimpleJWT 5.5.1.
  Dependências de execução necessárias foram instaladas em `/tmp/feat38-venv`, sem
  alterar `requirements.txt`, `pyproject.toml` ou o lockfile. Bibliotecas auxiliares
  foram resolvidas nesse ambiente, sem reproduzir integralmente o lockfile.
- Os três comandos acima foram executados com o interpretador
  `/tmp/feat38-venv/bin/python` no lugar de `python`.
- Nenhum teste em PostgreSQL, teste de carga concorrente ou acesso ao banco da
  aplicação foi executado. A proteção contra duplicatas foi validada pela API e
  por uma inserção duplicada direta, rejeitada pela constraint do banco de testes.
