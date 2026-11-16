---
name: stop-hook
description: Hook "stop" do noc-guard que avisa o operador quando uma resposta parece concluir uma investigação sem registrar o achado na Base de Conhecimento.
---

# stop-hook

Script: `~/.kiro/noc-guard/skills/stop-hook/kb_reminder.py`

## Objetivo

Camada extra de visibilidade para o Checklist Final do steering: ao fim de cada turno,
lê o JSON do hook via STDIN (`assistant_response`) e, se a resposta menciona causa raiz /
falso positivo / recomendação sem nenhuma chamada a `kb_manager.py --action add`,
imprime um aviso no STDERR e sai com código 1 (o Kiro exibe o aviso ao operador).

## Quando usar

Não é chamado pelo modelo: é registrado como hook `stop` no agente `noc-guard` pelo instalador.

## Parâmetros

Nenhum. Entrada: JSON via STDIN. Saída: `0` (nada a avisar ou entrada inválida) ou `1` (aviso).

## Limites

- Heurístico (palavras-chave); nunca bloqueia a resposta, só avisa.
- Sem rede, sem AWS, sem escrita em disco.
