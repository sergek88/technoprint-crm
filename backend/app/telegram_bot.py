"""
TechnoPrint Telegram Bot — уведомления и команды.

Работает в фоновом режиме вместе с FastAPI.
Уведомления:
  - Новый заказ → сообщение владельцу
  - Итоги дня (20:00)
  - Просроченные долги (09:00)
  - Итоги месяца (1 числа)
Команды:
  /today — итоги за сегодня
  /month — итоги за месяц
  /debts — список долгов
  /year  — годовой итог
Текстовые сообщения:
  "оплатили счет 485"     → пометить счёт оплаченным
  "о 485 486 487"         → массовая оплата счетов
  "товар 5000"            → добавить расход (запчасти/ОЗОН)
  "т 5000 3200"           → несколько расходов сразу
"""

import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

TZ_YEKATERINBURG = timezone(timedelta(hours=5))

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import TG_BOT_TOKEN, TG_ADMIN_CHAT_ID, BANK_COMMISSION, CARD_COMMISSION

logger = logging.getLogger(__name__)

bot: Bot | None = None
tg_app: Application | None = None


def _fmt(n) -> str:
    return f"{round(float(n)):,}".replace(",", " ") + " ₽"


# ═══════════════ NOTIFICATIONS (called from routers) ═══════════════

async def notify_new_order(order_data: dict):
    """Send notification about a new order to the admin."""
    if not bot or not TG_ADMIN_CHAT_ID:
        return
    try:
        service = order_data.get("service_name", "?")
        client = order_data.get("client_name", "?")
        total = Decimal(str(order_data.get("amount_total", 0)))
        cash = Decimal(str(order_data.get("amount_cash", 0)))
        bank = Decimal(str(order_data.get("amount_bank", 0)))
        card = Decimal(str(order_data.get("amount_card", 0)))

        pay_parts = []
        if cash > 0:
            pay_parts.append(f"нал {_fmt(cash)}")
        if bank > 0:
            pay_parts.append(f"безнал {_fmt(bank)}")
        if card > 0:
            pay_parts.append(f"карта {_fmt(card)}")
        pay_str = ", ".join(pay_parts) if pay_parts else _fmt(total)

        is_paid = order_data.get("is_paid", True)
        debt_mark = " ⚠️ ДОЛГ" if not is_paid else ""

        text = f"🧾 Заказ #{order_data.get('id', '?')}: {service} — {client} — {pay_str}{debt_mark}"
        notes = order_data.get("notes", "")
        if notes:
            text += f"\n📝 {notes}"
        await bot.send_message(chat_id=TG_ADMIN_CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"TG notify_new_order error: {e}")


async def notify_cash_withdrawal(amount: float, user_name: str, added_to_salary: bool, salary_remaining: float | None = None):
    """Send notification when someone withdraws cash from register."""
    if not bot or not TG_ADMIN_CHAT_ID:
        return
    try:
        text = f"💰 Касса: {user_name} забрал {_fmt(amount)}"
        if added_to_salary:
            text += " (→ ЗП)"
            if salary_remaining is not None:
                text += f"\n📊 Остаток ЗП: {_fmt(salary_remaining)}"
        await bot.send_message(chat_id=TG_ADMIN_CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"TG notify_cash_withdrawal error: {e}")


