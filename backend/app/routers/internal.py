"""
Internal API for JarClaude integration.
No JWT auth — protected by X-Internal-Token header only.
Only accessible from localhost (same server).
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select, func, extract, not_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Order, Expense, MonthlyCost, CashWithdrawal, SalaryPayment
from app.config import INTERNAL_TOKEN, BANK_COMMISSION, CARD_COMMISSION

router = APIRouter(prefix="/internal", tags=["internal"])


def _fmt(n) -> str:
    return f"{round(float(n)):,}".replace(",", " ") + " ₽"


def _check_token(x_internal_token: str = Header(default="")):
    if not INTERNAL_TOKEN or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_check_token),
):
    """Full stats snapshot for JarClaude: today + current month + debts."""
    today = date.today()
    y, m = today.year, today.month

    # ── Today ──
    today_r = await db.execute(
        select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.amount_cash), 0),
            func.coalesce(func.sum(Order.amount_bank), 0),
            func.coalesce(func.sum(Order.amount_card), 0),
        ).where(Order.date == today)
    )
    t_count, t_cash, t_bank, t_card = today_r.one()
    t_total = t_cash + t_bank + t_card

    # ── Month ──
    month_r = await db.execute(
        select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.amount_cash), 0),
            func.coalesce(func.sum(Order.amount_bank), 0),
            func.coalesce(func.sum(Order.amount_card), 0),
        ).where(
            extract("year", Order.date) == y,
            extract("month", Order.date) == m,
        )
    )
    m_count, m_cash, m_bank, m_card = month_r.one()
    m_bank_net = m_bank * Decimal(str(1 - BANK_COMMISSION))
    m_card_net = m_card * Decimal(str(1 - CARD_COMMISSION))
    m_revenue = m_cash + m_bank_net + m_card_net

    exp_r = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            extract("year", Expense.date) == y,
            extract("month", Expense.date) == m,
        )
    )
    m_exp_supplies = exp_r.scalar()

    mc_r = await db.execute(
        select(MonthlyCost).where(MonthlyCost.year == y, MonthlyCost.month == m)
    )
    mc = mc_r.scalar_one_or_none()
    m_exp_fixed = Decimal("0")
    if mc:
        m_exp_fixed = mc.salary_admin + mc.salary_master + mc.rent + mc.taxes + mc.other
    m_profit = m_revenue - m_exp_supplies - m_exp_fixed

    # ── Debts ──
    debts_r = await db.execute(
        select(Order).where(Order.is_paid == False).order_by(Order.date)
    )
    debt_orders = debts_r.scalars().all()

    debt_total = Decimal("0")
    debt_items = []
    for o in debt_orders:
        await db.refresh(o, ["client", "service"])
        amount = o.amount_bank + o.amount_card
        days = (today - o.date).days
        debt_total += amount
        debt_items.append({
            "client": o.client.name,
            "service": o.service.name,
            "amount": float(amount),
            "days": days,
            "invoice": o.invoice_number,
        })

    # ── Cash register ──
    cash_in_r = await db.execute(
        select(func.coalesce(func.sum(Order.amount_cash), 0)).where(
            not_(func.lower(func.coalesce(Order.notes, '')).contains('перевод'))
        )
    )
    cash_out_r = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.from_cash_register == True)
    )
    withdrawn_r = await db.execute(select(func.coalesce(func.sum(CashWithdrawal.amount), 0)))
    cash_register = cash_in_r.scalar() - cash_out_r.scalar() - withdrawn_r.scalar()

    return {
        "today": {
            "date": str(today),
            "order_count": t_count,
            "cash": float(t_cash),
            "bank": float(t_bank),
            "card": float(t_card),
            "total": float(t_total),
        },
        "month": {
            "year": y,
            "month": m,
            "order_count": m_count,
            "revenue": float(m_revenue),
            "expenses_supplies": float(m_exp_supplies),
            "expenses_fixed": float(m_exp_fixed),
            "profit": float(m_profit),
        },
        "debts": {
            "count": len(debt_items),
            "total": float(debt_total),
            "items": debt_items[:20],  # top 20
        },
        "cash_register": float(cash_register),
    }


# ═══════════════ ACTION ENDPOINTS ═══════════════


@router.post("/mark-paid")
async def mark_invoices_paid(
    invoices: str,  # comma-separated invoice numbers: "485,486,487"
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_check_token),
):
    """Mark one or more invoices as paid. Returns results per invoice."""
    numbers = [n.strip() for n in invoices.split(",") if n.strip()]
    if not numbers:
        raise HTTPException(400, "No invoice numbers provided")

    results = []
    for inv in numbers:
        result = await db.execute(
            select(Order).where(Order.invoice_number == inv, Order.is_paid == False)
        )
        order = result.scalar_one_or_none()
        if order:
            order.is_paid = True
            order.paid_at = datetime.now()
            await db.refresh(order, ["client"])
            amount = order.amount_bank + order.amount_card
            results.append({"invoice": inv, "status": "paid", "client": order.client.name, "amount": float(amount)})
        else:
            result2 = await db.execute(select(Order).where(Order.invoice_number == inv))
            existing = result2.scalar_one_or_none()
            if existing:
                results.append({"invoice": inv, "status": "already_paid"})
            else:
                results.append({"invoice": inv, "status": "not_found"})
    await db.commit()
    return {"results": results}


@router.post("/expense")
async def add_expense(
    amount: float,
    description: str = "ОЗОН",
    category: str = "parts",
    from_cash: bool = False,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_check_token),
):
    """Add an expense (supplies/parts purchase)."""
    today = date.today()
    expense = Expense(
        date=today,
        category=category,
        description=description,
        amount=Decimal(str(amount)),
        from_cash_register=from_cash,
    )
    db.add(expense)
    await db.commit()
    return {"status": "ok", "amount": amount, "description": description, "date": str(today)}


@router.post("/salary-payment")
async def add_salary_payment(
    amount: float,
    payment_type: str = "card",  # cash, bank, card
    notes: str = "",
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_check_token),
):
    """Add a salary payment for the previous month."""
    today = date.today()
    if today.month == 1:
        prev_year, prev_month = today.year - 1, 12
    else:
        prev_year, prev_month = today.year, today.month - 1

    if amount == 13550:
        payment_type = "bank"  # official salary

    payment = SalaryPayment(
        year=prev_year, month=prev_month,
        date=today, amount=Decimal(str(amount)),
        payment_type=payment_type, notes=notes,
    )
    db.add(payment)
    await db.commit()

    # Calculate remaining balance
    from app.routers.salary import _calc_salary
    sal = await _calc_salary(db, prev_year, prev_month)

    month_names = ["Январь","Февраль","Март","Апрель","Май","Июнь",
                   "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
    return {
        "status": "ok",
        "amount": amount,
        "payment_type": payment_type,
        "month": f"{month_names[prev_month-1]} {prev_year}",
        "balance": float(sal.balance),
    }


@router.get("/debts")
async def get_debts(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_check_token),
):
    """Get all current debts with details."""
    today = date.today()
    result = await db.execute(
        select(Order).where(Order.is_paid == False).order_by(Order.date)
    )
    orders = result.scalars().all()

    items = []
    total = Decimal("0")
    for o in orders:
        await db.refresh(o, ["client", "service"])
        amount = o.amount_bank + o.amount_card
        days = (today - o.date).days
        total += amount
        items.append({
            "id": o.id,
            "invoice": o.invoice_number,
            "client": o.client.name,
            "service": o.service.name,
            "amount": float(amount),
            "days": days,
            "date": str(o.date),
        })

    return {"count": len(items), "total": float(total), "items": items}
