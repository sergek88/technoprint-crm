from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

TZ_YEKATERINBURG = timezone(timedelta(hours=5))

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, extract
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (Order, Service, Client, CartridgeRefill, WorkJob, GoodSale,
                        Document, DocumentItem, CartridgeSpecType)
from app.schemas import OrderCreate, OrderUpdate, OrderResponse
from app.auth import get_current_user, require_admin, User
from app.audit_log import log as audit
from app.ws import manager

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _enrich(order: Order) -> OrderResponse:
    item = OrderResponse.model_validate(order)
    item.service_name = order.service.name if order.service else None
    item.client_name = order.client.name if order.client else None
    item.amount_total = order.amount_cash + order.amount_bank + order.amount_card
    return item


# ─── человекочитаемая услуга по счёту: «2 заправки и замена чипа» ───
_RU_FORMS = {
    "заправка": ("заправка", "заправки", "заправок"),
    "восстановление": ("восстановление", "восстановления", "восстановлений"),
    "замена чипа": ("замена чипа", "замены чипа", "замен чипа"),
    "ремонт": ("ремонт", "ремонта", "ремонтов"),
    "товар": ("товар", "товара", "товаров"),
}
_CAT_ORDER = ["заправка", "восстановление", "замена чипа", "ремонт", "товар"]


def _ru_plural(n: int, forms) -> str:
    n10, n100 = n % 10, n % 100
    if 11 <= n100 <= 14:
        return forms[2]
    if n10 == 1:
        return forms[0]
    if 2 <= n10 <= 4:
        return forms[1]
    return forms[2]


def _count_word(n: int, forms) -> str:
    w = _ru_plural(n, forms)
    return f"{n} {w}" if n > 1 else w


def _order_summary(items: list) -> str | None:
    """items: (kind, spec_name, item_name). ВСЕ позиции картриджей — заправки; чип/восстановление —
    добавка. Напр. 2 work-позиции (одна с чипом) → «2 заправки и замена чипа»."""
    from collections import Counter
    n_refill = 0
    extras = Counter()      # чип / восстановление среди заправок
    named = []              # работы И товары — конкретными названиями (Печать, Картридж HP…)
    for kind, spec, name in items:
        if kind == "goods":
            named.append((name or "").strip() or "товар")
        elif kind == "repair":
            named.append((name or "").strip() or "работа")
        else:               # work = заправка картриджа (любого типа)
            n_refill += 1
            nm = (spec or name or "").lower()
            if "чип" in nm:
                extras["замена чипа"] += 1
            elif "восстанов" in nm:
                extras["восстановление"] += 1
    parts = []
    if n_refill:
        parts.append(_count_word(n_refill, _RU_FORMS["заправка"]))
    for ex in ("восстановление", "замена чипа"):
        if extras[ex]:
            parts.append(_count_word(extras[ex], _RU_FORMS[ex]))
    # работы и товары — конкретными названиями, адаптивно по длине (без дублей)
    seen = set()
    uniq = [r for r in named if not (r.lower() in seen or seen.add(r.lower()))]
    if uniq:
        # одна позиция — показываем длиннее (читаемо); несколько — короче, чтобы влезло 2
        NAME_CAP = 44 if len(uniq) == 1 else 26
        BUDGET = 54
        def _short(s):
            s = s.strip()
            return s if len(s) <= NAME_CAP else s[:NAME_CAP - 1].rstrip() + "…"
        shown, used = [], 0
        for nm in uniq:
            t = _short(nm)
            add = len(t) + (2 if shown else 0)   # ", " между позициями
            if shown and used + add > BUDGET:
                break
            shown.append(t); used += add
        s_named = ", ".join(shown)
        rest = len(uniq) - len(shown)
        if rest > 0:
            s_named += f" +{rest} поз."
        parts.append(s_named)
    if not parts:
        return None
    s = parts[0] if len(parts) == 1 else (", ".join(parts[:-1]) + " и " + parts[-1])
    return s[:1].upper() + s[1:]


async def _order_content_summaries(db: AsyncSession, order_ids: list[int]) -> dict:
    """Реальное содержимое заказа для журнала: order_id → строка («2 заправки и замена чипа», «Печать»…).
    Покрывает и заказы из счёта (через документ), и кассовые (через прямые order_id-связи заправок/работ/товара).
    Заказы без связей (ручные) не трогаем — у них остаётся название услуги."""
    if not order_ids:
        return {}
    by_order: dict = {}  # oid -> [(kind, spec, name)]
    # 1) через документы (заказы из счёта)
    docs = (await db.execute(select(Document.id, Document.order_id)
            .where(Document.order_id.in_(order_ids)))).all()
    doc_order = {d.id: d.order_id for d in docs}
    if doc_order:
        rows = (await db.execute(
            select(DocumentItem.document_id, DocumentItem.kind, DocumentItem.name, CartridgeSpecType.name.label("spec"))
            .select_from(DocumentItem)
            .join(CartridgeRefill, CartridgeRefill.id == DocumentItem.refill_id, isouter=True)
            .join(CartridgeSpecType, CartridgeSpecType.id == CartridgeRefill.spec_type_id, isouter=True)
            .where(DocumentItem.document_id.in_(list(doc_order.keys()))))).all()
        for r in rows:
            by_order.setdefault(doc_order.get(r.document_id), []).append((r.kind, r.spec, r.name))
    # 2) прямые связи order_id (кассовые заказы без документа)
    direct = [oid for oid in order_ids if oid not in by_order]
    if direct:
        rr = (await db.execute(
            select(CartridgeRefill.order_id, CartridgeSpecType.name.label("spec"))
            .select_from(CartridgeRefill)
            .join(CartridgeSpecType, CartridgeSpecType.id == CartridgeRefill.spec_type_id, isouter=True)
            .where(CartridgeRefill.order_id.in_(direct)))).all()
        for r in rr:
            by_order.setdefault(r.order_id, []).append(("work", r.spec, None))
        wr = (await db.execute(select(WorkJob.order_id, WorkJob.title).where(WorkJob.order_id.in_(direct)))).all()
        for r in wr:
            by_order.setdefault(r.order_id, []).append(("repair", None, r.title))
        gr = (await db.execute(select(GoodSale.order_id, GoodSale.name).where(GoodSale.order_id.in_(direct)))).all()
        for r in gr:
            by_order.setdefault(r.order_id, []).append(("goods", None, r.name))
    return {oid: _order_summary(its) for oid, its in by_order.items() if its}


