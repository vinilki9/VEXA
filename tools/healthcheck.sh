#!/usr/bin/env bash
set -Eeuo pipefail
base=${VEXA_PUBLIC_URL:-https://45.143.139.162}
api=$(curl -fsS --max-time 15 --retry 5 --retry-delay 5 --retry-all-errors "$base/health")
python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["status"]=="ok" and d["database"]=="connected"' <<< "$api"
map=$(curl -fsS --max-time 15 "$base/maps/health")
python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["service"]=="VEXA MAP"; print("MAP readiness:", {k:d.get(k) for k in ("map_ready","search_ready","routing_configured")})' <<< "$map"
for panel in dispatch admin; do
  html=$(curl -fsS --max-time 15 "$base/$panel/")
  # Check actual built asset (not just HTTP 200 from SPA fallback).
  asset=$(python3 -c 'import re,sys; h=sys.stdin.read(); m=re.search(r"src=[\x27\x22]([^\x27\x22]+\.js)[\x27\x22]",h); assert m,"Missing web JS bundle"; print(m.group(1))' <<< "$html")
  url=$(python3 -c 'from urllib.parse import urljoin; import sys; print(urljoin(sys.argv[1],sys.argv[2]))' "$base/$panel/" "$asset")
  kind=$(curl -fsS --max-time 15 -o /dev/null -w '%{content_type}' "$url")
  [[ $kind == *javascript* ]] || { echo "Invalid JS asset type for $panel: $kind"; exit 1; }
done
worker=$(docker compose --env-file /opt/vexa/.env -f /opt/vexa/infrastructure/compose.production.yml ps -q dispatch_worker)
[[ -n $worker && $(docker inspect --format '{{.State.Health.Status}}' "$worker") == healthy ]]
printf 'Public API and both web panels respond over verified TLS. Map data readiness is separate.\n'
