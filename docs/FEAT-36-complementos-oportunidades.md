# Campos complementares das oportunidades — PR complementar

## Base e diagnóstico

Trabalho na branch `FEAT-41`, conforme solicitado. Como a feature original já foi
integrada, a branch avançou linearmente até `origin/DEV` (`ff54267`) antes das
alterações, sem reescrever commits ou criar merge. A base inclui filtros de
oportunidades da FEAT-37 e notificações/decisões da FEAT-44. O usuário autorizou
commit, push e PR complementar após implementação e validação.

`core.png` e `db.sqlite3` já estavam modificados e são excluídos desta entrega.
O banco local estava em uso por outro processo: todas as verificações/testes usam
`core.tests.settings`, com banco exclusivamente em memória. Não foram usados dados
de produção, credenciais reais ou migrations no banco local/publicado.

Não foram encontrados AGENTS.md aplicáveis no repositório/ancestrais verificados.
Foi consultado somente o documento frontend indicado,
`Front_marujob/docs/FEAT-36-contrato-complementos.md`, em modo de leitura.
Nenhum arquivo do frontend foi modificado. O contrato implementado corresponde
aos nomes, opções e formatos solicitados, sem divergência necessária no frontend.

Antes, `Freelance` continha apenas `id`, `empresa`, `titulo`, `descricao`, `tag`,
`preco` e `tempo`. O serializer usava `fields='__all__'`, de modo que propriedades
complementares desconhecidas não persistiam. A view já fornece propriedade pelo
usuário autenticado, consultas paginadas e permissões corretas; não foi necessário
alterá-la, nem as permissões, autenticação ou paginação.

## Arquivos

| Arquivo | Alteração |
| --- | --- |
| `core/models/freelance.py` | Oito campos opcionais, escolhas exatas e validadores monetários |
| `core/serializers/freelance.py` | Exposição de todos os campos, data ISO estrita, decimais como strings e validação do estado final da faixa |
| `core/migrations/0020_freelance_complementos.py` | Oito AddField sobre a folha `0019_notificacoes_retroativas` |
| `core/tests/test_freelance_complementos.py` | 19 testes de API e migração com persistência real no banco de teste |
| `core/tests/test_opportunity_queries.py` | Atualiza o conjunto exato de chaves esperado, preservando testes de busca/paginação; alinha lint ao estilo unittest do projeto |
| `core/tests/test_notificacoes.py` | Restaura a folha atual após o teste de backfill, em vez de deixar o banco de testes em 0019 |
| `docs/FEAT-36-complementos-oportunidades.md` | Contrato, validações, migração e resultados |

Nenhum endpoint, relacionamento, CASCADE, regra de retenção ou obrigação dos campos
anteriores foi alterado. Os serializers compartilhados de oportunidade também
passam a incluir os campos novos em detalhes de favoritos/candidaturas, de forma
aditiva, sem renomear ou remover campos anteriores.

## Contrato final

| Campo | Regra |
| --- | --- |
| `requisitos` | Texto opcional, até 1000 caracteres, padrão `""` |
| `beneficios` | Texto opcional, até 1000 caracteres, padrão `""` |
| `tipo_contratacao` | `CLT`, `PJ`, `Autônomo`, `Temporário`, `Estágio`, `Outros` ou `""` |
| `nivel_experiencia` | `Iniciante`, `Júnior`, `Pleno`, `Sênior`, `Especialista` ou `""` |
| `jornada_trabalho` | Texto opcional, até 100 caracteres, padrão `""` |
| `data_publicacao` | Data gravável `YYYY-MM-DD` ou null; sem data automática |
| `salario_minimo` | Decimal não negativo, até 8 dígitos inteiros e 2 decimais, ou null |
| `salario_maximo` | Mesmo limite, maior ou igual ao mínimo, ou null |

Textos opcionais aceitam `""`; não aceitam null. Requisitos, benefícios e jornada
preservam espaços e quebras de linha enviados, sem truncar ou alterar o texto.
Opções são exatas, incluindo caixa e acentos; valores desconhecidos são rejeitados.
Datas compactas, datetimes, datas inexistentes ou sem o formato exato são rejeitados.

