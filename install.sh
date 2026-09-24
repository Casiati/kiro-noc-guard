#!/usr/bin/env bash
#
# kiro-noc-guard — installer
#
# Uso/Usage:
#   ./install.sh              # installs and asks before setting default agent
#   ./install.sh --yes        # installs and sets default automatically
#   ./install.sh --no-default # installs but doesn't touch the default agent
#
set -euo pipefail

# Language prompt
LANG_CHOICE=""
if [ -t 0 ]; then
  printf "Select installer language / Selecione o idioma de instalação:\n"
  printf " [1] English\n [2] Português (Brasil)\n> "
  read -r LANG_CHOICE
fi

if [ "$LANG_CHOICE" = "2" ]; then
  MSG_REQ="Verificando pré-requisitos"
  MSG_NO_PY="python3 não encontrado (obrigatório)."
  MSG_KIRO_OK="kiro-cli    encontrado"
  MSG_KIRO_NO="kiro-cli    NÃO encontrado — a instalação continua, mas o agente só funciona com o Kiro CLI"
  MSG_OPT_OK="encontrado (opcional)"
  MSG_OPT_NO="ausente (opcional — padrões inativos)"
  MSG_VAL_REPO="Validando arquivos do repositório"
  MSG_ERR_MISSING="arquivo ausente no repositório:"
  MSG_ERR_ABS="há caminho absoluto de usuário nos arquivos de origem; use ~ ou __HOME__."
  MSG_MKDIR="Criando diretórios em"
  MSG_BACKUP="backup:"
  MSG_INSTALLING="Instalando arquivos"
  MSG_ASSEMBLING="agente   -> montando em"
  MSG_PATHS="Ajustando caminhos para o usuário atual"
  MSG_PATHS_OK="ok (os arquivos usam ~ ou Path.home(), resolvidos em tempo de execução)"
  MSG_RUN_TESTS="Rodando a suíte de testes e gerando as listas de permissão"
  MSG_ERR_TESTS="a suíte de testes falhou; o agente NÃO foi alterado."
  MSG_VAL_KIRO="Validando a configuração com o Kiro CLI"
  MSG_VALID="configuração válida"
  MSG_ERR_KIRO="kiro-cli rejeitou a configuração; o agente NÃO foi alterado."
  MSG_DEFAULT="Agente default"
  MSG_NOT_CHANGED="não alterado. Para ativar depois:"
  MSG_PROMPT_DEF="Definir '%s' como agente default do kiro-cli? [s/N] "
  MSG_KEPT="mantido como está. Para ativar depois:"
  MSG_NON_INT="sessão não interativa; para ativar:"
  MSG_DONE="Instalação concluída"
  MSG_AUDIT="Auditar a qualquer momento:"
  MSG_USE="Usar sem mudar o default:"

  MSG_KB_TITLE="Base de Conhecimento Compartilhada (AWS S3)"
  MSG_KB_DESC="O agente pode auto-documentar a resolução de incidentes em arquivos Markdown sincronizados via AWS S3 para toda a equipe compartilhar o histórico de soluções."
  MSG_KB_ENABLE="Deseja ativar a Base de Conhecimento compartilhada via AWS S3? [s/N] "
  MSG_KB_PROMPT="Informe o nome completo do Bucket S3 (ex: noc-runbooks-123456789012-us-east-1): "
  MSG_KB_INVALID="Nome de bucket inválido! Deve ter entre 3 e 63 caracteres (letras minúsculas, números, hífens e pontos; sem '..')."
  MSG_KB_SKIPPED="Base de Conhecimento não ativada (pode ser configurada depois)."

  export LANG_RULE_TEXT="CRITICAL LANGUAGE RULE: Although your system prompt is in English, you MUST ALWAYS output the visual alerts and all chat interactions exclusively in Brazilian Portuguese (pt-BR)."
  export ALERT_TPL_TEXT="🚨 **[ALERTA DE AÇÃO DE RISCO / MUTAÇÃO]** 🚨
> [EMOJI] [Explicação ultra leiga e direta do que o comando fará]. Cuidado [EMOJI]

