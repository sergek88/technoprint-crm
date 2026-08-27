"""Хелпер журнала действий. log() добавляет запись в сессию; commit делает вызывающий код."""
from decimal import Decimal
from app.models import AuditLog

ACTION_LABEL = {
    "delete_order": "Удаление заказа",
    "delete_document": "Удаление документа",
    "remove_debt": "Снятие записи из ЦРМ",
    "finalize": "Проведение в ЦРМ",
    "mark_paid": "Отметка «оплачено»",
    "cash_withdraw": "Снятие из кассы",
    "edit_org": "Изменение реквизитов",
    "move_salary_payment": "Перенос выплаты ЗП",
    "receipt_cash": "Тов. чек → наличные",
}


def log(db, user, action: str, detail: str = "", amount=None):
    db.add(AuditLog(
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
        action=action,
        detail=(detail or "")[:500],
        amount=(Decimal(str(amount)) if amount is not None else None),
    ))
