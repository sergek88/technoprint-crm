from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, extract, case, not_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Order, Expense, MonthlyCost, CashWithdrawal, SalaryPayment, CartridgeRefill, WorkJob, GoodSale
from app.schemas import DailySummary, MonthlySummary, YearlySummary, OrderResponse
from app.auth import get_current_user, require_admin, User
from app.audit_log import log as audit
from app.config import BANK_COMMISSION, CARD_COMMISSION

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/daily", response_model=DailySummary)
async def daily_summary(
    date: date = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if date is None:
        from datetime import date as d
        date = d.today()

    result = await db.execute(
        select(Order).where(Order.date == date)
        .options(selectinload(Order.service), selectinload(Order.client)).order_by(Order.id)
    )
    orders = result.scalars().all()

    # показываем ВСЕ заказы (и оплаченные, и в долг) — владельцу нужен полный оборот за день
    cash = sum(o.amount_cash for o in orders)
    bank = sum(o.amount_bank for o in orders)
    card = sum(o.amount_card for o in orders)

    order_items = []
    for o in orders:
        item = OrderResponse.model_validate(o)
        item.service_name = o.service.name if o.service else None
        item.client_name = o.client.name if o.client else None
        item.amount_total = o.amount_cash + o.amount_bank + o.amount_card
        order_items.append(item)

    # реальное содержимое вместо «Оплата по счёту» / «Ремонт/работа»
    from app.routers.orders import _order_content_summaries
    summ = await _order_content_summaries(db, [o.id for o in orders])
    for it in order_items:
        if summ.get(it.id):
            it.service_name = summ[it.id]

    cash_register = await _calc_cash_register(db)

    return DailySummary(
        date=date,
        order_count=len(orders),
        cash=cash,
        bank=bank,
        card=card,
        total=cash + bank + card,
        cash_register=cash_register,
        orders=order_items,
    )


async def _monthly(year: int, month: int, db: AsyncSession) -> MonthlySummary:
    result = await db.execute(
        select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.amount_cash), 0),
            func.coalesce(func.sum(Order.amount_bank), 0),
            func.coalesce(func.sum(Order.amount_card), 0),
            func.coalesce(func.sum(
                case((Order.is_paid == False, Order.amount_bank + Order.amount_card), else_=Decimal("0"))
            ), 0),
        ).where(
            extract("year", Order.date) == year,
            extract("month", Order.date) == month,
        )
    )
    count, cash, bank, card, debt = result.one()

    bank_net = bank * Decimal(str(1 - BANK_COMMISSION))
    card_net = card * Decimal(str(1 - CARD_COMMISSION))
    revenue = cash + bank_net + card_net

    exp_result = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            extract("year", Expense.date) == year,
            extract("month", Expense.date) == month,
        )
    )
    expenses_supplies = exp_result.scalar()

    mc_result = await db.execute(
        select(MonthlyCost).where(MonthlyCost.year == year, MonthlyCost.month == month)
    )
    mc = mc_result.scalar_one_or_none()
    expenses_fixed = Decimal("0")
    if mc:
        expenses_fixed = mc.salary_admin + mc.salary_master + mc.rent + mc.taxes + mc.other

    return MonthlySummary(
        year=year,
        month=month,
        order_count=count,
        cash=cash,
        bank=bank,
        card=card,
        revenue=revenue,
        expenses_supplies=expenses_supplies,
        expenses_fixed=expenses_fixed,
        expenses_total=expenses_supplies + expenses_fixed,
        profit=revenue - expenses_supplies - expenses_fixed,
        debt_amount=debt,
    )


@router.get("/monthly", response_model=MonthlySummary)
async def monthly_summary(
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await _monthly(year, month, db)


@router.get("/yearly", response_model=YearlySummary)
async def yearly_summary(
    year: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    from datetime import date as d
    today = d.today()
    max_month = today.month if year == today.year else 12

    months = []
    for m in range(1, max_month + 1):
        months.append(await _monthly(year, m, db))

    total_revenue = sum(m.revenue for m in months)
    total_expenses = sum(m.expenses_total for m in months)
    total_profit = total_revenue - total_expenses
    active_months = sum(1 for m in months if m.order_count > 0) or 1
    total_cash = sum(m.cash for m in months)

    return YearlySummary(
        year=year,
        months=months,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        total_profit=total_profit,
        avg_monthly_profit=total_profit / active_months,
        total_cash=total_cash,
    )


async def _calc_cash_register(db: AsyncSession) -> Decimal:
    """Cash register = cash orders (no 'перевод') - cash expenses - withdrawals."""
    cash_in_r = await db.execute(
        select(func.coalesce(func.sum(Order.amount_cash), 0)).where(
            not_(func.lower(func.coalesce(Order.notes, '')).contains('перевод'))
        )
    )
    cash_in = cash_in_r.scalar()

    cash_out_r = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.from_cash_register == True
        )
    )
    cash_out = cash_out_r.scalar()

    withdrawn_r = await db.execute(
        select(func.coalesce(func.sum(CashWithdrawal.amount), 0))
    )
    withdrawn = withdrawn_r.scalar()

    return cash_in - cash_out - withdrawn


