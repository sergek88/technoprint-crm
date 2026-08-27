"""Управление пользователями: владелец заводит свои логины и пароли, никаких зашитых учёток."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User as UserModel
from app.auth import get_current_user, require_admin, hash_password, verify_password, User
from app.audit_log import log as audit

router = APIRouter(prefix="/api/users", tags=["users"])

MIN_PASSWORD = 8


class UserIn(BaseModel):
    username: str
    password: str
    full_name: str
    role: str = "worker"          # admin | worker


class UserPatch(BaseModel):
    full_name: str | None = None
    role: str | None = None
    password: str | None = None   # смена пароля админом


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


def _out(u: UserModel) -> dict:
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role,
            "created_at": u.created_at.isoformat() if u.created_at else None}


def _check_password(password: str) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise HTTPException(400, f"Пароль слишком короткий — минимум {MIN_PASSWORD} символов")


@router.get("")
async def list_users(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    rows = (await db.execute(select(UserModel).order_by(UserModel.id))).scalars().all()
    return [_out(u) for u in rows]


@router.post("", status_code=201)
async def create_user(body: UserIn, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    username = body.username.strip().lower()
    if not username:
        raise HTTPException(400, "Логин не может быть пустым")
    if body.role not in ("admin", "worker"):
        raise HTTPException(400, "Роль должна быть admin или worker")
    _check_password(body.password)
    exists = (await db.execute(select(UserModel).where(func.lower(UserModel.username) == username))).scalars().first()
    if exists:
        raise HTTPException(400, "Такой логин уже занят")
    u = UserModel(username=username, password_hash=hash_password(body.password),
                  full_name=body.full_name.strip() or username, role=body.role)
    db.add(u)
    audit(db, admin, "user_create", f"Пользователь {username} ({body.role})")
    await db.commit()
    return _out(u)


@router.patch("/{user_id}")
async def update_user(user_id: int, body: UserPatch, db: AsyncSession = Depends(get_db),
                      admin: User = Depends(require_admin)):
    u = await db.get(UserModel, user_id)
    if not u:
        raise HTTPException(404, "Пользователь не найден")
    if body.full_name is not None:
        u.full_name = body.full_name.strip() or u.username
    if body.role is not None:
        if body.role not in ("admin", "worker"):
            raise HTTPException(400, "Роль должна быть admin или worker")
        if u.role == "admin" and body.role != "admin":
            admins = (await db.execute(select(func.count(UserModel.id)).where(UserModel.role == "admin"))).scalar()
            if admins <= 1:
                raise HTTPException(400, "Нельзя снять права с последнего администратора")
        u.role = body.role
    if body.password is not None:
        _check_password(body.password)
        u.password_hash = hash_password(body.password)
    audit(db, admin, "user_update", f"Пользователь {u.username}")
    await db.commit()
    return _out(u)


@router.delete("/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    u = await db.get(UserModel, user_id)
    if not u:
        raise HTTPException(404, "Пользователь не найден")
    if u.id == admin.id:
        raise HTTPException(400, "Нельзя удалить самого себя")
    if u.role == "admin":
        admins = (await db.execute(select(func.count(UserModel.id)).where(UserModel.role == "admin"))).scalar()
        if admins <= 1:
            raise HTTPException(400, "Нельзя удалить последнего администратора")
    audit(db, admin, "user_delete", f"Пользователь {u.username}")
    await db.delete(u)
    await db.commit()
    return {"ok": True}


@router.put("/me/password")
async def change_own_password(body: PasswordChange, db: AsyncSession = Depends(get_db),
                              user: User = Depends(get_current_user)):
    """Смена собственного пароля — доступна и работнику."""
    u = await db.get(UserModel, user.id)
    if not u or not verify_password(body.old_password, u.password_hash):
        raise HTTPException(400, "Текущий пароль неверный")
    _check_password(body.new_password)
    u.password_hash = hash_password(body.new_password)
    audit(db, user, "password_change", f"Пользователь {u.username}")
    await db.commit()
    return {"ok": True}
