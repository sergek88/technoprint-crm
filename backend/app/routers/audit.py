from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_admin, User
from app.models import AuditLog
from app.audit_log import ACTION_LABEL

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
async def list_audit(limit: int = Query(default=200, le=1000),
                     db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    rows = (await db.execute(select(AuditLog).order_by(desc(AuditLog.id)).limit(limit))).scalars().all()
    return [{
        "id": r.id,
        "ts": r.ts.isoformat() if r.ts else None,
        "user": r.username,
        "action": r.action,
        "action_label": ACTION_LABEL.get(r.action, r.action),
        "detail": r.detail,
        "amount": float(r.amount) if r.amount is not None else None,
    } for r in rows]
