from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Boolean, Date, DateTime, Numeric, Text,
    ForeignKey, UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="worker")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(100))
    client_type: Mapped[str] = mapped_column(String(20), nullable=False, default="individual")
    notes: Mapped[str | None] = mapped_column(Text)
    # реквизиты (для счетов организациям) — из UBC/1С
    full_name: Mapped[str | None] = mapped_column(String(300))   # юр. наименование
    inn: Mapped[str | None] = mapped_column(String(20))
    kpp: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(String(300))
    account: Mapped[str | None] = mapped_column(String(40))      # расчётный счёт
    corr_account: Mapped[str | None] = mapped_column(String(40))
    bank: Mapped[str | None] = mapped_column(String(255))
    bik: Mapped[str | None] = mapped_column(String(20))
    director: Mapped[str | None] = mapped_column(String(150))    # директор / отв. лицо
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    orders: Mapped[list["Order"]] = relationship(back_populates="client")
    advances: Mapped[list["Advance"]] = relationship(back_populates="client")


class AuditLog(Base):
    """Журнал важных действий (удаления, деньги) — кто/что/когда."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer)
    username: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(50))
    detail: Mapped[str | None] = mapped_column(String(500))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    default_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    orders: Mapped[list["Order"]] = relationship(back_populates="service")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    amount_cash: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    amount_bank: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    amount_card: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    invoice_number: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    service: Mapped["Service"] = relationship(back_populates="orders")
    client: Mapped["Client"] = relationship(back_populates="orders")
    creator: Mapped["User | None"] = relationship()


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    from_cash_register: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CashWithdrawal(Base):
    __tablename__ = "cash_withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MonthlyCost(Base):
    __tablename__ = "monthly_costs"
    __table_args__ = (UniqueConstraint("year", "month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    salary_admin: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    salary_master: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    rent: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    taxes: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    other: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text)


class Advance(Base):
    __tablename__ = "advances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_spent: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    client: Mapped["Client"] = relationship(back_populates="advances")
    deductions: Mapped[list["AdvanceDeduction"]] = relationship(back_populates="advance", order_by="AdvanceDeduction.date")


class AdvanceDeduction(Base):
    __tablename__ = "advance_deductions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advance_id: Mapped[int] = mapped_column(ForeignKey("advances.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))

    advance: Mapped["Advance"] = relationship(back_populates="deductions")


class SalaryMonth(Base):
    __tablename__ = "salary_months"
    __table_args__ = (UniqueConstraint("year", "month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    refills_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    repairs_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)


class SalaryWork(Base):
    __tablename__ = "salary_works"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    client: Mapped[str | None] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SalaryPayment(Base):
    __tablename__ = "salary_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    payment_type: Mapped[str] = mapped_column(String(20), nullable=False)  # cash, bank, card
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(100), nullable=False)


# ═══════════════ CARTRIDGES (migrated from UBC) ═══════════════

class Manufacturer(Base):
    __tablename__ = "manufacturers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # keeps UBC id
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class CartridgeType(Base):
    __tablename__ = "cartridge_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class CartridgeDefect(Base):
    __tablename__ = "cartridge_defects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class CartridgeWorker(Base):
    __tablename__ = "cartridge_workers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class CartridgeModel(Base):
    __tablename__ = "cartridge_models"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer_id: Mapped[int | None] = mapped_column(ForeignKey("manufacturers.id"))
    type_id: Mapped[int | None] = mapped_column(ForeignKey("cartridge_types.id"))
    norm: Mapped[int | None] = mapped_column(Integer)            # toner norm, grams — reference only
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    weight_empty: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    code_1c: Mapped[str | None] = mapped_column(String(50))      # link to 1С goods


class Cartridge(Base):
    """Cartridge card — a physical cartridge belonging to a client, refilled over time."""
    __tablename__ = "cartridges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)   # keeps UBC CartCards.ID
    barcode: Mapped[str | None] = mapped_column(String(50), index=True)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("cartridge_models.id"))
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), index=True)
    count_do: Mapped[int] = mapped_column(Integer, default=0)
    total_sum: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    is_eternal: Mapped[bool] = mapped_column(Boolean, default=False)
    is_china: Mapped[bool] = mapped_column(Boolean, default=False)
    remark: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)


class CartridgeSpecType(Base):
    """Тип операции по картриджу: заправка / заправка-восстановление (ф/м/р/…) / замена чипа.
    Seeded from UBC TovarsSpecType. is_refill=True → раздел «Заправки», иначе → «Работы»."""
    __tablename__ = "cartridge_spec_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)   # keeps UBC TovarsSpecType.Id
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_refill: Mapped[bool] = mapped_column(Boolean, default=True)   # refill-type → «Заправки»
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class CartridgePrice(Base):
    """Прайс-лист: стандартная цена для модели картриджа × типа операции (ручное переопределение).
    Если записи нет — цена подсказывается из истории (последняя заправка этой модели/типа)."""
    __tablename__ = "cartridge_prices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("cartridge_models.id"), index=True)
    spec_type_id: Mapped[int] = mapped_column(ForeignKey("cartridge_spec_types.id"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (UniqueConstraint("model_id", "spec_type_id", name="uq_cartridge_price"),)


class CartridgeRefill(Base):
    """One refill/work event on a cartridge card (history)."""
    __tablename__ = "cartridge_refills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)   # keeps UBC CartCardsTable.Id
    cartridge_id: Mapped[int] = mapped_column(ForeignKey("cartridges.id"), index=True)
    first_date: Mapped[datetime | None] = mapped_column(DateTime)
    last_date: Mapped[datetime | None] = mapped_column(DateTime)
    work_date: Mapped[datetime | None] = mapped_column(DateTime)
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("cartridge_workers.id"))
    defect_id: Mapped[int | None] = mapped_column(ForeignKey("cartridge_defects.id"))
    spec_id: Mapped[int | None] = mapped_column(Integer)         # raw UBC spec ref (TovarsSpec.Id)
    spec_type_id: Mapped[int | None] = mapped_column(ForeignKey("cartridge_spec_types.id"))  # тип операции
    act_id: Mapped[int | None] = mapped_column(Integer)          # raw UBC document ref (resolve later)
    advice: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(String(255))
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))    # price of this refill/work
    is_billed: Mapped[bool] = mapped_column(Boolean, default=False)  # closed (cash OR invoice)?
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), index=True)  # invoice path
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)  # cash income (Документ не нужен)


# ═══════════════ DOCUMENTS (Документы: счёт/акт/накладная/чек) ═══════════════

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(20), default="invoice")  # invoice/act/waybill/receipt
    number: Mapped[str | None] = mapped_column(String(50))
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), index=True)   # "на основании"
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))       # CRM debt link
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ═══════════════ РАБОТЫ (ремонт техники — НЕ картриджи) ═══════════════

class WorkType(Base):
    """Справочник видов работ: ремонт системника / ремонт МФУ / диагностика / …"""
    __tablename__ = "work_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class WorkJob(Base):
    """Одна работа/ремонт техники для клиента (раздел «Работы»)."""
    __tablename__ = "work_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)   # keeps UBC AppRepair.Id
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), index=True)
    device_label: Mapped[str | None] = mapped_column(String(255))  # "Принтер HP LJ 1102 (s/n …)"
    title: Mapped[str] = mapped_column(String(300), nullable=False)  # описание работы
    date: Mapped[date | None] = mapped_column(Date)
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("cartridge_workers.id"))
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str | None] = mapped_column(String(50))
    remark: Mapped[str | None] = mapped_column(Text)
    is_billed: Mapped[bool] = mapped_column(Boolean, default=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)  # cash income link
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())


class Good(Base):
    """Справочник товаров (номенклатура из 1С)."""
    __tablename__ = "goods"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    category: Mapped[str | None] = mapped_column(String(150))
    unit: Mapped[str] = mapped_column(String(20), default="шт")
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # память цены
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GoodSale(Base):
    """Продажа товара клиенту (раздел «Товар»)."""
    __tablename__ = "good_sales"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), index=True)
    good_id: Mapped[int | None] = mapped_column(ForeignKey("goods.id"))
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=1)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    date: Mapped[date | None] = mapped_column(Date)
    remark: Mapped[str | None] = mapped_column(Text)
    is_billed: Mapped[bool] = mapped_column(Boolean, default=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())


class Organization(Base):
    """Реквизиты своей организации (ИП) для печати документов. Одна строка (id=1)."""
    __tablename__ = "organization"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str | None] = mapped_column(String(255))
    phones: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(127))
    inn: Mapped[str | None] = mapped_column(String(20))
    kpp: Mapped[str | None] = mapped_column(String(20))
    ogrnip: Mapped[str | None] = mapped_column(String(30))
    bank_name: Mapped[str | None] = mapped_column(String(255))
    bank_bik: Mapped[str | None] = mapped_column(String(20))
    bank_account: Mapped[str | None] = mapped_column(String(40))
    bank_corr: Mapped[str | None] = mapped_column(String(40))
    director: Mapped[str | None] = mapped_column(String(255))


class DocumentItem(Base):
    __tablename__ = "document_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="work")   # work / goods
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="шт")
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=1)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    refill_id: Mapped[int | None] = mapped_column(Integer)          # source refill


class AppSetting(Base):
    """Простой key-value для настроек/счётчиков (напр. счётчик печати штрих-кодов label_last)."""
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)


class SyncOp(Base):
    """Идемпотентность офлайн-синхронизации: запоминаем результат каждой записи по op_id,
    чтобы повторная отправка (после потери ответа) не задвоила заправку/счёт/деньги."""
    __tablename__ = "sync_ops"
    op_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[int] = mapped_column(Integer, default=200)
    response: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
