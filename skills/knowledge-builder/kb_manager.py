#!/usr/bin/env python3
import os
import re
import sys
import argparse
import subprocess
import datetime
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

def search_entry(bucket, local_dir, query, profile=None):
    if bucket:
        sync_from_s3(bucket, local_dir, profile)
        
    print(f"🔎 Pesquisando por '{query}' na base de conhecimento...")
    found = False
    query_lower = query.lower()
    
    for md_file in local_dir.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            if query_lower in content.lower():
                print(f"\n📄 Arquivo: {md_file.name}")
                print("-" * 60)
                # Exibe blocos correspondentes
                for block in content.split("### "):
                    if query_lower in block.lower():
                        print(f"### {block.strip()}\n")
                found = True
        except Exception as e:
            pass
            
    if not found:
        print(f"Nenhum registro encontrado para '{query}'.")

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