`preco` continua obrigatório como pagamento único e mantém a validação não negativa
da FEAT-34. A faixa salarial não o substitui. `tempo` permanece texto da duração
estimada e não é convertido em jornada. O prefixo de modalidade em `descricao`
é mantido, inclusive suas quebras de linha e limite existente de 200 caracteres.

As respostas de POST 201, PATCH/PUT 200, GET detalhe e cada item da listagem
contêm todos os 15 campos. Valores monetários são strings com duas casas decimais;
campos monetários ausentes retornam null. Exemplo de POST/representação completa:

```json
{
  "id":12,
  "empresa":3,
  "titulo":"Desenvolver uma página",
  "descricao":"Modalidade: Remoto\n\nDesenvolvimento de uma página responsiva.",
  "tag":"Desenvolvimento Web",
  "preco":"1500.00",
  "tempo":"40",
  "requisitos":"Conhecimento em Vue e acessibilidade.",
  "beneficios":"Horário flexível.",
  "tipo_contratacao":"PJ",
  "nivel_experiencia":"Pleno",
  "jornada_trabalho":"Segunda a sexta, das 9h às 18h",
  "data_publicacao":"2026-10-30",
  "salario_minimo":"2000.50",
  "salario_maximo":"3500.00"
}
```

No POST, enviar os campos acima sem `id`/`empresa`, que pertencem ao backend.
Omitir todos os oito campos novos continua válido; a resposta traz textos `""`,
data null e faixa null, inclusive para oportunidades anteriores à migration.

GET `/api/freelances/` mantém `count`, `next`, `previous`, `results`, paginação de
10 registros e filtros existentes. Cada item de `results` tem a representação
completa. Nenhum novo filtro ou endpoint foi introduzido.

## PATCH e erros

Campo omitido preserva o valor atual; texto `""` limpa; data null limpa. Exemplo:

```json
{"beneficios":"","data_publicacao":null}
```

Para remover a faixa, enviar ambos:

```json
{"salario_minimo":null,"salario_maximo":null}
```

A validação combina valores enviados e valores já persistidos. Assim, alterar
apenas o mínimo para valor acima do máximo existente é rejeitado; limpar apenas
um extremo de faixa existente também é rejeitado. Ambos nulos representam ausência;
ambos iguais são permitidos, inclusive zero. Não há arredondamento silencioso de
entradas com mais de duas casas: retornam 400.

Erros são associados aos nomes exatos dos campos, por exemplo:

```json
{"salario_maximo":["O valor máximo deve ser maior ou igual ao mínimo."]}
```

Faixa incompleta aponta o campo que falta:

```json
{"salario_minimo":["Preencha os dois extremos da faixa salarial ou deixe ambos nulos."]}
```

Texto acima do limite, opção inválida, data inválida, valor negativo ou precisão
inválida também retornam 400 por campo. JWT ausente/inválido continua 401;
escrita de freelancer/empresa não proprietária continua 403. `empresa` enviado em
POST/PATCH/PUT é ignorado com segurança, sem transferência de propriedade.

## Migration e aplicação

`0020_freelance_complementos` depende de `0019_notificacoes_retroativas` e contém
apenas oito AddField. Textos antigos recebem string vazia; data e valores recebem
null. Não há RunPython com dados fictícios, alteração de IDs, data inventada,
exclusão de oportunidades ou mudança de relacionamentos.

O teste de migration cria uma vaga histórica no estado 0019, com candidatura
aprovada, favorito e notificação lida. Aplica 0020 apenas no banco temporário e
verifica valores antigos, vínculos, status e leitura preservados, além dos novos
campos vazios/nulos. SQLite pode reconstruir internamente a tabela para AddField,
conforme o SQL gerado pelo Django; isso não recria o banco e os dados foram
preservados no teste. Não houve execução desse SQL no banco local ou em produção.

Após revisão e autorização no ambiente apropriado, com configurações normais:

```text
pdm run python manage.py migrate --plan
pdm run python manage.py migrate
```