async def notify_salary_payment(amount: float, pay_type_name: str, year: int, month: int, balance: float):
    """Send notification when a salary payment is added via CRM."""
    if not bot or not TG_ADMIN_CHAT_ID:
        return
    try:
        month_names = ["Январь","Февраль","Март","Апрель","Май","Июнь",
                       "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
        text = f"💰 Выплата ЗП: {_fmt(amount)} ({pay_type_name}) за {month_names[month-1]}\n📊 Остаток: {_fmt(balance)}"
        await bot.send_message(chat_id=TG_ADMIN_CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"TG notify_salary_payment error: {e}")


async def notify_debt_paid(order_data: dict):
    """Send notification when a debt is paid."""
    if not bot or not TG_ADMIN_CHAT_ID:
        return
    try:
        client = order_data.get("client_name", "?")
        total = Decimal(str(order_data.get("amount_total", 0)))
        text = f"✅ Долг оплачен: {client} — {_fmt(total)}"
        await bot.send_message(chat_id=TG_ADMIN_CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"TG notify_debt_paid error: {e}")


# ═══════════════ COMMANDS ═══════════════

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /today command — daily summary."""
    from app.database import async_session
    from app.models import Order

    from sqlalchemy import select, func

    today = date.today()
    async with async_session() as db:
        result = await db.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.amount_cash), 0),
                func.coalesce(func.sum(Order.amount_bank), 0),
                func.coalesce(func.sum(Order.amount_card), 0),
            ).where(Order.date == today)
        )
        count, cash, bank, card = result.one()

    total = cash + bank + card
    text = (
        f"📊 Итого за {today.strftime('%d.%m.%Y')}:\n"
        f"Заказов: {count}\n"
        f"Нал: {_fmt(cash)}\n"
        f"Безнал: {_fmt(bank)}\n"
        f"Карта: {_fmt(card)}\n"
        f"Всего: {_fmt(total)}"
    )
    await update.message.reply_text(text)


async def cmd_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /month command — monthly summary."""
    from app.database import async_session
    from app.models import Order, Expense, MonthlyCost
    from sqlalchemy import select, func, extract

    today = date.today()
    y, m = today.year, today.month

    async with async_session() as db:
        result = await db.execute(
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
        count, cash, bank, card = result.one()

        bank_net = bank * Decimal(str(1 - BANK_COMMISSION))
        card_net = card * Decimal(str(1 - CARD_COMMISSION))
        revenue = cash + bank_net + card_net

        exp_r = await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                extract("year", Expense.date) == y,
                extract("month", Expense.date) == m,
            )
        )
        exp_supplies = exp_r.scalar()

        mc_r = await db.execute(
            select(MonthlyCost).where(MonthlyCost.year == y, MonthlyCost.month == m)
        )
        mc = mc_r.scalar_one_or_none()
        exp_fixed = Decimal("0")
        if mc:
            exp_fixed = mc.salary_admin + mc.salary_master + mc.rent + mc.taxes + mc.other

        profit = revenue - exp_supplies - exp_fixed

    month_names = ["Январь","Февраль","Март","Апрель","Май","Июнь",
                   "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]

    text = (
        f"📊 {month_names[m-1]} {y}:\n"
        f"Заказов: {count}\n"
        f"Выручка: {_fmt(revenue)}\n"
        f"  Нал: {_fmt(cash)} | Безнал: {_fmt(bank)} | Карта: {_fmt(card)}\n"
        f"Расходы (товар): {_fmt(exp_supplies)}\n"
        f"Расходы (пост.): {_fmt(exp_fixed)}\n"
        f"{'📈' if profit >= 0 else '📉'} Прибыль: {_fmt(profit)}"
    )
    await update.message.reply_text(text)


async def cmd_debts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /debts command — list current debts."""
    from app.database import async_session
    from app.models import Order
    from sqlalchemy import select

    today = date.today()
    async with async_session() as db:
        result = await db.execute(
            select(Order).where(Order.is_paid == False).order_by(Order.date)
        )
        orders = result.scalars().all()

        if not orders:
            await update.message.reply_text("✅ Нет текущих долгов!")
            return

        lines = [f"⚠️ Долги ({len(orders)}):\n"]
        total = Decimal("0")
        for o in orders:
            await db.refresh(o, ["service", "client"])
            amount = o.amount_bank + o.amount_card
            days = (today - o.date).days
            marker = "🔴" if days > 14 else "🟡" if days > 7 else "🟢"
            lines.append(f"{marker} {o.client.name} — {o.service.name} — {_fmt(amount)} ({days} дн.)")
            total += amount

        lines.append(f"\nИтого: {_fmt(total)}")
        await update.message.reply_text("\n".join(lines))


async def cmd_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /year command — yearly summary."""
    from app.database import async_session
    from app.models import Order, Expense, MonthlyCost
    from sqlalchemy import select, func, extract

    y = date.today().year

    async with async_session() as db:
        result = await db.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.amount_cash), 0),
                func.coalesce(func.sum(Order.amount_bank), 0),
                func.coalesce(func.sum(Order.amount_card), 0),
            ).where(extract("year", Order.date) == y)
        )
        count, cash, bank, card = result.one()

        bank_net = bank * Decimal(str(1 - BANK_COMMISSION))
        card_net = card * Decimal(str(1 - CARD_COMMISSION))
        revenue = cash + bank_net + card_net

        exp_r = await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                extract("year", Expense.date) == y,
            )
        )
        exp_supplies = exp_r.scalar()

        mc_r = await db.execute(
            select(func.coalesce(func.sum(
                MonthlyCost.salary_admin + MonthlyCost.salary_master +
                MonthlyCost.rent + MonthlyCost.taxes + MonthlyCost.other
            ), 0)).where(MonthlyCost.year == y)
        )
        exp_fixed = mc_r.scalar()

    total_exp = exp_supplies + exp_fixed
    profit = revenue - total_exp

    text = (
        f"📊 Год {y}:\n"
        f"Заказов: {count}\n"
        f"Выручка: {_fmt(revenue)}\n"
        f"Расходы: {_fmt(total_exp)}\n"
        f"{'📈' if profit >= 0 else '📉'} Прибыль: {_fmt(profit)}"
    )
    await update.message.reply_text(text)


