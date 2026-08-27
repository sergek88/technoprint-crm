from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Order
from app.schemas import DebtItem, DebtsByClient
from app.auth import get_current_user, User

router = APIRouter(prefix="/api/debts", tags=["debts"])


@router.get("", response_model=list[DebtItem])
async def list_debts(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Order).options(selectinload(Order.service), selectinload(Order.client))
        .where(Order.is_paid == False)
        .order_by(Order.date)
    )
    orders = result.scalars().all()
    items = []
    today = date.today()
    for o in orders:
        items.append(DebtItem(
            order_id=o.id,
            date=o.date,
            client_id=o.client_id,
            client_name=o.client.name,
            client_phone=o.client.phone,
            service_name=o.service.name,
            amount=o.amount_bank + o.amount_card,
            days_overdue=(today - o.date).days,
            invoice_number=o.invoice_number,
        ))
    return items


@router.get("/overdue", response_model=list[DebtItem])
async def overdue_debts(
    days: int = Query(default=14, ge=1),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(
        select(Order).options(selectinload(Order.service), selectinload(Order.client))
        .where(Order.is_paid == False, Order.date <= cutoff)
        .order_by(Order.date)
    )
    orders = result.scalars().all()
    today = date.today()
    items = []
    for o in orders:
        items.append(DebtItem(
            order_id=o.id,
            date=o.date,
            client_id=o.client_id,
            client_name=o.client.name,
            client_phone=o.client.phone,
            service_name=o.service.name,
            amount=o.amount_bank + o.amount_card,
            days_overdue=(today - o.date).days,
            invoice_number=o.invoice_number,
        ))
    return items


@router.get("/by-client", response_model=list[DebtsByClient])
async def debts_by_client(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Order).options(selectinload(Order.service), selectinload(Order.client))
        .where(Order.is_paid == False)
        .order_by(Order.client_id, Order.date)
    )
    orders = result.scalars().all()
    today = date.today()

    grouped: dict[int, DebtsByClient] = {}
    for o in orders:
        debt_item = DebtItem(
            order_id=o.id,
            date=o.date,
            client_id=o.client_id,
            client_name=o.client.name,
            client_phone=o.client.phone,
            service_name=o.service.name,
            amount=o.amount_bank + o.amount_card,
            days_overdue=(today - o.date).days,
            invoice_number=o.invoice_number,
        )
        if o.client_id not in grouped:
            grouped[o.client_id] = DebtsByClient(
                client_id=o.client_id,
                client_name=o.client.name,
                client_phone=o.client.phone,
                total_debt=Decimal("0"),
                debts=[],
            )
        grouped[o.client_id].debts.append(debt_item)
        grouped[o.client_id].total_debt += debt_item.amount

    return sorted(grouped.values(), key=lambda x: x.total_debt, reverse=True)
