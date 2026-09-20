#!/usr/bin/env bash
set -eu
bash /workspace/epalle/_pod_start_comfy_now.sh
echo "---LISTEN---"
ss -lntp | grep 8188 || true
echo "---QUEUE---"
curl -sS --max-time 8 http://127.0.0.1:8188/queue
echo
echo "---HOST---"
curl -sS -D - --max-time 8 -o /tmp/comfy_stats.json http://127.0.0.1:8188/system_stats | head -20
python3 -c "import json; d=json.load(open('/tmp/comfy_stats.json')); print('devices', [x.get('name') for x in d.get('devices',[])])"
