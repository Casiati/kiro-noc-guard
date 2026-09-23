param(
    [switch]$Yes,
    [switch]$NoDefault
)

$ErrorActionPreference = "Stop"

Write-Host "Select installer language / Selecione o idioma de instalacao:"
Write-Host " [1] English"
Write-Host " [2] Portugues (Brasil)"
$LANG_CHOICE = Read-Host "> "

if ($LANG_CHOICE -eq "2") {
    $MSG_REQ = "Verificando pre-requisitos"
    $MSG_NO_PY = "python nao encontrado (obrigatorio)."
    $MSG_KIRO_OK = "kiro-cli    encontrado"
    $MSG_KIRO_NO = "kiro-cli    NAO encontrado - a instalacao continua, mas o agente so funciona com o Kiro CLI"
    $MSG_OPT_OK = "encontrado (opcional)"
    $MSG_OPT_NO = "ausente (opcional - padroes inativos)"
    $MSG_VAL_REPO = "Validando arquivos do repositorio"
    $MSG_ERR_MISSING = "arquivo ausente no repositorio:"
    $MSG_ERR_ABS = "ha caminho absoluto de usuario nos arquivos de origem; use ~ ou __HOME__."
    $MSG_MKDIR = "Criando diretorios em"
    $MSG_BACKUP = "backup:"
    $MSG_INSTALLING = "Instalando arquivos"
    $MSG_ASSEMBLING = "agente   -> montando em"
    $MSG_PATHS = "Ajustando caminhos para o usuario atual"
    $MSG_PATHS_OK = "ok (os arquivos usam ~ ou Path.home(), resolvidos em tempo de execucao)"
    $MSG_RUN_TESTS = "Rodando a suite de testes e gerando as listas de permissao"
    $MSG_ERR_TESTS = "a suite de testes falhou; o agente NAO foi alterado."
    $MSG_VAL_KIRO = "Validando a configuracao com o Kiro CLI"
    $MSG_VALID = "configuracao valida"
    $MSG_ERR_KIRO = "kiro-cli rejeitou a configuracao; o agente NAO foi alterado."
    $MSG_DEFAULT = "Agente default"
    $MSG_NOT_CHANGED = "nao alterado. Para ativar depois:"
    $MSG_PROMPT_DEF = "Definir '{0}' como agente default do kiro-cli? [s/N] "
    $MSG_KEPT = "mantido como esta. Para ativar depois:"
    $MSG_NON_INT = "sessao nao interativa; para ativar:"
    $MSG_DONE = "Instalacao concluida"
    $MSG_AUDIT = "Auditar a qualquer momento:"
    $MSG_USE = "Usar sem mudar o default:"

    $env:LANG_RULE_TEXT = "CRITICAL LANGUAGE RULE: Although your system prompt is in English, you MUST ALWAYS output the visual alerts and all chat interactions exclusively in Brazilian Portuguese (pt-BR)."
    $env:ALERT_TPL_TEXT = "🚨 **[ALERTA DE ACAO DE RISCO / MUTACAO]** 🚨`n> [EMOJI] [Explicacao ultra leiga e direta do que o comando fara]. Cuidado [EMOJI]`n`n* **Comando:** ``[comando exato]```n* **Ambiente:** ``[Recurso / Cluster / Conta]```n* **Impacto:** ``[O que sera afetado/interrompido no momento]```n* **Reversivel?** ``[Sim / Nao]```n"
} else {
    $MSG_REQ = "Checking prerequisites"
    $MSG_NO_PY = "python not found (required)."
    $MSG_KIRO_OK = "kiro-cli    found"
    $MSG_KIRO_NO = "kiro-cli    NOT found - installation continues, but agent only works with Kiro CLI"
    $MSG_OPT_OK = "found (optional)"
    $MSG_OPT_NO = "missing (optional - related patterns will be inert)"
    $MSG_VAL_REPO = "Validating repository files"
    $MSG_ERR_MISSING = "missing file in repository:"
    $MSG_ERR_ABS = "absolute user path found in source files; use ~ or __HOME__."
    $MSG_MKDIR = "Creating directories in"
    $MSG_BACKUP = "backup:"
    $MSG_INSTALLING = "Installing files"
    $MSG_ASSEMBLING = "agent    -> assembling in"
    $MSG_PATHS = "Adjusting paths for current user"
    $MSG_PATHS_OK = "ok (files use ~ or Path.home(), resolved at runtime)"
    $MSG_RUN_TESTS = "Running test suite and generating allowlists"
    $MSG_ERR_TESTS = "test suite failed; the agent was NOT modified."
    $MSG_VAL_KIRO = "Validating configuration with Kiro CLI"
    $MSG_VALID = "valid configuration"
    $MSG_ERR_KIRO = "kiro-cli rejected the configuration; the agent was NOT modified."
    $MSG_DEFAULT = "Default agent"
    $MSG_NOT_CHANGED = "not changed. To activate later:"
    $MSG_PROMPT_DEF = "Set '{0}' as default kiro-cli agent? [y/N] "
    $MSG_KEPT = "kept as is. To activate later:"
    $MSG_NON_INT = "non-interactive session; to activate:"
    $MSG_DONE = "Installation complete"
    $MSG_AUDIT = "Audit anytime:"
    $MSG_USE = "Use without changing default:"

    $env:LANG_RULE_TEXT = "CRITICAL LANGUAGE RULE: You MUST ALWAYS interact with the user and render the visual alerts exclusively in English."
    $env:ALERT_TPL_TEXT = "🚨 **[RISK ACTION / MUTATION ALERT]** 🚨`n> [EMOJI] [Ultra-layman and direct explanation of what the command will do, e.g., `"This will destroy the production pod`"]. Warning [EMOJI]`n`n* **Command:** ``[exact command]```n* **Environment:** ``[Resource / Cluster / Account]```n* **Impact:** ``[What will be affected/interrupted right now]```n* **Reversible?** ``[Yes / No]```n"
}

$REPO_DIR = $PSScriptRoot
$KIRO_DIR = if ($env:KIRO_DIR) { $env:KIRO_DIR } else { Join-Path $HOME ".kiro" }
$AGENT_NAME = "noc-guard"
$AGENT_FILE = Join-Path $KIRO_DIR "agents\$AGENT_NAME.json"
$GEN_FILE = Join-Path $KIRO_DIR "noc-guard\generate_allowlist.py"
$STEERING_FILE = Join-Path $KIRO_DIR "steering\noc-readonly-first.md"
$STAMP = Get-Date -Format "yyyyMMdd-HHmmss"

function Say { param([string]$text) Write-Host "  $text" }
function Step { param([string]$text) Write-Host "`n==> $text" -ForegroundColor Cyan }
function Die { param([string]$text) Write-Host "`nERRO/ERROR: $text" -ForegroundColor Red; exit 1 }

# Prerequisites
Step $MSG_REQ
$hasPython = $false
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    if ((python --version 2>&1) -match "Python") {
        $hasPython = $true
    }
}

