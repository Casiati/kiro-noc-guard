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
    $MSG_WINGET_INSTALL = "instale com: winget install {0}"
    $MSG_PY_REC = "Recomendacao: Voce pode instalar o Python no Windows facilmente via winget:`n  winget install Python.Python.3.12"
    $MSG_MISSING_NOTICE = "Alguns requisitos nao foram encontrados nesta maquina:"
    $MSG_MISSING_ESSENTIAL = "Essenciais (obrigatorios):"
    $MSG_MISSING_OPTIONAL = "Opcionais (recomendados):"
    $MSG_AUTO_INSTALL_PROMPT = "Deseja tentar instalar os itens ausentes automaticamente via winget/pip agora? [s/N] "
    $MSG_INSTALLING_PKG = "Instalando: {0}..."
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

    $MSG_KB_TITLE = "Base de Conhecimento Compartilhada (AWS S3)"
    $MSG_KB_DESC = "O agente pode auto-documentar a resolucao de incidentes em arquivos Markdown sincronizados via AWS S3 para toda a equipe compartilhar o historico de solucoes."
    $MSG_KB_EXISTING = "Bucket S3 configurado atualmente: {0}"
    $MSG_KB_KEEP_PROMPT = "Deseja manter o bucket atual [{0}]? [S/n/trocar] (Enter para manter): "
    $MSG_KB_ENABLE = "Deseja ativar a Base de Conhecimento compartilhada via AWS S3? [s/N] "
    $MSG_KB_PROMPT = "Informe o nome completo do Bucket S3 (ex: noc-runbooks-123456789012-us-east-1): "
    $MSG_KB_INVALID = "Nome de bucket invalido! Deve ter entre 3 e 63 caracteres (letras minusculas, numeros, hifens e pontos; sem '..')."
    $MSG_KB_SKIPPED = "Base de Conhecimento nao ativada (pode ser configurada depois)."

    $MSG_BOTO_PROMPT = "Deseja instalar o boto3 automaticamente via pip? [s/N] "
    $MSG_BOTO_DESC = "Beneficio: O boto3 e o SDK oficial da AWS para Python. Ele faz consultas diretas na API em memoria, tornando a busca no CloudTrail mais rapida e precisa do que via CLI."
    $MSG_BOTO_INSTALLING = "Instalando boto3 via pip..."
    $MSG_BOTO_OK = "boto3 instalado com sucesso!"
    $MSG_BOTO_FAIL = "Nao foi possivel instalar o boto3 automaticamente. O fallback nativo da AWS CLI continuara sendo usado normalmente."

    $env:LANG_RULE_TEXT = "CRITICAL LANGUAGE RULE: Although your system prompt is in English, you MUST ALWAYS output the visual alerts and all chat interactions exclusively in Brazilian Portuguese (pt-BR)."
    $env:ALERT_TPL_TEXT = "🚨 **[ALERTA DE ACAO DE RISCO / MUTACAO]** 🚨`n> [EMOJI] [Explicacao ultra leiga e direta do que o comando fara]. Cuidado [EMOJI]`n`n* **Comando:** ``[comando exato]```n* **Ambiente:** ``[Recurso / Cluster / Conta]```n* **Impacto:** ``[O que sera afetado/interrompido no momento]```n* **Reversivel?** ``[Sim / Nao]```n"
} else {
    $MSG_REQ = "Checking prerequisites"
    $MSG_NO_PY = "python not found (required)."
    $MSG_KIRO_OK = "kiro-cli    found"
    $MSG_KIRO_NO = "kiro-cli    NOT found - installation continues, but agent only works with Kiro CLI"
    $MSG_OPT_OK = "found (optional)"
    $MSG_OPT_NO = "missing (optional - related patterns will be inert)"
    $MSG_WINGET_INSTALL = "install with: winget install {0}"
    $MSG_PY_REC = "Recommendation: You can easily install Python on Windows via winget:`n  winget install Python.Python.3.12"
    $MSG_MISSING_NOTICE = "Some prerequisites were not found on this machine:"
    $MSG_MISSING_ESSENTIAL = "Essential (required):"
    $MSG_MISSING_OPTIONAL = "Optional (recommended):"
    $MSG_AUTO_INSTALL_PROMPT = "Would you like to attempt automatic installation of missing items via winget/pip now? [y/N] "
    $MSG_INSTALLING_PKG = "Installing: {0}..."
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

    $MSG_KB_TITLE = "Shared Knowledge Base (AWS S3)"
    $MSG_KB_DESC = "The agent can auto-document incident resolutions into Markdown files synced via AWS S3 so the entire team shares the same troubleshooting history."
    $MSG_KB_EXISTING = "Currently configured S3 Bucket: {0}"
    $MSG_KB_KEEP_PROMPT = "Keep current bucket [{0}]? [Y/n/change] (Enter to keep): "
    $MSG_KB_ENABLE = "Enable shared Knowledge Base via AWS S3? [y/N] "
    $MSG_KB_PROMPT = "Enter the full S3 Bucket name (e.g., noc-runbooks-123456789012-us-east-1): "
    $MSG_KB_INVALID = "Invalid bucket name! Must be between 3 and 63 characters (lowercase letters, numbers, hyphens, and dots; no '..')."
    $MSG_KB_SKIPPED = "Knowledge Base skipped (can be configured later)."

    $MSG_BOTO_PROMPT = "Would you like to install boto3 automatically via pip? [y/N] "
    $MSG_BOTO_DESC = "Benefit: boto3 is the official AWS SDK for Python. It makes direct in-memory API queries, making CloudTrail searches faster and more accurate than via CLI."
    $MSG_BOTO_INSTALLING = "Installing boto3 via pip..."
    $MSG_BOTO_OK = "boto3 installed successfully!"
    $MSG_BOTO_FAIL = "Could not automatically install boto3 via pip. The native AWS CLI fallback will continue to be used."

    $env:LANG_RULE_TEXT = "CRITICAL LANGUAGE RULE: You MUST ALWAYS interact with the user and render the visual alerts exclusively in English."
    $env:ALERT_TPL_TEXT = "🚨 **[RISK ACTION / MUTATION ALERT]** 🚨`n> [EMOJI] [Ultra-layman and direct explanation of what the command will do, e.g., `"This will destroy the production pod`"]. Warning [EMOJI]`n`n* **Command:** ``[exact command]```n* **Environment:** ``[Resource / Cluster / Account]```n* **Impact:** ``[What will be affected/interrupted right now]```n* **Reversible?** ``[Yes / No]```n"
}

$REPO_DIR = $PSScriptRoot
$KIRO_DIR = if ($env:KIRO_DIR) { $env:KIRO_DIR } else { Join-Path $HOME ".kiro" }
$AGENT_NAME = "noc-guard"
$AGENT_FILE = Join-Path $KIRO_DIR "agents\$AGENT_NAME.json"
$GEN_FILE = Join-Path $KIRO_DIR "noc-guard\generate_allowlist.py"
$STEERING_FILE = Join-Path $KIRO_DIR "noc-guard\steering\noc-readonly-first.md"
$LEGACY_STEERING = Join-Path $KIRO_DIR "steering\noc-readonly-first.md"
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

# 1. Identifica o que esta faltando antes
$missingEssential = @()
$missingOptional = @()

if (-not $hasPython) {
    $missingEssential += "python"
}

$WINGET_MAP = @{
    "python"  = "Python.Python.3.12"
    "aws"     = "Amazon.AWSCLI"
    "kubectl" = "Kubernetes.kubectl"
    "docker"  = "Docker.DockerDesktop"
    "jq"      = "jqlang.jq"
}

foreach ($opt in @("aws", "kubectl", "docker", "jq")) {
    if (-not (Get-Command $opt -ErrorAction SilentlyContinue)) {
        $missingOptional += $opt
    }
}

$hasBoto = $false
if ($hasPython) {
    $testBoto = python -c "import boto3; print('ok')" 2>$null
    if ($testBoto -eq "ok") { $hasBoto = $true }
}
if (-not $hasBoto) {
    $missingOptional += "boto3"
}

# Se houver itens ausentes, exibe resumo detalhado e pergunta se quer instalar
if ($missingEssential.Count -gt 0 -or $missingOptional.Count -gt 0) {
    Write-Host ""
    Write-Host "  AVISO: $MSG_MISSING_NOTICE" -ForegroundColor Yellow
    if ($missingEssential.Count -gt 0) {
        Write-Host "  - $MSG_MISSING_ESSENTIAL $($missingEssential -join ', ')" -ForegroundColor Red
    }
    if ($missingOptional.Count -gt 0) {
        Write-Host "  - $MSG_MISSING_OPTIONAL $($missingOptional -join ', ')" -ForegroundColor Cyan
    }
    Write-Host ""

    if (-not $Yes) {
        $respAuto = Read-Host "  $MSG_AUTO_INSTALL_PROMPT"
        if ($respAuto -match "^[sSyY]") {
            $hasWinget = (Get-Command "winget" -ErrorAction SilentlyContinue)
            if ($hasWinget) {
                foreach ($item in ($missingEssential + $missingOptional)) {
                    if ($item -eq "boto3") {
                        if ($hasPython -or (Get-Command "python" -ErrorAction SilentlyContinue)) {
                            Say ($MSG_INSTALLING_PKG -f "boto3 via pip")
                            Start-Process python -ArgumentList "-m pip install boto3 --quiet" -NoNewWindow -Wait
                        }
                    } else {
                        $pkg = $WINGET_MAP[$item]
                        if ($pkg) {
                            Say ($MSG_INSTALLING_PKG -f "$item ($pkg)")
                            Start-Process winget -ArgumentList "install --id $pkg -e --accept-package-agreements --accept-source-agreements" -NoNewWindow -Wait
                        }
                    }
                }
                # Recarrega PATH para detectar os novos binarios na sessao atual
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            } else {
                Write-Host "  AVISO: winget nao encontrado para instalacao automatica." -ForegroundColor Yellow
            }
        }
    }
}

# 2. Exibicao final dos pre-requisitos
$hasPython = $false
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    if ((python --version 2>&1) -match "Python") { $hasPython = $true }
}
if (-not $hasPython -and (Get-Command "python3" -ErrorAction SilentlyContinue)) {
    if ((python3 --version 2>&1) -match "Python") {
        Set-Alias python python3
        $hasPython = $true
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

$hasBoto = python -c "import boto3; print('ok')" 2>$null
if ($hasBoto -eq "ok") {
    Say "boto3        $MSG_OPT_OK"
} else {
    Say "boto3        nao instalado (search_trail usara fallback nativo da AWS CLI)"
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

# Knowledge Base (Optional)
Step $MSG_KB_TITLE

$KB_CONFIG_FILE = Join-Path $KIRO_DIR "noc-guard\.kb_bucket"
$EXISTING_BUCKET = ""
if (Test-Path $KB_CONFIG_FILE) {
    $EXISTING_BUCKET = (Get-Content $KB_CONFIG_FILE -Raw).Trim()
} elseif (Test-Path $STEERING_FILE) {
    $match = Select-String -Path $STEERING_FILE -Pattern '--bucket\s+([a-z0-9.-]+)'
    if ($match -and $match.Matches.Groups.Count -gt 1) {
        $EXISTING_BUCKET = $match.Matches.Groups[1].Value
    }
}

$KB_BUCKET = ""
if ($EXISTING_BUCKET) {
    Say ($MSG_KB_EXISTING -f $EXISTING_BUCKET)
    if (-not $Yes) {
        $KEEP_ANS = (Read-Host ($MSG_KB_KEEP_PROMPT -f $EXISTING_BUCKET)).Trim()
        if ([string]::IsNullOrWhiteSpace($KEEP_ANS) -or $KEEP_ANS -match '^[sSyY]') {
            $KB_BUCKET = $EXISTING_BUCKET
            Say "ok: mantendo bucket -> $KB_BUCKET"
        } elseif ($KEEP_ANS -match '^[tTcC]') {
            while ($true) {
                $BUCKET_INPUT = (Read-Host "$MSG_KB_PROMPT").Trim()
                if ([string]::IsNullOrWhiteSpace($BUCKET_INPUT)) {
                    Say $MSG_KB_SKIPPED
                    break
                }
                if ($BUCKET_INPUT -match '^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$' -and -not ($BUCKET_INPUT.Contains(".."))) {
                    $KB_BUCKET = $BUCKET_INPUT
                    Say "ok: bucket configurado -> $KB_BUCKET"
                    break
                } else {
                    Write-Host "  AVISO: $MSG_KB_INVALID" -ForegroundColor Yellow
                }
            }
        } else {
            Say $MSG_KB_SKIPPED
            if (Test-Path $KB_CONFIG_FILE) { Remove-Item $KB_CONFIG_FILE -Force }
        }
    } else {
        $KB_BUCKET = $EXISTING_BUCKET
        Say "ok: mantendo bucket configurado -> $KB_BUCKET"
    }
} else {
    Say $MSG_KB_DESC
    $ENABLE_KB_ANS = Read-Host "$MSG_KB_ENABLE"
    if ($ENABLE_KB_ANS -match '^[sSyY]') {
        while ($true) {
            $BUCKET_INPUT = (Read-Host "$MSG_KB_PROMPT").Trim()
            if ([string]::IsNullOrWhiteSpace($BUCKET_INPUT)) {
                Say $MSG_KB_SKIPPED
                break
            }
            if ($BUCKET_INPUT -match '^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$' -and -not ($BUCKET_INPUT.Contains(".."))) {
                $KB_BUCKET = $BUCKET_INPUT
                Say "ok: bucket configurado -> $KB_BUCKET"
                break
            } else {
                Write-Host "  AVISO: $MSG_KB_INVALID" -ForegroundColor Yellow
            }
        }
    } else {
        Say $MSG_KB_SKIPPED
    }
}

if ($KB_BUCKET) {
    $nocGuardDir = Join-Path $KIRO_DIR "noc-guard"
    if (-not (Test-Path $nocGuardDir)) { New-Item -ItemType Directory -Path $nocGuardDir -Force | Out-Null }
    Set-Content -Path $KB_CONFIG_FILE -Value $KB_BUCKET -Encoding utf8
    if ($langChoice -eq "1") {
        $env:KB_DIRECTIVE_TEXT = "- To query or record learnings in the shared NOC Knowledge Base / Runbooks, use: ``python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket $KB_BUCKET``. Whenever you successfully diagnose a complex root cause, run ``kb_manager.py --action add`` to auto-document the resolution."
    } else {
        $env:KB_DIRECTIVE_TEXT = "- Para consultar ou registrar aprendizados na Base de Conhecimento / Runbooks compartilhados da equipe, utilize o script: ``python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket $KB_BUCKET``. Sempre que diagnosticar com sucesso a causa raiz de um incidente complexo, execute ``kb_manager.py --action add`` para auto-documentar a resolucao."
    }
} else {
    $env:KB_DIRECTIVE_TEXT = ""
}

# Directories
Step "$MSG_MKDIR $KIRO_DIR"
foreach ($d in @("agents", "noc-guard", "noc-guard\steering", "noc-guard\skills\cloudtrail-search", "noc-guard\skills\knowledge-builder", "noc-guard\kb")) {
    $dPath = Join-Path $KIRO_DIR $d
    if (-not (Test-Path $dPath)) { New-Item -ItemType Directory -Path $dPath -Force | Out-Null }
    Say $dPath
}

# Limpeza de steering legado na pasta global que afetava outros agentes (ex: kiro_default)
if (Test-Path $LEGACY_STEERING) {
    Remove-Item $LEGACY_STEERING -Force
    Say "limpeza: removido steering legado global em $LEGACY_STEERING"
}

# Limpeza de skills legadas na pasta global
$LEGACY_CT = Join-Path $KIRO_DIR "skills\cloudtrail-search\search_trail.py"
if (Test-Path $LEGACY_CT) {
    Remove-Item $LEGACY_CT -Force
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
$SKILL_CT = Join-Path $KIRO_DIR "noc-guard\skills\cloudtrail-search\search_trail.py"
Copy-Item (Join-Path $REPO_DIR "skills\cloudtrail-search\search_trail.py") $SKILL_CT -Force
Say "skill (cloudtrail) -> $SKILL_CT"
$SKILL_KB = Join-Path $KIRO_DIR "noc-guard\skills\knowledge-builder\kb_manager.py"
Copy-Item (Join-Path $REPO_DIR "skills\knowledge-builder\kb_manager.py") $SKILL_KB -Force
Say "skill (knowledge)  -> $SKILL_KB"

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
if '__KB_DIRECTIVE__' in content:
    content = content.replace('__KB_DIRECTIVE__', os.environ.get('KB_DIRECTIVE_TEXT', ''))
p.write_text(content, encoding='utf-8')
"@

foreach ($f in @($STEERING_FILE, $GEN_FILE, $NEW_AGENT)) {
    $content = Get-Content $f -Raw -Encoding UTF8
    if ($content -match "__HOME__|__LANGUAGE_RULE__|__KB_DIRECTIVE__") {
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
