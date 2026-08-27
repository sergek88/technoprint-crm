"""Создать первого администратора. Запускается один раз при развёртывании.

    docker compose exec tp-backend python create_admin.py <логин> <пароль> ["Имя Фамилия"]

Дальше пользователей заводит сам владелец в интерфейсе (Реквизиты → Пользователи).
Никаких учёток по умолчанию в системе нет — и это намеренно.
"""
import asyncio
import sys

from sqlalchemy import select, func

from app.database import async_session
from app.models import User
from app.auth import hash_password

MIN_PASSWORD = 8


async def main(username: str, password: str, full_name: str) -> int:
    username = username.strip().lower()
    if len(password) < MIN_PASSWORD:
        print(f"Пароль слишком короткий — минимум {MIN_PASSWORD} символов")
        return 1
    async with async_session() as db:
        exists = (await db.execute(
            select(User).where(func.lower(User.username) == username))).scalars().first()
        if exists:
            print(f"Пользователь «{username}» уже есть — ничего не меняю")
            return 1
        db.add(User(username=username, password_hash=hash_password(password),
                    full_name=full_name or username, role="admin"))
        await db.commit()
        print(f"Администратор «{username}» создан")
        return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2],
                              sys.argv[3] if len(sys.argv) > 3 else "")))
