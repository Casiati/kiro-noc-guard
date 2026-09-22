#!/usr/bin/env bash
#
# kiro-noc-guard — instalador
#
# Instala o agente NOC read-only do Kiro CLI no usuário atual:
#   ~/.kiro/steering/noc-readonly-first.md   (diretriz de comportamento)
#   ~/.kiro/noc-guard/generate_allowlist.py  (gerador + suíte de testes)
#   ~/.kiro/agents/noc-aws.json              (config do agente, gerada)
#
# Uso:
#   ./install.sh              # instala (pergunta antes de definir como agente default)
#   ./install.sh --yes        # instala e define como default sem perguntar
#   ./install.sh --no-default # instala e nunca mexe no agente default
#   KIRO_DIR=/tmp/x ./install.sh --no-default   # instala em outro diretório (teste)
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIRO_DIR="${KIRO_DIR:-$HOME/.kiro}"
AGENT_NAME="noc-aws"
AGENT_FILE="$KIRO_DIR/agents/$AGENT_NAME.json"
GEN_FILE="$KIRO_DIR/noc-guard/generate_allowlist.py"
STEERING_FILE="$KIRO_DIR/steering/noc-readonly-first.md"
STAMP="$(date +%Y%m%d-%H%M%S)"

ASSUME_YES=0
SET_DEFAULT=1
for arg in "$@"; do
  case "$arg" in
    --yes|-y)     ASSUME_YES=1 ;;
    --no-default) SET_DEFAULT=0 ;;
    -h|--help)    sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "erro: argumento desconhecido '$arg' (use --help)" >&2; exit 2 ;;
  esac
done

