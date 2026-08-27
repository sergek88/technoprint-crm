from datetime import date as _date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user, User
from app.models import Good, GoodSale, Client
from app.routers.cartridges import _period_range, Period

router = APIRouter(prefix="/api/goods", tags=["goods"])


# ───────────── catalog search (для подбора товара) ─────────────
@router.get("/catalog")
async def goods_catalog(q: str = Query(default=""), db: AsyncSession = Depends(get_db),
                        _user: User = Depends(get_current_user)):
    q = (q or "").strip()
    stmt = select(Good).where(Good.is_active == True)
    if q:
        stmt = stmt.where(or_(Good.name.ilike(f"%{q}%"), Good.code.ilike(f"%{q}%")))
    stmt = stmt.order_by(Good.name).limit(40)
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": g.id, "code": g.code, "name": g.name, "category": g.category,
             "unit": g.unit, "last_price": float(g.last_price) if g.last_price is not None else None}
            for g in rows]


# ───────────── clients that have goods sales ─────────────
@router.get("/clients")
async def goods_clients(q: str = Query(default=""), db: AsyncSession = Depends(get_db),
                        _user: User = Depends(get_current_user)):
    q = (q or "").strip()
    if q:
        # поиск среди ВСЕХ клиентов — чтобы оформить продажу любому
        stmt = (select(Client.id, Client.name, func.count(GoodSale.id).label("sales"))
                .select_from(Client).join(GoodSale, GoodSale.client_id == Client.id, isouter=True)
                .where(Client.name.ilike(f"%{q}%"))
                .group_by(Client.id, Client.name).order_by(Client.name).limit(80))
    else:
        # без запроса — только клиенты с продажами
        stmt = (select(Client.id, Client.name, func.count(GoodSale.id).label("sales"))
                .select_from(Client).join(GoodSale, GoodSale.client_id == Client.id)
                .group_by(Client.id, Client.name).order_by(Client.name).limit(80))
    rows = (await db.execute(stmt)).all()
    unbilled = dict((await db.execute(
        select(GoodSale.client_id, func.count(GoodSale.id))
        .where(GoodSale.is_billed == False).group_by(GoodSale.client_id))).all())
    return [{"client_id": r.id, "client": r.name, "sales": r.sales,
             "unbilled": int(unbilled.get(r.id, 0))} for r in rows]


# ───────────── ЖУРНАЛ всех продаж товара ─────────────
def _goods_journal_filters(base, q, billed, period):
    if q:
        base = base.where(or_(Client.name.ilike(f"%{q}%"), GoodSale.name.ilike(f"%{q}%")))
    if billed == "billed":
        base = base.where(GoodSale.is_billed == True)
    elif billed == "unbilled":
        base = base.where(GoodSale.is_billed == False)
    start, end = _period_range(period)
    if start is not None:
        base = base.where(GoodSale.date >= start, GoodSale.date < end)
    return base


@router.get("/journal")
async def goods_journal(
    q: str = Query(default=""), billed: str = Query(default="all"),
    period: Period = Query(default="all"),
    limit: int = Query(default=100, le=300), offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user),
):
    q = (q or "").strip()
    base = (select(GoodSale.id, GoodSale.date, GoodSale.client_id, Client.name.label("client"),
                   GoodSale.name, GoodSale.qty, GoodSale.price, GoodSale.is_billed)
            .select_from(GoodSale)
            .join(Client, Client.id == GoodSale.client_id, isouter=True))
    base = _goods_journal_filters(base, q, billed, period)
    rows = (await db.execute(base.order_by(GoodSale.date.desc(), GoodSale.id.desc()).limit(limit).offset(offset))).all()
    return [{"id": r.id, "date": r.date.isoformat() if r.date else None, "client": r.client,
             "client_id": r.client_id, "name": r.name,
             "qty": float(r.qty) if r.qty is not None else 1,
             "price": float(r.price) if r.price is not None else None,
             "is_billed": r.is_billed} for r in rows]


