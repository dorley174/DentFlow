#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v docker >/dev/null 2>&1; then
  echo 'Установите и запустите Docker Desktop: https://docs.docker.com/get-started/get-docker/'
  exit 1
fi
docker compose version >/dev/null
if [ ! -f .env ]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 scripts/configure.py
  else
    docker run --rm -v "$PWD:/project" -w /project python:3.12-alpine python scripts/configure.py
  fi
fi
docker compose up -d --build --wait --wait-timeout 300
echo 'DentFlow запущен: http://localhost:8080'
echo 'Вход администратора: admin@dentflow.local / Admin-Demo-2026!'
echo 'Тестовые данные вымышлены. Инструкция: START_HERE.html'
