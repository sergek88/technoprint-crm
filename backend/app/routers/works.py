from datetime import date as _date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user, User
from app.models import WorkJob, WorkType, CartridgeWorker, Client
from app.routers.cartridges import _period_range, Period

router = APIRouter(prefix="/api/works", tags=["works"])


# ───────────── reference data ─────────────
@router.get("/refs")
async def work_refs(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    types = (await db.execute(select(WorkType).where(WorkType.is_active == True)
                              .order_by(WorkType.sort, WorkType.name))).scalars().all()
    workers = (await db.execute(select(CartridgeWorker).order_by(CartridgeWorker.name))).scalars().all()
    return {
        "work_types": [{"id": t.id, "name": t.name} for t in types],
        "workers": [{"id": w.id, "name": w.name} for w in workers],
    }


# ───────────── clients that have works ─────────────
@router.get("/clients")
async def work_clients(q: str = Query(default=""), db: AsyncSession = Depends(get_db),
                       _user: User = Depends(get_current_user)):
    q = (q or "").strip()
    if q:
        stmt = (select(Client.id, Client.name, func.count(WorkJob.id).label("jobs"))
                .select_from(Client).join(WorkJob, WorkJob.client_id == Client.id, isouter=True)
                .where(Client.name.ilike(f"%{q}%"))
                .group_by(Client.id, Client.name).order_by(Client.name).limit(80))
    else:
        stmt = (select(Client.id, Client.name, func.count(WorkJob.id).label("jobs"))
                .select_from(Client).join(WorkJob, WorkJob.client_id == Client.id)
                .group_by(Client.id, Client.name).order_by(Client.name).limit(80))
    rows = (await db.execute(stmt)).all()
    unbilled = dict((await db.execute(
        select(WorkJob.client_id, func.count(WorkJob.id))
        .where(WorkJob.is_billed == False).group_by(WorkJob.client_id))).all())
    return [{"client_id": r.id, "client": r.name, "jobs": r.jobs,
             "unbilled": int(unbilled.get(r.id, 0))} for r in rows]


# ───────────── ЖУРНАЛ всех работ ─────────────
def _work_journal_filters(base, q, billed, period):
    if q:
        base = base.where(or_(Client.name.ilike(f"%{q}%"), WorkJob.title.ilike(f"%{q}%"),
                              WorkJob.device_label.ilike(f"%{q}%")))
    if billed == "billed":
        base = base.where(WorkJob.is_billed == True)
    elif billed == "unbilled":
        base = base.where(WorkJob.is_billed == False)
    start, end = _period_range(period)
    if start is not None:
        base = base.where(WorkJob.date >= start, WorkJob.date < end)
    return base


@router.get("/journal")
async def work_journal(
    q: str = Query(default=""), billed: str = Query(default="all"),
    period: Period = Query(default="all"),
    limit: int = Query(default=100, le=300), offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user),
):
    q = (q or "").strip()
    base = (select(WorkJob.id, WorkJob.date, WorkJob.client_id, Client.name.label("client"),
                   WorkJob.title, WorkJob.device_label, WorkJob.price, WorkJob.is_billed,
                   CartridgeWorker.name.label("worker"))
            .select_from(WorkJob)
            .join(Client, Client.id == WorkJob.client_id, isouter=True)
            .join(CartridgeWorker, CartridgeWorker.id == WorkJob.worker_id, isouter=True))
    base = _work_journal_filters(base, q, billed, period)
    rows = (await db.execute(base.order_by(WorkJob.date.desc(), WorkJob.id.desc()).limit(limit).offset(offset))).all()
    return [{"id": r.id, "date": r.date.isoformat() if r.date else None, "client": r.client,
             "client_id": r.client_id, "title": r.title, "device_label": r.device_label,
             "worker": r.worker, "price": float(r.price) if r.price is not None else None,
             "is_billed": r.is_billed} for r in rows]


@router.get("/journal/summary")
async def work_journal_summary(
    q: str = Query(default=""), billed: str = Query(default="all"),
    period: Period = Query(default="all"),
    db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user),
):
    """Итоги журнала работ за период: сколько работ и на какую сумму (по всем строкам)."""
    q = (q or "").strip()
    stmt = (select(func.count(WorkJob.id), func.coalesce(func.sum(WorkJob.price), 0))
            .select_from(WorkJob)
            .join(Client, Client.id == WorkJob.client_id, isouter=True))
    stmt = _work_journal_filters(stmt, q, billed, period)
    cnt, total = (await db.execute(stmt)).one()
    return {"count": int(cnt or 0), "sum": float(total or 0)}


# ───────────── one client card: flat works list ─────────────
@router.get("/client/{client_id:int}")
async def work_card(client_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Клиент не найден")
    stmt = (select(WorkJob, CartridgeWorker.name.label("worker"))
            .select_from(WorkJob)
            .join(CartridgeWorker, CartridgeWorker.id == WorkJob.worker_id, isouter=True)
            .where(WorkJob.client_id == client_id)
            .order_by(desc(WorkJob.date), desc(WorkJob.id)))
    rows = (await db.execute(stmt)).all()
    jobs = [{
        "id": w.id, "title": w.title, "device_label": w.device_label,
        "date": w.date.isoformat() if w.date else None,
        "worker": worker, "worker_id": w.worker_id,
        "price": float(w.price) if w.price is not None else None,
        "remark": w.remark, "is_billed": w.is_billed,
    } for w, worker in rows]
    return {"client_id": client.id, "client": client.name, "jobs": jobs,
            "unbilled": sum(1 for j in jobs if not j["is_billed"])}


# ───────────── add / edit / delete a work ─────────────
class WorkIn(BaseModel):
    client_id: int
    title: str
    device_label: str | None = None
    date: _date | None = None
    worker_id: int | None = None
    price: float | None = None
    remark: str | None = None


@router.post("")
async def add_work(body: WorkIn, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    if not (body.title or "").strip():
        raise HTTPException(400, "Укажите вид работы")
    w = WorkJob(client_id=body.client_id, title=body.title.strip(), device_label=body.device_label,
                date=body.date or _date.today(), worker_id=body.worker_id,
                price=(Decimal(str(body.price)) if body.price is not None else None),
                remark=body.remark, is_billed=False)
    db.add(w)
    await db.commit()
    return {"ok": True, "id": w.id}


class WorkEditIn(BaseModel):
    title: str | None = None
    device_label: str | None = None
    date: _date | None = None
    worker_id: int | None = None
    price: float | None = None
    remark: str | None = None


@router.put("/{wid:int}")
async def edit_work(wid: int, body: WorkEditIn, db: AsyncSession = Depends(get_db),
                    _user: User = Depends(get_current_user)):
    w = await db.get(WorkJob, wid)
    if not w:
        raise HTTPException(404, "Работа не найдена")
    if w.is_billed:
        raise HTTPException(400, "Работа уже выписана (в счёте или кассе) — изменить нельзя")
    if body.title is not None:
        w.title = body.title.strip()
    w.device_label = body.device_label
    if body.date:
        w.date = body.date
    w.worker_id = body.worker_id
    w.price = Decimal(str(body.price)) if body.price is not None else None
    w.remark = body.remark
    await db.commit()
    return {"ok": True}


@router.delete("/{wid:int}")
async def delete_work(wid: int, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    w = await db.get(WorkJob, wid)
    if not w:
        raise HTTPException(404, "Работа не найдена")
    if w.is_billed:
        raise HTTPException(400, "Работа уже в документе — сначала уберите её из документа")
    await db.delete(w)
    await db.commit()
    return {"ok": True}
