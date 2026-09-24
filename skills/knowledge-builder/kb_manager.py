#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import datetime
from pathlib import Path

def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def sync_from_s3(bucket, local_dir):
    print(f"📥 Sincronizando da nuvem S3 (s3://{bucket}) para {local_dir}...")
    code, out, err = run_cmd(["aws", "s3", "sync", f"s3://{bucket}", str(local_dir), "--exact-timestamps"])
    if code != 0:
        print(f"⚠️ Aviso: falha ao baixar do S3 (o bucket pode estar vazio ou sem permissão): {err.strip()}")

def sync_to_s3(bucket, local_dir):
    print(f"📤 Sincronizando de {local_dir} para a nuvem S3 (s3://{bucket})...")
    code, out, err = run_cmd(["aws", "s3", "sync", str(local_dir), f"s3://{bucket}", "--exact-timestamps"])
    if code != 0:
        print(f"❌ Erro ao enviar para o S3: {err.strip()}")
        return False
    return True

def sanitize_filename(name):
    clean = "".join(c for c in name if c.isalnum() or c in ("-", "_", " ")).strip()
    clean = clean.replace(" ", "_")
    return (clean or "incidente_geral") + ".md"

def add_entry(bucket, local_dir, alert_name, content):
    sync_from_s3(bucket, local_dir)
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = sanitize_filename(alert_name)
    file_path = local_dir / filename
    
    entry_text = f"\n### [{date_str}] {alert_name}\n{content.strip()}\n"
    
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(entry_text)
    
    print(f"✅ Análise registrada localmente em: {file_path}")
    if sync_to_s3(bucket, local_dir):
        print("☁️ Base de conhecimento atualizada com sucesso no S3!")

def search_entry(bucket, local_dir, query):
    if bucket:
        sync_from_s3(bucket, local_dir)
        
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
    
    args = parser.parse_args()
    
    local_dir = Path.home() / ".kiro" / "noc-guard" / "kb"
    local_dir.mkdir(parents=True, exist_ok=True)
    
    if args.action == "add":
        if not args.alert or not args.content:
            print("Erro: --alert e --content são obrigatórios para registrar um aprendizado.", file=sys.stderr)
            sys.exit(1)
        add_entry(args.bucket, local_dir, args.alert, args.content)
    elif args.action == "search":
        if not args.query:
            print("Erro: --query é obrigatório para pesquisar na base de conhecimento.", file=sys.stderr)
            sys.exit(1)
        search_entry(args.bucket, local_dir, args.query)
    elif args.action == "sync":
        sync_from_s3(args.bucket, local_dir)
        sync_to_s3(args.bucket, local_dir)
        print("✅ Sincronização concluída.")

if __name__ == "__main__":
    main()
