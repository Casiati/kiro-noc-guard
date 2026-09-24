#!/usr/bin/env python3
"""
Hook 'stop' do noc-guard — lembrete de auto-documentação na Base de Conhecimento.

Este script roda ao final de CADA turno do assistente (trigger "stop"). Ele
recebe via STDIN um JSON com o campo "assistant_response" (texto completo da
resposta do turno) e verifica heuristicamente se a resposta parece ser uma
investigação de incidente concluída (menciona causa raiz/conclusão) sem
nenhuma chamada visível a `kb_manager.py --action add`.

Limitação conhecida e documentada: para o trigger "stop", o motor do Kiro
NÃO garante que o STDOUT deste hook seja injetado no contexto do próximo
turno (isso só é documentado para agentSpawn/userPromptSubmit). Por isso,
este hook não tenta "instruir" o modelo diretamente — ele apenas:
  1. Exit code != 0 quando detecta um provável caso não documentado, o que
     faz o Kiro exibir o STDERR como aviso visível ao operador na própria
     tela do chat (comportamento documentado para stop: "Other: Show STDERR
     warning to user").
  2. Nunca bloqueia nem falha a resposta em si (o turno já terminou).

Isso não substitui a instrução em texto no steering (fonte primária de
verdade para o modelo) — é uma camada extra de VISIBILIDADE para o operador
humano notar quando a auto-documentação pode ter sido pulada.
"""
import json
import re
import sys

# Palavras que indicam que o turno chamou (ou tentou chamar) o kb_manager.
KB_CALL_MARKERS = (
    "kb_manager.py",
    "--action add",
)

# Palavras que indicam que a resposta chegou a uma conclusão de investigação
# (root cause / falso positivo / recomendação) — sinal de que o critério do
# checklist final ("3+ comandos de leitura E conclusão explícita") pode ter
# sido atingido.
CONCLUSION_MARKERS = (
    "causa raiz", "root cause",
    "falso positivo", "false positive",
    "recomendação", "recommendation",
    "recomendo", "i recommend",
)


def main():
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Entrada inesperada: não bloqueia, apenas não avalia nada.
        sys.exit(0)

    response = event.get("assistant_response", "") or ""
    if not response:
        sys.exit(0)

    mentions_kb_call = any(marker in response for marker in KB_CALL_MARKERS)
    mentions_conclusion = any(
        marker.lower() in response.lower() for marker in CONCLUSION_MARKERS
    )

    if mentions_conclusion and not mentions_kb_call:
        print(
            "⚠️  noc-guard: esta resposta parece concluir uma investigação de "
            "incidente (menciona causa raiz/falso positivo/recomendação), mas "
            "não há indício de chamada ao kb_manager.py --action add. Confira "
            "o Checklist Final da Base de Conhecimento no steering — se o "
            "critério foi atingido, documente manualmente agora com:\n"
            "  python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py "
            "--bucket <bucket> --action add --alert \"<topico>\" --content \"<resumo>\"",
            file=sys.stderr,
        )
        sys.exit(1)  # exit != 0: Kiro exibe este STDERR como aviso ao operador

    sys.exit(0)


if __name__ == "__main__":
    main()
