#!/usr/bin/env python3
"""
validate_skills.py — linter estático de conformidade e segurança das skills do noc-guard.

Para cada diretório em skills/*/ verifica:

  1. SKILL.md   frontmatter YAML válido com `name` (kebab-case, igual ao nome do
                diretório, <= 64) e `description` (20..1024 caracteres) + corpo não vazio.
  2. Segurança  os scripts (*.py via AST; *.sh/*.ps1 via regex) não podem conter
                mutação não supervisionada, em linha com o steering noc-readonly-first:
                chamadas SDK de escrita (delete_*, put_*, ...), verbos de mutação da
                AWS CLI (delete-*, s3 cp/sync/rm, ...), kubectl de escrita, escrita/remoção
                em disco, shell=True, eval/exec.
                Exceção auditável: comentário `# noc-guard: allow-mutation: <motivo>`
                na mesma linha ou na linha anterior (motivo >= 10 caracteres).
     Custo     APIs cobradas (Logs Insights, Live Tail, GetMetricData, Athena...) são
                proibidas pela regra de custo zero e NÃO aceitam exceção.
  3. Tokens     scripts que consultam APIs de logs/eventos (FilterLogEvents,
                LookupEvents, GetLogEvents) precisam de evidência de contenção:
                parâmetro/argumento de limite (limit, MaxResults, --max-items...) ou
                um teto explícito (`if n >= 100: return|break`).

É uma análise heurística (não substitui revisão humana), feita sem executar as skills.

Uso:
    python3 scripts/validate_skills.py                    # valida ./skills do repositório
    python3 scripts/validate_skills.py --skills-dir DIR   # valida outro diretório
Exit code: 0 = tudo conforme; 1 = há erros.
"""
import argparse
import ast
import re
import sys
from pathlib import Path

DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"
SCRIPT_SUFFIXES = (".py", ".sh", ".ps1")

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PRAGMA_RE = re.compile(r"#\s*noc-guard:\s*allow-mutation\b[\s:\-]*(?P<reason>.*)$")
MIN_REASON = 10

# ------------------------------------------------------------- vocabulário
MUTATION_PREFIXES = (
    "create", "delete", "update", "put", "modify", "terminate", "start", "stop", "reboot",
    "attach", "detach", "remove", "restore", "reset", "revoke", "authorize", "disable",
    "enable", "deregister", "register", "tag", "untag", "import", "copy", "run", "invoke",
    "send", "publish", "execute", "cancel", "replace", "associate", "disassociate",
)
_MUT = "|".join(MUTATION_PREFIXES)
SDK_MUTATION_RE = re.compile(rf"^(?:{_MUT})_[a-z0-9_]+$")       # client.delete_log_group(...)
CLI_MUTATION_RE = re.compile(rf"^(?:{_MUT})-[a-z0-9-]+$")       # "delete-log-group"
TEXT_AWS_MUTATION_RE = re.compile(rf"\baws\s+[a-z0-9-]+\s+(?:{_MUT})-[a-z0-9-]+")
S3_WRITE_VERBS = ("cp", "mv", "rm", "sync", "rb", "mb")
TEXT_S3_WRITE_RE = re.compile(rf"\baws\s+s3\s+(?:{'|'.join(S3_WRITE_VERBS)})\b")
KUBECTL_WRITE_VERBS = ("delete", "apply", "create", "edit", "patch", "replace", "scale", "set",
                       "label", "annotate", "drain", "cordon", "uncordon", "taint", "exec", "cp")
TEXT_KUBECTL_WRITE_RE = re.compile(
    rf"\bkubectl\b[^\n|;&]*?\s(?:{'|'.join(KUBECTL_WRITE_VERBS)}|rollout\s+restart)\b")
TEXT_LOCAL_DESTRUCTIVE_RE = re.compile(
    r"(?:^|[\s;&|(])(?:rm\s+-[a-zA-Z]*[rf]|Remove-Item\b|mkfs|dd\s+if=|shred\b|truncate\s+-s|"
    r"systemctl\s+(?:restart|stop|start|disable|enable)|docker\s+(?:rm|restart|stop|kill|exec)|"
    r"(?:shutdown|reboot)\b)")

