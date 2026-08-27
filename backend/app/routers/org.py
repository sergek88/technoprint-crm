from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user, require_admin, User
from app.audit_log import log as audit
from app.models import Organization, AppSetting

router = APIRouter(prefix="/api/org", tags=["org"])

_FIELDS = ("id", "name", "address", "phones", "email", "inn", "kpp", "ogrnip",
           "bank_name", "bank_bik", "bank_account", "bank_corr", "director")

# Заготовка для первого запуска: строка создаётся один раз, если таблица пуста.
# Свои реквизиты вносятся в интерфейсе (раздел «Реквизиты») и живут в базе, а не в коде.
DEFAULTS = dict(
    name='ООО "Ромашка"',
    address="Индекс, регион, город, улица, дом",
    phones="8(000)000-00-00",
    inn="0000000000", kpp="000000000", ogrnip="0000000000000",
    bank_name="Название банка", bank_bik="000000000",
    bank_account="00000000000000000000", bank_corr="00000000000000000000",
)


async def _get(db: AsyncSession) -> Organization:
    o = await db.get(Organization, 1)
    if not o:
        o = Organization(id=1, **DEFAULTS)
        db.add(o)
        await db.commit()
        o = await db.get(Organization, 1)
    return o


def _dict(o: Organization):
    return {k: getattr(o, k) for k in _FIELDS}


@router.get("")
async def get_org(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    return _dict(await _get(db))


class OrgIn(BaseModel):
    name: str | None = None
    address: str | None = None
    phones: str | None = None
    email: str | None = None
    inn: str | None = None
    kpp: str | None = None
    ogrnip: str | None = None
    bank_name: str | None = None
    bank_bik: str | None = None
    bank_account: str | None = None
    bank_corr: str | None = None
    director: str | None = None


@router.put("")
async def put_org(body: OrgIn, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    o = await _get(db)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(o, k, v)
    audit(db, user, "edit_org", "Изменены реквизиты организации")
    await db.commit()
    return _dict(o)


# ───────── название системы: показывается в шапке и на экране входа ─────────
# Без авторизации: экран входа рисуется до логина. Ничего чувствительного не отдаём.
app_info = APIRouter(tags=["app"])


class AppTitleIn(BaseModel):
    title: str


@app_info.get("/api/app-info")
async def get_app_info(db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(AppSetting).where(AppSetting.key == "app_title"))).scalars().first()
    return {"title": (row.value if row and row.value else "CRM учёта")}


@app_info.put("/api/app-info")
async def set_app_info(body: AppTitleIn, db: AsyncSession = Depends(get_db),
                       _admin: User = Depends(require_admin)):
    title = body.title.strip()[:60] or "CRM учёта"
    row = (await db.execute(select(AppSetting).where(AppSetting.key == "app_title"))).scalars().first()
    if row:
        row.value = title
    else:
        db.add(AppSetting(key="app_title", value=title))
    await db.commit()
    return {"title": title}
