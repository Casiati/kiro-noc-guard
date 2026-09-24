#!/usr/bin/env python3
import os
import argparse
import subprocess
import datetime
from pathlib import Path

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Erro (pode ser ignorado se bucket novo/vazio): {result.stderr}")
    return result.stdout

def sync_from_s3(bucket, local_dir):
    print(f"📥 Baixando do S3 ({bucket}) para {local_dir}...")
    run_cmd(f"aws s3 sync s3://{bucket} {local_dir} --exact-timestamps")

def sync_to_s3(bucket, local_dir):
    print(f"📤 Subindo de {local_dir} para o S3 ({bucket})...")
    run_cmd(f"aws s3 sync {local_dir} s3://{bucket} --exact-timestamps")

def add_entry(bucket, local_dir, alert_name, content):
    sync_from_s3(bucket, local_dir)
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    filename = "".join(x for x in alert_name if x.isalnum() or x in " -_").strip().replace(" ", "_") + ".md"
    file_path = os.path.join(local_dir, filename)
    
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"\n### {date_str}\n")
        f.write(content + "\n")
    
    print(f"✅ Registro adicionado em {file_path}")
    sync_to_s3(bucket, local_dir)

def search_entry(local_dir, query):
    print(f"🔎 Buscando por '{query}' na base de conhecimento...")
    cmd = f'grep -ri "{query}" {local_dir}'
    out = run_cmd(cmd)
    if not out.strip():
        print("Nenhum registro encontrado.")
    else:
        print(out)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kiro NOC Knowledge Base Manager")
    parser.add_argument("--bucket", required=True, help="Nome do bucket S3 (ex: opsteam-noc-runbooks-dev)")
    parser.add_argument("--action", choices=["add", "search", "sync"], required=True)
    parser.add_argument("--alert", help="Nome do alerta/topico para adicionar")
    parser.add_argument("--content", help="Conteudo da analise")
    parser.add_argument("--query", help="Termo de busca")
    args = parser.parse_args()

    local_dir = os.path.expanduser("~/.kiro/kb")
    os.makedirs(local_dir, exist_ok=True)

    if args.action == "add":
        if not args.alert or not args.content:
            print("Erro: --alert e --content sao obrigatorios para action=add")
            exit(1)
        add_entry(args.bucket, local_dir, args.alert, args.content)
    elif args.action == "search":
        sync_from_s3(args.bucket, local_dir)
        if not args.query:
            print("Erro: --query obrigatorio para action=search")
            exit(1)
        search_entry(local_dir, args.query)
    elif args.action == "sync":
        sync_from_s3(args.bucket, local_dir)
        sync_to_s3(args.bucket, local_dir)
        print("✅ Sincronizacao completa.")
