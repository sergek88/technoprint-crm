from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Client, Order, Cartridge, WorkJob, GoodSale, Advance, Document
from app.schemas import ClientCreate, ClientUpdate, ClientResponse, ClientWithStats, OrderResponse
from app.auth import get_current_user, User

# таблицы со ссылкой client_id — для подсчёта/переноса при удалении/объединении
_CLIENT_REFS = [Order, Cartridge, WorkJob, GoodSale, Advance, Document]
_REQ_FIELDS = ("full_name", "inn", "kpp", "address", "account", "corr_account", "bank", "bik", "director", "phone")


async def _client_ref_count(db: AsyncSession, client_id: int) -> int:
    total = 0
    for m in _CLIENT_REFS:
        total += (await db.execute(select(func.count()).select_from(m).where(m.client_id == client_id))).scalar() or 0
    return total

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("", response_model=list[ClientWithStats])
async def list_clients(
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = select(Client).order_by(Client.name)
    if search:
        q = q.where(Client.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    clients = result.scalars().all()

    enriched = []
    for c in clients:
        stats = await db.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.amount_cash + Order.amount_bank + Order.amount_card), 0),
                func.coalesce(func.sum(
                    case((Order.is_paid.is_(False), Order.amount_bank + Order.amount_card), else_=Decimal("0"))
                ), 0),
            ).where(Order.client_id == c.id)
        )
        count, revenue, debt = stats.one()
        item = ClientWithStats.model_validate(c)
        item.total_orders = count
        item.total_revenue = revenue
        item.debt_amount = debt
        enriched.append(item)
    return enriched


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    client = Client(**data.model_dump())
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    data: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(client, key, val)
    await db.commit()
    await db.refresh(client)
    return client


@router.delete("/{client_id}")
async def delete_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Удалить клиента. Только если у него нет истории (иначе предложить объединение)."""
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    refs = await _client_ref_count(db, client_id)
    if refs > 0:
        raise HTTPException(status_code=400,
                            detail=f"У клиента есть история ({refs} записей). Объедините его с другим клиентом или удалите записи.")
    await db.delete(client)
    await db.commit()
    return {"ok": True}


@router.post("/{client_id}/merge/{target_id}")
async def merge_client(
    client_id: int,
    target_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Объединить дубль: вся история client_id переносится на target_id, дубль удаляется."""
    if client_id == target_id:
        raise HTTPException(status_code=400, detail="Нельзя объединить клиента с самим собой")
    src = await db.get(Client, client_id)
    tgt = await db.get(Client, target_id)
    if not src or not tgt:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    # перенести все ссылки на целевого клиента
    for m in _CLIENT_REFS:
        await db.execute(update(m).where(m.client_id == client_id).values(client_id=target_id))
    # дозаполнить реквизиты целевого из дубля, если у целевого пусто
    for f in _REQ_FIELDS:
        if not getattr(tgt, f, None) and getattr(src, f, None):
            setattr(tgt, f, getattr(src, f))
    await db.delete(src)
    await db.commit()
    return {"ok": True, "target_id": target_id}


@router.get("/{client_id}/orders", response_model=list[OrderResponse])
async def client_orders(
    client_id: int,
    year: int | None = None,
    limit: int | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = (
        select(Order)
        .where(Order.client_id == client_id)
        .order_by(Order.date.desc())
    )
    if year:
        from sqlalchemy import extract
        q = q.where(extract("year", Order.date) == year)
    if limit:
        q = q.limit(limit)
    result = await db.execute(q)
    orders = result.scalars().all()
    items = []
    for o in orders:
        await db.refresh(o, ["service", "client"])
        item = OrderResponse.model_validate(o)
        item.service_name = o.service.name
        item.client_name = o.client.name
        item.amount_total = o.amount_cash + o.amount_bank + o.amount_card
        items.append(item)
    return items