# ═══════════════ TEXT MESSAGE HANDLER ═══════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parse text messages for quick actions. Flexible parsing:
    Payment: 'оплатили 485', 'оплата 485', 'оплачен счет 485' — any word with 'оплат' + number
    Expense: 'заказал 3500', 'товар 3500', 'заказал на 3500' — any word with 'заказ/товар' + number
    """
    if not update.message or not update.message.text:
        return
    if str(update.effective_chat.id) != str(TG_ADMIN_CHAT_ID):
        return

    text = update.message.text.strip().lower()

    # --- Bulk payment: "о 485 486 487" or "о 485,486,487" ---
    m = re.match(r'^о\s+([\d\s,]+)$', text)
    if m:
        numbers = re.split(r'[\s,]+', m.group(1).strip())
        if numbers:
            await _handle_bulk_invoice_paid(update, numbers)
            return

    # --- Payment: any form of "оплат*" + number ---
    m = re.search(r'оплат\w*\s+\D*?(\d+)', text)
    if m:
        invoice = m.group(1)
        await _handle_invoice_paid(update, invoice)
        return

    # --- Salary payment: "зп 5000" ---
    m = re.match(r'^зп\s+(\d+)$', text)
    if m:
        amount = Decimal(m.group(1))
        await _handle_salary_payment(update, amount)
        return

    # --- Cash register expense: "к 5000 3200" ---
    m = re.match(r'^к\s+([\d\s]+)$', text)
    if m:
        numbers = m.group(1).split()
        if numbers:
            await _handle_bulk_expense(update, numbers, from_cash=True)
            return

    # --- Bulk expense: "т 5000 3200 1500" ---
    m = re.match(r'^т\s+([\d\s]+)$', text)
    if m:
        numbers = m.group(1).split()
        if numbers:
            await _handle_bulk_expense(update, numbers)
            return

    # --- Expense: any form of "заказ*" or "товар*" + number ---
    m = re.search(r'(?:заказ|товар)\w*\s+\D*?(\d+)', text)
    if m:
        amount = Decimal(m.group(1))
        await _handle_add_expense(update, amount)
        return


async def _handle_bulk_invoice_paid(update: Update, invoice_numbers: list[str]):
    """Mark multiple invoices as paid at once."""
    from app.database import async_session
    from app.models import Order
    from sqlalchemy import select

    results = []
    async with async_session() as db:
        for inv in invoice_numbers:
            result = await db.execute(
                select(Order).where(Order.invoice_number == inv, Order.is_paid == False)
            )
            order = result.scalar_one_or_none()
            if order:
                order.is_paid = True
                order.paid_at = datetime.now()
                await db.refresh(order, ["client"])
                amount = order.amount_bank + order.amount_card
                results.append(f"✅ {inv} — {order.client.name} — {_fmt(amount)}")
            else:
                result2 = await db.execute(
                    select(Order).where(Order.invoice_number == inv)
                )
                existing = result2.scalar_one_or_none()
                if existing:
                    results.append(f"⏭ {inv} — уже оплачен")
                else:
                    results.append(f"❌ {inv} — не найден")
        await db.commit()

    paid_count = sum(1 for r in results if r.startswith("✅"))
    header = f"Оплата счетов ({paid_count}/{len(invoice_numbers)}):\n\n"
    await update.message.reply_text(header + "\n".join(results))


async def _handle_invoice_paid(update: Update, invoice_number: str):
    """Mark order with given invoice number as paid."""
    from app.database import async_session
    from app.models import Order
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(
            select(Order).where(
                Order.invoice_number == invoice_number,
                Order.is_paid == False,
            )
        )
        order = result.scalar_one_or_none()
        if not order:
            # Maybe already paid or doesn't exist
            result2 = await db.execute(
                select(Order).where(Order.invoice_number == invoice_number)
            )
            existing = result2.scalar_one_or_none()
            if existing:
                await update.message.reply_text(f"Счёт {invoice_number} уже оплачен ✅")
            else:
                await update.message.reply_text(f"❌ Счёт {invoice_number} не найден")
            return

        order.is_paid = True
        order.paid_at = datetime.now()
        await db.refresh(order, ["client", "service"])
        client_name = order.client.name
        amount = order.amount_bank + order.amount_card
        await db.commit()

    await update.message.reply_text(
        f"✅ Счёт {invoice_number} оплачен!\n"
        f"{client_name} — {_fmt(amount)}"
    )


async def _handle_add_expense(update: Update, amount: Decimal, from_cash: bool = False):
    """Add an expense for today."""
    from app.database import async_session
    from app.models import Expense

    today = date.today()
    label = "Из кассы" if from_cash else "ОЗОН"
    async with async_session() as db:
        expense = Expense(
            date=today,
            category="parts",
            description=label,
            amount=amount,
            from_cash_register=from_cash,
        )
        db.add(expense)
        await db.commit()

    icon = "💵" if from_cash else "📦"
    await update.message.reply_text(
        f"{icon} Расход добавлен: {label} — {_fmt(amount)} ({today.strftime('%d.%m.%Y')})"
    )


async def _handle_bulk_expense(update: Update, amounts: list[str], from_cash: bool = False):
    """Add multiple expenses at once."""
    from app.database import async_session
    from app.models import Expense

    today = date.today()
    total = Decimal("0")
    label = "Из кассы" if from_cash else "ОЗОН"
    async with async_session() as db:
        for a in amounts:
            val = Decimal(a)
            db.add(Expense(date=today, category="parts", description=label, amount=val, from_cash_register=from_cash))
            total += val
        await db.commit()

    icon = "💵" if from_cash else "📦"
    if len(amounts) == 1:
        await update.message.reply_text(
            f"{icon} Расход добавлен: {label} — {_fmt(total)} ({today.strftime('%d.%m.%Y')})"
        )
    else:
        lines = [f"{icon} Расходы ({len(amounts)} шт.) на {_fmt(total)}:\n"]
        for a in amounts:
            lines.append(f"• {label} — {_fmt(Decimal(a))}")
        lines.append(f"\n({today.strftime('%d.%m.%Y')})")
        await update.message.reply_text("\n".join(lines))


async def _handle_salary_payment(update: Update, amount: Decimal):
    """Add salary payment for the previous month."""
    from app.database import async_session
    from app.models import SalaryPayment

    today = date.today()
    if today.month == 1:
        prev_year, prev_month = today.year - 1, 12
    else:
        prev_year, prev_month = today.year, today.month - 1

    if amount == Decimal("13550"):
        pay_type = "bank"       # официалка
        pay_label = "Офиц. ЗП"
    else:
        pay_type = "card"       # перевод
        pay_label = "Перевод"

    async with async_session() as db:
        payment = SalaryPayment(
            year=prev_year, month=prev_month,
            date=today, amount=amount,
            payment_type=pay_type, notes="",
        )
        db.add(payment)
        await db.commit()

        # Посчитать остаток
        from app.routers.salary import _calc_salary
        sal = await _calc_salary(db, prev_year, prev_month)

    month_names = ["Январь","Февраль","Март","Апрель","Май","Июнь",
                   "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
    await update.message.reply_text(
        f"💰 Выплата ЗП: {_fmt(amount)} ({pay_label}) за {month_names[prev_month-1]}\n"
        f"📊 Остаток: {_fmt(sal.balance)}"
    )


# ═══════════════ SCHEDULED TASKS ═══════════════

async def daily_summary_task():
    """Send daily summary at 20:00 local time."""
    if not bot or not TG_ADMIN_CHAT_ID:
        return

    from app.database import async_session
    from app.models import Order, Expense, CashWithdrawal
    from sqlalchemy import select, func, not_

    today = datetime.now(TZ_YEKATERINBURG).date()
    async with async_session() as db:
        # Orders today
        result = await db.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.amount_cash), 0),
                func.coalesce(func.sum(Order.amount_bank), 0),
                func.coalesce(func.sum(Order.amount_card), 0),
            ).where(Order.date == today)
        )
        count, cash, bank, card = result.one()

        # Today's expenses
        exp_r = await db.execute(
            select(
                func.count(Expense.id),
                func.coalesce(func.sum(Expense.amount), 0),
            ).where(Expense.date == today)
        )
        exp_count, exp_total = exp_r.one()

        # New debts today
        new_debts_r = await db.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.amount_bank + Order.amount_card), 0),
            ).where(Order.date == today, Order.is_paid == False)
        )
        new_debt_count, new_debt_sum = new_debts_r.one()

        # All debts total
        all_debts_r = await db.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.amount_bank + Order.amount_card), 0),
            ).where(Order.is_paid == False)
        )
        all_debt_count, all_debt_sum = all_debts_r.one()

        # Cash register balance
        cash_in_r = await db.execute(
            select(func.coalesce(func.sum(Order.amount_cash), 0)).where(
                not_(func.lower(func.coalesce(Order.notes, '')).contains('перевод'))
            )
        )
        cash_in = cash_in_r.scalar()
        cash_out_r = await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.from_cash_register == True)
        )
        cash_out = cash_out_r.scalar()
        withdrawn_r = await db.execute(select(func.coalesce(func.sum(CashWithdrawal.amount), 0)))
        register_balance = cash_in - cash_out - withdrawn_r.scalar()

    total = cash + bank + card
    lines = [
        f"🌙 Итог дня ({today.strftime('%d.%m.%Y')}):",
        f"{count} заказов, {_fmt(total)}",
        f"Нал: {_fmt(cash)} | Безнал: {_fmt(bank)} | Карта: {_fmt(card)}",
    ]

    if exp_count > 0:
        lines.append(f"\n💸 Расходы: {_fmt(exp_total)} ({exp_count} шт.)")

    if new_debt_count > 0:
        lines.append(f"\n⚠️ Новые долги: {new_debt_count} на {_fmt(new_debt_sum)}")

    if all_debt_count > 0:
        lines.append(f"📋 Всего долгов: {all_debt_count} на {_fmt(all_debt_sum)}")
    else:
        lines.append("\n✅ Долгов нет")

    lines.append(f"\n💰 Касса: {_fmt(register_balance)}")

    try:
        await bot.send_message(chat_id=TG_ADMIN_CHAT_ID, text="\n".join(lines))
    except Exception as e:
        logger.error(f"daily_summary_task error: {e}")


async def overdue_debts_task():
    """Send all debts notification at 09:00 local time, grouped by urgency."""
    if not bot or not TG_ADMIN_CHAT_ID:
        return

    from app.database import async_session
    from app.models import Order
    from sqlalchemy import select

    today = datetime.now(TZ_YEKATERINBURG).date()
    async with async_session() as db:
        result = await db.execute(
            select(Order).where(Order.is_paid == False).order_by(Order.date)
        )
        orders = result.scalars().all()
        if not orders:
            return

        red, yellow, green = [], [], []
        total = Decimal("0")
        for o in orders:
            await db.refresh(o, ["client"])
            amount = o.amount_bank + o.amount_card
            days = (today - o.date).days
            line = f"• {o.client.name} — {_fmt(amount)}, {days} дн."
            total += amount
            if days > 14:
                red.append(line)
            elif days > 7:
                yellow.append(line)
            else:
                green.append(line)

    lines = [f"📋 Долги: {len(orders)} на {_fmt(total)}\n"]
    if red:
        lines.append(f"🔴 Критично (>14 дн.) — {len(red)}:")
        lines.extend(red[:8])
    if yellow:
        lines.append(f"\n🟡 Внимание (7-14 дн.) — {len(yellow)}:")
        lines.extend(yellow[:8])
    if green:
        lines.append(f"\n🟢 Новые (<7 дн.) — {len(green)}:")
        lines.extend(green[:8])

    try:
        await bot.send_message(chat_id=TG_ADMIN_CHAT_ID, text="\n".join(lines))
    except Exception as e:
        logger.error(f"overdue_debts_task error: {e}")


async def monthly_summary_task():
    """Send monthly summary on the 1st of each month."""
    if not bot or not TG_ADMIN_CHAT_ID:
        return
    from app.database import async_session
    from app.models import Order, Expense, MonthlyCost
    from sqlalchemy import select, func, extract

    # Previous month
    today = datetime.now(TZ_YEKATERINBURG).date()
    prev_month = today.month - 1 if today.month > 1 else 12
    prev_year = today.year if today.month > 1 else today.year - 1

    async with async_session() as db:
        result = await db.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.amount_cash), 0),
                func.coalesce(func.sum(Order.amount_bank), 0),
                func.coalesce(func.sum(Order.amount_card), 0),
            ).where(
                extract("year", Order.date) == prev_year,
                extract("month", Order.date) == prev_month,
            )
        )
        count, cash, bank, card = result.one()
        bank_net = bank * Decimal(str(1 - BANK_COMMISSION))
        card_net = card * Decimal(str(1 - CARD_COMMISSION))
        revenue = cash + bank_net + card_net

        exp_r = await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                extract("year", Expense.date) == prev_year,
                extract("month", Expense.date) == prev_month,
            )
        )
        exp_supplies = exp_r.scalar()
        mc_r = await db.execute(
            select(MonthlyCost).where(MonthlyCost.year == prev_year, MonthlyCost.month == prev_month)
        )
        mc = mc_r.scalar_one_or_none()
        exp_fixed = Decimal("0")
        if mc:
            exp_fixed = mc.salary_admin + mc.salary_master + mc.rent + mc.taxes + mc.other
        profit = revenue - exp_supplies - exp_fixed

    month_names = ["Январь","Февраль","Март","Апрель","Май","Июнь",
                   "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
    text = (
        f"📊 Итоги за {month_names[prev_month-1]} {prev_year}:\n"
        f"Заказов: {count}\n"
        f"Выручка: {_fmt(revenue)}\n"
        f"Расходы: {_fmt(exp_supplies + exp_fixed)}\n"
        f"{'📈' if profit >= 0 else '📉'} Прибыль: {_fmt(profit)}"
    )
    try:
        await bot.send_message(chat_id=TG_ADMIN_CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"monthly_summary_task error: {e}")


async def scheduler_loop():
    """Run scheduled tasks at appropriate times (Yekaterinburg UTC+5)."""
    while True:
        try:
            now = datetime.now(TZ_YEKATERINBURG)
            # Daily summary at 20:00 local
            if now.hour == 20 and now.minute == 0:
                await daily_summary_task()
            # Overdue debts at 09:00
            if now.hour == 9 and now.minute == 0:
                await overdue_debts_task()
            # Monthly summary on 1st at 10:00
            if now.day == 1 and now.hour == 10 and now.minute == 0:
                await monthly_summary_task()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(60)


# ═══════════════ STARTUP ═══════════════

async def start_bot():
    """Initialize and start the Telegram bot."""
    global bot, tg_app

    if not TG_BOT_TOKEN:
        logger.info("TG_BOT_TOKEN not set, skipping Telegram bot")
        return

    try:
        tg_app = Application.builder().token(TG_BOT_TOKEN).build()

        tg_app.add_handler(CommandHandler("today", cmd_today))
        tg_app.add_handler(CommandHandler("month", cmd_month))
        tg_app.add_handler(CommandHandler("debts", cmd_debts))
        tg_app.add_handler(CommandHandler("year", cmd_year))
        async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            chat_id = update.effective_chat.id
            logger.info(f"START from chat_id={chat_id}, user={update.effective_user.first_name}")
            await update.message.reply_text(
                f"🖨 TechnoPrint Bot\n\n"
                f"Ваш chat_id: {chat_id}\n\n"
                f"Команды:\n"
                f"/today — итоги за сегодня\n"
                f"/month — итоги за месяц\n"
                f"/debts — список долгов\n"
                f"/year — годовой итог\n\n"
                f"Текстом (своими словами):\n"
                f"«оплатили 485» — пометить счёт оплаченным\n"
                f"«о 485 486 487» — массовая оплата\n"
                f"«заказал 3500» — добавить расход ОЗОН\n"
                f"«т 5000 3200» — несколько расходов\n"
                f"«к 5000» — расход из кассы\n"
                f"«зп 5000» — выплата ЗП мастеру"
            )
        tg_app.add_handler(CommandHandler("start", cmd_start))
        tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

        bot = tg_app.bot

        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling(drop_pending_updates=True)

        # Start scheduler
        asyncio.create_task(scheduler_loop())

        logger.info("Telegram bot started")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")


async def stop_bot():
    """Stop the Telegram bot gracefully."""
    global tg_app
    if tg_app:
        try:
            await tg_app.updater.stop()
            await tg_app.stop()
            await tg_app.shutdown()
        except Exception as e:
            logger.error(f"Failed to stop Telegram bot: {e}")
