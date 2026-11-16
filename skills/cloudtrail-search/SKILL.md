---
name: cloudtrail-search
description: Busca rápida e somente leitura de eventos de gestão do AWS CloudTrail (lookup-events) para triagem NOC — quem fez o quê, quando e de onde, com saída tabular compacta truncada em 100 linhas.
---

# cloudtrail-search

Script: `~/.kiro/noc-guard/skills/cloudtrail-search/search_trail.py`

## Objetivo

Responder rapidamente "quem alterou o quê, quando e de onde" em uma conta AWS durante um
incidente, usando a API gratuita `cloudtrail:LookupEvents` (90 dias de eventos de gestão,
sem trail/Athena/CloudTrail Lake). A saída é uma tabela de uma linha por evento:

```
Time (UTC) | User | Action | Resource | Status/Error | IP
```

É o ÚNICO caminho permitido para consultar CloudTrail no noc-guard (o steering
`noc-readonly-first` proíbe o `aws cloudtrail lookup-events` direto).

## Quando usar

- Correlacionar um alerta com mudanças recentes (`ModifyDBInstance`, `UpdateService`,
  `AuthorizeSecurityGroupIngress`, `PutBucketPolicy`...).
- Descobrir quem mexeu num recurso específico (`--resource-name`).
- Auditar as ações de um usuário/sessão (`--username`), inclusive sessões
  `botocore-session-*` / sessões de roles assumidas antes do cruzamento de identidade.
- Achar falhas de permissão/limites (`--errors-only`: `AccessDenied`, `ThrottlingException`...).

Não use para: eventos de dados (S3 object-level, Lambda invoke), janelas acima de 90 dias
ou mudanças dentro do Kubernetes (use `logs_search.py k8s-audit`).

## Parâmetros

| Parâmetro | Obrigatório | Padrão | Descrição |
|---|---|---|---|
| `--profile` | sim | — | Profile AWS resolvido pelo `aws-profile-resolver` (ex.: `CLXXX-NOC`). |
| `--region` | não | `us-east-1` | Região consultada (o CloudTrail é regional; eventos globais como IAM ficam em `us-east-1`). |
| `--since` | não | `1h` | Janela relativa: `N` + `m`/`h`/`d` (ex.: `30m`, `6h`, `7d`). Máx. `87600`; a API só guarda 90 dias. |
| `--event-name` | não | — | Filtra por `EventName` (ex.: `TerminateInstances`). |
| `--username` | não | — | Filtra por `Username` (IAM user, nome da sessão da role). |
| `--resource-name` | não | — | Filtra por `ResourceName` (ID/ARN/nome do recurso). |
| `--errors-only` | não | off | Mostra só eventos com `errorCode` (filtro local, após a busca). |

Restrição da API: `--event-name`, `--username` e `--resource-name` são mutuamente
exclusivos (o `LookupEvents` aceita um atributo por vez). Passar mais de um encerra com
exit code 1. Para cruzar critérios, filtre pelo mais seletivo e refine com `grep`.

## Exemplos de triagem

```bash
# O que mudou na última hora na conta?
python3 ~/.kiro/noc-guard/skills/cloudtrail-search/search_trail.py --profile CLXXX-NOC --since 1h

# Quem mexeu nesta instância RDS nas últimas 24h?
python3 ~/.kiro/noc-guard/skills/cloudtrail-search/search_trail.py --profile CLXXX-NOC --region sa-east-1 --since 24h --resource-name db-prod-01

# Alguém encerrou instâncias nos últimos 7 dias?
python3 ~/.kiro/noc-guard/skills/cloudtrail-search/search_trail.py --profile CLXXX-NOC --region sa-east-1 --since 7d --event-name TerminateInstances

# Erros (AccessDenied/Throttling) de uma sessão específica
python3 ~/.kiro/noc-guard/skills/cloudtrail-search/search_trail.py --profile CLXXX-NOC --since 6h --username botocore-session-1700000000 --errors-only

# Refinar a saída sem estourar contexto
python3 ~/.kiro/noc-guard/skills/cloudtrail-search/search_trail.py --profile CLXXX-NOC --since 24h --event-name UpdateService | grep -v Success
```

## Limites de segurança e de tokens

- Somente leitura: usa apenas `cloudtrail:LookupEvents` (boto3 ou, sem boto3, `aws cloudtrail
  lookup-events`). Nada é criado, alterado ou gravado em disco. Custo zero.
- Truncamento defensivo em 100 resultados: ao imprimir o 100º evento o script para e exibe
  `... [Truncated at 100 results to save tokens. Refine filters if you need more.]`.
  Se aparecer, NÃO conclua que não há mais eventos: estreite `--since` ou use um filtro.
- Colunas truncadas (usuário 25, ação 30, recurso 28 caracteres) para manter a saída compacta.
- Eventos malformados são pulados com aviso no stderr; o total pulado é informado ao final.
- `--errors-only` filtra localmente: em janelas longas a paginação pode demorar (a API
  limita ~2 req/s). Prefira combiná-lo com `--event-name`/`--username` ou janela curta.

## Saída e códigos de retorno

- `0`: sucesso (inclusive `No matching events found in the time window.`).
- `1`: argumento inválido, mais de um atributo de filtro, credencial expirada/ausente,
  erro de rede ou AWS CLI ausente (mensagem no stderr).
