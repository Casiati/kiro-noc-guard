---
name: knowledge-builder
description: Base de Conhecimento compartilhada do NOC (runbooks Markdown sincronizados com S3) — busca de incidentes anteriores antes de investigar e registro do achado ao concluir.
---

# knowledge-builder

Script: `~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py`

## Objetivo

Evitar investigações duplicadas: antes de investigar um alerta, buscar registros anteriores
do mesmo recurso; ao concluir (3+ comandos de leitura e conclusão explícita), registrar
causa raiz, evidências e recomendação para a equipe.

## Parâmetros

| Parâmetro | Obrigatório | Descrição |
|---|---|---|
| `--bucket` | sim | Bucket S3 da KB (3-63 caracteres, validado). |
| `--action` | sim | `search`, `add` ou `sync`. |
| `--query` | `search` | Termo pesquisado (case-insensitive) nos `.md`. |
| `--alert` | `add` | Nome curto do alerta/tópico (vira o nome do arquivo). |
| `--content` | `add` | Resumo: causa raiz, evidências, recomendação. |
| `--kb-profile` | não | Profile da conta do bucket (independente do profile do incidente). Também via `KB_PROFILE`. |

## Exemplos

```bash
python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket <bucket> --kb-profile <profile> --action search --query "rds-prod HighCPU"
python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket <bucket> --kb-profile <profile> --action add --alert "rds-prod HighCPU" --content "Causa: job noturno..."
```

## Efeitos colaterais (declarados)

Esta é a única skill que grava dados, e somente no escopo da própria KB:

- Cache local em `~/.kiro/noc-guard/kb/` (append do registro em `<alerta>.md`).
- `aws s3 sync` do cache para o bucket da KB (`add`/`sync`) — nunca em contas de clientes.

Essas gravações estão marcadas no código com `# noc-guard: allow-mutation` e são auditadas
por `scripts/validate_skills.py`.

## Códigos de retorno

`0` sucesso; `1` argumento inválido; `2` registro salvo só localmente (falha no envio ao S3).
