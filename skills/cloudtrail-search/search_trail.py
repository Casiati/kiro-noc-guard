#!/usr/bin/env python3
import argparse
import boto3
import json
import sys
from datetime import datetime, timedelta
import botocore.exceptions

def parse_args():
    parser = argparse.ArgumentParser(description="Fast CloudTrail Search for NOC")
    parser.add_argument("--profile", required=True, help="AWS Profile")
    parser.add_argument("--region", default="us-east-1", help="AWS Region")
    parser.add_argument("--since", default="1h", help="Time window (e.g., 1m, 30m, 1h, 24h, 7d)")
    parser.add_argument("--event-name", help="Filter by EventName")
    parser.add_argument("--username", help="Filter by Username")
    parser.add_argument("--resource-name", help="Filter by ResourceName")
    parser.add_argument("--errors-only", action="store_true", help="Show only events with errors")
    return parser.parse_args()

def parse_time(since_str):
    unit = since_str[-1]
    try:
        val = int(since_str[:-1])
    except ValueError:
        raise ValueError("Formato de tempo invalido. Use um numero seguido de m, h ou d (ex: 30m, 1h, 7d)")
    
    if unit == 'h':
        return datetime.utcnow() - timedelta(hours=val)
    elif unit == 'd':
        return datetime.utcnow() - timedelta(days=val)
    elif unit == 'm':
        return datetime.utcnow() - timedelta(minutes=val)
    else:
        raise ValueError("Unidade de tempo invalida. Use m (minutos), h (horas) ou d (dias).")

def run():
    args = parse_args()
    try:
        start_time = parse_time(args.since)
    except ValueError as e:
        print(f"Erro: {e}")
        sys.exit(1)

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    client = session.client('cloudtrail')

    lookup_attrs = []
    if args.event_name:
        lookup_attrs.append({'AttributeKey': 'EventName', 'AttributeValue': args.event_name})
    if args.username:
        lookup_attrs.append({'AttributeKey': 'Username', 'AttributeValue': args.username})
    if args.resource_name:
        lookup_attrs.append({'AttributeKey': 'ResourceName', 'AttributeValue': args.resource_name})
    
    if len(lookup_attrs) > 1:
        print("Erro: A API lookup_events do AWS CloudTrail suporta filtro por apenas UM atributo de cada vez (EventName, Username OU ResourceName).")
        sys.exit(1)

    kwargs = {'StartTime': start_time}
    if lookup_attrs:
        kwargs['LookupAttributes'] = lookup_attrs

    paginator = client.get_paginator('lookup_events')
    
    print(f"{'Hora (UTC)':<20} | {'Usuario':<25} | {'Acao':<30} | {'Recurso':<30} | {'Status/Erro':<20} | {'IP'}")
    print("-" * 150)
    
    count = 0
    try:
        for page in paginator.paginate(**kwargs):
            for event in page.get('Events', []):
                evt_data = json.loads(event.get('CloudTrailEvent', '{}'))
                
                err_code = evt_data.get('errorCode', '')
                if args.errors_only and not err_code:
                    continue
                
                status = err_code if err_code else "Success"
                user = event.get('Username', 'N/A')
                action = event.get('EventName', 'N/A')
                
                resources = [r.get('ResourceName') for r in event.get('Resources', []) if r.get('ResourceName')]
                res_str = resources[0] if resources else 'N/A'
                if len(res_str) > 28:
                    res_str = res_str[:25] + "..."
                    
                user_str = user[:23] + ".." if len(user) > 25 else user
                action_str = action[:28] + ".." if len(action) > 30 else action
                
                ip = evt_data.get('sourceIPAddress', 'N/A')
                time_str = event.get('EventTime').strftime('%Y-%m-%d %H:%M:%S') if event.get('EventTime') else 'N/A'
                
                print(f"{time_str:<20} | {user_str:<25} | {action_str:<30} | {res_str:<30} | {status:<20} | {ip}")
                count += 1
                if count >= 100:
                    print("... [Truncado em 100 resultados para poupar tokens. Refine os filtros se precisar de mais.]")
                    return
    except botocore.exceptions.ClientError as e:
         print(f"Erro na API AWS: {e}")
    
    if count == 0:
        print("Nenhum evento correspondente encontrado na janela de tempo.")

if __name__ == '__main__':
    run()
