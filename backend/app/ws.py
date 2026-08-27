import json
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, event: str, data: dict):
        message = json.dumps({"event": event, "data": data}, default=str, ensure_ascii=False)
        for ws in self.active[:]:
            try:
                await ws.send_text(message)
            except Exception:
                self.active.remove(ws)


manager = ConnectionManager()
