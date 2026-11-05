#!/usr/bin/env bash
# Запускается на production-сервере, никогда не читает тестовую БД.
set -euo pipefail
cd "$(dirname "$0")/.."
target_commit="${1:-}"
[[ "$target_commit" =~ ^[0-9a-f]{40}$ ]] || { echo 'Укажите полный SHA коммита'; exit 2; }
test -f .env.production
test -z "$(git status --porcelain)" || { echo 'Рабочее дерево изменено; сохраните изменения до обновления'; exit 2; }
git fetch origin main
git merge-base --is-ancestor "$target_commit" origin/main || { echo 'Commit отсутствует в origin/main'; exit 2; }
previous_commit=$(git rev-parse HEAD)
bash scripts/backup.sh production
git checkout --detach "$target_commit"
compose=(docker compose --env-file .env.production -f compose.production.yaml)
if python3 -c 'from pathlib import Path; import sys; sys.exit(0 if "TELEGRAM_ENABLED=true" in Path(".env.production").read_text().splitlines() else 1)'; then
  compose+=(--profile telegram)
fi
"${compose[@]}" config --quiet
"${compose[@]}" build
# Старый worker останавливается до миграции; медицинские данные не пересоздаются.
"${compose[@]}" stop worker backend telegram 2>/dev/null || true
"${compose[@]}" run --rm migrate
if "${compose[@]}" up -d --wait --wait-timeout 300; then
  echo "Обновление завершено. Предыдущий commit: $previous_commit"
else
  echo "Новая версия не прошла healthcheck. Предыдущий commit: $previous_commit"
  echo 'Автоматический откат БД не выполняется. Откройте процедуру восстановления в docs/DEPLOYMENT.md.'
  exit 1
fi
