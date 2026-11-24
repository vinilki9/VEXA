#!/usr/bin/env bash
# Restore only into a new isolated database inside the DB container; never overwrite production.
set -Eeuo pipefail
umask 077
file=${1:?Supply absolute path to verified dump}
[[ $file == /* && -f $file && -f $file.sha256 ]]
(cd "$(dirname "$file")" && sha256sum -c "$(basename "$file").sha256")
cd /opt/vexa
exec 9>"$HOME/.vexa-deploy.lock"; flock -n 9
C=(docker compose --env-file .env -f infrastructure/compose.production.yml)
name=vexa_restore_test_$(date -u +%Y%m%d%H%M%S)_$$
"${C[@]}" exec -T db sh -c 'exec createdb -U "$POSTGRES_USER" "$1"' sh "$name"
"${C[@]}" exec -T db sh -c 'exec pg_restore --exit-on-error --no-owner --no-acl -U "$POSTGRES_USER" -d "$1"' sh "$name" < "$file"
"${C[@]}" exec -T db sh -c 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -c "SELECT version_num FROM alembic_version"' sh "$name"
echo "Restored into isolated DB $name; production untouched. Remove test database manually after verification."
