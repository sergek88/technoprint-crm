from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import MonthlyCost
from app.schemas import MonthlyCostUpdate, MonthlyCostResponse
from app.auth import get_current_user, require_admin, User

router = APIRouter(prefix="/api/monthly-costs", tags=["monthly-costs"])


@router.get("", response_model=list[MonthlyCostResponse])
async def list_monthly_costs(
    year: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MonthlyCost)
        .where(MonthlyCost.year == year)
        .order_by(MonthlyCost.month)
    )
    items = []
    for mc in result.scalars().all():
        resp = MonthlyCostResponse.model_validate(mc)
        resp.total = mc.salary_admin + mc.salary_master + mc.rent + mc.taxes + mc.other
        items.append(resp)
    return items


@router.put("/{year}/{month}", response_model=MonthlyCostResponse)
async def upsert_monthly_cost(
    year: int,
    month: int,
    data: MonthlyCostUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    result = await db.execute(
        select(MonthlyCost).where(MonthlyCost.year == year, MonthlyCost.month == month)
    )
    mc = result.scalar_one_or_none()
    if not mc:
        mc = MonthlyCost(year=year, month=month)
        db.add(mc)
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(mc, key, val)
    await db.commit()
    await db.refresh(mc)
    resp = MonthlyCostResponse.model_validate(mc)
    resp.total = mc.salary_admin + mc.salary_master + mc.rent + mc.taxes + mc.other
    return resp


@router.post("/{year}/{month}/copy-previous", response_model=MonthlyCostResponse)
async def copy_from_previous(
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    result = await db.execute(
        select(MonthlyCost).where(MonthlyCost.year == prev_year, MonthlyCost.month == prev_month)
    )
    prev = result.scalar_one_or_none()
    if not prev:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Previous month not found")

    result2 = await db.execute(
        select(MonthlyCost).where(MonthlyCost.year == year, MonthlyCost.month == month)
    )
    mc = result2.scalar_one_or_none()
    if not mc:
        mc = MonthlyCost(year=year, month=month)
        db.add(mc)
    mc.salary_admin = prev.salary_admin
    mc.salary_master = prev.salary_master
    mc.rent = prev.rent
    mc.taxes = prev.taxes
    mc.other = prev.other
    await db.commit()
    await db.refresh(mc)
    resp = MonthlyCostResponse.model_validate(mc)
    resp.total = mc.salary_admin + mc.salary_master + mc.rent + mc.taxes + mc.other
    return resp
