from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Advance, AdvanceDeduction, Client
from app.schemas import AdvanceCreate, AdvanceDeductionCreate, AdvanceResponse, AdvanceDeductionResponse
from app.auth import require_admin, get_current_user, User

router = APIRouter(prefix="/api/advances", tags=["advances"])


def _to_response(adv: Advance) -> AdvanceResponse:
    deducted = sum(d.amount for d in adv.deductions)
    remaining = adv.amount - deducted
    resp = AdvanceResponse.model_validate(adv)
    resp.client_name = adv.client.name if adv.client else None
    resp.remaining = remaining
    resp.deductions = [AdvanceDeductionResponse.model_validate(d) for d in adv.deductions]
    return resp


@router.get("", response_model=list[AdvanceResponse])
async def list_advances(
    active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = (
        select(Advance)
        .options(selectinload(Advance.deductions), selectinload(Advance.client))
        .order_by(Advance.date.desc())
    )
    if active is True:
        q = q.where(Advance.is_spent == False)
    elif active is False:
        q = q.where(Advance.is_spent == True)
    result = await db.execute(q)
    return [_to_response(a) for a in result.scalars().all()]


@router.get("/{advance_id}", response_model=AdvanceResponse)
async def get_advance(
    advance_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Advance)
        .options(selectinload(Advance.deductions), selectinload(Advance.client))
        .where(Advance.id == advance_id)
    )
    adv = result.scalar_one_or_none()
    if not adv:
        raise HTTPException(status_code=404, detail="Advance not found")
    return _to_response(adv)


@router.post("", response_model=AdvanceResponse, status_code=201)
async def create_advance(
    data: AdvanceCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    adv = Advance(**data.model_dump())
    db.add(adv)
    await db.commit()
    result = await db.execute(
        select(Advance)
        .options(selectinload(Advance.deductions), selectinload(Advance.client))
        .where(Advance.id == adv.id)
    )
    return _to_response(result.scalar_one())


@router.post("/{advance_id}/deductions", response_model=AdvanceResponse)
async def add_deduction(
    advance_id: int,
    data: AdvanceDeductionCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Advance)
        .options(selectinload(Advance.deductions), selectinload(Advance.client))
        .where(Advance.id == advance_id)
    )
    adv = result.scalar_one_or_none()
    if not adv:
        raise HTTPException(status_code=404, detail="Advance not found")

    deduction = AdvanceDeduction(advance_id=advance_id, **data.model_dump())
    db.add(deduction)

    deducted = sum(d.amount for d in adv.deductions) + data.amount
    if deducted >= adv.amount:
        adv.is_spent = True

    await db.commit()
    result2 = await db.execute(
        select(Advance)
        .options(selectinload(Advance.deductions), selectinload(Advance.client))
        .where(Advance.id == advance_id)
    )
    return _to_response(result2.scalar_one())


@router.delete("/{advance_id}")
async def delete_advance(
    advance_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Удалить аванс целиком (вместе со списаниями)."""
    adv = await db.get(Advance, advance_id)
    if not adv:
        raise HTTPException(status_code=404, detail="Advance not found")
    await db.execute(delete(AdvanceDeduction).where(AdvanceDeduction.advance_id == advance_id))
    await db.delete(adv)
    await db.commit()
    return {"ok": True}
