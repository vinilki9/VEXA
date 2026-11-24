#!/usr/bin/env bash
# Installed by root; GitHub builds and transfers images before invoking this script.
set -Eeuo pipefail
umask 077
ROOT=/opt/vexa
BASE=/opt/vexa-deploy
STATE=$BASE/state
TARGET=${1:?Missing commit SHA}
[[ $(id -un) == vexa-deploy && -f $BASE/enabled && $TARGET =~ ^[0-9a-f]{40}$ ]] || { echo 'Deployment disabled or invalid user/target'; exit 1; }
exec 9>"$HOME/.vexa-deploy.lock"
flock -n 9
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/vexa_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o BatchMode=yes"
cd "$ROOT"
[[ $(git branch --show-current) == main && -z $(git status --porcelain --untracked-files=no) && -f .env ]]
git fetch origin main
[[ $(git rev-parse origin/main) == "$TARGET" ]] || { echo 'Target no longer current main'; exit 1; }
git merge --ff-only --no-overwrite-ignore "$TARGET"
[[ $(git rev-parse HEAD) == "$TARGET" ]]
for image in backend dispatcher platform-admin map; do docker image inspect "vexa-$image:$TARGET" >/dev/null; done
# Freeze compose and gateway configuration per commit. All relative paths resolve to infrastructure/.
release=$STATE/$TARGET
mkdir -p "$release"
cp infrastructure/compose.production.yml "$release/compose.yml"
cp infrastructure/Caddyfile.production "$release/Caddyfile"
compose() {
  local tag=$1; shift
  VEXA_IMAGE_TAG="$tag" VEXA_CADDY_FILE="$STATE/$tag/Caddyfile" docker compose --project-directory "$ROOT/infrastructure" --env-file "$ROOT/.env" -f "$STATE/$tag/compose.yml" "$@"
}
compose "$TARGET" config --quiet
# Keep running DB and Redis containers unchanged; pull only if missing.
compose "$TARGET" up -d --no-build --no-recreate --wait --wait-timeout 120 db redis
revision() {
  compose "$TARGET" exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT version_num FROM alembic_version ORDER BY version_num"' 2>/dev/null
}
# Before migration, stop writers to avoid inconsistent schema/old app interactions.
previous=$(cat "$STATE/current" 2>/dev/null || true)
compose "$TARGET" stop gateway dispatcher platform_admin dispatch_worker api vexa_map
before=$(revision || echo NO_VERSION_TABLE)
rollback() {
  rc=$?
  trap - ERR
  set +e
  echo 'Deployment failed; stopping new application services.' >&2
  compose "$TARGET" stop gateway dispatcher platform_admin dispatch_worker api vexa_map
  after=$(revision || echo NO_VERSION_TABLE)
  if [[ $previous =~ ^[0-9a-f]{40}$ && $before != NO_VERSION_TABLE && $before == "$after" && -f $STATE/$previous/compose.yml ]]; then
    echo 'Schema revision unchanged; attempting application rollback (no database restore).'
    compose "$previous" up -d --no-deps --no-build --wait --wait-timeout 180 api vexa_map && \
    compose "$previous" up -d --no-deps --no-build --wait --wait-timeout 180 dispatch_worker dispatcher platform_admin gateway && \
    bash "$BASE/healthcheck.sh" && echo 'Previous application restored.' || echo 'Rollback unsuccessful: manual intervention required.' >&2
  else
    echo 'Schema changed or no previous verified release. Application remains stopped; manual recovery required. Backup retained.' >&2
  fi
  exit "$rc"
}
trap rollback ERR
VEXA_BACKUP_LOCK_HELD=1 bash "$BASE/backup.sh"
compose "$TARGET" run --rm --no-deps migrate
compose "$TARGET" up -d --no-deps --no-build --wait --wait-timeout 180 api vexa_map
compose "$TARGET" up -d --no-deps --no-build --wait --wait-timeout 180 dispatch_worker dispatcher platform_admin
compose "$TARGET" up -d --no-deps --no-build --wait --wait-timeout 180 gateway
bash "$BASE/healthcheck.sh"
# Do not claim data readiness or a working taxi order from HTTP health alone.
printf '%s\n' "$TARGET" > "$STATE/current.tmp"
mv "$STATE/current.tmp" "$STATE/current"
trap - ERR
compose "$TARGET" ps
printf 'Deployment successful: %s\n' "$TARGET"
