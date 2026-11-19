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
| `--query` | `search` | Um ou mais termos. Todos devem aparecer no arquivo, em qualquer ordem (AND); acentos e maiúsculas são ignorados. |
| `--alert` | `add` | Nome curto do alerta/tópico (vira o nome do arquivo). |
| `--content` | `add` | Resumo: causa raiz, evidências, recomendação. |
| `--kb-profile` | não | Profile da conta do bucket (independente do profile do incidente). Também via `KB_PROFILE`. |

## Exemplos

```bash
python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket <bucket> --kb-profile <profile> --action search --query "rds-prod HighCPU"
python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket <bucket> --kb-profile <profile> --action add --alert "rds-prod HighCPU" --content "Causa: job noturno..."
```

### Como a busca funciona

- A consulta é separada em palavras. Um arquivo só entra se contiver **todas** (nome do arquivo + conteúdo), em qualquer ordem e posição.
- Se nenhum arquivo contém todas, a busca repete com **qualquer** palavra e avisa `Correspondência PARCIAL`, indicando `faltou: <termos>` em cada arquivo.
- Ordenação: mais termos casados primeiro, depois o registro mais recente. Cada arquivo mostra `[N/M termos; último registro: <data>]` e só os blocos que casam (máx. 3 por arquivo, 10 arquivos).
- `TRUNCADO` significa resultado incompleto: refine com um termo específico (ID do recurso, nome da instância) antes de concluir que não há mais registros.
- "Nenhum registro contém todos os termos" **não** prova que a KB não tem o assunto: tente termos isolados (ID do recurso, nome da instância, tipo de alerta).

## Efeitos colaterais (declarados)

Esta é a única skill que grava dados, e somente no escopo da própria KB:

- Cache local em `~/.kiro/noc-guard/kb/` (append do registro em `<alerta>.md`).
- `aws s3 sync` do cache para o bucket da KB (`add`/`sync`) — nunca em contas de clientes.

Essas gravações estão marcadas no código com `# noc-guard: allow-mutation` e são auditadas
por `scripts/validate_skills.py`.

## Códigos de retorno

`0` sucesso; `1` argumento inválido; `2` registro salvo só localmente (falha no envio ao S3).
