---
name: logs-search
description: Consultas somente leitura e de custo zero ao CloudWatch Logs (FilterLogEvents/Describe*) com agregação local compacta — audit e eventos do EKS, logs de aplicação e descoberta de fontes de log, sem Logs Insights.
---

# logs-search

Script: `~/.kiro/noc-guard/skills/logs-search/logs_search.py`

## Objetivo

Substituir o CloudWatch Logs Insights (cobrado por GB) nas triagens NOC usando apenas APIs
gratuitas (`logs:FilterLogEvents`, `logs:DescribeLogGroups`, `logs:DescribeLogStreams`,
`eks:DescribeCluster`) e agregando o resultado localmente para economizar tokens.

## Quando usar

- Primeiro passo em incidente EKS/app numa conta desconhecida: `sources`.
- Mudanças no Kubernetes (deploy, rollout restart, scale, configmap/secret): `k8s-audit`.
- Evolução de Ready/restarts/OOMKilled de pods: `k8s-audit --status`.
- Eventos do Kubernetes sem kubeconfig (Unhealthy, BackOff, FailedScheduling): `k8s-events`.
- Erros/timeout em qualquer log group de aplicação: `logs`.

## Modos e parâmetros principais

| Modo | Parâmetros |
|---|---|
| `sources` | `--cluster`, `--name`, `-n/--namespace`, `--pattern` (repetível) |
| `k8s-audit` | `--cluster` ou `--log-group`, `-n`, `--name`, `--status`, `--resource`, `--verb` |
| `k8s-events` | `--cluster` ou `--log-group`, `-n`, `--name`, `--type Warning|Normal`, `--reason` |
| `logs` | `--log-group` (obrigatório), `--stream-prefix`, `--filter-pattern`, `--all`, `--group-by message|bin|stream|none`, `--bin` |

Comuns: `--profile` (obrigatório), `--region` (`us-east-1`), `--since` (`1h`, máx. `90d`),
`--start`/`--end` (ISO-8601 UTC), `--limit` (40 linhas), `--width` (180 caracteres),
`--timeout` (90 s). Varredura: `--max-events` (3000), `--slice` (6h).

## Exemplos

```bash
python3 ~/.kiro/noc-guard/skills/logs-search/logs_search.py sources --profile CL048-NOC --cluster eks-prod --name api-foo
python3 ~/.kiro/noc-guard/skills/logs-search/logs_search.py k8s-audit --profile CL048-NOC --cluster eks-prod -n production --name api-foo --since 24h
python3 ~/.kiro/noc-guard/skills/logs-search/logs_search.py k8s-events --profile CL048-NOC --cluster eks-prod -n production --name api-foo --since 6h --type Warning
python3 ~/.kiro/noc-guard/skills/logs-search/logs_search.py logs --profile CL048-NOC --log-group /aws/ecs/app --since 3h --filter-pattern '?timeout ?refused' --group-by bin
```

## Limites de segurança e de tokens

- Somente leitura, custo zero, nada gravado em disco.
- Saída limitada por `--limit`/`--width`; leitura limitada por `--max-events` (linha `TRUNCADO`).
- Varredura do mais recente para o mais antigo: a linha `PARCIAL` indica que o início da
  janela NÃO foi lido — não conclua "sem mudanças/erros" para esse trecho.
- `AUDIT INDISPONÍVEL` (exit code 2): resultado vazio NÃO significa ausência de eventos.
