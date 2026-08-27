from io import BytesIO
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, or_, extract, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Order, Client, Service, Expense, MonthlyCost
from app.schemas import SearchResult
from app.auth import get_current_user, User
from app.config import BANK_COMMISSION, CARD_COMMISSION

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=list[SearchResult])
async def global_search(
    q: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    results: list[SearchResult] = []
    pattern = f"%{q}%"

    clients = await db.execute(
        select(Client).where(Client.name.ilike(pattern)).limit(5)
    )
    for c in clients.scalars():
        results.append(SearchResult(type="client", id=c.id, title=c.name, subtitle=c.phone))

    services = await db.execute(
        select(Service).where(Service.name.ilike(pattern)).limit(5)
    )
    for s in services.scalars():
        results.append(SearchResult(type="service", id=s.id, title=s.name))

    orders = await db.execute(
        select(Order)
        .where(or_(Order.notes.ilike(pattern), Order.invoice_number.ilike(pattern)))
        .order_by(Order.date.desc())
        .limit(5)
    )
    for o in orders.scalars():
        await db.refresh(o, ["service", "client"])
        title = f"{o.date} — {o.service.name}" if o.service else str(o.date)
        subtitle = o.client.name if o.client else None
        results.append(SearchResult(type="order", id=o.id, title=title, subtitle=subtitle))

    return results


@router.get("/export/monthly")
async def export_monthly(
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    from openpyxl import Workbook
    from decimal import Decimal

    wb = Workbook()
    ws = wb.active
    ws.title = f"{month:02d}.{year}"

    headers = ["#", "Дата", "Услуга", "Клиент", "Нал.", "Безнал.", "Карта", "Итого", "Оплачен", "Счёт", "Примечание"]
    ws.append(headers)

    result = await db.execute(
        select(Order)
        .where(extract("year", Order.date) == year, extract("month", Order.date) == month)
        .order_by(Order.date, Order.id)
    )
    orders = result.scalars().all()
    for i, o in enumerate(orders, 1):
        await db.refresh(o, ["service", "client"])
        ws.append([
            i,
            o.date.isoformat(),
            o.service.name if o.service else "",
            o.client.name if o.client else "",
            float(o.amount_cash),
            float(o.amount_bank),
            float(o.amount_card),
            float(o.amount_cash + o.amount_bank + o.amount_card),
            "Да" if o.is_paid else "Нет",
            o.invoice_number or "",
            o.notes or "",
        ])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"TechnoPrint_{year}-{month:02d}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/yearly")
async def export_yearly(
    year: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    from openpyxl import Workbook
    from decimal import Decimal

    wb = Workbook()
    ws = wb.active
    ws.title = f"Итоги {year}"

    headers = ["Месяц", "Заказов", "Нал.", "Безнал.", "Карта", "Выручка", "Расходы товар", "Расходы пост.", "Прибыль"]
    ws.append(headers)

    month_names = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                   "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

    for m in range(1, 13):
        r = await db.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.amount_cash), 0),
                func.coalesce(func.sum(Order.amount_bank), 0),
                func.coalesce(func.sum(Order.amount_card), 0),
            ).where(extract("year", Order.date) == year, extract("month", Order.date) == m)
        )
        count, cash, bank, card = r.one()
        revenue = cash + bank * Decimal(str(1 - BANK_COMMISSION)) + card * Decimal(str(1 - CARD_COMMISSION))

        exp_r = await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0))
            .where(extract("year", Expense.date) == year, extract("month", Expense.date) == m)
        )
        exp_supplies = exp_r.scalar()

        mc_r = await db.execute(
            select(MonthlyCost).where(MonthlyCost.year == year, MonthlyCost.month == m)
        )
        mc = mc_r.scalar_one_or_none()
        exp_fixed = Decimal("0")
        if mc:
            exp_fixed = mc.salary_admin + mc.salary_master + mc.rent + mc.taxes + mc.other

        ws.append([
            month_names[m - 1], count,
            float(cash), float(bank), float(card),
            float(revenue), float(exp_supplies), float(exp_fixed),
            float(revenue - exp_supplies - exp_fixed),
        ])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"TechnoPrint_{year}_год.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
