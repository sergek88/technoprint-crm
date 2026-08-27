from datetime import date as _date, datetime, timezone, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc, extract, update, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user, require_admin, User
from app.audit_log import log as audit
from app.models import (Document, DocumentItem, Cartridge, CartridgeModel,
                        CartridgeRefill, CartridgeSpecType, WorkJob, GoodSale, Order, Service, Client)
from app.ws import manager

TZ_YEKATERINBURG = timezone(timedelta(hours=5))
SERVICE_REFILL = "Заправка картриджа"
SERVICE_WORK = "Ремонт/работа"
SERVICE_GOODS = "Товар"

router = APIRouter(prefix="/api/documents", tags=["documents"])


# ───────────── cash income helper (Документ не нужен → доход в CRM) ─────────────
async def _get_or_create_service(db: AsyncSession, name: str) -> int:
    s = (await db.execute(select(Service).where(Service.name == name))).scalar_one_or_none()
    if s:
        return s.id
    s = Service(name=name, is_active=True)
    db.add(s)
    await db.flush()
    return s.id


async def _create_cash_order(db: AsyncSession, *, client_id: int, service_name: str,
                             amount: Decimal, on_date, notes: str, created_by: int,
                             transfer: bool = False) -> Order:
    sid = await _get_or_create_service(db, service_name)
    if transfer and "перевод" not in notes.lower():
        notes = (notes + " · перевод").strip()
    # перевод (Коле на карту) → в бакет «Перевод» (amount_card), НЕ в наличные:
    # касса (физ. ящик) считает только amount_cash → перевод в неё не попадёт; комиссий нет (обнулены).
    order = Order(date=on_date, service_id=sid, client_id=client_id,
                  amount_cash=(Decimal(0) if transfer else amount),
                  amount_bank=Decimal(0),
                  amount_card=(amount if transfer else Decimal(0)),
                  is_paid=True, paid_at=datetime.now(TZ_YEKATERINBURG).replace(tzinfo=None),
                  notes=notes, created_by=created_by)
    db.add(order)
    await db.flush()
    return order


