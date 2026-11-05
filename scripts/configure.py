#!/usr/bin/env python3
"""Генерация локального .env без внешних зависимостей и вывода секретов."""
import argparse
import os
import re
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description="Создать конфигурацию DentFlow")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--production", action="store_true")
    mode.add_argument("--development", action="store_true")
    parser.add_argument("--domain", help="Домен без https://, например app.example.ru")
    args = parser.parse_args()
    if args.production and (not args.domain or not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", args.domain) or "." not in args.domain):
        parser.error("Для production укажите --domain app.ваш-домен.ru (домен в punycode, без https://)")
    name = ".env.production" if args.production else (".env.development" if args.development else ".env")
    target = ROOT / name
    if target.exists():
        print(f"{name} уже существует. Файл сохранён без изменений.")
        return
    source = ROOT / (".env.production.example" if args.production else (".env.development.example" if args.development else ".env.example"))
    values = {
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "SECRET_KEY": secrets.token_hex(32),
    }
    if args.production:
        values.update(ALLOWED_ORIGINS=f"https://{args.domain}", PUBLIC_URL=f"https://{args.domain}")
    lines = source.read_text(encoding="utf-8").splitlines()
    text = "\n".join(f"{line.split('=', 1)[0]}={values[line.split('=', 1)[0]]}" if "=" in line and line.split("=", 1)[0] in values else line for line in lines) + "\n"
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"Создан {name}. Секреты не выводятся. Не загружайте этот файл в GitHub.")

if __name__ == "__main__":
    main()
