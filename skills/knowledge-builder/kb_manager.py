#!/usr/bin/env python3
import os
import re
import sys
import argparse
import subprocess
import datetime
import unicodedata
from pathlib import Path

# Mesma regra de validação de nome de bucket S3 usada em install.sh/install.ps1:
# 3-63 caracteres, minusculas/numeros/hifen/ponto, sem '..'.
BUCKET_RE = re.compile(r'^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$')

def valid_bucket(bucket):
    return bool(bucket) and bool(BUCKET_RE.match(bucket)) and ".." not in bucket

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", f"comando '{cmd[0]}' não encontrado. Instale o AWS CLI para usar a Base de Conhecimento compartilhada."

def s3_sync_cmd(src, dst, profile=None):
    """Monta o comando aws s3 sync, com --profile explícito quando informado.

    O bucket da Base de Conhecimento normalmente vive numa conta AWS
    separada (ex.: conta de serviços do NOC), distinta da conta do
    cliente/incidente sendo investigado. Sem --profile explícito, o AWS CLI
    usa AWS_PROFILE/default do ambiente, que pode não ter (e frequentemente
    não tem) permissão nesse bucket — mesmo que uma sessão SSO válida para
    OUTRA conta esteja ativa. Por isso este profile é sempre independente
    do --profile usado na investigação do incidente.
    """
    # noc-guard: allow-mutation: sync apenas entre o cache local e o bucket da KB do NOC (nunca conta de cliente)
    cmd = ["aws", "s3", "sync", src, dst, "--exact-timestamps"]
    if profile:
        cmd.extend(["--profile", profile])
    return cmd

def sync_from_s3(bucket, local_dir, profile=None):
    print(f"📥 Sincronizando da nuvem S3 (s3://{bucket}) para {local_dir}...")
    code, out, err = run_cmd(s3_sync_cmd(f"s3://{bucket}", str(local_dir), profile))
    if code != 0:
        hint = _profile_hint(err, profile)
        print(f"⚠️ Aviso: falha ao baixar do S3 (o bucket pode estar vazio ou sem permissão): {err.strip()}{hint}")

def sync_to_s3(bucket, local_dir, profile=None):
    print(f"📤 Sincronizando de {local_dir} para a nuvem S3 (s3://{bucket})...")
    code, out, err = run_cmd(s3_sync_cmd(str(local_dir), f"s3://{bucket}", profile))
    if code != 0:
        hint = _profile_hint(err, profile)
        print(f"❌ Erro ao enviar para o S3: {err.strip()}{hint}")
        return False
    return True

def _profile_hint(err, profile):
    """Mensagem extra quando o erro parece ser falta de credenciais e nenhum
    --kb-profile foi informado — a causa mais comum nesse cenário multi-conta."""
    if profile:
        return ""
    if "credentials" in err.lower() or "Unable to locate" in err:
        return (" | Dica: nenhum --kb-profile foi informado, então o AWS CLI usou "
                "AWS_PROFILE/default do ambiente. O bucket da KB costuma estar numa "
                "conta separada da conta investigada — informe o profile correto da "
                "conta do bucket com --kb-profile <nome>.")
    return ""

def sanitize_filename(name):
    clean = "".join(c for c in name if c.isalnum() or c in ("-", "_", " ")).strip()
    clean = clean.replace(" ", "_")
    return (clean or "incidente_geral") + ".md"

def add_entry(bucket, local_dir, alert_name, content, profile=None):
    sync_from_s3(bucket, local_dir, profile)
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = sanitize_filename(alert_name)
    file_path = local_dir / filename
    
    entry_text = f"\n### [{date_str}] {alert_name}\n{content.strip()}\n"
    
    # noc-guard: allow-mutation: append do registro no cache local da KB (~/.kiro/noc-guard/kb)
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(entry_text)
    
    print(f"✅ Análise registrada localmente em: {file_path}")
    if sync_to_s3(bucket, local_dir, profile):
        print("☁️ Base de conhecimento atualizada com sucesso no S3!")
        return True
    else:
        print("⚠️ ATENÇÃO: o registro ficou APENAS local — a equipe NÃO recebeu esta atualização "
              "(falha ao sincronizar com o S3). Rode 'kb_manager.py --action sync' (com --kb-profile "
              "se necessário) quando o acesso ao bucket for restabelecido.", file=sys.stderr)
        return False

