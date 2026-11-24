#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="/opt/vexa"
DEPLOY_DIR="/opt/vexa-deploy"
ENV_FILE="$PROJECT_DIR/.env"

TARGET="${1:?Missing commit SHA}"

export GIT_SSH_COMMAND="ssh -i /home/vexa-deploy/.ssh/vexa_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"

echo "=== VEXA AUTO DEPLOY ==="

if [[ ! -f "$DEPLOY_DIR/enabled" ]]; then
    echo "Deployment is not enabled yet."
    exit 1
fi

if [[ ! "$TARGET" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Invalid commit SHA."
    exit 1
fi

exec 9>"$HOME/.vexa-deploy.lock"
flock -n 9

cd "$PROJECT_DIR"

test -f "$ENV_FILE"

if [[ "$(git branch --show-current)" != "main" ]]; then
    echo "Expected main branch."
    exit 1
fi

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "Local changes detected."
    exit 1
fi

echo "Downloading VEXA updates..."

git fetch origin main

if [[ "$(git rev-parse origin/main)" != "$TARGET" ]]; then
    echo "Deployment target is not current main."
    exit 1
fi

git merge --ff-only --no-overwrite-ignore "$TARGET"

test "$(git rev-parse HEAD)" = "$TARGET"

COMPOSE=(
    docker compose
    --env-file "$ENV_FILE"
    -f "$PROJECT_DIR/infrastructure/docker-compose.yml"
)

echo "Checking Docker configuration..."

"${COMPOSE[@]}" config --quiet

echo "Building VEXA containers..."

"${COMPOSE[@]}" build

echo "Starting VEXA services..."

"${COMPOSE[@]}" up -d --no-build --wait --wait-timeout 180

echo "Checking container status..."

"${COMPOSE[@]}" ps

echo "================================"
echo "VEXA DEPLOYMENT SUCCESSFUL"
echo "================================"
