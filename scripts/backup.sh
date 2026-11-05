#!/usr/bin/env bash
# Копирует только выбранное окружение. Секреты не печатаются.
set -euo pipefail
cd "$(dirname "$0")/.."
target_env="${1:-devstand}"
case "$target_env" in
  devstand) compose=(docker compose); db=dentflow_devstand ;;
  production) compose=(docker compose --env-file .env.production -f compose.production.yaml); db=dentflow_production ;;
  *) echo 'Использование: bash scripts/backup.sh devstand|production'; exit 2 ;;
esac
umask 077
mkdir -p "backups/$target_env"
dest="backups/$target_env/$(date -u +%Y%m%dT%H%M%SZ).dump"
temp="$dest.partial"
trap 'rm -f "$temp"' EXIT
"${compose[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$temp"
test -s "$temp"
mv "$temp" "$dest"
echo "Резервная копия готова: $dest"
echo 'Перенесите её в защищённое хранилище в РФ. Проверяйте восстановление.'