@router.get("/sections")
async def sections_summary(year: int, month: int | None = None,
                          db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    """Выписано по разделам (заправки/работы/товар) за период — что заработал каждый раздел."""
    def conds(col):
        c = [extract("year", col) == year]
        if month:
            c.append(extract("month", col) == month)
        return c

    # Учёт по ДАТЕ РАБОТЫ: что сделано в этом месяце — то и в этом месяце (как зарплата мастера),
    # даже если счёт выписан позже. Молча закрытую историю (≤ 31.05.2026 без order/doc) НЕ показываем.
    from datetime import date as _d
    CUTOFF = _d(2026, 6, 1)
    eff = func.coalesce(CartridgeRefill.last_date, CartridgeRefill.work_date, CartridgeRefill.first_date)
    in_crm_r = (CartridgeRefill.order_id.isnot(None)) | (CartridgeRefill.document_id.isnot(None)) | (eff >= CUTOFF)
    in_crm_w = (WorkJob.order_id.isnot(None)) | (WorkJob.document_id.isnot(None)) | (WorkJob.date >= CUTOFF)
    in_crm_g = (GoodSale.order_id.isnot(None)) | (GoodSale.document_id.isnot(None)) | (GoodSale.date >= CUTOFF)
    r = (await db.execute(select(func.coalesce(func.sum(CartridgeRefill.price), 0), func.count(CartridgeRefill.id))
         .where(in_crm_r, CartridgeRefill.price.isnot(None), *conds(eff)))).one()
    w = (await db.execute(select(func.coalesce(func.sum(WorkJob.price), 0), func.count(WorkJob.id))
         .where(in_crm_w, WorkJob.price.isnot(None), *conds(WorkJob.date)))).one()
    g = (await db.execute(select(func.coalesce(func.sum(GoodSale.price * func.coalesce(GoodSale.qty, 1)), 0), func.count(GoodSale.id))
         .where(in_crm_g, GoodSale.price.isnot(None), *conds(GoodSale.date)))).one()
    return {
        "refills": {"sum": float(r[0] or 0), "count": int(r[1] or 0)},
        "works": {"sum": float(w[0] or 0), "count": int(w[1] or 0)},
        "goods": {"sum": float(g[0] or 0), "count": int(g[1] or 0)},
    }


@router.post("/cash-register/withdraw")
async def withdraw_cash(
    amount: Decimal = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    balance = await _calc_cash_register(db)
    if balance <= 0:
        return {"ok": False, "message": "Касса пуста"}

    # Если сумма указана — берём её, иначе всю кассу
    withdraw_amount = min(amount, balance) if amount and amount > 0 else balance

    today = date.today()
    withdrawal = CashWithdrawal(date=today, amount=withdraw_amount)
    db.add(withdrawal)

    added_to_salary = False
    if user.role == "worker":
        if today.month == 1:
            prev_year, prev_month = today.year - 1, 12
        else:
            prev_year, prev_month = today.year, today.month - 1

        payment = SalaryPayment(
            year=prev_year,
            month=prev_month,
            date=today,
            amount=withdraw_amount,
            payment_type="cash",
            notes="Забрал из кассы",
        )
        db.add(payment)
        added_to_salary = True

    audit(db, user, "cash_withdraw", "Снятие из кассы" + (" → в зарплату" if added_to_salary else ""), amount=withdraw_amount)
    await db.commit()

    salary_remaining = None
    if added_to_salary:
        from app.routers.salary import _calc_prev_month_balance
        info = await _calc_prev_month_balance(db)
        salary_remaining = info["balance"]

    from app.telegram_bot import notify_cash_withdrawal
    await notify_cash_withdrawal(float(withdraw_amount), user.full_name, added_to_salary, salary_remaining)

    resp = {"ok": True, "amount": float(withdraw_amount), "added_to_salary": added_to_salary}
    if salary_remaining is not None:
        resp["salary_remaining"] = salary_remaining
    return resp


@router.post("/cash-register/set")
async def set_cash_register(
    amount: Decimal = Query(...),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Admin: set the cash register to an exact amount via a correction entry."""
    if amount < 0:
        return {"ok": False, "message": "Сумма не может быть отрицательной"}
    current = await _calc_cash_register(db)
    delta = current - amount  # >0 → withdraw the difference; <0 → add the difference
    if delta != 0:
        db.add(CashWithdrawal(date=date.today(), amount=delta))
        await db.commit()
    return {"ok": True, "amount": float(amount)}


@router.get("/available-years", response_model=list[int])
async def available_years(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(func.distinct(extract("year", Order.date))).order_by(extract("year", Order.date).desc())
    )
    years = [int(row[0]) for row in result.all()]
    from datetime import date as d
    current = d.today().year
    if current not in years:
        years.insert(0, current)
    return years
