#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose config --quiet
docker compose exec -T backend python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/api/health").read().decode())'
docker compose ps
echo 'Откройте http://localhost:8080 и пройдите сценарий из docs/DEV_STAND.md.'