Não usar `--settings=core.tests.settings` para aplicar no banco real: essa
configuração é exclusivamente em memória. Evitar o atalho `pdm run migrate`, que
também executa hooks de geração de migrations/diagrama configurados no projeto.
Coordenar a aplicação antes de executar o backend novo contra o banco persistente.

## Testes e verificações

A primeira linha de base foi bloqueada por `ModuleNotFoundError: phonenumbers`.
A dependência já estava declarada na DEV: `pdm sync` instalou somente esse pacote,
sem alterar pyproject, lockfile ou requirements. A linha de base então passou com
**155 testes**. A validação final passou com **174 testes em 8,834 s, zero falhas**.

Os 19 testes adicionais cobrem criação antiga/completa, persistência, representações
POST/PATCH/detalhe/lista, paginação, datas selecionadas, textos exatos, limpeza,
limites, todas as opções, extremos nulos/parciais, negativos, invertidos e precisão,
PATCH considerando estado armazenado, JWT e propriedade, integração com
candidaturas/favoritos/notificações e preservação por migration histórica.
Nenhum teste legítimo foi removido, desabilitado ou enfraquecido. A asserção de
chaves anterior foi ampliada para exigir os novos campos também.

Comandos executados com banco isolado:

```text
pdm run python manage.py test --settings=core.tests.settings
pdm run python manage.py test core.tests.test_freelance_complementos --settings=core.tests.settings
pdm run python manage.py check --settings=core.tests.settings
pdm run python manage.py makemigrations --check --dry-run --settings=core.tests.settings
pdm run python manage.py migrate --plan --settings=core.tests.settings
pdm run python manage.py sqlmigrate core 0020 --settings=core.tests.settings
pdm run python manage.py spectacular --validate --file .schema-complementos.yaml --settings=core.tests.settings
pdm run ruff check core/models/freelance.py core/serializers/freelance.py core/tests/test_freelance_complementos.py core/tests/test_opportunity_queries.py core/tests/test_notificacoes.py
pdm run ruff format --check core/models/freelance.py core/serializers/freelance.py core/tests/test_freelance_complementos.py core/tests/test_opportunity_queries.py core/tests/test_notificacoes.py
git diff --check
```

Django check passou e não há mudanças de model sem migration. Plano e SQL foram
inspecionados em memória; o plano nesse banco vazio inclui o histórico completo,
não representa o estado de aplicação do banco local. Ruff e formatação passaram
nos cinco arquivos Python de implementação/testes modificados. Diagnósticos de
estilo unittest preexistentes no teste de consultas foram alinhados à convenção
dos demais testes, sem mudar suas verificações funcionais.

O aviso preexistente de diretório `staticfiles` ausente não impede a suíte.
Logs de rejeição de tokens Google vêm de mocks dos testes e não contêm tokens reais.
O arquivo temporário de schema é removido após a inspeção e não integra o commit.

`spectacular --validate` terminou com código 0 e gerou o documento, mas registrou
12 warnings (7 únicos) e 12 erros de documentação (3 únicos). Os erros dizem
respeito à ausência de serializer de schema em GoogleLoginView, DefinirSenhaView
e TrocarSenhaView; os avisos envolvem parâmetros de rotas, tipos de métodos e
componentes Nested. Essas views/serializers não foram alterados por esta entrega.
Portanto, o schema global não está livre de diagnósticos. Os oito campos foram
conferidos no componente Freelance, incluindo data com formato date e salários
como strings. Corrigir a documentação global de autenticação é pendência separada,
sem impedir a persistência/API validada pelos testes desta tarefa.

## Frontend e pendências

Não há divergência com o documento frontend consultado: manter nomes e opções
exatos, enviar data `YYYY-MM-DD`, limpar faixa com dois nulls e consumir os campos
na resposta persistida. A tolerância frontend a datetime na leitura não exige que
o backend produza datetime: o contrato entregue é data sem fuso.

Não há alteração necessária de Vue para este contrato. O frontend não foi
executado nesta tarefa. A aplicação real da migration e a homologação conjunta
continuam pendentes do ambiente responsável; não houve deploy. `core.png` e
`db.sqlite3` permanecem alterações locais preexistentes, fora do commit/PR.
