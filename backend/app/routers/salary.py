import calendar
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import MonthlyCost, SalaryMonth, SalaryPayment, SalaryWork, CartridgeRefill, AppSetting
from app.schemas import (
    SalaryPaymentCreate, SalaryPaymentResponse,
    SalaryWorkCreate, SalaryWorkResponse,
    SalaryResponse,
)
from app.auth import require_admin, get_current_user, User
from app import audit_log

router = APIRouter(prefix="/api/salary", tags=["salary"])

MONTHS_RU = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

# Нейтральные значения по умолчанию: ставки конкретной мастерской не зашиты в код,
# а задаются владельцем в интерфейсе (шестерёнка в разделе «Зарплата») и живут в app_settings.
SALARY_DEFAULTS = {
    "commission_rate": Decimal("0.15"),   # доля с выручки мастера
    "fixed_salary": Decimal("0"),         # оклад
    "fixed_rent": Decimal("0"),           # аренда — попадает в постоянные расходы месяца
    "payroll_tax": Decimal("0"),          # налоги с ЗП
}

# Имя сотрудника в заголовке раздела — тоже настройка, а не константа.
EMPLOYEE_NAME_KEY = "salary_employee_name"
EMPLOYEE_NAME_DEFAULT = "сотрудника"


async def _salary_settings(db: AsyncSession) -> dict:
    rows = dict((await db.execute(
        select(AppSetting.key, AppSetting.value).where(AppSetting.key.like("salary_%")))).all())
    out = {}
    for name, default in SALARY_DEFAULTS.items():
        v = rows.get("salary_" + name)
        try:
            out[name] = Decimal(str(v)) if v is not None else default
        except Exception:
            out[name] = default
    return out


async def _set_salary_setting(db: AsyncSession, name: str, value) -> None:
    key = "salary_" + name
    row = (await db.execute(select(AppSetting).where(AppSetting.key == key))).scalars().first()
    if row:
        row.value = str(value)
    else:
        db.add(AppSetting(key=key, value=str(value)))


async def _get_or_create_sm(db: AsyncSession, year: int, month: int) -> SalaryMonth:
    result = await db.execute(
        select(SalaryMonth).where(SalaryMonth.year == year, SalaryMonth.month == month)
    )
    sm = result.scalar_one_or_none()
    if not sm:
        sm = SalaryMonth(year=year, month=month, refills_amount=Decimal("0"), repairs_amount=Decimal("0"))
        db.add(sm)
        await db.flush()
    return sm


async def _calc_salary(db: AsyncSession, year: int, month: int) -> SalaryResponse:
    sm = await _get_or_create_sm(db, year, month)
    st = await _salary_settings(db)
    COMMISSION_RATE = st["commission_rate"]
    FIXED_SALARY = st["fixed_salary"]
    FIXED_RENT = st["fixed_rent"]
    PAYROLL_TAX = st["payroll_tax"]

    # Service works
    works_q = (
        select(SalaryWork)
        .where(SalaryWork.year == year, SalaryWork.month == month)
        .order_by(SalaryWork.date, SalaryWork.id)
    )
    works = (await db.execute(works_q)).scalars().all()
    works_total = sum(w.amount for w in works)

    # Refills commission base — AUTO from cartridge refills done this month (price sum).
    # Falls back to the manual value for past months whose refills have no price (migration).
    eff_date = func.coalesce(CartridgeRefill.last_date, CartridgeRefill.work_date)
    auto_refills = Decimal(str((await db.execute(
        select(func.coalesce(func.sum(CartridgeRefill.price), 0))
        .where(extract("year", eff_date) == year, extract("month", eff_date) == month)
    )).scalar() or 0))
    refills_auto = auto_refills > 0
    refills_amount = auto_refills if refills_auto else sm.refills_amount

    commission = (refills_amount + works_total) * COMMISSION_RATE
    total_accrued = commission + FIXED_SALARY

    # Payments
    pay_q = (
        select(SalaryPayment)
        .where(SalaryPayment.year == year, SalaryPayment.month == month)
        .order_by(SalaryPayment.date, SalaryPayment.id)
    )
    payments = (await db.execute(pay_q)).scalars().all()
    total_paid = sum(p.amount for p in payments)
    balance = total_accrued - total_paid

    # Side effect: update monthly_costs
    mc_q = select(MonthlyCost).where(MonthlyCost.year == year, MonthlyCost.month == month)
    mc = (await db.execute(mc_q)).scalar_one_or_none()
    if not mc:
        mc = MonthlyCost(year=year, month=month)
        db.add(mc)
    mc.salary_admin = total_accrued + PAYROLL_TAX
    mc.rent = FIXED_RENT
    await db.commit()

    return SalaryResponse(
        year=year,
        month=month,
        refills_amount=refills_amount,
        refills_auto=refills_auto,
        repairs_amount=sm.repairs_amount,
        works=[SalaryWorkResponse.model_validate(w) for w in works],
        works_total=works_total,
        commission_rate=COMMISSION_RATE,
        commission=commission,
        fixed_salary=FIXED_SALARY,
        payroll_tax=PAYROLL_TAX,
        total_accrued=total_accrued,
        payments=[SalaryPaymentResponse.model_validate(p) for p in payments],
        total_paid=total_paid,
        balance=balance,
    )


