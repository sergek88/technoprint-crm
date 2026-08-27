from contextlib import asynccontextmanager

import jwt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import SECRET_KEY, ALGORITHM
from app.database import init_db
from app.ws import manager
from app.routers import users, auth, orders, clients, services, expenses, monthly_costs, advances, debts, dashboard, search, salary, internal, cartridges, documents, works, org, goods, audit


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    from app.telegram_bot import start_bot, stop_bot
    await start_bot()
    yield
    await stop_bot()


app = FastAPI(title="TechnoPrint CRM", version="1.0.0", lifespan=lifespan)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Дедупликация офлайн-записей: если запрос несёт заголовок X-Op-Id и такой op уже
    выполнялся — возвращаем сохранённый ответ, не выполняя действие повторно.
    Защищает от задвоения денег/счетов при повторной отправке очереди (потеря ответа)."""

    async def dispatch(self, request, call_next):
        op_id = request.headers.get("x-op-id")
        if not op_id or request.method not in ("POST", "PUT", "DELETE"):
            return await call_next(request)

        from app.database import async_session
        from app.models import SyncOp
        from sqlalchemy import select

        # уже выполняли? → отдать прежний ответ
        try:
            async with async_session() as db:
                row = (await db.execute(select(SyncOp).where(SyncOp.op_id == op_id))).scalar_one_or_none()
                if row is not None:
                    return Response(content=row.response or "", status_code=row.status,
                                    media_type="application/json")
        except Exception:
            pass  # таблицы ещё нет / БД недоступна — выполняем как обычно

        resp = await call_next(request)
        body = b""
        async for chunk in resp.body_iterator:
            body += chunk

        if 200 <= resp.status_code < 300:
            try:
                async with async_session() as db:
                    db.add(SyncOp(op_id=op_id, status=resp.status_code,
                                  response=body.decode("utf-8", "ignore")))
                    await db.commit()
            except Exception:
                pass

        headers = dict(resp.headers)
        headers.pop("content-length", None)
        return Response(content=body, status_code=resp.status_code, headers=headers,
                        media_type=resp.media_type)


app.add_middleware(IdempotencyMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tp.fixpo.ru", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(clients.router)
app.include_router(services.router)
app.include_router(expenses.router)
app.include_router(monthly_costs.router)
app.include_router(advances.router)
app.include_router(debts.router)
app.include_router(dashboard.router)
app.include_router(search.router)
app.include_router(salary.router)
app.include_router(internal.router)
app.include_router(cartridges.router)
app.include_router(documents.router)
app.include_router(works.router)
app.include_router(org.router)
app.include_router(goods.router)
app.include_router(audit.router)
app.include_router(users.router)
app.include_router(org.app_info)


@app.websocket("/api/ws")
async def websocket_endpoint(ws: WebSocket):
    # Аутентификация: токен в query (?token=...). Без валидного JWT — отказ.
    token = ws.query_params.get("token", "")
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        await ws.close(code=1008)  # policy violation
        return
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


@app.get("/health")
async def health():
    return {"status": "ok"}
