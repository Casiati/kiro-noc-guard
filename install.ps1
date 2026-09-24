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
    $MSG_KB_PROFILE_DESC = "O bucket da Base de Conhecimento costuma estar numa conta AWS separada da conta de cada cliente/incidente investigado. Se o profile usado na investigacao nao tiver acesso a esse bucket, informe aqui o profile AWS (de ~/.aws/config) dedicado a essa conta - deixe em branco para usar o profile padrao do ambiente (AWS_PROFILE/default)."
    $MSG_KB_PROFILE_EXISTING = "Profile AWS configurado atualmente para a Base de Conhecimento: {0}"
    $MSG_KB_PROFILE_KEEP_PROMPT = "Deseja manter o profile atual [{0}]? [S/n/trocar] (Enter para manter): "
    $MSG_KB_PROFILE_PROMPT = "Informe o nome do profile AWS para acessar o bucket da KB (Enter para nao usar nenhum e cair no padrao do ambiente): "
    $MSG_KB_PROFILE_SET = "ok: profile da KB configurado -> {0}"
    $MSG_KB_PROFILE_SKIPPED = "Nenhum profile dedicado configurado para a KB - usara o padrao do ambiente (AWS_PROFILE/default)."

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
    $MSG_KB_PROFILE_DESC = "The Knowledge Base bucket usually lives in an AWS account separate from each client/incident account being investigated. If the profile used during the investigation lacks access to that bucket, enter here the AWS profile (from ~/.aws/config) dedicated to that account - leave blank to use the environment's default profile (AWS_PROFILE/default)."
    $MSG_KB_PROFILE_EXISTING = "Currently configured AWS profile for the Knowledge Base: {0}"
    $MSG_KB_PROFILE_KEEP_PROMPT = "Keep current profile [{0}]? [Y/n/change] (Enter to keep): "
    $MSG_KB_PROFILE_PROMPT = "Enter the AWS profile name to access the KB bucket (Enter to use none and fall back to the environment default): "
    $MSG_KB_PROFILE_SET = "ok: KB profile configured -> {0}"
    $MSG_KB_PROFILE_SKIPPED = "No dedicated profile configured for the KB - will use the environment default (AWS_PROFILE/default)."

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
# $PY_CMD guarda o nome real do executavel Python resolvido ('python' ou
# 'python3'). Nao usamos Set-Alias aqui: Start-Process resolve o executavel
# via Process.Start() do .NET (PATH do sistema operacional), que NAO respeita
# aliases do PowerShell engine — em maquinas onde so existe python3.exe, um
# Set-Alias funcionaria para chamadas diretas mas falharia silenciosamente em
# qualquer Start-Process python (o executavel nao seria encontrado).
$PY_CMD = $null
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    if ((python --version 2>&1) -match "Python") {
        $PY_CMD = "python"
    }
}
if (-not $PY_CMD -and (Get-Command "python3" -ErrorAction SilentlyContinue)) {
    if ((python3 --version 2>&1) -match "Python") {
        $PY_CMD = "python3"
    }
}
$hasPython = [bool]$PY_CMD

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
    $testBoto = & $PY_CMD -c "import boto3; print('ok')" 2>$null
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
                        if ($PY_CMD) {
                            Say ($MSG_INSTALLING_PKG -f "boto3 via pip")
                            # Chamada direta (nao Start-Process): usa o $PY_CMD resolvido
                            # de fato e herda stdout/stderr do console atual.
                            & $PY_CMD -m pip install boto3 --quiet
                        }
                    } else {
                        $pkg = $WINGET_MAP[$item]
                        if ($pkg) {
                            Say ($MSG_INSTALLING_PKG -f "$item ($pkg)")
                            # Chamada direta: herda stdout/stderr do console
                            # (winget e um comando unico, sem alias envolvido,
                            # mas Start-Process sem redirecionamento ainda
                            # ocultaria erros de instalacao do usuario).
                            winget install --id $pkg -e --accept-package-agreements --accept-source-agreements
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

# 2. Exibicao final dos pre-requisitos (reavalia apos possivel instalacao via winget)
$PY_CMD = $null
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    if ((python --version 2>&1) -match "Python") { $PY_CMD = "python" }
}
if (-not $PY_CMD -and (Get-Command "python3" -ErrorAction SilentlyContinue)) {
    if ((python3 --version 2>&1) -match "Python") { $PY_CMD = "python3" }
}
$hasPython = [bool]$PY_CMD
if (-not $hasPython) {
    Die $MSG_NO_PY
}
$pyver = (& $PY_CMD --version 2>&1)
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

$hasBoto = & $PY_CMD -c "import boto3; print('ok')" 2>$null
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
    "agents\noc-guard.json.template",
    "skills\stop-hook\kb_reminder.py"
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

# Profile AWS da KB (opcional) - independente do bucket: o profile usado para
# acessar o bucket da KB e tipicamente distinto do profile resolvido para
# cada cliente/incidente investigado (contas AWS diferentes). Persistido
# separadamente do bucket para permitir trocar um sem afetar o outro; e
# sempre OPCIONAL - sem ele, kb_manager.py cai no comportamento padrao
# (AWS_PROFILE/default do ambiente).
$KB_PROFILE_CONFIG_FILE = Join-Path $KIRO_DIR "noc-guard\.kb_profile"
$EXISTING_KB_PROFILE = ""
if ($KB_BUCKET -and (Test-Path $KB_PROFILE_CONFIG_FILE)) {
    $EXISTING_KB_PROFILE = (Get-Content $KB_PROFILE_CONFIG_FILE -Raw).Trim()
}

$KB_PROFILE = ""
if ($KB_BUCKET) {
    if ($EXISTING_KB_PROFILE) {
        Say ($MSG_KB_PROFILE_EXISTING -f $EXISTING_KB_PROFILE)
        if (-not $Yes) {
            $KEEP_PROFILE_ANS = (Read-Host ($MSG_KB_PROFILE_KEEP_PROMPT -f $EXISTING_KB_PROFILE)).Trim()
            if ([string]::IsNullOrWhiteSpace($KEEP_PROFILE_ANS) -or $KEEP_PROFILE_ANS -match '^[sSyY]') {
                $KB_PROFILE = $EXISTING_KB_PROFILE
                Say ($MSG_KB_PROFILE_SET -f $KB_PROFILE)
            } elseif ($KEEP_PROFILE_ANS -match '^[tTcC]') {
                $PROFILE_INPUT = (Read-Host "$MSG_KB_PROFILE_PROMPT").Trim()
                if ($PROFILE_INPUT) {
                    $KB_PROFILE = $PROFILE_INPUT
                    Say ($MSG_KB_PROFILE_SET -f $KB_PROFILE)
                } else {
                    Say $MSG_KB_PROFILE_SKIPPED
                    if (Test-Path $KB_PROFILE_CONFIG_FILE) { Remove-Item $KB_PROFILE_CONFIG_FILE -Force }
                }
            } else {
                Say $MSG_KB_PROFILE_SKIPPED
                if (Test-Path $KB_PROFILE_CONFIG_FILE) { Remove-Item $KB_PROFILE_CONFIG_FILE -Force }
            }
        } else {
            $KB_PROFILE = $EXISTING_KB_PROFILE
            Say ($MSG_KB_PROFILE_SET -f $KB_PROFILE)
        }
    } else {
        Say $MSG_KB_PROFILE_DESC
        if (-not $Yes) {
            $PROFILE_INPUT = (Read-Host "$MSG_KB_PROFILE_PROMPT").Trim()
            if ($PROFILE_INPUT) {
                $KB_PROFILE = $PROFILE_INPUT
                Say ($MSG_KB_PROFILE_SET -f $KB_PROFILE)
            } else {
                Say $MSG_KB_PROFILE_SKIPPED
            }
        } else {
            Say $MSG_KB_PROFILE_SKIPPED
        }
    }
}

if ($KB_PROFILE) {
    $nocGuardDir = Join-Path $KIRO_DIR "noc-guard"
    if (-not (Test-Path $nocGuardDir)) { New-Item -ItemType Directory -Path $nocGuardDir -Force | Out-Null }
    [System.IO.File]::WriteAllText($KB_PROFILE_CONFIG_FILE, $KB_PROFILE, [System.Text.UTF8Encoding]::new($false))
}

if ($KB_BUCKET) {
    $nocGuardDir = Join-Path $KIRO_DIR "noc-guard"
    if (-not (Test-Path $nocGuardDir)) { New-Item -ItemType Directory -Path $nocGuardDir -Force | Out-Null }
    # Set-Content -Encoding utf8 grava BOM no Windows PowerShell 5.1 (qualquer encoding
    # Unicode exceto UTF7 sempre cria BOM nessa versao). O BOM (U+FEFF) nao e removido
    # por .Trim() na releitura via Get-Content -Raw, contaminando $EXISTING_BUCKET em
    # reinstalacoes futuras. [System.IO.File]::WriteAllText com UTF8Encoding($false)
    # grava sem BOM de forma identica em PS 5.1 e PS 7+.
    [System.IO.File]::WriteAllText($KB_CONFIG_FILE, $KB_BUCKET, [System.Text.UTF8Encoding]::new($false))
    $KB_PROFILE_FLAG = ""
    if ($KB_PROFILE) {
        $KB_PROFILE_FLAG = " --kb-profile $KB_PROFILE"
    }
    if ($LANG_CHOICE -ne "2") {
        $env:KB_DIRECTIVE_TEXT = "## Final Checklist - Knowledge Base (NEXT)``n``nBefore ending EVERY response where you investigated an AWS/K8s/infra incident, check:``n``n1. Did this investigation involve 3+ read commands (AWS/logs/metrics/kubectl) AND did you reach an explicit conclusion (root cause identified, OR confirmed false positive, OR clear recommendation)?``n2. If YES to #1: your NEXT action, before finishing, MUST be running ``python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket $KB_BUCKET$KB_PROFILE_FLAG --action add --alert `"<short alert/topic name>`" --content `"<concise summary: root cause, evidence, recommendation>`"``. Do this silently as part of your workflow, then mention in your final answer that the finding was recorded.``n3. If NO (quick lookup, single command, no conclusion reached): skip this step, no need to mention it.``n``nTo search the Knowledge Base for prior similar incidents, use: ``python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket $KB_BUCKET$KB_PROFILE_FLAG --action search --query `"<term>`"``."
    } else {
        $env:KB_DIRECTIVE_TEXT = "## Checklist Final - Base de Conhecimento (PROXIMO PASSO)``n``nAntes de finalizar TODA resposta em que voce investigou um incidente de AWS/K8s/infra, verifique:``n``n1. Essa investigacao envolveu 3 ou mais comandos de leitura (AWS/logs/metricas/kubectl) E voce chegou a uma conclusao explicita (causa raiz identificada, OU falso positivo confirmado, OU recomendacao clara)?``n2. Se SIM ao item 1: sua PROXIMA acao, antes de terminar, DEVE ser executar ``python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket $KB_BUCKET$KB_PROFILE_FLAG --action add --alert `"<nome curto do alerta/topico>`" --content `"<resumo conciso: causa raiz, evidencias, recomendacao>`"``. Faca isso silenciosamente como parte do seu fluxo, depois mencione na resposta final que o achado foi registrado.``n3. Se NAO (consulta rapida, comando unico, sem conclusao): pule esta etapa, sem necessidade de mencion-la.``n``nPara pesquisar na Base de Conhecimento por incidentes semelhantes anteriores, utilize: ``python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket $KB_BUCKET$KB_PROFILE_FLAG --action search --query `"<termo>`"``."
    }
} else {
    $env:KB_DIRECTIVE_TEXT = ""
}

# Directories
Step "$MSG_MKDIR $KIRO_DIR"
foreach ($d in @("agents", "noc-guard", "noc-guard\steering", "noc-guard\skills\cloudtrail-search", "noc-guard\skills\knowledge-builder", "noc-guard\skills\stop-hook", "noc-guard\kb")) {
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
$SKILL_HOOK = Join-Path $KIRO_DIR "noc-guard\skills\stop-hook\kb_reminder.py"
Copy-Item (Join-Path $REPO_DIR "skills\stop-hook\kb_reminder.py") $SKILL_HOOK -Force
Say "hook (stop)  -> $SKILL_HOOK"

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
        $py_script | & $PY_CMD - $f $HOME_FWD
        Say "-> configured variables in $(Split-Path $f -Leaf)"
    }
}
Say $MSG_PATHS_OK