async def month_balance(db: AsyncSession, year: int, month: int) -> Decimal:
    """Остаток по ЗП за месяц (начислено − выплачено). Только чтение: ничего не создаёт и не коммитит,
    поэтому безопасно вызывать внутри чужой транзакции (см. перевод Коле в documents.py)."""
    st = await _salary_settings(db)
    works_total = Decimal(str((await db.execute(
        select(func.coalesce(func.sum(SalaryWork.amount), 0))
        .where(SalaryWork.year == year, SalaryWork.month == month))).scalar() or 0))
    eff_date = func.coalesce(CartridgeRefill.last_date, CartridgeRefill.work_date)
    auto_refills = Decimal(str((await db.execute(
        select(func.coalesce(func.sum(CartridgeRefill.price), 0))
        .where(extract("year", eff_date) == year, extract("month", eff_date) == month))).scalar() or 0))
    if auto_refills > 0:
        refills_amount = auto_refills
    else:
        sm = (await db.execute(select(SalaryMonth).where(
            SalaryMonth.year == year, SalaryMonth.month == month))).scalars().first()
        refills_amount = (sm.refills_amount if sm and sm.refills_amount else Decimal("0"))
    accrued = (refills_amount + works_total) * st["commission_rate"] + st["fixed_salary"]
    paid = Decimal(str((await db.execute(
        select(func.coalesce(func.sum(SalaryPayment.amount), 0))
        .where(SalaryPayment.year == year, SalaryPayment.month == month))).scalar() or 0))
    return accrued - paid