# --- Busca -------------------------------------------------------------------
# A consulta é separada em termos (palavras); acentos e caixa são ignorados nos dois
# lados. Primeiro exige TODOS os termos no arquivo (nome + conteúdo), em qualquer
# ordem (AND). Se ninguém satisfaz, repete com QUALQUER termo (OR), avisando que a
# correspondência é parcial. Registros = blocos que começam em "### [data] título".
BLOCK_SPLIT_RE = re.compile(r'(?m)^(?=### )')
BLOCK_DATE_RE = re.compile(r'^### \[(\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?)\]')
MAX_FILES = 10             # contenção de tokens: arquivos exibidos por consulta
MAX_BLOCKS_PER_FILE = 3    # contenção de tokens: registros exibidos por arquivo

def normalize(text):
    """Minúsculas e sem acentos (NFKD), para comparar 'investigação' == 'investigacao'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()

def split_terms(query):
    """Termos únicos da consulta como pares (como digitado, normalizado)."""
    terms, seen = [], set()
    for raw in query.split():
        norm = normalize(raw)
        if norm and norm not in seen:
            seen.add(norm)
            terms.append((raw, norm))
    return terms

def _block_date(block):
    m = BLOCK_DATE_RE.match(block)
    return m.group(1) if m else ""

def search_kb(local_dir, query):
    """Busca estruturada (sem saída no terminal). Retorna dict com mode/terms/files/unreadable.

    mode: 'all' (todos os termos), 'partial' (só alguns) ou 'none'.
    """
    terms = split_terms(query)
    candidates, unreadable = [], 0
    for md_file in sorted(local_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unreadable += 1
            continue
        haystack = normalize(md_file.name + "\n" + content)
        matched = [raw for raw, norm in terms if norm in haystack]
        if not matched:
            continue
        raw_blocks = [b for b in BLOCK_SPLIT_RE.split(content) if b.strip()]
        blocks = []
        for raw_block in raw_blocks:
            norm_block = normalize(raw_block)
            hits = sum(1 for _, norm in terms if norm in norm_block)
            if hits:
                blocks.append({"text": raw_block.strip(), "hits": hits, "date": _block_date(raw_block)})
        if not blocks:  # termo só no nome do arquivo: mostra o registro mais recente
            newest = sorted(raw_blocks, key=_block_date, reverse=True)[:1]
            blocks = [{"text": b.strip(), "hits": 0, "date": _block_date(b)} for b in newest]
        blocks.sort(key=lambda b: (b["hits"], b["date"]), reverse=True)
        candidates.append({
            "name": md_file.name,
            "matched": matched,
            "missing": [raw for raw, _ in terms if raw not in matched],
            "blocks": blocks,
            "latest": max((b["date"] for b in blocks), default=""),
        })

    def rank(f):
        return (len(f["matched"]), f["latest"])

    full = sorted((f for f in candidates if not f["missing"]), key=rank, reverse=True)
    if full:
        return {"mode": "all", "terms": terms, "files": full, "unreadable": unreadable}
    if candidates and len(terms) > 1:
        return {"mode": "partial", "terms": terms,
                "files": sorted(candidates, key=rank, reverse=True), "unreadable": unreadable}
    return {"mode": "none", "terms": terms, "files": [], "unreadable": unreadable}

def search_entry(bucket, local_dir, query, profile=None):
    if bucket:
        sync_from_s3(bucket, local_dir, profile)

    result = search_kb(local_dir, query)
    terms = result["terms"]
    print(f"🔎 Pesquisando por '{query}' na base de conhecimento "
          f"(termos: {', '.join(raw for raw, _ in terms)}; acentos e maiúsculas ignorados)...")
    if result["unreadable"]:
        print(f"⚠️ {result['unreadable']} arquivo(s) da KB não puderam ser lidos; "
              "o resultado pode estar incompleto.", file=sys.stderr)

    if result["mode"] == "none":
        print("Nenhum registro contém todos os termos. "
              "Tente termos isolados: ID do recurso, nome da instância, tipo de alerta.")
        return

    files = result["files"]
    if result["mode"] == "partial":
        print("⚠️ Correspondência PARCIAL: nenhum arquivo contém todos os termos. "
              "Mostrando arquivos com ao menos um (mais termos casados primeiro).")
    for f in files[:MAX_FILES]:
        info = f"{len(f['matched'])}/{len(terms)} termos"
        if f["missing"]:
            info += f"; faltou: {', '.join(f['missing'])}"
        if f["latest"]:
            info += f"; último registro: {f['latest']}"
        print(f"\n📄 Arquivo: {f['name']}  [{info}]")
        print("-" * 60)
        for block in f["blocks"][:MAX_BLOCKS_PER_FILE]:
            print(f"{block['text']}\n")
        extra = len(f["blocks"]) - MAX_BLOCKS_PER_FILE
        if extra > 0:
            print(f"... [TRUNCADO: +{extra} registro(s) neste arquivo; refine os termos]\n")
    if len(files) > MAX_FILES:
        print(f"\n⚠️ TRUNCADO: exibindo {MAX_FILES} de {len(files)} arquivos "
              "(ordenados por termos casados e data). Refine com um termo específico "
              "(ID do recurso, nome da instância) antes de concluir que não há mais registros.")

def main():
    parser = argparse.ArgumentParser(description="Gerenciador da Base de Conhecimento do NOC (S3 Sync)")
    parser.add_argument("--bucket", required=True, help="Nome completo do bucket S3 (ex: noc-runbooks-123456789012-us-east-1)")
    parser.add_argument("--action", choices=["add", "search", "sync"], required=True, help="Ação a executar")
    parser.add_argument("--alert", help="Nome do alerta ou tópico (obrigatório para action=add)")
    parser.add_argument("--content", help="Conteúdo do aprendizado/resolução (obrigatório para action=add)")
    parser.add_argument("--query", help="Termo de pesquisa (obrigatório para action=search)")
    parser.add_argument("--kb-profile", dest="kb_profile", default=os.environ.get("KB_PROFILE"),
                         help="Profile AWS (~/.aws/config) usado SOMENTE para acessar o bucket da Base de "
                              "Conhecimento — independente do profile usado na investigação do incidente, "
                              "já que o bucket normalmente vive numa conta separada. Pode também ser definido "
                              "via variável de ambiente KB_PROFILE.")

    args = parser.parse_args()

    if not valid_bucket(args.bucket):
        print("Erro: nome de bucket S3 inválido. Deve ter entre 3 e 63 caracteres "
              "(letras minúsculas, números, hífens e pontos; sem '..').", file=sys.stderr)
        sys.exit(1)
    
    local_dir = Path.home() / ".kiro" / "noc-guard" / "kb"
    # noc-guard: allow-mutation: cria o diretório de cache local da KB se ainda não existir
    local_dir.mkdir(parents=True, exist_ok=True)
    
    if args.action == "add":
        if not args.alert or not args.content:
            print("Erro: --alert e --content são obrigatórios para registrar um aprendizado.", file=sys.stderr)
            sys.exit(1)
        if not add_entry(args.bucket, local_dir, args.alert, args.content, args.kb_profile):
            sys.exit(2)  # registro salvo localmente, mas NÃO compartilhado com a equipe
    elif args.action == "search":
        if not args.query:
            print("Erro: --query é obrigatório para pesquisar na base de conhecimento.", file=sys.stderr)
            sys.exit(1)
        search_entry(args.bucket, local_dir, args.query, args.kb_profile)
    elif args.action == "sync":
        sync_from_s3(args.bucket, local_dir, args.kb_profile)
        if not sync_to_s3(args.bucket, local_dir, args.kb_profile):
            sys.exit(2)
        print("✅ Sincronização concluída.")

if __name__ == "__main__":
    main()
