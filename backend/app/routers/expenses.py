from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Expense
from app.schemas import ExpenseCreate, ExpenseUpdate, ExpenseResponse
from app.auth import require_admin, get_current_user, User

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.get("", response_model=list[ExpenseResponse])
async def list_expenses(
    month: int | None = None,
    year: int | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = select(Expense).order_by(Expense.date.desc())
    if month:
        q = q.where(extract("month", Expense.date) == month)
    if year:
        q = q.where(extract("year", Expense.date) == year)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=ExpenseResponse, status_code=201)
async def create_expense(
    data: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    expense = Expense(**data.model_dump())
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(expense, key, val)
    await db.commit()
    await db.refresh(expense)
    return expense


@router.delete("/{expense_id}")
async def delete_expense(
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    await db.delete(expense)
    await db.commit()
    return {"ok": True}