@router.get("", response_model=SalaryResponse)
async def get_salary(
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await _calc_salary(db, year, month)


# ───────────── гибкие правила зарплаты (настраиваемые ставки) ─────────────
class SalarySettingsIn(BaseModel):
    commission_rate: float | None = None   # доля (0.15 = 15%)
    fixed_salary: float | None = None
    fixed_rent: float | None = None
    payroll_tax: float | None = None
    employee_name: str | None = None       # чьё имя показывать в заголовке раздела


async def _employee_name(db: AsyncSession) -> str:
    row = (await db.execute(select(AppSetting).where(AppSetting.key == EMPLOYEE_NAME_KEY))).scalars().first()
    return (row.value if row and row.value else EMPLOYEE_NAME_DEFAULT)


@router.get("/settings")
async def get_salary_settings(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    st = await _salary_settings(db)
    out = {k: float(v) for k, v in st.items()}
    out["employee_name"] = await _employee_name(db)
    return out


@router.put("/settings")
async def put_salary_settings(body: SalarySettingsIn, db: AsyncSession = Depends(get_db),
                              _admin: User = Depends(require_admin)):
    for name in ("commission_rate", "fixed_salary", "fixed_rent", "payroll_tax"):
        val = getattr(body, name)
        if val is not None:
            if val < 0 or (name == "commission_rate" and val > 1):
                raise HTTPException(400, "Недопустимое значение (процент задаётся долей: 0.15 = 15%)")
            await _set_salary_setting(db, name, val)
    if body.employee_name is not None:
        row = (await db.execute(select(AppSetting).where(AppSetting.key == EMPLOYEE_NAME_KEY))).scalars().first()
        value = body.employee_name.strip()[:100]
        if row:
            row.value = value
        else:
            db.add(AppSetting(key=EMPLOYEE_NAME_KEY, value=value))
    await db.commit()
    st = await _salary_settings(db)
    out = {k: float(v) for k, v in st.items()}
    out["employee_name"] = await _employee_name(db)
    return out


# Имя сотрудника нужно и работнику (заголовок раздела), а /settings — только админу.
@router.get("/employee-name")
async def get_employee_name(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    return {"employee_name": await _employee_name(db)}


@router.put("/amounts")
async def update_amounts(
    year: int,
    month: int,
    refills_amount: Decimal | None = None,
    repairs_amount: Decimal | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    sm = await _get_or_create_sm(db, year, month)
    if refills_amount is not None:
        sm.refills_amount = refills_amount
    if repairs_amount is not None:
        sm.repairs_amount = repairs_amount
    await db.commit()
    return await _calc_salary(db, year, month)


@router.post("/works", response_model=SalaryResponse, status_code=201)
async def add_work(
    data: SalaryWorkCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    work = SalaryWork(
        year=data.year, month=data.month,
        date=data.date, description=data.description,
        client=data.client, amount=data.amount,
    )
    db.add(work)
    await db.commit()
    return await _calc_salary(db, data.year, data.month)


@router.delete("/works/{work_id}", response_model=SalaryResponse)
async def delete_work(
    work_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(SalaryWork).where(SalaryWork.id == work_id))
    work = result.scalar_one_or_none()
    if not work:
        raise HTTPException(status_code=404, detail="Work entry not found")
    year, month = work.year, work.month
    await db.delete(work)
    await db.commit()
    return await _calc_salary(db, year, month)


@router.post("/payments", response_model=SalaryResponse, status_code=201)
async def add_payment(
    data: SalaryPaymentCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    payment = SalaryPayment(
        year=data.year, month=data.month,
        date=data.date, amount=data.amount,
        payment_type=data.payment_type, notes=data.notes,
    )
    db.add(payment)
    await db.commit()
    sal = await _calc_salary(db, data.year, data.month)

    from app.telegram_bot import notify_salary_payment
    pay_names = {"cash": "Наличные", "bank": "Офиц. ЗП", "card": "Перевод"}
    await notify_salary_payment(float(data.amount), pay_names.get(data.payment_type, ""), data.year, data.month, float(sal.balance))

    return sal


class SalaryPaymentMove(BaseModel):
    year: int
    month: int
    shift_date: bool = False   # подтянуть и дату выплаты в целевой месяц (тот же день)


@router.put("/payments/{payment_id}/move", response_model=SalaryResponse)
async def move_payment(
    payment_id: int,
    body: SalaryPaymentMove,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Корректировка: перенести выплату в другой месяц (ЗП встала не в тот месяц)."""
    payment = (await db.execute(
        select(SalaryPayment).where(SalaryPayment.id == payment_id))).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Выплата не найдена")
    if not 1 <= body.month <= 12:
        raise HTTPException(status_code=400, detail="Неверный месяц")
    if not 2000 <= body.year <= 2100:
        raise HTTPException(status_code=400, detail="Неверный год")

    src_year, src_month = payment.year, payment.month
    if (src_year, src_month) == (body.year, body.month):
        raise HTTPException(status_code=400, detail="Выплата уже относится к этому месяцу")

    payment.year, payment.month = body.year, body.month
    if body.shift_date:
        # тот же день в целевом месяце; если такого дня нет (31→февраль) — последний день месяца
        day = min(payment.date.day, calendar.monthrange(body.year, body.month)[1])
        payment.date = date(body.year, body.month, day)

    audit_log.log(
        db, user, "move_salary_payment",
        f"Выплата ЗП от {payment.date.strftime('%d.%m.%Y')}: "
        f"{MONTHS_RU[src_month - 1]} {src_year} → {MONTHS_RU[body.month - 1]} {body.year}",
        payment.amount,
    )
    await db.commit()

    # пересчитать целевой месяц (обновит monthly_costs), вернуть исходный — его смотрит пользователь
    await _calc_salary(db, body.year, body.month)
    return await _calc_salary(db, src_year, src_month)


@router.delete("/payments/{payment_id}", response_model=SalaryResponse)
async def delete_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(SalaryPayment).where(SalaryPayment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    year, month = payment.year, payment.month
    await db.delete(payment)
    await db.commit()
    return await _calc_salary(db, year, month)


async def _calc_prev_month_balance(db: AsyncSession) -> dict:
    """Остаток ЗП за прошлый месяц."""
    today = date.today()
    if today.month == 1:
        prev_year, prev_month = today.year - 1, 12
    else:
        prev_year, prev_month = today.year, today.month - 1

    sal = await _calc_salary(db, prev_year, prev_month)
    return {
        "year": prev_year,
        "month": prev_month,
        "total_accrued": float(sal.total_accrued),
        "total_paid": float(sal.total_paid),
        "balance": float(sal.balance),
    }


@router.get("/prev-month-balance")
async def get_prev_month_balance(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await _calc_prev_month_balance(db)