# Regra de custo zero (steering): sem exceção possível.
BILLED_APIS = {
    "start_query", "start-query", "start_live_tail", "start-live-tail",
    "get_metric_data", "get-metric-data", "get_metric_widget_image", "get-metric-widget-image",
    "get_insight_rule_report", "get-insight-rule-report",
    "start_query_execution", "start-query-execution",  # Athena
}
BILLED_SERVICES = {"athena"}

# Chamadas locais de escrita/remoção/execução arbitrária.
MODULE_CALLS = {
    "os": {"remove", "unlink", "rmdir", "removedirs", "rename", "replace", "system", "popen",
           "makedirs", "mkdir", "chmod", "chown", "truncate", "kill"},
    "shutil": {"rmtree", "move", "copy", "copy2", "copyfile", "copytree", "chown"},
}
PATH_WRITE_METHODS = {"unlink", "rmdir", "rmtree", "write_text", "write_bytes", "touch", "mkdir",
                      "symlink_to", "hardlink_to", "chmod"}
DANGEROUS_BUILTINS = {"eval", "exec"}

# Contenção de tokens.
LOG_APIS = {"lookup_events", "lookup-events", "filter_log_events", "filter-log-events",
            "get_log_events", "get-log-events"}
LIMIT_MARKERS = {"limit", "--limit", "MaxResults", "maxResults", "MaxItems", "max_items",
                 "--max-items", "--max-results", "--max-events", "max_events", "PaginationConfig"}


# ----------------------------------------------------------------- modelos
class Finding:
    def __init__(self, level, path, line, category, message):
        self.level, self.path, self.line = level, path, line
        self.category, self.message = category, message

    def __str__(self):
        loc = f"{self.path}:{self.line}" if self.line else str(self.path)
        return f"  {self.level:<5} {loc} [{self.category}] {self.message}"


class SkillReport:
    def __init__(self, name):
        self.name = name
        self.findings = []
        self.token_evidence = []

    @property
    def errors(self):
        return [f for f in self.findings if f.level == "ERROR"]

    def add(self, *args):
        self.findings.append(Finding(*args))