# Tests + Allowlist
Step $MSG_RUN_TESTS
# Chamada direta (nao Start-Process): usa o $PY_CMD resolvido de fato, herda
# stdout/stderr do console atual (evita silenciar a saida de testes/falhas —
# Start-Process sem -RedirectStandardOutput/-RedirectStandardError descarta
# tudo que o processo filho imprime) e permite checar $LASTEXITCODE direto.
& $PY_CMD $GEN_FILE --agent $NEW_AGENT
if ($LASTEXITCODE -ne 0) {
    Remove-Item $NEW_AGENT -ErrorAction SilentlyContinue
    Die $MSG_ERR_TESTS
}

$py_val = @"
import json, sys, pathlib
cfg = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
sh = cfg['toolsSettings']['shell']
print(f"  AUTO: {len(sh['allowedCommands'])} | DENY: {len(sh['deniedCommands'])} | TOOLS: {len(cfg['allowedTools'])}")
"@
$py_val | & $PY_CMD - $NEW_AGENT

# Validation
if ($HAS_KIRO) {
    Step $MSG_VAL_KIRO
    # Chamada direta: herda stdout/stderr do console (Start-Process sem
    # redirecionamento explicito descartaria a saida de 'kiro-cli agent validate',
    # ocultando do usuario o motivo exato de uma eventual rejeicao de config).
    kiro-cli agent validate --path $NEW_AGENT
    if ($LASTEXITCODE -eq 0) {
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
