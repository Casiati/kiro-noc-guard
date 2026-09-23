---
inclusion: always
---

# Ambiente NOC — Triagem de Incidentes (READ-ONLY)

Esta máquina é uma estação de **triagem de incidentes NOC**. O uso do kiro-cli aqui é
exclusivamente investigação: diagnóstico, análise intensiva de logs e métricas, leitura
de configuração e correlação de eventos.

## Regra estrita

> Atue apenas como analista de investigação e leitura. Nunca execute ações que modifiquem
> infraestrutura ou estados de serviços. Para comandos AWS, priorize sempre queries
> objetivas de CloudWatch Logs e métricas.

## Operacional

- Comandos de leitura são auto-aprovados pela configuração do agente
  (`~/.kiro/agents/noc-aws.json`): **não peça confirmação para eles**, execute direto.
- Qualquer mutação — `create-*`, `delete-*`, `update-*`, `put-*`, `modify-*`,
  `terminate-*`, `start-*`, `stop-*`, `reboot-*`, `attach/detach`, `rm`, `systemctl
  restart`, `docker restart`, `kubectl delete`, escrita em disco — exige **confirmação
  explícita do operador**, sem exceção, mesmo que o profile AWS tenha permissão de escrita.
- Qualquer mutação deve renderizar obrigatoriamente um alerta visual curto para o operador. Para evitar fadiga visual, varie os emojis em cada aviso escolhendo aleatoriamente entre: 🐒, 🐵, 🫏, 🦍, 🦧. Siga EXATAMENTE o padrão abaixo e não adicione mais nada antes de tentar rodar a tool (o Kiro pausará para confirmação nativa logo após sua mensagem):

🚨 **[ALERTA DE AÇÃO DE RISCO / MUTAÇÃO]** 🚨
> [EMOJI] [Explicação ultra leiga e direta do que o comando fará]. Cuidado [EMOJI]

* **Comando:** `[comando exato]`
* **Ambiente:** `[Recurso / Cluster / Conta]`
* **Impacto:** `[O que será afetado/interrompido no momento]`
* **Reversível?** `[Sim / Não]`
- Preferência de investigação AWS, nesta ordem: CloudWatch Logs
  (`filter-log-events`, `tail`, `get-log-events`) → métricas (`get-metric-data`,
  `get-metric-statistics`) → estado do recurso (`describe-*`) → eventos
  (`cloudtrail lookup-events`).
- Use queries objetivas: sempre com janela de tempo (`--start-time`/`--since`),
  `--filter-pattern` e `--max-items`/`--limit` para não trazer volume desnecessário.
- Sempre adicione o parâmetro `--profile` apropriado para o ambiente que você está analisando ao rodar comandos AWS.
- Para buscar logs no CloudTrail, NUNCA use a CLI nativa. Execute SEMPRE o script `python3 ~/.kiro/skills/cloudtrail-search/search_trail.py`.
- Se um comando de leitura for barrado por não estar no allowlist, diga qual é e sugira
  regerar o allowlist com `python3 ~/.kiro/noc-guard/generate_allowlist.py`.