# ------------------------------------------------------------- SKILL.md
def parse_frontmatter(text):
    """Frontmatter YAML simples (sem dependência de PyYAML).

    Suporta `chave: valor`, valores entre aspas e blocos `>`/`|` indentados.
    Retorna (dict, corpo) ou levanta ValueError.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md deve começar com '---' (frontmatter YAML)")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError("frontmatter sem '---' de fechamento")
    data, key = {}, None
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[:1] in (" ", "\t"):
            if key is None:
                raise ValueError(f"linha indentada sem chave: {raw!r}")
            data[key] = (data[key] + " " + raw.strip()).strip()
            continue
        if ":" not in raw:
            raise ValueError(f"linha inválida no frontmatter: {raw!r}")
        key, value = raw.split(":", 1)
        key, value = key.strip(), value.strip()
        if value in (">", "|", ">-", "|-"):
            value = ""
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        data[key] = value
    return data, "\n".join(lines[end + 1:])


def check_skill_md(skill_dir, report):
    md = skill_dir / "SKILL.md"
    rel = f"{skill_dir.name}/SKILL.md"
    if not md.is_file():
        report.add("ERROR", rel, 0, "skill-md", "SKILL.md ausente")
        return
    try:
        meta, body = parse_frontmatter(md.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        report.add("ERROR", rel, 0, "skill-md", str(e))
        return
    name, desc = meta.get("name", ""), meta.get("description", "")
    if not name:
        report.add("ERROR", rel, 0, "skill-md", "frontmatter sem 'name'")
    elif not NAME_RE.match(name) or len(name) > 64:
        report.add("ERROR", rel, 0, "skill-md", f"'name' inválido (kebab-case, <= 64): {name!r}")
    elif name != skill_dir.name:
        report.add("ERROR", rel, 0, "skill-md",
                   f"'name' ({name}) difere do diretório ({skill_dir.name})")
    if not desc:
        report.add("ERROR", rel, 0, "skill-md", "frontmatter sem 'description'")
    elif not 20 <= len(desc) <= 1024:
        report.add("ERROR", rel, 0, "skill-md", f"'description' deve ter 20..1024 caracteres ({len(desc)})")
    if not body.strip():
        report.add("ERROR", rel, 0, "skill-md", "SKILL.md sem documentação após o frontmatter")


# ----------------------------------------------------------- análise .py
def _pragmas(source):
    """{linha: motivo} dos comentários allow-mutation."""
    out = {}
    for i, line in enumerate(source.splitlines(), 1):
        m = PRAGMA_RE.search(line)
        if m:
            out[i] = m.group("reason").strip()
    return out


def _docstring_ids(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def _const_str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _seq_strings(node):
    return [s for s in (_const_str(e) for e in node.elts) if s is not None]


def _list_mutation(strs):
    """Detecta argv literal de mutação: ['aws','s3','sync',...] / ['kubectl','delete',...]."""
    if "aws" in strs:
        rest = strs[strs.index("aws") + 1:]
        if len(rest) >= 2 and rest[0] == "s3" and rest[1] in S3_WRITE_VERBS:
            return f"aws s3 {rest[1]}"
        for s in rest[:3]:
            if CLI_MUTATION_RE.match(s):
                return f"aws ... {s}"
    if "kubectl" in strs:
        rest = strs[strs.index("kubectl") + 1:]
        for i, s in enumerate(rest):
            if s in KUBECTL_WRITE_VERBS or (s == "rollout" and rest[i + 1:i + 2] == ["restart"]):
                return f"kubectl {s}"
    return None


def _open_write_mode(call):
    mode = None
    if len(call.args) >= 2:
        mode = _const_str(call.args[1])
    for kw in call.keywords:
        if kw.arg == "mode":
            mode = _const_str(kw.value) or "?"
    return mode if mode and any(c in mode for c in "wax+?") else None


class _PyVisitor(ast.NodeVisitor):
    def __init__(self, tree):
        self.docstrings = _docstring_ids(tree)
        self.security = []   # (line, msg)
        self.cost = []       # (line, msg)
        self.log_api = []    # (line, api)
        self.limits = []     # (line, evidência)

    # --- nomes usados como API (atributo ou string)
    def _api_name(self, name, line):
        if name in BILLED_APIS:
            self.cost.append((line, f"API cobrada '{name}' (regra de custo zero)"))
        if name in LOG_APIS:
            self.log_api.append((line, name))
        if name in LIMIT_MARKERS:
            self.limits.append((line, f"limite '{name}'"))

    def visit_Constant(self, node):
        s = _const_str(node)
        if s is not None and id(node) not in self.docstrings:
            self._api_name(s, node.lineno)
            if s in BILLED_SERVICES:
                self.cost.append((node.lineno, f"serviço cobrado '{s}' (regra de custo zero)"))
            elif s not in BILLED_APIS and CLI_MUTATION_RE.match(s):
                self.security.append((node.lineno, f"verbo de mutação da AWS CLI '{s}'"))
            for rx, label in ((TEXT_AWS_MUTATION_RE, "comando AWS de mutação"),
                              (TEXT_S3_WRITE_RE, "escrita via aws s3"),
                              (TEXT_KUBECTL_WRITE_RE, "kubectl de escrita"),
                              (TEXT_LOCAL_DESTRUCTIVE_RE, "comando local destrutivo")):
                m = rx.search(s)
                if m:
                    self.security.append((node.lineno, f"{label} em string: '{m.group(0).strip()}'"))
        self.generic_visit(node)

    def _visit_seq(self, node):
        cmd = _list_mutation(_seq_strings(node))
        if cmd:
            self.security.append((node.lineno, f"argv de mutação '{cmd}'"))
        self.generic_visit(node)

    visit_List = visit_Tuple = _visit_seq

    def visit_keyword(self, node):
        if node.arg:
            self._api_name(node.arg, getattr(node.value, "lineno", 0))
        self.generic_visit(node)

    def visit_Call(self, node):
        f = node.func
        if isinstance(f, ast.Attribute):
            attr = f.attr
            self._api_name(attr, node.lineno)
            owner = f.value.id if isinstance(f.value, ast.Name) else None
            if owner in MODULE_CALLS and attr in MODULE_CALLS[owner]:
                self.security.append((node.lineno, f"operação local de escrita/execução '{owner}.{attr}'"))
            elif attr in PATH_WRITE_METHODS:
                self.security.append((node.lineno, f"escrita/remoção em disco '.{attr}()'"))
            elif attr not in BILLED_APIS and SDK_MUTATION_RE.match(attr):
                self.security.append((node.lineno, f"chamada SDK de mutação '.{attr}()'"))
            if attr == "open" and _open_write_mode(node):
                self.security.append((node.lineno, f"arquivo aberto para escrita (mode={_open_write_mode(node)!r})"))
            if attr in ("client", "resource") and node.args and _const_str(node.args[0]) in BILLED_SERVICES:
                self.cost.append((node.lineno, f"cliente de serviço cobrado '{_const_str(node.args[0])}'"))
        elif isinstance(f, ast.Name):
            if f.id in DANGEROUS_BUILTINS:
                self.security.append((node.lineno, f"execução dinâmica '{f.id}()'"))
            elif f.id == "open" and _open_write_mode(node):
                self.security.append((node.lineno, f"arquivo aberto para escrita (mode={_open_write_mode(node)!r})"))
        for kw in node.keywords:
            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                self.security.append((node.lineno, "subprocess com shell=True"))
        self.generic_visit(node)

    def visit_Subscript(self, node):
        key = _const_str(node.slice)
        if key in LIMIT_MARKERS:
            self.limits.append((node.lineno, f"limite '{key}'"))
        self.generic_visit(node)

    def visit_Dict(self, node):
        for k in node.keys:
            if k is not None and _const_str(k) in LIMIT_MARKERS:
                self.limits.append((k.lineno, f"limite '{_const_str(k)}'"))
        self.generic_visit(node)

    def visit_If(self, node):
        # Teto explícito: `if <x> >= N: ... return|break` (N inteiro >= 1).
        t = node.test
        if isinstance(t, ast.Compare) and len(t.ops) == 1 and isinstance(t.ops[0], (ast.GtE, ast.Gt)):
            right = t.comparators[0]
            if isinstance(right, ast.Constant) and isinstance(right.value, int) and right.value >= 1 \
                    and any(isinstance(n, (ast.Return, ast.Break)) for b in node.body for n in ast.walk(b)):
                self.limits.append((node.lineno, f"teto explícito {ast.unparse(t)} -> return/break"))
        self.generic_visit(node)


def _apply_findings(items, pragmas, rel, report, category):
    used = set()
    for line, msg in sorted(set(items)):
        pline = line if line in pragmas else (line - 1 if (line - 1) in pragmas else None)
        if pline is not None and len(pragmas[pline]) >= MIN_REASON:
            used.add(pline)
            report.add("NOTE", rel, line, category, f"{msg} — permitido: {pragmas[pline]}")
        elif pline is not None:
            used.add(pline)
            report.add("ERROR", rel, line, category,
                       f"{msg} — allow-mutation sem motivo (mín. {MIN_REASON} caracteres)")
        else:
            report.add("ERROR", rel, line, category, msg)
    return used


def check_python(path, rel, report):
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        report.add("ERROR", rel, e.lineno or 0, "syntax", f"erro de sintaxe: {e.msg}")
        return
    v = _PyVisitor(tree)
    v.visit(tree)
    pragmas = _pragmas(source)
    used = _apply_findings(v.security, pragmas, rel, report, "security")
    for line, msg in sorted(set(v.cost)):
        report.add("ERROR", rel, line, "cost", msg + " — sem exceção possível")
    for line in sorted(set(pragmas) - used):
        report.add("WARN", rel, line, "security", "allow-mutation sem achado correspondente (remova)")
    if v.log_api:
        apis = sorted({a for _, a in v.log_api})
        if v.limits:
            line, ev = sorted(v.limits)[0]
            report.token_evidence.append(f"{rel}: {', '.join(apis)} contido por {ev} (linha {line})")
        else:
            report.add("ERROR", rel, v.log_api[0][0], "tokens",
                       f"consulta {', '.join(apis)} sem paginação limitada nem teto de resultados")


def check_text_script(path, rel, report):
    """Scripts shell/PowerShell: varredura por linha (sem AST)."""
    source = path.read_text(encoding="utf-8")
    pragmas = _pragmas(source)
    items, logs, limited = [], [], False
    for i, raw in enumerate(source.splitlines(), 1):
        line = raw.split("#", 1)[0] if path.suffix == ".sh" else raw
        for rx, label in ((TEXT_AWS_MUTATION_RE, "comando AWS de mutação"),
                          (TEXT_S3_WRITE_RE, "escrita via aws s3"),
                          (TEXT_KUBECTL_WRITE_RE, "kubectl de escrita"),
                          (TEXT_LOCAL_DESTRUCTIVE_RE, "comando local destrutivo")):
            m = rx.search(line)
            if m:
                items.append((i, f"{label}: '{m.group(0).strip()}'"))
        for api in BILLED_APIS:
            if "-" in api and re.search(rf"\b{re.escape(api)}\b", line):
                report.add("ERROR", rel, i, "cost", f"API cobrada '{api}' — sem exceção possível")
        if any(re.search(rf"\b{re.escape(a)}\b", line) for a in LOG_APIS if "-" in a):
            logs.append(i)
        if re.search(r"--max-items|--limit|--max-results|\|\s*head\b", line):
            limited = True
    used = _apply_findings(items, pragmas, rel, report, "security")
    for line in sorted(set(pragmas) - used):
        report.add("WARN", rel, line, "security", "allow-mutation sem achado correspondente (remova)")
    if logs and not limited:
        report.add("ERROR", rel, logs[0], "tokens", "consulta de logs/eventos sem --max-items/--limit/head")
    elif logs:
        report.token_evidence.append(f"{rel}: consulta de logs/eventos com limite")


# ---------------------------------------------------------------- driver
def skill_dirs(skills_dir):
    return sorted(d for d in skills_dir.iterdir()
                  if d.is_dir() and not d.name.startswith((".", "_")))


def validate_skill(skill_dir):
    report = SkillReport(skill_dir.name)
    check_skill_md(skill_dir, report)
    scripts = sorted(p for p in skill_dir.rglob("*")
                     if p.is_file() and p.suffix in SCRIPT_SUFFIXES and "__pycache__" not in p.parts)
    for path in scripts:
        rel = path.relative_to(skill_dir.parent).as_posix()
        if path.suffix == ".py":
            check_python(path, rel, report)
        else:
            check_text_script(path, rel, report)
    return report


def validate(skills_dir):
    skills_dir = Path(skills_dir)
    if not skills_dir.is_dir():
        raise FileNotFoundError(f"diretório de skills não encontrado: {skills_dir}")
    return [validate_skill(d) for d in skill_dirs(skills_dir)]


def main(argv=None):
    p = argparse.ArgumentParser(description="Valida conformidade e segurança das skills do noc-guard.")
    p.add_argument("--skills-dir", default=str(DEFAULT_SKILLS_DIR), help="diretório com skills/*/")
    args = p.parse_args(argv)
    try:
        reports = validate(args.skills_dir)
    except FileNotFoundError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    if not reports:
        print(f"erro: nenhuma skill encontrada em {args.skills_dir}", file=sys.stderr)
        return 1
    total_err = 0
    for r in reports:
        status = "FAIL" if r.errors else "OK"
        print(f"[{status:<4}] {r.name}")
        for f in r.findings:
            print(f)
        for ev in r.token_evidence:
            print(f"  TOKEN {ev}")
        total_err += len(r.errors)
    ok = sum(1 for r in reports if not r.errors)
    print(f"skills: {len(reports)}  ok: {ok}  erros: {total_err}")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
