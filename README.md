# kiro-noc-guard

[![Latest Release](https://img.shields.io/github/v/release/Casiati/kiro-noc-guard?color=blue&logo=github)](https://github.com/Casiati/kiro-noc-guard/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[🇧🇷 Leia em Português](#-kiro-noc-guard-pt-br) | [🇺🇸 Read in English](#-kiro-noc-guard-en)

## 🇧🇷 kiro-noc-guard (PT-BR)

Agente focado em incidentes para o [Kiro CLI](https://kiro.dev), configurado para ser ágil na leitura (diagnósticos) e extremamente seguro na mutação.

Em triagem de incidentes, confirmar cada comando de leitura custa tempo, mas liberar todas as permissões (`--trust-all-tools`) transforma o assistente num risco (ex: um `aws ec2 terminate-instances` sugerido com confiança). Este projeto resolve isso com listas de permissão estritas e extensamente testadas.

### ✨ Principais Funcionalidades
- **Auto-instalador Inteligente**: Detecta dependências ausentes e oferece instalação via `winget`, `apt-get`, `dnf` ou `pip`. Suporta Windows (PowerShell) e Linux/macOS.
- **S3 Knowledge Base**: Faça buscas automáticas em runbooks Markdown armazenados no S3. O agente aprende com seus procedimentos internos de forma nativa e sem expor dados.
- **CloudTrail Skill**: Um script Python (`search_trail.py`) ultrarrápido para buscas no AWS CloudTrail, com fallback automático integrado caso o pacote `boto3` não exista.
- **Logs Search Skill**: `logs_search.py` consulta o CloudWatch Logs em modo somente leitura e devolve saída agregada e compacta (economiza tokens): `k8s-audit` (deploys/rollouts/scale e, com `--status`, Ready/restarts dos pods via audit log do EKS), `k8s-events` (eventos do Kubernetes sem precisar de kubeconfig) `logs` (logs de aplicação com agregação local) e `sources` (descobre onde estão os logs). Custo zero: usa só APIs gratuitas (FilterLogEvents/Describe*), nunca Logs Insights.
- **Validador de Skills**: `validate_skills.py` audita estaticamente cada skill (frontmatter, mutação não supervisionada, APIs cobradas e contenção de tokens) antes de qualquer execução.
- **Token Containment**: o steering obriga o agente a filtrar logs e saídas na origem, medir o volume antes de ler e limitar a ~50 linhas, reduzindo custo e ruído no contexto.

### 🛡️ Arquitetura de Segurança (As 3 Camadas)

O Kiro CLI avalia as chamadas nesta ordem: `DENY` → `AUTO` → `PROMPT`.

#### 1. AUTO — Roda sem confirmação
Ferramentas de leitura e consultas rodam direto, garantindo agilidade no troubleshooting.
- **Shell**: Mais de 100 padrões cobrindo Texto/Log (`cat, grep, rg, jq`), Filesystem (`ls, df, find`), Sistema (`ps, free, lsof`), Rede (`curl, ping, dig`), Serviços (`systemctl status`), Containers (`docker ps, kubectl get/logs/describe`).
- **AWS CLI**: Somente verbos seguros: `describe-*, get-*, list-*, filter-*, lookup-*, query-*`, `s3 ls`, `logs tail`.
- **Encadeamento Seguro**: Pipes (`|`) e lógicos (`&&`, `;`) são permitidos **somente** entre comandos que já são de leitura (ex: `cat log | grep ERROR` passa direto; `cat log && rm -f file` é barrado).

#### 2. PROMPT — Exige aprovação explícita (y/N)
Qualquer comando de mutação ou escrita pausa a execução. Mesmo que seu profile AWS tenha permissão de admin, o Kiro vai exigir um "sim" explícito para:
- Escrita local: `rm, touch, cp, mv, sed -i, >`
- Mutação Nuvem/Infra: `aws ec2 terminate-instances`, `aws s3 cp`, `kubectl delete/exec`, `docker exec`, `systemctl restart`, `git push`.

#### 3. DENY — Bloqueio duro
Comandos catastróficos que nem sequer oferecem a opção de confirmação:
- `rm -rf /`, `mkfs`, fork bombs (`:(){...};:`), escapes perigosos de shell (`$(...)`).

### 🚀 Instalação

```bash
git clone https://github.com/Casiati/kiro-noc-guard.git
cd kiro-noc-guard

# Windows (PowerShell):
Set-ExecutionPolicy Bypass -Scope Process -Force; .\install.ps1

# Linux / macOS / Git Bash:
./install.sh
```
*O instalador cria a estrutura em `~/.kiro/noc-guard`, checa requisitos, roda os testes de segurança e só então grava a configuração do agente.*
*(Ou baixe o pacote pronto diretamente na [página de Releases](https://github.com/Casiati/kiro-noc-guard/releases/latest)).*

### 🛠️ Como testar e auditar regras
A segurança do guard é garantida pelo gerador `generate_allowlist.py`, que roda uma suíte com mais de 290 testes automatizados para certificar que não há vulnerabilidades de bypass.
```bash
# Rodar a suíte de testes (sem alterar o agente)
python3 scripts/generate_allowlist.py --check
```
Se precisar liberar um novo comando de leitura, adicione-o no gerador (`generate_allowlist.py`) e rode os testes. Isso garante que injeções perigosas continuem bloqueadas e seu ambiente seguro.

### 🧩 Validação das skills
Cada skill em `skills/<nome>/` tem um `SKILL.md` (frontmatter `name`/`description` + documentação). O linter `validate_skills.py` verifica, sem executar nada: frontmatter válido, ausência de mutação não supervisionada nos scripts (SDK `delete_*`/`put_*`..., `aws ... delete-*`, `aws s3 sync/cp/rm`, `kubectl delete/apply/rollout restart`, escrita/remoção em disco, `shell=True`), APIs cobradas (Logs Insights, Live Tail, `GetMetricData`, Athena — sem exceção) e contenção de tokens (consultas a `FilterLogEvents`/`LookupEvents`/`GetLogEvents` precisam de limite ou teto de resultados).
```bash
python3 scripts/validate_skills.py         # exit 0 = conforme
python3 scripts/test_validate_skills.py    # testes do validador
python3 scripts/test_allowlist.py          # suíte de allowlist como unittest
```
Escritas legítimas e restritas ao escopo da própria skill (ex.: cache e bucket da KB) devem ser marcadas com `# noc-guard: allow-mutation: <motivo>` na mesma linha ou na anterior; o validador as lista como `NOTE` para auditoria.

---

## 🇺🇸 kiro-noc-guard (EN)

Incident-response focused agent for [Kiro CLI](https://kiro.dev), tuned for fast read-only diagnostics and heavily restricted state mutations.

In incident triage, confirming every read tool costs time, but granting full trust (`--trust-all-tools`) is an operational risk (e.g., a confidently suggested `aws ec2 terminate-instances`). This project solves this using strict, thoroughly tested allowlists.

### ✨ Key Features
- **Smart Auto-installer**: Detects missing dependencies and offers automatic installation via `winget`, `apt-get`, `dnf` or `pip`. Works seamlessly on Windows (PowerShell) and Linux/macOS.
- **S3 Knowledge Base**: Sync and automatically search Markdown runbooks stored securely in an S3 bucket. The agent learns from your private procedures without exposing data.
- **CloudTrail Skill**: A fast, resilient Python script (`search_trail.py`) for optimized AWS CloudTrail searches, featuring automatic fallback if `boto3` is not installed.
- **Logs Search Skill**: `logs_search.py` queries CloudWatch Logs read-only and returns compact, aggregated output (saves tokens): `k8s-audit` (deploys/rollouts/scaling and, with `--status`, pod Ready/restarts from the EKS audit log), `k8s-events` (Kubernetes events without a kubeconfig) `logs` (application logs with local aggregation) and `sources` (discovers where the logs are). Zero cost: free APIs only (FilterLogEvents/Describe*), never Logs Insights.
- **Skill Validator**: `validate_skills.py` statically audits every skill (frontmatter, unsupervised mutation, billed APIs and token containment) before anything runs.
- **Token Containment**: the steering makes the agent filter logs and output at the source, size before reading and cap reads at ~50 lines, cutting cost and context noise.

### 🛡️ Security Architecture (The 3 Tiers)

The agent evaluates tool calls in this order: `DENY` → `AUTO` → `PROMPT`.

#### 1. AUTO — No confirmation required
Read-only utilities and queries execute instantly for fast troubleshooting.
- **Shell**: Over 100 patterns covering Text/Logs (`cat, grep, rg, jq`), Filesystem (`ls, df, find`), System (`ps, free, lsof`), Network (`curl, ping, dig`), Services (`systemctl status`), and Containers (`docker ps, kubectl get/logs/describe`).
- **AWS CLI**: Safe verbs only: `describe-*, get-*, list-*, filter-*, lookup-*, query-*`, `s3 ls`, `logs tail`.
- **Safe Chaining**: Pipes (`|`) and logical operators (`&&`, `;`) are allowed **ONLY** between read-only commands (e.g., `cat log | grep ERROR` runs; `cat log && rm -f file` is blocked).

#### 2. PROMPT — Requires explicit `[y/N]` approval
Any mutating command pauses execution. Even if your AWS profile holds write permissions, the agent will pause for:
- Local writes: `rm, touch, cp, mv, sed -i, >`
- Cloud/Infra mutation: `aws ec2 terminate-instances`, `aws s3 cp`, `kubectl delete/exec`, `docker exec`, `systemctl restart`, `git push`.

#### 3. DENY — Hard block
Catastrophic local commands are rejected completely without a prompt:
- `rm -rf /`, `mkfs`, fork bombs (`:(){...};:`), command substitutions (`$(...)`).

### 🚀 Quick Install

```bash
git clone https://github.com/Casiati/kiro-noc-guard.git
cd kiro-noc-guard

# Windows (PowerShell):
Set-ExecutionPolicy Bypass -Scope Process -Force; .\install.ps1

# Linux / macOS / Git Bash:
./install.sh
```
*The installer creates the `~/.kiro/noc-guard` isolation structure, checks prerequisites, runs the test suite, and then safely scaffolds the config.*
*(Or download the pre-packaged archive directly from the [Releases page](https://github.com/Casiati/kiro-noc-guard/releases/latest)).*

### 🛠️ Testing & Modifying Rules
Security is enforced by the python generator (`generate_allowlist.py`), containing 290+ automated test cases to prevent bypass vulnerabilities.
```bash
# Run test suite to validate rules (dry-run)
python3 scripts/generate_allowlist.py --check
```
When adding a new allowed command, modify the python script and re-run the tests. This ensures edge cases like `good-command && rm -rf /` remain securely blocked.

### 🧩 Skill Validation
Each skill in `skills/<name>/` ships a `SKILL.md` (`name`/`description` frontmatter + docs). The `validate_skills.py` linter statically checks: valid frontmatter, no unsupervised mutation in skill scripts (SDK `delete_*`/`put_*`..., `aws ... delete-*`, `aws s3 sync/cp/rm`, `kubectl delete/apply/rollout restart`, disk writes/removals, `shell=True`), billed APIs (Logs Insights, Live Tail, `GetMetricData`, Athena — never allowed) and token containment (`FilterLogEvents`/`LookupEvents`/`GetLogEvents` calls need a limit or an explicit result cap).
```bash
python3 scripts/validate_skills.py         # exit 0 = compliant
python3 scripts/test_validate_skills.py    # validator tests
python3 scripts/test_allowlist.py          # allowlist suite as unittest
```
Legitimate writes scoped to the skill itself (e.g. the KB cache and bucket) must be tagged with `# noc-guard: allow-mutation: <reason>` on the same or previous line; the validator lists them as `NOTE` for auditing.
