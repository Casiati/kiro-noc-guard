# kiro-noc-guard

Agente **read-only** para o [Kiro CLI](https://kiro.dev) voltado a analise de incidentes:
diagnóstico e análise intensiva de logs e métricas **sem prompt de aprovação a cada
comando**, com trava explícita para qualquer coisa que altere estado.

## Visão geral

Em triagem de incidente, cada confirmação de tool custa tempo. Mas liberar tudo
(`--trust-all-tools`) transforma o assistente em risco operacional: basta um `rm -rf`
ou um `aws ec2 terminate-instances` sugerido com confiança.

Este projeto resolve os dois lados com um allowlist **explícito e testado** de comandos
de leitura, mais um denylist de bloqueio duro. O resultado:

- Consultas de log, métrica, estado de recurso e pipelines de shell rodam direto.
- Mutação (`create/delete/update/put/modify/terminate/start/stop/reboot`, `rm`,
  `systemctl restart`, `kubectl delete`, escrita em disco) **para e pede seu "sim"**,
  mesmo que o profile AWS tenha permissão de escrita.
- Um punhado de comandos catastróficos locais é bloqueado de forma dura, sem opção
  de confirmar.

O que é versionado aqui: a config do agente, a diretriz de comportamento (*steering*)
e o gerador das listas de permissão com sua suíte de testes.

## Arquitetura de segurança (as 3 camadas)

O Kiro CLI avalia, para cada chamada de ferramenta, nesta ordem:
`deniedCommands` → `allowedCommands` → default (pedir aprovação). Bloqueio vence
liberação (verificado empiricamente, não só pela documentação).

### 1. AUTO — executa sem confirmação

Ferramentas de leitura liberadas em `allowedTools`: `read`, `grep`, `glob`, `code`,
`introspect`, `knowledge`, `web_search` e afins. **`shell`, `aws` e `write` ficam
deliberadamente fora** — se estivessem ali, aprovariam *qualquer* uso dessas
ferramentas, inclusive destrutivo.

No shell, ~119 padrões cobrem:

| Categoria | Exemplos |
|---|---|
| Texto e log | `cat zcat zgrep grep rg tail head wc sort uniq cut tr awk jq column strings xxd` |
| Filesystem | `ls stat file du df find lsblk findmnt` |
| Sistema | `ps ss lsof free vmstat iostat dmesg uptime uname` |
| Rede | `dig nslookup host curl ping -c traceroute whois` |
| Serviços | `journalctl`, `systemctl status/is-active/list-units/show`, `nginx -t` |
| Containers | `docker ps/logs/inspect/stats/events`, `kubectl get/describe/logs/top/explain` |
| Git | `status log diff show blame ls-files rev-parse`, `branch -a`, `remote -v` |
| AWS | verbos `describe- get- list- filter- lookup- search- head- batch-get- query- scan-`, `logs tail`, `s3 ls`, `s3api list/get/head-*`, `sts get-caller-identity`, `ce get-*` |

Encadeamento com `|`, `&&`, `;` e `||` é liberado **somente entre segmentos que já são
de leitura**. `cat app.log \| grep ERROR \| awk '{print $7}' \| sort \| uniq -c \| head`
roda direto; `cat app.log && rm -f evidencia.txt` não.

Na ferramenta `aws` (chamada estruturada, sem shell), vale
`toolsSettings.aws.autoAllowReadonly: true` **sem** `allowedServices` — listar um
serviço ali liberaria também as escritas dele.

Três liberações são exceções conscientes à regra "nada com verbo de mutação", todas
documentadas no gerador:

- `aws logs start-query` / `stop-query` — abrem e encerram consulta do CloudWatch Logs
  Insights; não mudam infraestrutura nem dados.
- `aws eks update-kubeconfig` — escreve apenas no `~/.kube/config` local.
- `kubectl` com whitelist **fechada** de flags globais (`--context`, `-n`,
  `--kubeconfig`, ...) antes de um subcomando de leitura; `exec`, `delete`, `apply`,
  `patch`, `scale`, `drain`, `port-forward` não casam.

### 2. PROMPT — exige confirmação explícita

Tudo que não casa com nenhuma lista cai aqui, inclusive:

```
rm  touch  cp  mv  sed -i  tee  >  >>            # escrita local
aws ec2 terminate-instances | stop-instances | create-tags | modify-*
aws rds delete-db-instance | reboot-db-instance
aws s3 cp | rm | sync       aws ssm put-parameter | send-command
aws logs delete-log-group | put-retention-policy
systemctl restart  docker exec  kubectl delete | exec | rollout restart
git commit | push | checkout        curl -X POST | -d | -o      wget
```

A ferramenta `write` do Kiro também está aqui, com `deniedPaths` em `~/.aws/**`,
`~/.ssh/**`, `/etc/**` e `~/.kiro/agents/**` (trava de automodificação: o agente não
reescreve as próprias permissões).

### 3. DENY — bloqueio duro, sem opção de confirmar

```
rm -rf / | /etc | /usr | ~ | --no-preserve-root
mkfs*  dd of=/dev/*  shred  fdisk  parted  wipefs  > /dev/sd*
shutdown  reboot  poweroff  halt  init 0|6     :(){ ... };:   (fork bomb)
chmod|chown -R em / e diretórios de sistema
journalctl --vacuum|--rotate|--flush           truncate em /var/log
find -delete | -exec        awk system()       sort|jq -o|--output
$(...)   `...`   <(...)     (substituição de comando em argumento)
```

Cada regra vale no início do comando **e** depois de `;`, `&&` ou `|`, com ou sem
`sudo` e com ou sem caminho absoluto (`/bin/rm`).

### Por que os padrões são assim

- O motor de regex do Kiro é o crate `regex` do Rust: **não há lookahead/lookbehind**.
  Nada de `(?!...)`; a segurança vem de allowlists fechadas.
- Argumentos de cada segmento recusam metacaracteres de shell
  (`;` `&` `|` `>` `<` backtick), o que impede pendurar mutação depois de um comando
  de leitura. `$` é permitido (necessário para `awk '{print $7}'`) e `$(` cai no DENY.
- Filtrar por substring não funciona neste domínio: `--output` contém `put` e
  `--start-time` contém `start`. Uma regra "bloquear tudo que contenha put/start"
  mataria justamente `aws logs filter-log-events --start-time ... --output json`.
  Por isso os padrões são ancorados no verbo da operação.

## Pré-requisitos

| Ferramenta | Obrigatória | Para quê |
|---|---|---|
| `kiro-cli` | sim (uso) | executa o agente |
| `python3` ≥ 3.8 | sim | gerador e suíte de testes |
| `aws` CLI v2 | opcional | consultas AWS |
| `kubectl` | opcional | consultas em Kubernetes |
| `docker`, `jq` | opcional | inspeção de containers e JSON |

As ferramentas opcionais ausentes apenas deixam os padrões correspondentes inertes.

## Instalação rápida

```bash
git clone https://github.com/Casiati/kiro-noc-guard.git
cd kiro-noc-guard
./install.sh
```

O instalador:

1. checa pré-requisitos;
2. cria `~/.kiro/{agents,steering,noc-guard}`;
3. faz backup datado de um `noc-aws.json`/steering já existente;
4. copia o steering e o gerador, ajustando caminhos para o `$HOME` atual;
5. instala `agents/noc-aws.json.template` como `~/.kiro/agents/noc-aws.json`;
6. roda a suíte de testes e **só então** grava as listas de permissão;
7. valida com `kiro-cli agent validate` e confere que `shell`/`aws` não estão em
   `allowedTools`;
8. pergunta se deve rodar `kiro-cli agent set-default noc-aws`.

Opções: `--yes` (define o default sem perguntar), `--no-default` (não mexe no default),
`KIRO_DIR=/tmp/sandbox ./install.sh --no-default` (instala fora do `~/.kiro`, útil para
testar).

Sem alterar seu agente default, dá para usar pontualmente:

```bash
kiro-cli chat --agent noc-aws
```

## Como testar e auditar

Rode a suíte antes de aplicar qualquer coisa — ela classifica ~143 comandos reais nas
três camadas e falha se algum sair do esperado:

```bash
python3 scripts/generate_allowlist.py --check
# testes: 143  falhas: 0  (padroes: 119 allow / 33 deny)
```

`--check` **não escreve** no agente. Sem `--check`, o script só grava depois de 0 falhas.
Para aplicar num arquivo específico: `--agent ~/.kiro/agents/noc-aws.json`.

Ao adicionar um comando, inclua-o também na lista `AUTO`, `PROMPT` ou `DENY_T` do
próprio script — é a suíte que garante que a mudança não abriu um buraco. Casos de
contorno já cobertos: `| xargs rm`, `bash -c 'rm ...'`, `FOO=bar rm -rf`,
`/bin/rm -rf /usr`, `cat a && rm -rf /`, `aws describe... ; aws terminate...`.

Inspeção do que está ativo:

```bash
kiro-cli agent validate --path ~/.kiro/agents/noc-aws.json
python3 -c "import json;s=json.load(open('$HOME/.kiro/agents/noc-aws.json'))['toolsSettings']['shell'];print(len(s['allowedCommands']),'allow /',len(s['deniedCommands']),'deny')"
```

Quando um comando de leitura legítimo for barrado, o caminho certo é adicioná-lo ao
gerador e rodar a suíte — não relaxar a config à mão.

## Estrutura do repositório

```
.
├── agents/noc-aws.json.template     # config base do agente (sem as listas geradas)
├── scripts/generate_allowlist.py    # gerador das listas + suíte de testes
├── skills/                          # scripts adicionais (como a busca no CloudTrail)
├── steering/noc-readonly-first.md   # diretriz de comportamento (sempre no contexto)
├── install.sh                       # instalador idempotente, com backup
├── .gitignore
└── README.md
```

## Limitações conhecidas

- O `allowedCommands` de encadeamento é um único padrão gerado (~13 KB). Ele é legível
  pelo gerador, não a olho nu no JSON.
- A camada PROMPT depende de o assistente perguntar. Em modo `--no-interactive` não há
  quem aprove: a chamada é recusada, o que é o comportamento seguro.
- Testado no Kiro CLI em Linux. `%USERPROFILE%\.kiro` (Windows) não foi validado.

## Aviso

Isto é uma camada de **redução de risco operacional**, não um sandbox. Ela não
substitui permissões IAM restritas: o correto continua sendo usar profiles AWS
read-only para triagem. O guard existe para o caso de um profile com escrita chegar
por engano até a sessão.

## Licença

Distribuído sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## Skill: Busca Rápida no CloudTrail

O `noc-aws` inclui um script Python customizado (`search_trail.py`) que resolve a lentidão e as limitações de paginação do `aws cloudtrail lookup-events`.

Exemplos de uso que o agente executa automaticamente:
- `python3 ~/.kiro/skills/cloudtrail-search/search_trail.py --profile NOME-DO-PROFILE --since 2h`
- `python3 ~/.kiro/skills/cloudtrail-search/search_trail.py --profile NOME-DO-PROFILE --event-name StopInstances --since 24h`
- `python3 ~/.kiro/skills/cloudtrail-search/search_trail.py --profile NOME-DO-PROFILE --errors-only`
