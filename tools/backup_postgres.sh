#!/usr/bin/env bash
# Run as vexa-deploy; no automatic deletion of database or volumes.
set -Eeuo pipefail
umask 077
ROOT=/opt/vexa
STATE=/opt/vexa-deploy/state
if [[ ${VEXA_BACKUP_LOCK_HELD:-0} != 1 ]]; then
  exec 9>"$HOME/.vexa-deploy.lock"
  flock -n 9 || { echo 'Deployment/backup busy; skip'; exit 0; }
fi
mkdir -p "$ROOT/backups"
chmod 700 "$ROOT/backups"
C=(docker compose --env-file "$ROOT/.env" -f "$ROOT/infrastructure/compose.production.yml")
file="$ROOT/backups/vexa-$(date -u +%Y%m%dT%H%M%SZ)-$$.dump"
trap 'rm -f "$file.tmp"' EXIT
"${C[@]}" exec -T db sh -c 'exec pg_dump -Fc --no-owner --no-acl -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$file.tmp"
test -s "$file.tmp"
"${C[@]}" exec -T db pg_restore --list < "$file.tmp" >/dev/null
mv "$file.tmp" "$file"
(cd "$(dirname "$file")" && sha256sum "$(basename "$file")" > "$(basename "$file").sha256")
# Keep at least seven latest verified backups, rotate older than 14 days only after new success.
python3 - "$ROOT/backups" <<'PYROTATE'
from pathlib import Path
import time,sys
p=Path(sys.argv[1]); files=sorted(p.glob('vexa-*.dump'),key=lambda f:f.stat().st_mtime,reverse=True)
for f in files[7:]:
    if f.stat().st_mtime < time.time()-14*86400 and f.with_name(f.name+'.sha256').is_file():
        f.unlink(); f.with_name(f.name+'.sha256').unlink()
PYROTATE
printf 'Backup verified (archive list and SHA256): %s\n' "$file"
