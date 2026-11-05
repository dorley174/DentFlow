"""Explicit production bootstrap. Never creates demo patients or passwords."""
import argparse
import getpass
import re
import sys
from sqlalchemy import select
from .db import SessionLocal
from .models import User
from .security import hash_password
from .seed import seed_plans

def main():
    parser = argparse.ArgumentParser(description='Создать владельца платформы DentFlow')
    parser.add_argument('--email', required=True)
    parser.add_argument('--name', default='Владелец DentFlow')
    args = parser.parse_args()
    email = args.email.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
        parser.error('Укажите корректный email')
    password = getpass.getpass('Новый уникальный пароль (минимум 14 символов): ')
    confirmation = getpass.getpass('Повторите пароль: ')
    if password != confirmation:
        raise SystemExit('Пароли не совпадают. Ничего не изменено.')
    if len(password) < 14 or 'demo' in password.lower() or len(password) > 128:
        raise SystemExit('Нужен уникальный пароль от 14 до 128 символов без demo.')
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            raise SystemExit('Этот аккаунт уже существует. Пароль не изменён.')
        seed_plans(db)
        db.add(User(email=email, name=args.name[:160], role='super_admin', password_hash=hash_password(password)))
        db.commit()
    print('Владелец платформы создан. Войдите на /login. Демо-пациенты не добавлены.')

if __name__ == '__main__':
    main()
