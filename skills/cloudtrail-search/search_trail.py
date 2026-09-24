#!/usr/bin/env python3
import argparse
import json
import sys
import subprocess
from datetime import datetime, timedelta

try:
    import boto3
    import botocore.exceptions
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

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
        raise ValueError("Invalid time format. Use a number followed by m, h, or d (e.g., 30m, 1h, 7d)")
    
    if unit == 'h':
        return datetime.utcnow() - timedelta(hours=val)
    elif unit == 'd':
        return datetime.utcnow() - timedelta(days=val)
    elif unit == 'm':
        return datetime.utcnow() - timedelta(minutes=val)
    else:
        raise ValueError("Invalid time unit. Use m (minutes), h (hours), or d (days).")

def format_event_time(event_time):
    if not event_time:
        return 'N/A'
    if hasattr(event_time, 'strftime'):
        return event_time.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(event_time, (int, float)):
        return datetime.utcfromtimestamp(event_time).strftime('%Y-%m-%d %H:%M:%S')
    return str(event_time)[:19]

def fetch_events_boto3(args, start_time):
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
        print("Error: AWS CloudTrail lookup_events API supports filtering by only ONE attribute at a time (EventName, Username, OR ResourceName).", file=sys.stderr)
        sys.exit(1)

    kwargs = {'StartTime': start_time}
    if lookup_attrs:
        kwargs['LookupAttributes'] = lookup_attrs

    paginator = client.get_paginator('lookup_events')
    for page in paginator.paginate(**kwargs):
        yield page.get('Events', [])

def fetch_events_cli(args, start_time):
    start_epoch = int(start_time.timestamp())
    cmd = [
        "aws", "cloudtrail", "lookup-events",
        "--profile", args.profile,
        "--region", args.region,
        "--start-time", str(start_epoch),
        "--output", "json"
    ]
    if args.event_name:
        cmd.extend(["--lookup-attributes", f"AttributeKey=EventName,AttributeValue={args.event_name}"])
    elif args.username:
        cmd.extend(["--lookup-attributes", f"AttributeKey=Username,AttributeValue={args.username}"])
    elif args.resource_name:
        cmd.extend(["--lookup-attributes", f"AttributeKey=ResourceName,AttributeValue={args.resource_name}"])

    next_token = None
    while True:
        current_cmd = list(cmd)
        if next_token:
            current_cmd.extend(["--next-token", next_token])
        res = subprocess.run(current_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"AWS CLI Error: {res.stderr.strip()}", file=sys.stderr)
            break
        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError:
            print(f"Error parsing AWS CLI output: {res.stdout[:200]}", file=sys.stderr)
            break

        yield data.get("Events", [])
        next_token = data.get("NextToken")
        if not next_token:
            break

def run():
    args = parse_args()
    try:
        start_time = parse_time(args.since)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if HAS_BOTO3:
        events_gen = fetch_events_boto3(args, start_time)
    else:
        events_gen = fetch_events_cli(args, start_time)

    print(f"{'Time (UTC)':<20} | {'User':<25} | {'Action':<30} | {'Resource':<30} | {'Status/Error':<20} | {'IP'}")
    print("-" * 150)
    
    count = 0
    try:
        for events in events_gen:
            for event in events:
                raw_evt = event.get('CloudTrailEvent', '{}')
                evt_data = json.loads(raw_evt) if isinstance(raw_evt, str) else raw_evt
                
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
                time_str = format_event_time(event.get('EventTime'))
                
                print(f"{time_str:<20} | {user_str:<25} | {action_str:<30} | {res_str:<30} | {status:<20} | {ip}")
                count += 1
                if count >= 100:
                    print("... [Truncated at 100 results to save tokens. Refine filters if you need more.]")
                    return
    except Exception as e:
        print(f"Error processing events: {e}", file=sys.stderr)
    
    if count == 0:
        print("No matching events found in the time window.")

if __name__ == '__main__':
    run()
