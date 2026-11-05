#!/usr/bin/env bash
# Восстанавливает в НОВУЮ БД; работающая БД не очищается.
set -euo pipefail
cd "$(dirname "$0")/.."
target_env="${1:-}"
source_file="${2:-}"
restore_name="${3:-}"
case "$target_env" in
  devstand) compose=(docker compose); prefix=dentflow_devstand_restore_ ;;
  production) compose=(docker compose --env-file .env.production -f compose.production.yaml); prefix=dentflow_production_restore_ ;;
  *) echo 'Использование: bash scripts/restore.sh devstand|production backups/....dump dentflow_ENV_restore_YYYYMMDD'; exit 2 ;;
esac
[[ "$restore_name" =~ ^${prefix}[a-z0-9_]+$ ]] || { echo "Имя новой БД должно начинаться с $prefix"; exit 2; }
test -f "$source_file"
"${compose[@]}" exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh "$restore_name"
"${compose[@]}" exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$1" --no-owner --exit-on-error' sh "$restore_name" < "$source_file"
echo "Копия восстановлена в отдельную БД $restore_name. Рабочая БД не изменена."
echo 'До переключения приложения проверьте контрольные записи и миграции. См. docs/DEPLOYMENT.md.'