async def _resolve_service(db: AsyncSession, service_id: int | None, service_name: str | None) -> int:
    """Find or create service by name. Returns service_id."""
    if service_name:
        service_name = service_name.strip()
        result = await db.execute(select(Service).where(Service.name == service_name))
        service = result.scalar_one_or_none()
        if service:
            return service.id
        # Auto-create new service
        new_service = Service(name=service_name, is_active=True)
        db.add(new_service)
        await db.flush()
        return new_service.id
    if service_id:
        return service_id
    raise HTTPException(status_code=400, detail="service_name or service_id required")


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    date: date | None = None,
    month: int | None = None,
    year: int | None = None,
    client_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = (select(Order).options(selectinload(Order.service), selectinload(Order.client))
         .order_by(Order.date, Order.id))
    if date:
        q = q.where(Order.date == date)
    if month:
        q = q.where(extract("month", Order.date) == month)
    if year:
        q = q.where(extract("year", Order.date) == year)
    if client_id:
        q = q.where(Order.client_id == client_id)
    result = await db.execute(q)
    orders = result.scalars().all()
    items = [_enrich(o) for o in orders]
    # реальное содержимое вместо «Оплата по счёту» / «Ремонт/работа»
    summ = await _order_content_summaries(db, [o.id for o in orders])
    for it in items:
        if summ.get(it.id):
            it.service_name = summ[it.id]
    return items


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sid = await _resolve_service(db, data.service_id, data.service_name)
    dump = data.model_dump(exclude={"service_name"})
    dump["service_id"] = sid
    order = Order(**dump, created_by=user.id)
    if order.is_paid:
        order.paid_at = datetime.now(TZ_YEKATERINBURG).replace(tzinfo=None)
    db.add(order)
    await db.commit()
    await db.refresh(order, ["service", "client"])
    item = _enrich(order)
    data_dict = item.model_dump(mode="json")
    await manager.broadcast("order_created", data_dict)
    # Telegram notification (fire-and-forget)
    try:
        from app.telegram_bot import notify_new_order
        import asyncio
        asyncio.create_task(notify_new_order(data_dict))
    except Exception:
        pass
    return item


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    data: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    updates = data.model_dump(exclude_unset=True)
    # Resolve service_name → service_id
    if "service_name" in updates:
        sname = updates.pop("service_name")
        if sname:
            updates["service_id"] = await _resolve_service(db, None, sname)
    for key, val in updates.items():
        setattr(order, key, val)
    # Set paid_at if is_paid changed to True
    if "is_paid" in updates and updates["is_paid"] and not order.paid_at:
        order.paid_at = datetime.now(TZ_YEKATERINBURG).replace(tzinfo=None)
    await db.commit()
    await db.refresh(order, ["service", "client"])
    item = _enrich(order)
    await manager.broadcast("order_updated", item.model_dump(mode="json"))
    return item


@router.delete("/{order_id}")
async def delete_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    # debt order created from an invoice — manage it via the document, not here
    doc = (await db.execute(select(Document).where(Document.order_id == order_id))).scalars().first()
    if doc:
        raise HTTPException(status_code=400, detail="Заказ создан из счёта — удаляйте через документ")
    # cash sale: return its linked refills/works/goods to "не выписано"
    for r in (await db.execute(select(CartridgeRefill).where(CartridgeRefill.order_id == order_id))).scalars().all():
        r.is_billed = False; r.order_id = None
    for w in (await db.execute(select(WorkJob).where(WorkJob.order_id == order_id))).scalars().all():
        w.is_billed = False; w.order_id = None
    for s in (await db.execute(select(GoodSale).where(GoodSale.order_id == order_id))).scalars().all():
        s.is_billed = False; s.order_id = None
    audit(db, user, "delete_order", f"Заказ #{order_id}: {order.notes or ''}",
          amount=(order.amount_cash + order.amount_bank + order.amount_card))
    await db.flush()
    await db.delete(order)
    await db.commit()
    await manager.broadcast("order_deleted", {"id": order_id})
    return {"ok": True}


@router.put("/{order_id}/mark-paid", response_model=OrderResponse)
async def mark_paid(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.is_paid = True
    order.paid_at = datetime.now(TZ_YEKATERINBURG).replace(tzinfo=None)
    await db.commit()
    await db.refresh(order, ["service", "client"])
    item = _enrich(order)
    data_dict = item.model_dump(mode="json")
    await manager.broadcast("debt_paid", data_dict)
    try:
        from app.telegram_bot import notify_debt_paid
        import asyncio
        asyncio.create_task(notify_debt_paid(data_dict))
    except Exception:
        pass
    return item
