from datetime import date as _date, datetime, timedelta
from decimal import Decimal
from typing import Literal

Period = Literal["day", "week", "month", "year", "all"]

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user, require_admin, User
from app.models import (Cartridge, CartridgeRefill, CartridgeModel, CartridgeWorker,
                        CartridgeDefect, CartridgeSpecType, CartridgePrice, AppSetting, Client)

router = APIRouter(prefix="/api/cartridges", tags=["cartridges"])

_eff_date = func.coalesce(CartridgeRefill.last_date, CartridgeRefill.work_date, CartridgeRefill.first_date)


# ───────────── reference data ─────────────
@router.get("/refs")
async def cartridge_refs(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    workers = (await db.execute(select(CartridgeWorker).order_by(CartridgeWorker.name))).scalars().all()
    defects = (await db.execute(select(CartridgeDefect).order_by(CartridgeDefect.name))).scalars().all()
    models = (await db.execute(select(CartridgeModel.id, CartridgeModel.name).order_by(CartridgeModel.name))).all()
    spec_types = (await db.execute(
        select(CartridgeSpecType).where(CartridgeSpecType.is_refill == True, CartridgeSpecType.is_active == True)
        .order_by(CartridgeSpecType.sort, CartridgeSpecType.name))).scalars().all()
    # мастер по умолчанию: настройка cart_default_worker, иначе единственный/первый мастер
    dw = (await db.execute(select(AppSetting.value).where(AppSetting.key == "cart_default_worker"))).scalars().first()
    default_worker_id = None
    try:
        default_worker_id = int(dw) if dw else None
    except (TypeError, ValueError):
        default_worker_id = None
    if default_worker_id is None and len(workers) == 1:
        default_worker_id = workers[0].id
    return {
        "workers": [{"id": w.id, "name": w.name} for w in workers],
        "defects": [{"id": d.id, "name": d.name} for d in defects],
        "models": [{"id": m.id, "name": m.name} for m in models],
        "spec_types": [{"id": s.id, "name": s.name} for s in spec_types],
        "default_worker_id": default_worker_id,
    }


@router.get("/next-barcode")
async def next_barcode(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    return {"barcode": await _next_barcode(db)}


async def _max_tpr(db: AsyncSession) -> int:
    rows = (await db.execute(select(Cartridge.barcode).where(Cartridge.barcode.ilike("TPR%")))).scalars().all()
    mx = 0
    for b in rows:
        try:
            mx = max(mx, int(str(b)[3:]))
        except (ValueError, TypeError):
            pass
    return mx


async def _get_setting_int(db: AsyncSession, key: str, default: int = 0) -> int:
    v = (await db.execute(select(AppSetting.value).where(AppSetting.key == key))).scalars().first()
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


async def _set_setting(db: AsyncSession, key: str, value) -> None:
    row = (await db.execute(select(AppSetting).where(AppSetting.key == key))).scalars().first()
    if row:
        row.value = str(value)
    else:
        db.add(AppSetting(key=key, value=str(value)))


async def _next_num(db: AsyncSession) -> int:
    """Следующий свободный номер штрих-кода: больше и существующих карточек, и напечатанных наклеек."""
    return max(await _max_tpr(db), await _get_setting_int(db, "label_last")) + 1


def _fmt_barcode(n: int) -> str:
    return f"TPR{n:06d}"


async def _next_barcode(db: AsyncSession) -> str:
    return _fmt_barcode(await _next_num(db))


# ───────────── печать листа штрих-кодов (наклейки на картриджи) ─────────────
@router.get("/labels/preview")
async def labels_preview(count: int = Query(default=24), start: int | None = Query(default=None),
                         db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    count = max(1, min(count, 200))
    base = (start - 1) if (start and start > 0) else (await _next_num(db) - 1)
    codes = [_fmt_barcode(base + i) for i in range(1, count + 1)]
    return {"start": base + 1, "count": count, "codes": codes}


@router.post("/labels/commit")
async def labels_commit(last: int = Query(...), db: AsyncSession = Depends(get_db),
                        _user: User = Depends(get_current_user)):
    """Сдвинуть счётчик после печати, чтобы следующая печать продолжила нумерацию."""
    cur = await _get_setting_int(db, "label_last")
    if last > cur:
        await _set_setting(db, "label_last", last)
        await db.commit()
    return {"ok": True, "label_last": max(cur, last)}


# ═══════════════ ПРАЙС-ЛИСТ (стандартные цены: модель × тип операции) ═══════════════
async def _history_price(db: AsyncSession, model_id: int | None, spec_type_id: int):
    """Последняя реальная цена этой модели по этому типу операции (подсказка)."""
    if not model_id:
        return None
    stmt = (select(CartridgeRefill.price)
            .join(Cartridge, Cartridge.id == CartridgeRefill.cartridge_id)
            .where(Cartridge.model_id == model_id, CartridgeRefill.spec_type_id == spec_type_id,
                   CartridgeRefill.price.isnot(None))
            .order_by(_eff_date.desc(), CartridgeRefill.id.desc()).limit(1))
    return (await db.execute(stmt)).scalars().first()


async def _override_price(db: AsyncSession, model_id: int, spec_type_id: int):
    return (await db.execute(select(CartridgePrice.price).where(
        CartridgePrice.model_id == model_id,
        CartridgePrice.spec_type_id == spec_type_id))).scalars().first()


async def _effective_price(db: AsyncSession, model_id: int | None, spec_type_id: int):
    """(price, source): override → history → база(заправка) override/history → (None, None)."""
    if not model_id:
        return None, None
    ov = await _override_price(db, model_id, spec_type_id)
    if ov is not None:
        return float(ov), "manual"
    h = await _history_price(db, model_id, spec_type_id)
    if h is not None:
        return float(h), "auto"
    if spec_type_id != 1:  # нет цены для восстановления → берём базовую заправку как ориентир
        ov1 = await _override_price(db, model_id, 1)
        if ov1 is not None:
            return float(ov1), "base"
        h1 = await _history_price(db, model_id, 1)
        if h1 is not None:
            return float(h1), "base"
    return None, None


@router.get("/suggest-price")
async def suggest_price(model_id: int = Query(...), spec_type_id: int = Query(1),
                        db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    price, source = await _effective_price(db, model_id, spec_type_id)
    return {"price": price, "source": source}


@router.get("/pricelist")
async def pricelist(q: str = Query(default=""), limit: int = Query(default=60, le=200),
                    offset: int = Query(default=0),
                    db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Список моделей с базовой ценой заправки (ручная или из истории). Популярные сверху."""
    q = (q or "").strip()
    base = (select(CartridgeModel.id, CartridgeModel.name,
                   func.count(CartridgeRefill.id).label("cnt"))
            .select_from(CartridgeModel)
            .join(Cartridge, Cartridge.model_id == CartridgeModel.id)
            .join(CartridgeRefill, CartridgeRefill.cartridge_id == Cartridge.id, isouter=True)
            .group_by(CartridgeModel.id, CartridgeModel.name))
    if q:
        base = base.where(CartridgeModel.name.ilike(f"%{q}%"))
    base = base.order_by(desc("cnt"), CartridgeModel.name).limit(limit).offset(offset)
    rows = (await db.execute(base)).all()
    model_ids = [r.id for r in rows]

    overrides, hist = {}, {}
    if model_ids:
        overrides = {m: p for m, p in (await db.execute(
            select(CartridgePrice.model_id, CartridgePrice.price)
            .where(CartridgePrice.spec_type_id == 1, CartridgePrice.model_id.in_(model_ids)))).all()}
        hist = {m: p for m, p in (await db.execute(
            select(Cartridge.model_id, CartridgeRefill.price)
            .distinct(Cartridge.model_id)
            .select_from(CartridgeRefill).join(Cartridge, Cartridge.id == CartridgeRefill.cartridge_id)
            .where(CartridgeRefill.spec_type_id == 1, CartridgeRefill.price.isnot(None),
                   Cartridge.model_id.in_(model_ids))
            .order_by(Cartridge.model_id, _eff_date.desc(), CartridgeRefill.id.desc()))).all()}

    out = []
    for r in rows:
        ovp = overrides.get(r.id)
        if ovp is not None:
            price, source = float(ovp), "manual"
        elif hist.get(r.id) is not None:
            price, source = float(hist[r.id]), "auto"
        else:
            price, source = None, None
        out.append({"model_id": r.id, "model": r.name, "count": int(r.cnt or 0),
                    "base_price": price, "source": source})
    return out


@router.get("/pricelist/{model_id:int}")
async def pricelist_model(model_id: int, db: AsyncSession = Depends(get_db),
                          _user: User = Depends(get_current_user)):
    """Все типы операций для одной модели: ручная цена + подсказка из истории."""
    model = await db.get(CartridgeModel, model_id)
    if not model:
        raise HTTPException(404, "Модель не найдена")
    specs = (await db.execute(select(CartridgeSpecType)
             .where(CartridgeSpecType.is_refill == True, CartridgeSpecType.is_active == True)
             .order_by(CartridgeSpecType.sort, CartridgeSpecType.name))).scalars().all()
    overrides = {m: p for m, p in (await db.execute(
        select(CartridgePrice.spec_type_id, CartridgePrice.price)
        .where(CartridgePrice.model_id == model_id))).all()}
    rows = []
    for s in specs:
        ovp = overrides.get(s.id)
        sug = await _history_price(db, model_id, s.id)
        rows.append({"spec_type_id": s.id, "name": s.name,
                     "price": float(ovp) if ovp is not None else None,
                     "suggested": float(sug) if sug is not None else None})
    return {"model_id": model_id, "model": model.name, "rows": rows}


class PriceSetIn(BaseModel):
    model_id: int
    spec_type_id: int
    price: float | None = None  # None → очистить переопределение


@router.put("/pricelist")
async def set_price(body: PriceSetIn, db: AsyncSession = Depends(get_db),
                    _admin: User = Depends(require_admin)):
    existing = (await db.execute(select(CartridgePrice).where(
        CartridgePrice.model_id == body.model_id,
        CartridgePrice.spec_type_id == body.spec_type_id))).scalars().first()
    if body.price is None:
        if existing:
            await db.delete(existing)
            await db.commit()
        return {"ok": True, "cleared": True}
    if existing:
        existing.price = Decimal(str(body.price))
        existing.updated_at = datetime.now()
    else:
        db.add(CartridgePrice(model_id=body.model_id, spec_type_id=body.spec_type_id,
                              price=Decimal(str(body.price)), updated_at=datetime.now()))
    await db.commit()
    return {"ok": True}


# ───────────── client list (cartridges grouped by client) ─────────────
@router.get("/clients")
async def cartridge_clients(
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = (q or "").strip()
    # clients that own at least one cartridge
    if q:
        # поиск среди ВСЕХ клиентов (по имени или штрих-коду картриджа) — чтобы завести заправку любому.
        # Штрих-код ищем гибко: "52.15"/"5215" → совпадает с TPR005215 (по цифрам, игнорируя разделители).
        digits = "".join(c for c in q if c.isdigit())
        bc_cond = Cartridge.barcode.ilike(f"%{q}%")
        if digits:
            norm = func.regexp_replace(Cartridge.barcode, r"\D", "", "g")
            bc_cond = or_(bc_cond, norm.like(f"%{digits}%"))
        sub = select(Cartridge.client_id).where(bc_cond)
        stmt = (select(Client.id, Client.name, func.count(func.distinct(Cartridge.id)).label("carts"))
                .select_from(Client).join(Cartridge, Cartridge.client_id == Client.id, isouter=True)
                .where(or_(Client.name.ilike(f"%{q}%"), Client.id.in_(sub)))
                .group_by(Client.id, Client.name).order_by(Client.name).limit(80))
    else:
        stmt = (select(Client.id, Client.name, func.count(func.distinct(Cartridge.id)).label("carts"))
                .select_from(Client).join(Cartridge, Cartridge.client_id == Client.id)
                .group_by(Client.id, Client.name).order_by(Client.name).limit(80))
    rows = (await db.execute(stmt)).all()

    # unbilled refill counts per client
    unbilled = dict((await db.execute(
        select(Cartridge.client_id, func.count(CartridgeRefill.id))
        .select_from(Cartridge).join(CartridgeRefill, CartridgeRefill.cartridge_id == Cartridge.id)
        .where(CartridgeRefill.is_billed == False)
        .group_by(Cartridge.client_id)
    )).all())

    return [{"client_id": r.id, "client": r.name, "cartridges": r.carts,
             "unbilled": int(unbilled.get(r.id, 0))} for r in rows]


# ───────────── поиск картриджа по штрих-коду (гибко: "52.15"/"5215" → TPR005215) ─────────────
@router.get("/by-barcode")
async def cartridge_by_barcode(code: str = Query(...), db: AsyncSession = Depends(get_db),
                               _user: User = Depends(get_current_user)):
    digits = "".join(c for c in code if c.isdigit())
    if not digits:
        return {"matches": []}
    norm = func.regexp_replace(Cartridge.barcode, r"\D", "", "g")
    base = (select(Cartridge.id, Cartridge.barcode, Cartridge.client_id, Cartridge.model_id,
                   CartridgeModel.name.label("model"), Client.name.label("client"))
            .select_from(Cartridge)
            .join(CartridgeModel, CartridgeModel.id == Cartridge.model_id, isouter=True)
            .join(Client, Client.id == Cartridge.client_id, isouter=True))
    target = digits.lstrip("0") or "0"
    # 1) точное совпадение по числу (TPR005215 == "5215")
    rows = (await db.execute(base.where(func.ltrim(norm, "0") == target).limit(10))).all()
    if not rows:
        # 2) частичное по подстроке цифр — для неполного ввода
        rows = (await db.execute(base.where(norm.like(f"%{digits}%")).order_by(Cartridge.barcode).limit(10))).all()
    return {"matches": [{"cartridge_id": r.id, "barcode": r.barcode, "client_id": r.client_id,
                         "model_id": r.model_id, "model": r.model, "client": r.client} for r in rows]}


# ───────────── ЖУРНАЛ всех заправок (плоский список по дате) ─────────────
def _period_range(period: str):
    """Полуинтервал [start, end) для фильтра журнала: start <= дата < end.
    (None, None) = без ограничения (Всё время). Период закрыт сверху, чтобы записи
    с будущей датой не протекали в «Сегодня»/«Неделя»/«Месяц»/«Год»."""
    t = _date.today()
    if period == "day":
        return t, t + timedelta(days=1)
    if period == "week":
        s = t - timedelta(days=t.weekday())          # понедельник текущей недели
        return s, s + timedelta(days=7)
    if period == "month":
        s = t.replace(day=1)
        e = s.replace(year=s.year + 1, month=1) if s.month == 12 else s.replace(month=s.month + 1)
        return s, e
    if period == "year":
        s = t.replace(month=1, day=1)
        return s, s.replace(year=s.year + 1)
    return None, None


@router.get("/journal")
async def cartridge_journal(
    q: str = Query(default=""), billed: str = Query(default="all"),
    period: Period = Query(default="all"),
    limit: int = Query(default=100, le=300), offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user),
):
    q = (q or "").strip()
    eff = func.coalesce(CartridgeRefill.last_date, CartridgeRefill.work_date, CartridgeRefill.first_date)
    base = (select(CartridgeRefill.id, eff.label("d"), Cartridge.barcode, Cartridge.client_id,
                   CartridgeRefill.cartridge_id,
                   Client.name.label("client"), CartridgeModel.name.label("model"),
                   CartridgeSpecType.name.label("spec_type"), CartridgeWorker.name.label("worker"),
                   CartridgeRefill.price, CartridgeRefill.is_billed)
            .select_from(CartridgeRefill)
            .join(Cartridge, Cartridge.id == CartridgeRefill.cartridge_id)
            .join(Client, Client.id == Cartridge.client_id, isouter=True)
            .join(CartridgeModel, CartridgeModel.id == Cartridge.model_id, isouter=True)
            .join(CartridgeSpecType, CartridgeSpecType.id == CartridgeRefill.spec_type_id, isouter=True)
            .join(CartridgeWorker, CartridgeWorker.id == CartridgeRefill.worker_id, isouter=True))
    if q:
        base = base.where(or_(Client.name.ilike(f"%{q}%"), Cartridge.barcode.ilike(f"%{q}%"),
                              CartridgeModel.name.ilike(f"%{q}%")))
    if billed == "billed":
        base = base.where(CartridgeRefill.is_billed == True)
    elif billed == "unbilled":
        base = base.where(CartridgeRefill.is_billed == False)
    start, end = _period_range(period)
    if start is not None:
        base = base.where(eff >= start, eff < end)
    rows = (await db.execute(base.order_by(eff.desc(), CartridgeRefill.id.desc()).limit(limit).offset(offset))).all()
    return [{"id": r.id, "date": r.d.isoformat() if r.d else None, "barcode": r.barcode,
             "client": r.client, "client_id": r.client_id, "cartridge_id": r.cartridge_id,
             "model": r.model, "spec_type": r.spec_type,
             "worker": r.worker, "price": float(r.price) if r.price is not None else None,
             "is_billed": r.is_billed} for r in rows]


@router.get("/journal/summary")
async def cartridge_journal_summary(
    q: str = Query(default=""), billed: str = Query(default="all"),
    period: Period = Query(default="all"),
    db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user),
):
    """Итоги журнала за период: сколько заправок и на какую сумму (по всем строкам, не только на странице)."""
    q = (q or "").strip()
    eff = func.coalesce(CartridgeRefill.last_date, CartridgeRefill.work_date, CartridgeRefill.first_date)
    stmt = (select(func.count(CartridgeRefill.id),
                   func.coalesce(func.sum(CartridgeRefill.price), 0))
            .select_from(CartridgeRefill)
            .join(Cartridge, Cartridge.id == CartridgeRefill.cartridge_id)
            .join(Client, Client.id == Cartridge.client_id, isouter=True)
            .join(CartridgeModel, CartridgeModel.id == Cartridge.model_id, isouter=True))
    if q:
        stmt = stmt.where(or_(Client.name.ilike(f"%{q}%"), Cartridge.barcode.ilike(f"%{q}%"),
                              CartridgeModel.name.ilike(f"%{q}%")))
    if billed == "billed":
        stmt = stmt.where(CartridgeRefill.is_billed == True)
    elif billed == "unbilled":
        stmt = stmt.where(CartridgeRefill.is_billed == False)
    start, end = _period_range(period)
    if start is not None:
        stmt = stmt.where(eff >= start, eff < end)
    cnt, total = (await db.execute(stmt)).one()
    return {"count": int(cnt or 0), "sum": float(total or 0)}


# ───────────── one client card: FLAT list of refills (заправки) ─────────────
@router.get("/client/{client_id:int}")
async def client_card(client_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Клиент не найден")

    rstmt = (
        select(CartridgeRefill.id, CartridgeRefill.cartridge_id, Cartridge.barcode,
               CartridgeModel.name.label("model"), CartridgeRefill.last_date, CartridgeRefill.work_date,
               CartridgeRefill.first_date,
               CartridgeRefill.advice, CartridgeRefill.remark, CartridgeRefill.price, CartridgeRefill.is_billed,
               CartridgeRefill.worker_id, CartridgeRefill.defect_id, CartridgeRefill.spec_type_id,
               CartridgeSpecType.name.label("spec_type"),
               CartridgeWorker.name.label("worker"), CartridgeDefect.name.label("defect"))
        .select_from(CartridgeRefill)
        .join(Cartridge, Cartridge.id == CartridgeRefill.cartridge_id)
        .join(CartridgeModel, CartridgeModel.id == Cartridge.model_id, isouter=True)
        .join(CartridgeSpecType, CartridgeSpecType.id == CartridgeRefill.spec_type_id, isouter=True)
        .join(CartridgeWorker, CartridgeWorker.id == CartridgeRefill.worker_id, isouter=True)
        .join(CartridgeDefect, CartridgeDefect.id == CartridgeRefill.defect_id, isouter=True)
        .where(Cartridge.client_id == client_id)
        .order_by(desc(func.coalesce(CartridgeRefill.last_date, CartridgeRefill.work_date, CartridgeRefill.first_date)))
    )
    refills = [{
        "id": r.id, "cartridge_id": r.cartridge_id, "barcode": r.barcode, "model": r.model,
        "date": (r.last_date or r.work_date or r.first_date).isoformat() if (r.last_date or r.work_date or r.first_date) else None,
        "worker": r.worker, "defect": r.defect, "worker_id": r.worker_id, "defect_id": r.defect_id,
        "spec_type": r.spec_type, "spec_type_id": r.spec_type_id,
        "advice": r.advice, "remark": r.remark,
        "price": float(r.price) if r.price is not None else None, "is_billed": r.is_billed,
    } for r in (await db.execute(rstmt)).all()]

    # client's cartridges (only for the "add refill / new cartridge" picker)
    carts = (await db.execute(
        select(Cartridge.id, Cartridge.barcode, Cartridge.model_id, CartridgeModel.name.label("model"))
        .select_from(Cartridge).join(CartridgeModel, CartridgeModel.id == Cartridge.model_id, isouter=True)
        .where(Cartridge.client_id == client_id).order_by(Cartridge.barcode)
    )).all()

    # remembered price per cartridge = price of its most recent priced refill (refills are date-desc)
    last_price = {}
    for r in refills:
        cid = r["cartridge_id"]
        if cid not in last_price and r["price"] is not None:
            last_price[cid] = r["price"]

    return {
        "client_id": client.id, "client": client.name,
        "refills": refills,
        "cartridges": [{"id": c.id, "barcode": c.barcode, "model": c.model, "model_id": c.model_id,
                        "last_price": last_price.get(c.id)} for c in carts],
        "unbilled": sum(1 for r in refills if not r["is_billed"]),
    }


def _parse_d(s):
    if not s:
        return None
    try:
        return _date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _cartridge_stats(refills: list) -> dict:
    """Статистика по картриджу для герой-шапки: всего, сумма, средняя, интервал, прогноз «пора»."""
    count = len(refills)
    priced = [r["price"] for r in refills if r["price"] is not None]
    total_sum = round(sum(priced), 2) if priced else 0.0
    avg_price = round(total_sum / len(priced), 2) if priced else None
    last = refills[0] if refills else None          # refills отсортированы по дате убыв.
    last_date = last["date"] if last else None
    last_price = next((r["price"] for r in refills if r["price"] is not None), None)
    last_spec_type = last["spec_type"] if last else None
    last_spec_type_id = last["spec_type_id"] if last else None
    defect_open = last["defect"] if last else None

    dates = sorted({d for d in (_parse_d(r["date"]) for r in refills) if d})
    avg_interval = None
    if len(dates) >= 2:
        diffs = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        diffs = [d for d in diffs if d > 0]
        if diffs:
            avg_interval = round(sum(diffs) / len(diffs))

    days_since = predicted_next = None
    due = "none"
    if dates:
        days_since = (_date.today() - dates[-1]).days
        if avg_interval:
            predicted_next = (dates[-1] + timedelta(days=avg_interval)).isoformat()
            if days_since >= avg_interval:
                due = "overdue"
            elif days_since >= avg_interval * 0.8:
                due = "soon"
    return {
        "count": count, "total_sum": total_sum, "avg_price": avg_price,
        "last_date": last_date, "last_price": last_price,
        "last_spec_type": last_spec_type, "last_spec_type_id": last_spec_type_id,
        "avg_interval_days": avg_interval, "days_since_last": days_since,
        "predicted_next_date": predicted_next, "due": due, "defect_open": defect_open,
    }


def _refill_rows(rows):
    out = []
    for r in rows:
        d = (r.last_date or r.work_date or r.first_date)
        out.append({
            "id": r.id, "cartridge_id": r.cartridge_id, "barcode": r.barcode, "model": r.model,
            "date": d.isoformat() if d else None,
            "worker": r.worker, "defect": r.defect, "worker_id": r.worker_id, "defect_id": r.defect_id,
            "spec_type": r.spec_type, "spec_type_id": r.spec_type_id,
            "advice": r.advice, "remark": r.remark,
            "price": float(r.price) if r.price is not None else None, "is_billed": r.is_billed,
        })
    return out


# ───────────── поиск КАРТРИДЖЕЙ (по штрих-коду/модели/клиенту) → список карточек ─────────────
@router.get("/search")
async def cartridge_search(q: str = Query(default=""), limit: int = Query(default=60, le=200),
                           db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    q = (q or "").strip()
    if not q:
        return []
    eff = func.coalesce(CartridgeRefill.last_date, CartridgeRefill.work_date, CartridgeRefill.first_date)
    base = (select(Cartridge.id, Cartridge.barcode, Cartridge.client_id,
                   Cartridge.is_eternal, Cartridge.is_china,
                   CartridgeModel.name.label("model"), Client.name.label("client"),
                   func.count(CartridgeRefill.id).label("cnt"),
                   func.max(eff).label("last"),
                   func.count(CartridgeRefill.id).filter(CartridgeRefill.is_billed == False).label("unbilled"))
            .select_from(Cartridge)
            .join(CartridgeModel, CartridgeModel.id == Cartridge.model_id, isouter=True)
            .join(Client, Client.id == Cartridge.client_id, isouter=True)
            .join(CartridgeRefill, CartridgeRefill.cartridge_id == Cartridge.id, isouter=True)
            .group_by(Cartridge.id, Cartridge.barcode, Cartridge.client_id,
                      Cartridge.is_eternal, Cartridge.is_china, CartridgeModel.name, Client.name))
    digits = "".join(c for c in q if c.isdigit())
    conds = [Cartridge.barcode.ilike(f"%{q}%"), CartridgeModel.name.ilike(f"%{q}%"), Client.name.ilike(f"%{q}%")]
    if digits:
        norm = func.regexp_replace(Cartridge.barcode, r"\D", "", "g")
        conds.append(norm.like(f"%{digits}%"))
    base = base.where(or_(*conds))
    rows = (await db.execute(base.order_by(desc("last")).limit(limit))).all()
    return [{"cartridge_id": r.id, "barcode": r.barcode, "client_id": r.client_id,
             "client": r.client or "—", "model": r.model, "count": int(r.cnt or 0),
             "unbilled": int(r.unbilled or 0), "has_unbilled": int(r.unbilled or 0) > 0,
             "is_eternal": r.is_eternal, "is_china": r.is_china,
             "last_date": r.last.isoformat() if r.last else None} for r in rows]


# ───────────── КАРТОЧКА КАРТРИДЖА: история заправок именно этого картриджа ─────────────
@router.get("/card/{cid:int}")
async def cartridge_card(cid: int, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    cart = await db.get(Cartridge, cid)
    if not cart:
        raise HTTPException(404, "Картридж не найден")
    client = await db.get(Client, cart.client_id) if cart.client_id else None
    model = await db.get(CartridgeModel, cart.model_id) if cart.model_id else None
    rstmt = (
        select(CartridgeRefill.id, CartridgeRefill.cartridge_id, Cartridge.barcode,
               CartridgeModel.name.label("model"), CartridgeRefill.last_date, CartridgeRefill.work_date,
               CartridgeRefill.first_date,
               CartridgeRefill.advice, CartridgeRefill.remark, CartridgeRefill.price, CartridgeRefill.is_billed,
               CartridgeRefill.worker_id, CartridgeRefill.defect_id, CartridgeRefill.spec_type_id,
               CartridgeSpecType.name.label("spec_type"),
               CartridgeWorker.name.label("worker"), CartridgeDefect.name.label("defect"))
        .select_from(CartridgeRefill)
        .join(Cartridge, Cartridge.id == CartridgeRefill.cartridge_id)
        .join(CartridgeModel, CartridgeModel.id == Cartridge.model_id, isouter=True)
        .join(CartridgeSpecType, CartridgeSpecType.id == CartridgeRefill.spec_type_id, isouter=True)
        .join(CartridgeWorker, CartridgeWorker.id == CartridgeRefill.worker_id, isouter=True)
        .join(CartridgeDefect, CartridgeDefect.id == CartridgeRefill.defect_id, isouter=True)
        .where(CartridgeRefill.cartridge_id == cid)
        .order_by(desc(func.coalesce(CartridgeRefill.last_date, CartridgeRefill.work_date)))
    )
    refills = _refill_rows((await db.execute(rstmt)).all())
    stats = _cartridge_stats(refills)
    last_price = stats["last_price"]
    mname = model.name if model else None
    return {
        "single": True,
        "client_id": cart.client_id, "client": client.name if client else "—",
        "client_type": client.client_type if client else None,
        "client_inn": client.inn if client else None,
        "cartridge_id": cart.id, "barcode": cart.barcode, "model": mname,
        "model_id": cart.model_id, "model_norm": model.norm if model else None,
        "is_eternal": cart.is_eternal, "is_china": cart.is_china, "remark": cart.remark,
        "stats": stats,
        "refills": refills,
        "cartridges": [{"id": cart.id, "barcode": cart.barcode, "model": mname,
                        "model_id": cart.model_id, "last_price": last_price}],
        "unbilled": sum(1 for r in refills if not r["is_billed"]),
    }


# ───────────── add a refill (toner informational — never blocks) ─────────────
class RefillIn(BaseModel):
    date: _date
    spec_type_id: int | None = 1
    worker_id: int | None = None
    defect_id: int | None = None
    advice: str | None = "Заправка"
    remark: str | None = None
    price: float | None = None


@router.post("/{cid:int}/refills")
async def add_refill(cid: int, body: RefillIn, db: AsyncSession = Depends(get_db),
                     _user: User = Depends(get_current_user)):
    c = await db.get(Cartridge, cid)
    if not c:
        raise HTTPException(404, "Картридж не найден")
    dt = datetime.combine(body.date, datetime.min.time())
    r = CartridgeRefill(cartridge_id=cid, first_date=dt, last_date=dt, work_date=dt,
                        spec_type_id=body.spec_type_id or 1,
                        worker_id=body.worker_id, defect_id=body.defect_id,
                        advice=body.advice or "Заправка", remark=body.remark,
                        price=(Decimal(str(body.price)) if body.price is not None else None), is_billed=False)
    db.add(r)
    await db.commit()
    return {"ok": True, "id": r.id}


# ───────────── edit / delete a refill (workers allowed) ─────────────
class RefillEditIn(BaseModel):
    date: _date | None = None
    spec_type_id: int | None = None
    worker_id: int | None = None
    defect_id: int | None = None
    remark: str | None = None
    price: float | None = None


@router.put("/refills/{rid:int}")
async def edit_refill(rid: int, body: RefillEditIn, db: AsyncSession = Depends(get_db),
                      _user: User = Depends(get_current_user)):
    r = await db.get(CartridgeRefill, rid)
    if not r:
        raise HTTPException(404, "Заправка не найдена")
    if r.is_billed:
        raise HTTPException(400, "Заправка уже выписана (в счёте или кассе) — изменить нельзя")
    if body.date:
        dt = datetime.combine(body.date, datetime.min.time())
        r.first_date = r.last_date = r.work_date = dt
    if body.spec_type_id is not None:
        r.spec_type_id = body.spec_type_id
    r.worker_id = body.worker_id
    r.defect_id = body.defect_id
    r.remark = body.remark
    r.price = Decimal(str(body.price)) if body.price is not None else None
    await db.commit()
    return {"ok": True}


@router.delete("/refills/{rid:int}")
async def delete_refill(rid: int, db: AsyncSession = Depends(get_db),
                        _user: User = Depends(get_current_user)):
    r = await db.get(CartridgeRefill, rid)
    if not r:
        raise HTTPException(404, "Заправка не найдена")
    if r.is_billed:
        raise HTTPException(400, "Заправка уже в документе — сначала уберите её из документа")
    await db.delete(r)
    await db.commit()
    return {"ok": True}


# ───────────── create a new cartridge for a client (barcode auto-sequential) ─────────────
class CartridgeIn(BaseModel):
    client_id: int
    model_id: int | None = None
    is_eternal: bool = True
    remark: str | None = None
    barcode: str | None = None   # можно вписать/отсканировать код уже наклеенной этикетки


@router.post("")
async def create_cartridge(body: CartridgeIn, db: AsyncSession = Depends(get_db),
                           _user: User = Depends(get_current_user)):
    barcode = (body.barcode or "").strip() or await _next_barcode(db)
    c = Cartridge(barcode=barcode, client_id=body.client_id, model_id=body.model_id,
                  is_eternal=body.is_eternal, remark=body.remark, created_at=datetime.now())
    db.add(c)
    await db.commit()
    return {"ok": True, "id": c.id, "barcode": barcode}


class CartridgeEditIn(BaseModel):
    barcode: str | None = None
    model_id: int | None = None
    client_id: int | None = None
    is_eternal: bool | None = None
    is_china: bool | None = None
    remark: str | None = None


@router.put("/{cid:int}")
async def update_cartridge(cid: int, body: CartridgeEditIn, db: AsyncSession = Depends(get_db),
                          _user: User = Depends(get_current_user)):
    """Редактирование карточки существующего картриджа (штрих-код, модель, клиент, флаги)."""
    c = await db.get(Cartridge, cid)
    if not c:
        raise HTTPException(404, "Картридж не найден")
    if body.barcode is not None:
        bc = body.barcode.strip()
        if bc:
            c.barcode = bc
    if body.model_id is not None:
        c.model_id = body.model_id
    if body.client_id is not None:
        c.client_id = body.client_id
    if body.is_eternal is not None:
        c.is_eternal = body.is_eternal
    if body.is_china is not None:
        c.is_china = body.is_china
    if body.remark is not None:
        c.remark = body.remark
    await db.commit()
    return {"ok": True, "id": c.id, "barcode": c.barcode}
