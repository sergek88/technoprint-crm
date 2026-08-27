from __future__ import annotations

import datetime
from decimal import Decimal
from pydantic import BaseModel


# --- Auth ---
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str

    model_config = {"from_attributes": True}


# --- Client ---
class ClientReq(BaseModel):
    full_name: str | None = None
    inn: str | None = None
    kpp: str | None = None
    address: str | None = None
    account: str | None = None
    corr_account: str | None = None
    bank: str | None = None
    bik: str | None = None
    director: str | None = None

class ClientCreate(ClientReq):
    name: str
    phone: str | None = None
    client_type: str = "individual"
    notes: str | None = None

class ClientUpdate(ClientReq):
    name: str | None = None
    phone: str | None = None
    client_type: str | None = None
    notes: str | None = None

class ClientResponse(ClientReq):
    id: int
    name: str
    phone: str | None
    client_type: str
    notes: str | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}

class ClientWithStats(ClientResponse):
    total_orders: int = 0
    total_revenue: Decimal = Decimal("0")
    debt_amount: Decimal = Decimal("0")


# --- Service ---
class ServiceCreate(BaseModel):
    name: str
    default_price: Decimal | None = None

class ServiceUpdate(BaseModel):
    name: str | None = None
    default_price: Decimal | None = None
    is_active: bool | None = None

class ServiceResponse(BaseModel):
    id: int
    name: str
    default_price: Decimal | None
    is_active: bool

    model_config = {"from_attributes": True}


# --- Order ---
class OrderCreate(BaseModel):
    date: datetime.date
    service_id: int | None = None
    service_name: str | None = None
    client_id: int
    amount_cash: Decimal = Decimal("0")
    amount_bank: Decimal = Decimal("0")
    amount_card: Decimal = Decimal("0")
    is_paid: bool = True
    invoice_number: str | None = None
    notes: str | None = None

class OrderUpdate(BaseModel):
    date: datetime.date | None = None
    service_id: int | None = None
    service_name: str | None = None
    client_id: int | None = None
    amount_cash: Decimal | None = None
    amount_bank: Decimal | None = None
    amount_card: Decimal | None = None
    is_paid: bool | None = None
    invoice_number: str | None = None
    notes: str | None = None

class OrderResponse(BaseModel):
    id: int
    date: datetime.date
    service_id: int
    client_id: int
    service_name: str | None = None
    client_name: str | None = None
    amount_cash: Decimal
    amount_bank: Decimal
    amount_card: Decimal
    amount_total: Decimal = Decimal("0")
    is_paid: bool
    paid_at: datetime.datetime | None
    invoice_number: str | None
    notes: str | None
    created_by: int | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# --- Expense ---
class ExpenseCreate(BaseModel):
    date: datetime.date
    category: str | None = None
    description: str
    amount: Decimal
    from_cash_register: bool = False

class ExpenseUpdate(BaseModel):
    date: datetime.date | None = None
    category: str | None = None
    description: str | None = None
    amount: Decimal | None = None
    from_cash_register: bool | None = None

class ExpenseResponse(BaseModel):
    id: int
    date: datetime.date
    category: str | None
    description: str
    amount: Decimal
    from_cash_register: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# --- Monthly Costs ---
class MonthlyCostUpdate(BaseModel):
    salary_admin: Decimal | None = None
    salary_master: Decimal | None = None
    rent: Decimal | None = None
    taxes: Decimal | None = None
    other: Decimal | None = None
    notes: str | None = None

class MonthlyCostResponse(BaseModel):
    id: int
    year: int
    month: int
    salary_admin: Decimal
    salary_master: Decimal
    rent: Decimal
    taxes: Decimal
    other: Decimal
    total: Decimal = Decimal("0")
    notes: str | None

    model_config = {"from_attributes": True}


# --- Advance ---
class AdvanceCreate(BaseModel):
    client_id: int
    date: datetime.date
    amount: Decimal
    notes: str | None = None

class AdvanceDeductionCreate(BaseModel):
    date: datetime.date
    amount: Decimal
    description: str | None = None

class AdvanceDeductionResponse(BaseModel):
    id: int
    date: datetime.date
    amount: Decimal
    description: str | None

    model_config = {"from_attributes": True}

class AdvanceResponse(BaseModel):
    id: int
    client_id: int
    client_name: str | None = None
    date: datetime.date
    amount: Decimal
    is_spent: bool
    remaining: Decimal = Decimal("0")
    notes: str | None
    deductions: list[AdvanceDeductionResponse] = []

    model_config = {"from_attributes": True}


# --- Dashboard ---
class DailySummary(BaseModel):
    date: datetime.date
    order_count: int
    cash: Decimal
    bank: Decimal
    card: Decimal
    total: Decimal
    cash_register: Decimal = Decimal("0")
    orders: list[OrderResponse] = []

class MonthlySummary(BaseModel):
    year: int
    month: int
    order_count: int
    cash: Decimal
    bank: Decimal
    card: Decimal
    revenue: Decimal
    expenses_supplies: Decimal
    expenses_fixed: Decimal
    expenses_total: Decimal
    profit: Decimal
    debt_amount: Decimal

class YearlySummary(BaseModel):
    year: int
    months: list[MonthlySummary]
    total_revenue: Decimal
    total_expenses: Decimal
    total_profit: Decimal
    avg_monthly_profit: Decimal
    total_cash: Decimal


# --- Debts ---
class DebtItem(BaseModel):
    order_id: int
    date: datetime.date
    client_id: int
    client_name: str
    client_phone: str | None
    service_name: str
    amount: Decimal
    days_overdue: int
    invoice_number: str | None

class DebtsByClient(BaseModel):
    client_id: int
    client_name: str
    client_phone: str | None
    total_debt: Decimal
    debts: list[DebtItem]


# --- Salary ---
class SalaryWorkCreate(BaseModel):
    year: int
    month: int
    date: datetime.date
    description: str
    client: str | None = None
    amount: Decimal

class SalaryWorkResponse(BaseModel):
    id: int
    year: int
    month: int
    date: datetime.date
    description: str
    client: str | None
    amount: Decimal
    created_at: datetime.datetime

    model_config = {"from_attributes": True}

class SalaryPaymentCreate(BaseModel):
    year: int
    month: int
    date: datetime.date
    amount: Decimal
    payment_type: str  # cash, bank, card
    notes: str | None = None

class SalaryPaymentResponse(BaseModel):
    id: int
    year: int
    month: int
    date: datetime.date
    amount: Decimal
    payment_type: str
    notes: str | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}

class SalaryResponse(BaseModel):
    year: int
    month: int
    refills_amount: Decimal
    refills_auto: bool = False
    repairs_amount: Decimal
    works: list[SalaryWorkResponse]
    works_total: Decimal
    commission_rate: Decimal
    commission: Decimal
    fixed_salary: Decimal
    payroll_tax: Decimal
    total_accrued: Decimal
    payments: list[SalaryPaymentResponse]
    total_paid: Decimal
    balance: Decimal


# --- Search ---
class SearchResult(BaseModel):
    type: str  # "order", "client", "service"
    id: int
    title: str
    subtitle: str | None = None