* **Comando:** \`[comando exato]\`
* **Ambiente:** \`[Recurso / Cluster / Conta]\`
* **Impacto:** \`[O que será afetado/interrompido no momento]\`
* **Reversível?** \`[Sim / Não]\`"
else
  MSG_REQ="Checking prerequisites"
  MSG_NO_PY="python3 not found (required)."
  MSG_KIRO_OK="kiro-cli    found"
  MSG_KIRO_NO="kiro-cli    NOT found — installation continues, but agent only works with Kiro CLI"
  MSG_OPT_OK="found (optional)"
  MSG_OPT_NO="missing (optional — related patterns will be inert)"
  MSG_VAL_REPO="Validating repository files"
  MSG_ERR_MISSING="missing file in repository:"
  MSG_ERR_ABS="absolute user path found in source files; use ~ or __HOME__."
  MSG_MKDIR="Creating directories in"
  MSG_BACKUP="backup:"
  MSG_INSTALLING="Installing files"
  MSG_ASSEMBLING="agent    -> assembling in"
  MSG_PATHS="Adjusting paths for current user"
  MSG_PATHS_OK="ok (files use ~ or Path.home(), resolved at runtime)"
  MSG_RUN_TESTS="Running test suite and generating allowlists"
  MSG_ERR_TESTS="test suite failed; the agent was NOT modified."
  MSG_VAL_KIRO="Validating configuration with Kiro CLI"
  MSG_VALID="valid configuration"
  MSG_ERR_KIRO="kiro-cli rejected the configuration; the agent was NOT modified."
  MSG_DEFAULT="Default agent"
  MSG_NOT_CHANGED="not changed. To activate later:"
  MSG_PROMPT_DEF="Set '%s' as default kiro-cli agent? [y/N] "
  MSG_KEPT="kept as is. To activate later:"
  MSG_NON_INT="non-interactive session; to activate:"
  MSG_DONE="Installation complete"
  MSG_AUDIT="Audit anytime:"
  MSG_USE="Use without changing default:"

  MSG_KB_TITLE="Shared Knowledge Base (AWS S3)"
  MSG_KB_DESC="The agent can auto-document incident resolutions into Markdown files synced via AWS S3 so the entire team shares the same troubleshooting history."
  MSG_KB_ENABLE="Enable shared Knowledge Base via AWS S3? [y/N] "
  MSG_KB_PROMPT="Enter the full S3 Bucket name (e.g., noc-runbooks-123456789012-us-east-1): "
  MSG_KB_INVALID="Invalid bucket name! Must be between 3 and 63 characters (lowercase letters, numbers, hyphens, and dots; no '..')."
  MSG_KB_SKIPPED="Knowledge Base skipped (can be configured later)."

  export LANG_RULE_TEXT="CRITICAL LANGUAGE RULE: You MUST ALWAYS interact with the user and render the visual alerts exclusively in English."
  export ALERT_TPL_TEXT="🚨 **[RISK ACTION / MUTATION ALERT]** 🚨
> [EMOJI] [Ultra-layman and direct explanation of what the command will do, e.g., \"This will destroy the production pod\"]. Warning [EMOJI]

* **Command:** \`[exact command]\`
* **Environment:** \`[Resource / Cluster / Account]\`
* **Impact:** \`[What will be affected/interrupted right now]\`
* **Reversible?** \`[Yes / No]\`"
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIRO_DIR="${KIRO_DIR:-$HOME/.kiro}"
AGENT_NAME="noc-guard"
AGENT_FILE="$KIRO_DIR/agents/$AGENT_NAME.json"
GEN_FILE="$KIRO_DIR/noc-guard/generate_allowlist.py"
STEERING_FILE="$KIRO_DIR/noc-guard/steering/noc-readonly-first.md"
LEGACY_STEERING="$KIRO_DIR/steering/noc-readonly-first.md"
STAMP="$(date +%Y%m%d-%H%M%S)"

ASSUME_YES=0
SET_DEFAULT=1
for arg in "$@"; do
  case "$arg" in
    --yes|-y)     ASSUME_YES=1 ;;
    --no-default) SET_DEFAULT=0 ;;
    -h|--help)    sed -n '2,15p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "error: unknown argument '$arg'" >&2; exit 2 ;;
  esac
done

say()  { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
warn() { printf '  AVISO/WARN: %s\n' "$*"; }
die()  { printf '\nERRO/ERROR: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- pré-requisitos
step "$MSG_REQ"
command -v python3 >/dev/null 2>&1 || die "$MSG_NO_PY"
say "python3     $(python3 --version 2>&1 | awk '{print $2}')"

if command -v kiro-cli >/dev/null 2>&1; then
  say "$MSG_KIRO_OK"
  HAS_KIRO=1
else
  say "$MSG_KIRO_NO"
  HAS_KIRO=0
fi
for opt in aws kubectl docker jq; do
  if command -v "$opt" >/dev/null 2>&1; then
    say "$opt$(printf '%*s' $((12 - ${#opt})) '') $MSG_OPT_OK"
  else
    say "$opt$(printf '%*s' $((12 - ${#opt})) '') $MSG_OPT_NO"
  fi
done

if python3 -c 'import boto3' >/dev/null 2>&1; then
  say "boto3        $MSG_OPT_OK"
else
  say "boto3        não instalado (search_trail usará fallback nativo da AWS CLI)"
fi

# ------------------------------------------------------- arquivos de origem
step "$MSG_VAL_REPO"
for f in "$REPO_DIR/scripts/generate_allowlist.py" \
         "$REPO_DIR/steering/noc-readonly-first.md" \
         "$REPO_DIR/agents/noc-guard.json.template"; do
  [ -f "$f" ] || die "$MSG_ERR_MISSING $f"
  say "ok  ${f#"$REPO_DIR"/}"
done

if grep -rInE '/home/[a-z0-9_-]+|/Users/[a-z0-9_-]+' \
      "$REPO_DIR/scripts/generate_allowlist.py" \
      "$REPO_DIR/steering/noc-readonly-first.md" \
      "$REPO_DIR/agents/noc-guard.json.template" >/dev/null; then
  die "$MSG_ERR_ABS"
fi

# --------------------------------------------- base de conhecimento (opcional)
step "$MSG_KB_TITLE"
say "$MSG_KB_DESC"
KB_BUCKET=""
if [ -t 0 ] && [ "$ASSUME_YES" -eq 0 ]; then
  read -r -p "$MSG_KB_ENABLE" ENABLE_KB_ANS < /dev/tty || ENABLE_KB_ANS=""
  case "$ENABLE_KB_ANS" in
    [sSyY]*)
      while true; do
        read -r -p "$MSG_KB_PROMPT" BUCKET_INPUT < /dev/tty || BUCKET_INPUT=""
        BUCKET_INPUT="$(echo "$BUCKET_INPUT" | tr -d '[:space:]')"
        if [ -z "$BUCKET_INPUT" ]; then
          say "$MSG_KB_SKIPPED"
          break
        fi
        if [[ "$BUCKET_INPUT" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] && [[ "$BUCKET_INPUT" != *".."* ]]; then
          KB_BUCKET="$BUCKET_INPUT"
          say "ok: bucket configurado -> $KB_BUCKET"
          break
        else
          warn "$MSG_KB_INVALID"
        fi
      done
      ;;
    *)
      say "$MSG_KB_SKIPPED"
      ;;
  esac
else
  say "$MSG_KB_SKIPPED"
fi

if [ -n "$KB_BUCKET" ]; then
  if [ "$LANG_CHOICE" = "1" ]; then
    export KB_DIRECTIVE_TEXT="- To query or record learnings in the shared NOC Knowledge Base / Runbooks, use: \`python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket $KB_BUCKET\`. Whenever you successfully diagnose a complex root cause, run \`kb_manager.py --action add\` to auto-document the resolution."
  else
    export KB_DIRECTIVE_TEXT="- Para consultar ou registrar aprendizados na Base de Conhecimento / Runbooks compartilhados da equipe, utilize o script: \`python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket $KB_BUCKET\`. Sempre que diagnosticar com sucesso a causa raiz de um incidente complexo, execute \`kb_manager.py --action add\` para auto-documentar a resolução."
  fi
else
  export KB_DIRECTIVE_TEXT=""
fi

# ------------------------------------------------------------------ diretórios
step "$MSG_MKDIR $KIRO_DIR"
for d in agents noc-guard noc-guard/steering noc-guard/skills/cloudtrail-search noc-guard/skills/knowledge-builder noc-guard/kb; do
  mkdir -p "$KIRO_DIR/$d"
  say "$KIRO_DIR/$d"
done

# --------------------------------------------------------------------- backups & limpeza
# Limpeza de steering legado na pasta global que afetava outros agentes (ex: kiro_default)
if [ -f "$LEGACY_STEERING" ]; then
  rm -f "$LEGACY_STEERING"
  say "limpeza: removido steering legado global em $LEGACY_STEERING"
fi

# Limpeza de skills legadas na pasta global
if [ -f "$KIRO_DIR/skills/cloudtrail-search/search_trail.py" ]; then
  rm -f "$KIRO_DIR/skills/cloudtrail-search/search_trail.py"
fi

if [ -f "$AGENT_FILE" ]; then
  cp -p "$AGENT_FILE" "$AGENT_FILE.bak-$STAMP"
  say "$MSG_BACKUP $AGENT_FILE.bak-$STAMP"
fi
if [ -f "$STEERING_FILE" ]; then
  cp -p "$STEERING_FILE" "$STEERING_FILE.bak-$STAMP"
  say "$MSG_BACKUP $STEERING_FILE.bak-$STAMP"
fi

# ------------------------------------------------------------------ instalação
step "$MSG_INSTALLING"
install -m 0644 "$REPO_DIR/steering/noc-readonly-first.md" "$STEERING_FILE"
say "steering -> $STEERING_FILE"
install -m 0755 "$REPO_DIR/scripts/generate_allowlist.py" "$GEN_FILE"
say "gerador  -> $GEN_FILE"
install -m 0755 "$REPO_DIR/skills/cloudtrail-search/search_trail.py" "$KIRO_DIR/noc-guard/skills/cloudtrail-search/search_trail.py"
say "skill (cloudtrail) -> $KIRO_DIR/noc-guard/skills/cloudtrail-search/search_trail.py"
install -m 0755 "$REPO_DIR/skills/knowledge-builder/kb_manager.py" "$KIRO_DIR/noc-guard/skills/knowledge-builder/kb_manager.py"
say "skill (knowledge)  -> $KIRO_DIR/noc-guard/skills/knowledge-builder/kb_manager.py"

NEW_AGENT="$AGENT_FILE.new-$STAMP"
trap 'rm -f "$NEW_AGENT"' EXIT
install -m 0644 "$REPO_DIR/agents/noc-guard.json.template" "$NEW_AGENT"
say "$MSG_ASSEMBLING $(basename "$NEW_AGENT")"

step "$MSG_PATHS ($HOME)"
for f in "$STEERING_FILE" "$GEN_FILE" "$NEW_AGENT"; do
  if grep -qE '__HOME__|__LANGUAGE_RULE__|__KB_DIRECTIVE__' "$f"; then
    python3 - "$f" "$HOME" <<'PY'
import sys, pathlib, os
p, home = pathlib.Path(sys.argv[1]), sys.argv[2]
content = p.read_text(encoding="utf-8")
content = content.replace("__HOME__", home)
if "__LANGUAGE_RULE__" in content:
    content = content.replace("__LANGUAGE_RULE__", os.environ.get("LANG_RULE_TEXT", ""))
if "__ALERT_TEMPLATE__" in content:
    content = content.replace("__ALERT_TEMPLATE__", os.environ.get("ALERT_TPL_TEXT", ""))
if "__KB_DIRECTIVE__" in content:
    content = content.replace("__KB_DIRECTIVE__", os.environ.get("KB_DIRECTIVE_TEXT", ""))
p.write_text(content, encoding="utf-8")
PY
    say "-> configured variables in $(basename "$f")"
  fi
done
say "$MSG_PATHS_OK"

# ------------------------------------------------- testes + geração das listas
step "$MSG_RUN_TESTS"
python3 "$GEN_FILE" --agent "$NEW_AGENT" || die "$MSG_ERR_TESTS"

python3 - "$NEW_AGENT" <<'PY'
import json, sys, pathlib
cfg = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
sh = cfg["toolsSettings"]["shell"]
print(f"  AUTO: {len(sh['allowedCommands'])} | DENY: {len(sh['deniedCommands'])} | TOOLS: {len(cfg['allowedTools'])}")
PY

# ----------------------------------------------------------------- validação
if [ "$HAS_KIRO" = "1" ]; then
  step "$MSG_VAL_KIRO"
  if kiro-cli agent validate --path "$NEW_AGENT"; then
    say "$MSG_VALID"
  else
    die "$MSG_ERR_KIRO"
  fi
fi

mv -f "$NEW_AGENT" "$AGENT_FILE"
trap - EXIT
say "agent    -> $AGENT_FILE"

# ------------------------------------------------------------- agente default
step "$MSG_DEFAULT"
CMD="kiro-cli agent set-default $AGENT_NAME"
if [ "$SET_DEFAULT" = "0" ] || [ "$HAS_KIRO" = "0" ]; then
  say "$MSG_NOT_CHANGED  $CMD"
elif [ "$ASSUME_YES" = "1" ]; then
  $CMD
elif [ -t 0 ]; then
  printf "  $MSG_PROMPT_DEF" "$AGENT_NAME"
  read -r resp
  case "$resp" in
    s|S|y|Y) $CMD ;;
    *) say "$MSG_KEPT  $CMD" ;;
  esac
else
  say "$MSG_NON_INT  $CMD"
fi

step "$MSG_DONE"
say "agent:    $AGENT_FILE"
say "steering: $STEERING_FILE"
say "gen:      $GEN_FILE"
say ""
say "$MSG_AUDIT  python3 $GEN_FILE --check"
say "$MSG_USE    kiro-cli chat --agent $AGENT_NAME"