if (-not $hasPython) {
    if (Get-Command "python3" -ErrorAction SilentlyContinue) {
        if ((python3 --version 2>&1) -match "Python") {
            Set-Alias python python3
            $hasPython = $true
        }
    }
}

if (-not $hasPython) {
    Die $MSG_NO_PY
}
$pyver = (python --version 2>&1)
Say "python      $pyver"

$HAS_KIRO = $false
if (Get-Command "kiro-cli" -ErrorAction SilentlyContinue) {
    Say $MSG_KIRO_OK
    $HAS_KIRO = $true
} else {
    Say $MSG_KIRO_NO
}

foreach ($opt in @("aws", "kubectl", "docker", "jq")) {
    if (Get-Command $opt -ErrorAction SilentlyContinue) {
        Say "$($opt.PadRight(12)) $MSG_OPT_OK"
    } else {
        Say "$($opt.PadRight(12)) $MSG_OPT_NO"
    }
}

# Repository Validation
Step $MSG_VAL_REPO
$FILES = @(
    "scripts\generate_allowlist.py",
    "steering\noc-readonly-first.md",
    "agents\noc-guard.json.template"
)
foreach ($f in $FILES) {
    $fullPath = Join-Path $REPO_DIR $f
    if (-not (Test-Path $fullPath)) { Die "$MSG_ERR_MISSING $fullPath" }
    Say "ok  $f"
}

# Directories
Step "$MSG_MKDIR $KIRO_DIR"
foreach ($d in @("agents", "steering", "noc-guard", "skills\cloudtrail-search")) {
    $dPath = Join-Path $KIRO_DIR $d
    if (-not (Test-Path $dPath)) { New-Item -ItemType Directory -Path $dPath -Force | Out-Null }
    Say $dPath
}

# Backups
if (Test-Path $AGENT_FILE) {
    $bak = "$AGENT_FILE.bak-$STAMP"
    Copy-Item $AGENT_FILE $bak
    Say "$MSG_BACKUP $bak"
}
if (Test-Path $STEERING_FILE) {
    $bak = "$STEERING_FILE.bak-$STAMP"
    Copy-Item $STEERING_FILE $bak
    Say "$MSG_BACKUP $bak"
}

