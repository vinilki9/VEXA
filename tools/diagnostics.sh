#!/usr/bin/env bash
set -Eeuo pipefail
cd /opt/vexa
free -h
df -h / /var/lib/docker
docker system df
docker compose --env-file .env -f infrastructure/compose.production.yml ps -a
systemctl list-timers vexa-backup.timer --no-pager
bash /opt/vexa-deploy/healthcheck.sh
