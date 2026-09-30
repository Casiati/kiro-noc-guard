#!/usr/bin/env python3
"""
logs-search — consultas READ-ONLY, GRATUITAS e compactas ao CloudWatch Logs (NOC).

Regra de custo zero: só usa APIs sem cobrança por consulta (FilterLogEvents,
DescribeLogGroups, DescribeLogStreams, eks:DescribeCluster). Logs Insights
(cobrado por GB varrido), Live Tail e similares NÃO são usados.

Modos:
  k8s-audit   Escritas no kube-apiserver (deploy/rollout/scale/config) de um
              workload, via audit log do EKS. --status mostra a evolução de
              Ready/restarts dos pods e réplicas do deployment.
  k8s-events  Eventos do Kubernetes (BackOff, Unhealthy, FailedScheduling,
              OOMKilling...) de um workload, agregados — sem precisar de kubeconfig.
  logs        Logs de aplicação (qualquer log group): FilterLogEvents com
              filter pattern + agregação local por mensagem, intervalo ou stream.
  sources     Descobre ONDE estão os logs de um cluster/app em qualquer conta:
              tipos de log do control plane habilitados, audit disponível,
              Container Insights, log groups relacionados e último evento.

Robustez (vale para qualquer cliente):
  - k8s-audit/k8s-events checam antes se o audit do EKS existe e tem eventos
    na janela; se não houver, avisam explicitamente (vazio != "sem mudanças").
  - Varredura em fatias (--slice, padrão 6h) do MAIS RECENTE para o mais
    antigo: se estourar --timeout, perde-se só o começo da janela e a
    cobertura real é informada (linha PARCIAL).

Exemplos:
  logs_search.py sources    --profile P --cluster eks-x --name api-foo
  logs_search.py k8s-audit  --profile P --cluster eks-x -n production --name api-foo --since 24h
  logs_search.py k8s-audit  --profile P --cluster eks-x -n production --name api-foo --status --since 3h
  logs_search.py k8s-events --profile P --cluster eks-x -n production --name api-foo --since 24h --type Warning
  logs_search.py logs       --profile P --log-group /aws/ecs/app --since 3h --group-by message
  logs_search.py logs       --profile P --log-group /aws/ecs/app --since 3h --filter-pattern '?timeout ?refused' --group-by bin

APIs usadas (todas de leitura e sem cobrança por chamada): logs:FilterLogEvents,
logs:DescribeLogGroups, logs:DescribeLogStreams, eks:DescribeCluster.
Nada é gravado em disco.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

try:
    import boto3
    import botocore.exceptions
    HAS_BOTO3 = True
except ImportError:  # fallback para a AWS CLI
    HAS_BOTO3 = False

WRITE_VERBS = ("create", "update", "patch", "delete", "deletecollection")
CHANGE_RESOURCES = ("deployments", "replicasets", "pods", "configmaps", "secrets",
                    "horizontalpodautoscalers", "scaledobjects")
# filter pattern padrão do modo logs (sintaxe do CloudWatch: ?termo = OU)
DEFAULT_ERROR_PATTERN = ("?ERROR ?Error ?error ?EXCEPTION ?Exception ?exception ?FATAL ?Fatal ?panic "
                         "?timeout ?Timeout ?refused ?OOMKilled")


# ------------------------------------------------------------------ tempo
def _now():
    return datetime.now(timezone.utc)


def parse_duration(value):
    """'30m' / '6h' / '7d' -> timedelta (1m..90d)."""
    m = re.fullmatch(r"(\d+)([mhd])", (value or "").strip())
    if not m:
        raise ValueError(f"duração inválida '{value}': use N seguido de m, h ou d (ex.: 30m, 6h, 7d)")
    n, unit = int(m.group(1)), m.group(2)
    delta = {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]
    if n <= 0 or delta > timedelta(days=90):
        raise ValueError(f"duração fora do limite (1m..90d): '{value}'")
    return delta


def parse_since(value, now=None):
    """'30m' / '6h' / '7d' -> datetime UTC (agora - duração)."""
    return (now or _now()) - parse_duration(value)


def fmt_age(ms, now=None):
    """Idade humana de um epoch-ms: '3min', '5h', '12d'."""
    if not ms:
        return "-"
    sec = max(((now or _now()).timestamp() * 1000 - ms) / 1000, 0)
    for unit, size in (("d", 86400), ("h", 3600), ("min", 60)):
        if sec >= size:
            return f"{int(sec // size)}{unit}"
    return f"{int(sec)}s"


def fmt_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def parse_iso(value):
    """'2026-09-29T19:40:00Z' / '2026-09-29 19:40' -> datetime UTC (naive = UTC)."""
    v = value.strip().replace(" ", "T")
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        raise ValueError(f"data inválida '{value}': use ISO-8601, ex.: 2026-09-29T19:40:00Z")
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def resolve_window(args, now=None):
    now = now or _now()
    start = parse_iso(args.start) if args.start else parse_since(args.since, now)
    end = parse_iso(args.end) if args.end else now
    if start >= end:
        raise ValueError("início da janela precisa ser anterior ao fim")
    return start, end


def to_ms(dt):
    return int(dt.timestamp() * 1000)


def fmt_ts(value):
    """Normaliza timestamps (ISO string, epoch ms) para 'YYYY-MM-DD HH:MM:SS'."""
    if value is None or value == "":
        return "-"
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return str(value).replace("T", " ")[:19]


# --------------------------------------------------------------- saída
def trunc(value, width):
    s = " ".join(str(value).split())  # colapsa quebras de linha/espaços
    return s if len(s) <= width else s[: max(width - 1, 1)] + "…"


def print_table(headers, rows, width):
    if not rows:
        print("(nenhum resultado)")
        return
    rows = [[trunc(c, width) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    widths[-1] = 0  # última coluna não é alinhada (mensagem/detalhe)
    line = lambda cells: " | ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip()
    print(line(headers))
    print("-" * min(sum(widths) + 3 * len(widths) + 20, 160))
    for r in rows:
        print(line(r))


# ------------------------------------------------------------ backends
class AwsError(RuntimeError):
    def __init__(self, msg, code=""):
        super().__init__(msg)
        self.code = code


class Boto3Backend:
    def __init__(self, profile, region):
        try:
            self.session = boto3.Session(profile_name=profile, region_name=region)
            self.logs = self.session.client("logs")
        except botocore.exceptions.ProfileNotFound as e:
            raise AwsError(f"profile AWS '{profile}' não encontrado: {e}")
        except botocore.exceptions.BotoCoreError as e:
            raise AwsError(f"erro do SDK ao criar sessão: {e}")
        self.profile = profile
        self._eks = None

    @property
    def eks(self):
        if self._eks is None:
            self._eks = self.session.client("eks")
        return self._eks

    def _call(self, fn, **kw):
        try:
            return fn(**kw)
        except botocore.exceptions.NoCredentialsError:
            raise AwsError("sem credenciais AWS (rode aws sso login)")
        except botocore.exceptions.ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("ExpiredToken", "ExpiredTokenException", "RequestExpired",
                        "UnrecognizedClientException"):
                raise AwsError(f"credenciais expiradas/inválidas no profile '{self.profile}' (aws sso login)",
                               code)
            raise AwsError(f"erro da API AWS ({code}): {e}", code)
        except botocore.exceptions.EndpointConnectionError as e:
            raise AwsError(f"falha de rede até o endpoint AWS: {e}")
        except botocore.exceptions.BotoCoreError as e:
            raise AwsError(f"erro do SDK AWS: {e}")

    def filter_events(self, group, stream_prefix, pattern, start_ms, end_ms, max_events, deadline):
        kw = {"logGroupName": group, "startTime": start_ms, "endTime": end_ms}
        if stream_prefix:
            kw["logStreamNamePrefix"] = stream_prefix
        if pattern:
            kw["filterPattern"] = pattern
        kw["limit"] = max(1, min(max_events, 10000))
        got = 0
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError
            resp = self._call(self.logs.filter_log_events, **kw)
            for ev in resp.get("events", []):
                yield ev
                got += 1
                if got >= max_events:
                    return
            token = resp.get("nextToken")
            if not token:
                return
            kw["nextToken"] = token

    def describe_log_streams(self, group, prefix=None, latest_first=False, max_items=500):
        kw = {"logGroupName": group, "limit": 50}
        if prefix:
            kw["logStreamNamePrefix"] = prefix
        if latest_first:  # a API não aceita prefixo + ordenação por LastEventTime
            kw.update(orderBy="LastEventTime", descending=True, limit=min(max_items, 50))
        out = []
        while len(out) < max_items:
            resp = self._call(self.logs.describe_log_streams, **kw)
            out.extend(resp.get("logStreams", []))
            if not resp.get("nextToken") or latest_first:
                break
            kw["nextToken"] = resp["nextToken"]
        return out[:max_items]

    def describe_log_groups(self, pattern, max_items=200):
        kw = {"logGroupNamePattern": pattern, "limit": 50}
        out = []
        while len(out) < max_items:
            resp = self._call(self.logs.describe_log_groups, **kw)
            out.extend(resp.get("logGroups", []))
            if not resp.get("nextToken"):
                break
            kw["nextToken"] = resp["nextToken"]
        return out[:max_items]

    def describe_cluster(self, name):
        return self._call(self.eks.describe_cluster, name=name).get("cluster", {})


class CliBackend:
    def __init__(self, profile, region):
        self.opts = ["--profile", profile, "--region", region, "--output", "json"]

    def _run(self, service, sub, timeout=120):
        cmd = ["aws", service] + sub + self.opts
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            raise AwsError("'aws' CLI não encontrada no PATH (instale a AWS CLI ou o boto3)")
        except subprocess.TimeoutExpired:
            raise TimeoutError
        if res.returncode != 0:
            err = res.stderr.strip()
            m = re.search(r"\((\w+)\) when calling", err)
            raise AwsError(f"AWS CLI: {err or 'código de saída ' + str(res.returncode)}", m.group(1) if m else "")
        try:
            return json.loads(res.stdout or "{}")
        except json.JSONDecodeError:
            raise AwsError(f"saída inesperada da AWS CLI: {res.stdout[:200]}")

    def filter_events(self, group, stream_prefix, pattern, start_ms, end_ms, max_events, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        sub = ["filter-log-events", "--log-group-name", group, "--start-time", str(start_ms),
               "--end-time", str(end_ms), "--max-items", str(max_events)]
        if stream_prefix:
            sub += ["--log-stream-name-prefix", stream_prefix]
        if pattern:
            sub += ["--filter-pattern", pattern]
        yield from self._run("logs", sub, timeout=max(int(remaining), 1)).get("events", [])

    def describe_log_streams(self, group, prefix=None, latest_first=False, max_items=500):
        sub = ["describe-log-streams", "--log-group-name", group]
        if prefix:
            sub += ["--log-stream-name-prefix", prefix]
        if latest_first:
            sub += ["--order-by", "LastEventTime", "--descending"]
            max_items = min(max_items, 50)
        sub += ["--max-items", str(max_items)]
        return self._run("logs", sub).get("logStreams", [])

    def describe_log_groups(self, pattern, max_items=200):
        sub = ["describe-log-groups", "--log-group-name-pattern", pattern, "--max-items", str(max_items)]
        return self._run("logs", sub).get("logGroups", [])

    def describe_cluster(self, name):
        return self._run("eks", ["describe-cluster", "--name", name]).get("cluster", {})


def make_backend(args):
    return (Boto3Backend if HAS_BOTO3 else CliBackend)(args.profile, args.region)


# ------------------------------------------------------ filter patterns
def _q(value):
    """Valor seguro para literal de filter pattern JSON do CloudWatch."""
    if not re.fullmatch(r"[\w.\-:/*@]+", value):
        raise ValueError(f"valor inválido para filtro: '{value}' (use apenas letras, números, . - _ : / *)")
    return f'"{value}"'


def _any(field, values):
    parts = [f"$.{field} = {_q(v)}" for v in values]
    return parts[0] if len(parts) == 1 else "(" + " || ".join(parts) + ")"


def _name_prefix(name):
    return name if name.endswith("*") else name + "*"


def build_audit_pattern(namespace, name, resources, verbs, status_view):
    conds = []
    if namespace:
        conds.append(f"$.objectRef.namespace = {_q(namespace)}")
    if name:
        conds.append(f"$.objectRef.name = {_q(_name_prefix(name))}")
    if status_view:
        conds.append(_any("objectRef.resource", resources or ("pods", "deployments", "replicasets")))
        conds.append('$.objectRef.subresource = "status"')
        conds.append(_any("verb", ("patch", "update")))
    else:
        conds.append(_any("objectRef.resource", resources or CHANGE_RESOURCES))
        # scale = HPA/KEDA/kubectl scale; status fica de fora (ruído do kubelet)
        conds.append('($.objectRef.subresource NOT EXISTS || $.objectRef.subresource = "scale")')
        conds.append(_any("verb", verbs or WRITE_VERBS))
    return "{ " + " && ".join(conds) + " }"


def build_events_pattern(namespace, name):
    conds = ['$.objectRef.resource = "events"']
    if namespace:
        conds.append(f"$.objectRef.namespace = {_q(namespace)}")
    if name:
        conds.append(f"$.objectRef.name = {_q(_name_prefix(name))}")
    conds.append(_any("verb", ("create", "patch", "update")))
    return "{ " + " && ".join(conds) + " }"


AUDIT_STREAM = "kube-apiserver-audit"


# ---------------------------------------------------------- k8s-audit
def _parse_audit(events):
    """Mensagens do CloudWatch -> dicts de audit (ignora linhas não-JSON)."""
    out = []
    for ev in events:
        try:
            out.append(json.loads(ev.get("message", "")))
        except (ValueError, TypeError):
            continue
    return _dedupe_sort(out)


def _dedupe_sort(audits):
    """Remove duplicatas (bordas de fatias adjacentes) e ordena no tempo."""
    seen, out = set(), []
    for e in audits:
        key = ((e.get("auditID"), e.get("stage")) if e.get("auditID")
               else json.dumps(e, sort_keys=True, default=str))
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    out.sort(key=lambda e: e.get("requestReceivedTimestamp") or "")
    return out


def _find_key(obj, key, acc, depth=0):
    if depth > 12:
        return acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, (str, int, float)):
                acc.append(str(v))
            else:
                _find_key(v, key, acc, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _find_key(v, key, acc, depth + 1)
    return acc


def _flat_keys(obj, prefix="", depth=0, acc=None):
    acc = [] if acc is None else acc
    if isinstance(obj, dict) and depth < 3:
        for k, v in obj.items():
            if k in ("metadata",) and depth == 0:
                continue
            _flat_keys(v, f"{prefix}.{k}" if prefix else k, depth + 1, acc)
    elif prefix:
        acc.append(prefix)
    return acc


def change_detail(e):
    """Resumo curto do que a requisição altera (imagem, réplicas, restart...)."""
    r = e.get("requestObject") or {}
    parts = []
    images = sorted(set(_find_key(r, "image", [])))
    if images:
        parts.append("image=" + ",".join(i.rsplit("/", 1)[-1] for i in images))
    spec = r.get("spec") if isinstance(r, dict) else None
    if isinstance(spec, dict) and "replicas" in spec:
        parts.append(f"replicas={spec['replicas']}")
    restarted = _find_key(r, "kubectl.kubernetes.io/restartedAt", [])
    if restarted:
        parts.append("rollout-restart=" + restarted[0])
    if not parts and isinstance(r, dict) and r and e.get("verb") in ("patch", "update"):
        keys = _flat_keys(r)
        if keys:
            parts.append("campos=" + ",".join(keys[:4]) + ("…" if len(keys) > 4 else ""))
    code = (e.get("responseStatus") or {}).get("code")
    if code and int(code) >= 400:
        parts.append(f"FALHOU({code}: {(e.get('responseStatus') or {}).get('reason', '')})")
    return " ".join(parts)


def _short_user(u):
    u = u or "-"
    for p in ("system:serviceaccount:", "system:"):
        if u.startswith(p):
            return u[len(p):]
    return u


def summarize_changes(audits):
    """Linha do tempo com repetições consecutivas colapsadas (×N)."""
    rows, last_key = [], None
    for e in audits:
        o = e.get("objectRef") or {}
        res = o.get("resource", "-") + ("/" + o["subresource"] if o.get("subresource") else "")
        key = (e.get("verb"), res, o.get("name"), _short_user((e.get("user") or {}).get("username")),
               str((e.get("responseStatus") or {}).get("code", "-")), change_detail(e))
        ts = fmt_ts(e.get("requestReceivedTimestamp"))
        if rows and key == last_key:
            rows[-1]["n"] += 1
            rows[-1]["last"] = ts
        else:
            rows.append({"first": ts, "last": ts, "n": 1, "key": key})
            last_key = key
    out = []
    for r in rows:
        verb, res, name, user, code, detail = r["key"]
        when = r["first"] if r["n"] == 1 else f"{r['first']} ×{r['n']} até {r['last'][11:]}"
        out.append([when, verb, res, name or "-", user, code, detail])
    return out


def status_summary(e):
    r = e.get("requestObject") or {}
    s = r.get("status") if isinstance(r, dict) else None
    if not isinstance(s, dict):
        return None
    res = (e.get("objectRef") or {}).get("resource")
    parts = []
    conds = {c.get("type"): c for c in s.get("conditions", []) or [] if isinstance(c, dict)}
    if res == "pods":
        for t in ("Ready", "PodScheduled"):
            if t in conds:
                c = conds[t]
                parts.append(f"{t}={c.get('status')}" + (f"({c['reason']})" if c.get("reason") else ""))
        for cs in s.get("containerStatuses", []) or []:
            st = cs.get("state") or {}
            state = next(iter(st), "?")
            reason = (st.get(state) or {}).get("reason") if isinstance(st.get(state), dict) else None
            item = f"{cs.get('name', '?')}:ready={cs.get('ready')},restarts={cs.get('restartCount', '?')},{state}"
            if reason:
                item += f"({reason})"
            term = ((cs.get("lastState") or {}).get("terminated") or {})
            if term:
                item += f",last={term.get('reason')}/exit={term.get('exitCode')}"
            parts.append(item)
        if s.get("phase"):
            parts.insert(0, f"phase={s['phase']}")
    else:
        for k in ("replicas", "readyReplicas", "availableReplicas", "unavailableReplicas", "updatedReplicas"):
            if k in s:
                parts.append(f"{k}={s[k]}")
        for t in ("Available", "Progressing", "ReplicaFailure"):
            if t in conds:
                c = conds[t]
                parts.append(f"{t}={c.get('status')}" + (f"({c['reason']})" if c.get("reason") else ""))
    return " ".join(parts) if parts else None


def summarize_status(audits):
    """Transições de estado por objeto (repetições idênticas colapsadas)."""
    rows, last_by_obj = [], {}
    for e in audits:
        summary = status_summary(e)
        if not summary:
            continue
        o = e.get("objectRef") or {}
        obj = f"{o.get('resource', '-')}/{o.get('name', '-')}"
        ts = fmt_ts(e.get("requestReceivedTimestamp"))
        prev = last_by_obj.get(obj)
        if prev is not None and prev["summary"] == summary:
            prev["n"] += 1
            prev["last"] = ts
            continue
        row = {"first": ts, "last": ts, "n": 1, "obj": obj, "summary": summary}
        rows.append(row)
        last_by_obj[obj] = row
    return [[r["first"] if r["n"] == 1 else f"{r['first']} ×{r['n']} até {r['last'][11:]}",
             r["obj"], r["summary"]] for r in rows]


# --------------------------------------------------------- k8s-events
def _event_fields(r):
    """Normaliza core/v1 Event e events.k8s.io/v1 Event."""
    inv = r.get("involvedObject") or r.get("regarding") or {}
    series = r.get("series") or {}
    count = r.get("count") or series.get("count") or r.get("deprecatedCount")
    return {
        "obj": (f"{inv.get('kind', '')}/{inv.get('name')}" if inv.get("name") else None),
        "reason": r.get("reason"),
        "type": r.get("type"),
        "message": r.get("message") or r.get("note"),
        "first": r.get("firstTimestamp") or r.get("eventTime") or r.get("deprecatedFirstTimestamp"),
        "last": (r.get("lastTimestamp") or series.get("lastObservedTime")
                 or r.get("deprecatedLastTimestamp")),
        "count": int(count) if isinstance(count, (int, float, str)) and str(count).isdigit() else None,
    }


def _min_ts(*values):
    vals = [fmt_ts(v) for v in values if v]
    return min(vals) if vals else None


def _max_ts(*values):
    vals = [fmt_ts(v) for v in values if v]
    return max(vals) if vals else None


def summarize_k8s_events(audits, type_filter=None, reason_filter=None):
    """Agrega por (reason, type, message): total de ocorrências, objetos e janela."""
    per_obj = {}  # nome do objeto Event -> estado acumulado
    for e in audits:
        o = e.get("objectRef") or {}
        ev_name = o.get("name") or "?"
        r = e.get("requestObject") if isinstance(e.get("requestObject"), dict) else {}
        f = _event_fields(r)
        ts = e.get("requestReceivedTimestamp")
        cur = per_obj.setdefault(ev_name, {
            "obj": None, "reason": None, "type": None, "message": None,
            "first": None, "last": None, "count": 0, "hits": 0})
        for k in ("obj", "reason", "type", "message"):
            if f[k] and not cur[k]:
                cur[k] = f[k]
        if f["message"]:
            cur["message"] = f["message"]
        cur["first"] = _min_ts(cur["first"], f["first"], ts)
        cur["last"] = _max_ts(cur["last"], f["last"], ts)
        cur["hits"] += 1
        if f["count"]:
            cur["count"] = max(cur["count"], f["count"])
    groups = {}
    for ev_name, cur in per_obj.items():
        obj = cur["obj"] or ev_name.rsplit(".", 1)[0]
        reason, etype = cur["reason"] or "?", cur["type"] or "?"
        if type_filter and etype.lower() != type_filter.lower():
            continue
        if reason_filter and reason.lower() != reason_filter.lower():
            continue
        key = (reason, etype, cur["message"] or "(mensagem fora da janela)")
        g = groups.setdefault(key, {"objs": set(), "count": 0, "first": None, "last": None})
        g["objs"].add(obj)
        g["count"] += cur["count"] or cur["hits"]
        g["first"] = _min_ts(g["first"], cur["first"])
        g["last"] = _max_ts(g["last"], cur["last"])
    rows = []
    for (reason, etype, msg), g in sorted(groups.items(), key=lambda kv: (kv[1]["last"] or "", kv[1]["count"]),
                                          reverse=True):
        objs = sorted(g["objs"])
        objs_s = objs[0].split("/", 1)[-1] + (f" (+{len(objs) - 1})" if len(objs) > 1 else "")
        rows.append([etype, reason, str(g["count"]), fmt_ts(g["first"]), fmt_ts(g["last"]), objs_s, msg])
    return rows


# ------------------------------------------------- saúde do audit do EKS
AUDIT_UNAVAILABLE = ("missing_group", "no_streams", "stale")


def _probe(backend, group, start_ms, end_ms, deadline):
    """True se existir ao menos 1 evento de audit no intervalo (sonda barata)."""
    try:
        for _ in backend.filter_events(group, AUDIT_STREAM, None, start_ms, end_ms, 1, deadline):
            return True
    except TimeoutError:
        return None
    return False


def audit_health(backend, group, start, end, probe_timeout=20):
    """Verifica se o audit existe e cobre a janela, antes de concluir "vazio".

    Estados: ok | gap (audit parou antes do fim da janela) | stale (nenhum
    evento na janela) | no_streams | missing_group.
    lastEventTimestamp dos streams atrasa até ~1h e a listagem por prefixo é
    alfabética, então: (1) ordena por LastEventTime; (2) antes de declarar
    stale/gap, confirma com uma sonda de 1 evento via FilterLogEvents.
    """
    try:
        latest = [s for s in backend.describe_log_streams(group, latest_first=True, max_items=50)
                  if (s.get("logStreamName") or "").startswith(AUDIT_STREAM)]
        streams = latest or backend.describe_log_streams(group, prefix=AUDIT_STREAM, max_items=500)
    except AwsError as e:
        if e.code == "ResourceNotFoundException":
            return {"state": "missing_group", "last": None}
        raise
    if not streams:
        return {"state": "no_streams", "last": None}
    last = max(max(s.get("lastIngestionTime") or 0, s.get("lastEventTimestamp") or 0) for s in streams) or None
    s_ms, e_ms = to_ms(start), to_ms(end)
    if last and last >= e_ms - 2 * 3_600_000:
        return {"state": "ok", "last": last}
    deadline = time.monotonic() + probe_timeout
    recent_from = max(s_ms, e_ms - 2 * 3_600_000)
    if _probe(backend, group, recent_from, e_ms, deadline):
        return {"state": "ok", "last": last}
    if last and last >= s_ms:
        return {"state": "gap", "last": last}
    found = _probe(backend, group, s_ms, e_ms, deadline)
    if found or found is None:  # None = sonda estourou: não afirma indisponível
        return {"state": "gap" if found else "ok", "last": last}
    return {"state": "stale", "last": last}


def control_plane_logging(backend, cluster):
    """(habilitados, desabilitados, erro) dos tipos de log do control plane."""
    try:
        info = backend.describe_cluster(cluster)
    except AwsError as e:
        if e.code == "ResourceNotFoundException":
            return None, None, "cluster não encontrado nesta conta/região"
        if e.code in ("AccessDeniedException", "AccessDenied"):
            return None, None, "sem permissão eks:DescribeCluster"
        return None, None, str(e)[:120]
    on, off = [], []
    entries = (info.get("logging") or {}).get("clusterLogging") or []
    if not entries:
        return None, None, "describe-cluster sem informação de logging"
    for item in entries:
        (on if item.get("enabled") else off).extend(item.get("types") or [])
    return on, off, None


def audit_unavailable_msg(health, group, cp):
    on, off, err = cp
    why = {"missing_group": f"log group {group} não existe",
           "no_streams": f"sem streams {AUDIT_STREAM}* em {group}",
           "stale": f"último evento de audit em {fmt_ts(health['last'])} (antes da janela)"}[health["state"]]
    if on is not None:
        why += "; control plane logging: " + ("audit HABILITADO" if "audit" in on else "audit DESABILITADO")
    elif err:
        why += f"; ({err})"
    return why


# ----------------------------------------------------------- varredura
def scan_filter_slices(backend, group, pattern, start, end, slice_td, max_events, timeout,
                       stream_prefix=AUDIT_STREAM):
    """FilterLogEvents em fatias, da mais recente para a mais antiga.

    Retorna (eventos, meta). meta['covered_from'] = início do trecho
    varrido POR COMPLETO (de covered_from até end).
    """
    deadline = time.monotonic() + timeout
    events, covered_from, partial, truncated = [], end, False, False
    cur_end = end
    while cur_end > start:
        cur_start = max(start, cur_end - slice_td)
        try:
            for ev in backend.filter_events(group, stream_prefix, pattern, to_ms(cur_start), to_ms(cur_end),
                                            max_events - len(events), deadline):
                events.append(ev)
        except TimeoutError:
            partial = True
            break
        if len(events) >= max_events:
            truncated = True
            break
        covered_from = cur_end = cur_start
    return events, {"covered_from": covered_from, "partial": partial, "truncated": truncated}


# ---------------------------------------------------------------- CLI
def parse_args(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--profile", required=True, help="profile AWS (obrigatório)")
    common.add_argument("--region", default="us-east-1")
    common.add_argument("--since", default="1h", help="janela relativa: 30m, 6h, 7d (padrão 1h)")
    common.add_argument("--start", help="início ISO-8601 (UTC), ex.: 2026-09-29T19:40:00Z (sobrepõe --since)")
    common.add_argument("--end", help="fim ISO-8601 (UTC); padrão: agora")
    common.add_argument("--limit", type=int, default=40, help="máx. de linhas exibidas (padrão 40)")
    common.add_argument("--width", type=int, default=180, help="largura máx. por coluna (padrão 180)")
    common.add_argument("--timeout", type=int, default=90, help="tempo máx. de varredura em s (padrão 90)")

    scan = argparse.ArgumentParser(add_help=False)
    scan.add_argument("--max-events", type=int, default=3000, help="máx. de eventos lidos (padrão 3000)")
    scan.add_argument("--slice", default="6h", help="tamanho da fatia da varredura (padrão 6h)")

    k8s = argparse.ArgumentParser(add_help=False)
    k8s.add_argument("--cluster", help="nome do cluster EKS (log group /aws/eks/<cluster>/cluster)")
    k8s.add_argument("--log-group", dest="log_group", help="log group do audit (sobrepõe --cluster)")
    k8s.add_argument("--namespace", "-n")
    k8s.add_argument("--name", help="prefixo do objeto (deployment/pod/replicaset), ex.: api-foo")

    p = argparse.ArgumentParser(description="Consultas read-only, gratuitas e compactas ao CloudWatch Logs (NOC).")
    sub = p.add_subparsers(dest="mode", required=True)

    a = sub.add_parser("k8s-audit", parents=[common, scan, k8s],
                       help="escritas/rollouts ou estado (--status) via audit")
    a.add_argument("--status", action="store_true", help="evolução de Ready/restarts/réplicas (status patches)")
    a.add_argument("--resource", action="append", help="recurso(s) k8s (repetível); padrão depende do modo")
    a.add_argument("--verb", action="append", help="verbo(s) (repetível); padrão: create/update/patch/delete")

    e = sub.add_parser("k8s-events", parents=[common, scan, k8s], help="eventos k8s agregados via audit")
    e.add_argument("--type", help="Warning ou Normal")
    e.add_argument("--reason", help="ex.: Unhealthy, BackOff, FailedScheduling, OOMKilling")

    lg = sub.add_parser("logs", parents=[common, scan], help="logs de aplicação (FilterLogEvents + agregação local)")
    lg.add_argument("--log-group", dest="log_group", required=True)
    lg.add_argument("--stream-prefix", help="prefixo de log stream (ex.: nome do pod/task)")
    lg.add_argument("--filter-pattern", help="filter pattern do CloudWatch (padrão: termos de erro comuns); "
                                            "use --all para não filtrar")
    lg.add_argument("--all", action="store_true", help="sem filter pattern (todas as linhas)")
    lg.add_argument("--group-by", choices=("message", "bin", "stream", "none"), default="message",
                    help="message (padrão): mensagens agregadas; bin: contagem por intervalo; "
                         "stream: contagem por stream; none: linhas cruas mais recentes")
    lg.add_argument("--bin", default="5m", help="intervalo do --group-by bin (padrão 5m)")

    s = sub.add_parser("sources", parents=[common], help="onde estão os logs de um cluster/app (descoberta)")
    s.add_argument("--cluster", help="nome do cluster EKS")
    s.add_argument("--name", help="nome do app/serviço (busca log groups que o contenham)")
    s.add_argument("--namespace", "-n", help="namespace (busca log groups que o contenham)")
    s.add_argument("--pattern", action="append", help="termo extra de busca de log group (repetível)")

    args = p.parse_args(argv)
    if args.mode in ("k8s-audit", "k8s-events") and not (args.cluster or args.log_group):
        p.error("informe --cluster ou --log-group")
    if args.mode == "sources" and not (args.cluster or args.name or args.namespace or args.pattern):
        p.error("informe --cluster, --name, --namespace ou --pattern")
    if args.mode == "logs" and args.all and args.filter_pattern:
        p.error("use --filter-pattern OU --all")
    if args.limit <= 0 or args.width < 20:
        p.error("--limit deve ser > 0 e --width >= 20")
    return args


def _window_label(start, end):
    fmt_end = "%H:%M" if start.date() == end.date() else "%Y-%m-%d %H:%M"
    return f"{start.strftime('%Y-%m-%d %H:%M')}..{end.strftime(fmt_end)} UTC"


def _k8s_pattern(args):
    if args.mode == "k8s-audit":
        return build_audit_pattern(args.namespace, args.name, args.resource, args.verb, args.status)
    return build_events_pattern(args.namespace, args.name)


def _coverage_notes(meta, args):
    notes = []
    if meta["partial"]:
        notes.append(f"PARCIAL: cobertura completa só de {fmt_ts(to_ms(meta['covered_from']))} até o fim da "
                     "janela (varredura do mais recente p/ o mais antigo); o trecho mais antigo NÃO foi lido — "
                     "aumente --timeout ou reduza --since/estreite o filtro")
    if meta["truncated"]:
        notes.append(f"TRUNCADO: limite de {args.max_events} eventos (--max-events) atingido; "
                     "eventos mais antigos podem faltar — estreite o filtro/--since")
    return notes


def cmd_k8s(args, backend, start, end):
    group = args.log_group or f"/aws/eks/{args.cluster}/cluster"
    pattern = _k8s_pattern(args)
    title = ("estado (status)" if getattr(args, "status", False) else "alterações") \
        if args.mode == "k8s-audit" else "eventos"
    scope = f"ns={args.namespace or '*'} name={args.name or '*'}"

    health = audit_health(backend, group, start, end)
    if health["state"] in AUDIT_UNAVAILABLE:
        cp = control_plane_logging(backend, args.cluster) if args.cluster else (None, None, None)
        print(f"# k8s {title} | {group} | {scope} | {_window_label(start, end)}")
        print(f"# AUDIT INDISPONÍVEL: {audit_unavailable_msg(health, group, cp)}")
        print("# Resultado vazio aqui NÃO significa 'sem alterações/eventos'. Fontes alternativas:")
        print(f"#  - descobrir outras fontes: logs_search.py sources --profile {args.profile} "
              f"--cluster {args.cluster or '<cluster>'}" + (f" --name {args.name}" if args.name else ""))
        print("#  - kubectl (se houver acesso): get events (retém ~1h), rollout history, describe, logs")
        print("#  - mudanças via API AWS (nodegroup/addon/update-cluster): search_trail.py")
        return 2

    notes = []
    if health["state"] == "gap":
        notes.append(f"AVISO: último evento de audit em {fmt_ts(health['last'])}; "
                     "trecho posterior da janela sem cobertura (audit desligado ou atraso de ingestão)")
    events, meta = scan_filter_slices(backend, group, pattern, start, end, parse_duration(args.slice),
                                      args.max_events, args.timeout)
    notes += _coverage_notes(meta, args)
    audits = _parse_audit(events)

    if args.mode == "k8s-audit" and args.status:
        headers, rows = ["quando (UTC)", "objeto", "estado"], summarize_status(audits)
    elif args.mode == "k8s-audit":
        headers = ["quando (UTC)", "verbo", "recurso", "nome", "usuário", "http", "detalhe"]
        rows = summarize_changes(audits)
    else:
        headers = ["tipo", "reason", "total", "primeiro", "último", "objeto", "mensagem"]
        rows = summarize_k8s_events(audits, args.type, args.reason)

    print(f"# k8s {title} | {group} | {scope} | {_window_label(start, end)} | "
          f"audit lidos={len(audits)} linhas={len(rows)}")
    for n in notes:
        print(f"# {n}")
    # eventos: os mais relevantes primeiro; audit: linha do tempo, mantém os mais recentes
    shown = rows[: args.limit] if args.mode == "k8s-events" else rows[-args.limit:]
    if len(rows) > len(shown):
        print(f"# exibindo {len(shown)} de {len(rows)} linhas (--limit)")
    print_table(headers, shown, args.width)
    return 0


# ---------------------------------------------------------------- logs
_NORM = [(re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<uuid>"),
         (re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<ts>"),
         (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "<ip>"),
         (re.compile(r"\b0x[0-9a-f]+\b|\b[0-9a-f]{16,}\b", re.I), "<hex>"),
         (re.compile(r"(?<![A-Za-z_])\d+(?:\.\d+)?"), "<n>")]  # 5000ms -> <n>ms; ignora v2/http2


def normalize_message(msg, width=160):
    """Colapsa partes variáveis (ids, horários, IPs, números) para agregar mensagens iguais."""
    s = " ".join(str(msg).split())
    for rx, rep in _NORM:
        s = rx.sub(rep, s)
    return s[:width]


def summarize_logs(events, group_by, bin_td):
    if group_by == "none":
        evs = sorted(events, key=lambda e: e.get("timestamp") or 0, reverse=True)
        return (["quando (UTC)", "stream", "mensagem"],
                [[fmt_ts(e.get("timestamp")), e.get("logStreamName", "-"), e.get("message", "")] for e in evs])
    if group_by == "bin":
        size = int(bin_td.total_seconds() * 1000)
        counts = {}
        for e in events:
            b = (e.get("timestamp") or 0) // size * size
            counts[b] = counts.get(b, 0) + 1
        return ["intervalo (UTC)", "eventos"], [[fmt_ts(b), str(n)] for b, n in sorted(counts.items())]
    groups = {}
    for e in events:
        key = e.get("logStreamName", "-") if group_by == "stream" else normalize_message(e.get("message", ""))
        g = groups.setdefault(key, {"n": 0, "first": None, "last": None, "sample": e.get("message", "")})
        g["n"] += 1
        ts = e.get("timestamp")
        g["first"] = ts if g["first"] is None or (ts and ts < g["first"]) else g["first"]
        g["last"] = ts if g["last"] is None or (ts and ts > g["last"]) else g["last"]
    ordered = sorted(groups.items(), key=lambda kv: (kv[1]["n"], kv[1]["last"] or 0), reverse=True)
    label = "stream" if group_by == "stream" else "mensagem (exemplo)"
    return (["total", "primeiro", "último", label],
            [[str(g["n"]), fmt_ts(g["first"]), fmt_ts(g["last"]), k if group_by == "stream" else g["sample"]]
             for k, g in ordered])


def cmd_logs(args, backend, start, end):
    pattern = None if args.all else (args.filter_pattern or DEFAULT_ERROR_PATTERN)
    events, meta = scan_filter_slices(backend, args.log_group, pattern, start, end, parse_duration(args.slice),
                                      args.max_events, args.timeout, stream_prefix=args.stream_prefix)
    headers, rows = summarize_logs(events, args.group_by, parse_duration(args.bin))
    print(f"# logs | {args.log_group}" + (f" stream={args.stream_prefix}*" if args.stream_prefix else "") +
          f" | {_window_label(start, end)} | eventos lidos={len(events)} linhas={len(rows)} "
          f"group-by={args.group_by}")
    print(f"# filter-pattern: {pattern or '(nenhum)'}")
    for n in _coverage_notes(meta, args):
        print(f"# {n}")
    shown = rows[-args.limit:] if args.group_by == "bin" else rows[: args.limit]
    if len(rows) > len(shown):
        print(f"# exibindo {len(shown)} de {len(rows)} linhas (--limit)")
    print_table(headers, shown, args.width)
    return 0


# ----------------------------------------------------------- sources
_GROUP_TERM = re.compile(r"[\w.\-/#]+")
STALE_DAYS = 7


def _source_terms(args):
    terms = []
    for t in [args.cluster, args.name, args.namespace] + list(args.pattern or []):
        if not t:
            continue
        if not _GROUP_TERM.fullmatch(t):
            raise ValueError(f"termo inválido para busca de log group: '{t}' (use letras, números, . - _ / #)")
        if t not in terms:
            terms.append(t)
    return terms


def _last_event_ms(backend, group):
    try:
        streams = backend.describe_log_streams(group, latest_first=True, max_items=1)
    except AwsError:
        return None
    if not streams:
        return None
    s = streams[0]
    return max(s.get("lastIngestionTime") or 0, s.get("lastEventTimestamp") or 0) or None


def cmd_sources(args, backend, start, end):
    now_ms = to_ms(end)
    print(f"# sources | cluster={args.cluster or '-'} name={args.name or '-'} ns={args.namespace or '-'} | "
          f"profile={args.profile} region={args.region} | janela de referência {_window_label(start, end)}")
    hints = []
    if args.cluster:
        on, off, err = control_plane_logging(backend, args.cluster)
        if err:
            print(f"control plane logging: ? ({err})")
        else:
            print(f"control plane logging: habilitados={','.join(on) or 'nenhum'} "
                  f"desabilitados={','.join(off) or 'nenhum'}")
        group = f"/aws/eks/{args.cluster}/cluster"
        health = audit_health(backend, group, start, end)
        label = {"ok": "OK", "gap": "COM LACUNA", "stale": "SEM EVENTOS NA JANELA",
                 "no_streams": "SEM STREAMS", "missing_group": "AUSENTE"}[health["state"]]
        last = (f", metadado do stream: {fmt_ts(health['last'])} (pode atrasar ~1h)"
                if health["last"] else "")
        print(f"audit EKS ({group}): {label}{last}")
        if health["state"] in ("ok", "gap"):
            hints.append("audit disponível -> k8s-audit / k8s-audit --status / k8s-events")
        else:
            hints.append("sem audit -> alterações/eventos k8s só via kubectl (events ~1h) ou CloudTrail (API AWS)")

    groups = {}
    for term in _source_terms(args):
        for g in backend.describe_log_groups(term):
            groups[g["logGroupName"]] = g
    names = sorted(groups)
    ci_prefix = f"/aws/containerinsights/{args.cluster}/" if args.cluster else None
    if ci_prefix:
        ci = [n[len(ci_prefix):] for n in names if n.startswith(ci_prefix)]
        print(f"container insights: {'presente (' + ','.join(ci) + ')' if ci else 'ausente'}")
    print(f"log groups relacionados: {len(names)}" + (f" (exibindo {args.limit})" if len(names) > args.limit else ""))

    rows, app_groups = [], []
    for n in names[: args.limit]:
        g = groups[n]
        last = _last_event_ms(backend, n)
        stale = bool(last) and now_ms - last > STALE_DAYS * 86_400_000
        status = "vazio" if not last else ("PARADO" if stale else "ativo")
        if status == "ativo" and not n.endswith("/cluster"):
            app_groups.append(n)
        # a busca por logGroupNamePattern NÃO retorna retenção/tamanho; só exibe o que veio
        rows.append([n, f"{g['retentionInDays']}d" if g.get("retentionInDays") else "-",
                     fmt_ts(last) if last else "-", fmt_age(last, end) if last else "-", status])
    if rows:
        print_table(["log group", "retenção", "último evento", "idade", "status"], rows, args.width)
    if app_groups:
        hints.append(f"logs ativos -> logs --log-group {app_groups[0]} --since 3h --group-by message")
    elif not rows:
        hints.append("nenhum log group encontrado: logs da app podem estar só nos pods (kubectl logs) "
                     "ou em ferramenta externa (New Relic/Datadog/Loki)")
    for h in hints:
        print(f"# próximo passo: {h}")
    return 0


def main(argv=None):
    args = parse_args(argv)
    try:
        start, end = resolve_window(args)
        # valida entradas antes de abrir sessão AWS
        if args.mode == "sources":
            _source_terms(args)
        else:
            parse_duration(args.slice)
            if args.mode == "logs":
                parse_duration(args.bin)
            else:
                _k8s_pattern(args)
        backend = make_backend(args)
        cmd = {"sources": cmd_sources, "logs": cmd_logs}.get(args.mode, cmd_k8s)
        return cmd(args, backend, start, end)
    except (ValueError, AwsError) as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1
    except TimeoutError:
        print("Erro: tempo esgotado consultando a AWS (reduza a janela ou aumente --timeout)", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