say()  { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
die()  { printf '\nERRO: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- pré-requisitos
step "Verificando pré-requisitos"
command -v python3 >/dev/null 2>&1 || die "python3 não encontrado (obrigatório)."
say "python3     $(python3 --version 2>&1 | awk '{print $2}')"

if command -v kiro-cli >/dev/null 2>&1; then
  say "kiro-cli    encontrado"
  HAS_KIRO=1
else
  say "kiro-cli    NÃO encontrado — a instalação continua, mas o agente só funciona com o Kiro CLI"
  HAS_KIRO=0
fi
for opt in aws kubectl docker jq; do
  if command -v "$opt" >/dev/null 2>&1; then
    say "$opt$(printf '%*s' $((12 - ${#opt})) '')encontrado (opcional)"
  else
    say "$opt$(printf '%*s' $((12 - ${#opt})) '')ausente (opcional — os padrões relacionados ficam inertes)"
  fi
done

# ------------------------------------------------------- arquivos de origem
step "Validando arquivos do repositório"
for f in "$REPO_DIR/scripts/generate_allowlist.py" \
         "$REPO_DIR/steering/noc-readonly-first.md" \
         "$REPO_DIR/agents/noc-aws.json.template"; do
  [ -f "$f" ] || die "arquivo ausente no repositório: $f"
  say "ok  ${f#"$REPO_DIR"/}"
done

# Nenhum caminho absoluto de outro usuário deve vazar para a instalação.
if grep -rInE '/home/[a-z0-9_-]+|/Users/[a-z0-9_-]+' \
      "$REPO_DIR/scripts/generate_allowlist.py" \
      "$REPO_DIR/steering/noc-readonly-first.md" \
      "$REPO_DIR/agents/noc-aws.json.template" >/dev/null; then
  die "há caminho absoluto de usuário nos arquivos de origem; use ~ ou __HOME__."
fi

# ------------------------------------------------------------------ diretórios
step "Criando diretórios em $KIRO_DIR"
for d in agents steering noc-guard skills/cloudtrail-search; do
  mkdir -p "$KIRO_DIR/$d"
  say "$KIRO_DIR/$d"
done

# --------------------------------------------------------------------- backups
if [ -f "$AGENT_FILE" ]; then
  cp -p "$AGENT_FILE" "$AGENT_FILE.bak-$STAMP"
  say "backup: $AGENT_FILE.bak-$STAMP"
fi
if [ -f "$STEERING_FILE" ]; then
  cp -p "$STEERING_FILE" "$STEERING_FILE.bak-$STAMP"
  say "backup: $STEERING_FILE.bak-$STAMP"
fi

# ------------------------------------------------------------------ instalação
step "Instalando arquivos"
install -m 0644 "$REPO_DIR/steering/noc-readonly-first.md" "$STEERING_FILE"
say "steering -> $STEERING_FILE"
install -m 0755 "$REPO_DIR/scripts/generate_allowlist.py" "$GEN_FILE"
say "gerador  -> $GEN_FILE"
install -m 0755 "$REPO_DIR/skills/cloudtrail-search/search_trail.py" "$KIRO_DIR/skills/cloudtrail-search/search_trail.py"
say "skill    -> $KIRO_DIR/skills/cloudtrail-search/search_trail.py"

# A config do agente é montada num arquivo temporário e só substitui a atual no
# final, se testes e validação passarem. Falha => configuração anterior intacta.
NEW_AGENT="$AGENT_FILE.new-$STAMP"
trap 'rm -f "$NEW_AGENT"' EXIT
install -m 0644 "$REPO_DIR/agents/noc-aws.json.template" "$NEW_AGENT"
say "agente   -> montando em $(basename "$NEW_AGENT")"

# Parametrização de caminhos: __HOME__ -> $HOME do usuário atual.
step "Ajustando caminhos para o usuário atual ($HOME)"
for f in "$STEERING_FILE" "$GEN_FILE" "$NEW_AGENT"; do
  if grep -q '__HOME__' "$f"; then
    python3 - "$f" "$HOME" <<'PY'
import sys, pathlib
p, home = pathlib.Path(sys.argv[1]), sys.argv[2]
p.write_text(p.read_text().replace("__HOME__", home))
PY
    say "substituído __HOME__ em $(basename "$f")"
  fi
done
say "ok (os arquivos usam ~ / Path.home(), resolvidos em tempo de execução)"

# ------------------------------------------------- testes + geração das listas
step "Rodando a suíte de testes e gerando as listas de permissão"
python3 "$GEN_FILE" --agent "$NEW_AGENT" || die "a suíte de testes falhou; o agente NÃO foi alterado."

python3 - "$NEW_AGENT" <<'PY'
import json, sys, pathlib
cfg = json.loads(pathlib.Path(sys.argv[1]).read_text())
sh = cfg["toolsSettings"]["shell"]
assert sh["allowedCommands"] and sh["deniedCommands"], "listas vazias após a geração"
assert sh["autoAllowReadonly"] is False and sh["denyByDefault"] is False
assert "shell" not in cfg["allowedTools"] and "aws" not in cfg["allowedTools"], \
    "shell/aws não podem estar em allowedTools (isso aprovaria mutações)"
print(f"  AUTO: {len(sh['allowedCommands'])} padrões | "
      f"DENY: {len(sh['deniedCommands'])} padrões | "
      f"ferramentas liberadas: {len(cfg['allowedTools'])}")
PY

# ----------------------------------------------------------------- validação
if [ "$HAS_KIRO" = "1" ]; then
  step "Validando a configuração com o Kiro CLI"
  if kiro-cli agent validate --path "$NEW_AGENT"; then
    say "configuração válida"
  else
    die "kiro-cli rejeitou a configuração; o agente NÃO foi alterado."
  fi
fi

mv -f "$NEW_AGENT" "$AGENT_FILE"
trap - EXIT
say "agente   -> $AGENT_FILE"

# ------------------------------------------------------------- agente default
step "Agente default"
CMD="kiro-cli agent set-default $AGENT_NAME"
if [ "$SET_DEFAULT" = "0" ] || [ "$HAS_KIRO" = "0" ]; then
  say "não alterado. Para ativar depois:  $CMD"
elif [ "$ASSUME_YES" = "1" ]; then
  $CMD
elif [ -t 0 ]; then
  printf '  Definir "%s" como agente default do kiro-cli? [s/N] ' "$AGENT_NAME"
  read -r resp
  case "$resp" in
    s|S|y|Y) $CMD ;;
    *) say "mantido como está. Para ativar depois:  $CMD" ;;
  esac
else
  say "sessão não interativa; para ativar:  $CMD"
fi

step "Instalação concluída"
say "agente:   $AGENT_FILE"
say "steering: $STEERING_FILE"
say "gerador:  $GEN_FILE"
say ""
say "Auditar a qualquer momento:  python3 $GEN_FILE --check"
say "Usar sem mudar o default:    kiro-cli chat --agent $AGENT_NAME"
