#!/usr/bin/env bash
# One-time root setup. Does not run containers or enable deployment.
set -Eeuo pipefail
umask 077
[[ $(id -u) == 0 ]] || { echo 'Run as root'; exit 1; }
cd /opt/vexa
id vexa-deploy >/dev/null
[[ -f tools/deploy_vps.sh && -f infrastructure/compose.production.yml ]]
install -d -o root -g root -m 755 /opt/vexa-deploy
rm -f /opt/vexa-deploy/enabled
# Keep a copy of any earlier script, never overwrite production .env.
if [[ -f /opt/vexa-deploy/deploy.sh ]]; then
  cp -p /opt/vexa-deploy/deploy.sh "/opt/vexa-deploy/deploy.sh.bak.$(date -u +%Y%m%dT%H%M%SZ)"
fi
install -o root -g root -m 755 tools/deploy_vps.sh /opt/vexa-deploy/deploy.sh
install -o root -g root -m 755 tools/backup_postgres.sh /opt/vexa-deploy/backup.sh
install -o root -g root -m 755 tools/healthcheck.sh /opt/vexa-deploy/healthcheck.sh
install -d -o vexa-deploy -g vexa-deploy -m 700 /opt/vexa-deploy/state
if [[ ! -e .env ]]; then
  PW=$(python3 -c 'import secrets; print(secrets.token_urlsafe(36))')
  SK=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
  sed -e "s/REPLACE_WITH_RANDOM_PASSWORD/$PW/g" -e "s/REPLACE_WITH_DIFFERENT_RANDOM_SECRET_AT_LEAST_32_CHARACTERS/$SK/g" .env.example > .env
  chown vexa-deploy:vexa-deploy .env
  chmod 600 .env
else
  echo 'Existing .env preserved; check it matches production template before enabling.'
fi
[[ -f .env && ! -L .env ]] || exit 1
if sudo -u vexa-deploy -H git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo 'Refusing tracked .env; remove from Git and rotate exposed secrets.' >&2; exit 1
fi
chown vexa-deploy:vexa-deploy .env
chmod 600 .env
python3 - <<'PYENV'
import sys
from pathlib import Path
sys.path.insert(0, 'tools')
from release_preflight import parse_env, inspect_env
values = parse_env(Path('.env').read_text(encoding='utf-8'))
errors = inspect_env(values)
if values.get('VEXA_DOMAIN') != '45.143.139.162':
    errors.append('VEXA_DOMAIN must be 45.143.139.162')
if values.get('ENVIRONMENT') != 'production':
    errors.append('ENVIRONMENT must be production')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
PYENV
bash -n /opt/vexa-deploy/deploy.sh
sudo -u vexa-deploy -H docker compose --env-file /opt/vexa/.env -f /opt/vexa/infrastructure/compose.production.yml config --quiet
install -m 644 infrastructure/vexa-backup.service /etc/systemd/system/vexa-backup.service
install -m 644 infrastructure/vexa-backup.timer /etc/systemd/system/vexa-backup.timer
install -m 644 infrastructure/vexa-health.service /etc/systemd/system/vexa-health.service
install -m 644 infrastructure/vexa-health.timer /etc/systemd/system/vexa-health.timer
systemctl daemon-reload
systemctl enable --now vexa-backup.timer vexa-health.timer
printf 'Setup complete. Deployment must be enabled explicitly after verification.\n'
