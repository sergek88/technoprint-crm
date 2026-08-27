from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Service
from app.schemas import ServiceCreate, ServiceUpdate, ServiceResponse
from app.auth import get_current_user, User

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("", response_model=list[ServiceResponse])
async def list_services(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Service).order_by(Service.name))
    return result.scalars().all()


@router.post("", response_model=ServiceResponse, status_code=201)
async def create_service(
    data: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    service = Service(**data.model_dump())
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service


@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: int,
    data: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(service, key, val)
    await db.commit()
    await db.refresh(service)
    return service