MONTHS_RU = ["январь", "февраль", "март", "апрель", "май", "июнь",
             "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]

async def _salary_tracked_from(db: AsyncSession) -> tuple[int, int] | None:
    """С какого месяца зарплата в CRM ведётся полностью (настройка salary_tracked_from, «ГГГГ-ММ»).

    До этого месяца в остатках могут висеть фантомные долги из-за незаполненной истории выплат —
    туда переводы закидывать нельзя. Не задана — ограничения нет.
    """
    from app.models import AppSetting
    row = (await db.execute(select(AppSetting).where(AppSetting.key == "salary_tracked_from"))).scalars().first()
    raw = (row.value or "").strip() if row else ""
    if not raw:
        return None
    try:
        year, month = raw.split("-")[:2]
        return int(year), int(month)
    except (ValueError, IndexError):
        return None


async def _add_transfer_salary(db: AsyncSession, on_date, total: Decimal, label: str) -> list[tuple]:
    """Перевод клиента Коле на карту → выплата ЗП (до commit).

    Пока за ПРОШЛЫЙ месяц не рассчитались, перевод закрывает его долг, и только остаток идёт
    в текущий месяц. Долг перед Колей бывает только за прошлый месяц — глубже не заглядываем.
    Возвращает список (год, месяц, сумма) для уведомлений.
    """
    from app.models import SalaryPayment
    from app.routers.salary import month_balance

    prev_year, prev_month = ((on_date.year - 1, 12) if on_date.month == 1
                             else (on_date.year, on_date.month - 1))
    left = Decimal(str(total))
    parts: list[tuple] = []

    tracked_from = await _salary_tracked_from(db)
    debt = (await month_balance(db, prev_year, prev_month)
            if (tracked_from is None or (prev_year, prev_month) >= tracked_from) else Decimal(0))
    if debt > 0 and left > 0:
        to_prev = min(left, debt).quantize(Decimal("0.01"))
        if to_prev > 0:
            parts.append((prev_year, prev_month, to_prev,
                          f"Перевод от клиента ({label}) — в счёт долга за {MONTHS_RU[prev_month - 1]}"))
            left -= to_prev
    if left > 0:
        parts.append((on_date.year, on_date.month, left, f"Перевод от клиента ({label})"))

    for year, month, amount, notes in parts:
        db.add(SalaryPayment(year=year, month=month, date=on_date,
                             amount=amount, payment_type="card", notes=notes))
    return parts


async def _notify_transfer_salary(db: AsyncSession, parts: list[tuple]) -> None:
    """Telegram-уведомление о начислении перевода в ЗП (после commit) — по каждому месяцу."""
    try:
        from app.routers.salary import _calc_salary
        from app.telegram_bot import notify_salary_payment
        for year, month, amount, _notes in parts:
            sal = await _calc_salary(db, year, month)
            await notify_salary_payment(float(amount), "Перевод", year, month, float(sal.balance))
    except Exception:
        pass


async def _broadcast_order(db: AsyncSession, order: Order):
    """Announce a freshly-created cash order live (journal/dashboard) + Telegram — after commit."""
    try:
        from app.routers.orders import _enrich
        await db.refresh(order, ["service", "client"])
        payload = _enrich(order).model_dump(mode="json")
        await manager.broadcast("order_created", payload)
        try:
            from app.telegram_bot import notify_new_order
            import asyncio
            asyncio.create_task(notify_new_order(payload))
        except Exception:
            pass
    except Exception:
        pass

TYPE_LABEL = {
    "invoice": "Счёт на оплату",
    "act": "Акт выполненных работ",
    "waybill": "Товарная накладная",
    "receipt": "Товарный чек",
}


async def _next_number(db: AsyncSession, doc_type: str) -> str:
    # нумерация сквозная в пределах года (сбрасывается с нового года)
    yr = _date.today().year
    rows = (await db.execute(select(Document.number).where(
        Document.doc_type == doc_type, extract("year", Document.date) == yr))).scalars().all()
    mx = 0
    for n in rows:
        try:
            mx = max(mx, int(n))
        except (ValueError, TypeError):
            pass
    return str(mx + 1)


def _doc_dict(doc: Document, client_name: str, items: list[DocumentItem]):
    return {
        "id": doc.id, "doc_type": doc.doc_type, "type_label": TYPE_LABEL.get(doc.doc_type, doc.doc_type),
        "number": doc.number, "date": doc.date.isoformat() if doc.date else None,
        "client_id": doc.client_id, "client": client_name,
        "total": float(doc.total or 0), "is_paid": doc.is_paid,
        "parent_id": doc.parent_id, "order_id": doc.order_id, "note": doc.note,
        "items": [{"id": it.id, "kind": it.kind, "name": it.name, "unit": it.unit,
                   "qty": float(it.qty), "price": float(it.price), "total": float(it.total)} for it in items],
    }


async def _refill_item_name(db: AsyncSession, r: CartridgeRefill) -> str:
    """Название позиции для счёта/чека по заправке: «Заправка картриджа HP CF217A (TPR…)»."""
    cart = await db.get(Cartridge, r.cartridge_id)
    model = await db.get(CartridgeModel, cart.model_id) if cart and cart.model_id else None
    stype = await db.get(CartridgeSpecType, r.spec_type_id) if r.spec_type_id else None
    mname = (model.name if model else "") or ""
    if mname.lower().startswith("картридж"):
        mname = mname[len("картридж"):].strip()
    base = (stype.name if stype else "Заправка")
    if "картридж" not in base.lower():
        base += " картриджа"
    name = (base + " " + mname).strip()
    if cart and cart.barcode:
        name += f" ({cart.barcode})"
    return name


# ───────────── create invoice (счёт) from selected unbilled refills ─────────────
class CreateInvoiceIn(BaseModel):
    client_id: int
    refill_ids: list[int] = []
    date: _date | None = None   # для офлайна: дата создания (по умолчанию сегодня)
    transfer: bool = False      # перевод Коле на карту → мимо кассы + в зарплату


@router.post("")
async def create_invoice(body: CreateInvoiceIn, db: AsyncSession = Depends(get_db),
                         _user: User = Depends(get_current_user)):
    if not body.refill_ids:
        raise HTTPException(400, "Не выбрано ни одной заправки")
    refills = (await db.execute(select(CartridgeRefill).where(CartridgeRefill.id.in_(body.refill_ids)).with_for_update())).scalars().all()
    if not refills:
        raise HTTPException(404, "Заправки не найдены")
    if any(r.is_billed for r in refills):
        raise HTTPException(400, "Среди выбранных есть уже выписанные заправки")

    doc = Document(client_id=body.client_id, doc_type="invoice",
                   number=await _next_number(db, "invoice"), date=body.date or _date.today(), total=Decimal(0))
    db.add(doc)
    await db.flush()

    total = Decimal(0)
    for r in refills:
        name = await _refill_item_name(db, r)
        price = Decimal(str(r.price)) if r.price is not None else Decimal(0)
        db.add(DocumentItem(document_id=doc.id, kind="work", name=name, unit="шт",
                            qty=Decimal(1), price=price, total=price, refill_id=r.id))
        total += price
        r.is_billed = True
        r.document_id = doc.id

    doc.total = total
    await db.commit()
    return {"ok": True, "id": doc.id}


# ───────────── create invoice (счёт) from selected works (раздел «Работы») ─────────────
class CreateWorkInvoiceIn(BaseModel):
    client_id: int
    work_ids: list[int] = []
    date: _date | None = None
    transfer: bool = False   # перевод Коле на карту → мимо кассы + в зарплату


@router.post("/works")
async def create_work_invoice(body: CreateWorkInvoiceIn, db: AsyncSession = Depends(get_db),
                              _user: User = Depends(get_current_user)):
    if not body.work_ids:
        raise HTTPException(400, "Не выбрано ни одной работы")
    works = (await db.execute(select(WorkJob).where(WorkJob.id.in_(body.work_ids)).with_for_update())).scalars().all()
    if not works:
        raise HTTPException(404, "Работы не найдены")
    if any(w.is_billed for w in works):
        raise HTTPException(400, "Среди выбранных есть уже выписанные работы")

    doc = Document(client_id=body.client_id, doc_type="invoice",
                   number=await _next_number(db, "invoice"), date=body.date or _date.today(), total=Decimal(0))
    db.add(doc)
    await db.flush()

    total = Decimal(0)
    for w in works:
        name = w.title + (f" — {w.device_label}" if w.device_label else "")
        price = Decimal(str(w.price)) if w.price is not None else Decimal(0)
        db.add(DocumentItem(document_id=doc.id, kind="repair", name=name, unit="шт",
                            qty=Decimal(1), price=price, total=price))
        total += price
        w.is_billed = True
        w.document_id = doc.id

    doc.total = total
    await db.commit()
    return {"ok": True, "id": doc.id}


# ───────────── «Документ не нужен»: наличные → доход в CRM (без документа) ─────────────
@router.post("/cash")
async def cash_out_refills(body: CreateInvoiceIn, db: AsyncSession = Depends(get_db),
                           user: User = Depends(get_current_user)):
    if not body.refill_ids:
        raise HTTPException(400, "Не выбрано ни одной заправки")
    refills = (await db.execute(select(CartridgeRefill).where(CartridgeRefill.id.in_(body.refill_ids)).with_for_update())).scalars().all()
    if not refills:
        raise HTTPException(404, "Заправки не найдены")
    if any(r.is_billed for r in refills):
        raise HTTPException(400, "Среди выбранных есть уже выписанные заправки")
    total = sum((Decimal(str(r.price)) for r in refills if r.price is not None), Decimal(0))
    on_date = body.date or _date.today()
    order = await _create_cash_order(db, client_id=body.client_id, service_name=SERVICE_REFILL,
                                     amount=total, on_date=on_date,
                                     notes=f"Заправка картриджа ({'перевод' if body.transfer else 'наличные'}) — {len(refills)} шт",
                                     created_by=user.id, transfer=body.transfer)
    # автоматически формируем ТОВАРНЫЙ ЧЕК (нал, привязан к заказу) — чтобы не выписывать счёт вручную
    doc = Document(client_id=body.client_id, doc_type="receipt",
                   number=await _next_number(db, "receipt"), date=on_date,
                   total=total, order_id=order.id, is_paid=True)
    db.add(doc)
    await db.flush()
    for r in refills:
        name = await _refill_item_name(db, r)
        price = Decimal(str(r.price)) if r.price is not None else Decimal(0)
        db.add(DocumentItem(document_id=doc.id, kind="work", name=name, unit="шт",
                            qty=Decimal(1), price=price, total=price, refill_id=r.id))
        r.is_billed = True
        r.order_id = order.id
    parts = await _add_transfer_salary(db, on_date, total, "заправки") if body.transfer else []
    await db.commit()
    await _broadcast_order(db, order)
    await _notify_transfer_salary(db, parts)
    return {"ok": True, "order_id": order.id, "doc_id": doc.id, "doc_number": doc.number, "total": float(total)}


@router.post("/cash-works")
async def cash_out_works(body: CreateWorkInvoiceIn, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    if not body.work_ids:
        raise HTTPException(400, "Не выбрано ни одной работы")
    works = (await db.execute(select(WorkJob).where(WorkJob.id.in_(body.work_ids)).with_for_update())).scalars().all()
    if not works:
        raise HTTPException(404, "Работы не найдены")
    if any(w.is_billed for w in works):
        raise HTTPException(400, "Среди выбранных есть уже выписанные работы")
    on_date = body.date or _date.today()
    # КАЖДАЯ работа — отдельный заказ (позиция) со своей суммой, а не одной строкой общей суммой
    orders = []
    total = Decimal(0)
    for w in works:
        price = Decimal(str(w.price)) if w.price is not None else Decimal(0)
        order = await _create_cash_order(db, client_id=body.client_id, service_name=SERVICE_WORK,
                                         amount=price, on_date=on_date,
                                         notes=(w.title or "Работа"),
                                         created_by=user.id, transfer=body.transfer)
        w.is_billed = True
        w.order_id = order.id
        orders.append(order)
        total += price
    parts = await _add_transfer_salary(db, on_date, total, "работы") if (body.transfer and total > 0) else []
    await db.commit()
    for o in orders:
        await _broadcast_order(db, o)
    await _notify_transfer_salary(db, parts)
    return {"ok": True, "order_ids": [o.id for o in orders], "total": float(total)}


# ───────────── товар: счёт и наличные ─────────────
class GoodsBatchIn(BaseModel):
    client_id: int
    sale_ids: list[int] = []
    date: _date | None = None
    transfer: bool = False      # перевод Коле на карту → мимо кассы + в зарплату


async def _load_unbilled_sales(db, sale_ids):
    if not sale_ids:
        raise HTTPException(400, "Не выбрано ни одного товара")
    sales = (await db.execute(select(GoodSale).where(GoodSale.id.in_(sale_ids)).with_for_update())).scalars().all()
    if not sales:
        raise HTTPException(404, "Товары не найдены")
    if any(s.is_billed for s in sales):
        raise HTTPException(400, "Среди выбранных есть уже выписанные позиции")
    return sales


@router.post("/goods")
async def create_goods_invoice(body: GoodsBatchIn, db: AsyncSession = Depends(get_db),
                               _user: User = Depends(get_current_user)):
    sales = await _load_unbilled_sales(db, body.sale_ids)
    doc = Document(client_id=body.client_id, doc_type="invoice",
                   number=await _next_number(db, "invoice"), date=body.date or _date.today(), total=Decimal(0))
    db.add(doc)
    await db.flush()
    total = Decimal(0)
    for s in sales:
        qty = Decimal(str(s.qty)) if s.qty is not None else Decimal(1)
        price = Decimal(str(s.price)) if s.price is not None else Decimal(0)
        line = qty * price
        db.add(DocumentItem(document_id=doc.id, kind="goods", name=s.name, unit="шт",
                            qty=qty, price=price, total=line))
        total += line
        s.is_billed = True
        s.document_id = doc.id
    doc.total = total
    await db.commit()
    return {"ok": True, "id": doc.id}


@router.post("/cash-goods")
async def cash_out_goods(body: GoodsBatchIn, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    sales = await _load_unbilled_sales(db, body.sale_ids)
    total = sum(((Decimal(str(s.qty or 1))) * (Decimal(str(s.price)) if s.price is not None else Decimal(0))
                 for s in sales), Decimal(0))
    on_date = body.date or _date.today()
    order = await _create_cash_order(db, client_id=body.client_id, service_name=SERVICE_GOODS,
                                     amount=total, on_date=on_date,
                                     notes=f"Товар ({'перевод' if body.transfer else 'наличные'}) — {len(sales)} поз.",
                                     created_by=user.id, transfer=body.transfer)
    for s in sales:
        s.is_billed = True
        s.order_id = order.id
    parts = await _add_transfer_salary(db, on_date, total, "товар") if body.transfer else []
    await db.commit()
    await _broadcast_order(db, order)
    await _notify_transfer_salary(db, parts)
    return {"ok": True, "order_id": order.id, "total": float(total)}


# ───────────── list documents of a client ─────────────
@router.get("")
async def list_documents(client_id: int = Query(...), db: AsyncSession = Depends(get_db),
                         _user: User = Depends(get_current_user)):
    docs = (await db.execute(
        select(Document).where(Document.client_id == client_id).order_by(desc(Document.date), desc(Document.id))
    )).scalars().all()
    return [{"id": d.id, "doc_type": d.doc_type, "type_label": TYPE_LABEL.get(d.doc_type, d.doc_type),
             "number": d.number, "date": d.date.isoformat() if d.date else None,
             "total": float(d.total or 0), "is_paid": d.is_paid, "order_id": d.order_id} for d in docs]


# ───────────── one document with items ─────────────
@router.get("/{doc_id:int}")
async def get_document(doc_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Документ не найден")
    client = await db.get(Client, doc.client_id)
    items = (await db.execute(select(DocumentItem).where(DocumentItem.document_id == doc_id).order_by(DocumentItem.id))).scalars().all()
    out = _doc_dict(doc, client.name if client else "", items)
    if client:
        out["client_req"] = {k: getattr(client, k) for k in
                             ("full_name", "inn", "kpp", "address", "account", "corr_account", "bank", "bik", "director")}
    children = (await db.execute(select(Document).where(Document.parent_id == doc_id).order_by(Document.id))).scalars().all()
    out["children"] = [{"id": c.id, "doc_type": c.doc_type, "type_label": TYPE_LABEL.get(c.doc_type, c.doc_type),
                        "number": c.number} for c in children]
    return out


# ───────────── edit a line (price / qty / name) ─────────────
class ItemUpdate(BaseModel):
    name: str | None = None
    qty: float | None = None
    price: float | None = None


async def _recompute_doc_total(db: AsyncSession, doc: Document) -> Decimal:
    """Пересчитать сумму документа по позициям и синхронизировать сумму связанного заказа-долга."""
    items = (await db.execute(select(DocumentItem).where(DocumentItem.document_id == doc.id))).scalars().all()
    doc.total = sum((i.total for i in items), Decimal(0))
    if doc.order_id:
        order = await db.get(Order, doc.order_id)
        if order:
            order.amount_bank = doc.total   # долг по счёту = безнал
    return doc.total


@router.put("/{doc_id:int}/items/{item_id:int}")
async def update_item(doc_id: int, item_id: int, body: ItemUpdate,
                      db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    it = await db.get(DocumentItem, item_id)
    if not it or it.document_id != doc_id:
        raise HTTPException(404, "Строка не найдена")
    if body.name is not None:
        it.name = body.name
    if body.qty is not None:
        it.qty = Decimal(str(body.qty))
    if body.price is not None:
        it.price = Decimal(str(body.price))
    it.total = (it.qty or Decimal(0)) * (it.price or Decimal(0))
    await db.flush()
    doc = await db.get(Document, doc_id)
    total = await _recompute_doc_total(db, doc)
    await db.commit()
    return {"ok": True, "item_total": float(it.total), "doc_total": float(total)}


# ───────────── добавить позицию в документ ─────────────
class ItemCreate(BaseModel):
    name: str
    qty: float = 1
    price: float = 0
    kind: str | None = None


@router.post("/{doc_id:int}/items")
async def add_item(doc_id: int, body: ItemCreate, db: AsyncSession = Depends(get_db),
                   _user: User = Depends(get_current_user)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Документ не найден")
    if not (body.name or "").strip():
        raise HTTPException(400, "Укажите наименование позиции")
    # тип позиции: как у существующих строк (иначе товар)
    existing = (await db.execute(select(DocumentItem.kind).where(DocumentItem.document_id == doc_id).limit(1))).scalar_one_or_none()
    kind = body.kind or existing or "goods"
    qty = Decimal(str(body.qty or 1))
    price = Decimal(str(body.price or 0))
    it = DocumentItem(document_id=doc_id, kind=kind, name=body.name.strip(), unit="шт",
                      qty=qty, price=price, total=qty * price)
    db.add(it)
    await db.flush()
    total = await _recompute_doc_total(db, doc)
    await db.commit()
    return {"ok": True, "item_id": it.id, "doc_total": float(total)}


# ───────────── удалить позицию ─────────────
@router.delete("/{doc_id:int}/items/{item_id:int}")
async def delete_item(doc_id: int, item_id: int, db: AsyncSession = Depends(get_db),
                      _user: User = Depends(get_current_user)):
    it = await db.get(DocumentItem, item_id)
    if not it or it.document_id != doc_id:
        raise HTTPException(404, "Строка не найдена")
    await db.delete(it)
    await db.flush()
    doc = await db.get(Document, doc_id)
    total = await _recompute_doc_total(db, doc)
    await db.commit()
    return {"ok": True, "doc_total": float(total)}


# ───────────── изменить шапку документа (дата) ─────────────
class DocEdit(BaseModel):
    date: _date | None = None


@router.put("/{doc_id:int}")
async def edit_document(doc_id: int, body: DocEdit, db: AsyncSession = Depends(get_db),
                        _user: User = Depends(get_current_user)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Документ не найден")
    if body.date:
        doc.date = body.date
        # перенести и связанный заказ-долг на новую дату (чтобы счёт ушёл в нужный месяц в отчётах/долгах)
        if doc.order_id:
            order = await db.get(Order, doc.order_id)
            if order:
                order.date = body.date
        # производные документы (акт/накладная/чек) тоже двигаем за счётом
        await db.execute(update(Document).where(Document.parent_id == doc_id).values(date=body.date))
    await db.commit()
    return {"ok": True}


# ───────────── перевыпустить документ (новый номер + дата) ─────────────
@router.put("/{doc_id:int}/reissue")
async def reissue_document(doc_id: int, db: AsyncSession = Depends(get_db),
                           user: User = Depends(get_current_user)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Документ не найден")
    old = doc.number
    doc.number = await _next_number(db, doc.doc_type)
    doc.date = _date.today()
    # синхронизировать номер счёта в связанном заказе
    if doc.order_id:
        order = await db.get(Order, doc.order_id)
        if order:
            order.invoice_number = doc.number
            order.notes = f"Счёт №{doc.number}"
    audit(db, user, "reissue", f"Перевыпуск {TYPE_LABEL.get(doc.doc_type, doc.doc_type)} №{old} → №{doc.number}")
    await db.commit()
    return {"ok": True, "number": doc.number, "date": doc.date.isoformat()}


# ───────────── поиск документов по номеру ─────────────
@router.get("/search")
async def search_documents(q: str = Query(default=""), db: AsyncSession = Depends(get_db),
                           _user: User = Depends(get_current_user)):
    q = (q or "").strip()
    if not q:
        return []
    rows = (await db.execute(
        select(Document, Client.name)
        .join(Client, Client.id == Document.client_id, isouter=True)
        .where(Document.number.ilike(f"%{q}%"))
        .order_by(desc(Document.date), desc(Document.id)).limit(50)
    )).all()
    return [{"id": d.id, "number": d.number, "doc_type": d.doc_type,
             "type_label": TYPE_LABEL.get(d.doc_type, d.doc_type),
             "date": d.date.isoformat() if d.date else None, "client": cn or "—",
             "total": float(d.total or 0), "is_paid": d.is_paid} for d, cn in rows]


# ───────────── derive акт/накладная/чек «на основании» ─────────────
SERVICE_INVOICE = "Оплата по счёту"

# тип позиций счёта → реальная услуга для строки заказа (чтобы в журнале была не «Оплата по счёту»)
_KIND_SERVICE = {"work": SERVICE_REFILL, "repair": SERVICE_WORK, "goods": SERVICE_GOODS}


async def _doc_service_name(db: AsyncSession, doc_id: int) -> str:
    kinds = set((await db.execute(
        select(DocumentItem.kind).where(DocumentItem.document_id == doc_id))).scalars().all())
    if len(kinds) == 1:
        return _KIND_SERVICE.get(next(iter(kinds)), SERVICE_INVOICE)
    return SERVICE_INVOICE   # смешанный/пустой счёт — общий тип


async def _root_doc(db: AsyncSession, doc: Document) -> Document:
    root = doc
    seen = set()
    while root.parent_id and root.id not in seen:
        seen.add(root.id)
        p = await db.get(Document, root.parent_id)
        if not p:
            break
        root = p
    return root


class DeriveIn(BaseModel):
    doc_type: str  # act | waybill | receipt
    date: _date | None = None   # офлайн: дата создания


@router.post("/{doc_id:int}/derive")
async def derive_document(doc_id: int, body: DeriveIn, db: AsyncSession = Depends(get_db),
                          _user: User = Depends(get_current_user)):
    if body.doc_type not in ("act", "waybill", "receipt"):
        raise HTTPException(400, "Неверный тип документа")
    src = await db.get(Document, doc_id)
    if not src:
        raise HTTPException(404, "Документ не найден")
    # one derived doc of each type per source
    existing = (await db.execute(select(Document).where(Document.parent_id == src.id,
                Document.doc_type == body.doc_type))).scalars().first()
    if existing:
        return {"ok": True, "id": existing.id, "already": True}
    items = (await db.execute(select(DocumentItem).where(DocumentItem.document_id == doc_id).order_by(DocumentItem.id))).scalars().all()
    new = Document(client_id=src.client_id, doc_type=body.doc_type,
                   number=await _next_number(db, body.doc_type), date=body.date or _date.today(),
                   total=src.total, parent_id=src.id)
    db.add(new)
    await db.flush()
    for it in items:
        db.add(DocumentItem(document_id=new.id, kind=it.kind, name=it.name, unit=it.unit,
                            qty=it.qty, price=it.price, total=it.total, refill_id=it.refill_id))
    await db.commit()
    return {"ok": True, "id": new.id}


# ───────────── провести счёт → долг в CRM ─────────────
@router.put("/{doc_id:int}/finalize")
async def finalize_document(doc_id: int, db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Документ не найден")
    root = await _root_doc(db, doc)
    # Товарный чек — документ продажи ЗА НАЛИЧНЫЕ: сумма идёт в кассу и сразу «оплачено».
    # Счёт остаётся как был: безнал + долг до оплаты.
    is_receipt = doc.doc_type == "receipt"
    now = datetime.now(TZ_YEKATERINBURG).replace(tzinfo=None)

    if root.order_id:
        order = await db.get(Order, root.order_id)
        # счёт уже провели безналом (долг), а теперь выписали чек → значит заплатили наличными
        if is_receipt and order and not order.is_paid and (order.amount_bank or 0) > 0:
            amount = order.amount_bank
            order.amount_cash = (order.amount_cash or Decimal(0)) + amount
            order.amount_bank = Decimal(0)
            order.is_paid = True
            order.paid_at = now
            order.notes = f"Товарный чек №{doc.number}"
            root.is_paid = True
            doc.is_paid = True
            audit(db, user, "receipt_cash", f"Тов. чек №{doc.number}: безнал → наличные", amount=amount)
            await db.commit()
            try:
                from app.routers.orders import _enrich
                await db.refresh(order, ["service", "client"])
                await manager.broadcast("debt_paid", _enrich(order).model_dump(mode="json"))
            except Exception:
                pass
            return {"ok": True, "order_id": order.id, "to_cash": True}
        return {"ok": True, "order_id": root.order_id, "already": True}

    if (root.total or 0) <= 0:
        raise HTTPException(400, "Счёт пустой — нечего проводить")
    sid = await _get_or_create_service(db, await _doc_service_name(db, root.id))
    if is_receipt:
        order = Order(date=doc.date or _date.today(), service_id=sid, client_id=root.client_id,
                      amount_cash=root.total, amount_bank=Decimal(0), amount_card=Decimal(0),
                      is_paid=True, paid_at=now, invoice_number=root.number,
                      notes=f"Товарный чек №{doc.number}", created_by=user.id)
        root.is_paid = True
        doc.is_paid = True
    else:
        order = Order(date=_date.today(), service_id=sid, client_id=root.client_id,
                      amount_cash=Decimal(0), amount_bank=root.total, amount_card=Decimal(0),
                      is_paid=False, invoice_number=root.number,
                      notes=f"Счёт №{root.number}", created_by=user.id)
    db.add(order)
    await db.flush()
    root.order_id = order.id
    audit(db, user, "finalize",
          f"Тов. чек №{doc.number} (наличные)" if is_receipt else f"Счёт №{root.number}",
          amount=root.total)
    await db.commit()
    await _broadcast_order(db, order)
    return {"ok": True, "order_id": order.id, "cash": is_receipt}


# ───────────── счёт оплачен ─────────────
@router.put("/{doc_id:int}/mark-paid")
async def mark_document_paid(doc_id: int, db: AsyncSession = Depends(get_db),
                             user: User = Depends(get_current_user)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Документ не найден")
    root = await _root_doc(db, doc)
    root.is_paid = True
    order = await db.get(Order, root.order_id) if root.order_id else None
    if order and not order.is_paid:
        order.is_paid = True
        order.paid_at = datetime.now(TZ_YEKATERINBURG).replace(tzinfo=None)
    audit(db, user, "mark_paid", f"Счёт №{root.number}", amount=(order.amount_bank if order else root.total))
    await db.commit()
    if order:
        try:
            from app.routers.orders import _enrich
            await db.refresh(order, ["service", "client"])
            await manager.broadcast("debt_paid", _enrich(order).model_dump(mode="json"))
        except Exception:
            pass
    return {"ok": True}


# ───────────── удалить документ ─────────────
@router.delete("/{doc_id:int}")
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db),
                          user: User = Depends(get_current_user)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Документ не найден")
    # производный документ (акт/накладная/чек) — удаляем только его, не трогая счёт/долг/выписку
    if doc.parent_id:
        audit(db, user, "delete_document", f"{TYPE_LABEL.get(doc.doc_type, doc.doc_type)} №{doc.number}")
        await db.execute(sql_delete(DocumentItem).where(DocumentItem.document_id == doc.id))
        await db.flush()
        await db.delete(doc)
        await db.commit()
        return {"ok": True}
    # счёт (корень) — полный откат: дети + разблокировка позиций + снятие долга
    root = await _root_doc(db, doc)
    if root.is_paid:
        raise HTTPException(400, "Счёт оплачен — удалить нельзя")
    audit(db, user, "delete_document", f"Счёт №{root.number} (откат)", amount=root.total)
    children = (await db.execute(select(Document).where(Document.parent_id == root.id))).scalars().all()
    family_ids = [root.id] + [c.id for c in children]
    order_id = root.order_id
    order = await db.get(Order, order_id) if order_id else None  # fetch before deletes (avoid autoflush FK order)

    # unbill source refills / works
    for r in (await db.execute(select(CartridgeRefill).where(CartridgeRefill.document_id == root.id))).scalars().all():
        r.is_billed = False
        r.document_id = None
    for w in (await db.execute(select(WorkJob).where(WorkJob.document_id == root.id))).scalars().all():
        w.is_billed = False
        w.document_id = None
    for s in (await db.execute(select(GoodSale).where(GoodSale.document_id == root.id))).scalars().all():
        s.is_billed = False
        s.document_id = None
    await db.flush()

    # delete items (bulk), then child docs, then root, then the debt order — strict FK order
    await db.execute(sql_delete(DocumentItem).where(DocumentItem.document_id.in_(family_ids)))
    for c in children:
        await db.delete(c)
    await db.flush()
    await db.delete(root)
    await db.flush()
    if order:
        await db.delete(order)
    await db.commit()
    if order_id:
        try:
            await manager.broadcast("order_deleted", {"id": order_id})
        except Exception:
            pass
    return {"ok": True}


# ───────────── убрать долг из CRM (отменить проведение счёта) ─────────────
@router.put("/{doc_id:int}/remove-debt")
async def remove_debt(doc_id: int, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Документ не найден")
    root = await _root_doc(db, doc)
    if not root.order_id:
        return {"ok": True, "message": "Долга нет"}
    oid = root.order_id
    order = await db.get(Order, oid)
    audit(db, user, "remove_debt", f"Счёт №{root.number}", amount=(order.amount_bank if order else None))
    root.order_id = None
    root.is_paid = False
    await db.flush()
    if order:
        await db.delete(order)
    await db.commit()
    try:
        await manager.broadcast("order_deleted", {"id": oid})
    except Exception:
        pass
    return {"ok": True}
