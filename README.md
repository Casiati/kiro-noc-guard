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
A segurança do guard é garantida pelo gerador `generate_allowlist.py`, que roda uma suíte com mais de 220 testes automatizados para certificar que não há vulnerabilidades de bypass.
```bash
# Rodar a suíte de testes (sem alterar o agente)
python3 scripts/generate_allowlist.py --check
```
Se precisar liberar um novo comando de leitura, adicione-o no gerador (`generate_allowlist.py`) e rode os testes. Isso garante que injeções perigosas continuem bloqueadas e seu ambiente seguro.

---

## 🇺🇸 kiro-noc-guard (EN)

Incident-response focused agent for [Kiro CLI](https://kiro.dev), tuned for fast read-only diagnostics and heavily restricted state mutations.

In incident triage, confirming every read tool costs time, but granting full trust (`--trust-all-tools`) is an operational risk (e.g., a confidently suggested `aws ec2 terminate-instances`). This project solves this using strict, thoroughly tested allowlists.

### ✨ Key Features
- **Smart Auto-installer**: Detects missing dependencies and offers automatic installation via `winget`, `apt-get`, `dnf` or `pip`. Works seamlessly on Windows (PowerShell) and Linux/macOS.
- **S3 Knowledge Base**: Sync and automatically search Markdown runbooks stored securely in an S3 bucket. The agent learns from your private procedures without exposing data.
- **CloudTrail Skill**: A fast, resilient Python script (`search_trail.py`) for optimized AWS CloudTrail searches, featuring automatic fallback if `boto3` is not installed.

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
Security is enforced by the python generator (`generate_allowlist.py`), containing 220+ automated test cases to prevent bypass vulnerabilities.
```bash
# Run test suite to validate rules (dry-run)
python3 scripts/generate_allowlist.py --check
```
When adding a new allowed command, modify the python script and re-run the tests. This ensures edge cases like `good-command && rm -rf /` remain securely blocked.