@router.get("/journal/summary")
async def goods_journal_summary(
    q: str = Query(default=""), billed: str = Query(default="all"),
    period: Period = Query(default="all"),
    db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user),
):
    """Итоги журнала товара за период: сколько позиций и на какую сумму (price × qty, по всем строкам)."""
    q = (q or "").strip()
    stmt = (select(func.count(GoodSale.id),
                   func.coalesce(func.sum(GoodSale.price * func.coalesce(GoodSale.qty, 1)), 0))
            .select_from(GoodSale)
            .join(Client, Client.id == GoodSale.client_id, isouter=True))
    stmt = _goods_journal_filters(stmt, q, billed, period)
    cnt, total = (await db.execute(stmt)).one()
    return {"count": int(cnt or 0), "sum": float(total or 0)}


# ───────────── one client card: flat sales list ─────────────
@router.get("/client/{client_id:int}")
async def goods_card(client_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Клиент не найден")
    rows = (await db.execute(select(GoodSale).where(GoodSale.client_id == client_id)
            .order_by(desc(GoodSale.date), desc(GoodSale.id)))).scalars().all()
    sales = [{
        "id": s.id, "name": s.name, "good_id": s.good_id,
        "qty": float(s.qty) if s.qty is not None else 1,
        "price": float(s.price) if s.price is not None else None,
        "date": s.date.isoformat() if s.date else None,
        "remark": s.remark, "is_billed": s.is_billed,
    } for s in rows]
    return {"client_id": client.id, "client": client.name, "sales": sales,
            "unbilled": sum(1 for s in sales if not s["is_billed"])}


# ───────────── add / edit / delete a sale ─────────────
class SaleIn(BaseModel):
    client_id: int
    good_id: int | None = None
    name: str
    qty: float = 1
    price: float | None = None
    date: _date | None = None
    remark: str | None = None


@router.post("/sale")
async def add_sale(body: SaleIn, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    if not (body.name or "").strip():
        raise HTTPException(400, "Укажите товар")
    s = GoodSale(client_id=body.client_id, good_id=body.good_id, name=body.name.strip(),
                 qty=Decimal(str(body.qty or 1)),
                 price=(Decimal(str(body.price)) if body.price is not None else None),
                 date=body.date or _date.today(), remark=body.remark, is_billed=False)
    db.add(s)
    # remember price on the catalog item
    if body.good_id and body.price is not None:
        g = await db.get(Good, body.good_id)
        if g:
            g.last_price = Decimal(str(body.price))
    await db.commit()
    return {"ok": True, "id": s.id}


class SaleEditIn(BaseModel):
    name: str | None = None
    qty: float | None = None
    price: float | None = None
    date: _date | None = None
    remark: str | None = None


@router.put("/sale/{sid:int}")
async def edit_sale(sid: int, body: SaleEditIn, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    s = await db.get(GoodSale, sid)
    if not s:
        raise HTTPException(404, "Продажа не найдена")
    if s.is_billed:
        raise HTTPException(400, "Уже выписано (в счёте или кассе) — изменить нельзя")
    if body.name is not None:
        s.name = body.name.strip()
    if body.qty is not None:
        s.qty = Decimal(str(body.qty))
    s.price = Decimal(str(body.price)) if body.price is not None else None
    if body.date:
        s.date = body.date
    s.remark = body.remark
    if s.good_id and s.price is not None:
        g = await db.get(Good, s.good_id)
        if g:
            g.last_price = s.price
    await db.commit()
    return {"ok": True}


@router.delete("/sale/{sid:int}")
async def delete_sale(sid: int, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    s = await db.get(GoodSale, sid)
    if not s:
        raise HTTPException(404, "Продажа не найдена")
    if s.is_billed:
        raise HTTPException(400, "Уже выписано — сначала уберите из документа")
    await db.delete(s)
    await db.commit()
    return {"ok": True}