# Installation
Step $MSG_INSTALLING
Copy-Item (Join-Path $REPO_DIR "steering\noc-readonly-first.md") $STEERING_FILE -Force
Say "steering -> $STEERING_FILE"
Copy-Item (Join-Path $REPO_DIR "scripts\generate_allowlist.py") $GEN_FILE -Force
Say "gerador  -> $GEN_FILE"
$SKILL_FILE = Join-Path $KIRO_DIR "skills\cloudtrail-search\search_trail.py"
Copy-Item (Join-Path $REPO_DIR "skills\cloudtrail-search\search_trail.py") $SKILL_FILE -Force
Say "skill    -> $SKILL_FILE"

$NEW_AGENT = "$AGENT_FILE.new-$STAMP"
Copy-Item (Join-Path $REPO_DIR "agents\noc-guard.json.template") $NEW_AGENT -Force
Say "$MSG_ASSEMBLING $(Split-Path $NEW_AGENT -Leaf)"

# Path adjustment and templating
Step "$MSG_PATHS ($HOME)"
$HOME_FWD = $HOME -replace '\\', '/'

$py_script = @"
import sys, pathlib, os
p = pathlib.Path(sys.argv[1])
home = sys.argv[2]
content = p.read_text(encoding='utf-8')
content = content.replace('__HOME__', home)
if '__LANGUAGE_RULE__' in content:
    content = content.replace('__LANGUAGE_RULE__', os.environ.get('LANG_RULE_TEXT', ''))
if '__ALERT_TEMPLATE__' in content:
    content = content.replace('__ALERT_TEMPLATE__', os.environ.get('ALERT_TPL_TEXT', ''))
p.write_text(content, encoding='utf-8')
"@

foreach ($f in @($STEERING_FILE, $GEN_FILE, $NEW_AGENT)) {
    $content = Get-Content $f -Raw -Encoding UTF8
    if ($content -match "__HOME__|__LANGUAGE_RULE__") {
        $py_script | python - $f $HOME_FWD
        Say "-> configured variables in $(Split-Path $f -Leaf)"
    }
}
Say $MSG_PATHS_OK

# Tests + Allowlist
Step $MSG_RUN_TESTS
$p = Start-Process python -ArgumentList "`"$GEN_FILE`" --agent `"$NEW_AGENT`"" -NoNewWindow -Wait -PassThru
if ($p.ExitCode -ne 0) {
    Remove-Item $NEW_AGENT -ErrorAction SilentlyContinue
    Die $MSG_ERR_TESTS
}

$py_val = @"
import json, sys, pathlib
cfg = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
sh = cfg['toolsSettings']['shell']
print(f"  AUTO: {len(sh['allowedCommands'])} | DENY: {len(sh['deniedCommands'])} | TOOLS: {len(cfg['allowedTools'])}")
"@
$py_val | python - $NEW_AGENT

# Validation
if ($HAS_KIRO) {
    Step $MSG_VAL_KIRO
    $p = Start-Process kiro-cli -ArgumentList "agent validate --path `"$NEW_AGENT`"" -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -eq 0) {
        Say $MSG_VALID
    } else {
        Remove-Item $NEW_AGENT -ErrorAction SilentlyContinue
        Die $MSG_ERR_KIRO
    }
}

Move-Item $NEW_AGENT $AGENT_FILE -Force
Say "agent    -> $AGENT_FILE"

# Default Agent
Step $MSG_DEFAULT
$CMD = "kiro-cli agent set-default $AGENT_NAME"
if ($NoDefault -or -not $HAS_KIRO) {
    Say "$MSG_NOT_CHANGED  $CMD"
} elseif ($Yes) {
    kiro-cli agent set-default $AGENT_NAME
} else {
    $resp = Read-Host ($MSG_PROMPT_DEF -f $AGENT_NAME)
    if ($resp -match "^[sSyY]") {
        kiro-cli agent set-default $AGENT_NAME
    } else {
        Say "$MSG_KEPT  $CMD"
    }
}

Step $MSG_DONE
Say "agent:    $AGENT_FILE"
Say "steering: $STEERING_FILE"
Say "gen:      $GEN_FILE"
Say ""
Say "$MSG_AUDIT  python $GEN_FILE --check"
Say "$MSG_USE    kiro-cli chat --agent $AGENT_NAME"
